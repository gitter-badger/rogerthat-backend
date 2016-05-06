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
from types import NoneType

from mcfw.consts import MISSING
from mcfw.properties import object_factory
from mcfw.rpc import arguments, returns
from rogerthat.bizz.messaging import ChatFlags as ChatFlagsBizz
from rogerthat.dal.mfd import get_message_flow_run_record
from rogerthat.dal.service import get_service_identity
from rogerthat.models import Message, ServiceProfile, ServiceIdentity
from rogerthat.models.properties.forms import FormResult
from rogerthat.rpc import users
from rogerthat.rpc.service import service_api, service_api_callback
from rogerthat.rpc.users import get_current_user
from rogerthat.to.messaging import AnswerTO, MemberTO, AttachmentTO, BroadcastTargetAudienceTO, KeyValueTO, \
    BroadcastResultTO, ChatMessageListResultTO
from rogerthat.to.messaging.flow import FLOW_STEP_MAPPING, FormFlowStepTO
from rogerthat.to.messaging.forms import FormTO
from rogerthat.to.messaging.service_callback_results import PokeCallbackResultTO, MessageAcknowledgedCallbackResultTO, \
    FormAcknowledgedCallbackResultTO, FlowMemberResultCallbackResultTO
from rogerthat.to.service import UserDetailsTO
from rogerthat.utils import azzert, try_or_defer
from rogerthat.utils.app import create_app_user
from rogerthat.utils.service import create_service_identity_user


ChatFlags = ChatFlagsBizz  # Prevent unused import warning

@service_api(function=u"messaging.send")
@returns(unicode)
@arguments(parent_key=unicode, parent_message_key=unicode, message=unicode, answers=[AnswerTO],
           flags=int, members=[(unicode, MemberTO)], branding=unicode, tag=unicode, service_identity=unicode,
           alert_flags=int, dismiss_button_ui_flags=int, context=unicode, attachments=[AttachmentTO],
           broadcast_guid=unicode, step_id=unicode)
def send(parent_key, parent_message_key, message, answers, flags, members, branding, tag,
         service_identity=None, alert_flags=Message.ALERT_FLAG_VIBRATE, dismiss_button_ui_flags=0, context=None,
         attachments=None, broadcast_guid=None, step_id=None):
    from rogerthat.bizz.messaging import sendMessage, member_list_to_usermember_list
    from rogerthat.bizz.service import get_and_validate_service_identity_user

    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    mm = member_list_to_usermember_list(service_identity_user, members, alert_flags)

    flags &= ~Message.FLAG_SENT_BY_JS_MFR
    flags &= ~Message.FLAG_DYNAMIC_CHAT
    flags &= ~Message.FLAG_NOT_REMOVABLE
    flags &= ~Message.FLAG_CHAT_STICKY
    flags &= ~Message.FLAG_ALLOW_CHAT_PICTURE
    flags &= ~Message.FLAG_ALLOW_CHAT_VIDEO
    flags &= ~Message.FLAG_ALLOW_CHAT_PRIORITY
    flags &= ~Message.FLAG_ALLOW_CHAT_STICKY

    message = sendMessage(service_identity_user, mm, flags, 0,
                          parent_key if parent_key != MISSING else parent_message_key, message, answers,
                          None, branding, tag, dismiss_button_ui_flags, context=context, attachments=attachments,
                          is_mfr=users.get_current_user().is_mfr, broadcast_guid=broadcast_guid, step_id=step_id)
    return message.mkey

@service_api(function=u"messaging.start_chat")
@returns(unicode)
@arguments(members=[(unicode, MemberTO)], topic=unicode, description=unicode, alert_flags=int, service_identity=unicode,
           tag=unicode, context=unicode, reader_members=[(unicode, MemberTO)], flags=int, metadata=[KeyValueTO],
            avatar=unicode, background_color=unicode, text_color=unicode,
            default_priority=(int, long), default_sticky=bool)
def start_chat(members, topic, description, alert_flags=Message.ALERT_FLAG_VIBRATE, service_identity=None, tag=None,
               context=None, reader_members=None, flags=0, metadata=None,
               avatar=None, background_color=None, text_color=None,
               default_priority=Message.PRIORITY_NORMAL, default_sticky=False):
    from rogerthat.bizz.service import get_and_validate_service_identity_user
    from rogerthat.bizz.messaging import start_chat as start_chat_bizz, member_list_to_usermember_list

    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    writers = member_list_to_usermember_list(service_identity_user, members, alert_flags)
    readers = member_list_to_usermember_list(service_identity_user, reader_members, alert_flags, read_only=True) if reader_members else list()
    avatar = base64.b64decode(avatar) if avatar else None

    message = start_chat_bizz(service_identity_user, topic, description, writers, readers, tag, context, flags, metadata,
                              avatar, background_color, text_color,
                              default_priority, default_sticky)
    return message.mkey

@service_api(function=u"messaging.update_chat")
@returns(bool)
@arguments(parent_message_key=unicode, topic=unicode, description=unicode, flags=int, metadata=[KeyValueTO],
           avatar=unicode, background_color=unicode, text_color=unicode)
def update_chat(parent_message_key, topic=None, description=None, flags=-1, metadata=None, avatar=None,
                background_color=None, text_color=None):
    from rogerthat.bizz.messaging import update_chat as bizz_update_chat

    flags = None if flags < 0 else flags
    avatar = base64.b64decode(avatar) if avatar else None

    return bizz_update_chat(users.get_current_user(), parent_message_key, topic, description, flags, metadata, avatar,
                            background_color, text_color)

@service_api(function=u"messaging.send_chat_message")
@returns(unicode)
@arguments(parent_key=unicode, message=unicode, answers=[AnswerTO], attachments=[AttachmentTO], sender=(unicode, MemberTO), priority=(int, long), sticky=bool, tag=unicode, alert_flags=(int, long))
def send_chat_message(parent_key, message, answers=None, attachments=None, sender=None, priority=None, sticky=False, tag=None, alert_flags=Message.ALERT_FLAG_VIBRATE):
    from rogerthat.bizz.messaging import send_chat_message as bizz_send_chat_message
    service_user = users.get_current_user()
    message = bizz_send_chat_message(service_user, parent_key, message, answers, attachments, sender, priority, sticky, tag, alert_flags)
    return message.mkey

@service_api_callback(function=u"messaging.new_chat_message", code=ServiceProfile.CALLBACK_MESSAGING_NEW_CHAT_MESSAGE)
@returns()
@arguments(parent_message_key=unicode, message_key=unicode, sender=UserDetailsTO, message=unicode, answers=[AnswerTO], timestamp=int, tag=unicode, service_identity=unicode, attachments=[AttachmentTO])
def new_chat_message(parent_message_key, message_key, sender, message, answers, timestamp, tag, service_identity, attachments):
    pass

@service_api(function=u"messaging.list_chat_messages")
@returns(ChatMessageListResultTO)
@arguments(parent_message_key=unicode, cursor=unicode)
def list_chat_messages(parent_message_key, cursor=None):
    from rogerthat.bizz.messaging import list_chat_messages as bizz_list_chat_messages
    service_user = users.get_current_user()
    lr = bizz_list_chat_messages(service_user, parent_message_key, cursor)
    return ChatMessageListResultTO.from_model(lr.cursor, lr.messages, lr.user_profiles)


@service_api(function=u"messaging.broadcast")
@returns(BroadcastResultTO)
@arguments(broadcast_type=unicode, message=unicode, answers=[AnswerTO], flags=int, branding=unicode, tag=unicode, \
           service_identity=unicode, alert_flags=int, dismiss_button_ui_flags=int,
           target_audience=BroadcastTargetAudienceTO, attachments=[AttachmentTO], timeout=int)
def broadcast(broadcast_type, message, answers, flags, branding, tag, service_identity=None, \
              alert_flags=Message.ALERT_FLAG_VIBRATE, dismiss_button_ui_flags=0, target_audience=None, \
              attachments=None, timeout=0):
    from rogerthat.bizz.messaging import broadcastMessage
    from rogerthat.bizz.service import get_and_validate_service_identity_user, validate_broadcast_type

    service_user = users.get_current_user()
    service_identity_user = get_and_validate_service_identity_user(service_user, service_identity)
    validate_broadcast_type(service_user, broadcast_type)
    broadcast_guid = broadcastMessage(service_identity_user, broadcast_type, message, answers, flags, branding, tag, alert_flags, \
                     dismiss_button_ui_flags, target_audience, attachments, timeout)
    result = BroadcastResultTO()
    result.statistics_key = broadcast_guid
    return result

@service_api(function=u"messaging.send_form")
@returns(unicode)
@arguments(parent_key=unicode, parent_message_key=unicode, member=unicode, message=unicode, form=FormTO, flags=int,
           alert_flags=int, branding=unicode, tag=unicode, service_identity=unicode, context=unicode,
           attachments=[AttachmentTO], app_id=unicode, broadcast_guid=unicode, step_id=unicode)
def send_form(parent_key, parent_message_key, member, message, form, flags, alert_flags, branding, tag,
              service_identity=None, context=None, attachments=None, app_id=None, broadcast_guid=None, step_id=None):
    from rogerthat.bizz.messaging import sendForm
    from rogerthat.bizz.service import get_and_validate_service_identity_user, get_and_validate_app_id_for_service_identity_user

    flags = 0  # flags are currently not used; clear any flags set by api client (e.g. ALLOW_DISMISS or SHARED_MEMBERS)
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    app_id = get_and_validate_app_id_for_service_identity_user(service_identity_user, app_id)

    fm = sendForm(service_identity_user, parent_key if parent_key != MISSING else parent_message_key,
                  create_app_user(users.User(member), app_id), message, form, flags, branding, tag, alert_flags,
                  context=context, attachments=attachments, is_mfr=users.get_current_user().is_mfr,
                  broadcast_guid=broadcast_guid, step_id=step_id)
    return fm.mkey

@service_api_callback(function=u"messaging.form_update", code=ServiceProfile.CALLBACK_MESSAGING_FORM_ACKNOWLEDGED)
@returns(FormAcknowledgedCallbackResultTO)
@arguments(status=int, form_result=FormResult, answer_id=unicode, member=unicode, message_key=unicode, tag=unicode, \
           received_timestamp=int, acked_timestamp=int, parent_message_key=unicode, result_key=unicode,
           service_identity=unicode, user_details=[UserDetailsTO])
def form_acknowledged(status, form_result, answer_id, member, message_key, tag, received_timestamp, acked_timestamp,
                      parent_message_key, result_key, service_identity, user_details):
    pass

@service_api_callback(function=u"messaging.update", code=ServiceProfile.CALLBACK_MESSAGING_RECEIVED)
@returns(NoneType)
@arguments(status=int, answer_id=unicode, received_timestamp=int, member=unicode, message_key=unicode, tag=unicode,
           acked_timestamp=int, parent_message_key=unicode, service_identity=unicode, user_details=[UserDetailsTO])
def received(status, answer_id, received_timestamp, member, message_key, tag, acked_timestamp, parent_message_key,
             service_identity, user_details):
    pass

@service_api_callback(function=u"messaging.update", code=ServiceProfile.CALLBACK_MESSAGING_ACKNOWLEDGED)
@returns(MessageAcknowledgedCallbackResultTO)
@arguments(status=int, answer_id=unicode, received_timestamp=int, member=unicode, message_key=unicode, tag=unicode,
           acked_timestamp=int, parent_message_key=unicode, result_key=unicode, service_identity=unicode,
           user_details=[UserDetailsTO])
def acknowledged(status, answer_id, received_timestamp, member, message_key, tag, acked_timestamp, parent_message_key,
                 result_key, service_identity, user_details):
    pass

@service_api_callback(function=u"messaging.poke", code=ServiceProfile.CALLBACK_MESSAGING_POKE)
@returns(PokeCallbackResultTO)
@arguments(email=unicode, tag=unicode, result_key=unicode, context=unicode, service_identity=unicode,
           user_details=[UserDetailsTO], timestamp=int)
def poke(email, tag, result_key, context, service_identity, user_details, timestamp):
    pass

@service_api(function=u"messaging.seal")
@returns(NoneType)
@arguments(message_key=unicode, message_parent_key=unicode, parent_message_key=unicode, dirty_behavior=int)
def seal(message_key, message_parent_key, parent_message_key, dirty_behavior):
    from rogerthat.bizz.messaging import lockMessage
    svc_user = users.get_current_user()
    lockMessage(svc_user, message_key, message_parent_key if message_parent_key != MISSING else parent_message_key, dirty_behavior)


@service_api(function=u"messaging.delete_conversation", cache_result=False)
@returns(bool)
@arguments(parent_message_key=unicode, members=[(unicode, MemberTO)], service_identity=unicode)
def delete_conversation(parent_message_key, members, service_identity=None):
    from rogerthat.bizz.messaging import service_delete_conversation
    from rogerthat.bizz.service import get_and_validate_service_identity_user
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    return service_delete_conversation(service_identity_user, parent_message_key,
                                       _convert_to_member_users(service_identity_user, members))


@service_api(function=u"messaging.delete_chat", cache_result=False)
@returns(bool)
@arguments(parent_message_key=unicode)
def delete_chat(parent_message_key):
    from rogerthat.bizz.messaging import delete_chat as bizz_delete_chat
    service_user = users.get_current_user()
    return bizz_delete_chat(service_user, parent_message_key)


@service_api_callback(function=u"messaging.chat_deleted", code=ServiceProfile.CALLBACK_MESSAGING_CHAT_DELETED)
@returns()
@arguments(parent_message_key=unicode, member=UserDetailsTO, timestamp=int, service_identity=unicode, tag=unicode)
def chat_deleted(parent_message_key, member, timestamp, service_identity, tag):
    pass


@service_api(function=u"messaging.add_chat_members")
@returns()
@arguments(parent_message_key=unicode, members=[(unicode, MemberTO)], reader_members=[(unicode, MemberTO)])
def add_chat_members(parent_message_key, members, reader_members=None):
    from rogerthat.bizz.messaging import add_members_to_chat
    service_user = users.get_current_user()
    add_members_to_chat(service_user, parent_message_key, members, reader_members or list())


@service_api(function=u"messaging.delete_chat_members")
@returns()
@arguments(parent_message_key=unicode, members=[(unicode, MemberTO)], soft=bool)
def delete_chat_members(parent_message_key, members, soft=False):
    from rogerthat.bizz.messaging import delete_members_from_chat
    service_user = users.get_current_user()
    delete_members_from_chat(service_user, parent_message_key, members, soft)


@service_api(function=u"messaging.update_chat_members")
@returns()
@arguments(parent_message_key=unicode, members=[(unicode, MemberTO)], status=unicode)
def update_chat_members(parent_message_key, members, status):
    from rogerthat.bizz.messaging import update_chat_members as bizz_update_chat_members
    bizz_update_chat_members(users.get_current_user(), parent_message_key, members, status)


@returns([users.User])
@arguments(service_identity_user=users.User, members=[(unicode, MemberTO)])
def _convert_to_member_users(service_identity_user, members):
    from rogerthat.bizz.service import valididate_app_id_for_service_identity
    mm = None
    if members != MISSING:
        mm = []
        si = get_service_identity(service_identity_user)
        for m in members:
            if isinstance(m, MemberTO) and m.app_id != MISSING:
                valididate_app_id_for_service_identity(si, m.app_id)
                mm.append(create_app_user(users.User(m.member), m.app_id))
            else:
                mm.append(create_app_user(users.User(m), si.app_id))
    return mm

@service_api(function=u"messaging.start_flow")
@returns(unicode)
@arguments(message_parent_key=unicode, parent_message_key=unicode, flow=unicode, members=[(unicode, MemberTO)],
           service_identity=unicode, tag=unicode, context=unicode, force_language=unicode)
def start_flow(message_parent_key, parent_message_key, flow, members, service_identity=None,
                tag=None, context=None, force_language=None):
    from rogerthat.bizz.service.mfr import start_flow as start_flow_bizz
    from rogerthat.bizz.service import get_and_validate_service_identity_user
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)

    mm = _convert_to_member_users(service_identity_user, members)

    return start_flow_bizz(service_identity_user, \
                           message_parent_key if message_parent_key != MISSING else parent_message_key, flow, \
                           mm, True, True, tag, context=context, force_language=force_language)


@service_api(function=u"messaging.start_local_flow")
@returns(unicode)
@arguments(xml=unicode, members=[(unicode, MemberTO)], service_identity=unicode, tag=unicode,
           parent_message_key=unicode, context=unicode, force_language=unicode, download_attachments_upfront=bool,
           push_message=unicode)
def start_local_flow(xml, members, service_identity=None, tag=None, parent_message_key=None, context=None,
                     force_language=None, download_attachments_upfront=False, push_message=None):
    from rogerthat.bizz.service.mfr import start_local_flow as start_local_flow_bizz
    from rogerthat.bizz.service import get_and_validate_service_identity_user
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)

    mm = _convert_to_member_users(service_identity_user, members)
    return start_local_flow_bizz(service_identity_user, parent_message_key, xml, mm, tag, context, force_language,
                                 download_attachments_upfront, push_message)

#############################################
# DO NOT DOCUMENT THIS SERVICE API FUNCTION #
# MFR ONLY                                  #
@service_api(function=u"messaging.mfr_flow_member_result")
@returns(NoneType)
@arguments(message_flow_run_id=unicode, member=unicode, steps=[object_factory("step_type", FLOW_STEP_MAPPING)], \
           end_id=unicode, flush_id=unicode, parent_message_key=unicode, service_identity=unicode, results_email=bool, \
           email_admins=bool, emails=[unicode], message_flow_name=unicode, app_id=unicode)
def mfr_flow_member_result(message_flow_run_id, member, steps, end_id, flush_id, parent_message_key,
                           service_identity=None, results_email=False, email_admins=False, emails=None,
                           message_flow_name=None, app_id=None):
    from rogerthat.bizz.service import get_and_validate_app_id_for_service_identity_user
    svc_user = get_current_user()
    azzert(svc_user.is_mfr)

    if not service_identity or service_identity == MISSING:
        service_identity = ServiceIdentity.DEFAULT

    mfr = get_message_flow_run_record(svc_user, message_flow_run_id)
    if not mfr:
        return

    svc_identity_user = create_service_identity_user(svc_user, service_identity)
    azzert(mfr.service_identity == svc_identity_user.email())

    app_id = get_and_validate_app_id_for_service_identity_user(svc_identity_user, app_id)
    app_user = create_app_user(users.User(member), app_id)

    if end_id:
        from rogerthat.bizz.messaging import check_test_flow_broadcast_ended
        check_test_flow_broadcast_ended(app_user, users.User(mfr.service_identity), parent_message_key, mfr.tag)

    if results_email:
        from rogerthat.bizz.messaging import send_message_flow_results_email
        for step in steps:
            if step.step_type == FormFlowStepTO.TYPE and step.display_value and step.display_value.startswith('base64:'):
                step.display_value = base64.b64decode(step.display_value[7:]).decode('utf-8')
        try_or_defer(send_message_flow_results_email, message_flow_name, emails, email_admins, steps, app_user,
                     service_identity, svc_user, parent_message_key, mfr.tag)
    else:
        if mfr.post_result_callback:
            from rogerthat.bizz.messaging import send_message_flow_member_result
            send_message_flow_member_result(svc_user, service_identity, message_flow_run_id, parent_message_key,
                                            app_user, steps, end_id, flush_id, mfr.tag)

############################################

@service_api_callback(function=u"messaging.flow_member_result", code=ServiceProfile.CALLBACK_MESSAGING_FLOW_MEMBER_RESULT)
@returns(FlowMemberResultCallbackResultTO)
@arguments(message_flow_run_id=unicode, member=unicode, steps=[object_factory("step_type", FLOW_STEP_MAPPING)], \
           end_id=unicode, end_message_flow_id=unicode, parent_message_key=unicode, tag=unicode, result_key=unicode, \
           flush_id=unicode, flush_message_flow_id=unicode, service_identity=unicode, user_details=[UserDetailsTO])
def flow_member_result(message_flow_run_id, member, steps, end_id, end_message_flow_id, parent_message_key, tag, \
                       result_key, flush_id, flush_message_flow_id, service_identity, user_details):
    pass
