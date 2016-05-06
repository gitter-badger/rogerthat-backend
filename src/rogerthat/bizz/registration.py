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

import json
import logging
import types
import uuid
from random import choice

from google.appengine.api import xmpp, urlfetch
from google.appengine.ext import db, deferred

from mcfw.consts import MISSING
from mcfw.rpc import returns, arguments
from mcfw.utils import chunks
from rogerthat.bizz.friends import ack_invitation_by_invitation_secret, makeFriends, ORIGIN_YSAAA, \
    REGISTRATION_ORIGIN_QR, ACCEPT_AND_CONNECT_ID, register_result_response_receiver, REGISTRATION_ORIGIN_DEFAULT
from rogerthat.bizz.job import hookup_with_default_services
from rogerthat.bizz.messaging import sendMessage, send_messages_after_registration
from rogerthat.bizz.profile import create_user_profile
from rogerthat.bizz.system import update_settings_response_handler, unregister_mobile
from rogerthat.bizz.user import reactivate_user_profile
from rogerthat.capi.system import updateSettings
from rogerthat.consts import APPSCALE
from rogerthat.consts import MC_DASHBOARD
from rogerthat.dal import parent_key, put_and_invalidate_cache
from rogerthat.dal.app import get_app_by_user, get_app_by_id, get_app_and_translations_by_app_id
from rogerthat.dal.mobile import get_mobile_by_account, get_user_active_mobiles
from rogerthat.dal.profile import get_user_profile_key, get_user_profile, get_deactivated_user_profile, \
    get_service_profile, get_profile_key
from rogerthat.dal.registration import get_registration_by_mobile
from rogerthat.dal.service import get_service_identity
from rogerthat.models import MobileSettings, InstallationLog, Message, UserInteraction, ProfilePointer, ActivationLog, \
    App, AppSettings, ServiceIdentity
from rogerthat.models.properties.profiles import MobileDetails
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile
from rogerthat.rpc.rpc import logError
from rogerthat.rpc.service import logServiceError
from rogerthat.settings import get_server_settings
from rogerthat.to.messaging import UserMemberTO
from rogerthat.to.registration import AccountTO, MobileInfoTO
from rogerthat.to.service import UserDetailsTO
from rogerthat.to.system import SettingsTO, UpdateSettingsRequestTO
from rogerthat.translations import localize, DEFAULT_LANGUAGE
from rogerthat.utils import channel, azzert, now, try_or_defer, bizz_check
from rogerthat.utils.app import create_app_user, get_app_id_from_app_user, get_human_user_from_app_user
from rogerthat.utils.crypto import encrypt_for_jabber_cloud, decrypt_from_jabber_cloud
from rogerthat.utils.service import get_service_user_from_service_identity_user, \
    get_identity_from_service_identity_user, create_service_identity_user
from rogerthat.utils.transactions import run_in_xg_transaction


@returns(types.TupleType)
@arguments(human_user=users.User, name=unicode, app_id=unicode, use_xmpp_kick_channel=bool, GCM_registration_id=unicode,
           language=unicode, ysaaa=bool)
def register_mobile(human_user, name=None, app_id=App.APP_ID_ROGERTHAT, use_xmpp_kick_channel=True,
                    GCM_registration_id=None, language=None, ysaaa=False):
    # First unregister currently registered mobiles
    app_user = create_app_user(human_user, app_id)
    mobiles = get_user_active_mobiles(app_user)
    for m in mobiles:
        unregister_mobile(app_user, m)

    # Create account
    account = generate_account()

    # Save mobile in datastore
    mobile = Mobile(key_name=account.account)
    mobile.id = unicode(uuid.uuid1())
    mobile.description = "%s mobile" % app_user.email()

    mobile.user = app_user
    mobile.account = account.account
    mobile.accountPassword = account.password
    need_jabber_account = not APPSCALE and use_xmpp_kick_channel
    if need_jabber_account:
        mobile.status = Mobile.STATUS_NEW  # Account created status is set as soon as the ejabberd account is ready
    else:
        mobile.status = Mobile.STATUS_NEW | Mobile.STATUS_ACCOUNT_CREATED
    if GCM_registration_id:
        mobile.pushId = GCM_registration_id
    mobile.put()

    # AppScale deployments authenticate jabber users against rogerthat app directly
    if need_jabber_account:
        try_or_defer(create_jabber_account, account, mobile.key())

    age_and_gender_set = False

    # Create profile for user if needed
    deactivated_user_profile = get_deactivated_user_profile(app_user)
    if deactivated_user_profile:
        if deactivated_user_profile.birthdate is not None and deactivated_user_profile.gender is not None:
            age_and_gender_set = True
        reactivate_user_profile(deactivated_user_profile, app_user)
        ActivationLog(timestamp=now(), email=app_user.email(), mobile=mobile,
                      description="Reactivate user account by registering a mobile").put()
    else:
        user_profile = get_user_profile(app_user)
        if not user_profile:
            create_user_profile(app_user, name or human_user.email(), language, ysaaa)
        else:
            if user_profile.birthdate is not None and user_profile.gender is not None:
                age_and_gender_set = True
            if user_profile.isCreatedForService:
                user_profile.isCreatedForService = False
                user_profile.put()

    return account, mobile, age_and_gender_set


@returns()
@arguments(account=AccountTO, mobile_key=db.Key)
def create_jabber_account(account, mobile_key):
    settings = get_server_settings()
    jabberEndpoint = choice(settings.jabberEndPoints)
    payload = json.dumps(dict(username=account.user, server=account.server, password=account.password))
    challenge, data = encrypt_for_jabber_cloud(settings.jabberSecret.encode('utf8'), payload)
    response = urlfetch.fetch(url="http://%s/register" % jabberEndpoint, \
                              payload=data, method="POST",
                              allow_truncated=False, follow_redirects=False, validate_certificate=False, deadline=30)
    azzert(response.status_code == 200,
           "Failed to create jabber account %s.\n\nStatus code: %s" % (account.account, response.status_code))
    success, signalNum, out, err = json.loads(
        decrypt_from_jabber_cloud(settings.jabberSecret.encode('utf8'), challenge, response.content))
    logging.info("success: %s\nexit_code or signal: %s\noutput: %s\nerror: %s" % (success, signalNum, out, err))
    if not success and " already registered at node " in out:
        success = True
    azzert(success, "Failed to create jabber account %s.\n\nOutput: %s" % (account.account, out))
    if mobile_key:
        try_or_defer(_mark_mobile_as_registered, mobile_key)


def _mark_mobile_as_registered(mobile_key):
    def trans():
        mobile = db.get(mobile_key)
        mobile.status = mobile.status | Mobile.STATUS_ACCOUNT_CREATED
        mobile.put()

    db.run_in_transaction(trans)


def registration_account_creation_response(sender, stanza):
    register_elements = stanza.getElementsByTagNameNS("mobicage:jabber", "register")
    register_element = register_elements[0]
    registration_id = register_element.getAttribute('registrationid')
    user = register_element.getAttribute('user')
    if not registration_id.startswith(user):
        return
    result_elements = stanza.getElementsByTagNameNS("mobicage:jabber", "result")
    azzert(len(result_elements) == 1)
    result_element = result_elements[0]
    if result_element.getAttribute('success') == "True":
        mobile = get_mobile_by_account(registration_id)
        mobile.status = mobile.status | Mobile.STATUS_ACCOUNT_CREATED
        mobile.put()
    else:
        error_message = result_element.getAttribute('error')
        error_message = "Account creation in ejabberd for registration with id = '%s' failed with message: '%s'." % (
        registration_id, error_message)
        logging.error(error_message)
        server_settings = get_server_settings()
        xmpp.send_message(server_settings.xmppInfoMembers, error_message, message_type=xmpp.MESSAGE_TYPE_CHAT)


@returns(AccountTO)
@arguments(user=unicode)
def generate_account(user=None):
    settings = get_server_settings()

    result = AccountTO()
    result.user = user or unicode(uuid.uuid1())
    result.server = settings.jabberDomain
    result.password = unicode(uuid.uuid4()) + unicode(uuid.uuid4())
    result.account = u'%s@%s' % (result.user, result.server)
    return result


def send_welcome_message(user):
    def trans():
        ui = UserInteraction.get_by_key_name(user.email(), parent=parent_key(user)) or UserInteraction(
            key_name=user.email(), parent=parent_key(user))
        if ui.interactions & UserInteraction.INTERACTION_WELCOME != UserInteraction.INTERACTION_WELCOME:
            ui.interactions |= UserInteraction.INTERACTION_WELCOME
            db.put_async(ui)
            user_profile = get_user_profile(user)

            app, app_translations = get_app_and_translations_by_app_id(user_profile.app_id)
            if app.type in (App.APP_TYPE_ENTERPRISE, App.APP_TYPE_YSAAA, App.APP_TYPE_OSA_LOYALTY):
                return
            msg = app_translations.get_translation(user_profile.language, '_welcome_msg') if app_translations else None
            if not msg:
                msg = localize(user_profile.language, '_welcome_msg', app_name=app.name,
                               contact_email_address=app.get_contact_email_address())
            sendMessage(MC_DASHBOARD, [UserMemberTO(user, Message.ALERT_FLAG_VIBRATE)], Message.FLAG_ALLOW_DISMISS, 0,
                        None, msg, [], None, get_app_by_user(user).core_branding_hash, None, is_mfr=False)

    run_in_xg_transaction(trans)


@returns(Mobile)
@arguments(mobile_account=unicode, mobileInfo=MobileInfoTO, accounts=unicode, invitor_code=unicode,
           invitor_secret=unicode, ipaddress=unicode)
def finish_registration(mobile_account, mobileInfo, accounts, invitor_code, invitor_secret, ipaddress):
    from rogerthat.service.api import friends as service_api_friends
    m = get_mobile_by_account(mobile_account)
    mobile_key = m.key()
    ms_key = MobileSettings.get(m).key()
    profile_key = get_user_profile_key(m.user)

    def trans():
        mobile, ms, my_profile = db.get((mobile_key, ms_key, profile_key))

        mobile.status = mobile.status | Mobile.STATUS_REGISTERED
        mobile.type = mobileInfo.app_type
        mobile.simCountry = mobileInfo.sim_country if mobileInfo.sim_country != MISSING else None
        mobile.simCountryCode = mobileInfo.sim_country_code if mobileInfo.sim_country_code != MISSING else None
        mobile.simCarrierCode = mobileInfo.sim_carrier_code if mobileInfo.sim_carrier_code != MISSING else None
        mobile.simCarrierName = mobileInfo.sim_carrier_name if mobileInfo.sim_carrier_name != MISSING else None
        mobile.netCountry = mobileInfo.net_country if mobileInfo.net_country != MISSING else None
        mobile.netCountryCode = mobileInfo.net_country_code if mobileInfo.net_country_code != MISSING else None
        mobile.netCarrierCode = mobileInfo.net_carrier_code if mobileInfo.net_carrier_code != MISSING else None
        mobile.netCarrierName = mobileInfo.net_carrier_name if mobileInfo.net_carrier_name != MISSING else None
        mobile.hardwareModel = mobileInfo.device_model_name
        mobile.osVersion = mobileInfo.device_os_version if mobileInfo.device_os_version != MISSING else None
        mobile.localeLanguage = mobileInfo.locale_language if mobileInfo.locale_language and mobileInfo.locale_language != MISSING else DEFAULT_LANGUAGE
        mobile.localeCountry = mobileInfo.locale_country
        mobile.timezone = mobileInfo.timezone if mobileInfo.timezone != MISSING else None
        mobile.timezoneDeltaGMT = mobileInfo.timezone_delta_gmt if mobileInfo.timezone_delta_gmt != MISSING else None

        if mobileInfo.app_major_version != MISSING and mobileInfo.app_minor_version != MISSING:
            ms.majorVersion = mobileInfo.app_major_version
            ms.minorVersion = mobileInfo.app_minor_version

        # This is the official place where we set the profile language
        my_profile.language = mobile.localeLanguage
        my_profile.country = mobile.netCountry or mobile.simCountry or mobile.localeCountry
        my_profile.timezone = mobile.timezone
        my_profile.timezoneDeltaGMT = mobile.timezoneDeltaGMT

        my_profile.mobiles = MobileDetails()
        my_profile.mobiles.addNew(mobile.account, mobile.type, mobile.pushId, mobile.app_id)

        mobile.put()
        ms.put()
        my_profile.put()

        deferred.defer(_finishup_mobile_registration, mobile, accounts, invitor_code, invitor_secret, ipaddress,
                       ms_key, _transactional=True)

        return mobile, my_profile

    xg_on = db.create_transaction_options(xg=True)
    mobile, my_profile = db.run_in_transaction_options(xg_on, trans)
    channel.send_message(mobile.user, u'com.mobicage.registration.finished')
    typestr = "Unknown type"
    try:
        typestr = Mobile.typeAsString(mobile.type)
    except ValueError:
        pass

    server_settings = get_server_settings()
    registration = get_registration_by_mobile(mobile)
    if registration:
        InstallationLog(parent=registration.installation, timestamp=now(), registration=registration,
                        mobile=mobile, profile=my_profile, description="Registration successful.").put()

        if registration.installation and registration.installation.qr_url:
            service_user = get_service_user_from_service_identity_user(registration.installation.service_identity_user)
            service_identity = get_identity_from_service_identity_user(registration.installation.service_identity_user)
            svc_profile = get_service_profile(service_user)
            user_details = [UserDetailsTO.fromUserProfile(my_profile)]

            if registration.installation.service_callback_result == ACCEPT_AND_CONNECT_ID:
                service_identity_user = create_service_identity_user(service_user, service_identity)
                si = get_service_identity(service_identity_user)
                bizz_check(si, "ServiceIdentity %s not found" % service_identity_user)
                xmpp.send_message(server_settings.xmppInfoMembers,
                                  "User %s registered %s (%s) with account:\n%s\nFor service %s %s" % (
                                  mobile.user, mobile.hardwareModel, typestr, mobile.account, si.name,
                                  service_identity_user), message_type=xmpp.MESSAGE_TYPE_CHAT)
                app_id = get_app_id_from_app_user(mobile.user)
                if app_id not in si.appIds:
                    si.appIds.append(app_id)
                    put_and_invalidate_cache(si)
                try_or_defer(makeFriends, mobile.user, service_identity_user, original_invitee=None, servicetag=None,
                             origin=None, notify_invitee=False, notify_invitor=False, user_data=None)
            else:
                xmpp.send_message(server_settings.xmppInfoMembers, "User %s registered %s (%s) with account:\n%s" % (
                mobile.user, mobile.hardwareModel, typestr, mobile.account), message_type=xmpp.MESSAGE_TYPE_CHAT)

            service_api_friends.register_result(register_result_response_receiver, logServiceError, svc_profile,
                                                service_identity=service_identity,
                                                user_details=user_details,
                                                origin=REGISTRATION_ORIGIN_QR)
        else:
            xmpp.send_message(server_settings.xmppInfoMembers, "User %s registered %s (%s) with account:\n%s" % (
            mobile.user, mobile.hardwareModel, typestr, mobile.account), message_type=xmpp.MESSAGE_TYPE_CHAT)
            app = get_app_by_id(get_app_id_from_app_user(mobile.user))
            if app.admin_services:
                service_profiles = filter(None, db.get((get_profile_key(users.User(e)) for e in app.admin_services)))
                if service_profiles:
                    user_details = [UserDetailsTO.fromUserProfile(my_profile)]
                    for service_profile in service_profiles:
                        service_api_friends.register_result(register_result_response_receiver,
                                                            logServiceError,
                                                            service_profile,
                                                            service_identity=ServiceIdentity.DEFAULT,
                                                            user_details=user_details,
                                                            origin=REGISTRATION_ORIGIN_DEFAULT)
    else:
        xmpp.send_message(server_settings.xmppInfoMembers,
                          "User %s registered %s (%s) with account:\n%s\nBut registration model was not found!" % (
                          mobile.user, mobile.hardwareModel, typestr, mobile.account),
                          message_type=xmpp.MESSAGE_TYPE_CHAT)

    return mobile


def _finishup_mobile_registration_step2(mobile_key, invitor_code, invitor_secret, ipaddress, majorVersion,
                                        minorVersion):
    mobile = db.get(mobile_key)
    mobile_user = mobile.user
    server_settings = get_server_settings()

    def trans():  # Operates on 2 entity groups
        hookup_with_default_services.schedule(mobile_user, ipaddress)

        if invitor_code and invitor_secret:
            pp = ProfilePointer.get(invitor_code)
            if not pp:
                logging.error("User with userCode %s not found!" % invitor_code)
            else:
                deferred.defer(ack_invitation_by_invitation_secret, mobile_user, pp.user, invitor_secret,
                               _transactional=True, _countdown=10)

        elif invitor_code:
            for ysaaa_hash, static_email in chunks(server_settings.ysaaaMapping, 2):
                if invitor_code == ysaaa_hash:
                    service_user = users.User(static_email)
                    makeFriends(service_user, mobile_user, original_invitee=None, servicetag=None, origin=ORIGIN_YSAAA)
                    break
            else:
                azzert(False, u"ysaaa registration received but not found mapping")

        for _, static_email in chunks(server_settings.staticPinCodes, 2):
            if mobile_user.email() == static_email:
                break
        else:
            deferred.defer(send_messages_after_registration, mobile_key, _transactional=True)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


def _finishup_mobile_registration(mobile, accounts, invitor_code, invitor_secret, ipaddress, ms_key):
    mobile_user = mobile.user
    app_settings_key = AppSettings.create_key(get_app_id_from_app_user(mobile_user))
    server_settings = get_server_settings()

    def trans():  # Operates on 3 entity groups
        email = get_human_user_from_app_user(mobile_user).email()
        for _, static_email in chunks(server_settings.staticPinCodes, 2):
            if email == static_email:
                break
        else:
            deferred.defer(send_welcome_message, mobile_user, _transactional=True, _countdown=5)

        mobile_settings, app_settings = db.get([ms_key, app_settings_key])
        request = UpdateSettingsRequestTO()
        request.settings = SettingsTO.fromDBSettings(mobile_settings, app_settings)
        updateSettings(update_settings_response_handler, logError, mobile_user, request=request)

        deferred.defer(_finishup_mobile_registration_step2, mobile.key(), invitor_code, invitor_secret, ipaddress,
                       mobile_settings.majorVersion, mobile_settings.minorVersion, _transactional=True)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)
