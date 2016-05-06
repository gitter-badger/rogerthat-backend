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
import hashlib
import itertools
import json
import logging
import threading
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from types import NoneType

from google.appengine.api import memcache, images, search
from google.appengine.ext import db, deferred

from mcfw.cache import cached
from mcfw.rpc import returns, arguments, serialize_complex_value
from mcfw.utils import normalize_search_string
from rogerthat import consts
from rogerthat.bizz import log_analysis
from rogerthat.bizz.i18n import get_translator
from rogerthat.bizz.job import clear_service_inbox
from rogerthat.bizz.location import get_friend_location
from rogerthat.bizz.messaging import sendMessage, dashboardNotification
from rogerthat.capi.friends import becameFriends, updateGroups
from rogerthat.consts import MC_DASHBOARD
from rogerthat.consts import WEEK, MC_RESERVED_TAG_PREFIX
from rogerthat.dal import parent_key, parent_key_unsafe
from rogerthat.dal.app import get_app_by_id, get_app_name_by_id, get_app_by_user
from rogerthat.dal.friend import get_friends_map, get_friends_friends_maps, get_friend_invitation_history, \
    get_do_send_email_invitations
from rogerthat.dal.location import get_user_location
from rogerthat.dal.profile import get_profile_info, get_user_profile, is_service_identity_user, get_service_profile, \
    get_profile_infos, are_service_identity_users, get_user_profiles
from rogerthat.dal.roles import list_service_roles_by_type
from rogerthat.dal.service import get_friend_serviceidentity_connection, get_service_identity, \
    get_friend_service_identity_connections_of_service_identity_query, \
    get_broadcast_audience_of_service_identity_keys_query, \
    get_friend_service_identity_connections_of_service_identity_keys_query
from rogerthat.models import ProfileInfo, ServiceProfile, UserData, FriendServiceIdentityConnection, ServiceRole, \
    FriendInvitationHistory, ServiceTranslation, UserInvitationSecret, UserProfile, Message, ServiceIdentity, \
    ServiceInteractionDef, App, Group, BroadcastSettingsFlowCache, ProfilePointer, FriendMap
from rogerthat.models.properties.friend import FriendDetail
from rogerthat.models.properties.keyvalue import KVStore
from rogerthat.rpc import users
from rogerthat.rpc.models import RpcCAPICall, ServiceAPICallback, Mobile
from rogerthat.rpc.rpc import mapping, logError, SKIP_ACCOUNTS
from rogerthat.rpc.service import ServiceApiException, logServiceError
from rogerthat.service.api.friends import invited, is_in_roles
from rogerthat.settings import get_server_settings
from rogerthat.templates import render
from rogerthat.to.friends import UpdateFriendResponseTO, UpdateFriendRequestTO, FriendTO, FriendRelationTO, \
    BecameFriendsRequestTO, BecameFriendsResponseTO, ServiceFriendStatusTO, SubscribedBroadcastUsersTO, BroadcastFriendTO, \
    UpdateFriendSetResponseTO, GroupTO, UpdateGroupsResponseTO, UpdateGroupsRequestTO, FindFriendResponseTO, \
    FindFriendItemTO, SubscribedBroadcastReachTO
from rogerthat.to.location import GetLocationRequestTO
from rogerthat.to.messaging import ButtonTO, UserMemberTO
from rogerthat.to.roles import RoleTO
from rogerthat.to.service import UserDetailsTO, ServiceInteractionDefTO
from rogerthat.translations import localize, DEFAULT_LANGUAGE
from rogerthat.utils import channel, now, runeach, ed, azzert, foreach, base65, slog, is_clean_app_user_email, \
    try_or_defer, bizz_check, send_mail_via_mime, base38
from rogerthat.utils.app import get_app_user_tuple, get_app_id_from_app_user, get_human_user_from_app_user, \
    create_app_user, remove_app_id, create_app_user_by_email, get_app_user_tuple_by_email
from rogerthat.utils.crypto import sha256
from rogerthat.utils.service import get_service_identity_tuple, remove_slash_default, add_slash_default, \
    get_service_user_from_service_identity_user, create_service_identity_user
from rogerthat.utils.transactions import on_trans_committed

ACCEPT_ID = u"accepted"
ACCEPT_AND_CONNECT_ID = u"accept_and_connect"
DECLINE_ID = u"decline"

ESTABLISHED = u"established"
INVITE_ID = u"invite"
BEACON_DISCOVERY = u"%s.beacon_discovery" % MC_RESERVED_TAG_PREFIX
FRIEND_INVITATION_REQUEST = u"fir"
FRIEND_SHARE_SERVICE_REQUEST = u"fssr"
REQUEST_LOCATION_SHARING = u"rls"
INVITE_SERVICE_ADMIN = u"isa"
UPDATE_PROFILE = u"up"
FRIEND_ACCEPT_FAILED = u"faf"
INVITE_FACEBOOK_FRIEND = u"iff"

ORIGIN_USER_POKE = u"user_poke"
ORIGIN_SERVICE_INVITE = u"service_invite"
ORIGIN_USER_INVITE = u"user_invite"
ORIGIN_USER_RECOMMENDED = u"user_recommended"
ORIGIN_YSAAA = u"your_service_as_an_app"
ORIGIN_BEACON_DETECTED = u"beacon_detected"

ACTOR_TYPE_INVITOR = u"invitor"
ACTOR_TYPE_INVITEE = u"invitee"

REGISTRATION_ORIGIN_DEFAULT = u'default'
REGISTRATION_ORIGIN_QR = u'qr'

@returns([ButtonTO])
@arguments(language=unicode, accept_ui_flag=int)
def create_accept_decline_buttons(language, accept_ui_flag=0):
    buttons = list()

    button = ButtonTO()
    button.id = ACCEPT_ID
    button.caption = localize(language, "Accept invitation")
    button.action = None
    button.ui_flags = accept_ui_flag
    buttons.append(button)

    button = ButtonTO()
    button.id = DECLINE_ID
    button.caption = localize(language, "Decline invitation")
    button.action = None
    button.ui_flags = 0
    buttons.append(button)

    return buttons

@returns([ButtonTO])
@arguments(language=unicode)
def create_add_to_services_button(language):
    buttons = list()

    button = ButtonTO()
    button.id = ACCEPT_ID
    button.caption = localize(language, "Add to my services")
    button.action = None
    button.ui_flags = 0
    buttons.append(button)

    return buttons

UNIT_TEST_REFS = dict()

class PersonInvitationOverloadException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_FRIEND + 2,
                                     "Person was already invited three times.")

class PersonAlreadyInvitedThisWeekException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_FRIEND + 1,
                                     "This person was already invited in the last week.")

class InvalidEmailAddressException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_FRIEND + 0,
                                     "Invalid email address.")

class CannotSelfInviteException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_FRIEND + 3,
                                     "Can not invite myself.")

class DoesNotWantToBeInvitedViaEmail(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_FRIEND + 4,
                                     "This person does not want to be invited anymore via email.")

class CanNotRequestLocationFromServices(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_FRIEND + 5,
                                     "Cannot request location from service users.")

class UserNotFoundViaUserCode(ServiceApiException):
    def __init__(self, user_code):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_FRIEND + 6,
                                     "User not found via userCode", user_code=user_code)

class CanNotInviteFriendException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_FRIEND + 7,
                                     "This person is already your friend")

class CanNotInviteOtherServiceException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_FRIEND + 8,
                                     "Cannot invite services.")

@returns(NoneType)
@arguments(invitor_user=users.User, invitee_email=unicode, invitee_name=unicode, message=unicode, language=unicode, \
           servicetag=unicode, origin=unicode, app_id=unicode)
def invite(invitor_user, invitee_email, invitee_name, message, language, servicetag, origin, app_id):
    from rogerthat.bizz.service import valididate_app_id_for_service_identity_user
    # Basic validation checks
    if ':' in invitee_email:
        invitee_user, invitee_email_app_id = get_app_user_tuple_by_email(invitee_email)
        azzert(invitee_email_app_id == app_id, "Cannot invite user in other app")
        invitee_email = invitee_user.email()
    invitee, invitation_history, now_ = _validate_invitation(invitee_email, invitor_user, servicetag, app_id)
    # Check whether invitee is a nuntiuz user
    invitor_profile_info, invitee_profile_info = get_profile_infos([invitor_user, invitee], allow_none_in_results=True)

    if not invitee_profile_info:
        if not language:
            if invitor_profile_info:
                # Default to invitor language
                if invitor_profile_info.isServiceIdentity:
                    language = get_service_profile(invitor_profile_info.service_user).defaultLanguage
                else:
                    language = invitor_profile_info.language
            else:
                language = DEFAULT_LANGUAGE
        logging.info('sending invitation email to %s', invitee)
        _send_invitation_email(language, get_human_user_from_app_user(invitee).email(), invitor_user, invitee, invitation_history, now_, message, servicetag, origin)
        return

    if not invitee_profile_info.isServiceIdentity:
        # invitee is a human user. Send him an email
        if is_service_identity_user(invitor_user):
            valididate_app_id_for_service_identity_user(invitor_user, app_id)
        _send_invitation_message(servicetag, message, get_human_user_from_app_user(invitee).email(), invitor_user, invitee, invitation_history, now_, origin)
    else:
        # invitee is a service
        if is_service_identity_user(invitor_user):
            raise CanNotInviteOtherServiceException()

        azzert(get_app_id_from_app_user(invitor_user) == app_id)
        if "/" not in invitee.email():
            invitee = create_service_identity_user(invitee)
        valididate_app_id_for_service_identity_user(invitee, app_id)

        if not language:
            invitor_profile = get_user_profile(invitor_user)
            language = invitor_profile.language

        svc_user, identifier = get_service_identity_tuple(invitee)
        svc_profile = get_service_profile(svc_user)

        invitor_user_profile = get_user_profile(invitor_user)
        context = invited(invited_response_receiver, logServiceError, svc_profile,
                          email=get_human_user_from_app_user(invitor_user).email(), name=invitor_user_profile.name,
                          message=message, language=language, tag=servicetag, origin=origin,
                          service_identity=identifier,
                          user_details=[UserDetailsTO.fromUserProfile(invitor_user_profile)],
                          DO_NOT_SAVE_RPCCALL_OBJECTS=True)
        if context:  # None if friend.invited is not implemented
            context.invitor = invitor_user
            context.invitee = invitee
            context.servicetag = servicetag
            context.origin = origin
            context.put()
        else:
            deferred.defer(process_invited_response, svc_user, invitee, identifier, invitor_user, invitee, servicetag, \
                           origin, False, None, None)
        UNIT_TEST_REFS["invited"] = context


@returns(bool)
@arguments(profile1=ProfileInfo, profile2=ProfileInfo)
def areFriends(profile1, profile2):
    """Checks wether profile1 is connected to profile2 and profile2 is connected to profile1"""
    def check(p1, p2):
        if p1.isServiceIdentity:
            return not get_friend_serviceidentity_connection(p2.user, p1.user) is None
        else:
            friend_map = get_friends_map(p1.user)
            return friend_map and remove_slash_default(p2.user) in friend_map.friends

    return check(profile1, profile2) and check(profile2, profile1)


@returns(bool)
@arguments(profile_info1=ProfileInfo, profile_info2=ProfileInfo)
def canBeFriends(profile_info1, profile_info2):
    if profile_info1.isServiceIdentity:
        if profile_info2.isServiceIdentity:
            return False
        else:
            return get_app_id_from_app_user(profile_info2.user) in profile_info1.appIds

    if profile_info2.isServiceIdentity:
        return get_app_id_from_app_user(profile_info1.user) in profile_info2.appIds

    return get_app_id_from_app_user(profile_info1.user) == get_app_id_from_app_user(profile_info2.user)


@returns()
@arguments(app_user=users.User, service_profile=ServiceProfile, identifier=unicode, user_details=[UserDetailsTO],
           roles=[RoleTO], make_friends_if_in_role=bool)
def send_is_in_roles(app_user, service_profile, identifier, user_details, roles, make_friends_if_in_role=False):
    def trans():
        context = is_in_roles(is_in_roles_response_receiver, logServiceError, service_profile,
                              service_identity=identifier, user_details=user_details, roles=roles,
                              DO_NOT_SAVE_RPCCALL_OBJECTS=True)
        if context is not None:  # None if friend.is_in_roles not implemented
            context.human_user = app_user
            context.role_ids = [r.id for r in roles]
            context.make_friends_if_in_role = make_friends_if_in_role
            context.put()

    if roles:
        if db.is_in_transaction():
            trans()
        else:
            db.run_in_transaction(trans)


@returns(NoneType)
@arguments(invitor=users.User, invitee=users.User, original_invitee=users.User, servicetag=unicode, origin=unicode,
           notify_invitee=bool, notify_invitor=bool, user_data=unicode)
def makeFriends(invitor, invitee, original_invitee, servicetag, origin, notify_invitee=False, notify_invitor=True,
                user_data=None):
    """ Make friends between invitor and invitee. They can be both human users, or one can be a service_identity_user
        Although we are in the bizz layer, it is possible that the /+default+ suffix is not included! """
    from rogerthat.bizz.profile import schedule_re_index

    def notifyActorInWebUI(from_, to, actor, to_friendDetail):
        if to_friendDetail.type == FriendDetail.TYPE_USER:
            friendMap = get_friends_map(to)
            friends_of_friend = serialize_complex_value(
                [FriendRelationTO.fromDBFriendDetail(fd) for fd in friendMap.friendDetails.values()],
                FriendRelationTO, True)
        else:
            friends_of_friend = []

        # Send update request over channel API
        friend_dict = serialize_complex_value(FriendTO.fromDBFriendDetail(to_friendDetail, False, True, targetUser=from_), FriendTO, False)
        if to_friendDetail.type == FriendDetail.TYPE_SERVICE:
            # Preventing "InvalidMessageError: Message must be no longer than 32767 chars"
            del friend_dict['appData']
            del friend_dict['userData']

        channel.send_message(
            from_,
            u'rogerthat.friend.ackInvitation',
            actor=actor,
            friend=friend_dict,
            friends=friends_of_friend)

    def run(from_profile_info, to_profile_info, to_name, to_shareContacts, from_, to, actor_type):
        notifyFriends = None
        side_effects = list()
        to = remove_slash_default(to)
        if not from_profile_info.isServiceIdentity:
            # from_ is a human
            # to is a human or service
            friendMap = get_friends_map(from_)
            friendMap.friends.append(to)
            friendMap.friends = list(set(friendMap.friends))
            if to_profile_info:
                profile_type = FriendDetail.TYPE_SERVICE if to_profile_info.isServiceIdentity else FriendDetail.TYPE_USER
                if to_profile_info.isServiceIdentity and user_data is not None:
                    try:
                        data_object = json.loads(user_data)
                    except:
                        logging.warn("Invalid user data JSON string!", exc_info=True)
                        has_user_data = False
                    else:
                        user_data_model_key = UserData.createKey(from_, to_profile_info.user)
                        user_data_model = UserData(key=user_data_model_key)
                        user_data_model.data = None
                        user_data_model.userData = KVStore(user_data_model_key)
                        user_data_model.userData.from_json_dict(data_object)
                        user_data_model.put()
                        has_user_data = True
                else:
                    has_user_data = False
                to_friendDetail = friendMap.friendDetails.addNew(to, to_name, to_profile_info.avatarId, False, False,
                                                                 to_shareContacts, profile_type, has_user_data)
            else:
                to_friendDetail = friendMap.friendDetails.addNew(to, to_name, -1, False, False, to_shareContacts,
                                                                 FriendDetail.TYPE_USER)
            friendMap.generation += 1
            friendMap.version += 1  # version of the set of friend e-mails
            friendMap.put()
            side_effects.append(lambda: notifyActorInWebUI(from_, to, actor_type, to_friendDetail))
            side_effects.append(lambda: _defer_update_friend(friendMap, to, UpdateFriendRequestTO.STATUS_ADD))
            if not to_profile_info.isServiceIdentity:
                notifyFriends = (from_, to, friendMap, to_friendDetail)  # both from and to are human users
            schedule_re_index(from_)
        else:
            # from_ is a service
            # to is a human
            from_ = add_slash_default(from_)

            @db.non_transactional()
            def get_broadcast_types():
                return get_service_profile(get_service_user_from_service_identity_user(from_)).broadcastTypes or list()

            FriendServiceIdentityConnection.createFriendServiceIdentityConnection(to, to_profile_info.name, to_profile_info.avatarId, from_, get_broadcast_types(), to_profile_info.birthdate, to_profile_info.gender, to_profile_info.app_id).put()

            svc_user, identifier = get_service_identity_tuple(from_)
            svc_profile = get_service_profile(svc_user)
            user_details = [UserDetailsTO.fromUserProfile(to_profile_info)]
            if actor_type == ACTOR_TYPE_INVITOR:
                from rogerthat.service.api.friends import invite_result
                side_effects.append(lambda: invite_result(invite_result_response_receiver, logServiceError, svc_profile,
                                                          email=get_human_user_from_app_user(to).email(),
                                                          result=ACCEPT_ID, tag=servicetag, origin=origin,
                                                          service_identity=identifier, user_details=user_details))

            unknown_synced_roles = [r for r in list_service_roles_by_type(svc_user, ServiceRole.TYPE_SYNCED)
                                    if not to_profile_info.has_role(from_, u'sr:%s' % r.role_id)]
            if unknown_synced_roles:
                on_trans_committed(send_is_in_roles, to, svc_profile, identifier, user_details,
                                   map(RoleTO.fromServiceRole, unknown_synced_roles))

            on_trans_committed(slog, msg_="Service user gained", function_=log_analysis.SERVICE_STATS, service=from_.email(), tag=to.email(), type_=log_analysis.SERVICE_STATS_TYPE_GAINED)
        db.delete(FriendInvitationHistory.createKey(from_profile_info.user, to_profile_info.user))
        return side_effects, notifyFriends  # notifyFriends is None, or from_ and to are BOTH humans !

    def translate_service_identity_name(service_identity, target_user_profile):
        translator = get_translator(service_identity.service_user, [ServiceTranslation.IDENTITY_TEXT], target_user_profile.language)
        return translator.translate(ServiceTranslation.IDENTITY_TEXT, service_identity.name, target_user_profile.language)


    logging.info("Storing accepted friend connection from %s to %s" % (invitor, invitee))
    invitee_profile_info, invitor_profile_info = get_profile_infos([invitee, invitor])
    if invitor_profile_info.isServiceIdentity:
        myShareContacts = False
        invitor_name = translate_service_identity_name(invitor_profile_info, invitee_profile_info)
    else:
        myShareContacts = get_friends_map(invitor).shareContacts
        invitor_name = invitor_profile_info.name
    if invitee_profile_info.isServiceIdentity:
        hisShareContacts = False
        invitee_name = translate_service_identity_name(invitee_profile_info, invitor_profile_info)
    else:
        hisShareContacts = get_friends_map(invitee).shareContacts
        invitee_name = invitee_profile_info.name

    def go():
        bizz_check(canBeFriends(invitee_profile_info, invitor_profile_info),
                   "%s and %s can not be friends" % (invitee_profile_info.user, invitor_profile_info.user))
        if not areFriends(invitee_profile_info, invitor_profile_info):
            runMeResult = run(invitor_profile_info, invitee_profile_info, invitee_name, hisShareContacts, invitor, invitee, ACTOR_TYPE_INVITOR)
            runHimResult = run(invitee_profile_info, invitor_profile_info, invitor_name, myShareContacts, invitee, invitor, ACTOR_TYPE_INVITEE)
        else:
            runMeResult = runHimResult = [[], False]

        return runMeResult, runHimResult

    xg_on = db.create_transaction_options(xg=True)
    runMeResult, runHimResult = go() if db.is_in_transaction() else db.run_in_transaction_options(xg_on, go)
    runeach(itertools.chain(runMeResult[0], runHimResult[0]))

    # Delete invitation history
    if original_invitee:
        db.delete(FriendInvitationHistory.createKey(invitor, original_invitee))
    deferred.defer(_notify_users, invitor_profile_info, invitor, invitee_profile_info, invitee, notify_invitee, notify_invitor, (runMeResult[1], runHimResult[1]), _transactional=db.is_in_transaction(), _countdown=5)

@returns(NoneType)
@arguments(human_invitor_user=users.User, secret=unicode, phone_number=unicode, email_address=unicode, timestamp=int)
def log_invitation_secret_sent(human_invitor_user, secret, phone_number, email_address, timestamp):
    def trans():
        uis = UserInvitationSecret.get_by_id(base65.decode_int(secret), parent=parent_key(human_invitor_user))
        uis.sent_timestamp = timestamp
        uis.phone_number = phone_number
        uis.email_address = email_address
        uis.put()
    db.run_in_transaction(trans)

@returns(NoneType)
@arguments(invitee_user=users.User, invitor_user=users.User, secret=unicode)
def ack_invitation_by_invitation_secret(invitee_user, invitor_user, secret):
    if invitee_user == invitor_user:
        logging.info("%s clicked his own invitation link" % invitee_user.email())
        return

    invitee_profile_info, invitor_profile_info = get_profile_infos([invitee_user, invitor_user], expected_types=[UserProfile, ProfileInfo])

    invitee_friend_map = get_friends_map(invitee_user)
    if remove_slash_default(invitor_user) in invitee_friend_map.friends:
        logging.info("%s and %s are already friends!" % (invitee_user.email(), invitor_user.email()))
        name = invitor_profile_info.name
        msg = localize(invitee_profile_info.language, "You are already connected with %(name)s.", name=name)
        dashboardNotification(invitee_user, msg)
        return

    try:
        def trans():
            invitation_secret = UserInvitationSecret.get_by_id(base65.decode_int(secret),
                                                               parent=parent_key_unsafe(remove_slash_default(invitor_user)))
            azzert(invitation_secret, "Invitation secret not found")
            azzert(invitation_secret.status in (UserInvitationSecret.STATUS_CREATED, UserInvitationSecret.STATUS_SENT, UserInvitationSecret.STATUS_REDIRECTED), "Invitation secret not found")
            invitation_secret.status = UserInvitationSecret.STATUS_USED
            invitation_secret.used_timestamp = now()
            invitation_secret.used_for_user = invitee_user
            invitation_secret.put()
            makeFriends(invitor_user, invitee_user, invitation_secret.email, invitation_secret.service_tag, origin=invitation_secret.origin, notify_invitee=True)
        xg_on = db.create_transaction_options(xg=True)
        db.run_in_transaction_options(xg_on, trans)
    except AssertionError:
        logging.exception("Failed to accept a secret based invitation.")
        invitation_secret = UserInvitationSecret.get_by_id(base65.decode_int(secret),
                                                           parent=parent_key_unsafe(remove_slash_default(invitor_user)))
        def trans():
            button = ButtonTO()
            button.id = INVITE_ID
            button.caption = localize(invitee_profile_info.language, "Invite %(name)s", name=invitor_profile_info.name)
            button.action = None
            button.ui_flags = 0
            msg = localize(invitee_profile_info.language, "_friendship_request_failed", name=invitee_profile_info.name, friend_name=invitor_profile_info.name)
            message = sendMessage(MC_DASHBOARD, [UserMemberTO(invitee_user)], Message.FLAG_ALLOW_DISMISS, 0, None, msg,
                                  [button], None, get_app_by_user(invitee_user).core_branding_hash,
                                  FRIEND_ACCEPT_FAILED, is_mfr=False)
            message.invitor = invitee_user
            message.invitee = invitor_user
            message.service_tag = invitation_secret.service_tag if invitation_secret else None
            message.origin = invitation_secret.origin if invitation_secret else ORIGIN_USER_INVITE
            message.put()
        xg_on = db.create_transaction_options(xg=True)
        db.run_in_transaction_options(xg_on, trans)

@returns(NoneType)
@arguments(message=Message)
def ackInvitation(message):
    azzert(message.tag == FRIEND_INVITATION_REQUEST or message.tag == BEACON_DISCOVERY)
    invitor = message.invitor
    invitee = message.invitee
    origin = getattr(message, "origin", ORIGIN_USER_INVITE)
    servicetag = getattr(message, "servicetag", None)
    if message.memberStatusses[message.members.index(invitee)].button_index != message.buttons[ACCEPT_ID].index:
        if is_service_identity_user(invitor):
            svc_user, identifier = get_service_identity_tuple(add_slash_default(invitor))  # for old invites by services
            invitor_profile = get_service_profile(svc_user)
            from rogerthat.service.api.friends import invite_result
            invite_result(invite_result_response_receiver, logServiceError, invitor_profile, email=None,
                          result=DECLINE_ID, tag=servicetag, origin=origin, service_identity=identifier,
                          user_details=[UserDetailsTO.fromUserProfile(get_user_profile(invitee))])
        return

    makeFriends(invitor, invitee, invitee, servicetag, origin=origin)


@returns(NoneType)
@arguments(user=users.User, friend=users.User, enabled=bool)
def shareLocation(user, friend, enabled):
    def runMe():
        myFriendMap = get_friends_map(user)
        friendDetail = myFriendMap.friendDetails[friend.email()]
        friendDetail.shareLocation = enabled
        friendDetail.relationVersion += 1
        myFriendMap.generation += 1
        myFriendMap.put()
        userLocation = get_user_location(user)
        if userLocation.members:
            if enabled and not friend in userLocation.members:
                userLocation.members.append(friend)
                userLocation.put()
            elif not enabled and friend in userLocation.members:
                userLocation.members.remove(friend)
                userLocation.put()
        def updateMyWeb():
            channel.send_message(
                user,
                u'rogerthat.friend.shareLocationUpdate',
                friend=serialize_complex_value(FriendTO.fromDBFriendDetail(friendDetail), FriendTO, False))
        return (myFriendMap, friend, [updateMyWeb])

    def runHim():
        hisFriendMap = get_friends_map(friend)
        friendDetail = hisFriendMap.friendDetails[user.email()]
        friendDetail.sharesLocation = enabled
        friendDetail.relationVersion += 1
        hisFriendMap.generation += 1
        hisFriendMap.put()
        def updateWebOfFriend():
            channel.send_message(
                friend,
                u'rogerthat.friend.shareLocation',
                friend=serialize_complex_value(FriendTO.fromDBFriendDetail(friendDetail), FriendTO, False))
        return (hisFriendMap, user, [updateWebOfFriend])

    friendmap = get_friends_map(user)

    if not friend in friendmap.friends:
        logging.warning("ShareLocation performed to a non friend user!")
        return

    for friendMap, f, functions in [db.run_in_transaction(runMe), db.run_in_transaction(runHim)]:
        _defer_update_friend(friendMap, f, UpdateFriendRequestTO.STATUS_MODIFIED)
        for func in functions:
            func()

@returns(NoneType)
@arguments(user=users.User, friend=users.User, message=unicode)
def requestLocationSharing(user, friend, message):
    myFriendMap = get_friends_map(user)
    if not friend in myFriendMap.friends or myFriendMap.friendDetails[friend.email()].sharesLocation:
        logging.warning("RequestShareLocation performed to a non friend user!")
        return

    friend_profile, user_profile = get_profile_infos([friend, user], expected_types=[UserProfile, UserProfile])

    devices = list()
    if friend_profile.mobiles:
        for mob in friend_profile.mobiles:
            if mob.type_ in (Mobile.TYPE_ANDROID_HTTP, Mobile.TYPE_IPHONE_HTTP_APNS_KICK,
                             Mobile.TYPE_IPHONE_HTTP_XMPP_KICK, Mobile.TYPE_LEGACY_IPHONE_XMPP,
                             Mobile.TYPE_WINDOWS_PHONE):
                devices.append(mob)
    name = _get_full_name(user)
    if devices:
        m = localize(friend_profile.language, "User %(name)s has requested to share your location.", name=name)
        if message:
            m += "\n" + localize(friend_profile.language, "%(name)s added a personal note:\n%(message)s", name=name,
                          message=message)
        message = sendMessage(MC_DASHBOARD, [UserMemberTO(friend)], Message.FLAG_AUTO_LOCK, 0, None, m,
                              create_accept_decline_buttons(friend_profile.language,
                                                            Message.UI_FLAG_AUTHORIZE_LOCATION), None,
                              get_app_by_user(friend).core_branding_hash,
                              REQUEST_LOCATION_SHARING, is_mfr=False)
        message.invitor = user
        message.invitee = friend
        message.put()
    else:
        m = localize(user_profile.language, "%(name)s does not have a device which supports location tracking.",
                     name=name)
        sendMessage(MC_DASHBOARD, [UserMemberTO(user)], Message.FLAG_AUTO_LOCK | Message.FLAG_ALLOW_DISMISS, 0, None,
                    m, [], None, get_app_by_user(user).core_branding_hash, None, is_mfr=False)

@returns(NoneType)
@arguments(message=Message)
def ackRequestLocationSharing(message):
    azzert(message.tag == REQUEST_LOCATION_SHARING)
    user, friend = message.invitor, message.invitee
    user_profile, friend_profile = get_profile_infos([user, friend], expected_types=[UserProfile, UserProfile])
    if message.memberStatusses[message.members.index(message.invitee)].button_index != message.buttons[ACCEPT_ID].index:
        msg = localize(user_profile.language, "%(name)s declined your request to track his/her location.", name=friend_profile.name)
        dashboardNotification(user, msg)
        return

    def runMe():
        myFriendMap = get_friends_map(user)
        friendDetail = myFriendMap.friendDetails[friend.email()]
        friendDetail.sharesLocation = True
        friendDetail.relationVersion += 1
        myFriendMap.generation += 1
        myFriendMap.put()
        def updateWebOfInvitor():
            channel.send_message(
                user,
                u'rogerthat.friend.ackRequestLocationSharing',
                friend=serialize_complex_value(FriendTO.fromDBFriendDetail(friendDetail), FriendTO, False))
        return (myFriendMap, friend, [updateWebOfInvitor])

    def runHim():
        hisFriendMap = get_friends_map(friend)
        friendDetail = hisFriendMap.friendDetails[user.email()]
        friendDetail.shareLocation = True
        friendDetail.relationVersion += 1
        hisFriendMap.generation += 1
        hisFriendMap.put()
        def updateWebOfInvitee():
            channel.send_message(
                user,
                u'rogerthat.friend.ackRequestLocationSharingUpdate',
                friend=serialize_complex_value(FriendTO.fromDBFriendDetail(friendDetail), FriendTO, False))
        return (hisFriendMap, user, [updateWebOfInvitee])


    def trans():
        results = list()
        results.append(runMe())
        results.append(runHim())
        deferred.defer(_get_friend_location, user, friend, _transactional=True)
        return results

    xg_on = db.create_transaction_options(xg=True)
    for friendMap, f, functions in db.run_in_transaction_options(xg_on, trans):
        _defer_update_friend(friendMap, f, UpdateFriendRequestTO.STATUS_MODIFIED)
        for func in functions:
            func()

@returns(NoneType)
@arguments(user=users.User, service_identity_user=users.User, recipient_user=users.User)
def share_service_identity(user, service_identity_user, recipient_user):

    if not is_clean_app_user_email(recipient_user):
        logging.warn('Unclean recipient email address in share svc - invitor %s - recipient %s - svcid %s' %
                     (user, recipient_user, service_identity_user))
        return

    user_profile, service_identity, recipient_profile = get_profile_infos([user, service_identity_user, recipient_user], allow_none_in_results=True,
                                                                          expected_types=[UserProfile, ServiceIdentity, UserProfile])

    azzert(user_profile)
    azzert(service_identity)
    azzert(service_identity.shareEnabled)

    if not recipient_profile:
        sid = ServiceInteractionDef.get(service_identity.shareSIDKey)
        share_url = ServiceInteractionDefTO.emailUrl(sid)
        deferred.defer(_send_recommendation_email, user_profile.language, user_profile.name, get_human_user_from_app_user(user).email(),
                       get_human_user_from_app_user(recipient_user).email(), service_identity.name, share_url, get_app_id_from_app_user(user))
        slog(msg_="Recommend via email", function_=log_analysis.SERVICE_STATS, service=service_identity_user.email(), tag=log_analysis.SERVICE_STATS_TYPE_RECOMMEND_VIA_EMAIL, type_=log_analysis.SERVICE_STATS_TYPE_RECOMMEND_VIA_EMAIL)
        return
    # Share service via Rogerthat
    if get_friend_serviceidentity_connection(recipient_user, service_identity_user):
        logging.info("Recipient (%s) is already connected to the recommended service (%s)", recipient_user.email(),
                     service_identity_user.email())
        slog(msg_="Recommend via rogerthat (2)", function_=log_analysis.SERVICE_STATS,
             service=service_identity_user.email(), tag=log_analysis.SERVICE_STATS_TYPE_RECOMMEND_VIA_ROGERTHAT,
             type_=log_analysis.SERVICE_STATS_TYPE_RECOMMEND_VIA_ROGERTHAT)
    else:
        deferred.defer(_send_recommendation_message, recipient_profile.language, user, user_profile.name, service_identity_user,
                       service_identity, recipient_user)
        slog(msg_="Recommend via rogerthat", function_=log_analysis.SERVICE_STATS, service=service_identity_user.email(), tag=log_analysis.SERVICE_STATS_TYPE_RECOMMEND_VIA_ROGERTHAT, type_=log_analysis.SERVICE_STATS_TYPE_RECOMMEND_VIA_ROGERTHAT)

@arguments(language=unicode, from_name=unicode, from_email=unicode, to_email=unicode, service_name=unicode, share_url=unicode, app_id=unicode)
def _send_recommendation_email(language, from_name, from_email, to_email, service_name, share_url, app_id=App.APP_ID_ROGERTHAT):
    app = get_app_by_id(app_id)
    subject = localize(language, "%(user_name)s recommends you to connect to %(service_name)s on %(app_name)s.",
                       user_name=from_name, service_name=service_name, app_name=app.name)
    variables = dict(consts=consts, from_name=from_name, share_url=share_url, service_name=service_name, app_id=app_id,
                     app_name=app.name)
    body = render("recommend_service_email", [language], variables)
    html = render("recommend_service_email_html", [language], variables)

    if app.is_default:
        dashboard_email_address = get_server_settings().senderEmail
    else:
        dashboard_email_address = ("%s <%s>" % (app.name, app.dashboard_email_address))

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = dashboard_email_address
    msg['To'] = to_email
    msg.add_header('reply-to', from_email)
    msg.attach(MIMEText(body.encode('utf-8'), 'plain', 'utf-8'))
    msg.attach(MIMEText(html.encode('utf-8'), 'html', 'utf-8'))
    send_mail_via_mime(dashboard_email_address, to_email, msg)

@arguments(language=unicode, from_=users.User, from_name=unicode, service_identity_user=users.User,
           service_identity=ServiceIdentity, to=users.User)
def _send_recommendation_message(language, from_, from_name, service_identity_user, service_identity, to):
    app_name = get_app_name_by_id(get_app_id_from_app_user(from_))
    m = localize(language, "%(user_name)s recommends you to connect to %(service_name)s on %(app_name)s.\n\nAbout %(service_name)s:\n%(service_description)s",
                 user_name=from_name, service_name=service_identity.name,
                 service_description=service_identity.description, app_name=app_name)
    message = sendMessage(MC_DASHBOARD, [UserMemberTO(to)], Message.FLAG_AUTO_LOCK, 0, None, m,
                          create_accept_decline_buttons(language), None, get_app_by_user(to).core_branding_hash,
                          FRIEND_SHARE_SERVICE_REQUEST, is_mfr=False)
    message.invitor = from_
    message.invitee = to
    message.recommended_service = service_identity_user
    db.put(message)

@returns(NoneType)
@arguments(message=Message)
def ack_share_service(message):
    azzert(message.tag == FRIEND_SHARE_SERVICE_REQUEST)
    service_identity_user = add_slash_default(message.recommended_service)  # for old recommendation before migration
    invitee = message.invitee
    # If the invitee accepts the recommendation, then we somehow reverse roles, and the invitee invites the service
    # This means that the invitee is now an invitor
    if message.memberStatusses[message.members.index(invitee)].button_index == message.buttons[ACCEPT_ID].index:
        invite(invitee, service_identity_user.email(), get_service_identity(service_identity_user).name, None, None, None, ORIGIN_USER_RECOMMENDED, get_app_id_from_app_user(invitee))


@mapping('com.mobicage.capi.friends.update_friend_response')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=UpdateFriendResponseTO)
def update_friend_response(context, result):
    if result.updated is False and hasattr(context, 'update_status'):
        logging.warn("The updateFriend call was not processed by the phone.\nReason: %s", result.reason)


@mapping('com.mobicage.capi.friends.update_friend_set_response')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=UpdateFriendSetResponseTO)
def update_friend_set_response(context, result):
    if result.updated is False:
        logging.warn("The updateFriendSet call was not processed by the phone.\nReason: %s", result.reason)


@mapping('com.mobicage.capi.friends.became_friends_response')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=BecameFriendsResponseTO)
def became_friends_response(context, result):
    pass

@mapping('com.mobicage.capi.friends.update_groups_response')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=UpdateGroupsResponseTO)
def update_groups_response(context, result):
    pass

@returns(NoneType)
@arguments(user1=users.User, user2=users.User, current_mobile=Mobile)
def breakFriendShip(user1, user2, current_mobile=None):
    """ Break friendship between invitor and invitee. They can be both human users, or one can be a service_identity_user
        Although we are in the bizz layer, it is possible that the /+default+ suffix is not included! """
    from rogerthat.bizz.profile import schedule_re_index
    def removeShareLocationAccess(user, friend):
        userLocation = get_user_location(user)
        if userLocation.members and friend in userLocation.members:
            if friend in userLocation.members:
                userLocation.members.remove(friend)
                userLocation.put()

    def updateWeb(from_, to, friendDetail):
        # Send update request over channel API
        friend_dict = serialize_complex_value(FriendTO.fromDBFriendDetail(friendDetail), FriendTO, False)
        if friendDetail.type == FriendDetail.TYPE_SERVICE:
            # Preventing "InvalidMessageError: Message must be no longer than 32767 chars"
            del friend_dict['appData']
            del friend_dict['userData']
        channel.send_message(
            from_,
            u'rogerthat.friend.breakFriendShip',
            friend=friend_dict)

    def run(from_, to, initiator, from_is_service_identity, to_is_service_identity, current_mobile):
        to = remove_slash_default(to)
        email = to.email()  # possibly with ":<app id>" or "/<service identifier>"
        if not from_is_service_identity:
            removeShareLocationAccess(from_, to)
            friendMap = get_friends_map(from_)
            friend_map_updated = False
            if to in friendMap.friends:
                friendMap.friends.remove(to)
                friend_map_updated = True
            if email in friendMap.friendDetails:
                friendDetail = friendMap.friendDetails[email]
                if friendDetail.type == FriendDetail.TYPE_SERVICE and friendDetail.hasUserData:
                    db.delete(UserData.createKey(from_, add_slash_default(to)))
                friendMap.friendDetails.remove(email)
                friend_map_updated = True

                if to_is_service_identity:
                    # revoke all service roles for this service identity
                    service_identity_user = add_slash_default(to)
                    user_profile = get_user_profile(from_)
                    roles = user_profile.grants.get(service_identity_user.email(), list())
                    service_roles = [r for r in roles if r.startswith('sr:')]
                    if service_roles:
                        for sr in service_roles:
                            logging.debug("Revoking role %s of %s for %s", sr, service_identity_user, from_)
                            user_profile.revoke_role(service_identity_user, sr)
                        user_profile.put()

                        from rogerthat.bizz.roles import _send_service_role_grants_updates
                        on_trans_committed(_send_service_role_grants_updates,
                                           get_service_user_from_service_identity_user(service_identity_user))

                def side_effects():
                    from rogerthat.bizz.job.update_friends import _do_update_friend_request
                    yield lambda: updateWeb(from_, to, friendDetail)
                    yield lambda: deferred.defer(_do_update_friend_request, from_, friendDetail,
                                                 UpdateFriendRequestTO.STATUS_DELETE, friendMap,
                                                 extra_conversion_kwargs=dict(existence=FriendTO.FRIEND_EXISTENCE_DELETED))

                    if not to_is_service_identity:
                        found_member_in_groups = False

                        for g in Group.gql("WHERE ANCESTOR IS :1 and members = :2", parent_key(from_), to.email()):
                            found_member_in_groups = True
                            g.members.remove(to.email())
                            if len(g.members) == 0:
                                g.delete()
                            else:
                                g.put()

                        if found_member_in_groups:
                            extra_kwargs = dict()
                            if current_mobile is not None and from_ == initiator:
                                extra_kwargs[SKIP_ACCOUNTS] = [current_mobile.account]
                            yield lambda: updateGroups(update_groups_response, logError, from_,
                                                       request=UpdateGroupsRequestTO(), **extra_kwargs)
            else:
                def side_effects():
                    yield lambda: None

            if friend_map_updated:
                friendMap.generation += 1
                friendMap.version += 1  # version of the set of friend e-mails
                friendMap.put()

            schedule_re_index(from_)
        else:
            # from_ is service identity user
            # to is human
            from_ = add_slash_default(from_)
            fsic_key = FriendServiceIdentityConnection.createKey(friend_user=to, service_identity_user=from_)
            if db.get(fsic_key):
                on_trans_committed(slog, msg_="Service user lost", function_=log_analysis.SERVICE_STATS,
                                   service=from_.email(), tag=to.email(), type_=log_analysis.SERVICE_STATS_TYPE_LOST)

            db.delete([fsic_key,
                       BroadcastSettingsFlowCache.create_key(to, from_)])
            clear_service_inbox.schedule(from_, to)
            def side_effects():
                if to == initiator:
                    from rogerthat.service.api.friends import broke_friendship
                    svc_user, identifier = get_service_identity_tuple(from_)
                    svc_profile = get_service_profile(svc_user)
                    yield lambda: broke_friendship(broke_friendship_response_receiver, logServiceError, svc_profile,
                                                   email=get_human_user_from_app_user(to).email(),
                                                   service_identity=identifier,
                                                   user_details=[UserDetailsTO.fromUserProfile(get_user_profile(to))])
            from rogerthat.bizz.beacon import remove_beacon_discovery
            on_trans_committed(remove_beacon_discovery, app_user=to, service_identity_user=from_)
        return side_effects()

    # are_service_identity_users barfs if there is no ProfileInfo for a certain user.
    # a ProfileInfo for user2 will definitely exist:
    # - if user1 uses the Rogerthat App or is a ServiceIdentity (user1 does not contain ':')
    # - if user2 contains ':' or '/'
    if ':' not in user1.email() or ':' in user2.email() or '/' in user2.email():
        try:
            user1_is_svc_identity, user2_is_svc_identity = are_service_identity_users([user1, user2])
        except AssertionError:
            logging.debug('Ignoring breakFriendship request. One of the users does not exist.', exc_info=1)
            return
    else:
        # there is a ':' in user1, and no ':' in user2, and no '/' in user2
        user1_is_svc_identity = False
        user2_is_svc_identity = is_service_identity_user(user2)
        if not user2_is_svc_identity:
            # user2 should be appended with the app_id of user1
            user2 = create_app_user(user2, get_app_id_from_app_user(user1))

    logging.debug("user1 (%s) is a %s", user1, 'ServiceIdentity' if user1_is_svc_identity else 'UserProfile')
    logging.debug("user2 (%s) is a %s", user2, 'ServiceIdentity' if user2_is_svc_identity else 'UserProfile')

    # every db.run_in_transaction will return a list of side effects
    # itertools.chain appends 2 generators to each other
    # runeach executes every returned side effect of the 2 transactions
    xg_on = db.create_transaction_options(xg=True)
    runeach(itertools.chain(db.run_in_transaction_options(xg_on, run, user1, user2, user1, user1_is_svc_identity, user2_is_svc_identity, current_mobile),
                            db.run_in_transaction_options(xg_on, run, user2, user1, user1, user2_is_svc_identity, user1_is_svc_identity, current_mobile)))

@returns(NoneType)
@arguments(user=users.User, enabled=bool)
def setShareContacts(user, enabled):
    friendMap = get_friends_map(user)
    friendMap.shareContacts = enabled
    friendMap.put()
    for friendMap in get_friends_friends_maps(user):
        try:
            friendMap.friendDetails[user.email()].sharesContacts = enabled
            friendMap.put()
        except KeyError:
            logging.error("friendMap of %s is inconsistant" % friendMap.me())
            pass

@mapping(u'friend.invite_result.response_receiver')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=NoneType)
def invite_result_response_receiver(context, result):
    capi_call = context
    if getattr(capi_call, "poke", False):
        from rogerthat.bizz.service import poke_service_with_tag
        context = getattr(capi_call, "context", None)
        message_flow_run_id = getattr(capi_call, "message_flow_run_id", None)
        poke_service_with_tag(capi_call.invitor, capi_call.service_identity_user, capi_call.poke_tag, context,
                              message_flow_run_id, now())

@mapping(u'friend.broke_up.response_receiver')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=NoneType)
def broke_friendship_response_receiver(context, result):
    pass


@mapping(u'friend.update.response_receiver')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=NoneType)
def friend_update_response_receiver(context, result):
    pass


@mapping(u'friend.is_in_roles.response_receiver')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=[(int, long)])
def is_in_roles_response_receiver(context, result):
    from rogerthat.bizz.job.update_friends import schedule_update_a_friend_of_a_service_identity_user
    from rogerthat.bizz.roles import _send_service_role_grants_updates

    service_user = context.service_user
    service_identity_user = context.service_identity_user
    app_user = context.human_user
    role_ids = context.role_ids
    make_friends_if_in_role = context.make_friends_if_in_role

    def trans():
        user_profile = get_user_profile(app_user, cached=False)
        granted = False
        revoked = False
        for role_id in role_ids:
            role = u'sr:%s' % role_id
            if role_id in result:
                logging.debug("Granting role %s", role)
                user_profile.grant_role(service_identity_user, role)
                granted = True
            elif user_profile.has_role(service_identity_user, role):
                logging.debug("Revoking role %s", role)
                user_profile.revoke_role(service_identity_user, role, skip_warning=True)
                revoked = True

        if granted or revoked:
            user_profile.put()
            on_trans_committed(_send_service_role_grants_updates, service_user)

            if granted:
                if make_friends_if_in_role:
                    on_trans_committed(makeFriends, service_identity_user, app_user, app_user, None,
                                       notify_invitee=False, origin=ORIGIN_USER_INVITE)
                else:
                    on_trans_committed(schedule_update_a_friend_of_a_service_identity_user, service_identity_user,
                                       app_user, force=True)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


@mapping(u'friend.invited.response_receiver')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=unicode)
def invited_response_receiver(context, result):
    capi_call = context

    user_data = None
    if result and result.startswith('{'):
        try:
            json.loads(result)
        except:
            logging.info("Received weird response in invited_response_receiver: %s" % result)
            result = DECLINE_ID
        else:
            user_data = result
            result = ACCEPT_ID

    if result != ACCEPT_ID:
        return  # declined

    invitor = capi_call.invitor
    tag = capi_call.servicetag
    invitee = capi_call.invitee
    origin = capi_call.origin
    service_user = capi_call.service_user
    service_identity_user = capi_call.service_identity_user
    service_identifier = capi_call.service_identifier
    context = getattr(capi_call, "context", None)
    message_flow_run_id = getattr(capi_call, "message_flow_run_id", None)
    poke = getattr(capi_call, "poke", False)
    process_invited_response(service_user, service_identity_user, service_identifier, invitor, invitee, tag, origin, \
                             poke, context, message_flow_run_id, user_data)

@arguments(service_user=users.User, service_identity_user=users.User, service_identifier=unicode, invitor=users.User, \
           invitee=users.User, tag=unicode, origin=unicode, poke=bool, context=unicode, message_flow_run_id=unicode,
           user_data=unicode)
def process_invited_response(service_user, service_identity_user, service_identifier, invitor, invitee, tag, origin,
                             poke, context, message_flow_run_id, user_data=None):
    from rogerthat.service.api.friends import invite_result
    makeFriends(invitor, invitee, invitee, None, notify_invitor=False, origin=origin, user_data=user_data)
    user_details = [UserDetailsTO.fromUserProfile(get_user_profile(invitor))]
    def trans():
        invite_result_capi_call = invite_result(invite_result_response_receiver, logServiceError,
                                                get_service_profile(service_user), email=get_human_user_from_app_user(invitor).email(),
                                                result=ESTABLISHED, tag=tag, origin=origin,
                                                service_identity=service_identifier, user_details=user_details,
                                                DO_NOT_SAVE_RPCCALL_OBJECTS=True)
        if poke:
            if not invite_result_capi_call:  # None if friend.invite_result is not implemented
                return "poke_now"
            else:
                invite_result_capi_call.poke = True
                invite_result_capi_call.poke_tag = tag
                invite_result_capi_call.invitor = invitor
                invite_result_capi_call.service = invitee
                invite_result_capi_call.context = context
                invite_result_capi_call.message_flow_run_id = message_flow_run_id
                invite_result_capi_call.put()
    result = db.run_in_transaction(trans)
    if result == "poke_now":
        try_or_defer(_poke_service_directly, invitor, tag, context, message_flow_run_id, service_identity_user, now())

@cached(1, memcache=False)
@returns(unicode)
@arguments(user=users.User)
def userCode(user):
    return unicode(ed(sha256("MC!&;^%s!&;^" % remove_slash_default(user).email())))

@returns(ProfileInfo)
@arguments(code=unicode)
def get_profile_info_via_user_code(code):
    pp = ProfilePointer.get(code)
    if pp:
        return get_profile_info(pp.user)
    return None


@returns(UserProfile)
@arguments(code=unicode)
def get_user_profile_via_user_code(code):
    pp = ProfilePointer.get(code)
    if pp:
        return get_user_profile(pp.user)
    return None

@returns(ServiceProfile)
@arguments(code=unicode)
def get_service_profile_via_user_code(code):
    pp = ProfilePointer.get(code)
    if pp:
        return get_service_profile(pp.user)
    return None

@returns(unicode)
@arguments(code=unicode)
def get_user_invite_url(code):
    pp = ProfilePointer.get(code)
    if not pp or not pp.short_url_id:
        return None
    return '%s/M/%s' % (get_server_settings().baseUrl, base38.encode_int(pp.short_url_id))


@returns(tuple)
@arguments(code=unicode)
def get_user_and_qr_code_url(code):
    pp = ProfilePointer.get(code)
    if not pp or not pp.short_url_id:
        return None
    url = '%s/S/%s' % (get_server_settings().baseUrl, base38.encode_int(pp.short_url_id))
    return url, pp.user


@returns(ServiceFriendStatusTO)
@arguments(service_identity_user=users.User, app_user=users.User)
def get_service_friend_status(service_identity_user, app_user):
    human_user, app_id = get_app_user_tuple(app_user)
    fsic, app, friend_profile = db.get([FriendServiceIdentityConnection.createKey(app_user, service_identity_user),
                                        App.create_key(app_id),
                                        UserProfile.createKey(app_user)])
    is_friend = fsic != None
    if is_friend:
        last_heartbeat = memcache.get("last_user_heart_beat_%s" % app_user.email()) or 0  # @UndefinedVariable
    else:
        last_heartbeat = 0
    result = ServiceFriendStatusTO()
    result.app_id = app_id
    result.app_name = app.name
    result.devices = list()
    result.email = human_user.email()
    result.is_friend = is_friend
    result.last_heartbeat = last_heartbeat
    if friend_profile:
        result.avatar = friend_profile.avatarUrl
        result.language = friend_profile.language
        result.name = friend_profile.name
        if friend_profile.mobiles:
            for m in friend_profile.mobiles:
                result.devices.append(Mobile.typeAsString(m.type_))
    else:
        result.name = None
        result.avatar = None
        result.language = None


    return result

@returns([unicode])
@arguments(app_user=users.User)
def create_friend_invitation_secrets(app_user):
    def trans():
        invitations = [ UserInvitationSecret(parent=parent_key(app_user), status=UserInvitationSecret.STATUS_CREATED,
                                             creation_timestamp=now(), origin=ORIGIN_USER_INVITE) for _ in xrange(20) ]
        aysnc_puts = [ db.put_async(i) for i in invitations ]
        foreach(lambda i: i.get_result(), aysnc_puts)
        return [i.secret for i in invitations]
    return db.run_in_transaction(trans)

@returns(NoneType)
@arguments(message=Message)
def ack_invitation_by_secret_failed(message):
    azzert(message.tag == FRIEND_ACCEPT_FAILED)
    invitor = message.invitor
    invitee = message.invitee
    if message.memberStatusses[message.members.index(invitor)].button_index == message.buttons[INVITE_ID].index:
        invite(invitor, invitee.email(), get_profile_info(invitee).name, None, None, message.service_tag, origin=message.origin, app_id=get_app_id_from_app_user(invitor))
        logging.info("Mr %s accepted offer" % invitor.email())
    else:
        logging.info("Mr %s did not accept offer" % invitor.email())

def _get_friend_location(user, friend):
    get_friend_location(user, friend, GetLocationRequestTO.TARGET_MOBILE_FIRST_REQUEST_AFTER_GRANT)

def _notify_users(invitor_profile_info, invitor, invitee_profile_info, invitee, notify_invitee, notify_invitor, notify_friends):
    def trans():
        if notify_invitor and not invitor_profile_info.isServiceIdentity:
            deferred.defer(_notify_invitor, invitor, invitor_profile_info, invitee, invitee_profile_info, _transactional=True)
        if notify_invitee and not invitee_profile_info.isServiceIdentity:
            deferred.defer(_notify_invitee, invitee, invitee_profile_info, invitor_profile_info, _transactional=True)
        for notify_friend in notify_friends:
            if notify_friend:
                deferred.defer(_notify_friends, *notify_friend, **dict(_transactional=True))
    db.run_in_transaction(trans)

def _notify_friends(from_, to, friendMap, friendDetail):
    # from and to are human
    if not friendMap.shareContacts:
        return
    # create request
    request = BecameFriendsRequestTO()
    request.user = remove_app_id(from_).email()
    request.friend = FriendRelationTO.fromDBFriendDetail(friendDetail)
    request.friend.email = userCode(to)  # certainly human user

    # assemble recipients
    friends = filter(lambda f: f != to, friendMap.friends)
    # send
    if friends:
        _notify_friend_mobiles(friends, request)
    slog('T', request.user, "com.mobicage.capi.friends.becameFriends", friend=request.friend.email)
    slog('T', request.friend.email, "com.mobicage.capi.friends.becameFriends", friend=request.user)

def _notify_friend_mobiles(friends, request):
    def trans():
        if len(friends) <= 2:
            becameFriends(became_friends_response, logError, friends, request=request)
        else:
            becameFriends(became_friends_response, logError, friends[:2], request=request)
            deferred.defer(_notify_friend_mobiles, friends[2:], request, _transactional=True)
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)

def _notify_invitor(invitor_user, invitor_profile_info, invitee, invitee_profile_info):
    xg_on = db.create_transaction_options(xg=True)
    msg = localize(invitor_profile_info.language, "_friendship_accepted", name=invitor_profile_info.name,
                   friend_name=_get_full_name(invitee))
    def trans():
        dashboardNotification(invitor_user, msg)
    db.run_in_transaction_options(xg_on, trans)

def _notify_invitee(invitee_user, invitee_profile_info, invitor_profile_info):
    xg_on = db.create_transaction_options(xg=True)
    msg = localize(invitee_profile_info.language, "_friendship_established", name=invitee_profile_info.name, friend_name=invitor_profile_info.name)
    def trans():
        dashboardNotification(invitee_user, msg)
    db.run_in_transaction_options(xg_on, trans)


@returns(NoneType)
@arguments(friendMap=FriendMap, updated_user=users.User, status=int, skip_mobiles=[unicode])
def _defer_update_friend(friendMap, updated_user, status, skip_mobiles=None):
    from rogerthat.bizz.job.update_friends import send_update_friend_request
    deferred.defer(send_update_friend_request, friendMap.user, updated_user, status, friendMap.key(),
                   skip_mobiles=skip_mobiles, _transactional=db.is_in_transaction())


def _validate_invitation(invitee_email, invitor_user, servicetag, app_id):
    from rogerthat.bizz.service import UnsupportedAppIdException

    if not invitee_email:
        raise InvalidEmailAddressException()

    if "@" in invitee_email:
        invitee_user = users.User(invitee_email)
        invitee_profile_info = get_profile_info(invitee_user, skip_warning=True)
        if not (invitee_profile_info and invitee_profile_info.isServiceIdentity):
            invitee_user = create_app_user(invitee_user, app_id)
    else:
        # invitee_email is in fact a hashed_email of a human user
        invitee_email = invitee_email.split('?')[0]
        pp = ProfilePointer.get_by_key_name(invitee_email)
        if not pp:
            raise UserNotFoundViaUserCode(invitee_email)
        invitee_user = pp.user
        invitee_email = get_human_user_from_app_user(invitee_user).email()
        if get_app_id_from_app_user(invitee_user) != app_id:
            logging.debug("Expected app_id of invitee to be %s, but was %s",
                          app_id, get_app_id_from_app_user(invitee_user))
            raise UnsupportedAppIdException(app_id)
        invitee_profile_info = get_profile_info(invitee_user)

    invitor_profile_info = get_profile_info(invitor_user)
    if invitor_profile_info.isServiceIdentity:
        if not (invitee_profile_info and invitee_profile_info.isServiceIdentity):
            if get_app_id_from_app_user(invitee_user) not in invitor_profile_info.appIds:
                logging.debug("Expected app_id of invitee to be in [%s], but was %s",
                              ', '.join(invitor_profile_info.appIds), get_app_id_from_app_user(invitee_user))
                raise UnsupportedAppIdException(app_id)
        if get_friend_serviceidentity_connection(friend_user=invitee_user, service_identity_user=invitor_user):  # what if invitee is a service identity?
            raise CanNotInviteFriendException()
    else:
        if not (invitee_profile_info and invitee_profile_info.isServiceIdentity):
            if get_app_id_from_app_user(invitee_user) != get_app_id_from_app_user(invitor_user):
                logging.debug("Expected app_id of invitee to be %s, but was %s",
                              get_app_id_from_app_user(invitor_user), get_app_id_from_app_user(invitee_user))
                raise UnsupportedAppIdException(app_id)
        else:
            if get_app_id_from_app_user(invitor_user) not in invitee_profile_info.appIds:
                logging.debug("Expected app_id of invitor to be in [%s], but was %s",
                              ', '.join(invitee_profile_info.appIds), get_app_id_from_app_user(invitor_user))
                raise UnsupportedAppIdException(app_id)
        friend_map = get_friends_map(invitor_user)
        if invitee_user in friend_map.friends:
            invitee_profile_info = get_profile_info(invitee_user)
            msg = localize(invitor_profile_info.language, "_invitee_was_already_friend", name=invitor_profile_info.name,
                           friend_email=invitee_profile_info.qualifiedIdentifier or invitee_email)
            dashboardNotification(invitor_user, msg)
            raise CanNotInviteFriendException()

    if invitor_user == invitee_user:
        if not invitor_profile_info.isServiceIdentity:
            msg = localize(invitor_profile_info.language, "_invited_yourself", name=invitor_profile_info.name)
            dashboardNotification(invitor_user, msg)
        raise CannotSelfInviteException()

    now_ = now()
    invitation_history = get_friend_invitation_history(invitor_user, invitee_user)
    if invitation_history:
        app_name = get_app_name_by_id(app_id)
        if len(invitation_history.inviteTimestamps) >= 3:
            if not invitor_profile_info.isServiceIdentity:
                msg = localize(invitor_profile_info.language, "_invited_too_often", name=invitor_profile_info.name,
                               friend_email=invitee_email, app_name=app_name)
                dashboardNotification(invitor_user, msg)
            raise PersonInvitationOverloadException()
        last_week = now_ - WEEK
        if any((ts > last_week for ts in invitation_history.inviteTimestamps)):
            server_settings = get_server_settings()
            if invitee_email not in server_settings.supportWorkers:
                if not invitor_profile_info.isServiceIdentity:
                    msg = localize(invitor_profile_info.language, "_invited_too_often_this_week",
                                   name=invitor_profile_info.name, friend_email=invitee_email, app_name=app_name)
                    dashboardNotification(invitor_user, msg)
                raise PersonAlreadyInvitedThisWeekException()
    else:
        invitation_history = FriendInvitationHistory.create(invitor_user, invitee_user)
        invitation_history.inviteTimestamps = list()
    invitation_history.tag = servicetag
    hasher = hashlib.sha256()
    hasher.update(str(uuid.uuid4()))
    hasher.update(str(uuid.uuid4()))
    hasher.update(str(uuid.uuid4()))
    hasher.update(str(uuid.uuid4()))
    invitation_history.lastAttemptKey = hasher.hexdigest()
    return invitee_user, invitation_history, now_

def _send_invitation_email(language, email, invitor_user, invitee, invitation_history, now_, message, service_tag, origin):
    if get_do_send_email_invitations(invitee):
        raise DoesNotWantToBeInvitedViaEmail()
    profile_info = get_profile_info(invitor_user, skip_warning=True)
    if profile_info.isServiceIdentity:
        invitor_user = add_slash_default(invitor_user)

    timestamp = now()
    uis = UserInvitationSecret(parent=parent_key_unsafe(remove_slash_default(invitor_user)), status=UserInvitationSecret.STATUS_SENT, \
                               creation_timestamp=timestamp, sent_timestamp=timestamp, email=invitee, \
                               service_tag=service_tag, origin=origin)
    uis.put()
    secret = uis.secret

    short_url = get_user_invite_url(userCode(invitor_user))

    _, app_id = get_app_user_tuple(invitee)
    app = get_app_by_id(app_id)
    variables = dict(profile=profile_info, short_url=short_url, secret=secret, message=message, app=app)
    variables['consts'] = consts
    if profile_info.isServiceIdentity:
        service_profile = get_service_profile(profile_info.service_user)
        variables['localized_organization_type'] = service_profile.localizedOrganizationType(language)
        body = render("service_invite_email", [language], variables)
        html = render("service_invite_email_html", [language], variables)
        si = get_service_identity(invitor_user)
        from_ = "%s <%s>" % (si.name, si.qualifiedIdentifier if si.qualifiedIdentifier else get_service_user_from_service_identity_user(invitor_user).email())
        subject = localize(language, "Discover our new app")
    else:
        body = render("invite_email", [language], variables)
        html = render("invite_email_html", [language], variables)
        from_user, _ = get_app_user_tuple(invitor_user)
        from_ = from_user.email()
        subject = localize(language, "%(name)s invites you to the %(app_name)s app!", name=profile_info.name, app_name=app.name)

    settings = get_server_settings()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_
    msg['To'] = email
    msg.attach(MIMEText(body.encode('utf-8'), 'plain', 'utf-8'))
    msg.attach(MIMEText(html.encode('utf-8'), 'html', 'utf-8'))
    send_mail_via_mime(settings.senderEmail, email, msg)

    invitation_history.inviteTimestamps.append(now_)
    invitation_history.put()

def _send_invitation_message(servicetag, message, name, user, invitee, invitation_history, now_, origin):
    name = _get_full_name(user)
    invitor_profile_info, invitee_user_profile = get_profile_infos([user, invitee], expected_types=[ProfileInfo, UserProfile])
    app_name = get_app_name_by_id(get_app_id_from_app_user(invitee))
    if invitor_profile_info.isServiceIdentity:
        m = localize(invitee_user_profile.language, "Service %(name)s wants to connect with you via %(app_name)s.", name=name, app_name=app_name)
    else:
        m = localize(invitee_user_profile.language, "User %(name)s wants to get in touch with you via %(app_name)s.", name=name, app_name=app_name)
    if message:
        m += "\n\n" + localize(invitee_user_profile.language, "%(name_or_email)s added a personal note:\n\n%(message)s", name_or_email=(invitor_profile_info.name or invitor_profile_info.user.email()), message=message)
    logging.info('Sending invitation: %s', m)
    message = sendMessage(MC_DASHBOARD, [UserMemberTO(invitee)], Message.FLAG_AUTO_LOCK, 0, None, m,
                          create_accept_decline_buttons(invitee_user_profile.language), None,
                          get_app_by_user(invitee).core_branding_hash, FRIEND_INVITATION_REQUEST, is_mfr=False)
    message.invitor = user
    message.invitee = invitee
    message.origin = origin
    if servicetag:
        message.servicetag = servicetag
    invitation_history.inviteTimestamps.append(now_)
    db.put([message, invitation_history])

def _send_invitation_message_from_service_to_user(app_user, service_identity_user, message, brandingHash, language,
                                                  origin, tag):
    m = sendMessage(service_identity_user, [UserMemberTO(app_user)], Message.FLAG_ALLOW_DISMISS, 0, None, message,
                    create_add_to_services_button(language), None, brandingHash, tag,
                    is_mfr=False, check_friends=False, allow_reserved_tag=True)
    m.invitor = service_identity_user
    m.invitee = app_user
    m.origin = origin
    m.put()

def _get_full_name(user):
    profile_info = get_profile_info(user)
    name = "%s (%s)" % (profile_info.name, profile_info.qualifiedIdentifier or remove_app_id(remove_slash_default(user)).email())
    return name

def _poke_service_directly(invitor, tag, context, message_flow_run_id, service_identity_user, timestamp):
    from rogerthat.bizz.service import poke_service_with_tag
    poke_service_with_tag(invitor, service_identity_user, tag, context, message_flow_run_id, timestamp)


@returns(SubscribedBroadcastUsersTO)
@arguments(service_identity_user=users.User, broadcast_type=unicode)
def getSubscribedBroadcastUsers(service_identity_user, broadcast_type):
    from rogerthat.bizz.service import validate_broadcast_type
    validate_broadcast_type(get_service_user_from_service_identity_user(service_identity_user), broadcast_type)

    qry = get_friend_service_identity_connections_of_service_identity_query(service_identity_user)
    sbuto = SubscribedBroadcastUsersTO()
    sbuto.connected_users = list()
    sbuto.not_connected_users = 0
    app_users = list()
    connections = dict()
    for connection in qry:
        app_user = users.User(connection.friend)
        if broadcast_type in connection.enabled_broadcast_types:
            app_users.append(app_user)
            connections[app_user.email()] = connection
        else:
            sbuto.not_connected_users = sbuto.not_connected_users + 1

    for user_profile in get_user_profiles(app_users):
        connection = connections[user_profile.user.email()]
        svc_friend = BroadcastFriendTO()
        svc_friend.avatar = u"%s/unauthenticated/mobi/cached/avatar/%s" % (get_server_settings().baseUrl, connection.friend_avatarId)
        svc_friend.name = connection.friend_name
        svc_friend.age = user_profile.age
        svc_friend.gender = user_profile.gender_str
        svc_friend.app_id = user_profile.app_id
        sbuto.connected_users.append(svc_friend)

    return sbuto

@returns(SubscribedBroadcastReachTO)
@arguments(service_identity_user=users.User, broadcast_type=unicode, min_age=(int, long, NoneType),
           max_age=(int, long, NoneType), gender=unicode)
def getSubscribedBroadcastReach(service_identity_user, broadcast_type, min_age=None, max_age=None, gender=None):
    from rogerthat.bizz.service import validate_broadcast_type
    validate_broadcast_type(get_service_user_from_service_identity_user(service_identity_user), broadcast_type)

    gender = UserProfile.gender_from_string(gender)

    @cached(1, request=False, memcache=True)
    @returns(int)
    @arguments(service_identity_user=users.User)
    def get_total_number_of_users(service_identity_user):
        return get_friend_service_identity_connections_of_service_identity_keys_query(service_identity_user) \
            .count(limit=None)

    @cached(1, request=False, memcache=True)
    @returns(int)
    @arguments(service_identity_user=users.User, min_age=int, max_age=int, gender=int, broadcast_type=unicode)
    def get_subscribed_number_of_users(service_identity_user, min_age=None, max_age=None, gender=None,
                                       broadcast_type=None):
        default = lambda x: None if x == -1 else x
        return get_broadcast_audience_of_service_identity_keys_query(service_identity_user, min_age=default(min_age),
                                                                     max_age=default(max_age), gender=default(gender),
                                                                     broadcast_type=broadcast_type).count(limit=None)

    def get_number_of_users():
        threading.current_thread().count = get_total_number_of_users(service_identity_user)

    thread = threading.Thread(target=get_number_of_users)
    thread.start()
    default = lambda x:-1 if x is None else x
    subscribed_count = get_subscribed_number_of_users(service_identity_user, default(min_age), default(max_age),
                                                      default(gender), broadcast_type)
    thread.join()
    total_count = thread.count
    result = SubscribedBroadcastReachTO()
    result.total_users = total_count
    result.subscribed_users = subscribed_count
    return result

@mapping(u'friend.in_reach.response_receiver')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=NoneType)
def in_reach_response_receiver(context, result):
    pass

@mapping(u'friend.out_of_reach.response_receiver')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=NoneType)
def out_of_reach_response_receiver(context, result):
    pass

@returns([GroupTO])
@arguments(app_user=users.User)
def getGroups(app_user):
    return [GroupTO.from_model(g) for g in Group.gql("WHERE ANCESTOR IS :1", parent_key(app_user)).fetch(None)]

@returns(str)
@arguments(app_user=users.User, guid=unicode, name=unicode, members=[unicode], avatar=unicode, current_mobile=Mobile)
def putGroup(app_user, guid, name, members, avatar, current_mobile):
    group = Group(key=Group.create_key(app_user, guid))
    group.name = name
    app_id = get_app_id_from_app_user(app_user)
    if App.APP_ID_ROGERTHAT == app_id:
        group.members = members
    else:
        group.members = []
        for m in members:
            group.members.append(create_app_user(users.User(m), app_id).email())

    if avatar:
        group.avatar = base64.b64decode(str(avatar))
        digester = hashlib.sha256()
        digester.update(group.avatar)
        group.avatar_hash = digester.hexdigest().upper()
    group.put()

    extra_kwargs = dict()
    if current_mobile is not None:
        extra_kwargs[SKIP_ACCOUNTS] = [current_mobile.account]
    updateGroups(update_groups_response, logError, app_user, request=UpdateGroupsRequestTO(), **extra_kwargs)
    return group.avatar_hash

@returns(NoneType)
@arguments(app_user=users.User, guid=unicode, current_mobile=Mobile)
def deleteGroup(app_user, guid, current_mobile):
    db.delete(Group.create_key(app_user, guid))

    extra_kwargs = dict()
    if current_mobile is not None:
        extra_kwargs[SKIP_ACCOUNTS] = [current_mobile.account]
    updateGroups(update_groups_response, logError, app_user, request=UpdateGroupsRequestTO(), **extra_kwargs)

@returns(unicode)
@arguments(avatar_hash=unicode, size=long)
def getGroupAvatar(avatar_hash, size):
    group = Group.gql("WHERE avatar_hash = :1", avatar_hash).get()
    if group:
        picture = str(group.avatar)
        img = images.Image(picture)
        if img.width > size or img.height > size:
            img.resize(size, size)
            picture = img.execute_transforms(output_encoding=img.format)

        return unicode(base64.b64encode(picture))
    return None

@returns(FindFriendResponseTO)
@arguments(app_user=users.User, search_string=unicode, cursor_string=unicode, avatar_size=int)
def find_friend(app_user, search_string, cursor_string=None, avatar_size=50):
    from rogerthat.bizz.profile import USER_INDEX

    def get_name_sort_options():
        sort_expr = search.SortExpression(expression='name', direction=search.SortExpression.ASCENDING)
        return search.SortOptions(expressions=[sort_expr])

    limit = 30
    results = []
    results_cursor = None

    app_id = get_app_id_from_app_user(app_user)

    the_index = search.Index(name=USER_INDEX)
    try:
        query_string = u"%s app_id:%s" % (normalize_search_string(search_string), app_id)
        query = search.Query(query_string=query_string,
                             options=search.QueryOptions(returned_fields=['email'],
                                                         sort_options=get_name_sort_options(),
                                                         limit=limit - len(results),
                                                         cursor=search.Cursor(cursor_string)))
        search_result = the_index.search(query)
        results.extend(search_result.results)
        results_cursor = search_result.cursor.web_safe_string if search_result.cursor else None
    except:
        logging.error('Search query error while searching friends for search_string "%s"', search_string, exc_info=True)
    users_ = [create_app_user_by_email(human_user_email, app_id) for human_user_email in [result.fields[0].value for result in results]]
    user_profiles = get_user_profiles(users_)

    r = FindFriendResponseTO()
    r.error_string = None
    r.items = list()
    r.cursor = results_cursor

    for up in user_profiles:
        t = FindFriendItemTO()
        t.name = up.name
        t.email = get_human_user_from_app_user(up.user).email()
        t.avatar_url = up.avatarUrl
        r.items.append(t)

    return r


@mapping(u'friend.register_result.response_receiver')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=NoneType)
def register_result_response_receiver(context, result):
    pass
