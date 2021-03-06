#! /usr/bin/env python
# -*- coding: UTF-8 -*-
#

import os
from functools import wraps
from math import ceil
from pyexcel_xlsx import get_data
import re
from StringIO import StringIO
import xlsxwriter
from uuid import uuid4

from Crypto.Cipher import AES
from Crypto import Random

from flask import abort, g, flash, request, url_for, session
from flask_login import current_user, login_required
from werkzeug.datastructures import Headers
from werkzeug.wrappers import Response

import pystache

from oclubs.access.secrets import get_secret
from oclubs.exceptions import NoRow
from oclubs.filters.resfilter import ResFilter, ResFilterConverter
from oclubs.filters.clubfilter import ClubFilter, ClubFilterConverter
from oclubs.filters.roomfilter import RoomFilter, RoomFilterConverter
from oclubs.enums import UserType

with open('/srv/oclubs/oclubs/example.md', 'r') as f:
    markdownexample = f.read().strip()


def download_xlsx(filename, info):
    '''Çreate xlsx file for given info and download it '''
    output = StringIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()
    row_num = 0
    col_num = 0

    for row in info:
        for grid in row:
            worksheet.write(row_num, col_num, grid)
            col_num += 1
        col_num = 0
        row_num += 1
    workbook.close()
    output.seek(0)
    headers = Headers()
    headers.set('Content-Disposition', 'attachment', filename=filename)
    return Response(output.read(), mimetype='application/vnd.openxmlformats-'
                    'officedocument.spreadsheetml.sheet', headers=headers)


def read_xlsx(file, data_type, header):
    '''Read xlsx and return a list of data'''
    raw = get_data(file)
    data = raw[data_type]
    if [d.lower().strip().replace(' ', '') for d in data[0]] != header:
        raise ValueError
    contents = data[1:]
    return contents


def get_callsign_decorator(objtype, kw):
    '''Decorator function'''
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            try:
                item = int(re.match(r'^\d+', kwargs[kw]).group(0))
                item = objtype(item)
                item._data
            except (NameError, AttributeError, OverflowError, NoRow):
                abort(404)
            kwargs[kw] = item
            setattr(g, kw, item)
            return func(*args, **kwargs)

        return decorated_function

    return decorator


def get_callsign(objtype, kw):
    '''Function that returns the object directly'''
    try:
        item = int(re.match(r'^\d+', kw).group(0))
        item = objtype(item)
    except (NameError, AttributeError, OverflowError, NoRow):
        abort(404)
    return item


def special_access_required(func):
    @login_required
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.type != UserType.ADMIN \
                and current_user.type != UserType.CLASSROOM_ADMIN \
                and current_user.type != UserType.CLUB_ADMIN \
                and current_user.type != UserType.DIRECTOR:
            if 'club' in kwargs:
                club = kwargs['club']
            elif 'activity' in kwargs:
                club = kwargs['activity'].club
            else:
                abort(403)  # Admin-only page

            if current_user.type == UserType.TEACHER:
                if current_user != club.teacher:
                    abort(403)
            else:
                if current_user != club.leader:
                    abort(403)
        return func(*args, **kwargs)

    return decorated_function


def require_student_membership(func):
    @login_required
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if 'club' in kwargs:
            club = kwargs['club']
        elif 'activity' in kwargs:
            club = kwargs['activity'].club
        else:
            assert False

        if current_user not in club.members:
            abort(403)

        return func(*args, **kwargs)

    return decorated_function


def require_membership(func):
    @login_required
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.type != UserType.ADMIN:
            if 'club' in kwargs:
                club = kwargs['club']
            elif 'activity' in kwargs:
                club = kwargs['activity'].club
            else:
                assert False

            if current_user not in [club.teacher] + club.members:
                abort(403)

        return func(*args, **kwargs)

    return decorated_function


def require_not_student(func):
    @login_required
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.type == UserType.STUDENT:
            abort(403)

        return func(*args, **kwargs)

    return decorated_function


def require_active_club(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if 'club' in kwargs:
            club = kwargs['club']
        elif 'activity' in kwargs:
            club = kwargs['activity'].club
        else:
            assert False

        if not club.is_active:
            abort(403)

        return func(*args, **kwargs)

    return decorated_function


def require_past_activity(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        activity = kwargs['activity']

        if activity.is_future:
            abort(403)

        return func(*args, **kwargs)

    return decorated_function


def require_future_activity(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        activity = kwargs['activity']

        if not activity.is_future:
            abort(403)

        return func(*args, **kwargs)

    return decorated_function


def fail(msg, group):
    flash(msg, group)
    g.hasfailures = True


def true_or_fail(cond, msg, group):
    if not cond:
        fail(msg, group)


def error_or_fail(cond, exc, msg, group):
    try:
        cond()
    except exc:
        pass
    else:
        fail(msg, group)


def pass_or_fail(cond, exc, msg, group):
    try:
        cond()
    except exc:
        fail(msg, group)


def form_is_valid():
    return not g.get('hasfailures', False)


def _strify(st):
    if isinstance(st, unicode):
        return st.encode('utf-8')
    return str(st)


def encrypt(msg):
    key = get_secret('encrypt_key').decode('hex')
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(key, AES.MODE_CFB, iv)
    return (iv + cipher.encrypt(_strify(msg))).encode('base-64').strip()


def decrypt(msg):
    key = get_secret('encrypt_key').decode('hex')
    msg = msg.strip().decode('base-64')
    iv = msg[:16]
    cipher = AES.new(key, AES.MODE_CFB, iv)
    return cipher.decrypt(msg)[16:]


class Pagination(object):
    def __init__(self, page, per_page, total_count):
        self.page = page
        self.per_page = per_page
        self.total_count = total_count

    @property
    def pages(self):
        return int(ceil(self.total_count / float(self.per_page)))

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    def iter_pages(self, left_edge=2, left_current=3,
                   right_current=4, right_edge=2):
        last = 0
        for num in xrange(1, self.pages + 1):
            if num <= left_edge or \
               (num > self.page - left_current - 1 and
                num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield {'num': None}
                if num == 1 or num == self.pages or abs(self.page - num) < 2:
                    yield {'num': num, 'hide': 0}  # Do not hide in phone
                elif abs(self.page - num) < 3:
                    yield {'num': num, 'hide': 1}  # Hide in phone secondly
                else:
                    yield {'num': num, 'hide': 2}  # Hide in phone firstly
                last = num


def render_email_template(name, parameters):
    with open(os.path.join('/srv/oclubs/oclubs/email_templates/',
                           name + '.mustache'), 'r') as textfile:
        data = textfile.read()

    return pystache.render(data, parameters)


def partition(p, l):
    return reduce(lambda x, y: x[not p(y)].append(y) or x, l, ([], []))


# Setup stuffs
def get_picture(picture, ext='jpg'):
    return url_for('static', filename='images/' + picture + '.' + ext)


def url_for_other_page(page):
    args = request.view_args.copy()
    args.update(request.args)
    args['page'] = page
    return url_for(request.endpoint, **args)


def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = str(uuid4())
    return session['_csrf_token']


def init_app(app):
    app.jinja_env.globals['getpicture'] = get_picture
    app.jinja_env.globals['url_for_other_page'] = url_for_other_page
    app.jinja_env.globals['csrf_token'] = generate_csrf_token
    app.jinja_env.globals['ClubFilter'] = ClubFilter
    app.jinja_env.globals['ResFilter'] = ResFilter
    app.jinja_env.globals['RoomFilter'] = RoomFilter

    app.url_map.converters['clubfilter'] = ClubFilterConverter
    app.url_map.converters['resfilter'] = ResFilterConverter
    app.url_map.converters['roomfilter'] = RoomFilterConverter
