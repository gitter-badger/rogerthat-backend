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
import os

from rogerthat.bizz.friends import get_user_and_qr_code_url
from rogerthat.bizz.service import get_default_qr_template_by_app_id
from rogerthat.bizz.system import qrcode
from rogerthat.consts import DEBUG
from rogerthat.dal.app import get_app_by_id, get_default_app
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.profile import get_user_profile, is_service_identity_user, get_profile_info
from rogerthat.models import ProfilePointer
from rogerthat.rpc import users
from rogerthat.settings import get_server_settings
from rogerthat.utils import urlencode, base38
from rogerthat.utils.app import get_app_id_from_app_user
from rogerthat.utils.cookie import set_cookie
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template


_BASE_DIR = os.path.dirname(__file__)

class InviteQRCodeRequestHandler(webapp.RequestHandler):

    def redirect(self, url, permanent=False):
        return super(InviteQRCodeRequestHandler, self).redirect(str(url), permanent)

    def get(self):
        code = self.request.get("code", None)
        if not code:
            self.response.set_status(404)
            return
        qr_code_url_and_user_tuple = get_user_and_qr_code_url(code)
        if not qr_code_url_and_user_tuple:
            self.response.set_status(404)
            return
        qr_code_url, qr_code_user = qr_code_url_and_user_tuple
        profile_info = get_profile_info(qr_code_user)  # might be user or service identity
        if profile_info:
            app_id = profile_info.app_id
        elif '/' in qr_code_user.email():  # deleted service identity
            app_id = get_default_app().app_id
        else:  # deleted or deactivated human user
            app_id = get_app_id_from_app_user(qr_code_user)
        qrtemplate, color = get_default_qr_template_by_app_id(app_id)
        img = qrcode(qr_code_url, qrtemplate.blob, color, False)
        if not img:
            self.response.set_status(404)
            return
        self.response.headers['Content-Type'] = "image/png"
        # Check target - could for example be 'fbwall' which means that the link should not be an attachment
        target = self.request.get("target", None)
        if target is None:
            self.response.headers['Content-Disposition'] = "attachment; filename=rogerthat-passport.png"
        self.response.out.write(img)

class InviteUserRequestHandler(webapp.RequestHandler):

    def return_error(self, reason="Unknown user account"):
        path = os.path.join(_BASE_DIR, 'error.html')
        self.response.out.write(template.render(path, {'debug':DEBUG, "reason":reason}))

    def get(self, user_code):
        pp = ProfilePointer.get_by_key_name(user_code)
        if not pp:
            return self.return_error()
        invitor_user_profile = get_user_profile(pp.user)
        if not invitor_user_profile:
            return self.return_error()
        current_user = users.get_current_user()

        user_agent = self.request.environ['HTTP_USER_AGENT']
        logging.info(user_agent)

        market = ''
        app = get_app_by_id(invitor_user_profile.app_id)
        if "Android" in user_agent:
            templ = "invite_mobile.html"
            market = app.android_market_android_uri
            appstore = "Android market"
            auto_detect = False
        elif "iPhone" in user_agent or 'iPad' in user_agent or 'iPod' in user_agent:
            templ = "invite_mobile.html"
            market = app.ios_appstore_web_uri
            appstore = "App Store"
            auto_detect = False
        else:
            templ = "invite_web.html"
            appstore = ""
            auto_detect = False

        short_link = None
        if current_user is None:
            current_user_profile = None
        elif is_service_identity_user(current_user):
            templ = "invite_service.html"
            current_user_profile = None
        else:
            current_user_profile = get_user_profile(current_user)
            if current_user == invitor_user_profile.user:
                templ = "invite_yourself.html"
                short_link = '%s/S/%s' % (get_server_settings().baseUrl, base38.encode_int(pp.short_url_id))

        app_url = "rogerthat://q/i%s" % user_code
        server_settings = get_server_settings()
        set_cookie(self.response, server_settings.cookieQRScanName, "rogerthat://i/qr?%s" \
                   % urlencode((("success", "true"), ("url", app_url))))
        current_user_friendmap = get_friends_map(current_user) if current_user else None
        path = os.path.join(_BASE_DIR, templ)
        self.response.out.write(template.render(path, {
            'debug':DEBUG,
            "continue": self.request.path_qs,
            "user_profile": invitor_user_profile,
            "you": current_user_profile,
            "connected": invitor_user_profile.user in current_user_friendmap.friends if current_user_friendmap else None,
            "user": current_user,
            "user_code": user_code,
            'short_link': short_link,
            'app_url' : app_url,
            'market': market,
            'auto_detect': auto_detect,
            "appstore": appstore,
            "app": app
        }))
