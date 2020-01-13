#!/usr/bin/env python
# -*- coding: utf-8 -*-
from handlers.ansible.api import AnsibleApi
from handlers.ansible.disk_serialization import capacity_convert, sum_capacity
import re
import os
import json
import logging

LOG = logging.getLogger(__name__)


class AnsibleRunApi(object):
    '''
    @description: 
    @param: id 主机ID
    @param: hostinfo [dict=(host="",port="", user="",password="", 
                    ansible_ssh_private_key_file="")]
    @return: 
    '''
    def __init__(self, hostinfo):
        self.response = []
        self.HOSTINFO = hostinfo
        self.Unknown = "Unknown"

    def hanlder_ssh_key(self):
        for host in self.HOSTINFO:
            check_host = host.get("ansible_ssh_private_key_file", None)
            if check_host:
                os.remove(check_host)

    def sys_info(self):
        taskinfo = [dict(module="setup", args="")]
        self.API = AnsibleApi(self.HOSTINFO, taskinfo)
        self.API.run_model()
        api_return = self.API.get_model_result
        for msg in api_return:
            for item in msg:
                data = msg[item]["message"]
                code = msg[item]["code"]
                if code != 0:
                    self.response.append(msg)
                else:
                    # 数据正常解析
                    disk_pattern = re.compile(r"^hd|sd|xvd|vd")
                    data = data["ansible_facts"]
                    ___vendor = data.get("ansible_system_vendor", self.Unknown)
                    ___model = data.get("ansible_product_name", self.Unknown)
                    ___sn = data.get("ansible_product_serial", self.Unknown)

                    for ___cpu_model in data.get("ansible_processor", []):
                        if ___cpu_model.endswith(
                                "GHz") or ___cpu_model.startswith("Intel"):
                            break
                        else:
                            ___cpu_model = self.Unknown
                    ___cpu_model = ___cpu_model[:48]
                    ___cpu_count = data.get("ansible_processor_count", 0)
                    ___cpu_cores = data.get(
                        "ansible_processor_cores", None) or len(
                            data.get('ansible_processor', []))
                    ___cpu_vcpus = data.get("ansible_processor_vcpus", 0)
                    ___memory = "%s%s" % capacity_convert('{} MB'.format(
                        data.get("ansible_memtotal_mb")))

                    disk_info = {}
                    for dev, dev_info in data.get("ansible_devices",
                                                  {}).items():
                        if disk_pattern.match(
                                dev) and dev_info["removable"] == "0":
                            disk_info[dev] = dev_info["size"]

                    ___disk_total = "%s %s" % sum_capacity(disk_info.values())
                    ___disk_info = json.dumps(disk_info)

                    ___os = data.get("ansible_distribution", self.Unknown)
                    ___os_version = data.get("ansible_distribution_version",
                                             self.Unknown)
                    ___os_arch = data.get("ansible_architecture", self.Unknown)
                    ___hostname_raw = data.get("ansible_hostname",
                                               self.Unknown)
                    ___all_ipv4_address = ",".join(
                        data.get("ansible_all_ipv4_addresses"))
                    data = dict(code=0)
                    for key, value in locals().items():
                        if key.startswith("_AnsibleRunApi___"):
                            # data[key.lstrip("_AnsibleRunApi___")] = value
                            data[key.replace("_AnsibleRunApi___", "")] = value
                    self.response.append({item: data})
        self.hanlder_ssh_key()
        return self.response

    def module(self, select_module, args):
        if select_module == "setup":
            self.sys_info()
        else:
            self.author_module(select_module, args)

    def author_module(self, select_module, args):
        """
            select_module: user,authorized_key
        """
        self.args = ""
        for k, v in args.items():
            if self.args:
                self.args = "{} {}={}".format(self.args, k, v)
            else:
                self.args = "{}={}".format(k, v)
        LOG.debug("req_args: %s", self.args)

        taskinfo = [dict(module=select_module, args=self.args)]
        self.API = AnsibleApi(self.HOSTINFO, taskinfo)
        self.API.run_model()
        api_return = self.API.get_model_result
        print(api_return)


if __name__ == "__main__":
    hostinfo = [
        dict(host="192.168.2.132",
             port=22051,
             user="root",
             password="",
             ansible_ssh_private_key_file="~/.ssh/youshumin"),
    ]
    api = AnsibleRunApi(hostinfo)
    # return_data = api.sys_info()
    # print(return_data)
    # args = "name=ceshi1001 password=-18SyrVeFt/xU state=present"

    # module_user
    # args = dict(
    #     name="ceshi1001",
    #     password=
    #     "$6$hoguaS4vbou3jV0k$N/XVOREHpCa7172P3MrlFsC5vDvhUu3S/NPkPxqDgHph.L9VSYXT8AvybWieyWH6oEJM8m9NNM3QRX/s./YNI1",
    #     state="present",
    #     generate_ssh_key=True,
    #     ssh_key_bits=2048)

    # module_authorized_key
    args = dict(
        user="ceshi1001",
        key=
        '{{lookup("file", "/Users/youshumin/Desktop/cuteboy9201/cute_ansible/keys/.new7663b484-ce42-47fc-9af2-ce63ff4799e4.pub")}}',
        manage_dir=True,
        state="present",
    )
    api.module("authorized_key", args)
