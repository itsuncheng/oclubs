#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#


"""oclubs Base Object."""

from __future__ import absolute_import, unicode_literals

from functools import wraps
import types
from enum import Enum

from flask import Markup

from oclubs.access import database, elasticsearch, redis

# In this file,
# cls refers to BaseObject class
# meta refers to _BaseMetaclass class
# prop refers to an instance of Property or ListProperty
# self refers to an instance of BaseObject

REDIS_CACHE_TIME = 3600 * 24  # 1 day


class Property(object):
    """Descriptor class."""
    def __init__(prop, dbname, ie=None, search=False, rediscached=False,
                 search_require_true=False, error_default=Ellipsis):
        super(Property, prop).__init__()
        prop.dbname = dbname
        prop.imp, prop.exp = _get_ie(ie)
        prop.search = _get_search(search, ie)
        prop.rediscached = rediscached
        prop.search_require_true = search_require_true
        prop.error_default = error_default

    def __get__(prop, self, owner=None):
        if self is None:
            return prop
        if prop.name not in self._cache:
            if prop.rediscached:
                cache = redis.RedisCache(
                    prop._get_redis_key(self), REDIS_CACHE_TIME)
                if not cache.new:
                    data = cache.get()
                else:
                    data = self._data[prop.name]
                    cache.set(data)
            else:
                data = self._data[prop.name]

            try:
                value = prop.imp(data)
            except Exception:
                if prop.error_default is not Ellipsis:
                    value = prop.imp(prop.error_default)
                else:
                    raise
            self._cache[prop.name] = value
        return self._cache[prop.name]

    def __set__(prop, self, value):
        # Proxies can't pass isinstance check
        try:
            value = value._get_current_object()
        except AttributeError:
            pass

        # Make strings simple
        try:
            value = value.strip()
        except AttributeError:
            pass

        self._cache[prop.name] = value

        dbvalue = prop.exp(value)
        if self.is_real:
            if self._dbdata is None:
                self._data

            if dbvalue == self._dbdata[prop.name]:
                return

            self._dbdata[prop.name] = dbvalue

            database.update_row(
                self.table,
                {prop.dbname: dbvalue},
                {self.identifier: self.id}
            )

            if prop.search:
                elasticsearch.update(
                    self.table,
                    self.id,
                    {prop.name: prop.search(value)}
                )

            # FIXME: doesn't support multiple search_require_true
            elif prop.search_require_true:
                if value:
                    self._escreate()
                else:
                    elasticsearch.delete(self.table, self.id)

            if prop.rediscached:
                cache = redis.RedisCache(
                    prop._get_redis_key(self), REDIS_CACHE_TIME)
                cache.set(dbvalue)
        else:
            self._dbdata = self._dbdata or {}
            self._dbdata[prop.name] = dbvalue

    def __delete__(prop, self):
        if prop.name in self._cache:
            del self._cache[prop.name]

        if self.is_real:
            self._dbdata = None
        else:
            if prop.name in self._dbdata:
                del self._dbdata[prop.name]

    def _get_redis_key(prop, self):
        return ':'.join(['cache', self.table, str(self.id), prop.name])


class ListProperty(object):
    """Descriptor class."""
    def __init__(prop, table, this, that, ie=None):
        super(ListProperty, prop).__init__()
        prop.table = table
        prop.this = this
        prop.that = that
        prop.imp, prop.exp = _get_ie(ie)

    def __get__(prop, self, owner=None):
        if self is None:
            return prop
        if prop.name not in self._cache:
            tempdata = database.fetch_onecol(
                prop.table,
                prop.that,
                {prop.this: self.id}
            )
            self._cache[prop.name] = \
                [prop.imp(member) for member in tempdata]

        return self._cache[prop.name]

    def __set__(prop, self, value):
        raise AttributeError("ListProperty is not writable.")

    def __delete__(prop, self):
        if prop.name in self._cache:
            del self._cache[prop.name]


class _BaseMetaclass(type):
    def __new__(meta, name, bases, dct):
        _propsdb = {}
        _esfields = []

        for key, value in dct.items():
            if isinstance(value, Property):
                _propsdb[value.dbname] = key
                if value.search:
                    _esfields.append(key)

                value.name = key
            if isinstance(value, ListProperty):
                value.name = key

        @property
        def _data(self):
            if self._dbdata is None:
                self._dbdata = database.fetch_onerow(
                    self.table,
                    _propsdb,
                    {self.identifier: self.id}
                )

            return self._dbdata

        dct['_data'] = _data

        def create(self, dup_key_update=False):
            if self.is_real:
                raise NotImplementedError
            data = {}
            for key, value in _propsdb.items():
                data[key] = self._dbdata[value]

            if dup_key_update:
                self._id = database.insert_or_update_row(self.table, data,
                                                         data)
            else:
                self._id = database.insert_row(self.table, data)

            if _esfields:
                self._escreate()

            # Reload with newest data from database
            self._dbdata = None
            self._data

            return self

        dct['create'] = create

        if _esfields:
            @classmethod
            def search(cls, query_string, offset=0, size=10):
                ret = elasticsearch.search(query_string, cls.table, _esfields,
                                           offset=offset, size=size)
                for item in ret['results']:
                    item['object'] = cls(item['_id'])

                    item['highlight'] = item.get('highlight', {})
                    for hlfield, hllist in item['highlight'].items():
                        item['highlight'][hlfield] = [
                            Markup(hlhtml) for hlhtml in hllist]

                return ret

            dct['search'] = search

            def _escreate(self):
                _esdata = {}
                for field in _esfields:
                    _esdata[field] = dct[field].search(self._cache[field])

                elasticsearch.create(self.table, self.id, _esdata)

            dct['_escreate'] = _escreate

        return super(_BaseMetaclass, meta).__new__(meta, name, bases, dct)

    def __call__(cls, oid):
        self = type.__call__(cls)
        self._id = int(oid)
        self._dbdata = None
        self._cache = {}
        return self


class BaseObject(object):
    __metaclass__ = _BaseMetaclass

    @property
    def id(self):
        if not self.is_real:
            raise NotImplementedError
        return self._id

    @property
    def is_real(self):
        return self._id > 0

    @property
    def callsign(self):
        return str(self.id) + '_' + self.name.replace(' ', '_')

    @classmethod
    def new(cls):
        return cls(0)

    def __eq__(self, other):
        if not isinstance(other, BaseObject):
            return NotImplemented
        try:
            return self.id == other.id
        except NotImplementedError:
            return NotImplemented

    def __ne__(self, other):
        if not isinstance(other, BaseObject):
            return NotImplemented
        try:
            return self.id != other.id
        except NotImplementedError:
            return NotImplemented

    def __hash__(self):
        return hash(self.id)


def object_proxy(name):
    return lambda oid: getattr(__import__('oclubs').objs, name)(oid)


def _get_ie(ie):
    if isinstance(ie, tuple) and len(ie) == 2:
        imp, exp = __get_ie(ie[0])[0], __get_ie(ie[1])[1]
    else:
        imp, exp = __get_ie(ie)

    return (lambda val: None if val is None else imp(val),
            lambda val: None if val is None else exp(val))


def __get_ie(ie):
    if ie is None:
        imp = exp = lambda val: val
    elif ie is NotImplemented:
        imp = exp = lambda val: NotImplemented
    elif isinstance(ie, basestring):
        imp, exp = object_proxy(ie), lambda val: val.id
    elif isinstance(ie, types.ModuleType):
        imp, exp = ie.loads, ie.dumps
    elif isinstance(ie, type) and issubclass(ie, BaseObject):
        imp, exp = ie, lambda val: val.id
    elif isinstance(ie, type) and issubclass(ie, Enum):
        imp, exp = ie, lambda val: val.value
    elif callable(ie):
        imp = exp = ie

    return imp, exp


def _get_search(search, ie):
    search = __get_search(search, ie)
    if search:
        return lambda val: None if val is None else search(val)


def __get_search(search, ie):
    if search is False:
        return None
    if search is True:
        if isinstance(ie, tuple):
            ie = ie[1]
        return __get_search(ie, False)
    elif search is None:
        return lambda val: val
    elif isinstance(search, basestring):
        if search == 'User':
            return lambda val: val.passportname
        elif search == 'FormattedText':
            return lambda val: val.raw
        else:
            return lambda val: val.name
    elif isinstance(search, type) and issubclass(search, Enum):
        return lambda val: val.format_name
    elif callable(search):
        return search

    return None


def paged_db_read(func):
    def get_pager(limit):
        tempstorage = type(b'tempstorage', (object,), {})

        def pager_fetch(*args, **kwargs):
            f, table, cols, conds = args
            conds = database.expand_cond(conds)
            if limit:
                conds['limit'] = limit

            ret = f(table, cols, conds, _calc_found=True, **kwargs)

            tempstorage.count = database.fetch_info(
                database.RawSQL('FOUND_ROWS()'))

            return ret

        def pager_return(data):
            if limit:
                return tempstorage.count, data

            return data

        return pager_fetch, pager_return

    @wraps(func)
    def decorated_function(*args, **kwargs):
        return func(pager=get_pager(kwargs.pop('limit', None)),
                    *args, **kwargs)

    return decorated_function
