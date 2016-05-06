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

from rogerthat.utils import get_officially_supported_languages, get_full_language_string
from mcfw.properties import unicode_property, bool_property, long_property, typed_property, unicode_list_property


class UserProfileTO(object):
    name = unicode_property('1')
    userCode = unicode_property('2')

    @staticmethod
    def fromUserProfile(user_profile):
        from rogerthat.bizz.friends import userCode
        p = UserProfileTO()
        p.name = user_profile.name
        p.userCode = userCode(user_profile.user)
        return p

class ProfileLocationTO(object):
    address = unicode_property('1')
    lat = long_property('2')
    lon = long_property('3')

class SearchConfigTO(object):
    enabled = bool_property('1')
    keywords = unicode_property('2')
    locations = typed_property('3', ProfileLocationTO, True)

    @staticmethod
    def fromDBSearchConfig(search_config, locations):
        sc = SearchConfigTO()
        sc.enabled = search_config.enabled
        sc.keywords = search_config.keywords
        sc.locations = list()
        for location in locations:
            loc = ProfileLocationTO()
            loc.address = location.address
            loc.lat = location.lat
            loc.lon = location.lon
            sc.locations.append(loc)
        return sc

class CompleteProfileTO(UserProfileTO):
    isService = bool_property('100')
    allLanguages = unicode_list_property('101')
    allLanguagesStr = unicode_list_property('102')
    userLanguage = unicode_property('103')
    organizationType = long_property('104')

    @staticmethod
    def fromProfileInfo(profile_info):
        from rogerthat.bizz.friends import userCode
        from rogerthat.dal.profile import get_service_profile
        from rogerthat.utils.service import get_service_user_from_service_identity_user
        p = CompleteProfileTO()
        p.isService = profile_info.isServiceIdentity
        p.name = profile_info.name
        if p.isService:
            p.userCode = None
            p.allLanguages = []
            p.allLanguagesStr = []
            p.userLanguage = None
            profile = get_service_profile(get_service_user_from_service_identity_user(profile_info.user))
            p.organizationType = profile.organizationType
        else:
            p.userCode = userCode(profile_info.user)
            p.allLanguages = get_officially_supported_languages(iso_format=False)
            p.allLanguagesStr = map(get_full_language_string, p.allLanguages)
            p.userLanguage = profile_info.language
            p.organizationType = 0
        return p

class TrialServiceTO(object):
    account = unicode_property('1')
    password = unicode_property('2')

    @staticmethod
    def fromDBTrialServiceAccount(account):
        ts = TrialServiceTO()
        ts.account = account.service.email()
        ts.password = account.password
        return ts
