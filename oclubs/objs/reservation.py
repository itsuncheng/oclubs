#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#

from oclubs.objs.base import

from __future__ import absolute_import, unicode_literals, division

from datetime import datetime, date, timedelta
import json

from oclubs.access import database
from oclubs.enums import ActivityTime
from oclubs.objs.base import BaseObject, Property, ListProperty, paged_db_read

class Reservation(BaseObject):
    table = 'reservation'
    identifier = 'res_id'
    activity = Property('res_activity', 'Activity')
    classroom = Property('res_classroom')
    SBNeeded = Property('res_SBNeeded', bool)
    SBAppDesc = Property('res_SBAppDesc', bool)
    instructors_approval = Property('res_instructors_approval', bool)
    directors_approval = Property('res_directors_approval', bool)
    SBApp_success = Property('res_SBApp_success', bool)

    def update_SBApp_success(self):
        if instructors_approval and directors_approval:
            SBApp_success = true
            return true

        return false

    def update_instructors_approval(self, is_approved):
        insert = {}
        update = {'res_id': self.id, 'res_instructors_approval': is_approved}
        database.insert_or_update_row('reservation', insert, update)
        is_SBApp_success(self)

    def update_directors_approval(self, is_approved):
        insert = {}
        update = {'res_id': self.id, 'res_directors_approval': is_approved}
        database.insert_or_update_row('reservation', insert, update)
        is_SBApp_success(self)

    @classmethod
    @paged_db_read
    def get_reservations_conditions(cls, times=(), additional_conds=None,
                                    dates=(True, True), room_buildings=(),
                                    SBNeeded=None, instructors_approval=None,
                                    directors_approval=None,
                                    SBApp_success=None, order_by_time=True,
                                    pager=None):
        conds = {}
        if additional_conds:
            conds.update(additional_conds)

        conds['join'] = conds.get('join',[])
        conds['join'].append(('inner', 'activity', [('act_id', 'res_activity')]))
        conds['where'] = conds.get('where', [])
        if isinstance(dates, date):
            conds['where'].append(('=', 'act_date', date_int(dates)))
        elif dates != (True, True):
            start, end = dates

            if start is True:
                conds['where'].append(('<=', 'act_date',
                                       date_int(end or date.today())))
            elif end is True:
                conds['where'].append(('>', 'act_date',
                                       date_int(start or date.today())))
            else:
                start = (start or date.today()) + ONE_DAY
                end = (end or date.today()) + ONE_DAY
                conds['where'].append(('range', 'act_date',
                                       (date_int(start), date_int(end))))

        if times:
            times = [time.value for time in times]
            conds['where'].append(('in', 'act_time', times))

        if room_buildings:
            room_buildings = [room_building.value for room_building in room_buildings]
            conds['join'] = conds.get('join', [])
            conds['join'].append(('inner', 'classroom', [('room_id', 'res_classroom')]))
            conds['where'].append(('in', 'room_building', room_buildings))

        if SBNeeded:
            conds['where'].append(('res_SBNeeded', SBNeeded))
        if instructors_approval:
            conds['where'].append(('res_instructors_approval', instructors_approval))
        if directors_approval:
            conds['where'].append(('res_directors_approval', directors_approval))
        if SBApp_success:
            conds['where'].append(('res_SBApp_success', SBApp_success))

        if order_by_time:
            conds['order'] = conds.get('order', [])
            conds['order'].append(('act_date', False))

        pager_fetch, pager_return = pager

        ret = pager_fetch(database.fetch_onecol, 'reservation', 'res_id', conds,
                        distinct=True)

        ret = [cls(item) for item in ret]

        return pager_return(ret)
