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

from google.appengine.ext import db

from rogerthat.dal import generator
from rogerthat.models import Message, Branding, TransferResult, TransferChunk, ThreadAvatar
from rogerthat.models.properties.friend import FriendDetail
from rogerthat.rpc import users
from rogerthat.utils import azzert
from rogerthat.utils.service import remove_slash_default
from mcfw.cache import cached
from mcfw.rpc import returns, arguments


GET_UNREAD_MESSAGES_JOB_GQL = lambda: Message.gql("WHERE member_status_index = '%s' AND creationTimestamp > :from_ AND creationTimestamp <= :to ORDER BY creationTimestamp DESC" % Message.MEMBER_INDEX_STATUS_NOT_RECEIVED)

@returns(db.GqlQuery)
@arguments(app_user=users.User, cursor=unicode, user_only=bool)
def get_messages_query(app_user, cursor, user_only):
    if user_only:
        qry = Message.gql("WHERE member_status_index = :member AND sender_type = :sender_type AND timestamp > 0 ORDER BY timestamp DESC")
        qry.bind(member=Message.statusIndexValue(app_user, Message.MEMBER_INDEX_STATUS_NOT_DELETED), sender_type=FriendDetail.TYPE_USER)
    else:
        qry = Message.gql("WHERE member_status_index = :member AND timestamp > 0 ORDER BY timestamp DESC")
        qry.bind(member=Message.statusIndexValue(app_user, Message.MEMBER_INDEX_STATUS_NOT_DELETED))
    qry.with_cursor(cursor)
    return qry

@returns(tuple)
@arguments(app_user=users.User, cursor=unicode, count=int, user_only=bool)
def get_messages(app_user, cursor, count, user_only=False):
    qry = get_messages_query(app_user, cursor, user_only)
    messages = qry.fetch(count)
    child_messages = list()
    for m in messages:
        for key in m.childMessages:
            child_messages.append(key)
    for m in db.get(child_messages):
        messages.append(m)
    return messages, qry.cursor()

@returns(db.GqlQuery)
@arguments(app_user=users.User, cursor=unicode)
def get_service_inbox_query(app_user, cursor):
    qry = Message.gql("WHERE member_status_index = :member AND sender_type = :sender_type ORDER BY creationTimestamp DESC")
    qry.bind(member=Message.statusIndexValue(app_user, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX),
             sender_type=FriendDetail.TYPE_SERVICE)
    qry.with_cursor(cursor)
    return qry

@returns(db.GqlQuery)
@arguments(service_identity_user=users.User, user=users.User, cursor=unicode)
def get_service_user_inbox_keys_query(service_identity_user, user, cursor):
    qry = db.GqlQuery("SELECT __key__ FROM Message WHERE member_status_index = :member AND member_status_index = :service")
    qry.bind(member=Message.statusIndexValue(user, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX),
             service=remove_slash_default(service_identity_user).email())
    qry.with_cursor(cursor)
    return qry

@returns(tuple)
@arguments(app_user=users.User, cursor=unicode)
def get_service_inbox(app_user, cursor):
    qry = get_service_inbox_query(app_user, cursor)
    return qry.fetch(50), qry.cursor()

@returns(int)
@arguments(app_user=users.User)
def get_messages_count(app_user):
    qry = Message.gql("WHERE member_status_index = :member ORDER BY timestamp DESC")
    qry.bind(member=app_user.email())
    return qry.count()

@returns([Message])
@arguments(app_user=users.User, message_key=unicode)
def get_root_message(app_user, message_key):
    root_message = get_message(message_key, None)
    azzert(app_user in root_message.members)
    return [root_message] + db.get(root_message.childMessages)

@returns([Message])
@arguments(app_user=users.User, message_keys=[unicode])
def get_root_messages(app_user, message_keys):
    messages = db.get([get_message_key(message_key, None) for message_key in message_keys])
    messages.extend(get_child_messages(app_user, messages))
    return messages

@returns([Message])
@arguments(app_user=users.User, parent_messages=[Message])
def get_child_messages(app_user, parent_messages):
    child_messages = list()
    for m in parent_messages:
        azzert(app_user in m.members)
        for key in m.childMessages:
            child_messages.append(key)
    return db.get(child_messages)

@returns(db.Key)
@arguments(message_key=unicode, message_parent_key=unicode)
def get_message_key(message_key, message_parent_key):
    if (message_parent_key):
        return db.Key.from_path(Message.kind(), message_parent_key, Message.kind(), message_key)
    else:
        return db.Key.from_path(Message.kind(), message_key)

@returns(Message)
@arguments(message_key=unicode, message_parent_key=unicode)
def get_message(message_key, message_parent_key):
    return Message.get(get_message_key(message_key, message_parent_key))

@cached(1, memcache=False)
@returns(Branding)
@arguments(hash_=unicode)
def get_branding(hash_):
    return Branding.get_by_key_name(hash_)

@returns(tuple)
@arguments(app_user=users.User, filtered_member=users.User, cursor=unicode, batch_size=int)
def get_message_history(app_user, filtered_member, cursor, batch_size):
    qry = Message.gql("WHERE member_status_index = :status_index AND member_status_index = :filtered_member ORDER BY timestamp DESC")
    qry.bind(status_index=Message.statusIndexValue(app_user, Message.MEMBER_INDEX_STATUS_NOT_DELETED),
             filtered_member=remove_slash_default(filtered_member).email())
    qry.with_cursor(cursor)
    messages = qry.fetch(batch_size)
    messages = filter(lambda m:m.timestamp > 0, messages)
    child_messages = list()
    thread_length = dict()
    for m in messages:
        if m.childMessages:
            child_messages.append(m.childMessages[-1])
            thread_length[m.childMessages[-1].name()] = len(m.childMessages) + 1
        else:
            child_messages.append(m.key())
            thread_length[m.key().name()] = 1
    messages = db.get(child_messages)
    messages = sorted(messages, key=lambda m: abs(m.timestamp), reverse=True)
    return messages, qry.cursor(), thread_length

@returns([Message])
@arguments(thread_key=unicode)
def get_message_thread(thread_key):
    pm = Message.get_by_key_name(thread_key)
    messages = db.get(pm.childMessages)
    messages.append(pm)
    return sorted(messages, key=lambda m: abs(m.creationTimestamp))

@returns(TransferResult)
@arguments(parent_message_key=unicode, message_key=unicode)
def get_transfer_result(parent_message_key, message_key):
    return TransferResult.get(TransferResult.create_key(parent_message_key, message_key))

@returns([TransferChunk])
@arguments(transfer_result_key=db.Key)
def get_transfer_chunks(transfer_result_key):
    return generator(TransferChunk.all().ancestor(transfer_result_key).order("number").run(batch_size=10))

@returns(int)
@arguments(transfer_result_key=db.Key)
def count_transfer_chunks(transfer_result_key):
    return TransferChunk.all().ancestor(transfer_result_key).count()


@returns(ThreadAvatar)
@arguments(parent_message_key=unicode)
def get_thread_avatar(parent_message_key):
    return ThreadAvatar.get(ThreadAvatar.create_key(parent_message_key))
