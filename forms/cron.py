#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
@Author: Youshumin
@Date: 2019-11-12 17:03:02 
@LastEditors: Youshumin 
@LastEditTime: 2019-11-13 10:33:34
@Description: 
'''
from oslo.form.fields import (BoolField, EmailField, IntegerField, StringField,
                              StringListField)
from oslo.form.form import Form


class CronPostFrom(Form):
    def __init__(self, handler=None):
        self.cron_id = StringField(required=True)
        self.cron_type = StringField(required=True)
        self.cron_body = StringField(required=True)
        self.cron_time_trigger = StringField(required=True)
        self.cron_time_body = StringField(required=True)
        super(CronPostFrom, self).__init__(handler)


class CronPutForm(CronPostFrom):
    def __init__(self, handler=None):
        super(CronPutForm, self).__init__(handler)


class CronDeleteForm(Form):
    def __init__(self, handler=None):
        self.cron_id = StringField(required=True)
        super(CronDeleteForm, self).__init__(handler)


class CronPatchForm(CronDeleteForm):
    def __init__(self, handler=None):
        super(CronPatchForm, self).__init__(handler)


class CronGetForm(Form):
    def __init__(self, handler=None):
        self.pageIndex = StringField(required=True)
        self.pageLimit = StringField(required=True)
        self.cron_id = StringField(required=False)
        super(CronGetForm, self).__init__(handler)
