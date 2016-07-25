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
    def __call__(cls, *args, **kwargs):
        cached = g.get('redisObjDict', None)
        self = cls.__new__(cls, *args, **kwargs)

        if cached:
            if self.key in g.redisObjDict:
                return g.redisObjDict[self.key]
        else:
            g.redisObjDict = {}

        self.__init__()

        g.redisObjDict[self.key] = self

        return self


class RedisStuff(object):
    __metaclass__ = _RedisMetaclass

    def __new__(cls, key, timeout):
        self = super(RedisStuff, cls).__new__(cls)
        self.key = key
        self.timeout = timeout
        return self

    def __init__(self):
        try:
            initial = self.load(self.key)
            data = self.unserialize(initial)
            super(RedisStuff, self).__init__(data)
            self.new = False
        except (TypeError, ValueError, KeyError):
            super(RedisStuff, self).__init__()
            self.new = True

        self._initial = self.serialize(self)

    @staticmethod
    def load(key):
        val = r.get(key)
        if val is None:
            raise KeyError
        return val

    @staticmethod
    def unserialize(data):
        return json.loads(data)

    def save(self):
        if not self:
            r.delete(self.key)
            return

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

    @property
    def modified(self):
        return self.serialize(self) != self._initial

    def unmanage(self):
        try:
            del g.redisObjDict[self.key]
        except KeyError:
            pass


class RedisDict(RedisStuff, dict):
    pass


class RedisList(RedisStuff, list):
    pass


class ImmutableMixin(object):
    def __init__(self, value=''):
        self._value = value

    def set(self, value):
        self._value = value

    def get(self):
        return self._value

    def __nonzero__(self):
        return bool(self._value)


class RedisCache(RedisStuff, ImmutableMixin):
    def serialize(self, obj):
        return super(RedisCache, self).serialize(obj.get())
