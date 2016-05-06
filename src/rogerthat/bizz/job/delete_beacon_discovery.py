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

from types import NoneType

from rogerthat.bizz.job import run_job
from rogerthat.bizz.location import delete_beacon_discovery_response
from rogerthat.capi.location import deleteBeaconDiscovery
from rogerthat.dal.service import get_friend_service_identity_connections_of_service_identity_keys_query
from rogerthat.models import FriendServiceIdentityConnection
from rogerthat.rpc import users
from rogerthat.rpc.rpc import logError
from rogerthat.to.location import DeleteBeaconDiscoveryRequestTO
from mcfw.rpc import returns, arguments


@returns(NoneType)
@arguments(service_idenity_user=users.User, uuid=unicode, major=unicode, minor=unicode)
def schedule_delete_beacon_discovery_for_all_users_of_service_identity(service_idenity_user, uuid, major, minor):
    request = DeleteBeaconDiscoveryRequestTO()
    request.uuid = uuid
    request.name = u"%s|%s" % (major, minor)

    run_job(get_friend_service_identity_connections_of_service_identity_keys_query, [service_idenity_user], _delete_beaconDiscovery_for_user, [request])

def _delete_beaconDiscovery_for_user(fsic_key, request):
    fsic = FriendServiceIdentityConnection.get(fsic_key)
    deleteBeaconDiscovery(delete_beacon_discovery_response, logError, fsic.friend, request=request)
