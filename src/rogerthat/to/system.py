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

import time

from rogerthat.to.profile import UserProfileTO
from mcfw.properties import bool_property, long_property, long_list_property, unicode_property, \
    typed_property, unicode_list_property


class SettingsTO(object):
    recordPhoneCalls = bool_property('1')
    recordPhoneCallsDays = long_property('2')
    recordPhoneCallsTimeslot = long_list_property('3')
    recordGeoLocationWithPhoneCalls = bool_property('4')

    geoLocationTracking = bool_property('5')
    geoLocationTrackingDays = long_property('6')
    geoLocationTrackingTimeslot = long_list_property('7')
    geoLocationSamplingIntervalBattery = long_property('8')
    geoLocationSamplingIntervalCharging = long_property('9')

    useGPSBattery = bool_property('10')
    useGPSCharging = bool_property('11')
    xmppReconnectInterval = long_property('12')
    operatingVersion = long_property('13')

    version = long_property('14')

    # properties coming from AppSettings
    wifiOnlyDownloads = bool_property('15', default=False)
    backgroundFetchTimestamps = long_list_property('16', default=[])

    ATTRIBUTES = (u'geoLocationTracking', \
                  u'geoLocationTrackingDays', u'geoLocationTrackingTimeslot', \
                  u'geoLocationSamplingIntervalBattery', u'geoLocationSamplingIntervalCharging', \
                  u'useGPSBattery', u'useGPSCharging', \
                  u'recordPhoneCalls', u'recordPhoneCallsDays', u'recordPhoneCallsTimeslot', \
                  u'recordGeoLocationWithPhoneCalls', \
                  u'xmppReconnectInterval')

    @staticmethod
    def fromDBSettings(mobile_settings, app_settings):
        from rogerthat.models import MobileSettings
        s = SettingsTO()
        for att in SettingsTO.ATTRIBUTES:
            setattr(s, att, getattr(mobile_settings, att))
        if isinstance(mobile_settings, MobileSettings):
            mobile = mobile_settings.mobile
            if mobile.operatingVersion != None:
                s.operatingVersion = mobile.operatingVersion
            else:
                s.operatingVersion = 0
            s.version = mobile_settings.version
        else:
            s.operatingVersion = 0
            s.version = 1

        if app_settings:
            s.wifiOnlyDownloads = app_settings.wifi_only_downloads
            s.backgroundFetchTimestamps = app_settings.background_fetch_timestamps
        else:
            s.wifiOnlyDownloads = SettingsTO.wifiOnlyDownloads.default
            s.backgroundFetchTimestamps = SettingsTO.backgroundFetchTimestamps.default
        return s

    def apply(self, settings):  # @ReservedAssignment
        for att in SettingsTO.ATTRIBUTES:
            setattr(settings, att, getattr(self, att))
        settings.timestamp = int(time.time())

class MobileRecipientTO(object):
    id = long_property('1')  # @ReservedAssignment
    description = unicode_property('2')

    @staticmethod
    def fromDBMobile(mobile):
        mrt = MobileRecipientTO()
        mrt.id = mobile.id
        mrt.description = u"%s (%s)" % (mobile.description, mobile.user.email())
        return mrt

class MobileTO(object):
    id = unicode_property('1')  # @ReservedAssignment
    description = unicode_property('2')
    hardwareModel = unicode_property('3')

    @staticmethod
    def fromDBMobile(mobile):
        mt = MobileTO()
        mt.id = mobile.id
        mt.description = mobile.description
        mt.hardwareModel = mobile.hardwareModel
        return mt

class UserStatusTO(object):
    profile = typed_property('1', UserProfileTO, False)
    registered_mobile_count = long_property('2')
    has_avatar = bool_property('3')

class SaveSettingsRequest(object):
    callLogging = bool_property('1')
    tracking = bool_property('2')

class SaveSettingsResponse(object):
    settings = typed_property('1', SettingsTO, False)

class IdentityTO(object):
    email = unicode_property('1')
    name = unicode_property('2')
    avatarId = long_property('3')
    qualifiedIdentifier = unicode_property('4')
    birthdate = long_property('5', default=0)
    gender = long_property('6', default=0)
    hasBirthdate = bool_property('7', default=False)
    hasGender = bool_property('8', default=False)
    profileData = unicode_property('9', default=None, doc="a JSON string containing extra profile fields")

class LogErrorRequestTO(object):
    mobicageVersion = unicode_property('1')
    platform = long_property('2')
    platformVersion = unicode_property('3')
    errorMessage = unicode_property('4')
    description = unicode_property('5')
    timestamp = long_property('6')

class LogErrorResponseTO(object):
    pass

class UnregisterMobileRequestTO(object):
    pass

class UnregisterMobileResponseTO(object):
    pass

class HeartBeatRequestTO(object):
    majorVersion = long_property('1')
    minorVersion = long_property('2')
    product = unicode_property('3')
    flushBackLog = bool_property('4')
    timestamp = long_property('5')
    timezone = unicode_property('6')
    buildFingerPrint = unicode_property('7')
    SDKVersion = unicode_property('8')
    networkState = unicode_property('9')
    appType = long_property('10')
    simCountry = unicode_property('11')
    simCountryCode = unicode_property('12')
    simCarrierName = unicode_property('13')
    simCarrierCode = unicode_property('14')
    netCountry = unicode_property('15')
    netCountryCode = unicode_property('16')
    netCarrierName = unicode_property('17')
    netCarrierCode = unicode_property('18')
    localeLanguage = unicode_property('19')
    localeCountry = unicode_property('20')
    timezoneDeltaGMT = long_property('21')
    deviceModelName = unicode_property('22')


class HeartBeatResponseTO(object):
    systemTime = long_property('1')

class GetIdentityRequestTO(object):
    pass

class GetIdentityResponseTO(object):
    identity = typed_property('1', IdentityTO, False)
    shortUrl = unicode_property('2')

class ForwardLogsRequestTO(object):
    jid = unicode_property('1')

class ForwardLogsResponseTO(object):
    pass

class IdentityUpdateRequestTO(object):
    identity = typed_property('1', IdentityTO, False)

class IdentityUpdateResponseTO(object):
    pass

class EditProfileRequestTO(object):
    name = unicode_property('1')
    avatar = unicode_property('2')  # base 64
    access_token = unicode_property('3')
    birthdate = long_property('4', default=0)
    gender = long_property('5', default=0)
    has_birthdate = bool_property('6', default=False)
    has_gender = bool_property('7', default=False)
    extra_fields = unicode_property('8', default=None, doc="a JSON string containing extra profile fields")

class EditProfileResponseTO(object):
    pass

class UpdateSettingsRequestTO(object):
    settings = typed_property('1', SettingsTO, False)

class UpdateSettingsResponseTO(object):
    pass

class UpdateAvailableRequestTO(object):
    majorVersion = long_property('1')
    minorVersion = long_property('2')
    downloadUrl = unicode_property('3')
    releaseNotes = unicode_property('4')

class UpdateAvailableResponseTO(object):
    pass

class UpdateApplePushDeviceTokenRequestTO(object):
    token = unicode_property('1')

class UpdateApplePushDeviceTokenResponseTO(object):
    pass

class GetIdentityQRCodeRequestTO(object):
    email = unicode_property('1')
    size = unicode_property('2')

class GetIdentityQRCodeResponseTO(object):
    qrcode = unicode_property('1')
    shortUrl = unicode_property('2')

class SetMobilePhoneNumberRequestTO(object):
    phoneNumber = unicode_property('1')

class SetMobilePhoneNumberResponseTO(object):
    pass

class ServiceIdentityInfoTO(object):
    name = unicode_property('1')
    email = unicode_property('2')
    avatar = unicode_property('3')
    admin_emails = unicode_list_property('4')
    description = unicode_property('5')
    app_ids = unicode_list_property('6')

    @staticmethod
    def fromServiceIdentity(service_identity):
        from rogerthat.utils.service import remove_slash_default
        si = ServiceIdentityInfoTO()
        si.name = service_identity.name
        si.email = remove_slash_default(service_identity.user).email()
        si.avatar = service_identity.avatarUrl
        si.admin_emails = list() if service_identity.metaData is None else [e.strip() for e in service_identity.metaData.split(',') if e.strip()]
        si.description = service_identity.description
        si.app_ids = service_identity.appIds
        return si


class TranslationValueTO(object):
    language = unicode_property('1')
    value = unicode_property('2')


class TranslationTO(object):
    type = long_property('1')
    key = unicode_property('2')
    values = typed_property('3', TranslationValueTO, True)


class TranslationSetTO(object):
    email = unicode_property('1')
    export_id = long_property('2')
    translations = typed_property('3', TranslationTO, True)


class LanguagesTO(object):
    default_language = unicode_property('1')
    supported_languages = unicode_list_property('2')
