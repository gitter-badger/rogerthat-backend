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
import hashlib
import json
import logging

from rogerthat.bizz.debugging import start_debugging, stop_debugging, forward_log
from rogerthat.bizz.system import unregister_mobile, update_settings_response_handler
from rogerthat.capi.system import updateSettings
from rogerthat.dal.app import get_app_settings
from rogerthat.dal.mobile import get_mobile_by_id
from rogerthat.models import Settings, MobileSettings, App
from rogerthat.rpc import users
from rogerthat.rpc.rpc import logError
from rogerthat.rpc.service import BusinessException
from rogerthat.settings import get_server_settings
from rogerthat.to import RETURNSTATUS_TO_SUCCESS, ReturnStatusTO
from rogerthat.to.system import SettingsTO, UpdateSettingsRequestTO
from rogerthat.utils import azzert
from rogerthat.utils.crypto import decrypt_value, md5
from google.appengine.ext import webapp
from mcfw.rpc import serialize_complex_value, parse_complex_value


class GetGeneralSettings(webapp.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'text/json'
        app_settings = get_app_settings(App.APP_ID_ROGERTHAT)
        self.response.out.write(json.dumps(serialize_complex_value(SettingsTO.fromDBSettings(Settings.get(), app_settings), SettingsTO, False)))

class GetMobileSettings(webapp.RequestHandler):

    def get(self):
        user = users.get_current_user()
        self.response.headers['Content-Type'] = 'text/json'
        mobile_id = self.request.GET['mobile_id']
        mobile = get_mobile_by_id(mobile_id)
        azzert(mobile.user == user)
        settings = MobileSettings.get(mobile)
        app_settings = get_app_settings(App.APP_ID_ROGERTHAT)
        settingsDict = serialize_complex_value(SettingsTO.fromDBSettings(settings, app_settings), SettingsTO, False)
        settingsDict["description"] = mobile.description
        settingsDict["hardwareModel"] = mobile.hardwareModel
        settingsDict["color"] = settings.color
        settingsDict["type"] = mobile.type
        self.response.out.write(json.dumps(settingsDict))

class SettingsSave(webapp.RequestHandler):

    def post(self):
        user = users.get_current_user()
        data = json.loads(self.request.POST["data"])

        if data['general']:
            settings = Settings.get()
            updateMobile = lambda s:None
        else:
            mobile = get_mobile_by_id(data['mobile_id'])
            azzert(mobile.user == user)
            settings = MobileSettings.get(mobile)
            settings.color = data['color']
            mobile.description = data['description']
            if settings.version:
                settings.version += 1
            mobile.put()
            request = UpdateSettingsRequestTO()
            def updateMobile(s):
                request.settings = SettingsTO.fromDBSettings(s, get_app_settings(App.APP_ID_ROGERTHAT))
                logging.info("Updating mobile " + mobile.description)
                updateSettings(update_settings_response_handler, logError, mobile.user, request=request)

        settingsTO = parse_complex_value(SettingsTO, data, False)
        if settingsTO.geoLocationSamplingIntervalBattery < Settings.MINIMUM_INTERVAL:
            return
        if settingsTO.geoLocationSamplingIntervalCharging < Settings.MINIMUM_INTERVAL:
            return
        if settingsTO.xmppReconnectInterval < Settings.MINIMUM_INTERVAL:
            return
        settingsTO.apply(settings)
        settings.put()

        updateMobile(settings)

class EditMobileDescription(webapp.RequestHandler):

    def post(self):
        self.response.headers['Content-Type'] = 'text/json'
        try:
            user = users.get_current_user()
            mobile_id = self.request.POST["mobile_id"]
            description = self.request.POST["description"]
            mobile = get_mobile_by_id(mobile_id)
            azzert(mobile.user == user)
            mobile.description = description
            mobile.put()
            self.response.out.write(json.dumps({'success': True}))
        except:
            self.response.out.write(json.dumps({'success': False}))

class DeleteMobile(webapp.RequestHandler):

    def post(self):
        self.response.headers['Content-Type'] = 'text/json'
        try:
            user = users.get_current_user()
            mobile_id = self.request.POST["mobile_id"]
            unregister_mobile(user, get_mobile_by_id(mobile_id))
            self.response.out.write(json.dumps({'success': True}))
        except:
            self.response.out.write(json.dumps({'success': False}))


class SettingsStartDebugging(webapp.RequestHandler):

    def post(self):
        try:
            mobile_id = self.request.POST["mobile_id"]
            user = users.get_current_user()
            start_debugging(user, mobile_id)
            return_status = RETURNSTATUS_TO_SUCCESS
        except BusinessException, e:
            return_status = ReturnStatusTO.create(success=False, errormsg=e.message)
        except Exception, e:
            logging.exception("Failed to start debugging")
            return_status = ReturnStatusTO.create(success=False, errormsg="An error occurred. Please try again later.")
        r_dict = serialize_complex_value(return_status, return_status.__class__, False, skip_missing=True)
        r_string = json.dumps(r_dict)
        self.response.headers['Content-Type'] = 'text/json'
        self.response.out.write(r_string)


class SettingsStopDebugging(webapp.RequestHandler):

    def post(self):
        mobile_id = self.request.POST["mobile_id"]
        stop_debugging(users.get_current_user(), mobile_id, notify_user=False)


class ForwardLog(webapp.RequestHandler):

    def _validate_hash(self, hash_to_be_validated, user_email, message):
        hash_ = hashlib.sha256()
        hash_.update(user_email)
        hash_.update(message)
        hash_.update(get_server_settings().jabberSecret)
        hash_ = hash_.hexdigest()
        return hash_to_be_validated == hash_

    def post(self):
        user_email = self.request.POST["user"]
        message = self.request.POST["message"]
        hash_ = self.request.POST["hash"]
        if not hash_ or not self._validate_hash(hash_, user_email, message):
            self.response.set_status(401, "Wrong hash")
            return

        forward_log(users.User(user_email), message)


class DebugLog(webapp.RequestHandler):

    def post(self):
        data = json.loads(self.request.body)
        jid = data['jid']
        message = data['message']

        settings = get_server_settings()
        app_user_email = decrypt_value(md5(settings.secret), base64.b64decode(jid))
        forward_log(users.User(app_user_email), message)
