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

from google.appengine.ext import db
from mcfw.properties import unicode_property, long_property, bool_property, typed_property


class InstallationLogTO(object):
    timestamp = long_property('1')
    time = unicode_property('2')
    description = unicode_property('3')
    description_url = unicode_property('4')
    pin = long_property('5')
    registration_user_email = unicode_property('6')
    mobile_os_version = unicode_property('7')
    mobile_hardware_model = unicode_property('8')
    profile_age = long_property('9')
    profile_gender = unicode_property('10')

    @staticmethod
    def from_model(obj):
        to = InstallationLogTO()
        to.timestamp = obj.timestamp
        to.time = unicode(obj.time)
        to.description = obj.description
        to.description_url = obj.description_url
        to.pin = obj.pin
        to.registration_user_email = obj.registration.user.email() if obj.registration else None
        to.mobile_os_version = obj.mobile.osVersion if obj.mobile else None
        to.mobile_hardware_model = obj.mobile.hardwareModel if obj.mobile else None
        try:
            to.profile_age = obj.profile.age if obj.profile else 0
        except db.ReferencePropertyResolveError:
            to.profile_age = 0
        try:
            to.profile_gender = obj.profile.gender_str if obj.profile else None
        except db.ReferencePropertyResolveError:
            to.profile_gender = None
        return to


class InstallationTO(object):
    install_id = unicode_property('1')
    version = unicode_property('2')
    platform = long_property('3')
    timestamp = long_property('4')
    app_id = unicode_property('5')
    platform_string = unicode_property('6')
    logs = typed_property('7', InstallationLogTO, True)
    logged_registration_successful = bool_property('8')

    @staticmethod
    def from_model(obj):
        to = InstallationTO()
        to.install_id = obj.install_id
        to.version = obj.version
        to.platform = obj.platform
        to.timestamp = obj.timestamp
        to.app_id = obj.app_id
        to.platform_string = unicode(obj.platform_string)
        to.logs = [InstallationLogTO.from_model(log) for log in obj.logs] if obj.logs else []
        to.logged_registration_successful = False
        t = 0
        for log in reversed(to.logs):
            if t != 0 and log.timestamp < t:
                break
            t = log.timestamp
            if log.description.capitalize().startswith('Registration successful'):
                to.logged_registration_successful = True

        return to

class InstallationsTO(object):
    offset = long_property('1')
    cursor = unicode_property('2')
    installations = typed_property('3', InstallationTO, True)

    @staticmethod
    def from_model(offset, cursor, installations):
        to = InstallationsTO()
        to.offset = offset
        to.cursor = unicode(cursor)
        to.installations = [InstallationTO.from_model(installation) for installation in installations]
        return to
