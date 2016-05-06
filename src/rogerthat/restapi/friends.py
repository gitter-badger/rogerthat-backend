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

from rogerthat.dal.profile import get_user_profile
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile
from rogerthat.rpc.service import ServiceApiException
from rogerthat.to.friends import FriendTO, FriendWithRelationsTO, FriendRelationTO, FullFriendsInfoTO, \
    FRIEND_TYPE_PERSON
from rogerthat.utils.app import create_app_user
from rogerthat.utils.service import create_service_identity_user
from mcfw.consts import MISSING
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments


@rest("/mobi/rest/friends/invite", "post")
@returns(unicode)
@arguments(email=unicode, message=unicode, tag=unicode)
def invite(email, message, tag):
    from rogerthat.bizz.friends import invite as bizzInvite
    from rogerthat.bizz.friends import ORIGIN_USER_INVITE
    try:
        app_user = users.get_current_user()
        bizzInvite(app_user, email, None, message, None, None, origin=ORIGIN_USER_INVITE, app_id=users.get_current_app_id())
    except ServiceApiException, e:
        return unicode(e)
    else:
        return


@rest("/mobi/rest/friends/get", "get")
@returns([FriendTO])
@arguments()
def get():
    from rogerthat.dal.friend import get_friends_map
    from rogerthat.models.properties.friend import FriendDetail
    user = users.get_current_user()
    friendMap = get_friends_map(user)
    return [FriendTO.fromDBFriendDetail(f) for f in friendMap.friendDetails if f.type == FriendDetail.TYPE_USER]

@rest("/mobi/rest/friends/get_full", "get")
@returns(FullFriendsInfoTO)
@arguments()
def get_full_friends_list():
    from rogerthat.dal.friend import get_friends_map_cached
    from rogerthat.dal.friend import get_friends_friends_maps
    from rogerthat.bizz.friends import userCode
    from rogerthat.models.properties.friend import FriendDetail
    app_user = users.get_current_user()
    friendMap = get_friends_map_cached(app_user)
    def secure_email(frto):
        uzer = users.User(str(frto.email))
        if uzer not in friendMap.friends:
            frto.email = userCode(uzer)
        return frto
    friendFriendMaps = get_friends_friends_maps(app_user)
    friendFriendMapsMap = dict(((ffm.user, ffm) for ffm in friendFriendMaps))
    l = list()
    for friend in friendMap.friends:
        ffm = friendFriendMapsMap.get(friend, None)
        if ffm:
            # User friends
            try:
                friendDetail = friendMap.friendDetails[ffm.user.email()]
            except KeyError:
                continue
            fwr = FriendWithRelationsTO()
            fwr.friend = FriendTO.fromDBFriendDetail(friendDetail)
            if friendDetail.sharesContacts:
                fwr.friends = [secure_email(FriendRelationTO.fromDBFriendDetail(fd)) for fd in ffm.friendDetails.values() if fd.email != app_user.email() and fd.type == FriendDetail.TYPE_USER]
            else:
                fwr.friends = []
            fwr.type = FRIEND_TYPE_PERSON
            l.append(fwr)

    for ffm in friendFriendMaps:
        try:
            friendDetail = friendMap.friendDetails[ffm.user.email()]
        except KeyError:
            continue
        if friendDetail.isService:
            continue
        fwr = FriendWithRelationsTO()
        fwr.friend = FriendTO.fromDBFriendDetail(friendDetail)
        if friendDetail.sharesContacts:
            fwr.friends = [FriendRelationTO.fromDBFriendDetail(fd) for fd in ffm.friendDetails.values()]
        else:
            fwr.friends = []
        l.append(fwr)
    ffit = FullFriendsInfoTO()
    ffit.shareContacts = friendMap.shareContacts
    ffit.friends = l

    user_profile = get_user_profile(app_user)
    ffit.canShareLocation = False
    if user_profile.mobiles:
        for mob in user_profile.mobiles:
            if mob.type_ in (Mobile.TYPE_ANDROID_HTTP, Mobile.TYPE_LEGACY_IPHONE_XMPP, Mobile.TYPE_IPHONE_HTTP_APNS_KICK,
                             Mobile.TYPE_IPHONE_HTTP_XMPP_KICK, Mobile.TYPE_WINDOWS_PHONE):
                ffit.canShareLocation = True
                break
    return ffit

@rest("/mobi/rest/friends/get_full_services", "get")
@returns([FriendTO])
@arguments()
def get_full_services_list():
    from rogerthat.dal.friend import get_friends_map_cached
    app_user = users.get_current_user()
    friendMap = get_friends_map_cached(app_user)
    return [FriendTO.fromDBFriendDetail(fd, True, True, tagetUser=app_user) for fd in (friendMap.friendDetails[friend.email()] for friend in friendMap.friends) if fd.isService]

@rest("/mobi/rest/friends/shareLocation", "post")
@returns(NoneType)
@arguments(friend=unicode, enabled=bool)
def shareLocation(friend, enabled):
    from rogerthat.bizz.friends import shareLocation as bizzShareLocation
    app_user = users.get_current_user()
    return bizzShareLocation(app_user, create_app_user(users.User(friend), users.get_current_app_id()), enabled)

@rest("/mobi/rest/friends/requestLocationSharing", "post")
@returns(NoneType)
@arguments(friend=unicode, message=unicode)
def requestLocationSharing(friend, message):
    from rogerthat.bizz.friends import requestLocationSharing as bizzRequestLocationSharing
    app_user = users.get_current_user()
    return bizzRequestLocationSharing(app_user, create_app_user(users.User(friend), users.get_current_app_id()), message)


@rest("/mobi/rest/friends/break", "post")
@returns(NoneType)
@arguments(friend=unicode, service_identity=unicode, app_id=unicode)
def breakFriendship(friend, service_identity=None, app_id=None):
    # service_identity & app_id are set when a service does a breakFriendship
    from rogerthat.bizz.friends import breakFriendShip as bizzBreakFriendship
    user = users.get_current_user()
    if service_identity and service_identity != MISSING:
        user = create_service_identity_user(user, service_identity)
    friend_user = users.User(friend)
    if app_id:
        friend_user = create_app_user(friend_user, app_id)
    else:
        pass  # the bizz layer will handle the app_id stuff
    return bizzBreakFriendship(user, friend_user)

@rest("/mobi/rest/friends/setShareContacts", "post")
@returns(NoneType)
@arguments(enabled=bool)
def setShareContacts(enabled):
    from rogerthat.bizz.friends import setShareContacts as bizzSetShareContacts
    user = users.get_current_user()
    return bizzSetShareContacts(user, enabled)

@rest("/mobi/rest/friends/userCode", "get")
@returns(unicode)
@arguments()
def userCode():
    from rogerthat.bizz.friends import userCode as userCodeBizz
    return userCodeBizz(users.get_current_user())
