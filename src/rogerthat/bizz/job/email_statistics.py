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
import email.encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import xlwt
from google.appengine.ext import db

from mcfw.rpc import arguments
from rogerthat.bizz.job import run_job
from rogerthat.bizz.service.statistics import get_statistics, get_statistics_list
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.service import get_service_idenities_by_send_email_statistics, get_service_menu_items, \
    get_service_identities, get_identity_statistics
from rogerthat.models import ServiceIdentity
from rogerthat.settings import get_server_settings
from rogerthat.templates import render
from rogerthat.utils import send_mail_via_mime

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

@arguments()
def schedule_email_statistics():
    run_job(get_service_idenities_by_send_email_statistics, [], _email_statistics, [])

@arguments(si=ServiceIdentity)
def _email_statistics(si):
    def trans():
        admin_emails = si.metaData
        if admin_emails:
            default_language = get_service_profile(si.service_user).defaultLanguage
            settings = get_server_settings()
            sisTO = get_statistics(si.user)
            if len(sisTO.users_gained) >= 8:
                _send_statistics_for_service_identity_user(si, admin_emails, default_language, settings, sisTO)
            if si.is_default:
                _send_statistics_for_service_user(si, admin_emails, default_language, settings)

    db.run_in_transaction(trans)

def _usage_compare(x, y):
    c = cmp(y['count'], x['count'])  # biggest count first
    if c == 0:
        return cmp(x['name'].lower(), y['name'].lower())
    return c

def _send_statistics_for_service_identity_user(si, admin_emails, default_language, settings, sisTO):
    stats_usage = list()
    for i in sisTO.menu_item_press:
        count = 0
        max_length = 8
        if len(i.data) < max_length:
            max_length = len(i.data)
        for d in range(1, max_length):
            count = count + i.data[d].count
        if count > 0:
            stats_usage.append({"name":i.name, "count":count})

    stats_usage.sort(cmp=_usage_compare)
    emails_to_send = [e.strip() for e in admin_emails.split(',') if e.strip()]
    variables = dict(service=si.name,
                     users={"today":sisTO.number_of_users,
                            "week":{"gained":sum(c.count for c in sisTO.users_gained[:8]),
                                    "lost":sum(c.count for c in sisTO.users_lost[:8])},
                            "month":{"gained":sum(c.count for c in sisTO.users_gained[:31]),
                                     "lost":sum(c.count for c in sisTO.users_lost[:31])}},
                     usage=stats_usage,
                     usage_length=len(stats_usage))
    body = render("service_identity_statistics_email", [default_language], variables)
    html = render("service_identity_statistics_email_html", [default_language], variables)
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Weekly statistics for %s" % si.name
    msg['From'] = settings.senderEmail
    msg['To'] = admin_emails
    msg.attach(MIMEText(body.encode('utf-8'), 'plain', 'utf-8'))
    msg.attach(MIMEText(html.encode('utf-8'), 'html', 'utf-8'))
    send_mail_via_mime(settings.dashboardEmail, emails_to_send, msg, transactional=True)

def _send_statistics_for_service_user(si, admin_emails, default_language, settings):
    service_identities = list(get_service_identities(si.service_user))
    book = xlwt.Workbook(encoding="utf-8")
    sheet = book.add_sheet("Statistics")
    wrap_alignment = xlwt.Alignment()
    wrap_alignment.wrap = xlwt.Alignment.WRAP_AT_RIGHT
    wrap_alignment.horz = xlwt.Alignment.HORZ_LEFT
    wrap_alignment.vert = xlwt.Alignment.VERT_CENTER
    red_font = xlwt.Font()
    red_font.colour_index = 10
    pattern_white = xlwt.Pattern()
    pattern_white.pattern = xlwt.Pattern.SOLID_PATTERN
    pattern_white.pattern_fore_colour = 1
    pattern_dark = xlwt.Pattern()
    pattern_dark.pattern = xlwt.Pattern.SOLID_PATTERN
    pattern_dark.pattern_fore_colour = 41
    regular_style1 = xlwt.XFStyle()
    regular_style1.alignment = wrap_alignment
    regular_style1.pattern = pattern_white
    red_style2 = xlwt.XFStyle()
    red_style2.alignment = wrap_alignment
    red_style2.pattern = pattern_dark
    red_style2.font = red_font
    START_USERS_DETAIL = 15
    START_USAGE_DETAIL = 26
    sheet.col(0).width = 5000
    sheet.col(1).width = 7000
    sheet.write(1, 0, "Summary users", red_style2)

    if len(service_identities) >= 2:
        col = 0
        sheet.write(3, 1, "Total")
        sheet.write(START_USERS_DETAIL - 1, 1, "Total", regular_style1)
    else:
        col = 1
    # SET summary users names
    sheet.write(4, col, "Today")
    sheet.write(5, col, "Last 7 days:")
    sheet.write(6, col, " - gained")
    sheet.write(7, col, " - lost")
    sheet.write(8, col, "Last 30 days:")
    sheet.write(9, col, " - gained")
    sheet.write(10, col, " - lost")
    row = START_USERS_DETAIL
    sheet.write(START_USERS_DETAIL - 3, 0, "Detail users", red_style2)
    sheet.write(START_USERS_DETAIL - 1, col, "Week", regular_style1)

    now_ = datetime.datetime.utcnow()
    now_date_today = datetime.date(now_.year, now_.month, now_.day).today()
    # SET detail users dates
    for i in range(1, 8):
        day_stats = now_date_today - datetime.timedelta(i * 7)
        dt = datetime.date(day_stats.year, day_stats.month, day_stats.day)
        sheet.write(row, col, dt.isocalendar()[1], regular_style1)
        row += 1

    # SET detail usage dates
    row = START_USAGE_DETAIL
    sheet.write(START_USAGE_DETAIL - 3, 0, "Detail usage", red_style2)
    sheet.write(START_USAGE_DETAIL - 1, 0, "Week", regular_style1)
    sheet.write(START_USAGE_DETAIL - 1, 1, "Menu item label", regular_style1)
    service_menu_items = get_service_menu_items(si.service_user)
    smi_labels = sorted([smi.label for smi in service_menu_items], key=lambda x: x.lower())
    for i in range(1, 8):
        day_stats = now_date_today - datetime.timedelta(i * 7)
        dt = datetime.date(day_stats.year, day_stats.month, day_stats.day)
        for label in smi_labels:
            sheet.write(row, 0, dt.isocalendar()[1], regular_style1)
            sheet.write(row, 1, label, regular_style1)
            row += 1

        row += 1

    col = 2
    summary_users_total = dict()

    summary_users_total["number_of_users"] = 0
    summary_users_total["w_user_gained"] = 0
    summary_users_total["w_user_lost"] = 0
    summary_users_total["m_user_gained"] = 0
    summary_users_total["m_user_lost"] = 0


    detail_users_total = [0, 0, 0, 0, 0, 0, 0]

    for service_identity in service_identities:
        ss = get_identity_statistics(service_identity.user)
        sis = get_statistics_list(ss)
        if len(sis["users_gained"]) >= 8:
            # Service has statistics for longer than 7 days
            # SET summary users data
            sheet.write(2, col, service_identity.name, regular_style1)
            sheet.write(3, col, service_identity.identifier, regular_style1)
            sheet.write(4, col, ss.number_of_users)
            sheet.write(6, col, sum(sis["users_gained"][:8]))
            sheet.write(7, col, sum(sis["users_lost"][:8]))
            sheet.write(9, col, sum(sis["users_gained"][:31]))
            sheet.write(10, col, sum(sis["users_lost"][:31]))

            summary_users_total["number_of_users"] += ss.number_of_users
            summary_users_total["w_user_gained"] += sum(sis["users_gained"][:8])
            summary_users_total["w_user_lost"] += sum(sis["users_lost"][:8])
            summary_users_total["m_user_gained"] += sum(sis["users_gained"][:31])
            summary_users_total["m_user_lost"] += sum(sis["users_lost"][:31])

            # SET detail users data
            row = START_USERS_DETAIL
            total_users = ss.number_of_users
            sheet.write(START_USERS_DETAIL - 2, col, service_identity.name, regular_style1)
            sheet.write(START_USERS_DETAIL - 1, col, service_identity.identifier, regular_style1)
            for i in range(1, 8):  # last 7 weeks
                weekly_total_users = total_users - sum(sis["users_gained"][:7 * i]) + sum(sis["users_lost"][:7 * i])
                sheet.write(row, col, weekly_total_users)
                detail_users_total[i - 1] += weekly_total_users
                row += 1

            # SET detail usage data
            row = START_USAGE_DETAIL
            sheet.write(START_USAGE_DETAIL - 2, col, service_identity.name, regular_style1)
            sheet.write(START_USAGE_DETAIL - 1, col, service_identity.identifier, regular_style1)
            for i in range(1, 8):  # last 7 weeks
                for label in smi_labels:
                    if label in sis["labels"]:
                        sheet.write(row, col, sum(sis[label][7 * (i - 1):7 * i]))
                    else:
                        sheet.write(row, col, 0)
                    row += 1
                row += 1
            col += 1

    if len(service_identities) >= 2:
        sheet.write(4, 1, summary_users_total["number_of_users"])
        sheet.write(6, 1, summary_users_total["w_user_gained"])
        sheet.write(7, 1, summary_users_total["w_user_lost"])
        sheet.write(9, 1, summary_users_total["m_user_gained"])
        sheet.write(10, 1, summary_users_total["m_user_lost"])

        row = START_USERS_DETAIL
        for i in range(7):
            sheet.write(row, 1, detail_users_total[i])
            row += 1

    if col > 2:
        output = StringIO()
        book.save(output)
        output.seek(0)
        statisticsXls = MIMEBase('application', 'vnd.ms-excel')
        statisticsXls.set_payload(output.getvalue())
        email.encoders.encode_base64(statisticsXls)
        statisticsXls.add_header('Content-Disposition', 'attachment;filename=stats_%s_w_%s.xls' % (now_date_today.year, now_date_today.isocalendar()[1]))
        emails_to_send = [e.strip() for e in admin_emails.split(',') if e.strip()]
        variables = dict(service=si.name)
        body = render("service_statistics_email", [default_language], variables)
        msg = MIMEMultipart()
        msg['Subject'] = "Weekly statistics for your identities of %s" % si.name
        msg['From'] = settings.senderEmail
        msg['To'] = admin_emails
        msg.attach(MIMEText(body.encode('utf-8'), 'plain', 'utf-8'))
        msg.attach(statisticsXls)
        send_mail_via_mime(settings.dashboardEmail, emails_to_send, msg, transactional=True)
