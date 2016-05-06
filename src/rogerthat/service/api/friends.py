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

import re
from types import NoneType

from rogerthat.dal.app import get_app_by_id
from rogerthat.dal.profile import get_profile_infos
from rogerthat.models import ServiceProfile, UserProfile
from rogerthat.rpc import users
from rogerthat.rpc.service import service_api, service_api_callback
from rogerthat.settings import get_server_settings
from rogerthat.to.activity import GeoPointWithTimestampTO
from rogerthat.to.beacon import BeaconTO
from rogerthat.to.friends import ServiceFriendStatusTO, FriendListResultTO, ServiceFriendTO, \
    SubscribedBroadcastUsersTO, SubscribedBroadcastReachTO
from rogerthat.to.messaging import BaseMemberTO, BroadcastTargetAudienceTO
from rogerthat.to.roles import RoleTO
from rogerthat.to.service import UserDetailsTO
from rogerthat.utils.app import create_app_user, get_app_user_tuple
from rogerthat.utils.crypto import decrypt, encrypt
from rogerthat.utils.service import create_service_identity_user
from mcfw.consts import MISSING
from mcfw.rpc import arguments, returns
from rogerthat.utils import bizz_check

@service_api(function=u"friend.invite")
@returns(NoneType)
@arguments(email=unicode, name=unicode, message=unicode, language=unicode, tag=unicode, service_identity=unicode, app_id=unicode)
def invite(email, name, message, language, tag, service_identity=None, app_id=None):
    from rogerthat.bizz.friends import invite as invite_bizz, ORIGIN_SERVICE_INVITE
    from rogerthat.bizz.service import get_and_validate_service_identity_user, get_and_validate_app_id_for_service_identity_user
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    app_id = get_and_validate_app_id_for_service_identity_user(service_identity_user, app_id)
    invite_bizz(service_identity_user, email, name, message, language, tag, origin=ORIGIN_SERVICE_INVITE, app_id=app_id)


@service_api_callback(function=u"friend.invite_result", code=ServiceProfile.CALLBACK_FRIEND_INVITE_RESULT)
@returns(NoneType)
@arguments(email=unicode, result=unicode, tag=unicode, origin=unicode, service_identity=unicode,
           user_details=[UserDetailsTO])
def invite_result(email, result, tag, origin, service_identity, user_details):
    pass


@service_api_callback(function=u"friend.invited", code=ServiceProfile.CALLBACK_FRIEND_INVITED)
@returns(unicode)
@arguments(email=unicode, name=unicode, message=unicode, language=unicode, tag=unicode, origin=unicode,
           service_identity=unicode, user_details=[UserDetailsTO])
def invited(email, name, message, language, tag, origin, service_identity, user_details):
    pass


@service_api_callback(function=u"friend.update", code=ServiceProfile.CALLBACK_FRIEND_UPDATE)
@returns()
@arguments(user_details=UserDetailsTO)
def update(user_details):
    pass


@service_api(function=u"friend.break_up")
@returns(NoneType)
@arguments(email=unicode, service_identity=unicode, app_id=unicode)
def break_friendship(email, service_identity=None, app_id=None):
    from rogerthat.bizz.friends import breakFriendShip
    from rogerthat.bizz.service import get_and_validate_service_identity_user, get_and_validate_app_id_for_service_identity_user
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    app_id = get_and_validate_app_id_for_service_identity_user(service_identity_user, app_id)
    breakFriendShip(service_identity_user, create_app_user(users.User(email), app_id))


@service_api_callback(function=u"friend.broke_up", code=ServiceProfile.CALLBACK_FRIEND_BROKE_UP)
@returns(NoneType)
@arguments(email=unicode, service_identity=unicode, user_details=[UserDetailsTO])
def broke_friendship(email, service_identity, user_details):
    pass


@service_api(function=u"friend.get_status", cache_result=False)
@returns(ServiceFriendStatusTO)
@arguments(email=unicode, service_identity=unicode, app_id=unicode)
def get_status(email, service_identity=None, app_id=None):
    from rogerthat.bizz.friends import get_service_friend_status
    from rogerthat.bizz.service import get_and_validate_service_identity_user, get_and_validate_app_id_for_service_identity_user
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    app_id = get_and_validate_app_id_for_service_identity_user(service_identity_user, app_id)
    return get_service_friend_status(service_identity_user, create_app_user(users.User(email), app_id))


@service_api(function=u"friend.resolve", cache_result=False)
@returns(ServiceFriendStatusTO)
@arguments(url=unicode, service_identity=unicode)
def resolve(url, service_identity=None):
    url = url.upper()
    m = re.match("(HTTPS?://)(.*)/(M|S)/(.*)", url)
    if m:
        from rogerthat.pages.shortner import get_short_url_by_code
        code = m.group(4)
        su = get_short_url_by_code(code)

        if su.full.startswith("/q/i"):
            from rogerthat.bizz.friends import get_profile_info_via_user_code
            profile_info = get_profile_info_via_user_code(su.full[4:])
            if profile_info:
                from rogerthat.bizz.friends import get_service_friend_status
                from rogerthat.bizz.service import get_and_validate_service_identity_user
                service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
                return get_service_friend_status(service_identity_user, profile_info.user)
    return None


@service_api(function=u"friend.list", cache_result=False)
@returns(FriendListResultTO)
@arguments(service_identity=unicode, cursor=unicode, app_id=unicode, batch_count=int)
def list_friends(service_identity=None, cursor=None, app_id=None, batch_count=100):
    from rogerthat.bizz.service import get_and_validate_service_identity_user, valididate_app_id_for_service_identity_user
    from rogerthat.dal.service import get_users_connected_to_service_identity

    bizz_check(batch_count <= 1000, "Cannot batch more than 1000 friends at once.")

    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    if app_id:
        valididate_app_id_for_service_identity_user(service_identity_user, app_id)
    if cursor:
        try:
            cursor = decrypt(service_identity_user, cursor)
        except:
            from rogerthat.bizz.exceptions import InvalidCursorException
            raise InvalidCursorException()
    fsics, cursor = get_users_connected_to_service_identity(service_identity_user, cursor, batch_count, app_id)
    # prevent extra roundtrip by trying to detect whether there are more results to fetch
    if len(fsics) < batch_count and cursor:
        extra_fsics, _ = get_users_connected_to_service_identity(service_identity_user, cursor, 1, app_id)
        if len(extra_fsics) == 0:
            cursor = None
    result = FriendListResultTO()
    result.cursor = unicode(encrypt(service_identity_user, cursor)) if cursor else None
    result.friends = list()

    user_profiles = get_profile_infos([fsic.friend for fsic in fsics], expected_types=[UserProfile] * len(fsics))
    app_names = {}
    for user_profile, fsic in zip(user_profiles, fsics):
        svc_friend = ServiceFriendTO()
        human_user, svc_friend.app_id = get_app_user_tuple(fsic.friend)
        svc_friend.avatar = u"%s/unauthenticated/mobi/cached/avatar/%s" % (get_server_settings().baseUrl, fsic.friend_avatarId)
        svc_friend.email = human_user.email()
        svc_friend.language = user_profile.language
        svc_friend.name = fsic.friend_name
        if svc_friend.app_id not in app_names:
            app = get_app_by_id(svc_friend.app_id)
            app_names[svc_friend.app_id] = app.name

        svc_friend.app_name = app_names[svc_friend.app_id]
        result.friends.append(svc_friend)
    return result


@service_api(function=u"friend.get_broadcast_audience")
@returns(SubscribedBroadcastUsersTO)
@arguments(broadcast_type=unicode, service_identity=unicode)
def get_broadcast_audience(broadcast_type, service_identity=None):
    from rogerthat.bizz.friends import getSubscribedBroadcastUsers
    from rogerthat.bizz.service import get_and_validate_service_identity_user
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    return getSubscribedBroadcastUsers(service_identity_user, broadcast_type)

@service_api(function=u"friend.get_broadcast_reach")
@returns(SubscribedBroadcastReachTO)
@arguments(broadcast_type=unicode, target_audience=BroadcastTargetAudienceTO, service_identity=unicode)
def get_broadcast_reach(broadcast_type, target_audience, service_identity=None):
    from rogerthat.bizz.friends import getSubscribedBroadcastReach
    from rogerthat.bizz.service import get_and_validate_service_identity_user
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    return getSubscribedBroadcastReach(service_identity_user, broadcast_type, target_audience.min_age,
                                       target_audience.max_age, target_audience.gender)

@service_api_callback(function=u"friend.in_reach", code=ServiceProfile.CALLBACK_FRIEND_IN_REACH)
@returns(NoneType)
@arguments(service_identity=unicode, user_details=[UserDetailsTO], beacon=BeaconTO, proximity=unicode, timestamp=int)
def in_reach(service_identity, user_details, beacon, proximity, timestamp):
    pass

@service_api_callback(function=u"friend.out_of_reach", code=ServiceProfile.CALLBACK_FRIEND_OUT_OF_REACH)
@returns(NoneType)
@arguments(service_identity=unicode, user_details=[UserDetailsTO], beacon=BeaconTO, timestamp=int)
def out_of_reach(service_identity, user_details, beacon, timestamp):
    pass

@service_api_callback(function=u"friend.is_in_roles", code=ServiceProfile.CALLBACK_FRIEND_IS_IN_ROLES)
@returns([(int, long)])
@arguments(service_identity=unicode, user_details=[UserDetailsTO], roles=[RoleTO])
def is_in_roles(service_identity, user_details, roles):
    """
    Returns the role_id's of the roles of which the user is a member of.
    """
    pass


@service_api(function=u"friend.rebuild_synced_roles")
@returns(NoneType)
@arguments(members=[BaseMemberTO], service_identities=[unicode])
def rebuild_synced_roles(members, service_identities):
    """
    Rebuilds access to service_identies based on SYNCED roles.
    If members is empty or None, access for all members of service_identities will be checked.
    If service_identies is empty or None, access for members of all service_identities will be checked.
    """
    from rogerthat.bizz.job.rebuild_synced_roles import schedule_rebuild_synced_roles
    service_user = users.get_current_user()

    if members in (None, MISSING):
        members = list()
    if service_identities in (None, MISSING):
        service_identities = list()

    schedule_rebuild_synced_roles(service_user, [create_app_user(users.User(m.member), m.app_id) for m in members],
                                  [create_service_identity_user(service_user, si_id) for si_id in service_identities])

@service_api(function=u"friend.track_location")
@returns(unicode)
@arguments(email=unicode, until=int, distance_filter=int, service_identity=unicode, app_id=unicode)
def track_location(email, until, distance_filter, service_identity=None, app_id=None):
    from rogerthat.bizz.location import start_service_location_tracking
    from rogerthat.bizz.service import get_and_validate_service_identity_user, get_and_validate_app_id_for_service_identity_user

    """
    Enables location tracking of the specified users until the specified timestamp has elapsed.
    service_identity: Service identity of the users.
    users: list of users that need to be tracked.
    until: timestamp until users will be tracked.
    frequency: number of seconds between location tracking intervals

    returns tracker id
    """
    # TODO Bart: Add an authorization system so that this api call only works for authorized services / identities
    service_user = users.get_current_user()
    service_identity_user = get_and_validate_service_identity_user(service_user, service_identity)
    app_id = get_and_validate_app_id_for_service_identity_user(service_identity_user, app_id)
    app_user = create_app_user(users.User(email), app_id)
    return start_service_location_tracking(service_identity_user, app_user, until, distance_filter)

@service_api(function=u"friend.cancel_location_tracker")
@returns(NoneType)
@arguments(tracker_key=unicode)
def cancel_location_tracker(tracker_key):
    from rogerthat.bizz.location import disable_service_location_tracker
    """
    Cancels the location tracking for a certain user
    """
    service_user = users.get_current_user()
    disable_service_location_tracker(service_user, tracker_key)

@service_api_callback(function=u"friend.location_fix", code=ServiceProfile.CALLBACK_FRIEND_LOCATION_FIX)
@returns(NoneType)
@arguments(service_identity=unicode, user_details=[UserDetailsTO], location=GeoPointWithTimestampTO, tracker_key=unicode)
def location_fix(service_identity, user_details, location, tracker_key):
    pass

@service_api_callback(function=u"friend.register", code=ServiceProfile.CALLBACK_FRIEND_REGISTER)
@returns(unicode)
@arguments(service_identity=unicode, user_details=[UserDetailsTO], origin=unicode)
def register(service_identity, user_details, origin):
    """
    Validates if a user can register when scanning a:
    - qr code
    Returns 'accepted', 'accept_and_connect' or 'denied'
    """
    pass

@service_api_callback(function=u"friend.register_result", code=ServiceProfile.CALLBACK_FRIEND_REGISTER_RESULT)
@returns(NoneType)
@arguments(service_identity=unicode, user_details=[UserDetailsTO], origin=unicode)
def register_result(service_identity, user_details, origin):
    pass
