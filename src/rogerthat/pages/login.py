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
import urllib

from rogerthat.bizz import session
from rogerthat.bizz.job import hookup_with_default_services
from rogerthat.bizz.limit import clear_rate_login
from rogerthat.bizz.profile import update_password_hash, create_user_profile
from rogerthat.bizz.session import create_session
from rogerthat.bizz.user import calculate_secure_url_digest, update_user_profile_language_from_headers
from rogerthat.consts import DEBUG
from rogerthat.dal.mobile import get_user_active_mobiles_count
from rogerthat.dal.profile import get_service_or_user_profile
from rogerthat.exceptions import ServiceExpiredException
from rogerthat.models import UserProfile
from rogerthat.rpc import users
from rogerthat.templates import get_languages_from_header
from rogerthat.utils import urlencode, now, azzert, channel
from rogerthat.utils.cookie import set_cookie
from rogerthat.utils.crypto import decrypt, sha256_hex
from google.appengine.api import xmpp
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import template
from rogerthat.settings import get_server_settings


_BASE_DIR = os.path.dirname(__file__)

class SessionHandler(webapp.RequestHandler):

    def redirect(self, url, permanent=False):
        return super(SessionHandler, self).redirect(str(url), permanent)

    def start_session(self, user, cont=None):
        try:
            secret, _ = create_session(user)
        except ServiceExpiredException:
            return self.redirect('/service_disabled')
        server_settings = get_server_settings()
        set_cookie(self.response, server_settings.cookieSessionName, secret)
        if not cont:
            cont = self.request.GET.get("continue", "/")
        if cont:
            self.redirect(cont)
        else:
            self.redirect("/")

    def stop_session(self):
        session.drop_session(users.get_current_session())
        server_settings = get_server_settings()
        set_cookie(self.response, server_settings.cookieSessionName, "")
        self.redirect("/")

class LoginHandler(webapp.RequestHandler):

    def get(self):
        user = users.get_current_user()
        if user:
            self.redirect("/")
        else:
            # Show login.html
            path = os.path.join(_BASE_DIR, 'login.html')
            cont = self.request.GET.get("continue", "/")
            self.response.out.write(template.render(path, {"continue": cont, 'debug':DEBUG}))

class SetPasswordHandler(SessionHandler):

    def return_error(self, reason="Invalid url received."):
        path = os.path.join(_BASE_DIR, 'error.html')
        self.response.out.write(template.render(path, {"reason":reason, "hide_header": True}))


    def parse_data(self, email, data):
        user = users.User(email)
        data = base64.decodestring(data)
        data = decrypt(user, data)
        data = json.loads(data)
        azzert(data["d"] == calculate_secure_url_digest(data))
        return data, user

    def get(self):
        email = self.request.get("email", None)
        data = self.request.get("data", None)

        if not email or not data:
            return self.return_error()

        try:
            data, _ = self.parse_data(email, data)
        except:
            logging.exception("Could not decipher url!")
            return self.return_error()

        now_ = now()
        timestamp = data["t"]
        if not (now_ < timestamp < now_ + 5 * 24 * 3600):
            return self.return_error("The %s link has expired." % data["a"])

        user = users.User(email)
        profile = get_service_or_user_profile(user)
        if profile and profile.lastUsedMgmtTimestamp + 5 * 24 * 3600 > timestamp:
            return self.return_error("You cannot use the %s link more than once." % data["a"])

        path = os.path.join(_BASE_DIR, 'setpassword.html')
        self.response.out.write(template.render(path, {
            'name': data['n'],
            'hide_header': True,
            'data': self.request.get("data"),
            'email': email,
            'action': data['a']
        }))

    def post(self):
        email = self.request.get("email", None)
        password = self.request.get("password", None)
        data = self.request.get("data", None)

        if not (email and password and data):
            return self.redirect("/")

        try:
            data, user = self.parse_data(email, data)
        except:
            logging.exception("Could not decypher url!")
            return self.redirect("/")

        now_ = now()

        language_header = self.request.headers.get('Accept-Language', None)
        language = get_languages_from_header(language_header)[0] if language_header else None

        passwordHash = sha256_hex(password)
        profile = get_service_or_user_profile(user)
        if not profile:
            profile = create_user_profile(user, data['n'], language)
            update_password_hash(profile, passwordHash, now_)
        else:
            def update():
                p = db.get(profile.key())
                if isinstance(profile, UserProfile) and not p.language:
                    p.language = language
                p.passwordHash = passwordHash
                p.lastUsedMgmtTimestamp = now_
                p.termsAndConditionsVersion = 1
                p.put()
                return p
            profile = db.run_in_transaction(update)

        user_agent = self.request.headers.get('User-Agent', '<unknown>')
        server_settings = get_server_settings()
        xmpp.send_message(server_settings.xmppInfoMembers, "User %s registered in the web. User-Agent: %s" % (email, user_agent), message_type=xmpp.MESSAGE_TYPE_CHAT)

        if isinstance(profile, UserProfile):
            hookup_with_default_services.schedule(user, ipaddress=os.environ.get('HTTP_X_FORWARDED_FOR', None))

        self.start_session(user, data["c"])

class ResetPasswordHandler(webapp.RequestHandler):

    def get(self):
        cont = self.request.GET.get("continue", "/")
        email = self.request.GET.get("email", "")
        path = os.path.join(_BASE_DIR, 'resetpassword.html')
        self.response.out.write(template.render(path, {"continue": cont, "hide_header": True, "email": email}))

class AuthenticationRequiredHandler(webapp.RequestHandler):

    def get(self):
        path = "/login"
        cont = self.request.GET.get("continue", None)
        if cont:
            path += "?" + urlencode((("continue", cont),))
        self.redirect(path)

class TermsAndConditionsRequiredHandler(webapp.RequestHandler):

    def get(self):
        cont = self.request.GET.get("continue", "/")
        self.redirect("/terms_and_conditions?" + urlencode((("continue", cont),)))

class TermsAndConditionsHandler(webapp.RequestHandler):

    def get(self):
        user = users.get_current_user()
        cont = self.request.GET.get("continue", "/")

        path = os.path.join(os.path.dirname(__file__), "terms_and_conditions.html")
        self.response.out.write(template.render(path, {
            'user':user,
            'continue': urllib.unquote(cont),
            'mobile_count':get_user_active_mobiles_count(user),
            'session':users.create_logout_url("/") if user else users.create_login_url("/")}))


class LogoutHandler(SessionHandler):

    def get(self):
        user = users.get_current_user()
        self.stop_session()
        channel.send_message(user, u'rogerthat.system.logout')

class OfflineDebugLoginHandler(SessionHandler):

    def get(self):
        from google.appengine.api import users as ae_users
        self.start_session(ae_users.get_current_user())

class AutoLogin(webapp.RequestHandler):

    def parse_data(self, email, data):
        user = users.User(email)
        data = base64.decodestring(data)
        data = decrypt(user, data)
        data = json.loads(data)
        azzert(data["d"] == calculate_secure_url_digest(data))
        return data, user

    def get(self):
        email = self.request.get("email", None)
        data = self.request.get("data", None)
        service_identity = self.request.get("si", None)

        user = users.get_current_user()
        if user:
            users.clear_user()
            channel.send_message(user, u'rogerthat.system.logout')

        if not email or not data:
            logging.warn("not al params received for email: %s and data: %s" % (email, data))
            self.redirect("/")
            return

        try:
            data, _ = self.parse_data(email, data)
        except:
            logging.warn("Could not decipher url! email: %s and data: %s" % (email, data) , exc_info=True)
            self.redirect("/")
            return

        user = users.User(email)

        profile = get_service_or_user_profile(user)
        if not profile:
            logging.warn("profile not found for email: %s" % email)
            self.redirect("/")
            return
        try:
            secret, _ = create_session(user, service_identity=service_identity)
        except ServiceExpiredException:
            return self.redirect('/service_disabled')
        server_settings = get_server_settings()
        set_cookie(self.response, server_settings.cookieSessionName, secret)

        clear_rate_login(user)
        update_user_profile_language_from_headers(profile, self.response.headers)

        params = self.request.GET
        redirect_url = '/'
        if params:
            params = dict((k, v.decode('utf8')) for k, v in params.iteritems())
            del params['email']
            del params['data']
            if "si" in params:
                del params['si']
            redirect_url = "%s?%s" % (redirect_url, urllib.urlencode(params))
        logging.info("Redirecting to url: %s" % redirect_url)
        self.redirect(redirect_url)
