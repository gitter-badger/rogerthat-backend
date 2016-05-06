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

from rogerthat.models import Registration, InstallationLog, Installation
from rogerthat.rpc.models import Mobile
from mcfw.rpc import returns, arguments


@returns(Registration)
@arguments(mobile=Mobile)
def get_registration_by_mobile(mobile):
    qry = Registration.gql("WHERE mobile = :mobile")
    qry.bind(mobile=mobile)
    return qry.get()

@returns(tuple)
@arguments(min_timestamp=int, max_timestamp=int, cursor=unicode, batch_size=(int, long))
def get_installations(min_timestamp, max_timestamp, cursor=None, batch_size=10):
    qry = Installation.gql("WHERE timestamp > :min_timestamp AND timestamp < :max_timestamp ORDER BY timestamp DESC")
    qry.bind(min_timestamp=min_timestamp, max_timestamp=max_timestamp)
    qry.with_cursor(cursor)
    installations = qry.fetch(batch_size)
    return installations, qry.cursor()

@returns([InstallationLog])
@arguments(installation=Installation)
def get_installation_logs_by_installation(installation):
    qry = InstallationLog.gql("WHERE ancestor IS :ancestor ORDER BY timestamp")
    qry.bind(ancestor=installation)
    return list(qry.run())

@returns(Registration)
@arguments(installation=Installation)
def get_last_but_one_registration(installation):
    qry = Registration.gql("WHERE installation = :installation ORDER BY timestamp DESC OFFSET 1")
    qry.bind(installation=installation)
    return qry.get()
