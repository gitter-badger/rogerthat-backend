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

from mcfw.rpc import returns, arguments
from rogerthat.rpc.rpc import expose
from rogerthat.to.beacon import GetBeaconRegionsResponseTO, GetBeaconRegionsRequestTO
from rogerthat.to.location import GetFriendLocationRequestTO, GetFriendLocationResponseTO, \
    GetFriendsLocationResponseTO, GetFriendsLocationRequestTO, GetLocationRequestTO, BeaconDiscoveredResponseTO, \
    BeaconDiscoveredRequestTO, BeaconInReachResponseTO, BeaconInReachRequestTO, BeaconOutOfReachResponseTO, \
    BeaconOutOfReachRequestTO
from rogerthat.utils.app import create_app_user, get_app_id_from_app_user
from rogerthat.utils.service import remove_slash_default, add_slash_default


@expose(('api',))
@returns(GetFriendLocationResponseTO)
@arguments(request=GetFriendLocationRequestTO)
def get_friend_location(request):
    from rogerthat.rpc import users
    from rogerthat.bizz.location import get_friend_location as bizz_get_friend_location
    user = users.get_current_user()
    bizz_get_friend_location(user, create_app_user(users.User(request.friend), get_app_id_from_app_user(user)),
                             target=GetLocationRequestTO.TARGET_MOBILE)
    response = GetFriendLocationResponseTO()
    response.location = None  # for backwards compatibility reasons
    return response


@expose(('api',))
@returns(GetFriendsLocationResponseTO)
@arguments(request=GetFriendsLocationRequestTO)
def get_friend_locations(request):
    from rogerthat.rpc import users
    from rogerthat.bizz.location import get_friend_locations as bizz_get_friend_locations
    user = users.get_current_user()
    response = GetFriendsLocationResponseTO()
    response.locations = bizz_get_friend_locations(user)
    return response


@expose(('api',))
@returns(BeaconDiscoveredResponseTO)
@arguments(request=BeaconDiscoveredRequestTO)
def beacon_discovered(request):
    from rogerthat.rpc import users
    from rogerthat.bizz.beacon import add_new_beacon_discovery
    app_user = users.get_current_user()
    response = BeaconDiscoveredResponseTO()
    service_identity_user, tag = add_new_beacon_discovery(app_user, request.uuid, request.name)
    if service_identity_user:
        response.friend_email = remove_slash_default(service_identity_user).email()
    else:
        response.friend_email = None
    response.tag = tag
    return response


@expose(('api',))
@returns(BeaconInReachResponseTO)
@arguments(request=BeaconInReachRequestTO)
def beacon_in_reach(request):
    from rogerthat.rpc import users
    from rogerthat.bizz.location import update_friend_in_reach
    update_friend_in_reach(users.get_current_user(), add_slash_default(users.User(request.friend_email)),
                           request.uuid, request.name, request.proximity)
    return BeaconInReachResponseTO()


@expose(('api',))
@returns(BeaconOutOfReachResponseTO)
@arguments(request=BeaconOutOfReachRequestTO)
def beacon_out_of_reach(request):
    from rogerthat.rpc import users
    from rogerthat.bizz.location import update_friend_out_of_reach
    update_friend_out_of_reach(users.get_current_user(), add_slash_default(users.User(request.friend_email)),
                               request.uuid, request.name)
    return BeaconOutOfReachResponseTO()


@expose(('api',))
@returns(GetBeaconRegionsResponseTO)
@arguments(request=GetBeaconRegionsRequestTO)
def getBeaconRegions(request):
    from rogerthat.rpc import users
    from rogerthat.dal.app import get_app_by_id

    app_user = users.get_current_user()
    app_id = get_app_id_from_app_user(app_user)
    app = get_app_by_id(app_id)
    if app:
        beacon_regions = app.beacon_regions()
    else:
        beacon_regions = list()
    return GetBeaconRegionsResponseTO.fromDBBeaconRegions(beacon_regions)
