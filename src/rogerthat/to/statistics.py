# -*- coding: utf-8 -*-
# Copyright 2016 Mobicage NV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @@license_version:1.1@@

from collections import defaultdict

from dateutil import relativedelta

from rogerthat.models import FlowStatistics
from rogerthat.to.friends import FriendListResultTO
from rogerthat.utils import is_flag_set
from mcfw.consts import MISSING
from mcfw.properties import long_property, typed_property, unicode_property


class UserStatisticsTO(object):
    user_count = long_property('1')
    service_user_count = long_property('2')
    service_count = long_property('3')

class DayStatisticsTO(object):
    day = long_property('1')
    month = long_property('2')
    year = long_property('3')
    count = long_property('4')

    def __init__(self, day=MISSING, month=MISSING, year=MISSING, count=MISSING):
        if day != MISSING:
            self.day = day
        if month != MISSING:
            self.month = month
        if year != MISSING:
            self.year = year
        if count != MISSING:
            self.count = count

    @staticmethod
    def fromDateAndCount(date, count):
        ds = DayStatisticsTO()
        ds.day = date.day
        ds.month = date.month
        ds.year = date.year
        ds.count = count
        return ds

    def __eq__(self, other):
        return (self.day, self.month, self.year) == (other.day, other.month, other.year)


class MenuItemPressTO(object):
    name = unicode_property('1')
    data = typed_property('2', DayStatisticsTO, True)


class ServiceIdentityStatisticsTO(object):
    number_of_users = long_property('1')
    users_gained = typed_property('2', DayStatisticsTO, True)
    users_lost = typed_property('3', DayStatisticsTO, True)
    menu_item_press = typed_property('4', MenuItemPressTO, True)


class ServiceIdentityStatisticsLoadingTO(object):
    number_of_users = long_property('1')
    users_gained = typed_property('2', DayStatisticsTO, True)
    users_lost = typed_property('3', DayStatisticsTO, True)
    friend_list = typed_property('4', FriendListResultTO, False)
    menu_item_press = typed_property('5', MenuItemPressTO, True)


class FlowStepButtonStatisticsTO(object):
    button_id = unicode_property('1')
    acked_count = typed_property('2', DayStatisticsTO, True)
    # the 'next_step' property is added after FlowStepStatisticsTO is declared (because the classes refer to each other)
    # next_steps = typed_property('3', FlowStepStatisticsTO, True)

    def __init__(self):
        self.button_id = None
        self.acked_count = list()
        self.next_steps = list()

    def get_step(self, step_id):
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None


class FlowStepStatisticsTO(object):
    step_id = unicode_property('1')
    buttons = typed_property('2', FlowStepButtonStatisticsTO, True)
    sent_count = typed_property('3', DayStatisticsTO, True)
    received_count = typed_property('4', DayStatisticsTO, True)
    read_count = typed_property('5', DayStatisticsTO, True)

    def __init__(self):
        self.step_id = None
        self.buttons = list()
        self.sent_count = list()
        self.received_count = list()
        self.read_count = list()

    def get_button(self, btn_id):
        for button in self.buttons:
            if button.button_id == btn_id:
                return button
        return None


# need to set next_step this way because FlowStepButtonStatisticsTO and FlowStepStatisticsTO refer to each other
FlowStepButtonStatisticsTO.next_steps = typed_property('3', FlowStepStatisticsTO, True)


class FlowStatisticsTO(object):
    tag = unicode_property('1')
    flows = typed_property('2', FlowStepStatisticsTO, True, doc='Hierarchical view of steps')
    steps = typed_property('3', FlowStepStatisticsTO, True,
                           doc='Flat view of steps, containing the total sent/received/read/acked counts per day')

    VIEW_FLOWS = 1
    VIEW_STEPS = 2

    GROUP_BY_DAY = u'day'
    GROUP_BY_MONTH = u'month'
    GROUP_BY_YEAR = u'year'

    def get_step(self, step_id):
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    @classmethod
    def from_model(cls, model, views, days=1, group_by=GROUP_BY_DAY):
        if not model:
            return None
        view_flows = is_flag_set(cls.VIEW_FLOWS, views)
        view_steps = is_flag_set(cls.VIEW_STEPS, views)

        flow_stat = cls()
        flow_stat.tag = model.tag
        flow_stat.flows = list()
        flow_stat.steps = list()
        flow_stat_date = model.last_entry_datetime_date

        breadcrumbs = list()
        steps_dict = defaultdict(lambda: (len(breadcrumbs), FlowStepStatisticsTO()))  # { step_id : (depth, step) }

        def count(breadcrumbs, step_id, status, btn_id=None):
            status_list = model.get_status_list(breadcrumbs, step_id, status, btn_id)
            day_stats_dict = dict()
            for days_ago, amount in enumerate(reversed(status_list[-days:])):
                date = flow_stat_date - relativedelta.relativedelta(days=days_ago)
                if group_by == cls.GROUP_BY_MONTH:
                    key = date.year * 100 + date.month
                    day_stats = day_stats_dict.get(key)
                    if day_stats is None:
                        day_stats = day_stats_dict[key] = DayStatisticsTO(day=-1, month=date.month, year=date.year,
                                                                          count=0)
                    day_stats.count += amount
                elif group_by == cls.GROUP_BY_YEAR:
                    key = date.year
                    day_stats = day_stats_dict.get(key)
                    if day_stats is None:
                        day_stats = day_stats_dict[key] = DayStatisticsTO(day=-1, month=-1, year=date.year,
                                                                          count=0)
                    day_stats.count += amount
                else:
                    day_stats_dict[date.year * 10000 + date.month * 100 + date.day] = DayStatisticsTO.fromDateAndCount(
                        date, amount)
            return [v for _, v in sorted(day_stats_dict.iteritems())]

        def add_day_stats(existing_count, count_to_add):
            for day_stats_to_add in count_to_add:
                for existing_day_stats in existing_count:
                    if existing_day_stats == day_stats_to_add:
                        existing_day_stats.count += day_stats_to_add.count
                        break
                else:
                    existing_count.append(day_stats_to_add)
                    existing_count.sort(key=lambda x: (x.year, x.month, x.day))

        def follow_the_flow():
            step_list = list()

            def decode_if_not_unicode(value):
                if isinstance(value, unicode):
                    return value
                return value.decode('utf-8')

            for step_id in model.get_next_step_ids(breadcrumbs):
                sent_count = count(breadcrumbs, step_id, FlowStatistics.STATUS_SENT)
                received_count = count(breadcrumbs, step_id, FlowStatistics.STATUS_RECEIVED)
                read_count = count(breadcrumbs, step_id, FlowStatistics.STATUS_READ)

                if view_flows:
                    step_stat = FlowStepStatisticsTO()
                    step_list.append(step_stat)
                    step_stat.step_id = decode_if_not_unicode(step_id)
                    step_stat.sent_count = sent_count
                    step_stat.received_count = received_count
                    step_stat.read_count = read_count

                if view_steps:
                    total_step_stat = steps_dict[step_id][1]
                    total_step_stat.step_id = decode_if_not_unicode(step_id)
                    for existing_count, count_to_add in ((total_step_stat.sent_count, sent_count),
                                                         (total_step_stat.received_count, received_count),
                                                         (total_step_stat.read_count, read_count)):
                        add_day_stats(existing_count, count_to_add)

                for btn_id in model.get_button_ids(breadcrumbs, step_id, days):
                    breadcrumbs.extend((step_id, btn_id))
                    next_steps = follow_the_flow()
                    breadcrumbs.pop(-1)
                    breadcrumbs.pop(-1)

                    acked_count = count(breadcrumbs, step_id, FlowStatistics.STATUS_ACKED, btn_id)

                    if view_flows:
                        btn_stat = FlowStepButtonStatisticsTO()
                        step_stat.buttons.append(btn_stat)

                        btn_stat.button_id = btn_id and decode_if_not_unicode(btn_id)  # None if None else decoded
                        btn_stat.acked_count = acked_count
                        btn_stat.next_steps = next_steps

                    if view_steps:
                        total_btn_stat = total_step_stat.get_button(btn_id)
                        if not total_btn_stat:
                            total_btn_stat = FlowStepButtonStatisticsTO()
                            total_btn_stat.button_id = btn_id and decode_if_not_unicode(btn_id)  # None if None else decoded
                            total_step_stat.buttons.append(total_btn_stat)
                        add_day_stats(total_btn_stat.acked_count, acked_count)

            return step_list  # empty if not view_flows

        flows = follow_the_flow()

        if view_flows:
            flow_stat.flows = flows

        if view_steps:
            flow_stat.steps = [x[1] for x in sorted(steps_dict.itervalues())]

        return flow_stat


class FlowStatisticsListResultTO(object):
    flow_statistics = typed_property('1', FlowStatisticsTO, True)
    cursor = unicode_property('2')

    @classmethod
    def create(cls, flow_statistics, cursor):
        flow_stats = cls()
        flow_stats.flow_statistics = flow_statistics
        flow_stats.cursor = cursor
        return flow_stats
