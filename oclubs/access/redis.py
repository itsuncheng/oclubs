#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#

from __future__ import absolute_import, unicode_literals

from redis import Redis
from flask import g
import json


r = Redis(host='localhost', port=6379, db=0)


def done(commit=True):
    if commit:
        for stuff in g.redisObjDict.values():
            stuff.save()
    g.redisObjDict.clear()


class _RedisMetaclass(type):
    def __call__(cls, key, timeout):
        cached = g.get('redisObjDict', None)
        if cached:
            if key in g.redisObjDict:
                return g.redisObjDict[key]
        else:
            g.redisObjDict = {}

        initial = cls.load(key)
        data = cls.unserialize(initial)
        self = super(_RedisMetaclass, cls).__call__(data)
        self.key = key
        self.timeout = timeout
        self._initial = initial

        g.redisObjDict[key] = self

        return self


class RedisStuff(object):
    __metaclass__ = _RedisMetaclass

    @staticmethod
    def load(key):
        val = r.get(key)
        if val is None:
            return ''
        return val

    @staticmethod
    def unserialize(data):
        try:
            return json.loads(data)
        except ValueError:
            return ''

    def save(self):
        dumped = self.serialize(self)
        if self._initial != dumped:
            r.set(self.key, dumped)
        if self.timeout < 0:
            r.persist(self.key)
        else:
            r.expire(self.key, self.timeout)

    @staticmethod
    def serialize(obj):
        return json.dumps(obj)


class RedisDict(RedisStuff, dict):
    pass


class RedisList(RedisStuff, list):
    pass


class RedisCache(RedisStuff):
    def __init__(self, value):
        self._value = value

    def set(self, value):
        self._value = value

    def get(self):
        return self._value

    def serialize(self, obj):
        return super(RedisCache, self).serialize(obj.get())
