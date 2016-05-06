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

from mcfw.consts import MISSING
from mcfw.rpc import returns, arguments
from rogerthat.models import Message
from rogerthat.rpc.rpc import expose
from rogerthat.to import WIDGET_MAPPING
from rogerthat.to.messaging import SendMessageResponseTO, SendMessageRequestTO, AckMessageRequestTO, \
    AckMessageResponseTO, LockMessageResponseTO, LockMessageRequestTO, DirtyBehavior, UserMemberTO, \
    MarkMessagesAsReadResponseTO, MarkMessagesAsReadRequestTO, DeleteConversationResponseTO, \
    DeleteConversationRequestTO, \
    GetConversationResponseTO, GetConversationRequestTO, UploadChunkResponseTO, UploadChunkRequestTO, \
    GetConversationAvatarResponseTO, GetConversationAvatarRequestTO
from rogerthat.to.messaging.forms import SubmitTextLineFormRequestTO, SubmitTextBlockFormRequestTO, \
    SubmitAutoCompleteFormRequestTO, SubmitSingleSelectFormRequestTO, SubmitMultiSelectFormRequestTO, \
    SubmitSingleSliderFormRequestTO, SubmitRangeSliderFormRequestTO, SubmitTextLineFormResponseTO, \
    SubmitTextBlockFormResponseTO, SubmitAutoCompleteFormResponseTO, SubmitSingleSelectFormResponseTO, \
    SubmitMultiSelectFormResponseTO, SubmitSingleSliderFormResponseTO, SubmitRangeSliderFormResponseTO, \
    SubmitDateSelectFormResponseTO, SubmitDateSelectFormRequestTO, TextLineTO, TextBlockTO, AutoCompleteTO, \
    SingleSelectTO, \
    MultiSelectTO, DateSelectTO, SingleSliderTO, RangeSliderTO, SubmitPhotoUploadFormResponseTO, \
    SubmitPhotoUploadFormRequestTO, PhotoUploadTO, SubmitGPSLocationFormResponseTO, \
    SubmitGPSLocationFormRequestTO, GPSLocationTO, MyDigiPassTO, SubmitMyDigiPassFormResponseTO, \
    SubmitMyDigiPassFormRequestTO, AdvancedOrderTO, SubmitAdvancedOrderFormResponseTO, SubmitAdvancedOrderFormRequestTO
from rogerthat.utils import try_or_defer
from rogerthat.utils.app import create_app_user, get_app_id_from_app_user
from rogerthat.utils.service import add_slash_default


@expose(('api',))
@returns(SendMessageResponseTO)
@arguments(request=SendMessageRequestTO)
def sendMessage(request):
    from rogerthat.bizz.messaging import sendMessage as sendMessageBizz
    from rogerthat.rpc import users

    sender = users.get_current_user()
    user_members = [UserMemberTO(create_app_user(users.User(m), get_app_id_from_app_user(sender)))
                    for m in request.members]
    attachments = list() if request.attachments is MISSING else request.attachments
    message = sendMessageBizz(sender, user_members, request.flags, request.timeout, request.parent_key, request.message,
                              request.buttons, request.sender_reply, None, None, is_mfr=False, attachments=attachments,
                              priority=Message.PRIORITY_NORMAL if request.priority is MISSING else request.priority)
    response = SendMessageResponseTO()
    response.key = message.mkey
    response.timestamp = message.creationTimestamp
    return response


@expose(('api',))
@returns(AckMessageResponseTO)
@arguments(request=AckMessageRequestTO)
def ackMessage(request):
    from rogerthat.bizz.messaging import ackMessage as ackMessageBizz
    from rogerthat.rpc import users

    responder = users.get_current_user()
    result = AckMessageResponseTO()
    result.result = ackMessageBizz(responder, request.message_key, request.parent_message_key, request.button_id, \
                                   request.custom_reply, request.timestamp)
    return result


@expose(('api',))
@returns(MarkMessagesAsReadResponseTO)
@arguments(request=MarkMessagesAsReadRequestTO)
def markMessagesAsRead(request):
    from rogerthat.bizz.messaging import markMessagesAsRead as markMessagesAsReadBizz
    from rogerthat.rpc import users

    markMessagesAsReadBizz(users.get_current_user(), request.parent_message_key, request.message_keys,
                           users.get_current_mobile())
    return MarkMessagesAsReadResponseTO()


@expose(('api',))
@returns(LockMessageResponseTO)
@arguments(request=LockMessageRequestTO)
def lockMessage(request):
    from rogerthat.bizz.messaging import lockMessage as lockMessageBizz
    from rogerthat.rpc import users

    user = users.get_current_user()
    message = lockMessageBizz(user, request.message_key, request.message_parent_key, DirtyBehavior.NORMAL)
    return LockMessageResponseTO.fromMessage(message)


def _submitForm(request, form_type):
    from rogerthat.bizz.messaging import submitForm as submitFormBizz
    from rogerthat.rpc import users

    response = WIDGET_MAPPING[form_type].submit_resp_to_type()
    response.result = submitFormBizz(users.get_current_user(), request.message_key, request.parent_message_key, \
                                     request.button_id, request.result, request.timestamp, form_type)
    return response


@expose(('api',))
@returns(SubmitTextLineFormResponseTO)
@arguments(request=SubmitTextLineFormRequestTO)
def submitTextLineForm(request):
    return _submitForm(request, TextLineTO.TYPE)


@expose(('api',))
@returns(SubmitTextBlockFormResponseTO)
@arguments(request=SubmitTextBlockFormRequestTO)
def submitTextBlockForm(request):
    return _submitForm(request, TextBlockTO.TYPE)


@expose(('api',))
@returns(SubmitAutoCompleteFormResponseTO)
@arguments(request=SubmitAutoCompleteFormRequestTO)
def submitAutoCompleteForm(request):
    return _submitForm(request, AutoCompleteTO.TYPE)


@expose(('api',))
@returns(SubmitSingleSelectFormResponseTO)
@arguments(request=SubmitSingleSelectFormRequestTO)
def submitSingleSelectForm(request):
    return _submitForm(request, SingleSelectTO.TYPE)


@expose(('api',))
@returns(SubmitMultiSelectFormResponseTO)
@arguments(request=SubmitMultiSelectFormRequestTO)
def submitMultiSelectForm(request):
    return _submitForm(request, MultiSelectTO.TYPE)


@expose(('api',))
@returns(SubmitDateSelectFormResponseTO)
@arguments(request=SubmitDateSelectFormRequestTO)
def submitDateSelectForm(request):
    return _submitForm(request, DateSelectTO.TYPE)


@expose(('api',))
@returns(SubmitSingleSliderFormResponseTO)
@arguments(request=SubmitSingleSliderFormRequestTO)
def submitSingleSliderForm(request):
    return _submitForm(request, SingleSliderTO.TYPE)


@expose(('api',))
@returns(SubmitRangeSliderFormResponseTO)
@arguments(request=SubmitRangeSliderFormRequestTO)
def submitRangeSliderForm(request):
    return _submitForm(request, RangeSliderTO.TYPE)


@expose(('api',))
@returns(SubmitPhotoUploadFormResponseTO)
@arguments(request=SubmitPhotoUploadFormRequestTO)
def submitPhotoUploadForm(request):
    return _submitForm(request, PhotoUploadTO.TYPE)


@expose(('api',))
@returns(SubmitGPSLocationFormResponseTO)
@arguments(request=SubmitGPSLocationFormRequestTO)
def submitGPSLocationForm(request):
    return _submitForm(request, GPSLocationTO.TYPE)


@expose(('api',))
@returns(SubmitMyDigiPassFormResponseTO)
@arguments(request=SubmitMyDigiPassFormRequestTO)
def submitMyDigiPassForm(request):
    return _submitForm(request, MyDigiPassTO.TYPE)


@expose(('api',))
@returns(SubmitAdvancedOrderFormResponseTO)
@arguments(request=SubmitAdvancedOrderFormRequestTO)
def submitAdvancedOrderForm(request):
    return _submitForm(request, AdvancedOrderTO.TYPE)


@expose(('api',))
@returns(DeleteConversationResponseTO)
@arguments(request=DeleteConversationRequestTO)
def deleteConversation(request):
    from rogerthat.bizz.messaging import delete_conversation
    from rogerthat.rpc import users
    try_or_defer(delete_conversation, users.get_current_user(), request.parent_message_key)
    return DeleteConversationResponseTO()


@expose(('api',))
@returns(GetConversationAvatarResponseTO)
@arguments(request=GetConversationAvatarRequestTO)
def getConversationAvatar(request):
    from rogerthat.bizz.messaging import get_conversation_avatar
    from rogerthat.rpc import users
    avatar = get_conversation_avatar(users.get_current_user(), request.thread_key, request.avatar_hash)
    response = GetConversationAvatarResponseTO()
    response.avatar = unicode(base64.b64encode(avatar)) if avatar else None
    return response


@expose(('api',))
@returns(GetConversationResponseTO)
@arguments(request=GetConversationRequestTO)
def getConversation(request):
    from rogerthat.bizz.messaging import get_conversation
    from rogerthat.rpc import users
    response = GetConversationResponseTO()
    response.conversation_sent = get_conversation(users.get_current_user(),
                                                  request.parent_message_key,
                                                  None if request.offset is MISSING else request.offset)
    return response


@expose(('api',))
@returns(UploadChunkResponseTO)
@arguments(request=UploadChunkRequestTO)
def uploadChunk(request):
    from rogerthat.rpc import users
    from rogerthat.bizz.messaging import store_chunk
    service_identity_user = add_slash_default(
        users.User(request.service_identity_user)) if request.service_identity_user else None
    store_chunk(users.get_current_user(), service_identity_user,
                request.parent_message_key, request.message_key, request.total_chunks, request.number, request.chunk,
                request.photo_hash, None if request.content_type is MISSING else request.content_type)
    return UploadChunkResponseTO()
