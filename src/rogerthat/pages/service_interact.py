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

from rogerthat.bizz import log_analysis
from rogerthat.bizz.service import get_service_interact_qr_code_url, get_default_qr_template_by_app_id
from rogerthat.bizz.system import qrcode
from rogerthat.consts import DEBUG
from rogerthat.dal.app import get_app_by_id
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.profile import get_user_profile
from rogerthat.dal.service import get_service_interaction_def, get_service_identity
from rogerthat.models import ProfilePointer, App
from rogerthat.rpc import users
from rogerthat.settings import get_server_settings
from rogerthat.templates import get_languages_from_header, render
from rogerthat.utils import base38, urlencode, safe_file_name, get_smartphone_install_url_by_user_agent, slog
from rogerthat.utils.cookie import set_cookie
from rogerthat.utils.service import remove_slash_default
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template


_BASE_DIR = os.path.dirname(__file__)

class ServiceInteractQRCodeRequestHandler(webapp.RequestHandler):

    def get(self, userCode, id_):
        download = self.request.get("download", "false") == "true"
        if not userCode or not id_:
            self.response.set_status(404)
            return
        pp = ProfilePointer.get(userCode)
        if not pp:
            self.response.set_status(404)
            return
        sid = get_service_interaction_def(pp.user, int(id_))
        short_link = get_service_interact_qr_code_url(sid)
        si = get_service_identity(sid.service_identity_user)
        if sid.qrTemplate:
            img = qrcode(short_link, str(sid.qrTemplate.blob) if sid.qrTemplate.blob else None, map(int, sid.qrTemplate.body_color), False)
        else:
            qrtemplate, color = get_default_qr_template_by_app_id(si.app_id)
            img = qrcode(short_link, qrtemplate.blob, color, False)
        if not img:
            self.response.set_status(404)
            return
        self.response.headers['Content-Type'] = "image/png"
        safe_service_name = safe_file_name(si.name)
        safe_poketag_name = safe_file_name(sid.tag)

        self.response.headers['Content-Disposition'] = "%s; filename=qr-%s-%s.png" % ("attachment" if download else "inline", safe_poketag_name, safe_service_name)
        self.response.headers['Cache-Control'] = "public, max-age=31536000"  # Cache for 1 year
        self.response.out.write(img)

class ServiceInteractRequestHandler(webapp.RequestHandler):

    def return_error(self, reason="Unknown Rogerthat service action"):
        path = os.path.join(_BASE_DIR, 'error.html')
        self.response.out.write(template.render(path, {'debug':DEBUG, "reason":reason}))

    def get(self, user_code, sid):
        user_agent = self.request.environ.get('HTTP_USER_AGENT')
        logging.info('HTTP_USER_AGENT: %s', user_agent)

        pp = ProfilePointer.get_by_key_name(user_code)
        if not pp:
            return self.return_error()
        sid = get_service_interaction_def(pp.user, int(sid))
        if not sid:
            return self.return_error()

        si = get_service_identity(sid.service_identity_user)
        app = get_app_by_id(si.app_id)

        def show_unsupported_platform():
            languages = get_languages_from_header(self.request.headers.get('Accept-Language', None))
            params = dict(profile_info=si, app=app)
            self.response.out.write(render('qr_code_scanned_unsupported_platform', languages, params, 'web'))

        if not user_agent:
            return show_unsupported_platform()

        market = ''
        render_new_style = False
        if "Android" in user_agent:
            templ = "service_interact_mobile.html"
            market = app.android_market_android_uri
            appstore = "Google Play"
            auto_detect = False
            render_new_style = True
        elif "iPhone" in user_agent or 'iPad' in user_agent or 'iPod' in user_agent:
            templ = "service_interact_mobile.html"
            market = app.ios_appstore_ios_uri
            appstore = "App Store"
            auto_detect = False
            render_new_style = True
        elif app.app_id == App.APP_ID_ROGERTHAT:
            # Only show the page containing "New to Rogerthat web? Join for free today!" when it's Rogerthat
            templ = "service_interact_web.html"
            appstore = ""
            auto_detect = False
        else:
            return show_unsupported_platform()

        if render_new_style:
            languages = get_languages_from_header(self.request.headers.get('Accept-Language', None))
            variables = {'profile_info': si,
                         'install_url': get_smartphone_install_url_by_user_agent(user_agent, app.app_id),
                         'app': app}
            self.response.out.write(render('qr_code_scanned', languages, variables, 'web'))
            slog(msg_="QR Code scan", function_=log_analysis.QRCODE_SCANNED, service=sid.user.email(), sid=sid.key().id(), supported_platform=True, from_rogerthat=False)
        else:
            user = users.get_current_user()
            short_link = None
            if user == si.service_user:
                templ = "service_interact_yourself.html"
                short_link = '%s/S/%s' % (get_server_settings().baseUrl, base38.encode_int(sid.shortUrl.key().id()))
            app_url = "rogerthat://q/s/%s/%s" % (user_code, sid.key().id())
            server_settings = get_server_settings()
            set_cookie(self.response, server_settings.cookieQRScanName, "rogerthat://i/qr?%s" \
                       % urlencode((("success", "true"), ("url", app_url))))
            user_friendmap = get_friends_map(user) if user else None
            path = os.path.join(_BASE_DIR, templ)
            self.response.out.write(template.render(path, {
                'debug':DEBUG,
                "continue": self.request.path_qs,
                "service_identity": si,
                "email": si.user.email(),
                "you": get_user_profile(user) if user else None,
                "connected": remove_slash_default(si.user) in user_friendmap.friends if user_friendmap else None,
                "user": user,
                "user_code": user_code,
                'short_link': short_link,
                "app_url": app_url,
                'market': market,
                'service_interaction_id': sid.key().id(),
                'service_interaction_description': sid.description,
                'auto_detect': auto_detect,
                'app': app,
                "appstore": appstore
            }))
