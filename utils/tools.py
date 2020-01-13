#!/usr/bin/env python
# -*- coding:utf-8 -*-
'''
@Author: YouShumin
@Date: 2019-12-25 10:43:54
@LastEditTime : 2019-12-25 11:43:46
@LastEditors  : YouShumin
@Description: 
@FilePath: /cute_ssh/utils/tools.py
'''
import paramiko
import io
import logging
import re
from tornado.websocket import WebSocketHandler
import pyte
import tornado.escape
import tornado.web
from tornado.escape import json_decode
from tornado.options import options
from tornado.util import ObjectDict
try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError
try:
    from types import UnicodeType
except ImportError:
    UnicodeType = str

LOG = logging.getLogger(__name__)


class InvalidValueError(Exception):
    pass


def to_bytes(ustr, encoding='utf-8'):
    if isinstance(ustr, UnicodeType):
        return ustr.encode(encoding)
    return ustr


def is_ip_hostname(hostname):
    it = iter(hostname)
    if next(it) == '[':
        return True
    for ch in it:
        if ch != '.' and not ch.isdigit():
            return False
    return True


def to_int(string):
    try:
        return int(string)
    except (TypeError, ValueError):
        pass


def is_valid_port(port):
    return 0 < port < 65536


def to_bytes(ustr, encoding='utf-8'):
    if isinstance(ustr, UnicodeType):
        return ustr.encode(encoding)
    return ustr


def is_valid_hostname(hostname):
    if hostname[-1] == '.':
        # strip exactly one dot from the right, if present
        hostname = hostname[:-1]
    if len(hostname) > 253:
        return False

    labels = hostname.split('.')
    numeric = re.compile(r'[0-9]+$')
    # the TLD must be not all-numeric
    if numeric.match(labels[-1]):
        return False


def to_str(bstr, encoding='utf-8'):
    if isinstance(bstr, bytes):
        return bstr.decode(encoding)
    return bstr


class InputChar(object):
    ENTER_CHAR = ["\r", "\n", "\år\n"]
    BELL_CHAR = b'\x07'
    TAB_CHAR = b"\t"
    DELETE_CHAR = b"\x7f"
    CTRL_C = b'\x03'


class OutputChar(object):
    BELL_CHAR = b'\x07'
    DELETE_CHAR = b'\x08\x1b[K'


class TtyInputOutputParser(object):
    def __init__(self):
        self.screen = pyte.Screen(80, 24)
        self.stream = pyte.ByteStream()
        self.stream.attach(self.screen)
        self.ps1_pattern = re.compile(r'^\[?.*@.*\]?[\$#]\s|mysql>\s')

    def clean_ps1_etc(self, command):
        return self.ps1_pattern.sub('', command)

    def parse_output(self, data, sep="\n"):
        pass

    def parse_input(self, data):
        command = []

        for item in data:
            LOG.debug("feed数据: {}".format(item))
            self.stream.feed(item)
        LOG.debug("screen_display数据为: {}".format(self.screen.display))

        for line in self.screen.display:
            line = line.strip()
            if line:
                command.append(line)
        if command:
            command = command[-1]
        else:
            command = ""
        self.screen.reset()
        command = self.clean_ps1_etc(command)
        return command.strip()


class MixinWebSocketHandler(WebSocketHandler):

    custom_headers = {'Server': 'TornadoServer'}

    html = ('<html><head><title>{code} {reason}</title></head><body>{code} '
            '{reason}</body></html>')

    def initialize(self):
        self.check_request()
        return super(MixinWebSocketHandler, self).initialize()

    def check_request(self):
        context = self.request.connection.context
        # result = self.is_forbidden(context, self.request.host_name)
        # result = self.is_forbidden(context, "192.168.2.1")
        self._transforms = []

        # if result:
        #     self.set_status(403)
        #     self.finish(
        #         self.html.format(code=self._status_code, reason=self._reason))
        # else:
        self.context = context

    def is_forbidden(self, context, hostname):
        ip = context.address[0]
        lst = context.trusted_downstream
        ip_address = None

        if lst and ip not in lst:
            LOG.warning('IP {!r} not found in trusted downstream {!r}'.format(
                ip, lst))
            return True

    def get_value(self, name):
        value = self.get_argument(name)
        if not value:
            raise InvalidValueError('Missing value {}'.format(name))
        return value

    def get_client_addr(self):
        if options.xheaders:
            return self.get_real_client_addr() or self.context.address
        else:
            return self.context.address

    def get_real_client_addr(self):
        ip = self.request.remote_ip

        if ip == self.request.headers.get('X-Real-Ip'):
            port = self.request.headers.get('X-Real-Port')
        elif ip in self.request.headers.get('X-Forwarded-For', ''):
            port = self.request.headers.get('X-Forwarded-Port')
        else:
            return

        port = to_int(port)
        if port is None or not is_valid_port(port):
            port = 65535

        return (ip, port)


class SSHClient(paramiko.SSHClient):
    def handler(self, title, instructions, prompt_list):
        answers = []
        for prompt_, _ in prompt_list:
            prompt = prompt_.strip().lower()
            if prompt.startswith('password'):
                answers.append(self.password)
            elif prompt.startswith("verification"):
                answers.append(self.totp)
            else:
                raise ValueError("Unknown prompt: {}".format(prompt_))
            return answers

    def auth_interactive(self, username, handler):
        if not self.totp:
            raise ValueError('Need a verification code for 2fa.')
        self._transport.auth_interactive(username, handler)

    def _auth(self, username, password, pkey, *args):

        self.password = password
        saved_exception = None
        two_factor = False
        allowed_types = set()
        two_factor_types = {"keyboard-interactive", "password"}

        if pkey is not None:
            LOG.info("Tryint publickey authentication")
            try:
                allowed_types = set(
                    self._transport.auth_publickey(username, pkey))
                two_factor = allowed_types & two_factor_types
                if not two_factor:
                    return
            except paramiko.SSHException as e:
                saved_exception = e

        if two_factor:
            LOG.info("Trying publickey 2fa")
            return self.auth_interactive(username, self.handler)

        if password is not None:
            LOG.info("Trying password authentication")
            try:
                self._transport.auth_password(username, password)
                return
            except paramiko.SSHException as e:
                saved_exception = e
                allowed_types = set(getattr(e, 'allow_types', []))
                two_factor = allowed_types & two_factor_types

        if two_factor:
            LOG.info("Trying password 2fa")
            return self.auth_interactive(username, self.handler)

        assert saved_exception is not None
        raise saved_exception


class PrivateKey(object):

    max_length = 16384

    tag_to_name = {
        "RSA": "RSA",
        "DSA": "DSS",
        "EC": "ECDSA",
        "OPENSSH": "Ed25519"
    }

    def __init__(self, privatekey, password=None, filename=""):
        self.privatekey = privatekey
        self.filename = filename
        self.password = password
        self.check_length()
        self.iostr = io.StringIO(privatekey)

    def check_length(self):
        if len(self.privatekey) > self.max_length:
            InvalidValueError('Invalid key length.')

    def parse_name(self, iostr, tag_to_name):
        name = None
        for line_ in iostr:
            line = line_.strip()
            if line and line.startswith('-----BEGIN ') and \
                    line.endswith(' PRIVATE KEY-----'):
                lst = line.split(' ')
                if len(lst) == 4:
                    tag = lst[1]
                    if tag:
                        name = tag_to_name.get(tag)
                        if name:
                            break
        return name, len(line_)