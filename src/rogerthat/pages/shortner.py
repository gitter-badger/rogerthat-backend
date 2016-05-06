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
from pprint import pformat
import re
import urllib

from rogerthat.bizz import log_analysis
from rogerthat.bizz.friends import get_service_profile_via_user_code, get_profile_info_via_user_code
from rogerthat.dal import parent_key_unsafe
from rogerthat.dal.app import get_app_name_by_id, get_app_by_id
from rogerthat.dal.service import get_service_identity, get_service_interaction_def
from rogerthat.models import ShortURL, UserInvitationSecret
from rogerthat.settings import get_server_settings
from rogerthat.templates import get_languages_from_header, render
from rogerthat.utils import base42, base65, now, determine_if_platform_supports_rogerthat_by_user_agent, \
    get_smartphone_install_url_by_user_agent, slog, base38
from rogerthat.utils.service import create_service_identity_user, remove_slash_default
from google.appengine.ext import webapp, db, deferred


_TMPL = """<html>
    <body>
        <noscript style="color:#000; font-size:4em;">Your browser does not support JavaScript! Please use a JavaScript enabled browser.</noscript>
        <script type="text/javascript">
<!--
var url = "%s";
window.location=url;
console.log("Redirected to "+ url);
-->
        </script>
    </body>
</html>"""

_BASE_DIR = os.path.dirname(__file__)

def get_short_url_and_filtered_code_by_code(code):
    su = None
    filtered_code = code
    if base38.is_base38(code):
        short_url_id = base38.decode_int(code)
        su = ShortURL.get(short_url_id)

    if su is None and base42.is_base42(code):
        short_url_id = base42.decode_int(code)
        su = ShortURL.get(short_url_id)

    if su is None:
        unquoted_code = urllib.unquote(code)
        filtered_code = base42.filter_unknown_base42_chars(unquoted_code)
        short_url_id = base42.decode_int(filtered_code)
        su = ShortURL.get(short_url_id)

    if su is None:
        filtered_code = base38.filter_unknown_base38_chars(unquoted_code)
        short_url_id = base38.decode_int(filtered_code)
        su = ShortURL.get(short_url_id)

    return su, filtered_code

def get_short_url_by_code(code):
    return get_short_url_and_filtered_code_by_code(code)[0]

class ShortUrlHandler(webapp.RequestHandler):

    def redirect(self, url, permanent=False):
        if "://" not in url:
            url = get_server_settings().baseUrl + url
        return super(ShortUrlHandler, self).redirect(str(url), permanent)

    def get(self, entry_point, code):
        language = get_languages_from_header(self.request.headers.get('Accept-Language', None))
        # In the past we used base42 to encode QR-Codes, due to problems we switched to base38. Currently base38 falls back to base42
        su, code = get_short_url_and_filtered_code_by_code(code)
        user_agent = self.request.environ.get('HTTP_USER_AGENT')
        logging.info("Environ: %s" % pformat(self.request.environ))
        for header, value in self.request.headers.iteritems():
            logging.info("%s: %s" % (header, value))
        if not user_agent or "Rogerth.at" in user_agent or "Rogerthat" in user_agent:
            # It's a iphone/android rogerthat client!
            logging.info("# It's a iphone/android rogerthat client!")
            if not su:
                logging.info("Unknown short url.")
                self.redirect("/")
            else:
                redirect_url = su.full
                params = self.request.GET
                if params:
                    params = dict((k, v.decode('utf8')) for k, v in params.iteritems())
                    if 's' in params and not 'u' in params and su.full.startswith("/q/i"):
                        profile_info = get_profile_info_via_user_code(su.full[4:])
                        if profile_info:
                            params['u'] = profile_info.name
                    params = dict((k, v.encode('utf8')) for k, v in params.iteritems())
                    redirect_url = "%s?%s" % (redirect_url, urllib.urlencode(params))
                logging.info("Redirecting to full url: %s." % redirect_url)
                self.redirect(redirect_url)
            return

        # It's a web-browser!
        logging.info("It is a web browser.")
        if not su:
            # Unknown short url
            logging.info("Unknown short url.")
            self.response.out.write(_TMPL % "/")
            return

        # We know this url!
        logging.info("We know this short url.")
        if su.full.startswith("/q/i"):
            # It's a user invitation code! (for now also used for default svc)
            self._handle_profile_based_invitations(entry_point, code, su, user_agent, language)
            return

        if su.full.startswith("/q/s/"):
            # It's a service interaction url
            self._handle_service_interaction_based_invitation(entry_point, code, language, su, user_agent)
            return

        # We were not able to redirect you, so we just display /
        self.response.out.write(_TMPL % su.full)

    def _handle_invitation_with_secret(self, code, su, user_agent, secret, profile_info, language):
        # There is a secret!
        logging.info("There is a secret!")
        if determine_if_platform_supports_rogerthat_by_user_agent(user_agent):  # It's a supported platform ===> redirect into the app
            logging.info("It's a supported platform ===> redirect into the app!")
            uis = UserInvitationSecret.get_by_id(base65.decode_int(secret), parent=parent_key_unsafe(remove_slash_default(profile_info.user)))
            if uis:
                deferred.defer(_set_redirect_timestamp_of_user_invitation_secret, uis.key(), now(), _transactional=db.is_in_transaction())
            logging.info("Redirecting into Rogerthat application.")
            self.redirect("rogerthat:/%s?%s" % (su.full, urllib.urlencode((("s", secret), ("u", profile_info.name.encode('utf8'))))))
        else:
            # Unsupported platform ===> Show sorry page with install instructions for android & iphone
            logging.info("Unsupported platform ===> Show sorry page with install instructions for android & iphone")
            context = {'profile': profile_info,
                       'payload': urllib.urlencode([("chl", "%s/S/%s?s=%s" % (get_server_settings().baseUrl, code, secret))]),
                       'app_name': get_app_name_by_id(profile_info.app_id)}
            self.response.out.write(render('sorry_step2', language, context, 'web'))

    def _handle_after_qr_code_scan(self, user_agent, profile_info, language, sid=None):
        variables = {'profile_info':profile_info,
                     'install_url':get_smartphone_install_url_by_user_agent(user_agent, profile_info.app_id),
                     'app':get_app_by_id(profile_info.app_id)}
        supported_platform = determine_if_platform_supports_rogerthat_by_user_agent(user_agent)
        if supported_platform:
            self.response.out.write(render('qr_code_scanned', language, variables, 'web'))
        else:
            self.response.out.write(render('qr_code_scanned_unsupported_platform', language, variables, 'web'))

        slog(msg_="QR Code scan", function_=log_analysis.QRCODE_SCANNED, service=profile_info.user.email(), sid=sid,
             supported_platform=supported_platform, from_rogerthat=False)

    def _handle_invitation_without_secret(self, entry_point, su, user_agent, profile_info, language):
        if entry_point == "S":  # It's a QR-Code!
            logging.info("It's a QR-Code!")
        else:
            logging.warning("Someone got a message with an M profile link without secret! This should not happen.")

        self._handle_after_qr_code_scan(user_agent, profile_info, language, None)

    def _handle_profile_based_invitations(self, entry_point, code, su, user_agent, language):
        logging.info("It's a user invitation code!")
        profile_info = get_profile_info_via_user_code(su.full[4:])
        if not profile_info:  # Profile of usercode not found. Sorry we can't help you :(
            logging.info("Profile of usercode not found. Sorry we can't help you :(")
            self.response.out.write(_TMPL % "/")
        else:
            logging.info("User is %s" % profile_info.user.email())
            secret = self.request.get('s', None)
            if secret:
                self._handle_invitation_with_secret(code, su, user_agent, secret, profile_info, language)
            else:
                self._handle_invitation_without_secret(entry_point, su, user_agent, profile_info, language)

    def _handle_service_interaction_based_invitation(self, entry_point, code, language, su, user_agent):
        match = re.match("^/q/s/(.+)/(\\d+)$", su.full)
        if not match:
            self.response.out.write(_TMPL % su.full)
        else:
            user_code = match.group(1)

            service_profile = get_service_profile_via_user_code(user_code)

            if not service_profile:  # Profile of usercode not found. Sorry we can't help you :(
                logging.info("Profile of usercode not found. Sorry we can't help you :(")
                self.response.out.write(_TMPL % "/")
                return

            service_user = service_profile.user

            if entry_point == "S":  # It's a QR-Code
                logging.info("It's a QR-Code")
                sid = int(match.group(2))
                service_interaction_def = get_service_interaction_def(service_user, int(sid))
                service_identity_user = create_service_identity_user(service_user, service_interaction_def.service_identity)
                service_identity = get_service_identity(service_identity_user)
                self._handle_after_qr_code_scan(user_agent, service_identity, language, sid)
                return

            if entry_point == "M":
                logging.info("It's a Message")
            else:
                logging.warn("Expected entry_point 'M' but got '%s'." % entry_point)

            if determine_if_platform_supports_rogerthat_by_user_agent(user_agent):
                logging.info("Redirecting into Rogerthat application.")
                self.redirect("rogerthat:/%s" % su.full)
            else:
                logging.info("Unsupported platform ===> Show sorry page with install instructions for android & iphone")

                # Get service identity by sid
                sid = int(match.group(2))
                service_interaction_def = get_service_interaction_def(service_user, int(sid))
                service_identity_user = create_service_identity_user(service_user, service_interaction_def.service_identity)
                service_identity = get_service_identity(service_identity_user)

                variables = {'profile': service_identity,
                             'payload': urllib.urlencode([("chl", "%s/S/%s" % (get_server_settings().baseUrl, code))]),
                             'app_name': get_app_name_by_id(service_identity.app_id)}
                # Unsupported platform ===> Show sorry page with install instructions for android & iphone
                self.response.out.write(render('sorry_step2', language, variables, 'web'))


def _set_redirect_timestamp_of_user_invitation_secret(user_invitation_secret_key, timestamp):
    def trans():
        uis = UserInvitationSecret.get(user_invitation_secret_key)
        uis.redirected_timestamp = timestamp
        uis.put()
    db.run_in_transaction(trans)
