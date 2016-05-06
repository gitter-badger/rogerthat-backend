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
import logging

from rogerthat.rpc import users
from rogerthat.to.system import LogErrorRequestTO
from google.appengine.ext import webapp


class LogExceptionHandler(webapp.RequestHandler):

    def post(self):
        description = self.request.get("description", None)
        platform = int(self.request.get("platform", 0))
        platform_version = self.request.get("platform_version", None)
        timestamp = long(self.request.get("timestamp", 0))
        mobicage_version = self.request.get("mobicage_version", None)
        error_message = self.request.get("error_message", None)

        logging.debug("Error logged over HTTP:\n%s", error_message)

        ler = LogErrorRequestTO()
        ler.description = description
        ler.platform = platform
        ler.platformVersion = platform_version
        ler.timestamp = timestamp
        ler.mobicageVersion = mobicage_version
        ler.errorMessage = error_message

        from rogerthat.bizz.system import logErrorBizz

        user = self.request.headers.get("X-MCTracker-User", None)
        password = self.request.headers.get("X-MCTracker-Pass", None)
        if user and password:
            users.set_json_rpc_user(base64.decodestring(user), base64.decodestring(password))
            return logErrorBizz(ler, users.get_current_user())
        else:
#           language = self.request.get("language", None)  # Unused
#           deviceId = self.request.get("device_id", None)  # Unused
            install_id = self.request.get("install_id", None)
            return logErrorBizz(ler, user=None, install_id=install_id)
