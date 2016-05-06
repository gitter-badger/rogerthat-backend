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

from rogerthat.to import ReturnStatusTO
from mcfw.properties import unicode_property, long_property, float_property


class UserTO(object):
    email = unicode_property('1')
    name = unicode_property('2')
    avatarId = long_property('3')
    app_id = unicode_property('4')

    @staticmethod
    def from_profile_info(profile_info):
        from rogerthat.utils.app import get_app_user_tuple

        u = UserTO()
        human_user, app_id = get_app_user_tuple(profile_info.user)
        u.email = human_user.email() if profile_info else None
        u.name = profile_info.name if profile_info else None
        u.avatarId = profile_info.avatarId if profile_info else -1
        u.app_id = app_id
        return u


class StartDebuggingReturnStatusTO(ReturnStatusTO):
    xmpp_target_jid = unicode_property('51')
    xmpp_target_password = unicode_property('52')
    type = long_property('53')

    @classmethod
    def create(cls, success=True, errormsg=None, xmpp_target_jid=None, xmpp_target_password=None, type_=0):
        r = super(StartDebuggingReturnStatusTO, cls).create(success, errormsg)
        r.xmpp_target_jid = xmpp_target_jid
        r.xmpp_target_password = xmpp_target_password
        r.type = type_
        return r


class MonitoringQueueTO(object):
    name = unicode_property('1')
    oldest_eta_usec = long_property('2')
    executed_last_minute = long_property('3')
    in_flight = long_property('4')
    enforced_rate = float_property('5')

    @staticmethod
    def from_model(name, model):
        to = MonitoringQueueTO()
        to.name = unicode(name)
        to.oldest_eta_usec = long(model.oldest_eta_usec) if model.oldest_eta_usec else 0
        to.executed_last_minute = long(model.executed_last_minute) if model.executed_last_minute else 0
        to.in_flight = long(model.in_flight) if model.in_flight else 0
        to.enforced_rate = float(model.enforced_rate) if model.enforced_rate else 0.0
        return to


class MonitoringClientErrorTO(object):
    platform = unicode_property('1')
    count = long_property('2')
    description = unicode_property('3')
    parent_id = unicode_property('4')

    @staticmethod
    def from_model(model):
        to = MonitoringClientErrorTO()
        to.platform = model.platform_string
        to.count = model.parent().occurenceCount
        to.description = model.parent().description
        to.parent_id = model.parent().key().name()
        return to
