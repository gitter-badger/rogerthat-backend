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

import json
import logging
import struct

from google.appengine.ext import webapp

from rogerthat.bizz.system import obsolete_apple_push_device_token
from rogerthat.dal.app import get_app_by_id
from rogerthat.dal.mobile import get_mobile_by_account
from rogerthat.dal.profile import get_profile_info
from rogerthat.rpc import users
from rogerthat.settings import get_server_settings
from rogerthat.to.admin import UserTO
from rogerthat.utils import now
from rogerthat.utils.crypto import encrypt_for_jabber_cloud
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments


@rest("/mobiadmin/rest/user_by_mobile_account", "get")
@returns(UserTO)
@arguments(account=unicode)
def get_user_by_mobile_account(account):
    mobile = get_mobile_by_account(account)
    profile_info = get_profile_info(mobile.user)
    return UserTO.from_profile_info(profile_info)


@rest("/mobiadmin/rest/user_by_email", "get")
@returns(UserTO)
@arguments(email=unicode)
def get_user_by_email(email):
    profile_info = get_profile_info(users.User(email))
    return UserTO.from_profile_info(profile_info)


@rest("/mobiadmin/rest/echo", "get")
@returns(unicode)
@arguments(value=unicode)
def echo(value):
    return value

class ApplePushFeedbackHandler(webapp.RequestHandler):

    def get(self):
        settings = get_server_settings()
        secret = self.request.headers.get("X-Nuntiuz-Secret", None)
        if secret != settings.jabberSecret:
            logging.error("Received unauthenticated apple feedback response, ignoring ...")
            return

        device = self.request.get('device')
        obsolete_apple_push_device_token(device)


class ApplePushCertificateDownloadHandler(webapp.RequestHandler):

    def get(self):
        settings = get_server_settings()
        secret = self.request.headers.get("X-Nuntiuz-Secret", None)
        if secret != settings.jabberSecret:
            logging.error("Received unauthenticated apple certificate request, ignoring ...")
            return
        app_id = self.request.get("id")
        if not app_id:
            return
        app = get_app_by_id(app_id)
        result = json.dumps(dict(cert=app.apple_push_cert, key=app.apple_push_key, valid_until=app.apple_push_cert_valid_until))
        self.response.headers['Content-Type'] = 'application/binary'
        _, data = encrypt_for_jabber_cloud(secret, result)
        self.response.write(data)


class ServerTimeHandler(webapp.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'application/binary'
        self.response.out.write(struct.pack('<q', now()))
