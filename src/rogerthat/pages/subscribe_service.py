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

import os

from rogerthat.consts import DEBUG
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.profile import get_service_profile, get_user_profile
from rogerthat.rpc import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template


_BASE_DIR = os.path.dirname(__file__)

class SubscribeHandler(webapp.RequestHandler):

    def return_error(self):
        path = os.path.join(_BASE_DIR, 'error.html')
        self.response.out.write(template.render(path, {'debug':DEBUG, "reason":"Unknown service"}))

    def get(self):
        tag = self.request.get("tag", "")
        service = self.request.get("service", "")
        if not service:
            return self.return_error()
        service_profile = get_service_profile(users.User(service))
        if not service_profile:
            return self.return_error()
        user = users.get_current_user()
        user_friendmap = get_friends_map(user) if user else None
        path = os.path.join(_BASE_DIR, 'subscribe_service.html')
        self.response.out.write(template.render(path, {
            'debug':DEBUG,
            "continue": self.request.path_qs,
            "tag": tag,
            "service": service_profile,
            "you": get_user_profile(user) if user else None,
            "connected": service_profile.user in user_friendmap.friends if user_friendmap else None,
            "user": user
        }))
