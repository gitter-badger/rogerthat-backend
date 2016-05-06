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

from mcfw.properties import unicode_property, long_property, typed_property
from rogerthat.to import ReturnStatusTO



class GrantTO(object):
    service_email = unicode_property('0')
    identity = unicode_property('1')
    user_email = unicode_property('2')
    user_name = unicode_property('3')
    user_avatar_id = long_property('4')
    role_type = unicode_property('5')
    role_id = long_property('6')
    role = unicode_property('7')
    app_id = unicode_property('8')


class RoleTO(object):
    id = long_property('1')
    name = unicode_property('2')
    creation_time = long_property('3')
    type = unicode_property('4')

    @staticmethod
    def fromServiceRole(service_role):
        r = RoleTO()
        r.id = service_role.role_id
        r.name = service_role.name
        r.creation_time = service_role.creationTime
        r.type = service_role.type
        return r


class RolesReturnStatusTO(ReturnStatusTO):
    roles = typed_property('51', RoleTO, True)
    service_identity_email = unicode_property('52')

    @classmethod
    def create(cls, success=True, errormsg=None, roles=None, service_identity_email=None):
        r = super(RolesReturnStatusTO, cls).create(success, errormsg)
        r.roles = list() if roles is None else roles
        r.service_identity_email = service_identity_email
        return r
