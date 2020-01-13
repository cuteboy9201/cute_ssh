#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
@Author: Youshumin
@Date: 2019-10-11 11:24:53
@LastEditors: Please set LastEditors
@LastEditTime: 2019-12-03 14:22:50
@Description: 
'''

import os

debug = os.environ.get("RUN_ENV")

if debug == "prod":
    from configs.cfg import *
else:
    from configs.dev_cfg import *

PATH_APP_ROOT = os.path.abspath(
    os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))))

COOKIE_SECRET = "0wEE^@!TKGwbC0p@nyY4*Cm*8ojzulHC48HT620YJl^zE6qE"
PROJECT_NAME = "CuTeeyes"
ALLOW_HOST = ["http://192.168.2.108:4445", "http://192.168.2.108:8080"]
LOGFILE = "/data/logs/dev_rbac.log"
HOST = "0.0.0.0"
PORT = 18083
