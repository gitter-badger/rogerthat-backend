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

from google.appengine.ext import db

from mcfw.cache import cached, get_from_request_cache, add_to_request_cache
from mcfw.consts import MISSING
from mcfw.rpc import returns, arguments
from rogerthat.consts import MC_DASHBOARD
from rogerthat.dal import parent_key
from rogerthat.dal.service import get_service_identity, get_default_service_identity, get_service_identity_not_cached, \
    get_default_service_identity_not_cached
from rogerthat.models import ProfileInfo, Profile, Avatar, TrialServiceAccount, FacebookProfilePointer, SearchConfig, \
    SearchConfigLocation, UserProfile, ServiceProfile, ServiceIdentity, UserProfileArchive, FacebookUserProfileArchive, App
from rogerthat.rpc import users
from rogerthat.utils import azzert, get_python_stack_trace
from rogerthat.utils.app import get_app_id_from_app_user
from rogerthat.utils.service import add_slash_default


@returns([bool])
@arguments(existing_users=[users.User])
def are_service_identity_users(existing_users):
    # XXX: try to get stuff from get_service_identity cache
    #       retrieve remaining from datastore in 1 multiget: get_service_identities_not_cached
    return [isinstance(p, ServiceIdentity) for p in get_profile_infos(existing_users)]

@returns(bool)
@arguments(existing_user=users.User)
def is_service_identity_user(existing_user):
    return get_service_identity(add_slash_default(existing_user)) is not None

@returns(ProfileInfo)
@arguments(user=users.User, cached=bool, skip_warning=bool)
def get_profile_info(user, cached=True, skip_warning=False):
    '''Returns a ProfileInfo (UserProfile or ServiceIdentity)'''
    if "/" in user.email():
        return get_service_identity(user) if cached else get_service_identity_not_cached(user)
    profile = _get_profile(user) if cached else _get_profile_not_cached(user)
    if not profile or isinstance(profile, UserProfile):
        return profile
    if not skip_warning:
        logging.warn("Implicit retrieving default ServiceIdentity for %s\n%s" % (user.email(), get_python_stack_trace(short=True)))
    return get_default_service_identity(user) if cached else get_default_service_identity_not_cached(user)

@returns([Profile])
@arguments(users=[users.User])
def get_profiles(users):
    return db.get([get_profile_key(u) for u in users])

@returns([UserProfile])
@arguments(users=[users.User])
def get_user_profiles(users):
    profiles = get_profiles(users)
    azzert(not [True for p in profiles if not isinstance(p, UserProfile)])
    return profiles

@returns(UserProfile)
@arguments(app_user=users.User, cached=bool)
def get_user_profile(app_user, cached=True):
    user_profile = _get_profile(app_user) if cached else _get_profile_not_cached(app_user)
    azzert(user_profile is None or isinstance(user_profile, UserProfile))
    return user_profile

@returns(ServiceProfile)
@arguments(user=users.User, cached=bool)
def get_service_profile(user, cached=True):
    azzert("/" not in user.email())
    service_profile = _get_profile(user) if cached else _get_profile_not_cached(user)
    azzert(service_profile is None or isinstance(service_profile, ServiceProfile))
    return service_profile

@returns([ServiceProfile])
@arguments(users=[users.User])
def get_service_profiles(users):
    profiles = get_profiles(users)
    azzert(not [True for p in profiles if not isinstance(p, ServiceProfile)])
    return profiles

@returns(Profile)
@arguments(user=users.User, cached=bool)
def get_service_or_user_profile(user, cached=True):
    if cached:
        return _get_profile(user)
    else:
        return _get_profile_not_cached(user)

@returns((UserProfileArchive, FacebookUserProfileArchive))
@arguments(app_user=users.User)
def get_deactivated_user_profile(app_user):
    user_profile = UserProfileArchive.get_by_key_name(app_user.email(), parent_key(app_user))
    if user_profile:
        return user_profile
    else:
        return FacebookUserProfileArchive.get_by_key_name(app_user.email(), parent_key(app_user))


@cached(1, request=True, lifetime=0)
@returns(Profile)
@arguments(user=users.User)
def _get_profile(user):
    return _get_profile_not_cached(user)

@returns(Profile)
@arguments(user=users.User)
def _get_profile_not_cached(user):
    if user == MC_DASHBOARD:
        logging.warn("Retrieving profile of MC_DASHBOARD\n%s" % get_python_stack_trace(short=True))
        return None
    # XXX: populate cache
    return Profile.get_by_key_name(user.email(), parent_key(user))

@returns(db.Key)
@arguments(user=users.User)
def get_profile_key(user):
    return Profile.createKey(user)

@returns(db.Key)
@arguments(app_user=users.User)
def get_user_profile_key(app_user):
    return get_profile_key(app_user)

@returns(db.Query)
@arguments(app_id=unicode)
def get_user_profile_keys_by_app_id(app_id):
    return UserProfile.all(keys_only=True).filter('app_id =', app_id)

@returns(db.Query)
@arguments(app_id=unicode)
def get_user_profiles_by_app_id(app_id):
    return UserProfile.all().filter('app_id =', app_id)

def _validate_profile_info_types(expected_types, entries):
    if expected_types is None:
        return
    azzert(len(expected_types) == len(entries))
    for expected_type, entry in zip(expected_types, entries):
        if entry is None:
            continue
        azzert(isinstance(entry, expected_type),
               "%s (%s) is not of expected type %s" % (entry.user.email(), entry.__class__.__name__, expected_type))

@returns([(ProfileInfo, NoneType)])
@arguments(users_=[users.User], update_request_cache=bool, update_mem_cache=bool, allow_none_in_results=bool,
           expected_types=list)
def get_profile_infos(users_, update_request_cache=True, update_mem_cache=True, allow_none_in_results=False,
                      expected_types=None):
    if db.is_in_transaction():
        r = _get_profile_infos_not_cached(users_)
        if not allow_none_in_results:
            azzert(None not in r, "There is no ProfileInfo for %s" % [k for k, v in zip(users_, r) if v is None])
        _validate_profile_info_types(expected_types, r)
        return r

    profile_infos = dict()
    # First try request cache
    cache_misses = False
    for user in users_:
        result = get_from_request_cache(_get_profile.cache_key(user)) if '/' not in user.email() else MISSING
        if result == MISSING or not result[0] or isinstance(result[1], ServiceProfile):
            # Lets try the ServiceIdentity cache
            f = get_service_identity
            result = get_from_request_cache(f.cache_key(user))
        if result == MISSING or not result[0]:
            cache_misses = True
            profile_infos[user] = None
        else:
            profile_infos[user] = result[1]
    if not cache_misses:
        r = [profile_infos[u] for u in users_]  # Keep original order
        if not allow_none_in_results:
            azzert(None not in r)
        _validate_profile_info_types(expected_types, r)
        return r

    remaining_profile_infos_to_get = [user for user, profile_info in profile_infos.iteritems() if profile_info is None]
    if len(remaining_profile_infos_to_get) == 0:
        r = [profile_infos[u] for u in users_]  # Keep original order
        _validate_profile_info_types(expected_types, r)
        return r

    remaining_profile_infos = _get_profile_infos_not_cached(remaining_profile_infos_to_get)
    for i in xrange(len(remaining_profile_infos_to_get)):
        profile_info = remaining_profile_infos[i]
        if profile_info is None:
            continue
        profile_infos[remaining_profile_infos_to_get[i]] = profile_info
        if update_request_cache:
            f = get_service_identity if profile_info.isServiceIdentity else _get_profile
            cache_key = f.cache_key(profile_info.user)
            add_to_request_cache(cache_key, True, profile_info)
            if profile_info.isServiceIdentity and profile_info.is_default:
                cache_key2 = f.cache_key(profile_info.service_user)
                add_to_request_cache(cache_key2, True, profile_info)

    r = [profile_infos[u] for u in users_]  # Keep original order
    if not allow_none_in_results:
        azzert(None not in r)
    _validate_profile_info_types(expected_types, r)
    return r

@returns([(ProfileInfo, NoneType)])
@arguments(users_=[users.User])
def _get_profile_infos_not_cached(users_):  # XXX: make smarter since users of this function often know what type to expect
    keys = list()
    for user in users_:
        if "/" in user.email():
            keys.append(ServiceIdentity.keyFromUser(user))
        else:  # Could be human or service users
            keys.append(get_user_profile_key(user))

    result = db.get(keys)
    for i in xrange(len(result)):
        r = result[i]
        if "/" not in users_[i].email() and (r is None or isinstance(r, ServiceProfile)):
            # profile did not exist or was a default identity.
            result[i] = get_default_service_identity(users_[i])  # XXX: we could make this smarter

    # XXX: populate cache
    return result

@returns([tuple])
@arguments(facebook_ids=[unicode], app_id=unicode)
def get_existing_profiles_via_facebook_ids(facebook_ids, app_id=App.APP_ID_ROGERTHAT):
    fpps = (db.Key.from_path(FacebookProfilePointer.kind(), str(fid)) for fid in facebook_ids)
    i = 0
    lst = []
    qrys = []
    for fpp in fpps:
        i += 1
        lst.append(fpp)
        if i == 10:
            qrys.append(db.get_async(lst))
            lst = []
            i = 0
    if i > 0:
        qrys.append(db.get_async(lst))
    def list_sequential():
        for qry in qrys:
            for item in qry.get_result():
                yield item
    matches = []
    for fpp in list_sequential():
        if fpp and get_app_id_from_app_user(fpp.user) == app_id:
            matches.append((fpp.facebookId, fpp.user))
    return matches

@returns([UserProfile])
@arguments(users_=[users.User])
def get_existing_user_profiles(users_):
    # XXX: populate cache
    return [p for p in Profile.get(map(lambda u: db.Key.from_path(Profile.kind(), u.email(), parent=parent_key(u)), users_))
            if p and isinstance(p, UserProfile)]

@returns(Avatar)
@arguments(id_=int)
def get_avatar_by_id(id_):
    return Avatar.get_by_id(id_)

@returns(bool)
@arguments(user=users.User)
def user_has_avatar(user):
    profile = _get_profile(user)
    if not profile:
        return False
    avatarId = -1 if not profile or not profile.avatarId else profile.avatarId
    if avatarId == -1:
        return False
    avatar = get_avatar_by_id(avatarId)
    return not (not avatar or not avatar.picture)

@returns(TrialServiceAccount)
@arguments(user=users.User)
def get_trial_service_by_owner(user):
    return TrialServiceAccount.all().filter("owner =", user).get()

@returns(TrialServiceAccount)
@arguments(service_user=users.User)
def get_trial_service_by_account(service_user):
    return TrialServiceAccount.all().filter("service =", service_user).get()

@returns(bool)
@arguments(service_user=users.User)
def is_trial_service(service_user):
    def _is_trial_service():
        return TrialServiceAccount.all().filter("service =", service_user).get() is not None

    if db.is_in_transaction():
        @db.non_transactional
        def non_transactional():
            return _is_trial_service()
        return non_transactional()

    return _is_trial_service()

@returns(tuple)  # return config & locations
@arguments(service_identity_user=users.User)
def get_search_config(service_identity_user):
    sc_key = SearchConfig.create_key(service_identity_user)
    sc = db.get(sc_key)
    if not sc:
        sc = SearchConfig(key=sc_key, enabled=False)
    return (sc, get_search_locations(service_identity_user))

@returns([SearchConfigLocation])
@arguments(service_identity_user=users.User)
def get_search_locations(service_identity_user):
    sc_key = SearchConfig.create_key(service_identity_user)
    return list(SearchConfigLocation.all().ancestor(sc_key))

@returns([FacebookProfilePointer])
@arguments(app_user=users.User)
def get_all_facebook_profile_pointers(app_user):
    return FacebookProfilePointer.all().filter("user =", app_user).fetch(None)
