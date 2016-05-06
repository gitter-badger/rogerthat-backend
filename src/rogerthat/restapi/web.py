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

from rogerthat.dal.friend import get_friends_map_key_by_user
from rogerthat.dal.messaging import get_messages_query, get_service_inbox_query
from rogerthat.dal.mobile import get_user_active_mobiles_count
from rogerthat.dal.profile import get_user_profile_key, get_avatar_by_id
from rogerthat.restapi.messaging import MESSAGES_BATCH_SIZE
from rogerthat.rpc import users
from rogerthat.to import MESSAGE_TYPE_MAPPING
from rogerthat.to.friends import FriendTO
from rogerthat.to.messaging import MessageListTO, RootMessageListTO
from rogerthat.to.profile import UserProfileTO
from rogerthat.to.system import UserStatusTO
from rogerthat.to.web import WebTO
from google.appengine.datastore import datastore_query
from google.appengine.ext import db
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments


@rest("/mobi/rest/web/load", "get")
@returns(WebTO)
@arguments()
def load_web():
    user = users.get_current_user()

    profile_key = get_user_profile_key(user)
    friends_map_key = get_friends_map_key_by_user(user)

    async_get = db.get_async([profile_key, friends_map_key])

    messages_query = get_messages_query(app_user=user, cursor=None, user_only=True)
    messages_iterator = messages_query.run(config=datastore_query.QueryOptions(limit=MESSAGES_BATCH_SIZE))

    service_inbox_query = get_service_inbox_query(user, None)
    service_inbox_iterator = service_inbox_query.run(config=datastore_query.QueryOptions(limit=MESSAGES_BATCH_SIZE))

    profile, friends_map = async_get.get_result()

    def convert_to_transferobject(message):
        member = user if not message.sharedMembers and message.sender != user else None
        message_type_descr = MESSAGE_TYPE_MAPPING[message.TYPE]
        args = [message]
        if message_type_descr.include_member_in_conversion:
            args.append(member)
        if message.isRootMessage:
            return message_type_descr.root_model_to_conversion(*args)
        else:
            return message_type_descr.model_to_conversion(*args)

    messages = list()
    async_child_messages = list()
    for parent_message in messages_iterator:
        messages.append(convert_to_transferobject(parent_message))
        async_child_messages.append(db.get_async(parent_message.childMessages))

    for i in xrange(len(messages)):
        messages[i].messages = [convert_to_transferobject(cm) for cm in async_child_messages[i].get_result()]

    user_status = UserStatusTO()
    user_status.profile = UserProfileTO.fromUserProfile(profile)
    avatar = get_avatar_by_id(profile.avatarId)
    user_status.has_avatar = bool(avatar and avatar.picture)
    user_status.registered_mobile_count = get_user_active_mobiles_count(user)

    message_screen_to = RootMessageListTO()
    message_screen_to.messages = messages
    message_screen_to.cursor = unicode(messages_query.cursor())
    message_screen_to.batch_size = MESSAGES_BATCH_SIZE

    service_inbox_to = MessageListTO()
    service_inbox_to.messages = [convert_to_transferobject(m) for m in service_inbox_iterator]
    service_inbox_to.cursor = unicode(service_inbox_query.cursor())
    service_inbox_to.batch_size = MESSAGES_BATCH_SIZE

    result = WebTO()
    result.friends = [FriendTO.fromDBFriendDetail(f) for f in friends_map.friendDetails] if friends_map else []
    result.user_status = user_status
    result.messages = message_screen_to
    result.service_inbox = service_inbox_to

    return result
