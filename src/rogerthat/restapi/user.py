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
import os
import re
import urllib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from rogerthat import utils
from rogerthat.bizz.limit import rate_signup_reset_password, rate_login, clear_rate_login
from rogerthat.bizz.rtemail import EMAIL_REGEX
from rogerthat.bizz.session import create_session
from rogerthat.bizz.user import calculate_secure_url_digest, update_user_profile_language_from_headers, \
    unsubscribe_from_reminder_email
from rogerthat.consts import SESSION_TIMEOUT
from rogerthat.dal.app import get_app_by_id
from rogerthat.dal.mobile import get_mobile_by_account
from rogerthat.dal.profile import get_profile_info, get_service_or_user_profile, get_deactivated_user_profile
from rogerthat.exceptions import ServiceExpiredException
from rogerthat.models import ActivationLog, App, CurrentlyForwardingLogs, FriendServiceIdentityConnection, \
    ServiceIdentity
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile
from rogerthat.settings import get_server_settings
from rogerthat.templates import render
from rogerthat.to.statistics import UserStatisticsTO
from rogerthat.translations import DEFAULT_LANGUAGE
from rogerthat.utils import now, is_clean_app_user_email, azzert, send_mail_via_mime
from rogerthat.utils.cookie import set_cookie
from rogerthat.utils.crypto import encrypt, sha256_hex, decrypt
from mcfw.cache import cached
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments

SIGNUP_SUCCESS = 1
SIGNUP_INVALID_EMAIL = 2
SIGNUP_INVALID_NAME = 3
SIGNUP_ACCOUNT_EXISTS = 4
SIGNUP_RATE_LIMITED = 5
SIGNUP_INVALID_EMAIL_DOMAIN = 6

LOGIN_SUCCESS = 1
LOGIN_FAIL_NO_PASSWORD = 2
LOGIN_FAIL = 3
LOGIN_TO_MANY_ATTEMPTS = 4
LOGIN_ACCOUNT_DEACTIVATED = 5
LOGIN_FAIL_SERVICE_EXPIRED = 6

DEACTIVATE_SUCCESS = 1
DEACTIVATE_ACCOUNT_DOES_NOT_EXITS = 2

@rest("/mobi/rest/user/signup", "post")
@returns(int)
@arguments(name=unicode, email=unicode, cont=unicode)
def signup(name, email, cont):
    if not name or not name.strip():
        return SIGNUP_INVALID_NAME

    if not email or not email.strip():
        return SIGNUP_INVALID_EMAIL

    if not EMAIL_REGEX.match(email):
        return SIGNUP_INVALID_EMAIL

    app = get_app_by_id(App.APP_ID_ROGERTHAT)  # TODO DEFAULT APP ID
    if app.user_regex:
        regexes = app.user_regex.splitlines()
        for regex in regexes:
            if re.match(regex, email):
                break
        else:
            return SIGNUP_INVALID_EMAIL_DOMAIN

    user = users.User(email)
    profile = get_service_or_user_profile(user)
    if profile and profile.passwordHash:
        return SIGNUP_ACCOUNT_EXISTS

    deactivated_profile = get_deactivated_user_profile(user)
    if deactivated_profile and deactivated_profile.passwordHash:
        return SIGNUP_ACCOUNT_EXISTS

    if not rate_signup_reset_password(user, os.environ.get('HTTP_X_FORWARDED_FOR', None)):
        return SIGNUP_RATE_LIMITED

    timestamp = now() + 5 * 24 * 3600
    data = dict(n=name, e=email, t=timestamp, a="registration", c=cont)
    data["d"] = calculate_secure_url_digest(data)
    data = encrypt(user, json.dumps(data))
    link = '%s/setpassword?%s' % (get_server_settings().baseUrl, urllib.urlencode((("email", email), ("data", base64.encodestring(data)),)))
    vars_ = dict(link=link, name=name, site=get_server_settings().baseUrl)
    body = render("signup", [DEFAULT_LANGUAGE], vars_)
    html = render("signup_html", [DEFAULT_LANGUAGE], vars_)
    logging.info("Sending message to %s\n%s" % (email, body))
    settings = get_server_settings()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Rogerthat registration"
    msg['From'] = settings.senderEmail if app.type == App.APP_TYPE_ROGERTHAT else ("%s <%s>" % (app.name, app.dashboard_email_address))
    msg['To'] = email
    msg.attach(MIMEText(body.encode('utf-8'), 'plain', 'utf-8'))
    msg.attach(MIMEText(html.encode('utf-8'), 'html', 'utf-8'))
    send_mail_via_mime(settings.senderEmail, email, msg)

    return SIGNUP_SUCCESS

@rest("/mobi/rest/user/reset_password", "post")
@returns(bool)
@arguments(email=unicode)
def reset_password(email):
    # XXX: Validating the email would be an improvement

    user = users.User(email)
    profile_info = get_profile_info(user)
    if not profile_info:
        return False

    if not rate_signup_reset_password(user, os.environ.get('HTTP_X_FORWARDED_FOR', None)):
        return False

    name = profile_info.name
    timestamp = now() + 5 * 24 * 3600
    data = dict(n=name, e=email, t=timestamp, a="reset password", c=None)
    data["d"] = calculate_secure_url_digest(data)
    data = encrypt(user, json.dumps(data))
    link = '%s/setpassword?%s' % (get_server_settings().baseUrl, urllib.urlencode((("email", email), ("data", base64.encodestring(data)),)))
    vars_ = dict(link=link, name=name)
    body = render("reset_password", [DEFAULT_LANGUAGE], vars_)
    html = render("reset_password_html", [DEFAULT_LANGUAGE], vars_)
    logging.info("Sending message to %s\n%s" % (email, body))
    settings = get_server_settings()
    utils.send_mail(settings.senderEmail2ToBeReplaced, email, "Rogerthat password reset", body, html=html)
    return True

@rest("/mobi/rest/user/login", "post")
@returns(int)
@arguments(email=unicode, password=unicode, remember=bool)
def login(email, password, remember):
    user = users.get_current_user()
    if user:
        return LOGIN_SUCCESS

    if not email or not password:
        return LOGIN_FAIL

    user = users.User(email)
    if not is_clean_app_user_email(user):
        return LOGIN_FAIL

    profile = get_service_or_user_profile(user)
    if not profile:
        deactivated_profile = get_deactivated_user_profile(user)

        if deactivated_profile:
            ActivationLog(timestamp=now(), email=user.email(), mobile=None, description="Login web with deactivated user").put()
            return LOGIN_ACCOUNT_DEACTIVATED
        else:
            return LOGIN_FAIL

    if not profile.passwordHash:
        return LOGIN_FAIL_NO_PASSWORD

    if not rate_login(user):
        return LOGIN_TO_MANY_ATTEMPTS

    if profile.passwordHash != sha256_hex(password):
        return LOGIN_FAIL

    from mcfw.restapi import GenericRESTRequestHandler
    response = GenericRESTRequestHandler.getCurrentResponse()
    try:
        secret, _ = create_session(user)
    except ServiceExpiredException:
        return LOGIN_FAIL_SERVICE_EXPIRED

    server_settings = get_server_settings()
    if remember:
        set_cookie(response, server_settings.cookieSessionName, secret, expires=now() + SESSION_TIMEOUT)
    else:
        set_cookie(response, server_settings.cookieSessionName, secret)

    clear_rate_login(user)

    request = GenericRESTRequestHandler.getCurrentRequest()
    update_user_profile_language_from_headers(profile, request.headers)

    return LOGIN_SUCCESS

@rest("/mobi/rest/user/unsubscribe/deactivate", "post")
@returns(int)
@arguments(email=unicode, data=unicode, reason=unicode)
def unsubscribe_deactivate(email, data, reason):

    def parse_data(email, data):
        user = users.User(email)
        data = base64.decodestring(data)
        data = decrypt(user, data)
        data = json.loads(data)
        azzert(data["d"] == calculate_secure_url_digest(data))
        return data, user

    try:
        data, app_user = parse_data(email, data)
    except:
        logging.exception("Could not decipher url!")
        return DEACTIVATE_ACCOUNT_DOES_NOT_EXITS

    is_success = unsubscribe_from_reminder_email(app_user)
    if is_success:
        ActivationLog(timestamp=now(), email=app_user.email(), mobile=None, description="Unsubscribed from reminder email | %s" % reason).put()
        return DEACTIVATE_SUCCESS
    else:
        ActivationLog(timestamp=now(), email=app_user.email(), mobile=None, description="Unsubscribed from reminder email not existing account | %s" % reason).put()
        return DEACTIVATE_ACCOUNT_DOES_NOT_EXITS

@rest("/mobi/rest/user/authenticate_mobile", "post")
@cached(1, 3600, False, True)
@returns(bool)
@arguments(email=unicode, password=unicode)
def authenticate_mobile(email, password):
    if email and email.startswith('dbg_'):
        return bool(CurrentlyForwardingLogs.all().filter('xmpp_target =', email).filter('xmpp_target_password =', password).count(1))

    mobile = get_mobile_by_account(email)
    return bool(mobile) and mobile.accountPassword == password

@rest("/mobi/rest/user/statistics", "get")
@returns(UserStatisticsTO)
@arguments()
def user_statistic():
    qry1 = Mobile.all(keys_only=True).filter('status >=', 4).filter('status <', 8)
    qry2 = FriendServiceIdentityConnection.all(keys_only=True)
    qry3 = ServiceIdentity.all(keys_only=True)
    qries = [ qry1, qry2, qry3 ]
    def stats(qry):
        cursor = None
        fetched = 1
        count = 0
        while fetched != 0:
            fetched = qry.with_cursor(cursor).count()
            count += fetched
            cursor = qry.cursor()
        return count - 1
    user_count, application_user_count, application_count = [stats(q) for q in qries]
    us = UserStatisticsTO()
    us.user_count = user_count
    us.service_user_count = application_user_count
    us.service_count = application_count
    return us
