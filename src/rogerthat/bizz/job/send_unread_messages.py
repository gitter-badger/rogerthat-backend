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
import time
from collections import namedtuple
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from babel.core import Locale, UnknownLocaleError
from babel.dates import format_date, format_time
from google.appengine.ext import db, deferred

from rogerthat.bizz.profile import get_profile_info_name, UNKNOWN_AVATAR, NUNTIUZ_AVATAR
from rogerthat.bizz.rtemail import generate_unsubscribe_link, generate_unsubscribe_broadcast_link
from rogerthat.consts import MC_DASHBOARD
from rogerthat.consts import MICRO_MULTIPLIER, ANDROID_MARKET_WEB_URI_FORMAT, \
    IOS_APPSTORE_WEB_URI_FORMAT, DEBUG
from rogerthat.dal.app import get_app_by_id
from rogerthat.dal.messaging import GET_UNREAD_MESSAGES_JOB_GQL
from rogerthat.dal.profile import get_profile_infos, get_profile_key
from rogerthat.models import LastUnreadMessageMailingJob, Message, App, UserProfile
from rogerthat.pages.profile import get_avatar_cached
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile
from rogerthat.settings import get_server_settings
from rogerthat.templates import JINJA_ENVIRONMENT
from rogerthat.translations import localize, DEFAULT_LANGUAGE
from rogerthat.utils import now, DSPickler, send_mail_via_mime, xml_escape
from rogerthat.utils.app import get_app_user_tuple_by_email, get_app_id_from_app_user
from rogerthat.utils.languages import convert_web_lang_to_iso_lang
from rogerthat.utils.service import add_slash_default

# Threat message as unread is it was unread for LEAP_TIME seconds.
LEAP_TIME = 2 * 86400  # Important: don't forget to update the translations when changing LEAP_TIME; hard-coded '2 days'

def send(dry_run=True):
    logging.info("Sending unread messages reminders.")
    deferred.defer(get_from, dry_run, _transactional=db.is_in_transaction())

def get_from(dry_run=True):
    def update():
        last = LastUnreadMessageMailingJob.get()
        now_ = now()
        start = last.timestamp
        last.timestamp = now_ - LEAP_TIME
        if not dry_run:
            last.put()
            logging.info("updated LastUnreadMessageMailingJob.timestamp to %s", time.ctime(last.timestamp))
        deferred.defer(assemble_data, start, now_, dict(), None, dry_run, _transactional=True)
    db.run_in_transaction(update)

def assemble_data(from_, to, stash, cursor, dry_run=True):
    key = '%s-%s' % (from_, to)
    dsp = DSPickler.read(key)
    if stash is None:
        stash = dsp.data
    logging.info("Looking for unread messages in the following time frame:\nfrom_: %s\nto: %s",
                 time.ctime(from_), time.ctime(to))
    query = GET_UNREAD_MESSAGES_JOB_GQL()
    query.bind(from_=from_, to=to)
    query.with_cursor(cursor)
    ums = query.fetch(100)
    ums_length = len(ums)
    for um in ums:
        if not um:
            logging.info("Skipped stale record.")
            continue
        if not (from_ < um.creationTimestamp <= to):
            logging.info("Skipped out-dated query result of %s with timestamp %s" % (um.mkey, time.ctime(um.creationTimestamp / MICRO_MULTIPLIER)))
            continue
        actors = [member.email() for member in um.members
                  if Message.statusIndexValue(member, Message.MEMBER_INDEX_STATUS_NOT_RECEIVED) in um.member_status_index
                  and Message.statusIndexValue(member, Message.MEMBER_INDEX_STATUS_NOT_DELETED) in um.member_status_index]
        for actor in actors:
            if not actor in stash:
                stash[actor] = [0, set()]
            stats = stash[actor]
            stats[0] = stats[0] + 1
            stats[1].add((um.sender, um.message, um.broadcast_type, um.creationTimestamp))
    if ums_length > 0:
        dsp.update(stash)
        deferred.defer(assemble_data, from_, to, None, query.cursor(), dry_run, _transactional=db.is_in_transaction())
    else:
        dsp.update((stash.keys(), stash.items()))
        deferred.defer(schedule_send_email, from_, to, 0, dry_run, _transactional=db.is_in_transaction())


def schedule_send_email(from_, to, position, dry_run=True, skipped_users=None):
    key = '%s-%s' % (from_, to)
    dsp = DSPickler.read(key)
    _, to_schedule = dsp.data
    def run(pos, skipped_users):
        if skipped_users is None:
            skipped_users = set()

        count = 0
        while pos < len(to_schedule):
            user_email, stats = to_schedule[pos]
            pos += 1

            max_timestamp = now() - LEAP_TIME
            if dry_run and not user_email.split(':', 1)[0].endswith('@mobicage.com'):
                skipped_users.add(user_email)
                continue
            elif (not any((s[3] < max_timestamp for s in stats[1]))):
                logging.info('Not sending out email reminder for %s because all the unread messages (%s) are sent '
                             'after %s (LEAP TIME: %ss)', user_email, len(stats[1]), time.ctime(max_timestamp), LEAP_TIME)
                skipped_users.add(user_email)
                continue

            deferred.defer(send_email, user_email, stats, dry_run, _transactional=True)
            logging.info("Send email to %s with stats %s" % (user_email, stats))
            count += 1
            if count == 4:  # 4, because max 5 defers in 1 transaction
                break

        if pos < len(to_schedule):
            deferred.defer(schedule_send_email, from_, to, pos, dry_run, skipped_users, _transactional=True)
        else:
            deferred.defer(send_overview_email, from_, to, dry_run, skipped_users, _transactional=True)
    db.run_in_transaction(run, position, skipped_users)


UnreadMessage = namedtuple('UnreadMessage',
                           ('name avatar message broadcast_type time unsubscribe_caption unsubscribe_link'))


def _create_unread_messages(stats, language, server_settings, user_profile):
    sender_users = list({s[0] for s in stats[1] if s[0] != MC_DASHBOARD})
    sender_profile_infos = dict(zip(sender_users, get_profile_infos(sender_users, allow_none_in_results=True)))

    timezone_diff = 0
    if user_profile.mobiles:
        for mobile_detail in user_profile.mobiles:
            mobile = Mobile.get(Mobile.create_key(mobile_detail.account))
            timezone_diff = mobile.timezoneDeltaGMT or 0
            break

    avatars = dict()  # { avatar_id : (avatar_data) }
    def get_avatar_url(avatar_id):
        avatar = avatars.get(avatar_id)
        if not avatar:
            if avatar_id in ('nuntiuz', 'unknown'):
                if avatar == 'nuntiuz':
                    avatar = UNKNOWN_AVATAR
                else:
                    avatar = NUNTIUZ_AVATAR
            else:
                avatar = get_avatar_cached(avatar_id, size=40)
            avatars[avatar_id] = avatar
        return 'cid:%s' % avatar_id

    unread_messages = list()  # sorted by message.creationTimestamp
    for sender_user, message, broadcast_type, creation_time in sorted(stats[1], key=lambda x: x[3]):
        sender_profile_info = sender_profile_infos.get(sender_user)
        if sender_profile_info:
            name = sender_profile_info.name
            avatar_url = get_avatar_url(sender_profile_info.avatarId)
        elif sender_user == MC_DASHBOARD:
            name = get_profile_info_name(sender_user, user_profile.app_id)
            avatar_url = get_avatar_url('nuntiuz')
        else:
            name = sender_user.email().split(':', 1)[0].split('/', 1)[0]
            avatar_url = get_avatar_url('unknown')

        creation_date_time = datetime.datetime.utcfromtimestamp(creation_time + timezone_diff)
        creation_time_str = '%s, %s' % (format_date(creation_date_time, locale=language, format='short'),
                                        format_time(creation_date_time, locale=language, format='short'))

        if broadcast_type:
            sender_user = add_slash_default(sender_user)

        if len(name) > 43:
            name = name[:40] + u'...'

        unread_messages.append(UnreadMessage(name, avatar_url, message, broadcast_type, creation_time_str,
                                             localize(language, 'email_reminder_unsubscribe_caption',
                                                      notification_type=xml_escape(broadcast_type) if broadcast_type else None,
                                                      service=xml_escape(name)),
                                             generate_unsubscribe_broadcast_link(user_profile.user, sender_user, name,
                                                                                 broadcast_type)))
    return unread_messages, avatars


def _get_template_params(stats, language, server_settings, user_profile, human_user_email, app):
    server_settings = get_server_settings()
    unread_messages, avatars = _create_unread_messages(stats, language, server_settings, user_profile)

    # Building the template variables
    count = len(unread_messages)
    if count == 1:
        title = localize(language, "%(app_name)s has 1 new message for you", app_name=app.name)
    else:
        title = localize(language, "%(app_name)s has %(count)d new messages for you",
                         count=count, app_name=app.name)

    if app.type == app.APP_TYPE_CITY_APP:
        support_email = localize(language, 'the_our_city_app_coach_email_address')
        support_html = localize(language, 'the_our_city_app_coach_email_address_html', email=support_email)
        website_link = localize(language, 'http://www.ourcityapps.com')
        team = localize(language, 'the_our_city_app_team')
    else:
        support_email = server_settings.supportEmail
        support_html = localize(language, 'the_app_support_email_address_html',
                                app_name=app.name, email=support_email)
        website_link = u'http://www.rogerthat.net'
        team = localize(language, 'the_app_team', app_name=app.name)

    unsubscribe_link = generate_unsubscribe_link(user_profile.user)

    # outro_part1 is equal for both the text and the HTML version
    outro_part1 = localize(language, 'email_reminder_outro_part1', app_name=app.name)

    # not using a for-loop here to keep the 'test_code' unit test happy
    cause_captions = [localize(language, 'cause_1'),
                      localize(language, 'cause_2'),
                      localize(language, 'cause_3'),
                      localize(language, 'cause_4'),
                      ]

    cause1 = localize(language, 'email_reminder_cause_no_internet')
    cause2 = localize(language, 'email_reminder_cause_force_quitted', app_name=app.name)
    # cause3 is iOS only, and is inserted below
    cause4_html = localize(language, 'email_reminder_cause_uninstalled',
                           app_name=app.name,
                           app_store='<a href="%s">App Store</a>' % (IOS_APPSTORE_WEB_URI_FORMAT % app.ios_app_id),
                           google_play='<a href="%s">Google Play</a>' % (ANDROID_MARKET_WEB_URI_FORMAT % app.android_app_id),
                           account='<a href="#">%s</a>' % human_user_email)
    cause4_text = localize(language, 'email_reminder_cause_uninstalled',
                           app_name=app.name,
                           app_store='App Store',
                           google_play='Google Play',
                           account=human_user_email)

    html_causes = [cause1, cause2, cause4_html]
    text_causes = [cause1, cause2, cause4_text]

    # for iOS user, add the cause about disabled Apple Push Notifications

    if user_profile.mobiles:
        for mobile_detail in user_profile.mobiles:
            if mobile_detail.type_ in Mobile.IOS_TYPES:
                cause3 = localize(language, 'email_reminder_cause_no_push', app_name=app.name)
                html_causes.insert(2, cause3)
                text_causes.insert(2, cause3)
                break

        has_mobiles = True
        email_reminder_intro_text = email_reminder_intro_html = localize(language, 'email_reminder_intro',
                                                                         app_name=app.name)
    else:
        has_mobiles = False
        email_reminder_intro_text = localize(language, 'email_reminder_intro_no_mobile_text',
                                             app_name=app.name,
                                             support=support_email,
                                             website_link=website_link)

        email_reminder_intro_html = localize(language, 'email_reminder_intro_no_mobile_html',
                                             app_name=app.name,
                                             support=support_email,
                                             website_link=website_link)

    common_params = dict(has_mobiles=has_mobiles,
                         title=title,
                         profile=user_profile,
                         language=language,
                         app=app,
                         team=team,
                         unread_messages=unread_messages,
                         unsubscribe_link=unsubscribe_link)

    text_params = dict(common_params,
                       causes=zip(cause_captions, text_causes),
                       outro='%s %s' % (outro_part1, localize(language, 'email_reminder_outro_part2_text',
                                                              support=support_email, website_link=website_link)),
                       unsubscribe_info='%s\n%s: %s' % (localize(language,
                                                                     'email_reminder_unsubscribe_from_email_text'),
                                                            localize(language, 'Unsubscribe'),
                                                            unsubscribe_link),
                       email_reminder_intro=email_reminder_intro_text,
                       )

    html_params = dict(common_params,
                       causes=zip(cause_captions, html_causes),
                       outro='%s %s' % (outro_part1, localize(language, 'email_reminder_outro_part2_html',
                                                              support=support_html, website_link=website_link)),
                       unsubscribe_info=localize(language, 'email_reminder_unsubscribe_from_email_html',
                                                     unsubscribe_link=unsubscribe_link),
                       email_reminder_intro=email_reminder_intro_html,
                       )

    return text_params, html_params, avatars


def send_email(app_user_email, stats, dry_run=True):
    # stats: (index, {(sender_user, message_content, broadcast_type, timestamp), ...})
    app_user = users.User(app_user_email)
    app_id = get_app_id_from_app_user(app_user)
    user_profile, app = db.get([get_profile_key(app_user), App.create_key(app_id)])
    if app.type in (App.APP_TYPE_YSAAA, App.APP_TYPE_OSA_LOYALTY):
        logging.debug("App type was %s: %s", app.type_str, app_user.email())
        return

    if not user_profile:
        logging.info("User was deactivated: %s" , app_user.email())
        return

    if user_profile.unsubscribed_from_reminder_email:
        logging.info("User unsubscribed from email reminders: %s" , app_user.email())
        return

    language = convert_web_lang_to_iso_lang(user_profile.language or DEFAULT_LANGUAGE)
    try:
        Locale.parse(language)
    except UnknownLocaleError:
        language = DEFAULT_LANGUAGE

    human_user, app_id = get_app_user_tuple_by_email(app_user_email)
    human_user_email = human_user.email()

    app = get_app_by_id(app_id)
    server_settings = get_server_settings()

    text_params, html_params, avatars = _get_template_params(stats, language, server_settings, user_profile,
                                                             human_user_email, app)

    jinja_template = JINJA_ENVIRONMENT.get_template('generic/unread_messages_notification_email.tmpl')
    body = jinja_template.render(text_params)

    jinja_template = JINJA_ENVIRONMENT.get_template('generic/unread_messages_notification_email_html.tmpl')
    html = jinja_template.render(html_params)

    logging.info("%sSending mail to %s\n%s", 'DRY RUN!\n\n' if dry_run else '', human_user_email, body)

    email_receivers = server_settings.supportWorkers if dry_run else [human_user_email]
    if app.is_default:
        email_sender = server_settings.senderEmail
    else:
        email_sender = ("%s <%s>" % (app.name, app.dashboard_email_address))

    rel_mime = MIMEMultipart('related')
    rel_mime['Subject'] = text_params['title']
    rel_mime['From'] = email_sender
    rel_mime['To'] = ', '.join(email_receivers)

    msg = MIMEMultipart('alternative')
    msg.attach(MIMEText(body.encode('utf-8'), 'plain', 'utf-8'))
    msg.attach(MIMEText(html.encode('utf-8'), 'html', 'utf-8'))
    rel_mime.attach(msg)

    for avatar_id, avatar_data in avatars.iteritems():
        mime_img = MIMEImage(avatar_data, 'png')
        mime_img.add_header('Content-Id', '<%s>' % avatar_id)
        mime_img.add_header("Content-Disposition", "inline", filename="%s.png" % avatar_id)
        rel_mime.attach(mime_img)

    send_mail_via_mime(email_sender, email_receivers, rel_mime)

    if DEBUG and dry_run:
        return html


def send_overview_email(from_, to, dry_run=True, skipped_users=None):
    if skipped_users is None:
        skipped_users = set()
    server_settings = get_server_settings()
    key = '%s-%s' % (from_, to)
    dsp = DSPickler.read(key)
    users = sorted(set(dsp.data[0]) - skipped_users)
    body = u"\n".join(users) or u"No reminders sent"
    body = "COUNT: %s (%.02f%%)\nDRY_RUN: %s\n\n%s" % (len(users),
                                                       100.0 * len(users) / UserProfile.all().count(None),
                                                       dry_run,
                                                       body)
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Rogerthat reminders sent"
    msg['From'] = server_settings.senderEmail
    msg['To'] = ', '.join(server_settings.supportWorkers)
    msg.attach(MIMEText(body.encode('utf-8'), 'plain', 'utf-8'))
    send_mail_via_mime(server_settings.dashboardEmail, server_settings.supportWorkers, msg)
    deferred.defer(cleanup, key)


def cleanup(dsp_key):
    dsp = DSPickler(dsp_key)
    dsp.delete()
