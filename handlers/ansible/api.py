#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
@Author: Youshumin
@Date: 2019-09-20 20:55:58
@LastEditors: Youshumin
@LastEditTime: 2019-10-11 16:12:06
@Description: 
'''

from collections import namedtuple
from tornado import gen
from ansible import constants as C
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.play import Play
from ansible.plugins.callback import CallbackBase
from ansible.vars.manager import VariableManager

C.HOST_KEY_CHECKING = False


class ModelResultsCollector(CallbackBase):
    def __init__(self, *args, **kwargs):
        super(ModelResultsCollector, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}

    def v2_runner_on_ok(self, result, *args, **kwargs):
        """执行成功"""
        self.host_ok[result._host.get_name()] = result

    def v2_runner_on_unreadchable(self, result, *args, **kwargs):
        """不可达"""
        self.host_unreachable[result._host.get_name()] = result

    def v2_runner_on_failed(self, result, *arfs, **kwargs):
        """执行失败"""
        self.host_failed[result._host.get_name()] = result


class PlayBookResultsCollector(CallbackBase):
    def __init__(self, *args, **kwargs):
        super(PlayBookResultsCollector, self).__init__(*args, **kwargs)
        self.task_ok = {}
        self.task_skipped = {}
        self.task_failed = {}
        self.task_status = {}
        self.task_unreachable = {}

    def v2_runner_on_ok(self, result, *args, **kwargs):
        self.task_ok[result._host.get_name()] = result

    def v2_runner_on_failed(self, result, *args, **kwargs):
        self.task_failed[result._host.get_name()] = result

    def v2_runner_on_unreachable(self, result):
        self.task_unreachable[result._host.get_name()] = result

    def v2_runner_on_skipped(self, result):
        self.task_ok[result._host.get_name()] = result

    def v2_playbook_on_stats(self, stats):
        hosts = sorted(stats.processed.keys())
        for h in hosts:
            t = stats.summarize(h)
            self.task_status[h] = {
                "ok": t['ok'],
                "changed": t['changed'],
                "unreachable": t['unreachable'],
                "skipped": t['skipped'],
                "failed": t['failures']
            }


class AnsibleApi(object):
    def __init__(self, hostinfo, taskinfo=None):
        self.resultinfo = []
        self.taskinfo = taskinfo
        self.hostinfo = hostinfo
        self.host_list = [i.get("host", None) for i in self.hostinfo]
        self.sources = ",".join(self.host_list)
        if len(self.host_list) == 1:
            self.sources += ","
        self.passwords = dict()
        self.callback = None
        self.__initializeData()

    def __initializeData(self):
        Options = namedtuple("Options", [
            "connection", "module_path", "forks", "remote_user",
            "private_key_file", "ssh_common_args", "ssh_extra_args",
            "sftp_extra_args", "scp_extra_args", "become", "become_method",
            "become_user", "verbosity", "check", "diff"
        ])
        self.options = Options(
            connection='smart',
            module_path=['/usr/share/ansible'],
            forks=100,
            remote_user=None,
            private_key_file=None,
            ssh_common_args=None,
            ssh_extra_args=None,
            sftp_extra_args=None,
            scp_extra_args=None,
            become=None,
            become_method="sudo",
            become_user=None,
            verbosity=None,
            check=False,
            diff=False,
        )
        self.loader = DataLoader()

        # 设置本次调用的host_list
        self.inventory = InventoryManager(loader=self.loader,
                                          sources=self.sources)
        # 加载之前的变量
        self.variable_manager = VariableManager(loader=self.loader,
                                                inventory=self.inventory)

        self.__set_hostinfo()

    def __set_hostinfo(self):
        # 设置调用主机认证信息
        for host in self.hostinfo:
            self.inventory.add_host(host.get("host"), port=host.get("port"))
            hostname = self.inventory.get_host(hostname=host.get("host"))
            self.variable_manager.set_host_variable(host=hostname,
                                                    varname='ansible_ssh_pass',
                                                    value=host.get('password'))
            self.variable_manager.set_host_variable(host=hostname,
                                                    varname='ansible_ssh_user',
                                                    value=host.get('user'))
            self.variable_manager.set_host_variable(host=hostname,
                                                    varname='ansible_ssh_port',
                                                    value=host.get('port'))
            if host.get("sudo_pass"):
                self.variable_manager.set_host_variable(
                    host=hostname,
                    varname="ansible_become_user",
                    value=host.get("sudo_user"))
                self.variable_manager.set_host_variable(
                    host=hostname,
                    varname="ansible_become_pass",
                    value=host.get("sudo_pass"))
                self.variable_manager.set_host_variable(
                    host=hostname, varname="ansible_become", value=True)
            if not host.get('password') or host.get('password') == "None":
                self.variable_manager.set_host_variable(
                    host=hostname,
                    varname="ansible_ssh_private_key_file",
                    value=host.get("ansible_ssh_private_key_file"))

    def run_model(self):
        for task in self.taskinfo:
            play_source = dict(name="andible_api_play",
                               hosts=self.host_list,
                               gather_facts="no",
                               tasks=[
                                   dict(action=dict(module=task.get("module"),
                                                    args=task.get("args")))
                               ])
            play = Play().load(play_source,
                               variable_manager=self.variable_manager,
                               loader=self.loader)
            tqm = None
            self.callback = ModelResultsCollector()
            try:
                tqm = TaskQueueManager(
                    inventory=self.inventory,
                    variable_manager=self.variable_manager,
                    loader=self.loader,
                    options=self.options,
                    passwords=self.passwords,
                    stdout_callback="minimal",
                )
                tqm._stdout_callback = self.callback
                result = tqm.run(play)
            except Exception as err:
                import traceback
                print(traceback.print_exc())
            finally:
                if tqm is not None:
                    tqm.cleanup()

    @property
    def get_model_result(self):
        for host, result in self.callback.host_ok.items():
            self.resultinfo.append(
                {host: {
                    "message": result._result,
                    "code": 0
                }})
        for host, result in self.callback.host_unreachable.items():
            self.resultinfo.append(
                {host: {
                    "message": result._result,
                    "code": -1
                }})
        for host, result in self.callback.host_failed.items():
            self.resultinfo.append(
                {host: {
                    "message": result._result,
                    "code": 1
                }})
        return self.resultinfo

    def run_playbook(self, PlayBookPath):
        try:
            self.callback = PlayBookResultsCollector()
            pbex = PlaybookExecutor(playbooks=[PlayBookPath],
                                    inventory=self.inventory,
                                    variable_manager=self.variable_manager,
                                    loader=self.loader,
                                    option=self.options,
                                    passwords=self.passwords)
            pbex._tqm._stdout_callback = self.callback
            pbex.run()
        except Exception as err:
            import traceback
            print(traceback.print_exc())
            return False

    def get_playbook_result(self):
        for host, result in self.callback.host_ok.items():
            self.resultinfo.append(
                {host: {
                    "message": result._result,
                    "code": 0
                }})
        for host, result in self.callback.host_unreachable.items():
            self.resultinfo.append(
                {host: {
                    "message": result._result,
                    "code": -1
                }})
        for host, result in self.callback.host_failed.items():
            self.resultinfo.append(
                {host: {
                    "message": result._result,
                    "code": 1
                }})
        for host, result in self.callback.task_status.items():
            self.resultinfo.append(
                {host: {
                    "message": result._result,
                    "code": 2
                }})

        for host, result in self.callback.task_skipped.items():
            self.resultinfo.append(
                {host: {
                    "message": result._result,
                    "code": 3
                }})
        return self.resultinfo
