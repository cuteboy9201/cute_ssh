#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
@Author: Youshumin
@Date: 2019-11-13 11:13:01
@LastEditors: Please set LastEditors
@LastEditTime: 2019-12-03 14:16:57
@Description: 
'''
RBAC_NAME = "rbac"
RBAC_DB = "mysql+pymysql://rbac:123456@192.168.2.69:12502/cute_rbac"
RBAC_DB_ECHO = False
ADMIN_LIST = ["youshumin", "superuser"]

MQ_URL = "amqp://admin:admin@192.168.2.132:5672/my_vhost"
# RABBITMQ_CLIENT
MQ_CLIENT_QUEUE = "ansible_queue"
MQ_CLIENT_EXCHANGE = "ansible_exchange"
MQ_CLIENT_ROUTING_KEY = "ansible.client"
# RABBITMQ_SERVER
MQ_SERVER_QUEUE = "return_ansible_queue"
MQ_SERVER_EXCHANGE = "return_ansible_exchange"
MQ_SERVER_ROUTING_KEY = "return_ansible.key"