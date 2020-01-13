#!/usr/bin/env python
# -*- coding:utf-8 -*-
'''
@Author: YouShumin
@Date: 2019-12-25 10:33:08
@LastEditTime : 2020-01-06 14:43:01
@LastEditors  : YouShumin
@Description: 
@FilePath: /cute_ssh/handlers/test.py
'''

import json
import logging
import socket
import struct
import weakref
from concurrent.futures import ThreadPoolExecutor

import paramiko
import tornado.web
from oslo.web.requesthandler import MixinRequestHandler
from oslo.web.route import route
from tornado import gen
from tornado.gen import coroutine
from tornado.ioloop import IOLoop
from tornado.options import define, options
from tornado.process import cpu_count
from utils.tools import (MixinWebSocketHandler, PrivateKey, SSHClient,
                         is_valid_hostname, is_valid_port, to_int, to_str)
from utils.worker import CLIENT as clients
from utils.worker import Worker, recycle_worker

LOG = logging.getLogger(__name__)
try:
    from types import UnicodeType
except ImportError:
    UnicodeType = str

try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

DELAY = 3
DEFAULT_PORT = 22
UUID_RE = "(?P<id>[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12})"


class InvalidValueError(Exception):
    pass


@route("/ws")
class WsockHandlers(MixinWebSocketHandler):
    def initialize(self):
        self.loop = IOLoop.current()
        super(WsockHandlers, self).initialize()
        self.worker_ref = None

    def open(self):
        self.src_addr = self.get_client_addr()
        LOG.info("Connected from {}:{}".format(*self.src_addr))

        workers = clients.get(self.src_addr[0])
        if not workers:
            self.close(reason="Websocket authentication failed...")
            return

        try:
            worker_id = self.get_value('id')
            LOG.debug("worker_id: {}".format(worker_id))
        except (tornado.web.MissingArgumentError, InvalidValueError) as exce:
            self.close(reason=str(exce))
        else:
            worker = workers.get(worker_id)
            if worker:
                workers[worker_id] = None
                self.set_nodelay(True)
                worker.set_handler(self)
                self.worker_ref = weakref.ref(worker)
                self.loop.add_handler(worker.fd, worker, IOLoop.READ)
            else:
                self.close(reason='Websocket authentication failed.')

    def on_message(self, message):
        worker = self.worker_ref()
        try:
            msg = json.loads(message)
            LOG.debug("Client Send Msg - [{}:{}] {!r}".format(
                self.src_addr[0], self.src_addr[1], message))
            LOG.debug("Client Send Msg Json Data - [{}:{}] {!r}".format(
                self.src_addr[0], self.src_addr[1], msg))
        except JSONDecodeError:
            return

        if not isinstance(msg, dict):
            return

        resize = msg.get('resize')

        if resize and len(resize) == 2:
            try:
                worker.chan.resize_pty(*resize)
            except (TypeError, struct.error, paramiko.SSHException):
                pass

        data = msg.get("data")
        if data and isinstance(data, UnicodeType):
            worker.data_to_dst.append(data)
            worker.on_write()

    def on_close(self):
        LOG.info('Disconnected from {}:{}'.format(*self.src_addr))

        if not self.close_reason:
            self.close_reason = "client disconnected."

        worker = self.worker_ref() if self.worker_ref else None
        if worker:
            worker.close(reason=self.close_reason)


@route("/webssh/")
class RequestGetWebSshClientHandler(MixinRequestHandler):

    executor = ThreadPoolExecutor(max_workers=cpu_count() * 5)

    def initialize(self):
        self.result = dict(id=None, status=None, encoding=None)
        self.loop = IOLoop.current()

    def ssh_connect(self, args):
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        LOG.debug("ssh connect args: {}".format(args))
        dst_addr = args[:2]
        LOG.info("Connecting to {}:{}".format(*dst_addr))
        try:
            ssh.connect(*args, timeout=6)
        except socket.error:
            raise ValueError('Unable to connect to {}:{}'.format(*dst_addr))
        except paramiko.BadAuthenticationType:
            raise ValueError('Bad authentication type.')
        except paramiko.AuthenticationException:
            raise ValueError('Authentication failed.')
        except paramiko.BadHostKeyException:
            raise ValueError('Bad host key.')

        chan = ssh.invoke_shell(term='xterm')
        chan.setblocking(0)
        worker = Worker(self.loop, ssh, chan, dst_addr)
        worker.encoding = self.get_default_encoding(ssh)
        return worker

    def get_default_encoding(self, ssh):
        try:
            _, stdout, _ = ssh.exec_command('locale charmap')
        except paramiko.SSHException:
            result = None
        else:
            result = to_str(stdout.read().strip())

        return result if result else 'utf-8'

    @coroutine
    def get(self):
        self.render("webssh.html", debug=False)

    @coroutine
    def post(self):
        LOG.debug("Connection ID: {}".format(id))

        address_ip = self.get_client_ip()
        prot = 13123
        workers = clients.get(address_ip, {})

        future = self.executor.submit(
            self.ssh_connect,
            ("192.168.2.38", "22", "root", "teeqee@123", None))
        try:
            worker = yield future
        except (ValueError, paramiko.SSHException) as exc:
            import traceback
            LOG.error(traceback.format_exc())
            self.send_fail_json(msg=str(exc))
            return
        else:
            if not workers:
                clients[address_ip] = workers
            worker.src_addr = (address_ip, prot)
            workers[worker.id] = worker
            LOG.info(workers)
            self.loop.call_later(DELAY, recycle_worker, worker)
            self.result.update(id=worker.id, encoding=worker.encoding)
        LOG.info(self.result)
        self.write(self.result)
