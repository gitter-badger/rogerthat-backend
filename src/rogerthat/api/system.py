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
import logging
import time

from rogerthat.bizz.friends import get_user_invite_url, get_user_and_qr_code_url
from rogerthat.bizz.service import get_default_qr_template_by_app_id
from rogerthat.dal.app import get_app_settings
from rogerthat.models import MobileSettings, JSEmbedding
from rogerthat.rpc import users
from rogerthat.rpc.rpc import expose
from rogerthat.rpc.users import get_current_user
from rogerthat.to.js_embedding import GetJSEmbeddingResponseTO, GetJSEmbeddingRequestTO
from rogerthat.to.system import SettingsTO, SaveSettingsRequest, SaveSettingsResponse, LogErrorResponseTO, \
    LogErrorRequestTO, UnregisterMobileRequestTO, UnregisterMobileResponseTO, HeartBeatRequestTO, HeartBeatResponseTO, \
    GetIdentityRequestTO, GetIdentityResponseTO, UpdateApplePushDeviceTokenRequestTO, UpdateApplePushDeviceTokenResponseTO, \
    GetIdentityQRCodeRequestTO, GetIdentityQRCodeResponseTO, SetMobilePhoneNumberRequestTO, SetMobilePhoneNumberResponseTO, \
    EditProfileRequestTO, EditProfileResponseTO
from rogerthat.utils import channel, slog, try_or_defer
from rogerthat.utils.app import create_app_user, get_app_id_from_app_user
from mcfw.rpc import returns, arguments


@expose(('api',))
@returns(LogErrorResponseTO)
@arguments(request=LogErrorRequestTO)
def logError(request):
    from rogerthat.bizz.system import logErrorBizz
    return logErrorBizz(request, get_current_user())

@expose(('api',))
@returns(SaveSettingsResponse)
@arguments(request=SaveSettingsRequest)
def saveSettings(request):
    mobile = users.get_current_mobile()
    db_settings = MobileSettings.get(mobile)
    db_settings.recordPhoneCalls = request.callLogging
    db_settings.geoLocationTracking = request.tracking
    db_settings.timestamp = int(time.time())
    db_settings.version += 1
    db_settings.put()
    response = SaveSettingsResponse()
    response.settings = SettingsTO.fromDBSettings(db_settings, get_app_settings(users.get_current_app_id()))
    channel.send_message(
        users.get_current_user(),
        u'rogerthat.settings.update',
        mobile_id=mobile.id)

    return response

@expose(('api',))
@returns(UnregisterMobileResponseTO)
@arguments(request=UnregisterMobileRequestTO)
def unregisterMobile(request):
    from rogerthat.bizz.system import unregister_mobile
    unregister_mobile(users.get_current_user(), users.get_current_mobile())

@expose(('api',))
@returns(HeartBeatResponseTO)
@arguments(request=HeartBeatRequestTO)
def heartBeat(request):
    from rogerthat.bizz.system import heart_beat
    response = HeartBeatResponseTO()
    app_user = users.get_current_user()
    current_mobile = users.get_current_mobile()
    response.systemTime = heart_beat(app_user, current_mobile, majorVersion=request.majorVersion, minorVersion=request.minorVersion, \
                                     flushBackLog=request.flushBackLog, appType=request.appType, \
                                     product=request.product, timestamp=request.timestamp, timezone=request.timezone, \
                                     timezoneDeltaGMT=request.timezoneDeltaGMT, osVersion=request.SDKVersion, \
                                     deviceModelName=request.deviceModelName, simCountry=request.simCountry, \
                                     simCountryCode=request.simCountryCode, simCarrierName=request.simCarrierName, \
                                     simCarrierCode=request.simCarrierCode, netCountry=request.netCountry, \
                                     netCountryCode=request.netCountryCode, netCarrierName=request.netCarrierName, \
                                     netCarrierCode=request.netCarrierCode, localeLanguage=request.localeLanguage, \
                                     localeCountry=request.localeCountry, accept_missing=True)
    slog('T', get_current_user().email(), "com.mobicage.api.system.heartBeat", timestamp=request.timestamp,
         major_version=request.majorVersion, minor_version=request.minorVersion, product=request.product,
         sdk_version=request.SDKVersion, networkState=request.networkState)
    return response

@expose(('api',))
@returns(GetIdentityResponseTO)
@arguments(request=GetIdentityRequestTO)
def getIdentity(request):
    from rogerthat.bizz.system import get_identity
    from rogerthat.bizz.friends import userCode as userCodeBizz
    user = users.get_current_user()
    response = GetIdentityResponseTO()
    response.shortUrl = unicode(get_user_invite_url(userCodeBizz(user)))
    response.identity = get_identity(user)
    return response

@expose(('api',))
@returns(UpdateApplePushDeviceTokenResponseTO)
@arguments(request=UpdateApplePushDeviceTokenRequestTO)
def updateApplePushDeviceToken(request):
    from rogerthat.bizz.system import update_apple_push_device_token
    try_or_defer(update_apple_push_device_token, users.get_current_mobile(), request.token)


@expose(('api',))
@returns(GetIdentityQRCodeResponseTO)
@arguments(request=GetIdentityQRCodeRequestTO)
def getIdentityQRCode(request):
    # Only for human users
    from rogerthat.bizz.friends import userCode as userCodeBizz
    from rogerthat.bizz.system import qrcode

    app_user = users.get_current_user()
    app_id = get_app_id_from_app_user(app_user)
    code = userCodeBizz(create_app_user(users.User(request.email), app_id))
    response = GetIdentityQRCodeResponseTO()
    response.shortUrl = unicode(get_user_invite_url(code))
    qrtemplate, color = get_default_qr_template_by_app_id(app_id)
    qr_code_url_and_user_tuple = get_user_and_qr_code_url(code)
    if not qr_code_url_and_user_tuple:
        logging.warn("getIdentityQRCode ProfilePointer was None\n- request.email: %s\n- request.size: %s", request.email, request.size)
        return None
    qr_code_url, _ = qr_code_url_and_user_tuple
    response.qrcode = unicode(base64.b64encode(qrcode(qr_code_url, qrtemplate.blob, color, False)))
    return response


@expose(('api',))
@returns(SetMobilePhoneNumberResponseTO)
@arguments(request=SetMobilePhoneNumberRequestTO)
def setMobilePhoneNumber(request):
    from rogerthat.bizz.system import set_validated_phonenumber
    set_validated_phonenumber(users.get_current_mobile(), request.phoneNumber)

@expose(('api',))
@returns(EditProfileResponseTO)
@arguments(request=EditProfileRequestTO)
def editProfile(request):
    from rogerthat.bizz.system import edit_profile
    edit_profile(users.get_current_user(), request.name, request.avatar, request.access_token, request.birthdate,
                 request.gender, request.has_birthdate, request.has_gender, users.get_current_mobile(),
                 accept_missing=True)

@expose(('api',))
@returns(GetJSEmbeddingResponseTO)
@arguments(request=GetJSEmbeddingRequestTO)
def getJsEmbedding(request):
    return GetJSEmbeddingResponseTO.fromDBJSEmbedding(JSEmbedding.all())
