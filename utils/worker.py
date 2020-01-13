#!/usr/bin/env python
# -*- coding:utf-8 -*-
'''
@Author: YouShumin
@Date: 2019-12-25 10:33:08
@LastEditTime : 2019-12-25 12:05:24
@LastEditors  : YouShumin
@Description: 
@FilePath: /cute_ssh/utils/worker.py
'''
import logging
import tornado.websocket

from tornado.ioloop import IOLoop
from tornado.iostream import _ERRNO_CONNRESET
from tornado.util import errno_from_exception
from utils.tools import InputChar, OutputChar, TtyInputOutputParser

BUF_SIZE = 32 * 1024
CLIENT = {}  # {ip: {id: worker}}
LOG = logging.getLogger(__name__)


def clear_worker(worker, clients):
    ip = worker.src_addr[0]
    workers = clients.get(ip)
    assert worker.id in workers
    workers.pop(worker.id)

    if not worker:
        clients.pop(ip)
        if not clients:
            clients.clear()


def recycle_worker(worker):
    if worker.handler:
        return
    LOG.warning("Recycle worker: {}".format(worker.id))
    worker.close(reason="worker recycled")


class Worker(object):
    def __init__(self, loop, ssh, chan, dst_addr):
        self.loop = loop
        self.ssh = ssh
        self.chan = chan
        self.dst_addr = dst_addr
        self.fd = chan.fileno()
        self.id = str(id(self))
        self.data_to_dst = []
        self.data_pre_dst = []
        self.handler = None
        self.mode = IOLoop.READ
        self.closed = False

        self.command_forbidden = False
        self.input_data = []
        self.output_data = []
        super(Worker, self).__init__()

    def __call__(self, fd, event):
        if event & IOLoop.READ:
            self.on_read()
        if event & IOLoop.WRITE:
            self.on_write()
        if event & IOLoop.ERROR:
            self.close(reason="error event occurred")

    def set_handler(self, handle):
        if not self.handler:
            self.handler = handle

    def update_handler(self, mode):
        if self.mode != mode:
            self.loop.update_handler(self.fd, mode)
            self.mode = mode
        if mode == IOLoop.WRITE:
            self.loop.call_later(0.1, self, self.fd, IOLoop.WRITE)

    def on_read(self):
        LOG.debug("Worker {} on read".format(self.id))
        try:
            data = self.chan.recv(BUF_SIZE)
        except (OSError, IOError) as e:
            LOG.error(e)
            if errno_from_exception(e) in _ERRNO_CONNRESET:
                self.close(reason="chan error on reading")
        else:
            LOG.debug("{!r} form {}:{}".format(data, *self.dst_addr))
            if not data:
                self.close(reason="chan close")
                return
            LOG.debug('{!r} to {}:{}'.format(data, *self.handler.src_addr))
            try:
                self.handler.write_message(data, binary=True)
            except tornado.websocket.WebSocketClosedError:
                self.close(reason='websocket closed')

    def on_write(self):
        LOG.debug("worker {} on write".format(self.id))
        if not self.data_to_dst:
            return

        data = "".join(self.data_to_dst)
        try:
            if self.command_forbidden:
                sent = self.chan.send(InputChar.CTRL_C)
            else:
                sent = self.chan.send(data)
        except (OSError, IOError) as e:
            LOG.error(e)
            if errno_from_exception(e) in _ERRNO_CONNRESET:
                self.close(reason="chan error on writing")
            else:
                self.update_handler(IOLoop.WRITE)
        else:
            self.data_pre_dst = data
            LOG.debug("data_pre_dst: {!r}".format(self.data_pre_dst))
            self.data_to_dst = []

            data = data[sent:]
            if data:
                self.data_to_dst.append(data)
                self.update_handler(IOLoop.WRITE)
            else:
                self.update_handler(IOLoop.READ)

    def close(self, reason=""):
        if self.closed:
            return

        self.closed = True
        LOG.info("close worker {} with reason: {}".format(self.id, reason))
        if self.handler:
            self.loop.remove_handler(self.fd)
            self.handler.close(reason=reason)
        self.chan.close()
        self.ssh.close()
        LOG.info("Connect to {}:{}".format(*self.dst_addr))

        clear_worker(self, CLIENT)