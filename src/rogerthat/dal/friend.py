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

from rogerthat.dal import parent_key, parent_key_unsafe
from rogerthat.models import FriendMap, FriendInvitationHistory, DoNotSendMeMoreInvites, FriendCategory
from rogerthat.models.properties.friend import FriendDetails
from rogerthat.rpc import users
from google.appengine.ext import db
from google.appengine.ext.db import GqlQuery
from mcfw.cache import cached
from mcfw.rpc import returns, arguments


@returns(db.Key)
@arguments(app_user=users.User)
def get_friends_map_key_by_user(app_user):
    return db.Key.from_path(FriendMap.kind(), app_user.email(), parent=parent_key(app_user))

@returns(FriendMap)
@arguments(app_user=users.User)
def get_friends_map(app_user):
    pkey = parent_key(app_user)
    name = app_user.email()
    fm = FriendMap.get_by_key_name(name, pkey)
    return fm if fm else FriendMap(pkey, name, generation=0, friends=list(), friendDetails=FriendDetails())

@cached(1, request=True, memcache=False)
@returns(FriendMap)
@arguments(app_user=users.User)
def get_friends_map_cached(app_user):
    return get_friends_map(app_user)

@returns([FriendMap])
@arguments(app_user=users.User)
def get_friends_friends_maps(app_user):
    return FriendMap.all().filter("friends =", app_user)

@returns(GqlQuery)
@arguments(app_user=users.User)
def get_friends_friends_maps_query(app_user):
    qry = FriendMap.gql("WHERE friends = :user")
    qry.bind(user=app_user)
    return qry

@returns(GqlQuery)
@arguments(app_user=users.User)
def get_friends_friends_maps_keys_query(app_user):
    qry = db.GqlQuery("SELECT __key__ FROM FriendMap WHERE friends = :user")
    qry.bind(user=app_user)
    return qry

@returns(FriendInvitationHistory)
@arguments(user=users.User, friend=users.User)
def get_friend_invitation_history(user, friend):
    return FriendInvitationHistory.get_by_key_name(friend.email(), parent_key_unsafe(user))

@returns(FriendInvitationHistory)
@arguments(key=unicode)
def get_friend_invitation_history_by_last_attempt_key(key):
    return FriendInvitationHistory.all().filter("lastAttemptKey =", key).get()

@returns(DoNotSendMeMoreInvites)
@arguments(user=users.User)
def get_do_send_email_invitations(user):
    return DoNotSendMeMoreInvites.get_by_key_name(user.email())


@returns([FriendCategory])
@arguments()
def get_friend_categories():
    return sorted(FriendCategory.all(), key=lambda x: x.name.lower())

@returns(FriendCategory)
@arguments(category_id=unicode)
def get_friend_category_by_id(category_id):
    return FriendCategory.get_by_key_name(category_id)
