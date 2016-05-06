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

from rogerthat.bizz.job.update_friends import schedule_update_a_friend_of_a_service_identity_user
from rogerthat.bizz.user import calculate_secure_url_digest
from rogerthat.dal.app import get_app_by_user, get_app_name_by_id
from rogerthat.dal.mobile import get_user_active_mobiles
from rogerthat.models import ActivationLog, App, ServiceIdentity, UserProfile, FriendServiceIdentityConnection
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile
from rogerthat.templates import get_languages_from_request
from rogerthat.templates.jinja_extensions import TranslateExtension
from rogerthat.translations import localize
from rogerthat.utils import azzert, now, xml_escape
from rogerthat.utils.app import get_human_user_from_app_user, get_app_id_from_app_user, get_app_user_tuple
from rogerthat.utils.crypto import decrypt
from rogerthat.utils.service import add_slash_default
from rogerthat.utils.transactions import run_in_xg_transaction
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import template
import jinja2


class UnsubscribeReminderHandler(webapp.RequestHandler):
    _BASE_DIR = None
    _JINJA_ENVIRONMENT = None

    @staticmethod
    def get_base_dir():
        if not UnsubscribeReminderHandler._BASE_DIR:
            UnsubscribeReminderHandler._BASE_DIR = os.path.dirname(__file__)
        return UnsubscribeReminderHandler._BASE_DIR

    @staticmethod
    def get_jinja_environment():
        if not UnsubscribeReminderHandler._JINJA_ENVIRONMENT:
            UnsubscribeReminderHandler._JINJA_ENVIRONMENT = \
                jinja2.Environment(loader=jinja2.FileSystemLoader([UnsubscribeReminderHandler.get_base_dir()]),
                                   extensions=[TranslateExtension])
        return UnsubscribeReminderHandler._JINJA_ENVIRONMENT

    def return_error(self, reason="Invalid url received."):
        path = os.path.join(self.get_base_dir(), 'error.html')
        self.response.out.write(template.render(path, {"reason":reason, "hide_header": True}))
        return None, None

    def parse_data(self, email, data):
        user = users.User(email)
        data = base64.decodestring(data)
        data = decrypt(user, data)
        data = json.loads(data)
        azzert(data["d"] == calculate_secure_url_digest(data))
        return data, user

    def get_user_info(self):
        email = self.request.get("email", None)
        data = self.request.get("data", None)

        if not email or not data:
            return self.return_error()

        try:
            data_dict, _ = self.parse_data(email, data)
        except:
            logging.warn("Could not decipher url!", exc_info=True)
            return self.return_error()

        app_user = users.User(email)
        return data_dict, app_user


    def get(self):
        data_dict, app_user = self.get_user_info()
        if not data_dict or not app_user:
            return

        app, user_profile = db.get([App.create_key(get_app_id_from_app_user(app_user)),
                                    UserProfile.createKey(app_user)])

        if not user_profile:
            self.redirect("/")
            return

        mobiles = list(get_user_active_mobiles(app_user))
        if mobiles:
            mobile = mobiles[0]
            if mobile.type in Mobile.ANDROID_TYPES:
                page_type = "android"
            elif mobile.type in Mobile.IOS_TYPES:
                page_type = "ios"
            else:
                return self.return_error()
        else:
            mobile = None
            page_type = "web"

        page_type = self.request.get("page_type", page_type)
        language = self.request.get("language", user_profile.language)

        ActivationLog(timestamp=now(), email=app_user.email(), mobile=mobile,
                      description="Visit unsubscribe page %s %s" % (page_type, user_profile.language)).put()

        jinja_template = self.get_jinja_environment().get_template('unsubscribe_reminder_service.html')

        params = {
            'name': data_dict['n'],
            'app_name': get_app_by_user(app_user).name,
            'hide_header': True,
            'data': self.request.get("data"),
            'app_email': app_user.email(),
            'email': get_human_user_from_app_user(app_user).email(),
            'action': data_dict['a'],
            'page_type': page_type,
            'language': language,
            'is_city_app': app.type == App.APP_TYPE_CITY_APP
        }

        self.response.out.write(jinja_template.render(params))


class UnsubscribeBroadcastHandler(UnsubscribeReminderHandler):

    def _un_subscribe(self, app_user, si_user, broadcast_type):
        user_profile, si, fsic = db.get([UserProfile.createKey(app_user),
                                         ServiceIdentity.keyFromUser(add_slash_default(si_user)),
                                         FriendServiceIdentityConnection.createKey(app_user, si_user)])

        logging.info('%s is unsubscribing from notifications of "%s" with type "%s".',
                     user_profile.name if user_profile else app_user.email(),
                     si.name if si else si_user.email(),
                     broadcast_type)

        updated = False
        if fsic:
            if broadcast_type in fsic.enabled_broadcast_types:
                fsic.enabled_broadcast_types.remove(broadcast_type)
                updated = True
            if broadcast_type not in fsic.disabled_broadcast_types:
                fsic.disabled_broadcast_types.append(broadcast_type)
                updated = True

        if updated:
            fsic.put()
            schedule_update_a_friend_of_a_service_identity_user(fsic.service_identity_user, fsic.friend, force=True,
                                                                clear_broadcast_settings_cache=True)
        else:
            logging.info('%s was already unsubscribed from notifications of "%s" with type "%s".',
                         user_profile.name if user_profile else app_user.email(),
                         si.name if si else si_user.email(),
                         broadcast_type)

        return updated, user_profile, si, fsic

    def get(self):
        data_dict, app_user = self.get_user_info()
        if not data_dict or not app_user:
            return
        azzert(data_dict['a'] == "unsubscribe broadcast")

        broadcast_type = data_dict['bt']
        si_user = users.User(data_dict['e'])

        _, user_profile, si, fsic = run_in_xg_transaction(self._un_subscribe, app_user, si_user, broadcast_type)

        if fsic or not si:
            message = '%s,<br><br>%s' % (xml_escape(localize(user_profile.language, u'dear_name',
                                                             name=user_profile.name)),
                                         xml_escape(localize(user_profile.language,
                                                             u'successfully_unsubscribed_broadcast_type',
                                                             notification_type=broadcast_type,
                                                             service=si.name if si else data_dict['n'])))
        else:
            language = get_languages_from_request(self.request)[0]
            if not user_profile:
                # User already deactivated his account
                human_user, app_id = get_app_user_tuple(app_user)
                message = localize(language, u'account_already_deactivated',
                                   account=human_user.email(), app_name=get_app_name_by_id(app_id))
            else:
                # User is not connected anymore to this service identity
                message = localize(language, u'account_already_disconnected_from_service',
                                   service_name=si.name)


        jinja_template = self.get_jinja_environment().get_template('unsubscribe_broadcast_type.html')
        self.response.out.write(jinja_template.render(dict(message=message)))
