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

from rogerthat.rpc import users
import webapp2


class UserAwareRequestHandler(webapp2.RequestHandler):

    def set_user(self):
        user = self.request.headers.get("X-MCTracker-User", None)
        password = self.request.headers.get("X-MCTracker-Pass", None)
        if not user or not password:
            return False
        return users.set_json_rpc_user(base64.decodestring(user), base64.decodestring(password))
