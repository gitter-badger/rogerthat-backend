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

from rogerthat.dal.app import get_app_by_id
from rogerthat.models import App
from rogerthat.templates import render, get_languages_from_header
from rogerthat.utils import get_smartphone_install_url_by_user_agent
from google.appengine.ext import webapp


_BASE_DIR = os.path.dirname(__file__)

class InstallationRequestHandler(webapp.RequestHandler):

    def redirect(self, url, permanent=False):
        return super(InstallationRequestHandler, self).redirect(str(url), permanent)

    def get(self):
        language = get_languages_from_header(self.request.headers.get('Accept-Language', None))
        invitation_kind = 'email' if 'email' in self.request.GET else 'SMS'
        app_id = self.request.get('a', App.APP_ID_ROGERTHAT)
        if not app_id:
            app_id = App.APP_ID_ROGERTHAT

        user_agent = self.request.environ['HTTP_USER_AGENT']
        market_url = get_smartphone_install_url_by_user_agent(user_agent, app_id)

        if market_url:
            self.redirect(market_url)
        else:
            self.response.out.write(render('sorry', language, {'invitation_kind': invitation_kind,
                                                               'app': get_app_by_id(app_id)}, 'web'))
