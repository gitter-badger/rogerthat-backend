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

import base64
import json
import logging
import re
import urllib

from rogerthat.bizz.messaging import process_mfr_email_reply
from rogerthat.bizz.user import calculate_secure_url_digest
from rogerthat.dal.profile import get_profile_info
from rogerthat.rpc import users
from rogerthat.settings import get_server_settings
from rogerthat.utils import azzert
from rogerthat.utils.crypto import encrypt
from google.appengine.api import app_identity
from google.appengine.ext import deferred
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
import html2text
from mcfw.rpc import returns, arguments


EMAIL_REGEX = re.compile(r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")
EMAIL_ADDRESS_EXPRESSION = re.compile("([^<]*<(?P<mail1>[^>]+)>.*|(?P<mail2>[^<]*))")
FOLLOW_UP_ID_EXPRESSION = re.compile("(?P<follow_up_id>.*)\\.followup@%s\\.appspotmail\\.com" % app_identity.get_application_id())

def follow_up(from_, regex, subject, body):
    follow_up_id = regex.groupdict()['follow_up_id']
    deferred.defer(process_mfr_email_reply, follow_up_id, from_, subject, body)

ROUTER = dict()
ROUTER[FOLLOW_UP_ID_EXPRESSION] = follow_up

class EmailHandler(InboundMailHandler):

    def receive(self, mail_message):
        try:
            for body in mail_message.bodies():  # Fix for 8bit encoded messages
                body = body[1]
                if hasattr(body, 'charset') and body.charset and body.charset.lower() == '8bit':
                    body.charset = '7bit'
                if hasattr(body, 'encoding') and body.encoding and body.encoding.lower() == '8bit':
                    body.encoding = '7bit'
            logging.info(str(mail_message.to_mime_message()))
        except:
            logging.exception("Could not log incoming message")

        plaintext_bodies = list(mail_message.bodies('text/plain'))
        if plaintext_bodies:
            body = plaintext_bodies[0][1]
            if body.charset and body.charset.lower() == '8bit':  # Fix for 8bit encoded messages
                body.charset = '7bit'
            body = body.decode()

            xmailer = mail_message.original.get("X-Mailer")
            if xmailer and 'outlook' in xmailer.lower():
                body = body.replace('\r\n\r\n', '\n')
        else:
            htmltext_bodies = list(mail_message.bodies('text/html'))
            if htmltext_bodies:
                body = htmltext_bodies[0][1]
                html = body.decode()
                body = html2text.html2text(html)
            else:
                logging.error("No text bodies found in received email.")
                return

        m = EMAIL_ADDRESS_EXPRESSION.search(mail_message.to)
        if m is None:
            logging.error("Unable to parse recipient email address!\n\n\n%s" % mail_message.to)
            return

        groups = m.groupdict()
        to_address = groups['mail2'] if groups['mail1'] is None else groups['mail1']

        for regex, function in ROUTER.iteritems():
            m = regex.search(to_address)
            if m:
                function(mail_message.sender, m, getattr(mail_message, 'subject', ''), body)
                break
        else:
            # If loop did not break ...
            logging.warning("Recipient email address not recognized!\n\n\n%s" % mail_message.to)
            return


def generate_user_specific_link(url_path, app_user, data):
    data["d"] = calculate_secure_url_digest(data)
    data = encrypt(app_user, json.dumps(data))
    return '%s%s?%s' % (get_server_settings().baseUrl, url_path,
                        urllib.urlencode(dict(email=app_user.email(), data=base64.encodestring(data))))


@returns(str)
@arguments(app_user=users.User)
def generate_unsubscribe_link(app_user):
    profile_info = get_profile_info(app_user)
    if not profile_info:
        return None

    data = dict(n=profile_info.name, e=app_user.email(), t=0, a="unsubscribe reminder", c=None)
    return generate_user_specific_link('/unsubscribe_reminder', app_user, data)


@returns(str)
@arguments(app_user=users.User, service_identity_user=users.User, service_identity_name=unicode,
           broadcast_type=unicode)
def generate_unsubscribe_broadcast_link(app_user, service_identity_user, service_identity_name, broadcast_type):
    if not broadcast_type:
        return None

    azzert('/' in service_identity_user.email())
    data = dict(n=service_identity_name, e=service_identity_user.email(), t=0, a="unsubscribe broadcast", c=None,
                bt=broadcast_type)
    return generate_user_specific_link('/unsubscribe_broadcast', app_user, data)


@returns(unicode)
@arguments(user=users.User)
def generate_auto_login_url(user):
    profile_info = get_profile_info(user, skip_warning=True)
    if not profile_info:
        return None

    name = profile_info.name
    data = dict(n=name, e=user.email(), t=0, a="auto login url", c=None)
    data["d"] = calculate_secure_url_digest(data)
    data = encrypt(user, json.dumps(data))
    return unicode('%s/auto_login?%s' % (get_server_settings().baseUrl, urllib.urlencode((("email", user.email()), ("data", base64.encodestring(data)),))))
