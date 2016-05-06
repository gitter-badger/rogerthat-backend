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

import logging
import urllib

from rogerthat.dal.app import get_app_by_id
from rogerthat.settings import get_server_settings
from rogerthat.templates import render, get_languages_from_header
from rogerthat.utils import get_platform_by_user_agent
from google.appengine.ext import webapp


class AppUrlHandler(webapp.RequestHandler):

    def get(self, app_id):
        language = get_languages_from_header(self.request.headers.get('Accept-Language', None))
        logging.info("Getting info about app with id %s", app_id)
        app = get_app_by_id(app_id.lower().strip())
        if not app or not app.is_in_appstores():
            # Unkown app ===> Show sorry page
            logging.info("Unkown app ===> Show sorry page ")
            context = {'app_id': app_id}
            self.response.out.write(render('sorry_app_unknown', language, context, 'web'))
            return
        user_agent = self.request.environ.get('HTTP_USER_AGENT')
        if user_agent:
            supported_platform = get_platform_by_user_agent(user_agent)
            if supported_platform == "android":
                self.redirect(str(app.android_market_web_uri))
                return
            if supported_platform == "ios":
                self.redirect(str(app.ios_appstore_web_uri))
                return
        logging.info("Unsupported platform ===> Show sorry page with install instructions for android & iphone")
        context = {'payload': urllib.urlencode([("chl", "%s/A/%s" % (get_server_settings().baseUrl, app_id))]),
                   'app_name': app.name}
        self.response.out.write(render('sorry_app_not_supported', language, context, 'web'))
