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

from rogerthat.rpc.rpc import capi
from rogerthat.to.friends import UpdateFriendRequestTO, UpdateFriendResponseTO, BecameFriendsRequestTO, \
    BecameFriendsResponseTO, UpdateFriendSetResponseTO, UpdateFriendSetRequestTO, UpdateGroupsResponseTO, \
    UpdateGroupsRequestTO
from mcfw.rpc import returns, arguments


@capi('com.mobicage.capi.friends.updateFriend')
@returns(UpdateFriendResponseTO)
@arguments(request=UpdateFriendRequestTO)
def updateFriend(request):
    pass


@capi('com.mobicage.capi.friends.updateFriendSet')
@returns(UpdateFriendSetResponseTO)
@arguments(request=UpdateFriendSetRequestTO)
def updateFriendSet(request):
    pass


@capi('com.mobicage.capi.friends.becameFriends')
@returns(BecameFriendsResponseTO)
@arguments(request=BecameFriendsRequestTO)
def becameFriends(request):
    pass


@capi('com.mobicage.capi.friends.updateGroups')
@returns(UpdateGroupsResponseTO)
@arguments(request=UpdateGroupsRequestTO)
def updateGroups(request):
    pass
