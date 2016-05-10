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
from mcfw.properties import long_property, unicode_property


class DeprecatedMobileInfoTO(object):
    type = long_property('1')
    hardwareModel = unicode_property('3')
    phoneNumber = unicode_property('4')
    countryCode = unicode_property('5')
    imei = unicode_property('6')
    imsi = unicode_property('7')
    language = unicode_property('8')

class MobileInfoTO(object):
    version = long_property('18')
    app_type = long_property('1')
    app_major_version = long_property('2')
    app_minor_version = long_property('3')
    device_model_name = unicode_property('4')
    device_os_version = unicode_property('5')
    sim_country = unicode_property('6')
    sim_country_code = unicode_property('7')
    sim_carrier_code = unicode_property('8')
    sim_carrier_name = unicode_property('9')
    net_country = unicode_property('10')
    net_country_code = unicode_property('11')
    net_carrier_code = unicode_property('12')
    net_carrier_name = unicode_property('13')
    locale_language = unicode_property('14')
    locale_country = unicode_property('15')
    timezone = unicode_property('16')
    timezone_delta_gmt = long_property('17')

    @staticmethod
    def fromDeprecatedMobileInfoTO(oldMobileInfo):
        mobileInfo = MobileInfoTO()
        mobileInfo.version = 1
        mobileInfo.app_type = oldMobileInfo.type
        mobileInfo.app_major_version = None
        mobileInfo.app_minor_version = None
        mobileInfo.device_model_name = oldMobileInfo.hardwareModel
        mobileInfo.device_os_version = None
        mobileInfo.sim_country = None
        mobileInfo.sim_country_code = None
        mobileInfo.sim_carrier_code = None
        mobileInfo.sim_carrier_name = None
        mobileInfo.net_country = None
        mobileInfo.net_country_code = None
        mobileInfo.net_carrier_code = None
        mobileInfo.net_carrier_name = None
        mobileInfo.locale_language = oldMobileInfo.language
        mobileInfo.locale_country = oldMobileInfo.countryCode
        mobileInfo.timezone = None
        mobileInfo.timezone_delta_gmt = None
        return mobileInfo


class AccountTO(object):
    user = unicode_property('1')
    server = unicode_property('2')
    password = unicode_property('3')
    account = unicode_property('4')

    def to_dict(self):
        return dict(user=self.user, server=self.server, password=self.password, account=self.account)


class OAuthInfoTO(object):
    authorize_url = unicode_property('1')
    scopes = unicode_property('2')
    state = unicode_property('3')
    client_id = unicode_property('4')

    @classmethod
    def create(cls, authorize_url, scopes, state, client_id):
        to = cls()
        to.authorize_url = authorize_url
        to.scopes = scopes
        to.state = state
        to.client_id = client_id
        return to
