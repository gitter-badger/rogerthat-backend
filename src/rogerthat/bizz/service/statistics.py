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

import datetime
import logging

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import xlwt
from babel.dates import format_date

from rogerthat.dal.service import get_identity_statistics
from rogerthat.models import ServiceIdentityStatistic, FlowStatistics
from rogerthat.rpc import users
from rogerthat.to.statistics import ServiceIdentityStatisticsTO, DayStatisticsTO, MenuItemPressTO, FlowStatisticsTO
from mcfw.rpc import returns, arguments


@returns(ServiceIdentityStatisticsTO)
@arguments(service_identity_user=users.User)
def get_statistics(service_identity_user):
    return get_statisticsTO(get_identity_statistics(service_identity_user))


@returns(tuple)
@arguments(service_identity_user=users.User, tags=[unicode], cursor=unicode)
def get_flow_statistics(service_identity_user, tags=None, cursor=None):
    if not tags:
        qry = FlowStatistics.list_by_service_identity_user(service_identity_user)
        qry.with_cursor(cursor)
        return qry.fetch(50), qry.cursor()
    return FlowStatistics.get([FlowStatistics.create_key(tag, service_identity_user) for tag in tags]), None


@returns(ServiceIdentityStatisticsTO)
@arguments(ss=ServiceIdentityStatistic)
def get_statisticsTO(ss):
    sis = ServiceIdentityStatisticsTO()
    gained = list()
    lost = list()
    sis.number_of_users = 0
    menuItemPress = list()
    if ss:
        sis.number_of_users = ss.number_of_users

        now_date_today = datetime.date.today()

        tmp = str(ss.last_entry_day)
        start = datetime.date(int(tmp[0:4]), int(tmp[4:6]), int(tmp[6:8]))
        daysToAdd = 0
        if now_date_today != start:
            daysToAdd = (now_date_today - start).days
            for x in xrange(daysToAdd):
                day_stats = now_date_today - datetime.timedelta(x)
                gained.append(DayStatisticsTO.fromDateAndCount(day_stats, 0))
                lost.append(DayStatisticsTO.fromDateAndCount(day_stats, 0))

        daysAdded = 0
        for i in xrange(len(ss.users_gained)):
            day_stats = now_date_today - datetime.timedelta(i + daysToAdd)
            gained.append(DayStatisticsTO.fromDateAndCount(day_stats, ss.users_gained[len(ss.users_gained) - 1 - i]))
            lost.append(DayStatisticsTO.fromDateAndCount(day_stats, ss.users_lost[len(ss.users_gained) - 1 - i]))
            daysAdded += 1

        daysAdded += daysToAdd
        day_stats = now_date_today - datetime.timedelta(daysAdded)
        gained.append(DayStatisticsTO.fromDateAndCount(day_stats, 0))
        lost.append(DayStatisticsTO.fromDateAndCount(day_stats, 0))

        for i in xrange(len(ss.mip_labels)):
            l = getattr(ss, 'mip_%s' % i)
            mip = MenuItemPressTO()
            mip.data = list()
            mip.name = ss.mip_labels[i]

            for x in range(0, daysToAdd):
                day_stats = now_date_today - datetime.timedelta(x)
                mip.data.append(DayStatisticsTO.fromDateAndCount(day_stats, 0))

            for x in xrange(len(l)):
                day_stats = now_date_today - datetime.timedelta(x + daysToAdd)
                mip.data.append(DayStatisticsTO.fromDateAndCount(day_stats, l[len(l) - 1 - x]))
            menuItemPress.append(mip)

    sis.users_gained = gained
    sis.users_lost = lost
    sis.menu_item_press = menuItemPress
    return sis


@returns(dict)
@arguments(ss=ServiceIdentityStatistic)
def get_statistics_list(ss):
    rr = dict()
    gained = list()
    lost = list()
    if ss:
        rr["labels"] = ss.mip_labels
        rr["number_of_users"] = ss.number_of_users

        now_date_today = datetime.date.today()

        tmp = str(ss.last_entry_day)
        start = datetime.date(int(tmp[0:4]), int(tmp[4:6]), int(tmp[6:8]))
        days_to_add = 0
        if now_date_today != start:
            days_to_add = (now_date_today - start).days
            for x in range(0, days_to_add):
                gained.append(0)
                lost.append(0)

        for i in xrange(len(ss.users_gained)):
            gained.append(ss.users_gained[len(ss.users_gained) - 1 - i])
            lost.append(ss.users_lost[len(ss.users_gained) - 1 - i])

        for i, lbl in enumerate(ss.mip_labels):
            l = getattr(ss, 'mip_%s' % i)
            data = list()

            for x in range(0, days_to_add):
                data.append(0)

            for x in xrange(len(l)):
                data.append(l[len(l) - 1 - x])
            rr[lbl] = data
    else:
        rr["labels"] = list()
        rr["number_of_users"] = 0

    rr["users_gained"] = gained
    rr["users_lost"] = lost
    return rr


def get_flow_statistics_excel(service_identity_user):
    bottom_border = xlwt.Borders()
    bottom_border.top = xlwt.Borders.THIN
    bottom_border.right = xlwt.Borders.THIN
    bottom_border.bottom = xlwt.Borders.THIN
    bottom_border.left = xlwt.Borders.THIN
    bold_border_style = xlwt.XFStyle()
    bold_border_style.font.bold = True
    bold_border_style.borders = bottom_border

    def write_sheet_header(flow_statistic):

        def set_column(column, width):
            messages_sheet.col(column).width = width
            return column + 1

        column = 0
        messages_sheet.write(0, column, '', bold_border_style)
        column = set_column(column, 5000)
        for step in flow_statistic.steps:
            step_name = step.step_id.replace('message_', '').replace('_', ' ').title()
            messages_sheet.write(0, column, step_name, bold_border_style)
            column = set_column(column, 5000)
            for button in step.buttons:
                button_name = button.button_id.replace('button_', '').replace('_',
                                                                              ' ') if button.button_id else 'Roger that'
                messages_sheet.write(0, column, u'%s (%s)' % (step_name, button_name), bold_border_style)
                column = set_column(column, 5000)
            messages_sheet.write(0, column, u'%s (lost)' % step_name, bold_border_style)
            column = set_column(column, 5000)

    book = xlwt.Workbook(encoding="utf-8")
    qry = FlowStatistics.list_by_service_identity_user(service_identity_user)
    has_sheets = False
    while True:
        models = qry.fetch(50)
        if not models:
            break

        for f in models:
            has_sheets = True
            fs = FlowStatisticsTO.from_model(f, FlowStatisticsTO.VIEW_STEPS, 1000, FlowStatisticsTO.GROUP_BY_MONTH)
            try:
                messages_sheet = book.add_sheet(fs.tag.replace('__sln__.', '').replace('_', ' ').title()[0:31])
            except:
                logging.info('skipping flow statistics with tag %s' % fs.tag)
                continue
            # new column per step and per button and also a new column for lost users in this step..
            write_sheet_header(fs)
            months_count = len(fs.steps[0].sent_count)
            for month in xrange(0, months_count):
                column = 0
                row = month + 1
                for step in fs.steps:
                    if column == 0:
                        if len(step.sent_count) == 0:
                            # no statistics for this flow in this month
                            continue

                        row_date = datetime.datetime(step.sent_count[0].year, step.sent_count[0].month, 1)
                        messages_sheet.write(row, column, format_date(row_date, locale='en', format='MMMM YYYY'))
                        column += 1
                    if len(step.sent_count) > month:
                        total_step_sent = step.sent_count[month].count
                    else:
                        total_step_sent = 0
                    total_step_button_presses = 0
                    messages_sheet.write(row, column, total_step_sent)
                    column += 1
                    for button in step.buttons:
                        if len(button.acked_count) > month:
                            button_acked_count = button.acked_count[month].count
                        else:
                            # No statistics for this button for this month yet.
                            button_acked_count = 0

                        messages_sheet.write(row, column, button_acked_count)
                        column += 1
                        # find daystatistic from this month
                        total_step_button_presses += button_acked_count
                    # amount of lost users that gave up on this step (left the flow, pressed 'back')
                    messages_sheet.write(row, column, total_step_sent - total_step_button_presses)
                    column += 1

        qry.with_cursor(qry.cursor())
    if not has_sheets:
        sheet = book.add_sheet('Statistics')
        sheet.write(0, 0, 'No statistics yet')

    excel_file = StringIO()
    book.save(excel_file)
    return excel_file.getvalue()
