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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import logging
import os
import random
import re
import uuid

from rogerthat import utils
from rogerthat.bizz.friends import get_service_profile_via_user_code, REGISTRATION_ORIGIN_QR, ACCEPT_ID, \
    ACCEPT_AND_CONNECT_ID
from rogerthat.bizz.i18n import get_translator
from rogerthat.bizz.profile import get_profile_for_facebook_user, FailedToBuildFacebookProfileException
from rogerthat.bizz.registration import register_mobile
from rogerthat.dal import parent_key, put_and_invalidate_cache
from rogerthat.dal.app import get_app_by_id
from rogerthat.dal.beacon import get_beacon
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.mobile import get_user_active_mobiles_count
from rogerthat.dal.profile import get_user_profile, get_deactivated_user_profile, get_service_or_user_profile, \
    get_service_profile
from rogerthat.dal.registration import get_last_but_one_registration
from rogerthat.dal.roles import get_service_admins
from rogerthat.dal.service import get_service_identity, get_service_interaction_def
from rogerthat.models import Installation, InstallationLog, Registration, ServiceTranslation, App, ServiceProfile, \
    UserProfile
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile
from rogerthat.rpc.service import BusinessException
from rogerthat.settings import get_server_settings
from rogerthat.templates import render
from rogerthat.to.beacon import GetBeaconRegionsResponseTO
from rogerthat.to.location import BeaconDiscoveredRequestTO
from rogerthat.to.registration import MobileInfoTO, DeprecatedMobileInfoTO
from rogerthat.to.service import UserDetailsTO
from rogerthat.translations import localize, DEFAULT_LANGUAGE
from rogerthat.utils import get_country_code_by_ipaddress, countries, now, azzert, send_mail_via_mime, bizz_check
from rogerthat.utils.app import create_app_user, get_human_user_from_app_user, create_app_user_by_email, \
    get_app_id_from_app_user
from rogerthat.utils.crypto import sha256_hex
from rogerthat.utils.languages import get_iso_lang
from rogerthat.utils.service import remove_slash_default, create_service_identity_user, \
    get_identity_from_service_identity_user
from google.appengine.api import xmpp
from google.appengine.ext import webapp, db, deferred
from google.appengine.ext.webapp import template
from mcfw.rpc import parse_complex_value, serialize_complex_value
from mcfw.utils import chunks


class RegisterMobileViaGoogleOrFacebookHandler(webapp.RequestHandler):

    def get(self):
        user = users.get_current_user()
        ua = self.request.get('ua')
        path = os.path.join(os.path.dirname(__file__), 'register_mobile.html')

        self.response.out.write(template.render(path, {
            'user': user,
            'ua': ua,
            'location': '/register?ua=' + ua,
            'hasMobiles': "true" if user and get_user_active_mobiles_count(user) > 0 else "false"}))

class RegisterMobileViaAndroidGoogleAccountHandler(webapp.RequestHandler):

    def post(self):
        use_xmpp_kick_channel = self.request.get('use_xmpp_kick', 'true') == 'true'
        account, _, age_and_gender_set = register_mobile(users.get_current_user(), use_xmpp_kick_channel=use_xmpp_kick_channel)
        self.response.out.write(json.dumps(dict(result="success", account=account.to_dict(), age_and_gender_set=age_and_gender_set)))


def _log_installation_country(installation, ipaddress):
    country_code = get_country_code_by_ipaddress(ipaddress)
    country_name = countries.name_for_code(country_code)
    db.put(InstallationLog(parent=installation, timestamp=now(), description="Installed from country: %s (%s)" % (country_name, country_code)))

def _verify_app_id(app_id):
    app = get_app_by_id(app_id)
    if app:
        return app
    logging.warn("Could not find app with id: %s", app_id)
    return None


class RegisterInstallIdentifierHandler(webapp.RequestHandler):

    def post(self):
        version = self.request.get("version", None)
        install_id = self.request.get("install_id", None)
        platform = self.request.get("platform", None)
        language = self.request.get("language", None)
        country = self.request.get("country", None)

        if '-' in language:
            language = get_iso_lang(language.lower())
        elif language and country:
            language = '%s_%s' % (language, country)

        if None in (version, install_id, platform):
            logging.error("Insufficient data")
            return

        app_id = self.request.get("app_id", App.APP_ID_ROGERTHAT)
        app = _verify_app_id(app_id)

        if platform == "android":
            mobile_type = Mobile.TYPE_ANDROID_HTTP
        elif platform == "iphone":
            use_xmpp_kick = self.request.get("use_xmpp_kick")
            if use_xmpp_kick is None:
                mobile_type = Mobile.TYPE_LEGACY_IPHONE_XMPP
            elif use_xmpp_kick == "true":
                mobile_type = Mobile.TYPE_IPHONE_HTTP_XMPP_KICK
            else:
                mobile_type = Mobile.TYPE_IPHONE_HTTP_APNS_KICK
        elif platform == "windows_phone":
            mobile_type = Mobile.TYPE_WINDOWS_PHONE
        else:
            logging.error("Unknown platform: %s" % platform)
            return

        now_ = now()
        installation = Installation(key_name=install_id, version=version, platform=mobile_type, timestamp=now(), app_id=app_id)
        installation_log = InstallationLog(parent=installation, timestamp=now_,
                                          description="Installed with language %s" % language)
        installation_log_app_id = InstallationLog(parent=installation, timestamp=now_,
                                          description="Installed with app_id: %s" % app_id)
        puts = [installation, installation_log, installation_log_app_id]

        ipaddress = os.environ.get('HTTP_X_FORWARDED_FOR', None)
        if not ipaddress:
            server_settings = get_server_settings()
            xmpp.send_message(server_settings.xmppInfoMembers, "Received installation registration request without IP address!")
            puts.append(InstallationLog(parent=installation, timestamp=now(),
                                        description="Received installation registration request without IP address!"))
        else:
            puts.append(InstallationLog(parent=installation, timestamp=now(),
                                        description="Resolving country from IP address: %s" % ipaddress))
            deferred.defer(_log_installation_country, installation, ipaddress)

        db.put(puts)

        self.response.headers['Content-Type'] = 'text/json'

        beacon_regions = []
        if app:
            beacon_regions = app.beacon_regions()

        self.response.out.write(json.dumps(dict(result="success", beacon_regions=serialize_complex_value(GetBeaconRegionsResponseTO.fromDBBeaconRegions(beacon_regions), GetBeaconRegionsResponseTO, False))))


class InitiateRegistrationViaEmailVerificationHandler(webapp.RequestHandler):

    def post(self):
        version = self.request.get("version", 0)
        email = self.request.get("email", None)
        registration_time = self.request.get("registration_time", None)
        device_id = self.request.get("device_id", None)
        registration_id = self.request.get("registration_id", None)
        request_signature = self.request.get("request_signature", None)
        install_id = self.request.get("install_id", None)
        language = self.request.get("language", None)
        country = self.request.get("country", None)
        request_id = self.request.get("request_id", None)
        app_id = self.request.get("app_id", App.APP_ID_ROGERTHAT)

        if language is None:
            language = DEFAULT_LANGUAGE
        elif '-' in language:
            language = get_iso_lang(language.lower())
        elif language and country:
            language = '%s_%s' % (language, country)

        server_settings = get_server_settings()

        # Verify request signature.
        calculated_signature = sha256_hex(version + email + " " + registration_time + " " + device_id + " " + \
                                           registration_id + " " + base64.b64decode(server_settings.registrationEmailSignature.encode("utf8")))
        if request_signature.upper() != calculated_signature.upper():
            self.response.set_status(501)
            return

        # Validate input.
        version = int(version)
        azzert(version > 0 and version <= 2)
        registration_time = int(registration_time)
        # XXX: validating the email would be an improvement

        app = _verify_app_id(app_id)
        azzert(app is not None, "app_id is not found")

        if " " in email:
            self.response.set_status(502)
            result = localize(language, "Spaces are not allowed in an e-mail address")
            self.response.out.write(json.dumps(dict(result=result)))
            return

        # User regex
        self.response.headers['Content-Type'] = 'text/json'
        if app.user_regex:
            app_user = create_app_user_by_email(email, app_id)
            existing_profile = get_service_or_user_profile(app_user)
            if existing_profile and isinstance(existing_profile, UserProfile):
                pass  # Existing users are allowed to register
            else:
                # Check app.user_regex
                regexes = app.user_regex.splitlines()
                for regex in regexes:
                    if re.match(regex, email):
                        break
                else:
                    self.response.set_status(502)
                    result = localize(language, "You can not register with this e-mail address")
                    self.response.out.write(json.dumps(dict(result=result)))
                    return

        @db.non_transactional
        def get_service_admins_non_transactional(app_user):
            return list(get_service_admins(app_user))

        def trans():
            db_puts = list()

            # Create registration entry.
            installation = Installation.get_by_key_name(install_id) if install_id else None
            app_user = create_app_user(users.User(email), app_id)
            registration = None
            if version == 2:
                registration = Registration.get_by_key_name(registration_id, parent_key(app_user))
                if registration and registration.request_id == request_id:
                    InstallationLog(parent=registration.installation, timestamp=now(), registration=registration,
                                    pin=registration.pin,
                                    description="Received a HTTP request retry for 'request pin'. Not sending a new mail.").put()
                    return

            rogerthat_profile = get_service_or_user_profile(users.User(email))
            if rogerthat_profile and isinstance(rogerthat_profile, ServiceProfile):
                # some guy tries to register a mobile on a service account ?!?
                variables = dict(email=email)
                body = render("somebody_tries_to_register_his_mobile_on_your_service_account_warning", [language], variables)
                html = render("somebody_tries_to_register_his_mobile_on_your_service_account_warning_html", [language], variables)
                logging.info("Sending message to %s\n%s" % (email, body))
                recipients = [email]

                for admin in get_service_admins_non_transactional(app_user):
                    recipients.append(admin.user_email)

                msg = MIMEMultipart('alternative')
                msg['Subject'] = "Warning, possibly somebody tries to hack your service account."
                msg['From'] = server_settings.senderEmail
                msg['To'] = ', '.join(recipients)
                msg.attach(MIMEText(body.encode('utf-8'), 'plain', 'utf-8'))
                msg.attach(MIMEText(html.encode('utf-8'), 'html', 'utf-8'))
                send_mail_via_mime(server_settings.senderEmail, recipients, msg)

                warning = InstallationLog(parent=installation, timestamp=now(),
                                     description="Warning somebody tries to register a mobile with the email address of service account %s" % email)
                db_puts.append(warning)
            else:
                profile = get_user_profile(app_user)
                if profile:
                    name = profile.name
                else:
                    deactivated_profile = get_deactivated_user_profile(app_user)
                    name = deactivated_profile.name if deactivated_profile else None
                if not registration:
                    registration = Registration(parent=parent_key(app_user), key_name=registration_id)
                registration.timestamp = registration_time
                registration.device_id = device_id
                server_settings = get_server_settings()
                for pin, static_email in chunks(server_settings.staticPinCodes, 2):
                    if email == static_email and len(pin) == 4:
                        registration.pin = int(pin)
                        pin_str = unicode(registration.pin).rjust(4, '0')
                        utils.send_mail(server_settings.dashboardEmail,
                                        server_settings.supportWorkers,
                                        pin_str,
                                        u'Configured pin code %s for %s' % (pin_str, app_user.email()))
                        break

                else:
                    registration.pin = random.randint(1000, 9999)
                registration.timesleft = 3
                registration.installation = installation
                registration.request_id = request_id
                registration.language = language
                db_puts.append(registration)

                i1 = InstallationLog(parent=registration.installation, timestamp=now(), registration=registration, pin=registration.pin,
                                     description="%s requested pin" % email)
                db_puts.append(i1)


                # Send email with pin.
                app = get_app_by_id(app_id)
                variables = dict(pin=registration.pin, name=name, app=app)
                body = render("activation_code_email", [language], variables)
                html = render("activation_code_email_html", [language], variables)

                logging.info("Sending message to %s\n%s" % (email, body))
                msg = MIMEMultipart('alternative')
                msg['Subject'] = localize(language, "%(app_name)s mobile registration", app_name=app.name)
                msg['From'] = server_settings.senderEmail if app.type == App.APP_TYPE_ROGERTHAT else ("%s <%s>" % (app.name, app.dashboard_email_address))
                msg['To'] = email
                msg.attach(MIMEText(body.encode('utf-8'), 'plain', 'utf-8'))
                msg.attach(MIMEText(html.encode('utf-8'), 'html', 'utf-8'))

                send_mail_via_mime(server_settings.senderEmail, email, msg)

                i2 = InstallationLog(parent=registration.installation, timestamp=now(), registration=registration, pin=registration.pin,
                                     description="Sent email to %s with pin %s" % (email, registration.pin))
                db_puts.append(i2)

            db.put(db_puts)

        xg_on = db.create_transaction_options(xg=True)
        db.run_in_transaction_options(xg_on, trans)


class VerifyEmailWithPinHandler(webapp.RequestHandler):

    def post(self):
        version = self.request.get("version", 0)
        email = self.request.get("email", None)
        registration_time = self.request.get("registration_time", None)
        device_id = self.request.get("device_id", None)
        registration_id = self.request.get("registration_id", None)
        pin_code = self.request.get("pin_code", None)
        pin_signature = self.request.get("pin_signature", None)
        request_id = self.request.get('request_id', None)
        app_id = self.request.get("app_id", App.APP_ID_ROGERTHAT)
        use_xmpp_kick_channel = self.request.get('use_xmpp_kick', 'true') == 'true'
        GCM_registration_id = self.request.get('GCM_registration_id', '')

        server_settings = get_server_settings()

        # Verify request signature.
        calculated_signature = sha256_hex(version + " " + email + " " + registration_time + " " + device_id + " " + \
                                       registration_id + " " + pin_code + base64.b64decode(server_settings.registrationPinSignature.encode("utf8")))
        if pin_signature.upper() != calculated_signature.upper():
            self.response.set_status(500)
            return

        # Validate input.
        version = int(version)
        azzert(version > 0 and version <= 2)
        registration_time = int(registration_time)
        pin_code = int(pin_code)
        # XXX: validating the email address would be an improvement.

        app = _verify_app_id(app_id)
        azzert(app is not None, "app_id is not found")

        human_user = users.User(email)
        app_user = create_app_user(human_user, app_id)
        registration = Registration.get_by_key_name(registration_id, parent_key(app_user))

        logging.info("Pin received for email %s and device_id [%s] of type %s and len %d - expecting device_id [%s] of type %s and len %d" \
                     % (email, device_id, type(device_id), len(device_id), registration.device_id, type(registration.device_id), len(registration.device_id)))

        azzert(registration)
        azzert(registration.timestamp == registration_time)
        azzert(registration.device_id == device_id)
        azzert(registration.timesleft > 0)

        is_retry = version >= 2 and request_id == registration.request_id
        registration.request_id = request_id

        # Handle request
        self.response.headers['Content-Type'] = 'text/json'
        if pin_code != registration.pin:
            # Allow pin code from previous registration
            previous_registration = get_last_but_one_registration(registration.installation)
            if not previous_registration or pin_code != previous_registration.pin or previous_registration.parent_key() != registration.parent_key():
                if not is_retry:
                    registration.timesleft -= 1
                    installation_log = InstallationLog(parent=registration.installation, timestamp=now(), registration=registration,
                                                       pin=pin_code, description="Entered wrong pin: %04d" % pin_code)
                else:
                    installation_log = InstallationLog(parent=registration.installation, timestamp=now(), registration=registration,
                                                       pin=pin_code, description="Received wrong pin again in HTTP request retry. Not seeing this as a failed attempt (already processed it).")
                db.put([registration, installation_log])
                self.response.out.write(json.dumps(dict(result="fail", attempts_left=registration.timesleft)))
                return

        account, registration.mobile, age_and_gender_set = register_mobile(human_user, app_id=app_id,
                                                                           use_xmpp_kick_channel=use_xmpp_kick_channel,
                                                                           GCM_registration_id=GCM_registration_id,
                                                                           language=registration.language)
        installation_log = InstallationLog(parent=registration.installation, timestamp=now(), registration=registration,
                                           pin=pin_code, mobile=registration.mobile, profile=get_user_profile(app_user),
                                           description="Entered correct pin: %04d%s" % (pin_code, " (in HTTP request retry)" if is_retry else ""))
        db.put([registration, installation_log])

        self.response.out.write(json.dumps(dict(result="success", account=account.to_dict(), age_and_gender_set=age_and_gender_set)))

class RegisterMobileViaFacebookHandler(webapp.RequestHandler):

    def post(self):
        version = self.request.get("version", None)
        install_id = self.request.get("install_id", None)
        registration_time = self.request.get("registration_time", None)
        device_id = self.request.get("device_id", None)
        registration_id = self.request.get("registration_id", None)
        access_token = self.request.get("access_token", None)
        signature = self.request.get("signature", None)
        language = self.request.get("language", None)
        country = self.request.get("country", None)
        app_id = self.request.get("app_id", App.APP_ID_ROGERTHAT)
        use_xmpp_kick_channel = self.request.get('use_xmpp_kick', 'true') == 'true'
        GCM_registration_id = self.request.get('GCM_registration_id', '')

        if '-' in language:
            language = get_iso_lang(language.lower())
        elif language and country:
            language = '%s_%s' % (language, country)

        server_settings = get_server_settings()

        calculated_signature = sha256_hex(version + " " + install_id + " " + registration_time + " " + device_id + " " + \
                                       registration_id + " " + access_token + base64.b64decode(server_settings.registrationMainSignature.encode("utf8")))
        if signature.upper() != calculated_signature.upper():
            logging.error("Invalid request signature.")
            self.response.set_status(500)
            return

        app = _verify_app_id(app_id)
        azzert(app is not None, "app_id is not found")

        installation = Installation.get_by_key_name(install_id) if install_id else None
        InstallationLog(parent=installation, timestamp=now(),
                        description="Creating facebook based profile & validating registration request. Language: %s" % language).put()
        try:
            profile = get_profile_for_facebook_user(access_token, None, True, app_id=app_id)
        except FailedToBuildFacebookProfileException, fe:
            logging.warn("Failed to build facebook profile", exc_info=True)
            InstallationLog(parent=installation, timestamp=now(),
                            description="ERROR: Failed to build facebook profile: %s" % fe).put()
            self.response.set_status(500)
            self.response.out.write(json.dumps(dict(error=fe.message)))
            return
        except Exception, e:
            logging.error("Failed to build facebook profile.", exc_info=True)
            InstallationLog(parent=installation, timestamp=now(),
                            description="ERROR: Failed to build facebook profile: %s" % e).put()
            self.response.set_status(500)
            return

        human_user = get_human_user_from_app_user(profile.user)

        # Create registration entry.
        self.response.headers['Content-Type'] = 'text/json'
        registration = Registration(parent=parent_key(profile.user), key_name=registration_id)
        registration.timestamp = int(registration_time)
        registration.device_id = device_id
        registration.pin = -1
        registration.timesleft = -1
        registration.installation = installation
        registration.language = language
        registration.put()
        account, registration.mobile, age_and_gender_set = register_mobile(human_user, app_id=app_id,
                                                                           use_xmpp_kick_channel=use_xmpp_kick_channel,
                                                                           GCM_registration_id=GCM_registration_id,
                                                                           language=registration.language)
        installation_log = InstallationLog(parent=installation, timestamp=now(), profile=profile, \
                                           description="Profile created & registration request validated.", \
                                           registration=registration, mobile=registration.mobile)
        db.put([registration, installation_log])
        self.response.out.write(json.dumps(dict(account=account.to_dict(), email=human_user.email(), age_and_gender_set=age_and_gender_set)))

class RegisterMobileViaQRHandler(webapp.RequestHandler):

    def post(self):
        from rogerthat.pages.shortner import get_short_url_by_code
        from rogerthat.service.api import friends as service_api_friends

        version = self.request.get("version", None)
        install_id = self.request.get("install_id", None)
        registration_time = self.request.get("registration_time", None)
        device_id = self.request.get("device_id", None)
        registration_id = self.request.get("registration_id", None)
        qr_url = self.request.get("qr_url", None)
        signature = self.request.get("signature", None)
        language = self.request.get("language", None)
        country = self.request.get("country", None)
        app_id = self.request.get("app_id", App.APP_ID_ROGERTHAT)
        use_xmpp_kick_channel = self.request.get('use_xmpp_kick', 'true') == 'true'
        GCM_registration_id = self.request.get('GCM_registration_id', '')

        if '-' in language:
            language = get_iso_lang(language.lower())
        elif language and country:
            language = '%s_%s' % (language, country)

        server_settings = get_server_settings()

        calculated_signature = sha256_hex(version + " " + install_id + " " + registration_time + " " + device_id + " " + \
                                       registration_id + " " + qr_url + base64.b64decode(server_settings.registrationMainSignature.encode("utf8")))

        try:
            if signature.upper() != calculated_signature.upper():
                logging.error("Invalid request signature.")
                self.response.set_status(500)
                return

            app = _verify_app_id(app_id)
            azzert(app is not None, "app_id is not found")
            bizz_check(install_id and qr_url, u"Could not validate QR code")

            installation = Installation.get_by_key_name(install_id)
            if not installation:
                platform = self.request.get("platform", None)
                if platform == "android":
                    mobile_type = Mobile.TYPE_ANDROID_HTTP
                elif platform == "iphone":
                    if use_xmpp_kick_channel:
                        mobile_type = Mobile.TYPE_IPHONE_HTTP_XMPP_KICK
                    else:
                        mobile_type = Mobile.TYPE_IPHONE_HTTP_APNS_KICK
                elif platform == "windows_phone":
                    mobile_type = Mobile.TYPE_WINDOWS_PHONE
                else:
                    logging.error("Unknown platform: %s" % platform)
                    self.response.set_status(500)
                    return

                now_ = now()
                installation = Installation(key_name=install_id, version=version, platform=mobile_type, timestamp=now_, app_id=app_id)
                installation_log = InstallationLog(parent=installation, timestamp=now_,
                                              description="Installed with language %s" % language)
                installation_log_app_id = InstallationLog(parent=installation, timestamp=now_,
                                                  description="Installed with app_id: %s" % app_id)
                put_and_invalidate_cache(installation, installation_log, installation_log_app_id)

            InstallationLog(parent=installation, timestamp=now(),
                            description="Creating qr based profile & validating registration request. Language: %s, QR url: %s" % (language, qr_url)).put()

            m = re.match('(.*)/(M|S)/(.*)', qr_url)
            bizz_check(m, u"Could not validate QR code")
            entry_point = m.group(2)
            code = m.group(3)

            bizz_check(entry_point == "S", u"Could not validate QR code")

            su = get_short_url_by_code(code)
            bizz_check(su, u"Could not validate QR code")

            logging.debug("register_via_qr qr_url: %s", qr_url)
            logging.debug("register_via_qr su.full: %s", su.full)

            match = re.match("^/q/s/(.+)/(\\d+)$", su.full)
            bizz_check(match, u"Could not validate QR code")

            user_code = match.group(1)
            service_profile = get_service_profile_via_user_code(user_code)
            bizz_check(service_profile, u"Could not validate QR code")

            service_user = service_profile.user

            sid = int(match.group(2))
            service_interaction_def = get_service_interaction_def(service_user, int(sid))
            service_identity_user = create_service_identity_user(service_user, service_interaction_def.service_identity)
            service_identity = get_identity_from_service_identity_user(service_identity_user)
            svc_profile = get_service_profile(service_user)

            logging.debug("register_via_qr service_identity_user: %s", service_identity_user)

            human_user = users.User(u"user%s@rogerth.at" % uuid.uuid4().get_hex())
            app_user = create_app_user(human_user, app_id)
            from rogerthat.bizz.profile import _create_new_avatar
            avatar, _ = _create_new_avatar(app_user, add_trial_overlay=False)
            user_profile = UserProfile(parent=parent_key(app_user), key_name=app_user.email())
            user_profile.name = None
            user_profile.language = language
            user_profile.avatarId = avatar.key().id()
            user_profile.app_id = get_app_id_from_app_user(app_user)
            user_details = [UserDetailsTO.fromUserProfile(user_profile)]
            r = service_api_friends.register(None, None, svc_profile,
                                             service_identity=service_identity,
                                             user_details=user_details,
                                             origin=REGISTRATION_ORIGIN_QR,
                                             PERFORM_CALLBACK_SYNCHRONOUS=True)

            logging.debug("register_via_qr with id: %s", r)
            bizz_check(r == ACCEPT_ID or r == ACCEPT_AND_CONNECT_ID, u"Service denied your install")

            installation.service_identity_user = service_identity_user
            installation.service_callback_result = r
            installation.qr_url = su.full[4:]
            installation.put()

            # Create registration entry.
            self.response.headers['Content-Type'] = 'text/json'
            registration = Registration(parent=parent_key(app_user), key_name=registration_id)
            registration.timestamp = int(registration_time)
            registration.device_id = device_id
            registration.pin = -1
            registration.timesleft = -1
            registration.installation = installation
            registration.language = language
            registration.put()
            account, registration.mobile, age_and_gender_set = register_mobile(human_user, app_id=app_id,
                                                                               use_xmpp_kick_channel=use_xmpp_kick_channel,
                                                                               GCM_registration_id=GCM_registration_id,
                                                                               language=registration.language)
            installation_log = InstallationLog(parent=installation, timestamp=now(), profile=get_user_profile(app_user), \
                                               description="Profile created & registration request validated.", \
                                               registration=registration, mobile=registration.mobile)
            db.put([registration, installation_log])
            self.response.out.write(json.dumps(dict(account=account.to_dict(), email=human_user.email(), age_and_gender_set=age_and_gender_set)))
        except BusinessException, be:
            logging.debug("BusinessException during via QR handler %s", be)
            self.response.set_status(500)
            return


class FinishRegistrationHandler(webapp.RequestHandler):

    def post(self):
        from rogerthat.bizz.registration import finish_registration
        account = self.request.POST['account']
        password = self.request.POST['password']
        accounts = self.request.POST.get('accounts', u"[]")
        if not users.set_json_rpc_user(account, password, True):
            self.response.set_status(401, "could not authenticate")
            return

        app_id = self.request.POST.get("app_id", App.APP_ID_ROGERTHAT)
        app = _verify_app_id(app_id)
        azzert(app is not None, "app_id is not found")

        mobileInfoJSON = json.loads(self.request.POST["mobileInfo"])
        if mobileInfoJSON.get('version', 1) == 1:
            oldMobileInfo = parse_complex_value(DeprecatedMobileInfoTO, mobileInfoJSON, False)
            mobileInfo = MobileInfoTO.fromDeprecatedMobileInfoTO(oldMobileInfo)
        else:
            mobileInfo = parse_complex_value(MobileInfoTO, mobileInfoJSON, False)

        invitor_code = self.request.POST.get('invitor_code')
        invitor_secret = self.request.POST.get('invitor_secret')

        beaconsString = self.request.POST.get('beacons')
        if beaconsString:
            beacons = json.loads(beaconsString)
        else:
            beacons = mobileInfoJSON.get('beacons')  # Beacons where places inside mobile info in 1.0.161.I

        ipaddress = os.environ.get('HTTP_X_FORWARDED_FOR', None)
        if not ipaddress:
            server_settings = get_server_settings()
            xmpp.send_message(server_settings.xmppInfoMembers, "Received finish registration request without origin ipaddress!")
        else:
            ipaddress = unicode(ipaddress)

        mobile = finish_registration(account, mobileInfo, accounts, invitor_code, invitor_secret, ipaddress)

        discoveredBeacons = dict()
        if beacons:
            logging.info("User discovered the following beacons during registration: %s", beacons)
            for b in beacons:
                beacon_discovered_request_to = parse_complex_value(BeaconDiscoveredRequestTO, b, False)
                beacon_uuid = beacon_discovered_request_to.uuid.lower()
                beacon = get_beacon(beacon_uuid, beacon_discovered_request_to.name)
                if not beacon:
                    logging.warn("Beacon not found uuid: %s name: %s" % (beacon_uuid, beacon_discovered_request_to.name))
                else:
                    friend_map = get_friends_map(mobile.user)
                    if remove_slash_default(beacon.service_identity_user) not in friend_map.friends:
                        si = get_service_identity(beacon.service_identity_user)
                        if si.beacon_auto_invite:
                            if app_id in si.appIds:
                                translator = get_translator(si.service_user, [ServiceTranslation.IDENTITY_TEXT], mobile.localeLanguage)
                                discoveredBeacons[beacon.service_identity_user] = dict(name=translator.translate(ServiceTranslation.IDENTITY_TEXT, si.name, mobile.localeLanguage),
                                                                                       avatar_url=si.avatarUrl,
                                                                                       friend_email=remove_slash_default(beacon.service_identity_user).email())
                            else:
                                logging.info("Beacon detected but %s does not contain app_id %s: {uuid: %s, name: %s}",
                                            beacon.service_identity_user, app_id, beacon_uuid, beacon_discovered_request_to.name)
                        else:
                            logging.info("Beacon detected but %s does not allow auto invite {app_id %s, uuid: %s, name: %s}",
                                            beacon.service_identity_user, app_id, beacon_uuid, beacon_discovered_request_to.name)
        r = json.dumps(dict(discovered_beacons=sorted(discoveredBeacons.values(), key=lambda x: x['name'])))
        logging.info("User discovered the following new beacons during registration: %s", r)
        self.response.out.write(r)

class LogRegistrationStepHandler(webapp.RequestHandler):

    STEPS = {'1': "'Create account' button pressed",
             '1a': "'Location usage' continue pressed",
             '1b': "'Notification usage' continue pressed",
             '2a': "'Use Facebook' button pressed",
             '2b': "'Use e-mail' button pressed"}

    def post(self):
        install_id = self.request.get("install_id", None)
        step = self.request.get("step", None)
        azzert(step is not None, "step is a required argument")
        msg = LogRegistrationStepHandler.STEPS.get(step, "Unknown step: %s" % step)
        installation = Installation.get_by_key_name(install_id) if install_id else None
        InstallationLog(parent=installation, timestamp=now(), description=msg).put()


class InitServiceAppHandler(webapp.RequestHandler):

    def post(self):
        version = self.request.get("version", None)
        install_id = self.request.get("install_id", None)
        registration_time = self.request.get("registration_time", None)
        device_id = self.request.get("device_id", None)
        registration_id = self.request.get("registration_id", None)
        signature = self.request.get("signature", None)
        language = self.request.get("language", None)
        country = self.request.get("country", None)
        app_id = self.request.get("app_id", App.APP_ID_ROGERTHAT)
        use_xmpp_kick_channel = self.request.get('use_xmpp_kick', 'true') == 'true'
        GCM_registration_id = self.request.get('GCM_registration_id', '')
        ysaaa_guid = self.request.get("service", None)

        if not ysaaa_guid:
            logging.warn('Missing YSAAA guid!\nPOST params: %s', self.request.POST)
            return self.abort(401)

        server_settings = get_server_settings()

        calculated_signature = sha256_hex(version + " " + install_id + " " + registration_time + " " + device_id + " " + \
                                       registration_id + " " + ysaaa_guid + base64.b64decode(server_settings.registrationMainSignature.encode("utf8")))
        if signature.upper() != calculated_signature.upper():
            logging.error("Invalid request signature.")
            self.response.set_status(500)
            return

        for ysaaa_hash, _ in chunks(server_settings.ysaaaMapping, 2):
            if ysaaa_guid == ysaaa_hash:
                break
        else:
            azzert(False, u"ysaaa registration received but not found mapping")


        if '-' in language:
            language = get_iso_lang(language.lower())
        elif language and country:
            language = '%s_%s' % (language, country)

        user_id = str(uuid.uuid4()).replace("-", "")
        user = users.User("%s@ysaaa.rogerth.at" % user_id)
        account, _, age_and_gender_set = register_mobile(user, user_id, app_id,
                                                         use_xmpp_kick_channel=use_xmpp_kick_channel,
                                                         GCM_registration_id=GCM_registration_id,
                                                         language=language,
                                                         ysaaa=True)
        self.response.out.write(json.dumps(dict(result="success", account=account.to_dict(),
                                                age_and_gender_set=age_and_gender_set)))
