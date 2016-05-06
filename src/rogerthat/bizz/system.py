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
import hashlib
import json
import logging
import os
import re
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from random import choice
from types import NoneType

from google.appengine.api import xmpp, urlfetch
from google.appengine.api.images import Image
from google.appengine.ext import db, deferred

from mcfw.cache import cached
from mcfw.consts import MISSING
from mcfw.imaging import generate_qr_code
from mcfw.rpc import returns, arguments
from rogerthat.bizz.job.update_friends import update_friend_service_identity_connections
from rogerthat.bizz.messaging import sendMessage
from rogerthat.capi.system import unregisterMobile, updateAvailable, forwardLogs
from rogerthat.consts import DEBUG, MC_DASHBOARD
from rogerthat.dal import put_and_invalidate_cache, generator
from rogerthat.dal.app import get_app_by_user
from rogerthat.dal.broadcast import get_broadcast_settings_flow_cache_keys_of_user
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.messaging import get_messages_count
from rogerthat.dal.mobile import get_mobile_by_id, get_mobile_by_key, get_user_active_mobiles_count, \
    get_mobiles_by_ios_push_id, get_user_active_mobiles
from rogerthat.dal.profile import get_avatar_by_id, get_user_profile_key, get_user_profile, get_profile_info, \
    get_deactivated_user_profile, get_service_profile
from rogerthat.models import MobileSettings, ClientDistro, Message, UserProfile, Avatar, CurrentlyForwardingLogs, \
    Installation, InstallationLog
from rogerthat.models.properties.profiles import MobileDetails
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile, RpcCAPICall, MobicageError, ClientError, ServiceAPICallback, Session
from rogerthat.rpc.rpc import mapping, logError
from rogerthat.rpc.service import logServiceError
from rogerthat.settings import get_server_settings
from rogerthat.templates import render
from rogerthat.to.messaging import ButtonTO, UserMemberTO
from rogerthat.to.profile import UserProfileTO
from rogerthat.to.system import UserStatusTO, IdentityTO, UpdateSettingsResponseTO, UnregisterMobileResponseTO, \
    UpdateAvailableResponseTO, UnregisterMobileRequestTO, UpdateAvailableRequestTO, IdentityUpdateResponseTO, \
    LogErrorResponseTO, LogErrorRequestTO, ForwardLogsResponseTO, ForwardLogsRequestTO
from rogerthat.translations import DEFAULT_LANGUAGE
from rogerthat.utils import now, azzert, try_or_defer, send_mail_via_mime, file_get_contents
from rogerthat.utils.app import get_human_user_from_app_user, get_app_id_from_app_user
from rogerthat.utils.crypto import encrypt_for_jabber_cloud, decrypt_from_jabber_cloud
from rogerthat.utils.languages import get_iso_lang

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO  # @UnusedImport

NUNTIUZ_UPDATE_REQUEST = u"nur"
DOWNLOAD_INSTALL = u"Download & install"
DOWNLOAD_INSTALL_ID = u"di"
NO_THANKS = u"No thanks"
NO_THANKS_ID = u"nt"

BUTTONS = list()
button = ButtonTO()
button.id = DOWNLOAD_INSTALL_ID
button.caption = DOWNLOAD_INSTALL
button.action = None
button.ui_flags = 0
BUTTONS.append(button)
button = ButtonTO()
button.id = NO_THANKS_ID
button.caption = NO_THANKS
button.action = None
button.ui_flags = 0
BUTTONS.append(button)
del button

_BASE_DIR = os.path.dirname(__file__)
_QR_SAMPLE_OVERLAY_PATH = os.path.join(_BASE_DIR, 'qr-sample.png')
QR_SAMPLE_OVERLAY = file_get_contents(_QR_SAMPLE_OVERLAY_PATH)
_QR_CODE_OVERLAY_PATH = os.path.join(_BASE_DIR, 'qr-brand.png')
DEFAULT_QR_CODE_OVERLAY = file_get_contents(_QR_CODE_OVERLAY_PATH)
_QR_CODE_HAND_ONLY_OVERLAY_PATH = os.path.join(_BASE_DIR, 'qr-hand-only.png')
HAND_ONLY_QR_CODE_OVERLAY = file_get_contents(_QR_CODE_HAND_ONLY_OVERLAY_PATH)

DEFAULT_QR_CODE_COLOR = [0x6a, 0xb8, 0x00]

ERROR_PATTERN_TXN_TOOK_TOO_LONG = re.compile('Transaction with name "(.*)" took (\d+) milliseconds!')


@returns(NoneType)
@arguments(user=users.User, mobile=Mobile)
def unregister_mobile(user, mobile):
    azzert(mobile.user == user)
    mark_mobile_for_delete(user, mobile.key())
    def trans():
        ctxs = unregisterMobile(unregister_mobile_success_callback, logError, user, request=UnregisterMobileRequestTO(),
                                   MOBILE_ACCOUNT=mobile, DO_NOT_SAVE_RPCCALL_OBJECTS=True)  # Only unregister this mobile :)
        for ctx in ctxs:
            ctx.mobile_key = mobile.key()
            ctx.put()
    db.run_in_transaction(trans)

@mapping('com.mobicage.capi.system.unregisterMobileSuccessCallBack')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=UnregisterMobileResponseTO)
def unregister_mobile_success_callback(context, result):
    mobile_key = context.mobile_key
    mobile = get_mobile_by_key(mobile_key)
    current_user = users.get_current_user()
    azzert(mobile.user == current_user)
    azzert(mobile == users.get_current_mobile())
    mobile.status = mobile.status | Mobile.STATUS_UNREGISTERED
    mobile.put()


@returns(NoneType)
@arguments(account=unicode, mobile_key=db.Key)
def delete_xmpp_account(account, mobile_key):
    settings = get_server_settings()
    jabberEndpoint = choice(settings.jabberEndPoints)
    account_parts = account.split("@")
    azzert(len(account_parts) == 2)
    user = account_parts[0]
    server = account_parts[1]
    payload = json.dumps(dict(username=user, server=server))
    challenge, data = encrypt_for_jabber_cloud(settings.jabberSecret.encode('utf8'), payload)
    jabberUrl = "http://%s/unregister" % jabberEndpoint
    logging.info("Calling url %s to unregister %s" % (jabberUrl, account))
    response = urlfetch.fetch(url=jabberUrl , \
                             payload=data, method="POST",
                             allow_truncated=False, follow_redirects=False, validate_certificate=False, deadline=30)
    azzert(response.status_code == 200)
    success, signalNum, out, err = json.loads(decrypt_from_jabber_cloud(settings.jabberSecret.encode('utf8'), challenge, response.content))
    logging.info("success: %s\nexit_code or signal: %s\noutput: %s\nerror: %s" % (success, signalNum, out, err))
    azzert(success)
    if mobile_key:
        try_or_defer(_mark_mobile_as_uregistered, mobile_key)

def _mark_mobile_as_uregistered(mobile_key):
    def trans():
        mobile = db.get(mobile_key)
        mobile.status = mobile.status | Mobile.STATUS_ACCOUNT_DELETED
        mobile.put()
        return mobile
    mobile = db.run_in_transaction(trans)
    server_settings = get_server_settings()
    xmpp.send_message(server_settings.xmppInfoMembers, "User %s has unregistered his mobile with account:\n%s" % (mobile.user, mobile.account), message_type=xmpp.MESSAGE_TYPE_CHAT)

def account_removal_response(sender, stanza):
    logging.info("Incoming 'unregister' message from sender %s:\n%s" % (sender, stanza))
    unregister_elements = stanza.getElementsByTagNameNS(u"mobicage:jabber", u"unregister")
    unregister_element = unregister_elements[0]
    mobile_id = unregister_element.getAttribute(u'mobileid')
    mobile = get_mobile_by_id(mobile_id)
    mobile.status = mobile.status | Mobile.STATUS_ACCOUNT_DELETED
    mobile.put()

@returns(NoneType)
@arguments(current_user=users.User, current_mobile=Mobile, majorVersion=int, minorVersion=int, flushBackLog=bool, appType=int, product=unicode, timestamp=long, \
           timezone=unicode, timezoneDeltaGMT=int, osVersion=unicode, deviceModelName=unicode, simCountry=unicode, \
           simCountryCode=unicode, simCarrierName=unicode, simCarrierCode=unicode, netCountry=unicode, \
           netCountryCode=unicode, netCarrierName=unicode, netCarrierCode=unicode, localeLanguage=unicode, \
           localeCountry=unicode, now_time=int)
def _heart_beat(current_user, current_mobile, majorVersion, minorVersion, flushBackLog, appType, product, timestamp, timezone, timezoneDeltaGMT, \
               osVersion, deviceModelName, simCountry, simCountryCode, simCarrierName, simCarrierCode, netCountry, \
               netCountryCode, netCarrierName, netCarrierCode, localeLanguage, localeCountry, now_time):
    m = current_mobile
    mobile_key = m.key()
    ms_key = MobileSettings.get(m).key()
    def trans():
        mobile, ms, my_profile = db.get((mobile_key, ms_key, get_user_profile_key(current_user)))
        ms.majorVersion = majorVersion
        ms.minorVersion = minorVersion
        ms.lastHeartBeat = now_time

        if appType != MISSING:
            mobile.type = my_profile.mobiles[mobile.account].type_ = appType
        if simCountry != MISSING:
            mobile.simCountry = simCountry
        if simCountryCode != MISSING:
            mobile.simCountryCode = simCountryCode
        if simCarrierCode != MISSING:
            mobile.simCarrierCode = simCarrierCode
        if simCarrierName != MISSING:
            mobile.simCarrierName = simCarrierName
        if netCountry != MISSING:
            mobile.netCountry = netCountry
        if netCountryCode != MISSING:
            mobile.netCountryCode = netCountryCode
        if netCarrierCode != MISSING:
            mobile.netCarrierCode = netCarrierCode
        if netCarrierName != MISSING:
            mobile.netCarrierName = netCarrierName
        if deviceModelName != MISSING:
            mobile.hardwareModel = deviceModelName
        if osVersion != MISSING:
            mobile.osVersion = osVersion
        if localeCountry != MISSING:
            mobile.localeCountry = localeCountry
        if localeLanguage != MISSING:
            mobile.localeLanguage = localeLanguage
        if timezone != MISSING:
            mobile.timezone = timezone
        if timezoneDeltaGMT != MISSING:
            mobile.timezoneDeltaGMT = timezoneDeltaGMT

        language = mobile.localeLanguage
        if language:
            if '-' in language:
                language = get_iso_lang(language.lower())
            elif mobile.localeCountry:
                language = '%s_%s' % (mobile.localeLanguage, mobile.localeCountry)

            if my_profile.language != language:
                my_profile.language = language
                # trigger friend.update service api call
                deferred.defer(update_friend_service_identity_connections, my_profile.key(), _transactional=True)
                db.delete_async(get_broadcast_settings_flow_cache_keys_of_user(my_profile.user))
        my_profile.country = mobile.netCountry or mobile.simCountry or mobile.localeCountry
        my_profile.timezone = mobile.timezone
        my_profile.timezoneDeltaGMT = mobile.timezoneDeltaGMT

        put_and_invalidate_cache(ms, mobile, my_profile)
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


@returns(int)
@arguments(current_user=users.User, current_mobile=Mobile, majorVersion=int, minorVersion=int, flushBackLog=bool, appType=int, product=unicode, timestamp=long, \
           timezone=unicode, timezoneDeltaGMT=int, osVersion=unicode, deviceModelName=unicode, simCountry=unicode, \
           simCountryCode=unicode, simCarrierName=unicode, simCarrierCode=unicode, netCountry=unicode, \
           netCountryCode=unicode, netCarrierName=unicode, netCarrierCode=unicode, localeLanguage=unicode, \
           localeCountry=unicode)
def heart_beat(current_user, current_mobile, majorVersion, minorVersion, flushBackLog, appType, product, timestamp, timezone, timezoneDeltaGMT, \
               osVersion, deviceModelName, simCountry, simCountryCode, simCarrierName, simCarrierCode, netCountry, \
               netCountryCode, netCarrierName, netCarrierCode, localeLanguage, localeCountry):
    now_time = int(time.time())

    try_or_defer(_heart_beat, current_user, current_mobile, majorVersion, minorVersion, flushBackLog, appType, product, timestamp, timezone, timezoneDeltaGMT, \
               osVersion, deviceModelName, simCountry, simCountryCode, simCarrierName, simCarrierCode, netCountry, \
               netCountryCode, netCarrierName, netCarrierCode, localeLanguage, localeCountry, now_time, accept_missing=True)
    return now_time

@returns(NoneType)
@arguments(distro=ClientDistro, userz=[users.User])
def publish_client_app(distro, userz):
    major, minor = (int(p) for p in distro.version.split('.'))

    def needsUpdate(m):
        settings = MobileSettings.get(m)
        return settings.majorVersion < major \
            or settings.majorVersion == major and settings.minorVersion < minor

    notes = distro.releaseNotes
    msg = u"""Version %(major)s.%(minor)s of Rogerthat has been released.

    Release notes:
    %(notes)s""" % dict(major=major, minor=minor, notes=notes)
    for user in userz:
        message = sendMessage(MC_DASHBOARD, [UserMemberTO(user)], Message.FLAG_AUTO_LOCK, 0, None, msg, BUTTONS, None,
                              get_app_by_user(user).core_branding_hash, NUNTIUZ_UPDATE_REQUEST, is_mfr=False)
        message.major = major
        message.minor = minor
        message.distro = distro.key()
        message.invitee = user
        message.put()

@returns(NoneType)
@arguments(message=Message)
def install_client_app(message):
    azzert(message.tag == NUNTIUZ_UPDATE_REQUEST)
    if message.memberStatusses[message.members.index(message.invitee)].button_index != message.buttons[DOWNLOAD_INSTALL_ID].index:
        return
    distro = ClientDistro.get(message.distro)
    request = UpdateAvailableRequestTO()
    request.majorVersion = message.major
    request.minorVersion = message.minor
    request.downloadUrl = u"https://rogerth.at/unauthenticated/mobi/distros/get/" + unicode(distro.key().id())
    request.releaseNotes = distro.releaseNotes
    updateAvailable(update_available_response_handler, logError, message.invitee, \
                    request=request)

@returns(UserStatusTO)
@arguments(user=users.User)
def get_user_status(user):
    logging.info("Getting user status for %s" % user)
    us = UserStatusTO()
    user_profile = get_user_profile(user)
    us.profile = UserProfileTO.fromUserProfile(user_profile) if user_profile else None
    us.registered_mobile_count = get_user_active_mobiles_count(user)
    if user_profile:
        avatar = get_avatar_by_id(user_profile.avatarId)
        us.has_avatar = bool(avatar and avatar.picture)
    else:
        us.has_avatar = False
    return us

@returns(IdentityTO)
@arguments(app_user=users.User, user_profile=UserProfile)
def get_identity(app_user, user_profile=None):
    idTO = IdentityTO()
    profile = user_profile or get_user_profile(app_user)
    idTO.email = get_human_user_from_app_user(app_user).email()
    idTO.name = profile.name
    idTO.avatarId = profile.avatarId
    idTO.qualifiedIdentifier = profile.qualifiedIdentifier
    idTO.birthdate = profile.birthdate or 0
    idTO.gender = profile.gender or 0
    idTO.hasBirthdate = profile.birthdate is not None
    idTO.hasGender = profile.gender is not None
    idTO.profileData = profile.profileData
    return idTO

@returns(NoneType)
@arguments(user=users.User, type_=unicode, subject=unicode, message=unicode)
def feedback(user, type_, subject, message):
    email_subject = "Feedback - %s - %s" % (type_, subject)
    friend_count = len(get_friends_map(user).friends)
    message_count = get_messages_count(user)
    mobiles = get_user_active_mobiles(user)
    email = user.email()
    timestamp = now()
    profile_info = get_profile_info(user)

    d = dict(type_=type_, subject=subject, message=message, email=email,
             profile_info=profile_info, friend_count=friend_count, message_count=message_count,
             mobiles=mobiles, timestamp=timestamp)

    body = render("feedback", [DEFAULT_LANGUAGE], d)
    server_settings = get_server_settings()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = email_subject
    msg['From'] = server_settings.senderEmail
    msg['To'] = server_settings.supportEmail
    msg.attach(MIMEText(body.encode('utf-8'), 'plain', 'utf-8'))
    send_mail_via_mime(server_settings.senderEmail, server_settings.supportEmail, msg)

@mapping('com.mobicage.capi.system.updateSettingsResponseHandler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=UpdateSettingsResponseTO)
def update_settings_response_handler(context, result):
    pass

@mapping('com.mobicage.capi.system.updateAvailableResponseHandler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=UpdateAvailableResponseTO)
def update_available_response_handler(context, result):
    pass

@mapping('com.mobicage.capi.system.identityUpdateResponseHandler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=IdentityUpdateResponseTO)
def identity_update_response_handler(context, result):
    pass

@mapping('com.mobicage.capi.system.forwardLogsResponseHandler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=ForwardLogsResponseTO)
def forward_logs_response_handler(context, result):
    pass

def _mark_mobile_for_delete(mobile):
    logging.info("Marking mobile (%s) for delete", mobile.key())
    mobile.pushId = None
    mobile.status = mobile.status | Mobile.STATUS_DELETE_REQUESTED
    db.put_async(mobile)

@returns(NoneType)
@arguments(user=users.User, mobile_key=db.Key)
def mark_mobile_for_delete(user, mobile_key):
    def trans():
        mobile, profile = db.get((mobile_key, get_user_profile_key(user)))
        _mark_mobile_for_delete(mobile)
        if not profile:
            logging.debug("No UserProfile found for user %s. Trying to get archived UserProfile...", user)
            profile = get_deactivated_user_profile(user)
        if profile:
            if not profile.mobiles:
                profile.mobiles = MobileDetails()
            profile.mobiles.remove(mobile.account)
            profile.put()
        else:
            logging.warn("No profile found for user %s", user)
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


@returns(NoneType)
@arguments(mobile=Mobile, token=unicode)
def update_apple_push_device_token(mobile, token):
    if mobile.type in Mobile.IOS_TYPES:
        token.decode("hex")  # just check whether is nicely hex encoded

    if mobile.pushId == token:
        pass  # prevent unnecessary datastore accesses

    old_mobiles = list(get_mobiles_by_ios_push_id(token))
    user = mobile.user
    def trans(mobile_key, user):
        mobile, profile = db.get((mobile_key, get_user_profile_key(user)))
        mobile.pushId = token
        db.put_async(mobile)
        if not profile.mobiles:
            profile.mobiles = MobileDetails()
        if mobile.account in profile.mobiles:
            profile.mobiles[mobile.account].pushId = token
        else:
            profile.mobiles.addNew(mobile.account, mobile.type, token, get_app_id_from_app_user(user))
        for old_mobile in old_mobiles:
            if mobile_key != old_mobile.key():
                if mobile.user == old_mobile.user:
                    _mark_mobile_for_delete(old_mobile)
                    profile.mobiles.remove(old_mobile.account)
                else:
                    deferred.defer(mark_mobile_for_delete, old_mobile.user, old_mobile.key(), _transactional=True)
        profile.put()
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans, mobile.key(), user)

@returns(NoneType)
@arguments(token=unicode)
def obsolete_apple_push_device_token(token):
    logging.info("Obsoleting apple push device " + token)
    for mobile in get_mobiles_by_ios_push_id(token):
        logging.info("Removing pushId from mobile %s of %s.", mobile.account, mobile.user)
        mobile.pushId = None
        mobile.put()


@cached(2, 0, datastore="qrcode_image")
@returns(str)
@arguments(content=unicode, overlay=str, color=[int], sample=bool)
def qrcode(content, overlay, color, sample):
    return generate_qr_code(content, overlay, color, QR_SAMPLE_OVERLAY if sample else None)


@returns(NoneType)
@arguments(mobile=Mobile, phone_number=unicode)
def set_validated_phonenumber(mobile, phone_number):
    if mobile.type == Mobile.TYPE_ANDROID_HTTP:
        mobile.phoneNumber = phone_number
        mobile.phoneNumberVerified = True
        mobile.put()
    elif mobile.type in Mobile.IOS_TYPES:
        if mobile.phoneNumberVerificationCode == phone_number:
            mobile.phoneNumberVerified = True
            mobile.put()
        else:
            raise ValueError("Verification code does not match")
    else:
        raise ValueError("Unknown platform")


@returns(bool)
@arguments(request=LogErrorRequestTO, user=users.User, install_id=unicode)
def shouldLogClientError(request, user, install_id):
    # Return boolean - should we put this error in mobile error logs
    if request.description:
        if 'Warning: DNS SRV did time out. Falling back to rogerth.at:5222' in request.description \
                or 'Using fallback value for DNS SRV (but network is up)' in request.description:
            return False
        matches = ERROR_PATTERN_TXN_TOOK_TOO_LONG.findall(request.description)
        if matches and int(matches[0][1]) < 5000:
            return False

    if request.errorMessage:
        if "ServerRespondedWrongHTTPCodeException" in request.errorMessage:
            return False
        if "java.lang.NullPointerException" in request.errorMessage \
                and "android.os.Parcel.readException(Parcel.java" in request.errorMessage:
            return False
        if "java.lang.SecurityException: !@Too many alarms (500) registered from pid " in request.errorMessage:
            return False

    return True

@returns(LogErrorResponseTO)
@arguments(request=LogErrorRequestTO, user=users.User, install_id=unicode, session=Session, shop=bool)
def logErrorBizz(request, user=None, install_id=None, session=None, shop=False):

    if not shouldLogClientError(request, user, install_id):
        logging.warn('Ignoring logError request for %s:\n%s\n\n%s',
                     user or install_id, request.description, request.errorMessage)
        return

    def do_in_trans():
        m = hashlib.sha256()
        m.update(request.mobicageVersion.encode('utf-8') if request.mobicageVersion else "")
        m.update("-")
        m.update(str(request.platform))
        m.update("-")
        m.update(request.platformVersion.encode('utf-8') if request.platformVersion else "")
        m.update("-")
        m.update(request.errorMessage.encode('utf-8') if request.errorMessage else "")
        m.update("-")
        m.update(request.description.encode('utf-8') if request.description else "")
        key = m.hexdigest()
        me = MobicageError.get_by_key_name(key)
        if not me:
            me = MobicageError(key_name=key)
            me.mobicageVersion = request.mobicageVersion
            me.platform = request.platform
            me.platformVersion = request.platformVersion
            me.errorMessage = request.errorMessage
            me.description = request.description
            me.occurenceCount = 1
        else:
            me.occurenceCount += 1
        me.put()
        ce = ClientError(parent=me)
        ce.user = user

        if session and session.user != user:
            if session.shop:
                ce.userStr = u"%s (%s via shop)" % (user, session.user)
            else:
                ce.userStr = u"%s (%s)" % (user, session.user)
        elif user:
            if shop:
                ce.userStr = u"%s (via shop)" % user
            else:
                ce.userStr = u"%s" % user
        else:
            ce.userStr = None

        ce.installId = install_id
        ce.timestamp = request.timestamp / 1000 if request.timestamp > now() * 10 else request.timestamp
        ce.put()

        if install_id:
            if DEBUG:
                description_url = "http://localhost:8000/datastore/edit/%s" % ce.parent_key()
            else:
                description_url = "https://appengine.google.com/datastore/edit?app_id=s~mobicagecloudhr&namespace=&key=%s" % ce.parent_key()

            installation = Installation.get_by_key_name(install_id) if install_id else None
            InstallationLog(parent=installation, timestamp=now(), description="ClientError occurred", description_url=description_url).put()

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, do_in_trans)

@returns(NoneType)
@arguments(app_user=users.User, name=unicode, image=unicode, access_token=unicode, birthdate=long, gender=long, \
           has_birthdate=bool, has_gender=bool, current_mobile=Mobile)
def _edit_profile(app_user, name, image, access_token, birthdate, gender, has_birthdate, has_gender, current_mobile):
    from rogerthat.bizz.profile import update_avatar_profile, couple_facebook_id_with_profile, schedule_re_index


    def trans(image):
        user_profile = get_user_profile(app_user)
        if name is not MISSING:
            user_profile.name = name

        # has_birthdate and has_gender are used starting from 1.0.999.A and 1.0.137.i
        if has_birthdate is not MISSING and has_gender is not MISSING:
            if has_birthdate is True:
                user_profile.birthdate = birthdate
            if has_gender is True:
                user_profile.gender = gender
        else:
            # birthdate and gender are only used without has_gender and has_birthdate in 1.0.998.A
            if birthdate is not MISSING and gender is not MISSING:
                if birthdate == 0 and gender == 0:
                    pass  # user pressed save in 1.0.998.A without setting gender and birthdate
                else:
                    user_profile.birthdate = birthdate
                    if gender != 0:
                        user_profile.gender = gender

        if image:
            avatar = get_avatar_by_id(user_profile.avatarId)
            if not avatar:
                avatar = Avatar(user=user_profile.user)

            image = base64.b64decode(str(image))
            img = Image(image)
            if img.width > 150 or img.height > 150:
                logging.info('Resizing avatar from %sx%s to 150x150', img.width, img.height)
                img.resize(150, 150)
                image = img.execute_transforms(img.format, 100)

            update_avatar_profile(user_profile, avatar, image)
        user_profile.version += 1
        user_profile.put()

        from rogerthat.bizz.profile import update_mobiles, update_friends
        update_mobiles(user_profile.user, user_profile, current_mobile)  # update myIdentity
        update_friends(user_profile)  # notify my friends
        schedule_re_index(app_user)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans, image)

    if access_token:
        couple_facebook_id_with_profile(app_user, access_token)

@returns(NoneType)
@arguments(app_user=users.User, name=unicode, image=unicode, access_token=unicode, birthdate=long, gender=long,
           has_birthdate=bool, has_gender=bool, current_mobile=Mobile)
def edit_profile(app_user, name, image, access_token=None, birthdate=MISSING, gender=MISSING,
                 has_birthdate=MISSING, has_gender=MISSING, current_mobile=None):
    try_or_defer(_edit_profile, app_user, name, image, access_token, birthdate, gender, has_birthdate, has_gender,
                 current_mobile, accept_missing=True)


@returns(CurrentlyForwardingLogs)
@arguments(app_user=users.User, xmpp_target_jid=unicode, mobile=Mobile, xmpp_target_password=unicode, type_=int)
def start_log_forwarding(app_user, xmpp_target_jid, mobile=None, xmpp_target_password=None,
                         type_=CurrentlyForwardingLogs.TYPE_XMPP):
    def trans():
        request = ForwardLogsRequestTO()
        request.jid = unicode(xmpp_target_jid) if xmpp_target_jid else None
        forwardLogs(forward_logs_response_handler, logError, app_user, request=request, MOBILE_ACCOUNT=mobile)
        if request.jid:
            clf = CurrentlyForwardingLogs(key=CurrentlyForwardingLogs.create_key(app_user),
                                          xmpp_target=request.jid,
                                          xmpp_target_password=xmpp_target_password,
                                          type=type_)
            clf.put()
            return clf
        else:
            db.delete(CurrentlyForwardingLogs.create_key(app_user))
            return None

    if db.is_in_transaction:
        return trans()
    else:
        xg_on = db.create_transaction_options(xg=True)
        return db.run_in_transaction_options(xg_on, trans)


@returns(NoneType)
@arguments(app_user=users.User)
def stop_log_forwarding(app_user):
    start_log_forwarding(app_user, None)


@returns([CurrentlyForwardingLogs])
@arguments()
def get_users_currently_forwarding_logs():
    def trans():
        return generator(CurrentlyForwardingLogs.all().ancestor(CurrentlyForwardingLogs.create_parent_key()))

    return db.run_in_transaction(trans)

@returns()
@arguments(service_user=users.User, email=unicode, success=bool)
def delete_service_finished(service_user, email, success):
    from rogerthat.service.api.system import service_deleted
    service_deleted(system_service_deleted_response_handler, logServiceError, get_service_profile(service_user), \
                    email=email, success=success)

@mapping('system.service_deleted.response_handler')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=NoneType)
def system_service_deleted_response_handler(context, result):
    pass
