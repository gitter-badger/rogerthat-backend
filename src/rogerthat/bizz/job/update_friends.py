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

import logging
from types import NoneType
import uuid

from google.appengine.api import memcache
from google.appengine.ext import db, deferred
from mcfw.rpc import returns, arguments, serialize_complex_value
from rogerthat.bizz.friends import update_friend_response, update_friend_set_response, \
    friend_update_response_receiver
from rogerthat.bizz.i18n import get_translator
from rogerthat.bizz.job import run_job, MODE_BATCH
from rogerthat.capi.friends import updateFriend, updateFriendSet
from rogerthat.consts import DEFAULT_QUEUE, HIGH_LOAD_WORKER_QUEUE
from rogerthat.dal import put_and_invalidate_cache
from rogerthat.dal.friend import get_friends_friends_maps_keys_query, get_friends_map_key_by_user, get_friends_map
from rogerthat.dal.mobile import get_mobile_by_account
from rogerthat.dal.profile import get_user_profile, get_service_profile, get_service_profiles
from rogerthat.dal.service import get_friend_service_identity_connections_keys_of_app_user_query, \
    get_all_service_friend_keys_query, get_friend_service_identity_connections_keys_query, \
    get_one_friend_service_identity_connection_keys_query
from rogerthat.models import ProfileInfo, ServiceTranslation, ServiceIdentity, FriendServiceIdentityConnection, \
    FriendMap, BroadcastSettingsFlowCache, ServiceProfile, App
from rogerthat.models.properties.friend import FriendDetail
from rogerthat.rpc import users
from rogerthat.rpc.rpc import logError
from rogerthat.rpc.service import logServiceError
from rogerthat.to.friends import UpdateFriendRequestTO, FriendTO, UpdateFriendSetRequestTO
from rogerthat.to.service import UserDetailsTO
from rogerthat.utils import channel, azzert, get_current_queue
from rogerthat.utils.app import remove_app_id, get_app_user_tuple
from rogerthat.utils.service import remove_slash_default, get_service_user_from_service_identity_user
from rogerthat.utils.transactions import on_trans_committed, run_in_transaction


def _must_continue_with_update_service(service_profile_or_user, bump_service_version=False, clear_broadcast_settings_cache=False):
    def trans(service_profile):
        azzert(service_profile)
        service_profile_updated = False
        if not service_profile.autoUpdating and not service_profile.updatesPending:
            service_profile.updatesPending = True
            service_profile_updated = True
        if bump_service_version:
            service_profile.version += 1
            service_profile_updated = True
        if clear_broadcast_settings_cache:
            service_profile.addFlag(ServiceProfile.FLAG_CLEAR_BROADCAST_SETTINGS_CACHE)
            service_profile_updated = True

        if service_profile_updated:
            channel.send_message(service_profile.user, 'rogerthat.service.updatesPendingChanged',
                                 updatesPending=service_profile.updatesPending)
            service_profile.put()

        return service_profile.autoUpdating

    is_user = not isinstance(service_profile_or_user, ServiceProfile)
    if db.is_in_transaction():
        azzert(not is_user)
        service_profile = service_profile_or_user
        auto_updating = trans(service_profile_or_user)
    else:
        service_profile = get_service_profile(service_profile_or_user, False) if is_user else service_profile_or_user
        auto_updating = db.run_in_transaction(trans, service_profile)

    if not auto_updating:
        logging.info("Auto-updates for %s are suspended." % service_profile.user.email())
    return auto_updating


@returns(NoneType)
@arguments(profile_info=ProfileInfo)
def schedule_update_friends_of_profile_info(profile_info):
    """If profile_info is human user ==> update friends and services of human_user
    If profile_info is service_identity ==> update human friendMaps of service_identity"""
    if profile_info.isServiceIdentity:
        service_profile = get_service_profile(profile_info.service_user, not db.is_in_transaction())
        if not _must_continue_with_update_service(service_profile):
            return

    worker_queue = get_current_queue() or HIGH_LOAD_WORKER_QUEUE
    deferred.defer(_run_update_friends_by_profile_info, profile_info.key(),
                   worker_queue=worker_queue,
                   _transactional=db.is_in_transaction(),
                   _queue=worker_queue)


@returns(NoneType)
@arguments(service_profile_or_user=(ServiceProfile, users.User), force=bool, bump_service_version=bool,
           clear_broadcast_settings_cache=bool)
def schedule_update_all_friends_of_service_user(service_profile_or_user, force=False, bump_service_version=False,
                                                clear_broadcast_settings_cache=False):
    '''Schedule update of all service_identities of a service to all connected users'''
    is_user = not isinstance(service_profile_or_user, ServiceProfile)
    service_user = service_profile_or_user if is_user else service_profile_or_user.user
    azzert('/' not in service_user.email(), "Expecting a service user, not a service identity.")
    if not force and not _must_continue_with_update_service(service_profile_or_user, bump_service_version,
                                                            clear_broadcast_settings_cache):
        return
    current_queue = get_current_queue()
    worker_queue = HIGH_LOAD_WORKER_QUEUE if current_queue in (None, DEFAULT_QUEUE) else current_queue
    deferred.defer(_run_update_friends_for_service_user, service_user, force, bump_service_version,
                   clear_broadcast_settings_cache,
                   get_all_service_friend_keys_query, [service_user],
                   worker_queue=worker_queue,
                   _transactional=db.is_in_transaction(),
                   _queue=worker_queue)

@returns(NoneType)
@arguments(service_profile_or_user=(ServiceProfile, users.User), target_user=users.User, force=bool,
           clear_broadcast_settings_cache=bool)
def schedule_update_a_friend_of_service_user(service_profile_or_user, target_user, force=False,
                                             clear_broadcast_settings_cache=False):
    '''Schedule update of all service_identities of a service to 1 user'''
    is_user = not isinstance(service_profile_or_user, ServiceProfile)
    service_user = service_profile_or_user if is_user else service_profile_or_user.user
    azzert('/' not in service_user.email(), "Expecting a service user, not a service identity.")
    if not force and not _must_continue_with_update_service(service_profile_or_user, False,
                                                            clear_broadcast_settings_cache):
        return
    deferred.defer(_run_update_friends_for_service_user, service_user, force, False, clear_broadcast_settings_cache,
                   get_friend_service_identity_connections_keys_query, [service_user, target_user],
                   _transactional=db.is_in_transaction())

@returns(NoneType)
@arguments(service_identity_user=users.User, target_user=users.User, force=bool, clear_broadcast_settings_cache=bool)
def schedule_update_a_friend_of_a_service_identity_user(service_identity_user, target_user, force=False,
                                                        clear_broadcast_settings_cache=False):
    '''Schedule update of 1 service_identity to 1 user'''
    azzert('/' in service_identity_user.email(), "Expecting a service identity user.")
    service_user = get_service_user_from_service_identity_user(service_identity_user)
    if db.is_in_transaction():
        service_profile_or_service_user = get_service_profile(service_user, False)
    else:
        service_profile_or_service_user = service_user
    if not force and not _must_continue_with_update_service(service_profile_or_service_user, False,
                                                            clear_broadcast_settings_cache):
        return
    deferred.defer(_run_update_friends_for_service_user, service_user, force, False, clear_broadcast_settings_cache,
                   get_one_friend_service_identity_connection_keys_query, [service_identity_user, target_user],
                   _transactional=db.is_in_transaction())


def _run_update_friends_for_service_user(service_user, force, bump_service_version, clear_broadcast_settings_cache,
                                         get_fsics_query_function, get_fsics_query_function_args,
                                         worker_queue=HIGH_LOAD_WORKER_QUEUE):
    '''Send update of all service_identities of a service to users defined by
    get_fsics_query_function(*get_fsics_query_function_args)'''
    translator = get_translator(service_user, [ServiceTranslation.IDENTITY_TEXT])
    translator_memcachekey = str(uuid.uuid4())
    memcache.add(translator_memcachekey, translator)  # @UndefinedVariable
    def trans():
        service_profile = get_service_profile(service_user)
        clear = service_profile.isFlagSet(ServiceProfile.FLAG_CLEAR_BROADCAST_SETTINGS_CACHE)
        if clear:
            service_profile.clearFlag(ServiceProfile.FLAG_CLEAR_BROADCAST_SETTINGS_CACHE)
            service_profile.put()
        if clear or clear_broadcast_settings_cache:
            logging.info("Clearing broadcast settings cache")

        on_trans_committed(run_job, get_fsics_query_function, get_fsics_query_function_args,
                           _update_friend_via_friend_connection, [translator_memcachekey,
                                                                  clear or clear_broadcast_settings_cache],
                           worker_queue=worker_queue)
    db.run_in_transaction(trans)


def _run_update_friends_by_profile_info(profile_info_key, worker_queue=HIGH_LOAD_WORKER_QUEUE):
    profile_info = db.get(profile_info_key)
    user = remove_slash_default(profile_info.user)

    if profile_info.isServiceIdentity:
        translator = get_translator(user, [ServiceTranslation.IDENTITY_TEXT])
        translator_memcachekey = str(uuid.uuid4())
        memcache.add(translator_memcachekey, translator)  # @UndefinedVariable
    else:
        translator_memcachekey = None

    def trans():
        run_job(get_friends_friends_maps_keys_query, [user], _update_friend, [profile_info_key, translator_memcachekey],
                worker_queue=worker_queue)
        if not profile_info.isServiceIdentity:
            update_friend_service_identity_connections(profile_info_key)
    db.run_in_transaction(trans)


def update_friend_service_identity_connections(profile_info_key):
    user = users.User(profile_info_key.parent().name())
    run_job(get_friend_service_identity_connections_keys_of_app_user_query, [user],
            _update_service_friends, [profile_info_key],
            MODE_BATCH, batch_timeout=2)


def _update_friend_via_friend_connection(friend_connection_key, translator_memcachekey,
                                         clear_broadcast_settings_cache=False):
    connection = db.get(friend_connection_key)
    if not connection:
        return
    _update_friend(get_friends_map_key_by_user(connection.friend), \
                   ServiceIdentity.keyFromUser(connection.service_identity), translator_memcachekey,
                   clear_broadcast_settings_cache)

def _update_friend(friend_map_key, profile_info_key, translator_memcachekey, clear_broadcast_settings_cache=False):
    profile_info = run_in_transaction(db.get, False, profile_info_key)  # to be sure we have the latest version of the model
    if translator_memcachekey:
        translator = memcache.get(translator_memcachekey)  # @UndefinedVariable
        if not translator:
            logging.warn("Memcache miss of translator")
            translator = get_translator(profile_info.service_user, [ServiceTranslation.IDENTITY_TEXT])
    elif profile_info.isServiceIdentity:
        translator = get_translator(profile_info.service_user, [ServiceTranslation.IDENTITY_TEXT])
    else:
        translator = None
    avatarId = profile_info.avatarId

    service_profile = get_service_profile(get_service_user_from_service_identity_user(profile_info.user)) if profile_info.isServiceIdentity else None

    def trans():
        friendMap = db.get(friend_map_key)
        if not friendMap:
            logging.warn("Friendmap not found for key: %s" % friend_map_key)
            return
        email = remove_slash_default(profile_info.user).email()
        if not email in friendMap.friendDetails:
            logging.warn("Probably friend %s was removed while updating %s" % (email, friendMap.user.email()))
            return
        friendDetail = friendMap.friendDetails[email]
        friendDetail.avatarId = avatarId
        if profile_info.isServiceIdentity:
            target_language = get_user_profile(friendMap.user).language
            friendDetail.name = translator.translate(ServiceTranslation.IDENTITY_TEXT, profile_info.name, target_language)
        else:
            friendDetail.name = profile_info.name
        friendDetail.type = FriendDetail.TYPE_SERVICE if profile_info.isServiceIdentity else FriendDetail.TYPE_USER
        friendDetail.relationVersion += 1
        friendMap.generation += 1

        puts = [friendMap]

        if profile_info.isServiceIdentity:
            fsic = db.get(FriendServiceIdentityConnection.createKey(friendMap.user, profile_info.user))
            for attr in ('disabled_broadcast_types', 'enabled_broadcast_types'):
                if getattr(fsic, attr) is None:
                    setattr(fsic, attr, list())

            _, app_id = get_app_user_tuple(friendMap.user)

            updated = False
            enabled_broadcast_types = list(fsic.enabled_broadcast_types)
            if app_id == App.APP_ID_OSA_LOYALTY:
                if enabled_broadcast_types:
                    enabled_broadcast_types = list()
                    updated = True
            else:
                # Add new broadcast types
                for broadcast_type in service_profile.broadcastTypes:
                    if broadcast_type not in (fsic.disabled_broadcast_types + fsic.enabled_broadcast_types):
                        enabled_broadcast_types = list(set(enabled_broadcast_types) | set([broadcast_type]))
                        updated = True
                # Remove deleted broadcast types
                for broadcast_type in fsic.enabled_broadcast_types:
                    if broadcast_type not in service_profile.broadcastTypes:
                        enabled_broadcast_types.remove(broadcast_type)
                        updated = True

            if updated:
                friendDetail.relationVersion += 1
                fsic.enabled_broadcast_types = enabled_broadcast_types
                puts.append(fsic)

            if updated or clear_broadcast_settings_cache:
                logging.info("Deleting BroadcastSettingsFlowCache from datastore")
                db.delete_async(BroadcastSettingsFlowCache.create_key(friendMap.user, profile_info.user))

        put_and_invalidate_cache(*puts)

        # defer updateFriend with countdown=1 to ensure that changes are persisted.
        deferred.defer(_trigger_update_friend, friendMap.user, friend_map_key, profile_info_key,
                       _transactional=True, _countdown=1, _queue=get_current_queue() or HIGH_LOAD_WORKER_QUEUE)

    db.run_in_transaction(trans)

@arguments(target_user=users.User, friend_map_or_key=(FriendMap, db.Key), profile_info_or_key=(ProfileInfo, db.Key))
def _trigger_update_friend(target_user, friend_map_or_key, profile_info_or_key):
    profile_info = db.get(profile_info_or_key) if isinstance(profile_info_or_key, db.Key) else profile_info_or_key
    logging.info("Sending out updates for %s (%s)", profile_info.name, profile_info.user.email())

    friendTO = send_update_friend_request(target_user, profile_info.user, UpdateFriendRequestTO.STATUS_MODIFIED,
                                          friend_map_or_key)
    if friendTO:
        if profile_info.isServiceIdentity:
            # Send update request over channel API
            friend_dict = serialize_complex_value(friendTO, FriendTO, False)
            # Preventing "InvalidMessageError: Message must be no longer than 32767 chars"
            del friend_dict['appData']
            del friend_dict['userData']
            channel.send_message(target_user, u'rogerthat.friends.update',
                                 friend=friend_dict)


@returns(FriendTO)
@arguments(target_user=users.User, updated_user=users.User, status=int, friend_map_or_key=(FriendMap, db.Key),
           bump_friend_map_generation=bool, extra_conversion_kwargs=dict, skip_mobiles=[unicode])
def send_update_friend_request(target_user, updated_user, status, friend_map_or_key=None,
                               bump_friend_map_generation=False, extra_conversion_kwargs=None, skip_mobiles=None):
    '''
    Sends the correct request (UpdateFriendRequest or UpdateFriendSetRequest) to the client,
    based on the version of the mobile.

    @param target_user: The user which will receive the update.
    @param updated_user: The user which has been updated.
    @param status: The kind of friend update. See UpdateFriendRequestTO.STATUS_*
    @param friend_map_or_key: Optional FriendMap or db.Key (to fetch the FriendMap by key).
                              If None, then the FriendMap will be fetched by key name.
    @param bump_friend_map_generation: Optional bool to define whether the FriendMap generation
                                       (and version in case of add/remove) needs to be bumped.
    @param extra_conversion_kwargs: Optional kwargs to pass to the FriendTO.fromDBFriendDetail method.
    @param skip_mobiles: mobile accounts that should be skipped.
    '''
    azzert(status in (UpdateFriendRequestTO.STATUS_ADD,
                      UpdateFriendRequestTO.STATUS_DELETE,
                      UpdateFriendRequestTO.STATUS_MODIFIED))

    def trans():
        if isinstance(friend_map_or_key, FriendMap):
            friend_map = friend_map_or_key
        elif isinstance(friend_map_or_key, db.Key):
            friend_map = db.get(friend_map_or_key)
        else:
            friend_map = get_friends_map(target_user)

        if status == UpdateFriendRequestTO.STATUS_DELETE:
            friend_detail = None
        else:
            try:
                friend_detail = friend_map.friendDetails[remove_slash_default(updated_user).email()]
            except KeyError:
                logging.warn("%s not found in the friendMap of %s. Not sending updateFriend request with status=%s",
                             remove_slash_default(updated_user), target_user, status)
                return None
        return _do_update_friend_request(target_user, friend_detail, status, friend_map, bump_friend_map_generation,
                                         extra_conversion_kwargs, skip_mobiles)

    if db.is_in_transaction():
        return trans()
    else:
        xg_on = db.create_transaction_options(xg=True)
        return db.run_in_transaction_options(xg_on, trans)


@returns(FriendTO)
@arguments(target_user=users.User, updated_friend_detail=FriendDetail, status=int, friend_map=FriendMap,
           bump_friend_map_generation=bool, extra_conversion_kwargs=dict, skip_mobiles=[unicode])
def _do_update_friend_request(target_user, updated_friend_detail, status, friend_map,
                              bump_friend_map_generation=False, extra_conversion_kwargs=None, skip_mobiles=None):

    @db.non_transactional()
    def convert_friend():
        conversion_kwargs = dict(includeAvatarHash=True,
                                 includeServiceDetails=(status != UpdateFriendRequestTO.STATUS_DELETE),
                                 targetUser=target_user)
        if extra_conversion_kwargs:
            conversion_kwargs.update(extra_conversion_kwargs)
            logging.debug("Running FriendTO.fromDBFriendDetail for %s with the following kwargs: %s",
                          updated_friend_detail.email, conversion_kwargs)
        return FriendTO.fromDBFriendDetail(updated_friend_detail, **conversion_kwargs)

    def update_friend_set(friend, mobile):
        request = UpdateFriendSetRequestTO()
        request.friends = [remove_app_id(users.User(f.email)).email() for f in friend_map.friendDetails]
        request.version = friend_map.version
        request.added_friend = friend if status == UpdateFriendRequestTO.STATUS_ADD else None
        updateFriendSet(update_friend_set_response, logError, target_user, request=request, MOBILE_ACCOUNT=mobile,
                        SKIP_ACCOUNTS=skip_mobiles)
        return request.added_friend

    def update_friend(friend, mobile):
        request = UpdateFriendRequestTO()
        request.friend = friend
        request.generation = friend_map.generation  # deprecated
        request.status = status
        capi_calls = updateFriend(update_friend_response, logError, target_user, request=request,
                                  DO_NOT_SAVE_RPCCALL_OBJECTS=True, MOBILE_ACCOUNT=mobile, SKIP_ACCOUNTS=skip_mobiles)
        for capi_call in capi_calls:
            capi_call.update_status = status
        put_and_invalidate_cache(*capi_calls)
        return request.friend


    status_is_added_or_removed = status in (UpdateFriendRequestTO.STATUS_ADD, UpdateFriendRequestTO.STATUS_DELETE)
    if bump_friend_map_generation:
        friend_map.generation += 1
        if status_is_added_or_removed:
            friend_map.version += 1
        friend_map.put()

    friend = convert_friend()

    # Recent mobiles expect an UpdateFriendSetRequest when a friend is added or removed
    if status_is_added_or_removed:
        user_profile = get_user_profile(target_user)
        if user_profile and user_profile.mobiles:
            for target_mobile_detail in user_profile.mobiles:
                target_mobile = get_mobile_by_account(target_mobile_detail.account)
                update_friend_set(friend, target_mobile)
        return friend
    else:
        return update_friend(friend, None)


def _update_service_friends(friend_service_identity_connection_keys, user_profile_key):
    def trans():
        user_profile = db.get(user_profile_key)
        friend_service_identity_connections = db.get(friend_service_identity_connection_keys)
        for fsic in friend_service_identity_connections:
            fsic.friend_name = user_profile.name
            fsic.friend_avatarId = user_profile.avatarId
            fsic.birthdate = user_profile.birthdate
            fsic.gender = user_profile.gender
        db.put(friend_service_identity_connections)
        return user_profile, friend_service_identity_connections

    user_profile, fsics = db.run_in_transaction(trans)

    from rogerthat.service.api import friends
    user_details = UserDetailsTO.fromUserProfile(user_profile)

    service_api_callbacks = list()
    service_users = set((get_service_user_from_service_identity_user(fsic.service_identity_user) for fsic in fsics))
    for service_profile in get_service_profiles((u for u in service_users)):
        context = friends.update(friend_update_response_receiver, logServiceError, service_profile,
                                 user_details=user_details, DO_NOT_SAVE_RPCCALL_OBJECTS=True)
        if context:
            service_api_callbacks.append(context)
    logging.info('sending friend.update to %s/%s services', len(service_api_callbacks), len(service_users))
    db.put(service_api_callbacks)
