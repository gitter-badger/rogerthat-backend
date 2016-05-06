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

from rogerthat.dal import parent_key, generator
from rogerthat.rpc import users
from google.appengine.ext import db
from mcfw.rpc import returns, arguments


class Friend(db.Model):
    shareLastLocation = db.BooleanProperty()
    sharesLastLocation = db.BooleanProperty()
    processed = db.BooleanProperty()
    
    def me(self):
        return users.User(self.parent_key().name())
    
    @property
    def friend(self):
        return users.User(self.key().name())
    
class FriendGeneration(db.Model):
    generation = db.IntegerProperty()

_GET_USER_FRIENDS_QUERY = Friend.gql('WHERE ANCESTOR IS :ancestor')
_GET_LAST_LOCATION_SHARING_FRIENDS = Friend.gql('WHERE ANCESTOR IS :ancestor AND sharesLastLocation = True')

@returns([Friend])
@arguments(user=users.User)
def get_user_friends(user):
    _GET_USER_FRIENDS_QUERY.bind(ancestor=parent_key(user))
    return generator(_GET_USER_FRIENDS_QUERY.run())

@returns([users.User])
@arguments(user=users.User)
def get_user_friends_users(user):
    return (f.friend for f in get_user_friends(user))

@returns(bool)
@arguments(user=users.User, friend=users.User)
def is_friend(user, friend):
    return Friend.get_by_key_name(friend.email(), parent_key(user)) != None

@returns(Friend)
@arguments(user=users.User, friend=users.User)
def get_user_friend(user, friend):
    return Friend.get_by_key_name(friend.email(), parent_key(user))

@returns([Friend])
@arguments(user=users.User)
def get_last_location_sharing_friends(user):
    _GET_LAST_LOCATION_SHARING_FRIENDS.bind(ancestor=parent_key(user))
    return generator(_GET_LAST_LOCATION_SHARING_FRIENDS.run())

@returns(FriendGeneration)
@arguments(user=users.User)
def get_friends_generation(user):
    p_key = parent_key(user)
    key_name = user.email()
    friend_generation = FriendGeneration.get_by_key_name(key_name, p_key)
    return friend_generation if friend_generation else FriendGeneration(p_key, key_name, generation=0)
