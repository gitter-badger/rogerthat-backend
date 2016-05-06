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

import base64
import logging

from rogerthat.bizz.friends import makeFriends
from rogerthat.bizz.service import InvalidAppIdException, UnsupportedAppIdException
from rogerthat.dal.app import get_app_name_by_id
from rogerthat.dal.profile import get_user_profile, get_profile_info
from rogerthat.dal.service import get_service_identity, get_default_service_identity
from rogerthat.models import App
from rogerthat.rpc.rpc import expose
from rogerthat.rpc.service import ApiWarning
from rogerthat.to.friends import FriendTO, GetFriendsListResponseTO, GetFriendsListRequestTO, ShareLocationResponseTO, \
    ShareLocationRequestTO, RequestShareLocationResponseTO, RequestShareLocationRequestTO, BreakFriendshipRequestTO, \
    BreakFriendshipResponseTO, InviteFriendResponseTO, InviteFriendRequestTO, GetAvatarRequestTO, GetAvatarResponseTO, \
    GetUserInfoRequestTO, GetUserInfoResponseTO, GetFriendInvitationSecretsResponseTO, GetFriendInvitationSecretsRequestTO, \
    AckInvitationByInvitationSecretResponseTO, AckInvitationByInvitationSecretRequestTO, LogInvitationSecretSentResponseTO, \
    LogInvitationSecretSentRequestTO, FindRogerthatUsersViaEmailRequestTO, FindRogerthatUsersViaEmailResponseTO, \
    FindRogerthatUsersViaFacebookResponseTO, FindRogerthatUsersViaFacebookRequestTO, FRIEND_TYPE_PERSON, \
    GetCategoryResponseTO, GetCategoryRequestTO, FriendCategoryTO, GetFriendEmailsResponseTO, GetFriendEmailsRequestTO, \
    GetFriendResponseTO, GetFriendRequestTO, GetGroupsResponseTO, GetGroupsRequestTO, GetGroupAvatarResponseTO, \
    GetGroupAvatarRequestTO, PutGroupResponseTO, PutGroupRequestTO, DeleteGroupResponseTO, DeleteGroupRequestTO, ErrorTO, \
    FindFriendResponseTO, FindFriendRequestTO, UserScannedResponseTO, UserScannedRequestTO, FRIEND_TYPE_SERVICE
from rogerthat.translations import localize
from rogerthat.utils import azzert, slog, try_or_defer, bizz_check
from rogerthat.utils.app import create_app_user, get_app_id_from_app_user, get_human_user_from_app_user, \
    remove_app_id
from rogerthat.utils.service import add_slash_default, remove_slash_default
from google.appengine.ext import db
from mcfw.consts import MISSING
from mcfw.rpc import returns, arguments


@expose(('api',))
@returns(GetFriendsListResponseTO)
@arguments(request=GetFriendsListRequestTO)
def getFriendsList(request):
    from rogerthat.rpc import users
    from rogerthat.dal.friend import get_friends_map
    user = users.get_current_user()
    friendMap = get_friends_map(user)
    response = GetFriendsListResponseTO()
    response.friends = [FriendTO.fromDBFriendDetail(f, True, True, targetUser=user) for f in friendMap.friendDetails]
    response.generation = friendMap.generation
    return response

@expose(('api',))
@returns(GetFriendEmailsResponseTO)
@arguments(request=GetFriendEmailsRequestTO)
def getFriendEmails(request):
    from rogerthat.rpc import users
    from rogerthat.dal.friend import get_friends_map

    @db.non_transactional
    def get_mobile_settings(m):
        from rogerthat.models import MobileSettings
        return MobileSettings.get(mobile=m)

    def trans():
        friendMap = get_friends_map(users.get_current_user())
        response = GetFriendEmailsResponseTO()
        response.emails = [remove_app_id(f).email() for f in friendMap.friends]
        response.generation = friendMap.generation
        response.friend_set_version = friendMap.version
        return response

    xg_on = db.create_transaction_options(xg=True)
    response = db.run_in_transaction_options(xg_on, trans)
    return response

@expose(('api',))
@returns(GetFriendResponseTO)
@arguments(request=GetFriendRequestTO)
def getFriend(request):
    from rogerthat.rpc import users
    from rogerthat.dal.friend import get_friends_map
    from rogerthat.pages.profile import get_avatar

    user = users.get_current_user()
    friendMap = get_friends_map(user)

    response = GetFriendResponseTO()
    response.generation = friendMap.generation

    friend = users.User(request.email)
    avatar_size = 100 if request.avatar_size is MISSING else request.avatar_size

    def populateFriendResponse():
        friendDetail = friendMap.friendDetails[friend.email()]
        response.friend = FriendTO.fromDBFriendDetail(friendDetail, True, True, targetUser=user)
        response.avatar = unicode(base64.b64encode(get_avatar(friendDetail.avatarId, avatar_size)))

    if friend.email() in friendMap.friendDetails:
        populateFriendResponse()
    else:
        friend = create_app_user(friend, get_app_id_from_app_user(user))
        if friend.email() in friendMap.friendDetails:
            populateFriendResponse()
        else:
            response.friend = None
            response.avatar = None
    return response

@expose(('api',))
@returns(ShareLocationResponseTO)
@arguments(request=ShareLocationRequestTO)
def shareLocation(request):
    from rogerthat.bizz.friends import shareLocation as bizzShareLocation
    from rogerthat.rpc import users
    user = users.get_current_user()
    bizzShareLocation(user, create_app_user(users.User(request.friend), get_app_id_from_app_user(user)), request.enabled)
    return None

@expose(('api',))
@returns(RequestShareLocationResponseTO)
@arguments(request=RequestShareLocationRequestTO)
def requestLocationSharing(request):
    from rogerthat.bizz.friends import requestLocationSharing as bizzRequestLocationSharing
    from rogerthat.rpc import users
    user = users.get_current_user()
    bizzRequestLocationSharing(user, create_app_user(users.User(request.friend), get_app_id_from_app_user(user)), request.message)
    return None

@expose(('api',))
@returns(BreakFriendshipResponseTO)
@arguments(request=BreakFriendshipRequestTO)
def breakFriendship(request):
    from rogerthat.bizz.friends import breakFriendShip as bizzBreakFriendship
    from rogerthat.rpc import users
    user = users.get_current_user()
    bizzBreakFriendship(user, users.User(request.friend), users.get_current_mobile())
    slog('T', user.email(), "com.mobicage.api.friends.breakFriendShip", email=request.friend)
    return None

@expose(('api',))
@returns(InviteFriendResponseTO)
@arguments(request=InviteFriendRequestTO)
def invite(request):
    from rogerthat.bizz.friends import invite as bizzInvite
    from rogerthat.bizz.friends import ORIGIN_USER_INVITE
    from rogerthat.rpc import users
    app_user = users.get_current_user()
    try:
        if request.email:
            bizzInvite(app_user, request.email, None, request.message, None, None, origin=ORIGIN_USER_INVITE,
                       app_id=get_app_id_from_app_user(app_user))
        else:
            logging.warn("%s not inviting email: %s", app_user, request.email)
    except InvalidAppIdException:
        logging.warn("%s triggered InvalidAppIdException while inviting email: %s", app_user, request.email)
    except UnsupportedAppIdException:
        logging.warn("%s triggered UnsupportedAppIdException while inviting email: %s", app_user, request.email)
    slog('T', users.get_current_user().email(), "com.mobicage.api.friends.invite", email=request.email, message=request.message)
    return None

@expose(('api',))
@returns(GetAvatarResponseTO)
@arguments(request=GetAvatarRequestTO)
def getAvatar(request):
    from rogerthat.pages.profile import get_avatar_cached
    response = GetAvatarResponseTO()
    size = 50 if request.size is MISSING else request.size
    response.avatar = unicode(base64.b64encode(get_avatar_cached(request.avatarId, size=size)))
    return response

@expose(('api',))
@returns(GetUserInfoResponseTO)
@arguments(request=GetUserInfoRequestTO)
def getUserInfo(request):
    from rogerthat.bizz.friends import get_profile_info_via_user_code
    from rogerthat.pages.profile import get_avatar_cached
    from rogerthat.rpc import users
    current_app_id = users.get_current_app_id()
    user_code = request.code
    if '@' in user_code:
        if "/" in user_code:
            profile_info = get_profile_info(users.User(user_code))
        else:
            profile_info = get_profile_info(create_app_user(users.User(user_code), current_app_id))
            if not profile_info:
                profile_info = get_default_service_identity(users.User(user_code))

        if not profile_info:
            raise ApiWarning("User with userCode or email '%s' not found!" % request.code)
    else:
        if "?" in user_code:
            user_code = user_code[:user_code.index("?")]
        profile_info = get_profile_info_via_user_code(user_code)

        if not profile_info:
            loglevel = logging.DEBUG if current_app_id == App.APP_ID_OSA_LOYALTY else logging.WARNING
            logging.log(loglevel, "User with userCode or email '%s' not found!" % request.code)
            response = GetUserInfoResponseTO()
            response.avatar = None
            response.avatar_id = 0
            response.description = None
            response.descriptionBranding = None
            response.app_id = response.email = response.name = response.qualifiedIdentifier = u"dummy"
            response.type = FRIEND_TYPE_PERSON
            response.profileData = None

            if current_app_id == App.APP_ID_OSA_LOYALTY:
                response.error = None
            else:
                response.error = ErrorTO()
                target_language = get_user_profile(users.get_current_user()).language
                response.error.title = localize(target_language, "Error")
                response.error.message = localize(target_language,
                                                  "The scanned QR code is not supported by the %(app_name)s app",
                                                  app_name=get_app_name_by_id(current_app_id))
                response.error.caption = response.error.action = None
            return response


    response = GetUserInfoResponseTO()
    response.avatar = unicode(base64.b64encode(get_avatar_cached(profile_info.avatarId)))
    response.avatar_id = profile_info.avatarId
    response.description = None
    response.descriptionBranding = None
    response.app_id = current_app_id if profile_info.isServiceIdentity else profile_info.app_id
    response.email = (remove_slash_default(profile_info.user) if profile_info.isServiceIdentity else get_human_user_from_app_user(profile_info.user)).email()
    response.name = profile_info.name
    response.qualifiedIdentifier = profile_info.qualifiedIdentifier
    response.type = FRIEND_TYPE_SERVICE if profile_info.isServiceIdentity else FRIEND_TYPE_PERSON
    response.profileData = None if profile_info.isServiceIdentity else profile_info.profileData

    if request.allow_cross_app == MISSING:
        request.allow_cross_app = False

    if request.allow_cross_app or current_app_id == profile_info.app_id:
        response.error = None
    else:
        response.error = ErrorTO()
        target_language = get_user_profile(users.get_current_user()).language
        response.error.title = localize(target_language, "Error")
        response.error.message = localize(target_language,
                                          "The scanned QR code is not supported by the %(app_name)s app",
                                          app_name=get_app_name_by_id(current_app_id))
        response.error.caption = response.error.action = None
    return response

@expose(('api',))
@returns(GetFriendInvitationSecretsResponseTO)
@arguments(request=GetFriendInvitationSecretsRequestTO)
def getFriendInvitationSecrets(request):
    from rogerthat.bizz.friends import create_friend_invitation_secrets
    from rogerthat.rpc import users
    response = GetFriendInvitationSecretsResponseTO()
    response.secrets = create_friend_invitation_secrets(users.get_current_user())
    return response

@expose(('api',))
@returns(AckInvitationByInvitationSecretResponseTO)
@arguments(request=AckInvitationByInvitationSecretRequestTO)
def ackInvitationByInvitationSecret(request):
    from rogerthat.bizz.friends import ack_invitation_by_invitation_secret, get_profile_info_via_user_code
    from rogerthat.rpc import users
    invitee = users.get_current_user()
    profile_info = get_profile_info_via_user_code(request.invitor_code)
    azzert(profile_info, "User with userCode %s not found!" % request.invitor_code)
    try_or_defer(ack_invitation_by_invitation_secret, invitee, profile_info.user, request.secret)
    return AckInvitationByInvitationSecretResponseTO()

@expose(('api',))
@returns(LogInvitationSecretSentResponseTO)
@arguments(request=LogInvitationSecretSentRequestTO)
def logInvitationSecretSent(request):
    from rogerthat.bizz.friends import log_invitation_secret_sent
    from rogerthat.rpc import users
    human_invitor_user = users.get_current_user()
    log_invitation_secret_sent(human_invitor_user, request.secret, request.phone_number, None, request.timestamp)
    return LogInvitationSecretSentResponseTO()

@expose(('api',))
@returns(FindRogerthatUsersViaEmailResponseTO)
@arguments(request=FindRogerthatUsersViaEmailRequestTO)
def findRogerthatUsersViaEmail(request):
    from rogerthat.bizz.profile import find_rogerthat_users_via_email
    from rogerthat.rpc import users
    response = FindRogerthatUsersViaEmailResponseTO()
    user_list = list()

    app_user = users.get_current_user()
    app_id = users.get_current_app_id()

    for email in request.email_addresses:
        try:
            user_list.append(create_app_user(users.User(email), app_id))
        except:
            logging.warning("Failed to parse '%s' into user object with app_id '%s'." % (email, app_id), exc_info=True)
    response.matched_addresses = [get_human_user_from_app_user(u).email() for u in find_rogerthat_users_via_email(app_user, user_list)]
    return response

@expose(('api',))
@returns(FindRogerthatUsersViaFacebookResponseTO)
@arguments(request=FindRogerthatUsersViaFacebookRequestTO)
def findRogerthatUsersViaFacebook(request):
    from rogerthat.bizz.profile import find_rogerthat_users_via_facebook
    from rogerthat.rpc import users
    response = FindRogerthatUsersViaFacebookResponseTO()
    response.matches = find_rogerthat_users_via_facebook(users.get_current_user(), request.access_token)
    return response

@expose(('api',))
@returns(GetCategoryResponseTO)
@arguments(request=GetCategoryRequestTO)
def getCategory(request):
    from rogerthat.dal.friend import get_friend_category_by_id
    response = GetCategoryResponseTO()
    response.category = FriendCategoryTO.from_model(get_friend_category_by_id(request.category_id))
    return response

@expose(('api',))
@returns(GetGroupsResponseTO)
@arguments(request=GetGroupsRequestTO)
def getGroups(request):
    from rogerthat.rpc import users
    from rogerthat.bizz.friends import getGroups as getGroupsBizz
    response = GetGroupsResponseTO()
    response.groups = getGroupsBizz(users.get_current_user())
    return response

@expose(('api',))
@returns(GetGroupAvatarResponseTO)
@arguments(request=GetGroupAvatarRequestTO)
def getGroupAvatar(request):
    from rogerthat.bizz.friends import getGroupAvatar as getGroupAvatarBizz
    response = GetGroupAvatarResponseTO()
    size = 50 if request.size is MISSING else request.size
    response.avatar = getGroupAvatarBizz(request.avatar_hash, size)
    return response

@expose(('api',))
@returns(PutGroupResponseTO)
@arguments(request=PutGroupRequestTO)
def putGroup(request):
    from rogerthat.bizz.friends import putGroup as putGroupBizz
    from rogerthat.rpc import users
    response = PutGroupResponseTO()
    avatar_hash_str = putGroupBizz(users.get_current_user(), request.guid, request.name, request.members, request.avatar, users.get_current_mobile())
    response.avatar_hash = None if avatar_hash_str is None else avatar_hash_str.decode('utf-8')
    return response

@expose(('api',))
@returns(DeleteGroupResponseTO)
@arguments(request=DeleteGroupRequestTO)
def deleteGroup(request):
    from rogerthat.bizz.friends import deleteGroup as deleteGroupBizz
    from rogerthat.rpc import users
    deleteGroupBizz(users.get_current_user(), request.guid, users.get_current_mobile())
    return DeleteGroupResponseTO()

@expose(('api',))
@returns(FindFriendResponseTO)
@arguments(request=FindFriendRequestTO)
def findFriend(request):
    from rogerthat.bizz.friends import find_friend
    from rogerthat.rpc import users
    response_to = find_friend(users.get_current_user(),
                               request.search_string,
                               None if request.cursor is MISSING else request.cursor,
                               50 if request.avatar_size is MISSING else min(67, request.avatar_size))  # max 67px
    return response_to


@expose(('api',))
@returns(UserScannedResponseTO)
@arguments(request=UserScannedRequestTO)
def userScanned(request):
    from rogerthat.rpc import users
    app_id = users.get_current_app_id()
    app_user = create_app_user(users.User(request.email), request.app_id)
    service_identity_user = add_slash_default(users.User(request.service_email))

    if app_id == request.app_id:
        should_make_friends = True
    else:
        si = get_service_identity(service_identity_user)
        bizz_check(si, "ServiceIdentity %s not found" % service_identity_user)
        should_make_friends = request.app_id in si.appIds

    if should_make_friends:
        try_or_defer(makeFriends, app_user, service_identity_user, original_invitee=None, servicetag=None, origin=None,
                     notify_invitee=False, notify_invitor=False, user_data=None)

    return UserScannedResponseTO()
