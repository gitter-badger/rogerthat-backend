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

from types import NoneType

from rogerthat.api.messaging import ackMessage as ackMessageApi, lockMessage as lockMessageApi, \
    sendMessage as sendMessageApi, submitTextLineForm as submitTextLineFormApi, \
    submitTextBlockForm as submitTextBlockFormApi, submitAutoCompleteForm as submitAutoCompleteFormApi, \
    submitSingleSelectForm as submitSingleSelectFormApi, submitMultiSelectForm as submitMultiSelectFormApi, \
    submitSingleSliderForm as submitSingleSliderFormApi, submitRangeSliderForm as submitRangeSliderFormApi, \
    submitDateSelectForm as submitDateSelectFormApi, submitPhotoUploadForm as submitPhotoUploadFormApi
from rogerthat.dal.messaging import get_messages, get_message_key, get_root_message, get_message_history, \
    get_message_thread, get_service_inbox, get_message
from rogerthat.to import MESSAGE_TYPE_MAPPING, ROOT_MESSAGE_TYPE_TO_MAPPING, MESSAGE_TYPE_TO_MAPPING
from rogerthat.to.messaging import SendMessageResponseTO, SendMessageRequestTO, AckMessageResponseTO, \
    AckMessageRequestTO, MessageTO, RootMessageTO, LockMessageResponseTO, LockMessageRequestTO, MessageReceivedResponseTO, \
    MessageReceivedRequestTO, MessageListTO, RootMessageListTO
from rogerthat.to.messaging.forms import SubmitTextLineFormResponseTO, SubmitTextLineFormRequestTO, \
    SubmitTextBlockFormResponseTO, SubmitTextBlockFormRequestTO, SubmitAutoCompleteFormResponseTO, \
    SubmitAutoCompleteFormRequestTO, SubmitSingleSelectFormResponseTO, SubmitSingleSelectFormRequestTO, \
    SubmitMultiSelectFormResponseTO, SubmitMultiSelectFormRequestTO, SubmitSingleSliderFormResponseTO, \
    SubmitSingleSliderFormRequestTO, SubmitRangeSliderFormResponseTO, SubmitRangeSliderFormRequestTO, \
    SubmitDateSelectFormResponseTO, SubmitDateSelectFormRequestTO, SubmitPhotoUploadFormResponseTO, \
    SubmitPhotoUploadFormRequestTO
from mcfw.properties import object_factory
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments


MESSAGES_BATCH_SIZE = 25

@rest("/mobi/rest/messaging/send", "post")
@returns(SendMessageResponseTO)
@arguments(request=SendMessageRequestTO)
def sendMessage(request):
    return sendMessageApi(request)

@rest("/mobi/rest/messaging/ack", "post")
@returns(AckMessageResponseTO)
@arguments(request=AckMessageRequestTO)
def ackMessage(request):
    return ackMessageApi(request)

@rest("/mobi/rest/messaging/delete_conversation", "post")
@returns(NoneType)
@arguments(parent_message_key=unicode)
def deleteConversation(parent_message_key):
    from rogerthat.bizz.messaging import delete_conversation
    from rogerthat.rpc import users
    delete_conversation(users.get_current_user(), parent_message_key)

@rest("/mobi/rest/messaging/submitTextLineForm", "post")
@returns(SubmitTextLineFormResponseTO)
@arguments(request=SubmitTextLineFormRequestTO)
def submitTextLineForm(request):
    return submitTextLineFormApi(request)

@rest("/mobi/rest/messaging/submitTextBlockForm", "post")
@returns(SubmitTextBlockFormResponseTO)
@arguments(request=SubmitTextBlockFormRequestTO)
def submitTextBlockForm(request):
    return submitTextBlockFormApi(request)

@rest("/mobi/rest/messaging/submitAutoCompleteForm", "post")
@returns(SubmitAutoCompleteFormResponseTO)
@arguments(request=SubmitAutoCompleteFormRequestTO)
def submitAutoCompleteForm(request):
    return submitAutoCompleteFormApi(request)

@rest("/mobi/rest/messaging/submitSingleSelectForm", "post")
@returns(SubmitSingleSelectFormResponseTO)
@arguments(request=SubmitSingleSelectFormRequestTO)
def submitSingleSelectForm(request):
    return submitSingleSelectFormApi(request)

@rest("/mobi/rest/messaging/submitMultiSelectForm", "post")
@returns(SubmitMultiSelectFormResponseTO)
@arguments(request=SubmitMultiSelectFormRequestTO)
def submitMultiSelectForm(request):
    return submitMultiSelectFormApi(request)

@rest("/mobi/rest/messaging/submitDateSelectForm", "post")
@returns(SubmitDateSelectFormResponseTO)
@arguments(request=SubmitDateSelectFormRequestTO)
def submitDateSelectForm(request):
    return submitDateSelectFormApi(request)

@rest("/mobi/rest/messaging/submitSingleSliderForm", "post")
@returns(SubmitSingleSliderFormResponseTO)
@arguments(request=SubmitSingleSliderFormRequestTO)
def submitSingleSliderForm(request):
    return submitSingleSliderFormApi(request)

@rest("/mobi/rest/messaging/submitRangeSliderForm", "post")
@returns(SubmitRangeSliderFormResponseTO)
@arguments(request=SubmitRangeSliderFormRequestTO)
def submitRangeSliderForm(request):
    return submitRangeSliderFormApi(request)

@rest("/mobi/rest/messaging/submitPhotoUploadForm", "post")
@returns(SubmitPhotoUploadFormResponseTO)
@arguments(request=SubmitPhotoUploadFormRequestTO)
def submitPhotoUploadForm(request):
    return submitPhotoUploadFormApi(request)

@rest("/mobi/rest/messaging/lock", "post")
@returns(LockMessageResponseTO)
@arguments(request=LockMessageRequestTO)
def lockMessage(request):
    return lockMessageApi(request)

@rest("/mobi/rest/messaging/received", "post")
@returns(MessageReceivedResponseTO)
@arguments(request=MessageReceivedRequestTO)
def messageReceived(request):
    from rogerthat.rpc import users
    user = users.get_current_user()
    from rogerthat.bizz.messaging import message_received
    message_received(user, get_message_key(request.message_key, request.message_parent_key), request.received_timestamp)

@rest("/mobi/rest/messaging/get", "get")
@returns(RootMessageListTO)
@arguments(cursor=unicode)
def getMessages(cursor):
    from rogerthat.rpc import users
    user = users.get_current_user()
    result = RootMessageListTO()
    result.messages, result.cursor = _get_messages(cursor, user)
    result.batch_size = MESSAGES_BATCH_SIZE
    return result

@rest("/mobi/rest/messaging/get_single", "post")
@returns(object_factory("message_type", MESSAGE_TYPE_TO_MAPPING))
@arguments(message_key=unicode, parent_message_key=unicode)
def getSingleMessage(message_key, parent_message_key):
    from rogerthat.rpc import users
    user = users.get_current_user()
    message = get_message(message_key, parent_message_key)
    return _convert_to_tos(user, [message])[0]

@rest("/mobi/rest/messaging/get_root_message", "get")
@returns(object_factory("message_type", ROOT_MESSAGE_TYPE_TO_MAPPING))
@arguments(message_key=unicode)
def getRootMessage(message_key):
    from rogerthat.rpc import users
    user = users.get_current_user()
    messages = get_root_message(user, message_key)
    member = user if not messages[0].sharedMembers and messages[0].sender != user else None
    message = RootMessageTO.fromMessage(messages[0], member)
    message.messages = [MessageTO.fromMessage(m, member) for m in messages[1:]]
    return message

@rest("/mobi/rest/messaging/get_service_inbox", "post")
@returns(MessageListTO)
@arguments(cursor=unicode)
def getServiceInbox(cursor):
    from rogerthat.rpc import users
    user = users.get_current_user()
    messages, cursor = get_service_inbox(user, cursor)
    result = MessageListTO()
    result.cursor = unicode(cursor)
    result.messages = _convert_to_tos(user, messages)
    return result

@rest("/mobi/rest/messaging/history", "post")
@returns(MessageListTO)
@arguments(query_param=unicode, cursor=unicode)
def getMessageHistory(query_param, cursor):
    from rogerthat.rpc import users
    user = users.get_current_user()
    member = users.User(query_param)
    messages, new_cursor, thread_sizes = get_message_history(user, member, cursor, MESSAGES_BATCH_SIZE)
    history = MessageListTO()
    messages = _convert_to_tos(user, messages, thread_sizes)
    history.messages = messages
    history.cursor = unicode(new_cursor)
    history.batch_size = MESSAGES_BATCH_SIZE
    return history

@rest("/mobi/rest/messaging/thread", "get")
@returns([MessageTO])
@arguments(thread_key=unicode)
def getMessageThread(thread_key):
    from rogerthat.rpc import users
    from rogerthat.utils import azzert
    user = users.get_current_user()
    messages = get_message_thread(thread_key)
    azzert(user in messages[0].members)  # security check
    result = list()
    for message in messages:
        member = user if not message.sharedMembers and message.sender != user else None
        message_type_descr = MESSAGE_TYPE_MAPPING[message.TYPE]
        args = [message]
        if message_type_descr.include_member_in_conversion:
            args.append(member)
        result.append(message_type_descr.model_to_conversion(*args))
    return result

@rest("/mobi/rest/messaging/mark_messages_as_read", "post")
@returns(NoneType)
@arguments(parent_message_key=unicode, message_keys=[unicode])
def markMessagesAsRead(parent_message_key, message_keys):
    from rogerthat.rpc import users
    from rogerthat.bizz.messaging import markMessagesAsRead as markMessagesAsReadBizz
    user = users.get_current_user()
    markMessagesAsReadBizz(user, parent_message_key, message_keys)

@rest("/mobi/rest/messaging/dismiss_conversation", "post")
@returns(NoneType)
@arguments(parent_message_key=unicode, message_keys=[unicode], timestamp=int)
def dismissConversation(parent_message_key, message_keys, timestamp):
    from rogerthat.rpc import users
    from rogerthat.bizz.messaging import ackMessage as ackMessageBizz
    for key in message_keys:
        ackMessageBizz(users.get_current_user(), key, None if key == parent_message_key else parent_message_key,
                       button_id=None, custom_reply=None, timestamp=timestamp)

@rest("/mobi/rest/messaging/new_photo_upload_url", "get")
@returns(unicode)
@arguments()
def newPhotoUploadUrl():
    from google.appengine.ext import blobstore
    return blobstore.create_upload_url('/mobi/message/photo_upload/post')

def _convert_to_tos(user, messageList, thread_sizes=None):
    messages = list()
    for message in messageList:
        member = user if not message.sharedMembers and message.sender != user else None
        message_type_descr = MESSAGE_TYPE_MAPPING[message.TYPE]
        args = [message]
        if message_type_descr.include_member_in_conversion:
            args.append(member)
        to_obj = message_type_descr.model_to_conversion(*args)
        if thread_sizes:
            to_obj.thread_size = thread_sizes.get(message.key().name(), 0)
        messages.append(to_obj);
    return messages

def _arrangeMessageInTree(user, messageList):
    messages = dict()
    for message in messageList:
        member = user if not message.sharedMembers and message.sender != user else None
        message_type_descr = MESSAGE_TYPE_MAPPING[message.TYPE]
        args = [message]
        if message_type_descr.include_member_in_conversion:
            args.append(member)
        if message.isRootMessage:
            messages[message.mkey] = message_type_descr.root_model_to_conversion(*args)
        else:
            messages[message.pkey].messages.append(message_type_descr.model_to_conversion(*args))

    for message in messages.values():
        message.messages = sorted(message.messages, key=lambda m:m.timestamp)

    messages = sorted(messages.values(), key=lambda m:m.threadTimestamp, reverse=True)
    return messages

def _get_messages(cursor, user):
    messageList, cursor = get_messages(user, cursor, MESSAGES_BATCH_SIZE, user_only=True)
    messages = _arrangeMessageInTree(user, messageList)
    return messages, unicode(cursor)
