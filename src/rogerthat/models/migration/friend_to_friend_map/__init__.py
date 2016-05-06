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

from rogerthat.dal import parent_key
from rogerthat.dal.friend import get_friends_map
from rogerthat.models import FriendMap
from rogerthat.models.migration.friend_to_friend_map.friends import Friend, get_user_friends, get_friends_generation
from rogerthat.models.properties.friend import FriendDetails
from google.appengine.ext import db


def convert():
    for friend in Friend.all():
        friend.processed = False
        friend.put()
    friend = Friend.all().filter("processed =", False).fetch(1)
    while friend:
        friend = friend[0]
        def run():
            friendMap = get_friends_map(friend.me())
            friendMap.delete()
            friendMap = FriendMap(\
                parent_key(friend.me()), \
                friend.me().email(), \
                generation=get_friends_generation(friend.me()).generation, \
                friends=list(), \
                friendDetails=FriendDetails())
            friends = get_user_friends(friend.me())
            for f in friends:
                friendMap.friends.append(f.friend)
                friendMap.friendDetails.addNew(f.friend, None, -1, True if f.shareLastLocation else False, True if f.sharesLastLocation else False, True)
                f.processed = True
                f.put()
            friendMap.put()
            return friendMap
        db.run_in_transaction(run)
        friend = Friend.all().filter("processed =", False).fetch(1)
