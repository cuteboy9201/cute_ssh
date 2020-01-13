#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
@Author: Youshumin
@Date: 2019-09-21 14:16:04
@LastEditors: Youshumin
@LastEditTime: 2019-10-15 15:24:07
@Description: 
'''
from collections import OrderedDict


def capacity_convert(size, expect='auto', rate=1024):
    """
    :param size: '100MB', '1G'
    :param expect: 'K, M, G, T
    :param rate: Default 1000, may be 1024
    :return:
    """

    rate_mapping = (
        ('K', rate),
        ('KB', rate),
        ('M', rate**2),
        ('MB', rate**2),
        ('G', rate**3),
        ('GB', rate**3),
        ('T', rate**4),
        ('TB', rate**4),
    )

    rate_mapping = OrderedDict(rate_mapping)

    std_size = 0  # To KB
    for unit in rate_mapping:
        if size.endswith(unit):
            try:
                std_size = float(size.strip(unit).strip()) * rate_mapping[unit]
            except ValueError:
                pass

    if expect == 'auto':
        for unit, rate_ in rate_mapping.items():
            if rate > std_size / rate_ >= 1 or unit == "T":
                expect = unit
                break

    if expect not in rate_mapping:
        expect = 'K'

    expect_size = round(std_size / rate_mapping[expect], 1)
    return expect_size, expect


def sum_capacity(cap_list):
    total = 0
    for cap in cap_list:
        size, _ = capacity_convert(cap, expect="K")
        total += size
    total = '{} K'.format(total)
    return capacity_convert(total, expect="auto")
