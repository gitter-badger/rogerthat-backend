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

from rogerthat.dal import parent_key
from rogerthat.models import Beacon
from rogerthat.rpc import users
from mcfw.rpc import returns, arguments


@returns(Beacon)
@arguments(uuid=unicode, name=unicode)
def get_beacon(uuid, name):
    qry = Beacon.gql("WHERE uuid = :uuid AND name = :name")
    qry.bind(uuid=uuid.lower(), name=name)
    return qry.get()

@returns([Beacon])
@arguments(service_user=users.User, service_identity=unicode)
def get_beacons(service_user, service_identity):
    qry = Beacon.all().ancestor(parent_key(service_user)).filter('service_identity =', service_identity)
    return qry.fetch(None)
