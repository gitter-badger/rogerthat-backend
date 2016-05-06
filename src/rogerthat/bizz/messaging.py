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
from collections import namedtuple
import hashlib
import json
import logging
import re
import time
from types import NoneType, BooleanType
import urllib2
import uuid
import zlib

from google.appengine.api import app_identity, images
from google.appengine.ext import db, deferred
from mcfw.consts import MISSING
from mcfw.properties import object_factory
from mcfw.rpc import returns, arguments, serialize_complex_value
from mcfw.utils import Enum
from rogerthat import utils, templates
from rogerthat.bizz import log_analysis
from rogerthat.bizz.i18n import get_translator
from rogerthat.bizz.job import run_job
from rogerthat.capi.messaging import newMessage, updateMessageMemberStatus, messageLocked, conversationDeleted, \
    transferCompleted, updateMessage
from rogerthat.consts import MC_DASHBOARD
from rogerthat.consts import MESSAGE_ACKED, MESSAGE_ACK_FAILED_LOCKED, MESSAGE_ACKED_NO_CHANGES, \
    MICRO_MULTIPLIER, MC_RESERVED_TAG_PREFIX, CHAT_MAX_BUTTON_REPLIES, SCHEDULED_QUEUE
from rogerthat.dal import put_and_invalidate_cache
from rogerthat.dal.app import get_app_name_by_id, get_app_by_user
from rogerthat.dal.friend import get_friends_map_cached
from rogerthat.dal.messaging import get_message, get_branding, get_messages, get_transfer_result, \
    count_transfer_chunks, get_transfer_chunks, get_message_key, get_thread_avatar
from rogerthat.dal.profile import get_user_profile, get_service_profile, get_profile_infos, \
    are_service_identity_users, is_service_identity_user, get_profile_key
from rogerthat.dal.service import get_friend_serviceidentity_connection, \
    get_friend_service_identity_connections_of_service_identity_query, get_api_keys, get_service_identity, \
    get_service_identities
from rogerthat.models import Message, FormMessage, ServiceProfile, UserProfile, ServiceMenuDef, Branding, \
    TransferResult, TransferChunk, ServiceTranslation, FlowResultMailFollowUp, Broadcast, ChatWriterMembers, \
    ChatReaderMembers, ChatMembers, DeleteMemberFromChatJob, AddMemberToChatJob, UpdateChatMemberJob, ThreadAvatar, \
    AbstractChatJob, App, BroadcastStatistic, FlowStatistics
from rogerthat.models.properties.forms import Form, RangeSlider, SingleSlider, MultiSelect, SingleSelect, \
    AutoComplete, TextBlock, TextLine, Choice, WidgetResult, FormResult, UnicodeWidgetResult, UnicodeListWidgetResult, \
    LongWidgetResult, LongListWidgetResult, FloatWidgetResult, FloatListWidgetResult, DateSelect, PhotoUpload, GPSLocation, \
    LocationWidgetResult, MyDigiPass, MdpScope, MyDigiPassWidgetResult, AdvancedOrder, AdvancedOrderCategory
from rogerthat.models.properties.friend import FriendDetail
from rogerthat.models.properties.messaging import Buttons, Button, MemberStatuses, MemberStatus, Attachments, \
    Attachment
from rogerthat.rpc import users
from rogerthat.rpc.models import RpcCAPICall, ServiceAPICallback, Mobile
from rogerthat.rpc.rpc import mapping, logError, DO_NOT_SAVE_RPCCALL_OBJECTS, CAPI_KEYWORD_ARG_PRIORITY, \
    CAPI_KEYWORD_ARG_APPLE_PUSH_MESSAGE, PRIORITY_HIGH, PRIORITY_NORMAL, TARGET_MFR, DEFER_KICK, SKIP_ACCOUNTS
from rogerthat.rpc.service import ServiceApiException, logServiceError, BusinessException, ApiWarning
from rogerthat.rpc.users import get_current_mobile
from rogerthat.settings import get_server_settings
from rogerthat.to import WIDGET_MAPPING, WIDGET_RESULT_MAPPING
from rogerthat.to.messaging import ButtonTO, NewMessageRequestTO, NewMessageResponseTO, MemberStatusUpdateRequestTO, \
    MemberStatusUpdateResponseTO, MessageTO, MessageLockedRequestTO, MessageLockedResponseTO, AnswerTO, DirtyBehavior, \
    UserMemberTO, ConversationDeletedResponseTO, ConversationDeletedRequestTO, MemberStatusTO, TransferCompletedRequestTO, \
    TransferCompletedResponseTO, AttachmentTO, BroadcastTargetAudienceTO, \
    MemberTO, UpdateMessageResponseTO, UpdateMessageRequestTO, KeyValueTO, BaseMemberTO
from rogerthat.to.messaging.flow import FLOW_STEP_MAPPING, FormFlowStepTO
from rogerthat.to.messaging.forms import FormTO, WebFormMessageTO, UpdateFormResponseTO, TextBlockTO, MyDigiPassTO
from rogerthat.to.messaging.service_callback_results import MessageAcknowledgedCallbackResultTO, \
    FormAcknowledgedCallbackResultTO, FlowMemberResultCallbackResultTO
from rogerthat.to.service import UserDetailsTO
from rogerthat.translations import localize
from rogerthat.utils import now, channel, azzert, try_or_defer, is_flag_set, is_numeric_string, slog, today, set_flag, \
    unset_flag
from rogerthat.utils.app import get_app_user_tuple, get_human_user_from_app_user, get_app_id_from_app_user, \
    create_app_user
from rogerthat.utils.iOS import construct_push_notification
from rogerthat.utils.service import get_service_identity_tuple, get_service_user_from_service_identity_user, \
    remove_slash_default, create_service_identity_user, get_identity_from_service_identity_user, add_slash_default
from rogerthat.utils.transactions import on_trans_committed, run_in_transaction


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


REPLY_ON_FOLLOW_UP_MESSAGE = 'REPLY_ON_FOLLOW_UP_MESSAGE'
MAX_CHAT_MEMBERS_SIZE = 800000
MAX_CHAT_MEMBER_UPDATE_SIZE = 15

ackListeners = dict()


class ChatFlags(Enum):
    NOT_REMOVABLE = 1
    ALLOW_ANSWER_BUTTONS = 2
    ALLOW_PICTURE = 4
    ALLOW_VIDEO = 8
    ALLOW_PRIORITY = 16
    ALLOW_STICKY = 32
    READ_ONLY = 64

    _MESSAGE_FLAG_MAPPING = {NOT_REMOVABLE: Message.FLAG_NOT_REMOVABLE,
                             ALLOW_ANSWER_BUTTONS: Message.FLAG_ALLOW_CHAT_BUTTONS,
                             ALLOW_PICTURE: Message.FLAG_ALLOW_CHAT_PICTURE,
                             ALLOW_VIDEO: Message.FLAG_ALLOW_CHAT_VIDEO,
                             ALLOW_PRIORITY: Message.FLAG_ALLOW_CHAT_PRIORITY,
                             ALLOW_STICKY: Message.FLAG_ALLOW_CHAT_STICKY,
                             READ_ONLY:-(Message.FLAG_ALLOW_REPLY | Message.FLAG_ALLOW_REPLY_ALL)}

    @classmethod
    def message_flag(cls, chat_flag):
        return cls._MESSAGE_FLAG_MAPPING[chat_flag]


class ChatMemberStatus(Enum):
    READER = 'READER'
    WRITER = 'WRITER'

    @classmethod
    def is_read_only(cls, chat_member_status):
        return chat_member_status == cls.READER


class ResponseReceivedFromNonMemberException(ValueError):
    pass

class InvalidDirtyBehaviorException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 16,
                                     "Invalid dirty_behavior.")

class MessageLockedException(ServiceApiException, deferred.PermanentTaskFailure):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 10,
                                     "Message is already locked.")

class MessageNotFoundException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 9,
                                     "Message not found.")

class CanOnlySendToFriendsException(ServiceApiException):
    def __init__(self, member, app_id):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 0,
                                     "Member is not in your friends list.", member=member, app_id=app_id)

class CanNotSendToServicesException(ServiceApiException):
    def __init__(self, member, app_id):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 15,
                                     "Can not send to services.", member=member, app_id=app_id)

class ParentMessageNotFoundException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 1,
                                     "Parent message not found.")

class CanOnlyReplyToMembersException(Exception):
    pass

class DuplicateMembersException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 13,
                                     "Duplicate members.")

class InvalidFlagsException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 3,
                                     "Invalid flags.")

class UnknownMessageAlertFlagException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 17,
                                     "Invalid alert flags.")

class RingAlertFlagsAreNotCombinableException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 18,
                                     "You cannot combine multiple ring flags.")

class IntervalAlertFlagsAreNotCombinableException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 19,
                                     "You cannot combine multiple interval flags.")

class AutoLockCanOnlyHaveOneMemberInMessageException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 11,
                                     "Autoseal flag implies maximum one member.")

class UnDismissableMessagesNeedAnswersException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 12,
                                     "Undismissable messages need at least one answer.")

class InvalidSenderReplyValue(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 2,
                                     "Illegal sender answer.")

class TagTooLargeException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 4,
                                     "Tag too large.")

class UnsupportedActionTypeException(ServiceApiException):
    def __init__(self, scheme):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 6,
                                     "Unsupported answer action type.", scheme=scheme)

class UnknownAnswerWidgetType(ServiceApiException):
    def __init__(self, widget_type):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 5,
                                     "Unknown answer widget type", widget_type=widget_type)

class IncompleteButtonException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 8,
                                     "Incomplete button.")

class BrandingNotFoundException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 7,
                                     "Branding not found.")

class DuplicateButtonIdException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 14,
                                     "Duplicate button ids.")

class InvalidWidgetValueException(ServiceApiException):
    def __init__(self, property_):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 20,
                                     "Invalid value in widget.", property=property_)

class ValueTooLongException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 21,
                                     "Value too long.")

class NoChoicesSpecifiedException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 22,
                                     "No choices specified.")

class DuplicateChoiceLabelException(ServiceApiException):
    def __init__(self, label):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 23,
                                     "Duplicate label in choices.", label=label)

class DuplicateChoiceValueException(ServiceApiException):
    def __init__(self, value):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 24,
                                     "Duplicate value in choices.", value=value)

class DuplicateValueException(ServiceApiException):
    def __init__(self, value):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 25,
                                     "Duplicate value.", value=value)

class ValueNotInChoicesException(ServiceApiException):
    def __init__(self, value):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 26,
                                     "Value not in choices.", value=value)

class ValueNotWithinBoundariesException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 27,
                                     "Value not within boundaries.")

class InvalidBoundariesException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 28,
                                     "Invalid boundaries.")

class InvalidRangeException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 29,
                                     "Invalid values for range.")

class MultipleChoicesNeededException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 30,
                                     "At least 2 choices needed.")

class InvalidUnitException(ServiceApiException):
    def __init__(self, missing_tag):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 31,
                                     "Invalid unit format.", missing_tag=missing_tag)

class SuggestionTooLongException(ServiceApiException):
    def __init__(self, index):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 32,
                                     "Suggestion too long.", index=index)

class MembersDoNotReflectParentMessageException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 33,
                                     "Members do not reflect parent message members.")

class DismissUiFlagWithoutAllowDismissException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 34,
                                     "Undismissable messages can not have dismiss button ui flags.")

class UnknownUiFlagException(ServiceApiException):
    def __init__(self, button):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 35,
                                     "Invalid button ui flags.", button=button)

class UnknownDismissButtonUiFlagException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 36,
                                     "Invalid dismiss button ui flags.")

class InvalidDateSelectModeException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 37,
                                     "Invalid mode for date_select widget.")

class InvalidDateSelectMinuteIntervalException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 38,
                                     "The minimum minute_interval value is 1; the maximum minute_interval value is 30.")

class MinuteIntervalNotEvenlyDividedInto60Exception(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 39,
                                     "The minute_interval value must be a divisor of 60.")

class InvalidStepValue(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 40,
                                     "Step can not be greater than the slider range.")

class InvalidValueInDateSelectWithModeTime(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 41,
                                     "Invalid value in date_select with mode 'time'. The min_date, max_date and date values should be between 0 and 86400.")

class InvalidValueInDateSelectWithModeDate(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 42,
                                     "Invalid value in date_select with mode 'date'. The min_date, max_date and date values should be multiples of 86400.")

class DateSelectValuesShouldBeMultiplesOfMinuteInterval(ServiceApiException):
    def __init__(self, minute_interval):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 43,
                                     "The min_date, max_date and date values should be multiples of minute_interval.", minute_interval=minute_interval)

class ReservedTagException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 44,
                                     "Tag should not start with %s" % MC_RESERVED_TAG_PREFIX)

class InvalidBrandingException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 45,
                                     "This branding can not be used for messages.")

class InvalidFormException(ServiceApiException):
    def __init__(self, message):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 46, message)

class InvalidPhotoUploadQualityException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 47,
                                     "Invalid quality in photo_upload. Values can be 'best', 'user' or the max size in bytes")

class InvalidPhotoUploadSourceException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 48,
                                     "No source to select a picture has been provided.")

class InvalidPhotoUploadRatioException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 49,
                                     "Invalid ratio in photo_upload. (example: 100x100)")

class AttachmentDownloadException(ServiceApiException):
    def __init__(self, reason):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 50,
                                     "Not all attachment download URLs are reachable", reason=reason)

class InvalidAttachmentException(ServiceApiException):
    def __init__(self, reason):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 51,
                                     "Invalid attachment", reason=reason)

class MemberNotFoundException(ServiceApiException):
    def __init__(self, member, app_id):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 52,
                                     "Member not found", member=member, app_id=app_id)

class InvalidChatMemberStatusException(ServiceApiException):
    def __init__(self, status):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 53,
                                     "Invalid chat status", status=status)

class InvalidPriorityException(ServiceApiException):
    def __init__(self, priority):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 54,
                                     "Invalid priority.", priority=priority)

class InvalidMyDigiPassScopeException(ServiceApiException):
    def __init__(self, scope):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 55,
                                     "Invalid scope.", scope=scope)

class StepIdForbiddenException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 56,
                                     "step_id is only allowed in combination with 1 recipient and flag AUTO_LOCK.")

class MessageFlowValidationException(ServiceApiException):
    def __init__(self, reason):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE + 57,
                                     "Messageflow invalid.", reason=reason)


@returns(NoneType)
@arguments(user=users.User, message=unicode, lock_immediately=bool, context=unicode)
def dashboardNotification(user, message, lock_immediately=True, context=None):
    _ = sendMessage(MC_DASHBOARD, [UserMemberTO(user, Message.ALERT_FLAG_SILENT)], \
                    Message.FLAG_ALLOW_DISMISS | Message.FLAG_AUTO_LOCK, 0, None, message, [], None, \
                    get_app_by_user(user).core_branding_hash, None, is_mfr=False, context=context)


@returns(FormMessage)
@arguments(sender_user_possibly_with_slash_default=users.User, parent_key=unicode, member=users.User, message=unicode,
           form=FormTO, flags=int, branding=unicode, tag=unicode, alert_flags=int, context=unicode, key=unicode,
           is_mfr=bool, forced_member_status=MemberStatusTO, forced_form_result=FormResult, broadcast_type=unicode,
           attachments=[AttachmentTO], broadcast_guid=unicode, step_id=unicode, allow_reserved_tag=bool)
def sendForm(sender_user_possibly_with_slash_default, parent_key, member, message, form, flags, branding, tag,
             alert_flags=Message.ALERT_FLAG_VIBRATE, context=None, key=None, is_mfr=False, forced_member_status=None,
             forced_form_result=None, broadcast_type=None, attachments=None, broadcast_guid=None, step_id=None,
             allow_reserved_tag=False):
    _validate_form(form, remove_slash_default(sender_user_possibly_with_slash_default))

    if forced_member_status:
        azzert(forced_member_status.member == member.email())

    if message is None:
        message = u""

    azzert(sender_user_possibly_with_slash_default != MC_DASHBOARD)
    sender_type = FriendDetail.TYPE_SERVICE

    flags &= ~Message.FLAG_ALLOW_REPLY
    flags &= ~Message.FLAG_ALLOW_REPLY_ALL

    if is_mfr:
        flags |= Message.FLAG_SENT_BY_MFR
    else:
        flags &= ~Message.FLAG_SENT_BY_MFR

    flags |= Message.FLAG_AUTO_LOCK  # Force this for forms

    if not parent_key and sender_user_possibly_with_slash_default != MC_DASHBOARD:
        _validateFlags(flags, [member])
        _validate_members(sender_user_possibly_with_slash_default, True, [member])

    _validate_alert_flags([UserMemberTO(member, alert_flags)])
    _validate_tag(tag, allow_reserved_tag)

    if branding:
        sender_svc_user = get_service_user_from_service_identity_user(sender_user_possibly_with_slash_default)
        _validate_branding(branding, sender_svc_user)

    attachments = _validate_attachments(attachments)

    sender_user_without_slash_default = remove_slash_default(sender_user_possibly_with_slash_default)

    if parent_key:
        pk = db.Key.from_path(Message.kind(), parent_key)
        parent_message = Message.get(pk)
        if not parent_message:
            raise ParentMessageNotFoundException()
        if member and set(parent_message.members) != set([member, sender_user_without_slash_default]):
            raise MembersDoNotReflectParentMessageException()
        child_messages = parent_message.childMessages
    else:
        pk = None
        parent_message = None
        child_messages = list()

    step_id = _validate_step_id(step_id, flags, [member])  # checking this one AFTER checking members of parent_message

    key = key or unicode(uuid.uuid4())
    maintenant = now()
    maintenant_detailed = int(time.time() * MICRO_MULTIPLIER)

    def run(member):
        if parent_key:
            if step_id:
                # we need to append to the flow statistics
                breadcrumbs, service_identity_user, readable_parent_message_tag, parent_message, _ = \
                    _get_flow_stats_breadcrumbs(pk, child_messages)

                on_trans_committed(bump_flow_statistics_by_member_status, member, service_identity_user,
                                   readable_parent_message_tag, today(), breadcrumbs, step_id, forced_member_status)
            else:
                parent_message = Message.get(pk)

            fm = FormMessage(key_name=key, parent=pk)
            parent_message.childMessages.append(fm.key())
            # Services specify their flags
            fm.flags = flags
            fm.originalFlags = flags
            parent_message.timestamp = maintenant_detailed
            fm.timestamp = 0 - maintenant_detailed
        else:
            if step_id:
                on_trans_committed(bump_flow_statistics_by_member_status, member,
                                   add_slash_default(sender_user_without_slash_default),
                                   parse_to_human_readable_tag(tag), today(), list(), step_id, forced_member_status)

            fm = FormMessage(key_name=key)
            fm.childMessages = list()
            fm.flags = flags
            fm.originalFlags = flags
            fm.timestamp = maintenant_detailed
            parent_message = None

        _add_form(form, fm)
        fm.members = [member, sender_user_without_slash_default]
        fm.sender = sender_user_without_slash_default
        fm.message = message
        fm.creationTimestamp = maintenant
        fm.generation = 1
        fm.memberStatusses = MemberStatuses()
        ms = MemberStatus()
        ms.index = 0
        ms.custom_reply = None
        ms.dismissed = False
        if forced_member_status:
            ms.status = forced_member_status.status
            ms.received_timestamp = forced_member_status.received_timestamp
            ms.acked_timestamp = forced_member_status.acked_timestamp
            ms.button_index = fm.buttons[forced_member_status.button_id].index
            ms.form_result = forced_form_result if forced_form_result and forced_form_result.result else None
            ms.ack_device = u"mobile" if get_current_mobile() else u"web"
        else:
            ms.status = 0
            ms.received_timestamp = 0
            ms.acked_timestamp = 0
            ms.button_index = -1
            ms.form_result = None
            ms.ack_device = None
        fm.memberStatusses.add(ms)
        fm.branding = branding
        fm.tag = tag
        fm.alert_flags = alert_flags
        fm.sender_type = sender_type
        if sender_type == FriendDetail.TYPE_SERVICE:
            fm.addStatusIndex(member, Message.SERVICE_MESSAGE_DEFAULT_MEMBER_INDEX_STATUSSES)
        else:
            fm.addStatusIndex(member, Message.USER_MESSAGE_DEFAULT_MEMBER_INDEX_STATUSSES)
        for mem in fm.members:
            fm.member_status_index.append(mem.email())
        if forced_member_status:
            if is_flag_set(MemberStatus.STATUS_RECEIVED, forced_member_status.status):
                fm.removeStatusIndex(member, Message.MEMBER_INDEX_STATUS_NOT_RECEIVED)
            if is_flag_set(MemberStatus.STATUS_READ, forced_member_status.status) \
                    or is_flag_set(MemberStatus.STATUS_ACKED, forced_member_status.status):
                fm.removeStatusIndex(member, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX)
            if is_flag_set(MemberStatus.STATUS_DELETED, forced_member_status.status):
                fm.removeStatusIndex(member, Message.MEMBER_INDEX_STATUS_NOT_DELETED)
        fm.broadcast_type = broadcast_type
        fm.broadcast_guid = broadcast_guid
        fm.step_id = step_id
        _add_attachments(attachments, fm)
        put = list()
        put.append(fm)
        if parent_key:
            put.append(parent_message)
        db.put(put)
        return fm, member, parent_message

    if db.is_in_transaction():
        fm, member, parent_message = run(member)
    else:
        fm, member, parent_message = db.run_in_transaction(run, member)

    # Define previous message
    previous_thread_message = None
    if parent_message:
        if len(parent_message.childMessages) > 1:
            previous_thread_message = db.get(parent_message.childMessages[-2])
        else:
            previous_thread_message = parent_message

    context_list = list()

    thread_size = 1 + (len(parent_message.childMessages) if parent_message else 0)

    req = WIDGET_MAPPING[fm.form.type].new_req_to_type()
    req.form_message = WIDGET_MAPPING[fm.form.type].fm_to_type.fromFormMessage(fm)
    req.form_message.thread_size = thread_size
    req.form_message.context = context
    try:
        if previous_thread_message:
            previous_thread_message_member_status = previous_thread_message.memberStatusses[previous_thread_message.members.index(member)]
        else:
            previous_thread_message_member_status = None
        if req.form_message.alert_flags < Message.ALERT_FLAG_RING_5 \
            and ((previous_thread_message_member_status
                    and abs(fm.timestamp) - previous_thread_message_member_status.acked_timestamp < 30
                    and previous_thread_message_member_status.ack_device == "web")
                 or (context and context.startswith('__web__'))):
                req.form_message.alert_flags = Message.ALERT_FLAG_SILENT
    except:
        logging.exception("Failed to silence message to phone.")
    kwargs = {"request":req, DO_NOT_SAVE_RPCCALL_OBJECTS:True}
    if req.form_message.alert_flags == Message.ALERT_FLAG_SILENT:
        kwargs[CAPI_KEYWORD_ARG_PRIORITY] = PRIORITY_NORMAL
    else:
        kwargs[CAPI_KEYWORD_ARG_PRIORITY] = PRIORITY_HIGH
        kwargs[CAPI_KEYWORD_ARG_APPLE_PUSH_MESSAGE] = _generate_push_json(fm, parent_message, member,
                                                                          sender_is_service_identity=True)
    if context or parent_key:
        kwargs[DEFER_KICK] = True

    if is_flag_set(Message.FLAG_SENT_BY_JS_MFR, flags):
        current_mobile = users.get_current_mobile()
        if current_mobile:
            kwargs[SKIP_ACCOUNTS] = [current_mobile.account]

    ctxs = WIDGET_MAPPING[fm.form.type].new_form_call(new_message_response_handler, logError, member, **kwargs)
    for ctx in ctxs:
        ctx.message = fm.key()
        context_list.append(ctx)

    db.put(context_list)

    # Send request over channel API
    msg_dict = serialize_complex_value(WebFormMessageTO.fromMessage(fm, thread_size), WebFormMessageTO, False)
    msg_dict['context'] = context
    channel.send_message(member, u'rogerthat.messaging.newMessage', message=msg_dict)

    if fm.broadcast_guid and not fm.parent_key():
        slog(msg_="Broadcast stats sent", function_=log_analysis.BROADCAST_STATS, service=fm.sender.email(),
             type_=log_analysis.BROADCAST_STATS_SENT, broadcast_guid=broadcast_guid)

    return fm

@returns(unicode)
@arguments(service_identity_user=users.User, broadcast_type=unicode, message=unicode, \
           answers=[AnswerTO], flags=int, branding=unicode, tag=unicode, alert_flags=int, \
           dismiss_button_ui_flags=int, target_audience=BroadcastTargetAudienceTO, attachments=[AttachmentTO], \
           timeout=int)
def broadcastMessage(service_identity_user, broadcast_type, message, answers, flags, branding, \
              tag, alert_flags=Message.ALERT_FLAG_VIBRATE, dismiss_button_ui_flags=0, target_audience=None,
              attachments=None, timeout=0):

    from rogerthat.bizz.service import valididate_app_id_for_service_identity_user

    # First dry run inline to trigger potential parameter validation errors
    if target_audience not in (MISSING, None) and target_audience.app_id is not MISSING:

        valididate_app_id_for_service_identity_user(service_identity_user, target_audience.app_id)
        qry = get_friend_service_identity_connections_of_service_identity_query(service_identity_user, target_audience.app_id)
    else:
        qry = get_friend_service_identity_connections_of_service_identity_query(service_identity_user)
    volunteer = qry.get()
    if not volunteer:
        return
    volunteer = UserMemberTO(volunteer.friend, alert_flags)
    sendMessage(service_identity_user, [volunteer], flags, timeout, None, message, answers, None, branding, tag, \
                dismiss_button_ui_flags, dry_run=True, broadcast_type=broadcast_type)
    # Dry run succeeded, let's schedule the real job

    from rogerthat.bizz.job.service_broadcast import schedule_identity_broadcast_message
    extra_kwargs = dict()
    if target_audience not in (MISSING, None):
        extra_kwargs.update(min_age=target_audience.min_age,
                            max_age=target_audience.max_age,
                            gender=UserProfile.gender_from_string(target_audience.gender),
                            app_id=target_audience.app_id if target_audience.app_id is not MISSING else None)
    def trans():
        broadcast_guid = schedule_identity_broadcast_message(service_identity_user, broadcast_type, message, answers, flags, branding, tag,
                                        alert_flags, dismiss_button_ui_flags, attachments=attachments, timeout=timeout,
                                        **extra_kwargs)
        stats = BroadcastStatistic(key=BroadcastStatistic.create_key(broadcast_guid, service_identity_user),
                                   timestamp=now())
        stats.message = message[:500]
        stats.put()
        return broadcast_guid

    return db.run_in_transaction(trans)


@returns(str)
@arguments(avatar=str)
def _validate_thread_avatar(avatar):
    img = images.Image(avatar)
    img.im_feeling_lucky()
    img.execute_transforms()
    if img.height != img.width:
        devation = float(img.width) / float(img.height)
        if devation < 0.95 or devation > 1.05:
            from rogerthat.bizz.service import AvatarImageNotSquareException
            logging.debug("Avatar Size: %sx%s" % (img.width, img.height))
            raise AvatarImageNotSquareException()

    if img.width != 100 and img.height != 100:
        img = images.Image(avatar)
        img.resize(100, 100)
        return img.execute_transforms(images.PNG, 100)

    return avatar

@returns(Message)
@arguments(sender_user_possibly_with_slash_default=users.User, members=[UserMemberTO], flags=int, timeout=int,
           parent_key=unicode, message=unicode, answers=[ButtonTO], sender_answer=unicode, branding=unicode,
           tag=unicode, dismiss_button_ui_flags=int, context=unicode, key=unicode, is_mfr=bool,
           forced_member_status=MemberStatusTO, dry_run=bool, allow_reserved_tag=bool, broadcast_type=unicode,
           attachments=[AttachmentTO], check_friends=bool, check_friends_of=users.User,
           thread_avatar=str, thread_background_color=unicode, thread_text_color=unicode, priority=int, broadcast_guid=unicode,
           default_priority=(int, long), default_sticky=bool, step_id=unicode, default_alert_flags=int)
def sendMessage(sender_user_possibly_with_slash_default, members, flags, timeout, parent_key, message, answers,
                sender_answer, branding, tag, dismiss_button_ui_flags=0, context=None, key=None, is_mfr=False,
                forced_member_status=None, dry_run=False, allow_reserved_tag=False, broadcast_type=None,
                attachments=None, check_friends=True, check_friends_of=None,
                thread_avatar=None, thread_background_color=None, thread_text_color=None,
                priority=Message.PRIORITY_NORMAL, broadcast_guid=None,
                default_priority=Message.PRIORITY_NORMAL, default_sticky=False, step_id=None,
                default_alert_flags=Message.ALERT_FLAG_VIBRATE):

    from rogerthat.service.api.messaging import new_chat_message

    STICKY_TIMEOUT = 60 * 60 * 12

    if message is None:
        message = u""

    member_users = [m.member for m in members]

    if sender_user_possibly_with_slash_default == MC_DASHBOARD:
        get_profile_infos(member_users, expected_types=[UserProfile] * len(member_users))
        sender_is_service_identity = False
        sender_type = FriendDetail.TYPE_USER
    else:
        sender_is_service_identity = is_service_identity_user(sender_user_possibly_with_slash_default)
        sender_type = FriendDetail.TYPE_SERVICE if sender_is_service_identity else FriendDetail.TYPE_USER

    if parent_key:
        pk = db.Key.from_path(Message.kind(), parent_key)
        parent_message = Message.get(pk)
        if not parent_message:
            raise ParentMessageNotFoundException()

        child_messages = parent_message.childMessages
    else:
        child_messages = list()

    is_chat = is_flag_set(Message.FLAG_DYNAMIC_CHAT, parent_message.flags if parent_key else flags)
    if is_chat:
        flags |= Message.FLAG_ALLOW_DISMISS
        if parent_key:
            # copy chat-related flags from parent message
            for f in (Message.FLAG_DYNAMIC_CHAT, Message.FLAG_NOT_REMOVABLE, Message.FLAG_ALLOW_CHAT_BUTTONS,
                      Message.FLAG_CHAT_STICKY, Message.FLAG_ALLOW_CHAT_PICTURE, Message.FLAG_ALLOW_CHAT_VIDEO,
                      Message.FLAG_ALLOW_CHAT_PRIORITY, Message.FLAG_ALLOW_CHAT_STICKY):
                if is_flag_set(f, parent_message.flags):
                    flags |= f

    # In case of a service message, auto remove allow reply flags
    if not is_chat and (sender_user_possibly_with_slash_default == MC_DASHBOARD or sender_is_service_identity):
        flags &= ~Message.FLAG_ALLOW_REPLY
        flags &= ~Message.FLAG_ALLOW_REPLY_ALL

    if is_mfr:
        flags |= Message.FLAG_SENT_BY_MFR
    else:
        flags &= ~Message.FLAG_SENT_BY_MFR

    if check_friends and not parent_key and sender_user_possibly_with_slash_default != MC_DASHBOARD:
        _validateFlags(flags, member_users)
        if check_friends_of is None:
            _validate_members(sender_user_possibly_with_slash_default, sender_is_service_identity, member_users)
        else:
            check_friends_of_is_service_identity = is_service_identity_user(check_friends_of)
            _validate_members(check_friends_of, check_friends_of_is_service_identity, member_users)

    _validate_alert_flags(members)
    _validate_dismiss_ui_flags(dismiss_button_ui_flags, flags)
    _validate_tag(tag, allow_reserved_tag)
    _validate_priority(priority)

    if thread_avatar:
        thread_avatar = _validate_thread_avatar(thread_avatar)

    if branding:
        sender_svc_user = get_service_user_from_service_identity_user(sender_user_possibly_with_slash_default)
        _validate_branding(branding, sender_svc_user)

    attachments = _validate_attachments(attachments)

    sender_user_without_slash_default = remove_slash_default(sender_user_possibly_with_slash_default)  # see comment in sendForm

    step_id = _validate_step_id(step_id, flags, [m for m in member_users if m != sender_user_without_slash_default])

    # make list of recipients
    recipients = list(member_users)
    logging.info("sender: %s" % sender_user_without_slash_default)
    if sender_user_without_slash_default not in recipients:
        recipients.append(sender_user_without_slash_default)

    if parent_key:
        if not is_chat and member_users:
            if set(recipients) != set(parent_message.members):
                logging.info("recipients: %s" % recipients)
                logging.info("parent_message.members: %s" % parent_message.members)
                raise MembersDoNotReflectParentMessageException()
        recipients = None

    key = key or unicode(uuid.uuid4())
    maintenant = now()

    maintenant_detailed = int(time.time() * MICRO_MULTIPLIER)

    if members:
        _alert_flags = reduce(lambda x, y: x | y, (m.alert_flags for m in members))
    else:
        _alert_flags = default_alert_flags

    def alert_flags(member):
        for m in members:
            if m.member == member:
                return m.alert_flags
        return _alert_flags

    class DryRunException(Exception):
        pass

    def put_chat_members(cls, member_emails):
        max_size = size = MAX_CHAT_MEMBERS_SIZE
        chat_members_models = list()
        for member_email in member_emails:
            if size >= max_size:
                size = 0
                chat_members_model = cls(parent=db.Key.from_path(Message.kind(), parent_key or key))
                chat_members_models.append(chat_members_model)
            chat_members_model.members.append(member_email)
            size += len(member_email)
        put_and_invalidate_cache(*chat_members_models)

    def run(recipients, member_users, _alert_flags):
        if parent_key:
            m = Message(key_name=key, parent=pk)

            if step_id:
                # we need to append to the flow statistics
                breadcrumbs, service_identity_user, readable_parent_message_tag, parent_message, previous_message = \
                    _get_flow_stats_breadcrumbs(pk, child_messages)

                on_trans_committed(bump_flow_statistics_by_member_status, member_users[0], service_identity_user,
                                   readable_parent_message_tag, today(), breadcrumbs, step_id, forced_member_status)

            elif child_messages:
                parent_message, previous_message = Message.get([pk, child_messages[-1]])
                if previous_message.key() != parent_message.childMessages[-1]:
                    logging.warn("previous message was not the last message of the thread (1)")
                    previous_message = Message.get(parent_message.childMessages[-1])
            else:
                parent_message = previous_message = Message.get(pk)
                if parent_message.childMessages:
                    logging.warn("previous message was not the last message of the thread (2)")
                    previous_message = Message.get(parent_message.childMessages[-1])

            parent_message.childMessages.append(m.key())
            if is_chat:
                m.members = list()
            elif parent_message.flags & Message.FLAG_SHARED_MEMBERS == Message.FLAG_SHARED_MEMBERS \
                    or sender_user_without_slash_default == parent_message.sender:
                # shared members, or replier is the sender
                logging.info("Copying members from parent message")
                member_users = list(parent_message.members)
                if sender_user_without_slash_default in member_users:  #
                    member_users.remove(sender_user_without_slash_default)  # This hack is to make sure the sender is the last member
                member_users.append(sender_user_without_slash_default)  #
                m.members = member_users
                member_users = list(member_users)
            else:
                # not shared members, and replier is not the sender
                logging.info("Calculating members")
                member_users = [parent_message.sender, sender_user_without_slash_default]
                m.members = list(member_users)
            if parent_message.sender in parent_message.members and \
                    not parent_message.members.index(parent_message.sender) in parent_message.memberStatusses:
                logging.info("Removing " + str(sender_user_without_slash_default) + " from members list " + str(member_users))
                member_users.remove(sender_user_without_slash_default)
            recipients = list(m.members)
            m.flags = flags
            m.originalFlags = flags
            m.timeout = timeout
            if sender_user_without_slash_default != MC_DASHBOARD:
                if sender_is_service_identity:
                    # Services specify their flags
                    m.flags = flags
                    m.originalFlags = flags
                else:
                    # Users inherit the flags of the root message
                    # if chat take pm.flags and remove locked
                    if is_chat:
                        tmp_flags = parent_message.flags
                        tmp_flags &= ~Message.FLAG_LOCKED
                        if is_flag_set(Message.FLAG_CHAT_STICKY, flags):
                            tmp_flags |= Message.FLAG_CHAT_STICKY
                        else:
                            m.timeout = now() + STICKY_TIMEOUT

                        m.flags = m.originalFlags = tmp_flags
                    else:
                        m.flags = m.originalFlags = parent_message.originalFlags or parent_message.flags

            parent_message.timestamp = maintenant_detailed
            m.timestamp = 0 - maintenant_detailed

            # Copy thread properties from parent_messages
            m.thread_avatar_hash = parent_message.thread_avatar_hash
            m.thread_background_color = parent_message.thread_background_color
            m.thread_text_color = parent_message.thread_text_color
        else:
            if step_id:
                # we need to append to the flow statistics
                on_trans_committed(bump_flow_statistics_by_member_status, member_users[0],
                                   add_slash_default(sender_user_without_slash_default),
                                   parse_to_human_readable_tag(tag), today(), list(), step_id, forced_member_status)

            m = Message(key_name=key)
            m.childMessages = list()
            m.flags = flags
            m.originalFlags = flags
            m.timeout = timeout
            if is_chat:
                put_chat_members(ChatWriterMembers, (m.member.email() for m in members if not m.read_only))
                put_chat_members(ChatReaderMembers, (m.member.email() for m in members if m.read_only))
                m.members = list()
            else:
                m.members = list(recipients)
            m.timestamp = maintenant_detailed
            parent_message = None

            if thread_avatar:
                thread_avatar_model = ThreadAvatar.create(key, thread_avatar)
                thread_avatar_model.put()

                m.thread_avatar_hash = thread_avatar_model.avatar_hash

            m.thread_background_color = thread_background_color
            m.thread_text_color = thread_text_color

        _validate_buttons(answers, m.flags)
        _validateSenderReply(sender_answer, answers, recipients, sender_user_without_slash_default)

        m.service_api_updates = parent_message.service_api_updates if parent_message else None
        m.sender = sender_user_without_slash_default
        m.message = message
        m.step_id = step_id

        # If the new message is sent in the same second as the previous message in the thread,
        # then the clients show both messages in the message list. Bumping the creationTimestamp with 1s in this case.
        m.creationTimestamp = maintenant
        if parent_key:
            if previous_message.creationTimestamp >= m.creationTimestamp:
                m.creationTimestamp = previous_message.creationTimestamp + 1

        m.generation = 1
        m.branding = branding
        m.tag = tag
        m.dismiss_button_ui_flags = dismiss_button_ui_flags
        m.sender_type = sender_type

        m.broadcast_type = broadcast_type
        m.broadcast_guid = broadcast_guid
        if parent_message:
            if parent_message.default_priority is None:
                parent_message.default_priority = Message.PRIORITY_NORMAL
                parent_message.default_sticky = False

        m.default_priority = parent_message.default_priority if parent_message else default_priority

        if is_chat and not is_flag_set(Message.FLAG_ALLOW_CHAT_PRIORITY, m.flags):
            m.priority = m.default_priority
        else:
            m.priority = priority

        if m.priority == Message.PRIORITY_URGENT_WITH_ALARM:
            _alert_flags &= ~Message.ALERT_FLAG_SILENT
            _alert_flags |= Message.ALERT_FLAG_VIBRATE
            _alert_flags |= Message.ALERT_FLAG_INTERVAL_5
            if members:
                for member in members:
                    member.alert_flags &= ~Message.ALERT_FLAG_SILENT
                    member.alert_flags |= Message.ALERT_FLAG_VIBRATE
                    member.alert_flags |= Message.ALERT_FLAG_INTERVAL_5

        m.default_sticky = parent_message.default_sticky if parent_message else default_sticky

        if is_chat and not is_flag_set(Message.FLAG_ALLOW_CHAT_STICKY, m.flags):
            if m.default_sticky is False:
                if is_flag_set(Message.FLAG_CHAT_STICKY, m.flags):
                    m.flags &= ~Message.FLAG_CHAT_STICKY
                    m.timeout = now() + STICKY_TIMEOUT
            elif not is_flag_set(Message.FLAG_CHAT_STICKY, m.flags):
                m.flags |= Message.FLAG_CHAT_STICKY
                m.timeout = 0

        m.alert_flags = _alert_flags
        _addButtons(answers, m)
        _add_attachments(attachments, m)
        m.memberStatusses = MemberStatuses()
        if not is_chat:
            for index in xrange(len(member_users)):
                ms = MemberStatus()
                if forced_member_status and forced_member_status.member == member_users[index].email():
                    ms.status = forced_member_status.status
                    ms.received_timestamp = forced_member_status.received_timestamp
                    ms.acked_timestamp = forced_member_status.acked_timestamp
                    ms.dismissed = forced_member_status.button_id is None
                    ms.button_index = -1 if ms.dismissed else m.buttons[forced_member_status.button_id].index
                    ms.custom_reply = forced_member_status.custom_reply
                    ms.ack_device = u"mobile" if get_current_mobile() else u"web"
                else:
                    ms.status = 0
                    ms.received_timestamp = 0
                    ms.acked_timestamp = 0
                    ms.dismissed = False
                    ms.button_index = -1
                    ms.custom_reply = None
                    ms.ack_device = None
                ms.index = index
                ms.form_result = None
                m.memberStatusses.add(ms)
            if sender_answer:
                index = member_users.index(sender_user_without_slash_default)
                ms = m.memberStatusses[index]
                ms.status = MemberStatus.STATUS_RECEIVED | MemberStatus.STATUS_ACKED
                ms.received_timestamp = maintenant
                ms.acked_timestamp = maintenant
                ms.button_index = m.buttons[sender_answer].index
            if sender_type == FriendDetail.TYPE_SERVICE:
                mems = list(m.members)
                mems.remove(sender_user_without_slash_default)
                m.addStatusIndex(mems, Message.SERVICE_MESSAGE_DEFAULT_MEMBER_INDEX_STATUSSES)
            else:
                m.addStatusIndex(m.members, Message.USER_MESSAGE_DEFAULT_MEMBER_INDEX_STATUSSES)
            for mem in m.members:
                m.member_status_index.append(mem.email())
            m.removeStatusIndex(m.sender, Message.MEMBER_INDEX_STATUS_NOT_RECEIVED)
            if forced_member_status:
                member_user = users.User(forced_member_status.member)
                if is_flag_set(MemberStatus.STATUS_RECEIVED, forced_member_status.status):
                    m.removeStatusIndex(member_user, Message.MEMBER_INDEX_STATUS_NOT_RECEIVED)
                if is_flag_set(MemberStatus.STATUS_READ, forced_member_status.status) \
                        or is_flag_set(MemberStatus.STATUS_ACKED, forced_member_status.status):
                    m.removeStatusIndex(member_user, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX)
                if is_flag_set(MemberStatus.STATUS_DELETED, forced_member_status.status):
                    m.removeStatusIndex(member_user, Message.MEMBER_INDEX_STATUS_NOT_DELETED)

        put = list()
        put.append(m)
        if parent_key:
            put.append(parent_message)
        if dry_run:
            raise DryRunException()
        else:
            db.put(put)

        return m, recipients, parent_message

    try:
        if db.is_in_transaction():
            m, recipients, parent_message = run(recipients, member_users, _alert_flags)
        else:
            m, recipients, parent_message = db.run_in_transaction(run, recipients, member_users, _alert_flags)
    except DryRunException:
        return None

    if m.timeout > 0:
        countdown = m.timeout - now()
        if countdown <= 0:
            countdown = 1

        if is_chat:
            deferred.defer(_remove_sticky_message_for_all_members, key, parent_key, context,
                           _countdown=countdown, _queue=SCHEDULED_QUEUE, _transactional=db.is_in_transaction())
        else:
            deferred.defer(_remove_message_for_all_members, key, parent_key, context,
                           _countdown=countdown, _queue=SCHEDULED_QUEUE, _transactional=db.is_in_transaction())

    if is_chat:
        deferred.defer(_distribute_new_chat_message_to_all_members, ChatWriterMembers, key, parent_key, context,
                       _transactional=db.is_in_transaction())
        if parent_key:
            deferred.defer(_distribute_new_chat_message_to_all_members, ChatReaderMembers, key, parent_key, context,
                           _transactional=db.is_in_transaction())

        if parent_message and parent_message.service_api_updates:
            if not sender_is_service_identity:
                service_user, service_identity = get_service_identity_tuple(parent_message.service_api_updates)
                profile_info = get_user_profile(sender_user_possibly_with_slash_default)
                new_chat_message(new_chat_message_response_handler, logServiceError, get_service_profile(service_user),
                                 parent_message_key=parent_message.mkey,
                                 message_key=m.mkey,
                                 message=message,
                                 answers=[AnswerTO.fromButtonTO(b) for b in answers],
                                 timestamp=m.creationTimestamp,
                                 tag=parent_message.tag,
                                 service_identity=service_identity,
                                 sender=UserDetailsTO.fromUserProfile(profile_info),
                                 attachments=attachments)
    else:
        # Filter service users and non-existing users
        recipients = [recipient
                      for recipient in recipients
                      if recipient != MC_DASHBOARD and '/' not in recipient.email()]
        recipients = [recipient
                      for (recipient, profile) in zip(recipients, db.get(map(get_profile_key, recipients)))
                      if profile and isinstance(profile, UserProfile)]

        # Define previous message
        previous_thread_message = None
        if not is_chat and parent_message:
            if len(parent_message.childMessages) > 1:
                previous_thread_message = db.get(parent_message.childMessages[-2])
            else:
                previous_thread_message = parent_message


        def _create_request(recipient):
            member = None if m.sharedMembers or m.sender == recipient else recipient
            return _create_new_message_request(m, parent_message, context, alert_flags(recipient), member)


        context_list = list()
        for recipient in recipients:
            request = _create_request(recipient)
            context_list += _update_new_message_request_and_create_capi_call(recipient, m, parent_message,
                                                                             previous_thread_message, request, context,
                                                                             sender_is_service_identity)
        db.put(context_list)

        for recipient in recipients:
            request = _create_request(recipient)
            try_or_defer(_send_newMessage_channel_api_call, recipient, request, context)

    if m.broadcast_guid and not m.parent_key():
        slog(msg_="Broadcast stats sent", function_=log_analysis.BROADCAST_STATS, service=m.sender.email(),
             type_=log_analysis.BROADCAST_STATS_SENT, broadcast_guid=broadcast_guid)

    return m


def _send_newMessage_channel_api_call(recipient, request, context):
    msg_dict = serialize_complex_value(request.message, MessageTO, False)
    msg_dict['context'] = context
    channel.send_message(recipient, u'rogerthat.messaging.newMessage', message=msg_dict)


def _create_new_message_request(m, parent_message, context, alert_flags, member=None, make_read_only=False):
    request = NewMessageRequestTO()
    request.message = MessageTO.fromMessage(m, member)
    request.message.context = context
    request.message.alert_flags = alert_flags
    request.message.thread_size = 1 + (len(parent_message.childMessages) if parent_message else 0)
    if make_read_only:  # eg. for chat readers
        request.message.flags &= ~Message.FLAG_ALLOW_REPLY
        request.message.flags &= ~Message.FLAG_ALLOW_REPLY_ALL
    return request


@returns([RpcCAPICall])
@arguments(recipient=users.User, m=Message, parent_message=Message, previous_thread_message=Message,
           request=NewMessageRequestTO, context=unicode, sender_is_service_identity=bool)
def _update_new_message_request_and_create_capi_call(recipient, m, parent_message, previous_thread_message, request,
                                                     context, sender_is_service_identity):
    if parent_message and parent_message.mkey == m.mkey:
        parent_message = None  # Some protection for the logic being used later on in this function

    is_chat = is_flag_set(Message.FLAG_DYNAMIC_CHAT, m.flags)
    if not is_chat:
        # Silence message in a flow use case ran from the web
        try:
            previous_thread_message_member_status = previous_thread_message.memberStatusses[previous_thread_message.members.index(recipient)] if previous_thread_message else None
            if request.message.alert_flags < Message.ALERT_FLAG_RING_5 \
                and ((previous_thread_message_member_status
                        and abs(m.timestamp) - previous_thread_message_member_status.acked_timestamp < 30
                        and previous_thread_message_member_status.ack_device == "web")
                     or (context and context.startswith('__web__'))):
                request.message.alert_flags = Message.ALERT_FLAG_SILENT
        except:
            logging.exception("Failed to silence message to phone.")

    # Determine priority
    kwargs = {"request": request, DO_NOT_SAVE_RPCCALL_OBJECTS:True}
    if not (parent_message is None and is_chat) \
        and (recipient == m.sender or request.message.alert_flags == Message.ALERT_FLAG_SILENT):
        kwargs[CAPI_KEYWORD_ARG_PRIORITY] = PRIORITY_NORMAL
    else:
        kwargs[CAPI_KEYWORD_ARG_PRIORITY] = PRIORITY_HIGH
        kwargs[CAPI_KEYWORD_ARG_APPLE_PUSH_MESSAGE] = _generate_push_json(m, parent_message, recipient, sender_is_service_identity)

    # Skip or defer kick for a possible follow-up message
    if not is_chat and sender_is_service_identity and (context or parent_message):
        kwargs[DEFER_KICK] = True

    # Do not send message to originating device
    if not is_chat and (recipient == m.sender or is_flag_set(Message.FLAG_SENT_BY_JS_MFR, m.flags)):
        current_mobile = users.get_current_mobile()
        if current_mobile:
            kwargs[SKIP_ACCOUNTS] = [current_mobile.account]

    ctxs = newMessage(new_message_response_handler, logError, recipient, **kwargs)
    for ctx in ctxs:
        ctx.message = m.key()
        ctx.is_chat = is_chat

    return ctxs

@returns()
@arguments(chat_members_key=db.Key, request=UpdateMessageRequestTO, offset=(int, long))
def _send_delete_chat_message(chat_members_key, request, offset=0):
    chat_members = db.get(chat_members_key)
    if not chat_members:
        return

    new_offset = offset + 100
    recipients = map(users.User, chat_members.members[offset:new_offset])

    recipients_count = len(recipients)
    if not recipients_count:
        return


    context_list = list()
    for recipient in recipients:
        context_list += updateMessage(update_message_response_handler, logError, recipient, request=request,
                                      DO_NOT_SAVE_RPCCALL_OBJECTS=True)
    db.put(context_list)

    if new_offset < len(chat_members.members):
        deferred.defer(_send_delete_chat_message, chat_members_key, request, new_offset)


def _remove_sticky_message_for_all_members(message_key, parent_message_key, context):
    if not parent_message_key:
        return
    # existence 0 DELETED
    # existence 1 ACTIVE
    parent_message = get_message(parent_message_key, None)
    last_child_message = None if not parent_message.childMessages else parent_message.childMessages[-1].name()
    request = UpdateMessageRequestTO.create(parent_message_key=parent_message_key,
                                            message_key=message_key,
                                            last_child_message=last_child_message,
                                            existence=0)

    run_job(_get_chat_members, [ChatMembers, parent_message_key],
            _send_delete_chat_message, [request])

def _remove_message_for_all_members(message_key, parent_message_key, context):
    # existence 0 DELETED
    # existence 1 ACTIVE
    parent_message = get_message(parent_message_key if parent_message_key else message_key, None)
    last_child_message = None if not parent_message.childMessages else parent_message.childMessages[-1].name()
    request = UpdateMessageRequestTO.create(parent_message_key=parent_message_key,
                                            message_key=message_key,
                                            last_child_message=last_child_message,
                                            existence=0)

    if message_key:
        if parent_message_key:
            message = get_message(message_key, parent_message_key)
        else:
            message = parent_message
        for ms in message.memberStatusses:
            ms.status |= MemberStatus.STATUS_DELETED
        for member in message.members:
            message.removeStatusIndex(member, (Message.MEMBER_INDEX_STATUS_NOT_DELETED, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX))
        message.put()

    context_list = list()
    for member in parent_message.members:
        context_list += updateMessage(update_message_response_handler, logError, member, request=request,
                                      DO_NOT_SAVE_RPCCALL_OBJECTS=True)
    db.put(context_list)


def _distribute_new_chat_message_to_all_members(cls, message_key, parent_message_key, context):
    run_job(_get_chat_members, [cls, parent_message_key or message_key],
            _distribute_chat_message, [message_key, parent_message_key, context],
            qry_transactional=True)


def _get_chat_members(cls, thread_key):
    return cls.all(keys_only=True).ancestor(cls.create_parent_key(thread_key))


@returns()
@arguments(chat_members_key=db.Key, message_key=unicode, parent_message_key=unicode, context=unicode, offset=(int, long))
def _distribute_chat_message(chat_members_key, message_key, parent_message_key, context, offset=0):
    chat_members = db.get(chat_members_key)
    if not chat_members:
        return

    read_only = isinstance(chat_members, ChatReaderMembers)
    new_offset = offset + 100
    recipients = chat_members.members[offset:new_offset]

    recipients_count = len(recipients)
    if not recipients_count:
        return

    message = get_message(message_key, parent_message_key)
    if not read_only:
        # remove the sender from the recipients
        try:
            recipients.remove(message.sender.email())
            if recipients_count == 1:
                return  # we just removed the only recipient (writer)
        except ValueError:
            pass  # sender was not in recipients

    parent_message = get_message(parent_message_key, None) if parent_message_key else None
    _distribute_chat_message_to_recipients(map(users.User, recipients), message, parent_message, context, read_only)

    if new_offset < len(chat_members.members):
        deferred.defer(_distribute_chat_message, chat_members_key, message_key, parent_message_key, context, new_offset)


@returns()
@arguments(recipients=[users.User], message=Message, parent_message=Message, context=unicode, read_only=bool)
def _distribute_chat_message_to_recipients(recipients, message, parent_message, context, read_only):
    request = _create_new_message_request(message, parent_message, context, message.alert_flags, member=None,
                                          make_read_only=read_only)
    requests = [request]
    if read_only:
        if request.message.thread_size == 1:
            return  # readers shouldn't receive an empty chat thread
        elif request.message.thread_size == 2:
            # readers should get the parent_message (containing the chat info) as well
            requests.insert(0, _create_new_message_request(parent_message, None, context, parent_message.alert_flags,
                                                           member=None, make_read_only=read_only))

    context_list = list()
    for recipient in recipients:
        for request in requests:
            context_list += _update_new_message_request_and_create_capi_call(recipient, message, parent_message,
                                                                             None, request, context, True)
    db.put(context_list)


def _delete_chat_message(chat_members_key, offset=0):
    chat_members = db.get(chat_members_key)
    if not chat_members:
        return

    new_offset = offset + 100
    recipients = chat_members.members[offset:new_offset]

    recipients_count = len(recipients)
    if not recipients_count:
        return

    for m in chat_members.members:
        delete_conversation(users.User(m), chat_members.parent_message_key, True)

    deferred.defer(_delete_chat_message, chat_members_key, new_offset)


@returns(Message)
@arguments(service_identity_user=users.User, topic=unicode, description=unicode, writers=[UserMemberTO],
           readers=[UserMemberTO], tag=unicode, context=unicode, chat_flags=int, metadata=[KeyValueTO],
           thread_avatar=str, thread_background_color=unicode, thread_text_color=unicode,
           default_priority=(int, long), default_sticky=bool)
def start_chat(service_identity_user, topic, description, writers, readers, tag, context, chat_flags, metadata=None,
               thread_avatar=None, thread_background_color=None, thread_text_color=None,
               default_priority=Message.PRIORITY_NORMAL, default_sticky=False):
    logging.info('Starting chat with %s writers and %s readers', len(writers), len(readers))
    message_flags = Message.FLAG_ALLOW_REPLY | Message.FLAG_ALLOW_REPLY_ALL | Message.FLAG_SHARED_MEMBERS | Message.FLAG_DYNAMIC_CHAT

    if chat_flags:
        # Validate flags
        if chat_flags < 0 or chat_flags > sum(ChatFlags.all()):
            raise InvalidFlagsException()

        for cf in ChatFlags.all():
            if is_flag_set(cf, chat_flags):
                message_flag = ChatFlags.message_flag(cf)
                if message_flag >= 0:
                    message_flags |= message_flag
                else:
                    message_flags &= ~message_flag

    if metadata in (None, MISSING):
        metadata = list()

    content = json.dumps(_create_chat_data(topic, description, _create_chat_metadata(metadata)))

    members = writers + readers

    def trans():
        message = sendMessage(service_identity_user, members, message_flags, 0, None, content, [], None, None, tag,
                              context=context, check_friends=False, thread_avatar=thread_avatar,
                              thread_background_color=thread_background_color, thread_text_color=thread_text_color,
                              default_priority=default_priority, default_sticky=default_sticky)
        message.service_api_updates = service_identity_user
        message.put()
        return message

    message = run_in_transaction(trans, xg=True)

    sendMessage(message.sender, [], message.flags, message.timeout, message.mkey, u"%s\n\n%s" % (topic, description),
                [], None, None, None, default_alert_flags=Message.ALERT_FLAG_SILENT)

    return message


@returns([dict])
@arguments(metadata=[KeyValueTO])
def _create_chat_metadata(metadata):
    return [dict(k=m.key, v=m.value) for m in metadata]


@returns(dict)
@arguments(topic=unicode, description=unicode, metadata_dicts=[dict])
def _create_chat_data(topic, description, metadata_dicts):
    return dict(t=topic, d=description, i=metadata_dicts)


@returns(bool)
@arguments(service_user=users.User, parent_message_key=unicode, topic=unicode, description=unicode,
           flags=(int, NoneType), metadata=[KeyValueTO], thread_avatar=str, thread_background_color=unicode,
           thread_text_color=unicode)
def update_chat(service_user, parent_message_key, topic=None, description=None, flags=None, metadata=None,
                thread_avatar=None, thread_background_color=None, thread_text_color=None):

    if thread_avatar:
        thread_avatar = _validate_thread_avatar(thread_avatar)

    def trans(topic, description, flags, metadata):
        parent_message = get_message(parent_message_key, None)
        if not parent_message:
            raise ParentMessageNotFoundException()

        if get_service_user_from_service_identity_user(parent_message.sender) != service_user:
            raise MessageNotFoundException()

        if not is_flag_set(Message.FLAG_DYNAMIC_CHAT, parent_message.flags):
            raise MessageNotFoundException()

        to_put = set()

        message_updated = False
        chat_data = json.loads(parent_message.message)
        if topic in (None, MISSING):
            topic = chat_data['t']
        else:
            message_updated |= (topic != chat_data['t'])

        if description in (None, MISSING):
            description = chat_data['d']
        else:
            message_updated |= (description != chat_data['d'])

        if metadata in (None, MISSING):
            kv_dicts = chat_data['i']
        else:
            kv_dicts = _create_chat_metadata(metadata)
            if not message_updated:
                # check if metadata has changed
                for kv_dict, old_kv_dict in zip(kv_dicts, chat_data['i']):
                    if kv_dict['k'] != old_kv_dict['k']:
                        message_updated = True
                        break
                    if kv_dict['v'] != old_kv_dict['v']:
                        message_updated = True
                        break

        if message_updated:
            parent_message.message = json.dumps(_create_chat_data(topic, description, kv_dicts))
            to_put.add(parent_message)

        messages = None
        def get_messages():
            return [parent_message] + db.get(parent_message.childMessages)

        flags_updated = False
        if flags not in (None, MISSING):
            messages = get_messages()
            for chat_flag in ChatFlags.all():
                message_flag = ChatFlags.message_flag(chat_flag)
                if is_flag_set(chat_flag, flags):
                    set_or_unset_flag = set_flag if message_flag >= 0 else unset_flag
                else:
                    set_or_unset_flag = unset_flag if message_flag >= 0 else set_flag
                for m in messages:
                    m.flags = set_or_unset_flag(m.flags, message_flag)
            to_put = to_put.union(messages)
            flags_updated = True

        avatar_updated = False
        if thread_avatar is not None:
            if thread_avatar == "":
                # need to remove the avatar
                db.delete(ThreadAvatar.create_key(parent_message_key))
            else:
                thread_avatar_model = ThreadAvatar.create(parent_message_key, thread_avatar)
                to_put.add(thread_avatar_model)

            messages = messages or get_messages()
            for m in messages:
                m.thread_avatar_hash = None if thread_avatar == "" else thread_avatar_model.avatar_hash
            to_put = to_put.union(messages)
            avatar_updated = True

        background_color_updated = False
        if thread_background_color is not None:
            messages = messages or get_messages()
            for m in messages:
                m.thread_background_color = None if thread_background_color == "" else thread_background_color
            to_put = to_put.union(messages)
            background_color_updated = True

        text_color_updated = False
        if thread_text_color is not None:
            messages = messages or get_messages()
            for m in messages:
                m.thread_text_color = None if thread_text_color == "" else thread_text_color
            to_put = to_put.union(messages)
            text_color_updated = True

        if to_put:
            db.put(to_put)
            deferred.defer(_run_update_chat_job, parent_message_key, flags_updated, message_updated, avatar_updated,
                           background_color_updated, text_color_updated, _transactional=True)

        return bool(to_put)

    return db.run_in_transaction(trans, topic, description, flags, metadata)


ChatMessagesListResult = namedtuple('ChatMessagesListResult', 'cursor messages user_profiles')


@returns(ChatMessagesListResult)
@arguments(service_user=users.User, parent_message_key=unicode, cursor=unicode)
def list_chat_messages(service_user, parent_message_key, cursor=None):
    parent_message = get_message(parent_message_key, None)
    if not parent_message:
        raise ParentMessageNotFoundException()

    if get_service_user_from_service_identity_user(parent_message.sender) != service_user:
        raise MessageNotFoundException()

    if not is_flag_set(Message.FLAG_DYNAMIC_CHAT, parent_message.flags):
        raise MessageNotFoundException()

    messages = db.get(parent_message.childMessages)
    senders = list({m.sender for m in messages if m.sender_type == FriendDetail.TYPE_USER})
    user_profiles = dict(zip(senders, get_profile_infos(senders, allow_none_in_results=True)))
    return ChatMessagesListResult(cursor=None, messages=messages, user_profiles=user_profiles)


@returns(Message)
@arguments(service_user=users.User, parent_key=unicode, message=unicode, answers=[AnswerTO], attachments=[AttachmentTO],
           sender=(unicode, BaseMemberTO), priority=(int, long), sticky=bool, tag=unicode, alert_flags=(int, long))
def send_chat_message(service_user, parent_key, message, answers=None, attachments=None, sender=None, priority=None, sticky=False, tag=None, alert_flags=Message.ALERT_FLAG_VIBRATE):
    from rogerthat.bizz.service import valididate_app_id_for_service_identity

    def trans():
        parent_message = get_message(parent_key, None)
        if not parent_message:
            raise ParentMessageNotFoundException()

        if get_service_user_from_service_identity_user(parent_message.sender) != service_user:
            raise MessageNotFoundException()

        if not is_flag_set(Message.FLAG_DYNAMIC_CHAT, parent_message.flags):
            raise MessageNotFoundException()

        return parent_message

    parent_message = db.run_in_transaction(trans)

    if sender:
        si = get_service_identity(add_slash_default(parent_message.sender))
        if isinstance(sender, MemberTO):
            if sender.app_id is MISSING:
                sender.app_id = si.app_id
            else:
                valididate_app_id_for_service_identity(si, sender.app_id)
            sender_user = create_app_user(users.User(sender.member), sender.app_id)
        else:
            sender_user = create_app_user(users.User(sender), si.app_id)
    else:
        sender_user = None

    if not priority:
        priority = Message.PRIORITY_NORMAL

    tmp_flags = parent_message.flags
    if sticky:
        tmp_flags |= Message.FLAG_CHAT_STICKY
    else:
        tmp_flags &= ~Message.FLAG_CHAT_STICKY

    m = sendMessage(sender_user if sender_user else parent_message.sender, [], tmp_flags, parent_message.timeout,
                    parent_key, message, answers or [], None, None, tag, is_mfr=False, attachments=attachments,
                    priority=priority, default_alert_flags=alert_flags)
    return m



@returns([UserMemberTO])
@arguments(service_identity_user=users.User, members=[(unicode, MemberTO)], alert_flags=int, read_only=bool)
def member_list_to_usermember_list(service_identity_user, members, alert_flags, read_only=False):
    from rogerthat.bizz.service import valididate_app_id_for_service_identity
    mm = []
    if members != MISSING:
        si = get_service_identity(service_identity_user)
        for m in members:
            if isinstance(m, MemberTO):
                if m.app_id is MISSING:
                    m.app_id = si.app_id
                else:
                    valididate_app_id_for_service_identity(si, m.app_id)
                mm.append(UserMemberTO.fromMemberTO(m, read_only))
            else:
                mm.append(UserMemberTO(create_app_user(users.User(m), si.app_id), alert_flags, read_only))
    return mm

@returns(int)
@arguments(responder=users.User, message_key=unicode, message_parent_key=unicode, button_id=unicode, custom_reply=unicode, \
           timestamp=int)
def ackMessage(responder, message_key, message_parent_key, button_id, custom_reply, timestamp):
    def run():
        azzert(db.is_in_transaction())
        r = _ack_message(message_key, message_parent_key, responder, timestamp, button_id, custom_reply)
        if not r:
            return r
        message, ms, locked = r
        db.put_async(message)
        return message, ms, locked

    try:
        result = db.run_in_transaction(run)
        if not result:
            return MESSAGE_ACKED_NO_CHANGES
        else:
            message, ms, locked = result
    except MessageLockedException:
        return MESSAGE_ACK_FAILED_LOCKED
    _send_updates(responder, message, ms, True, ServiceProfile.CALLBACK_MESSAGING_ACKNOWLEDGED)
    if locked:
        _send_locked(message, DirtyBehavior.NORMAL)
    if message.tag in ackListeners \
        and (message.sender == MC_DASHBOARD \
             or message.tag.startswith(MC_RESERVED_TAG_PREFIX) \
             or hasattr(message, 'follow_up_id')):
        try_or_defer(ackListeners[message.tag], message)
    return MESSAGE_ACKED

@returns(int)
@arguments(responder=users.User, message_key=unicode, parent_message_key=unicode, button_id=unicode, result=WidgetResult, \
           timestamp=int, form_type=unicode)
def submitForm(responder, message_key, parent_message_key, button_id, result, timestamp, form_type):

    def run():
        r = _ack_message(message_key, parent_message_key, responder, timestamp, button_id, None, is_form=True)
        if not r:
            return r
        message, ms, locked = r
        if result:
            ms.form_result = FormResult()
            ms.form_result.type = result.TYPE
            ms.form_result.result = WIDGET_RESULT_MAPPING[result.TYPE].to_model_conversion(result)
        db.put_async(message)
        return message, ms, locked

    try:
        r = db.run_in_transaction(run)
        if r:
            message, ms, locked = r
        else:
            return MESSAGE_ACKED_NO_CHANGES
    except MessageLockedException:
        return MESSAGE_ACK_FAILED_LOCKED

    _send_form_updated(responder, message, parent_message_key, ms, button_id)

    if locked:
        _send_locked(message, DirtyBehavior.NORMAL)

    if message.tag in ackListeners \
        and (message.sender == MC_DASHBOARD \
             or message.tag.startswith(MC_RESERVED_TAG_PREFIX) \
             or hasattr(message, 'follow_up_id')):
        try_or_defer(ackListeners[message.tag], message)

    return MESSAGE_ACKED

@returns(NoneType)
@arguments(user=users.User, parent_message_key=unicode, message_keys=[unicode], mobile=Mobile)
def markMessagesAsRead(user, parent_message_key, message_keys, mobile=None):
    deferred.defer(_markMessagesAsRead, user, parent_message_key, message_keys, mobile, _countdown=1)

def _markMessagesAsRead(user, parent_message_key, message_keys, mobile):
    def run():
        datastore_keys = list()
        first_key_is_parent_message = 'no'
        if parent_message_key in message_keys:
            message_keys.remove(parent_message_key)
            datastore_keys.append(get_message_key(parent_message_key, None))
            first_key_is_parent_message = 'yes'
        elif parent_message_key:
            datastore_keys.append(get_message_key(parent_message_key, None))
            first_key_is_parent_message = 'skip'

        for message_key in message_keys:
            datastore_keys.append(get_message_key(message_key, parent_message_key))

        puts = db.get(datastore_keys)
        if first_key_is_parent_message == 'skip':
            parent_message = puts.pop(0)
            datastore_keys.pop(0)
        elif first_key_is_parent_message == 'yes':
            parent_message = puts[0]
        else:
            parent_message = None

        puts = filter(lambda m: m and not is_flag_set(Message.FLAG_DYNAMIC_CHAT, m.flags), puts)
        if not puts:
            return []

        for datastore_key, m in zip(datastore_keys, puts):
            if not m:
                logging.warning("Could not find message with key %s!" % datastore_key.name())
                continue
            ms = m.memberStatusses[m.members.index(user)]
            was_already_read = is_flag_set(MemberStatus.STATUS_READ, ms.status)
            ms.status |= MemberStatus.STATUS_READ
            m.removeStatusIndex(user, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX)
            if m.step_id and not was_already_read:
                # assuming that the length of the message_keys is 1 in this case,
                # so there will never be more than 1 defer scheduled (transaction won't fail)
                bump_flow_statistics_for_message_update(user, [FlowStatistics.STATUS_READ], m, parent_message)

        puts = filter(None, puts)
        db.put(puts)
        for message in puts:
            request = MemberStatusUpdateRequestTO.fromMessageAndMember(message, user)
            kwargs = dict()
            current_mobile = mobile
            if current_mobile:
                kwargs[SKIP_ACCOUNTS] = [current_mobile.account]
                channel.send_message(user, u'rogerthat.messaging.memberUpdate', \
                                     update=serialize_complex_value(request, MemberStatusUpdateRequestTO, False))
            updateMessageMemberStatus(message_member_response_handler, logError, user, request=request, **kwargs)
        return puts

    xg_on = db.create_transaction_options(xg=True)
    messages = db.run_in_transaction_options(xg_on, run)
    for message in messages:
        if message.broadcast_guid and not message.parent_key():
            slog(msg_="Broadcast stats read", function_=log_analysis.BROADCAST_STATS, service=message.sender.email(),
                 type_=log_analysis.BROADCAST_STATS_READ, broadcast_guid=message.broadcast_guid)

@returns(Message)
@arguments(service_user_or_app_user=users.User, message_key=unicode, message_parent_key=unicode, dirty_behavior=int)
def lockMessage(service_user_or_app_user, message_key, message_parent_key, dirty_behavior):
    if (dirty_behavior not in DirtyBehavior.ALL):
        raise InvalidDirtyBehaviorException()

    def run():
        message = get_message(message_key, message_parent_key)
        # Human user: the person locking this message must be the sender
        # Service: check that the message sender (= a service_identity_user) belongs to the service who locks this message
        if not message or get_service_user_from_service_identity_user(message.sender) != get_service_user_from_service_identity_user(service_user_or_app_user):
            raise MessageNotFoundException()
        if message.flags & Message.FLAG_LOCKED == Message.FLAG_LOCKED:
            raise MessageLockedException()
        message.flags |= Message.FLAG_LOCKED

        for member in message.members:
            if member == message.sender:
                continue
            if dirty_behavior == DirtyBehavior.CLEAR_DIRTY:
                message.removeStatusIndex(member, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX)
            elif dirty_behavior == DirtyBehavior.MAKE_DIRTY:
                message.addStatusIndex(member, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX)
                ms = message.memberStatusses[message.members.index(member)]
                ms.status &= ~MemberStatus.STATUS_READ
            else:  # DirtyBehavior.NORMAL -- add SHOW_IN_INBOX when message was not ACKED
                ms = message.memberStatusses[message.members.index(member)]
                if (ms.status & MemberStatus.STATUS_ACKED) != MemberStatus.STATUS_ACKED:
                    message.addStatusIndex(member, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX)
                    ms.status &= ~MemberStatus.STATUS_READ
        message.generation += 1
        message.put()
        return message
    message = db.run_in_transaction(run)
    _send_locked(message, dirty_behavior)
    return message


def is_tmp_key(message_key):
    return message_key.startswith('_tmp/')


@returns(Message)
@arguments(service_user=users.User, message_key=unicode, message_required=bool)
def _get_and_validate_message(service_user, message_key, message_required=True):
    message = get_message(message_key, None)
    if not message and message_required:
        raise ParentMessageNotFoundException()
    elif message and get_service_user_from_service_identity_user(message.sender) != service_user:
        raise ParentMessageNotFoundException()
    return message


@returns(bool)
@arguments(service_user=users.User, parent_message_key=unicode, writers=[(unicode, MemberTO)], readers=[(unicode, MemberTO)])
def add_members_to_chat(service_user, parent_message_key, writers, readers):

    def trans():
        message = _get_and_validate_message(service_user, parent_message_key)
        service_identity_user = create_service_identity_user(service_user,
                                                             get_identity_from_service_identity_user(message.sender))
        writer_user_members = member_list_to_usermember_list(service_identity_user, writers,
                                                             alert_flags=message.alert_flags, read_only=False)
        reader_user_members = member_list_to_usermember_list(service_identity_user, readers,
                                                             alert_flags=message.alert_flags, read_only=True)

        # dict with users to be added to the chat { email : (user_member, read_only) }
        users_dict = { m.member.email(): (m, True) for m in reader_user_members }
        users_dict.update({ m.member.email(): (m, False) for m in writer_user_members })

        to_put = set()
        readers_becoming_writers = list()
        # filter the writers and readers which were already member of the chat
        chat_members_list = ChatMembers.list_by_thread_and_chat_members(parent_message_key, users_dict.keys())
        for chat_members_model in chat_members_list:
            for chat_member in reversed(chat_members_model.members):
                user_member_tuple = users_dict.get(chat_member)
                if user_member_tuple:
                    user_member, read_only = user_member_tuple
                    if (not read_only and not chat_members_model.is_read_only()) or read_only:
                        # if writer_user was already a WRITER,
                        # or reader_user was already a READER,
                        # or reader_user was already a WRITER
                        logging.info('%s was already a member in chat %s',
                                     user_member.member.email(), parent_message_key)
                        del users_dict[chat_member]
                    elif (not read_only and chat_members_model.is_read_only()):
                        # if writer_user was a READER, then remove it from the readers model.
                        # it will be added to the writers later.
                        chat_members_model.members.remove(chat_member)
                        to_put.add(chat_members_model)
                        readers_becoming_writers.append(user_member.member)

        chat_members_cache = dict()
        job_guid = str(uuid.uuid4())
        for email, (user_member, read_only) in users_dict.iteritems():
            cls = ChatReaderMembers if read_only else ChatWriterMembers
            chat_members_model = chat_members_cache.get(cls)
            if not chat_members_model:
                chat_members_model = cls.get_last_by_thread(parent_message_key)
            if not chat_members_model \
                    or chat_members_model.members_size() + len(email) > MAX_CHAT_MEMBERS_SIZE:
                # need to create a new model because there was no model yet, or the model became too big
                chat_members_model = cls(parent=db.Key.from_path(Message.kind(), parent_message_key))

            chat_members_cache[cls] = chat_members_model

            chat_members_model.members.append(email)
            to_put.add(chat_members_model)
            to_put.add(AddMemberToChatJob(parent=AddMemberToChatJob.create_parent_key(parent_message_key),
                                          guid=job_guid,
                                          user=user_member.member,
                                          read_only=user_member.read_only))

        if to_put:
            put_and_invalidate_cache(*to_put)
            deferred.defer(_run_add_to_chat_job, parent_message_key, job_guid, _transactional=True)
            return True
        return False

    xg_on = db.create_transaction_options(xg=True)
    return db.run_in_transaction_options(xg_on, trans)


def _get_chat_job_qry(cls, parent_message_key, guid):
    return cls.list_by_guid(parent_message_key, guid)


@returns()
@arguments(parent_message_key=unicode, job_guid=unicode)
def _run_add_to_chat_job(parent_message_key, job_guid):
    message = get_message(parent_message_key, None)
    run_job(_get_chat_job_qry, [AddMemberToChatJob, parent_message_key, job_guid],
            _send_add_to_chat, [message])


@returns()
@arguments(job=AddMemberToChatJob, parent_message=Message)
def _send_add_to_chat(job, parent_message):
    flags = parent_message.flags
    if job.read_only:
        flags &= ~Message.FLAG_ALLOW_REPLY
        flags &= ~Message.FLAG_ALLOW_REPLY_ALL
    else:
        flags |= Message.FLAG_ALLOW_REPLY
        flags |= Message.FLAG_ALLOW_REPLY_ALL

    last_child_message = None if not parent_message.childMessages else parent_message.childMessages[-1].name()

    request = UpdateMessageRequestTO.create(parent_message_key=parent_message.mkey,
                                            message_key=None,
                                            last_child_message=last_child_message,
                                            flags=flags,
                                            existence=1)

    updateMessage(update_message_response_handler, logError, job.user, request=request)


@returns()
@arguments(parent_message_key=unicode, flags_updated=bool, message_updated=bool, avatar_updated=bool,
           background_color_updated=bool, text_color_updated=bool)
def _run_update_chat_job(parent_message_key, flags_updated, message_updated, avatar_updated, background_color_updated,
                         text_color_updated):
    run_job(_get_chat_members, [ChatMembers, parent_message_key],
            _send_update_chat, [flags_updated, message_updated, avatar_updated, background_color_updated, text_color_updated])


@returns()
@arguments(chat_members_key=db.Key, flags_updated=bool, message_updated=bool, avatar_updated=bool,
           background_color_updated=bool, text_color_updated=bool, offset=(int, long))
def _send_update_chat(chat_members_key, flags_updated, message_updated, avatar_updated, background_color_updated,
                      text_color_updated, offset=0):
    chat_members = db.get(chat_members_key)
    if not chat_members:
        return

    parent_message = get_message(chat_members.parent_message_key, None)
    last_child_message = None if not parent_message.childMessages else parent_message.childMessages[-1].name()

    requests = list()
    if flags_updated or avatar_updated or background_color_updated or text_color_updated:
        # update every message in the chat
        kwargs = dict(parent_message_key=parent_message.mkey,
                      message_key=None,
                      last_child_message=last_child_message)

        if flags_updated:
            flags = parent_message.flags
            if not is_flag_set(Message.FLAG_ALLOW_REPLY | Message.FLAG_ALLOW_REPLY_ALL, flags) \
                    or chat_members.is_read_only():
                flags &= ~Message.FLAG_ALLOW_REPLY
                flags &= ~Message.FLAG_ALLOW_REPLY_ALL
            else:
                flags |= Message.FLAG_ALLOW_REPLY
                flags |= Message.FLAG_ALLOW_REPLY_ALL
            kwargs['flags'] = flags

            if is_flag_set(Message.FLAG_NOT_REMOVABLE, parent_message.flags):
                kwargs['existence'] = 1

        if avatar_updated:
            kwargs['thread_avatar_hash'] = parent_message.thread_avatar_hash

        if background_color_updated:
            kwargs['thread_background_color'] = parent_message.thread_background_color

        if text_color_updated:
            kwargs['thread_text_color'] = parent_message.thread_text_color

        requests.append(UpdateMessageRequestTO.create(**kwargs))

    if message_updated:
        # only update parentMessage
        requests.append(UpdateMessageRequestTO.create(parent_message_key=None,
                                                      message_key=parent_message.mkey,
                                                      last_child_message=last_child_message,
                                                      message=parent_message.message))
    if not requests:
        return  # nothing updated?

    new_offset = offset + 100
    recipients = map(users.User, chat_members.members[offset:new_offset])

    recipients_count = len(recipients)
    if not recipients_count:
        return


    context_list = list()
    for recipient in recipients:
        for request in requests:
            context_list += updateMessage(update_message_response_handler, logError, recipient, request=request,
                                          DO_NOT_SAVE_RPCCALL_OBJECTS=True)
    db.put(context_list)

    if new_offset < len(chat_members.members):
        deferred.defer(_send_update_chat, chat_members_key, flags_updated, message_updated, avatar_updated,
                       background_color_updated, text_color_updated, new_offset)


@mapping('com.mobicage.capi.message.update_message_response_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=UpdateMessageResponseTO)
def update_message_response_handler(context, result):
    pass


@returns(bool)
@arguments(service_user=users.User, parent_message_key=unicode, members=[(unicode, MemberTO)], soft=bool)
def delete_members_from_chat(service_user, parent_message_key, members, soft=False):
    def trans():
        message = _get_and_validate_message(service_user, parent_message_key)
        service_identity_user = create_service_identity_user(service_user,
                                                             get_identity_from_service_identity_user(message.sender))
        user_members = member_list_to_usermember_list(service_identity_user, members, message.alert_flags)
        user_members_dict = dict()  # { <user email> : <read only> }
        user_member_emails = [u.member.email() for u in user_members]

        chat_members_list = list(ChatMembers.list_by_thread_and_chat_members(parent_message_key, user_member_emails))
        for chat_members_model in chat_members_list:
            for user_member_email in reversed(user_member_emails):
                try:
                    chat_members_model.members.remove(user_member_email)
                except ValueError:
                    continue
                else:
                    user_members_dict[user_member_email] = chat_members_model.is_read_only()
                    user_member_emails.remove(user_member_email)

        # user_member_emails contains the members which were not found in the model
        if len(user_member_emails) == len(user_members):
            logging.warn('No provided user (%s) found in chat %s', user_member_emails, parent_message_key)
            return False

        if user_member_emails:
            logging.warn('Users %s were not found in chat %s', user_member_emails, parent_message_key)

        to_put = list(chat_members_list)

        # If soft delete, then make sure the users can not reply anymore (writers become readers)
        # Else, prepare deleteConversation for every member in targets
        parent = AbstractChatJob.create_parent_key(parent_message_key)
        job_guid = str(uuid.uuid4())
        for app_user_email, read_only in user_members_dict.iteritems():
            if soft:
                if read_only:
                    pass  # nothing to do, user was already a reader
                else:
                    to_put.append(UpdateChatMemberJob(parent=parent,
                                                      guid=job_guid,
                                                      user=users.User(app_user_email),
                                                      read_only=True))
            else:
                to_put.append(DeleteMemberFromChatJob(parent=parent,
                                                      guid=job_guid,
                                                      user=users.User(app_user_email)))

        put_and_invalidate_cache(*to_put)
        if len(to_put) > 1:
            deferred.defer(_run_delete_from_chat_job, parent_message_key, job_guid, _transactional=True)
            if soft:
                deferred.defer(_run_update_chat_members_job, parent_message_key, job_guid, _transactional=True)
        return True

    xg_on = db.create_transaction_options(xg=True)
    return db.run_in_transaction_options(xg_on, trans)


@returns()
@arguments(parent_message_key=unicode, job_guid=unicode)
def _run_delete_from_chat_job(parent_message_key, job_guid):
    run_job(_get_chat_job_qry, [DeleteMemberFromChatJob, parent_message_key, job_guid],
            _send_delete_from_chat, [parent_message_key])


@returns()
@arguments(job=DeleteMemberFromChatJob, parent_message_key=unicode)
def _send_delete_from_chat(job, parent_message_key):
    _send_deleted(job.user, parent_message_key)


@returns(bool)
@arguments(service_user=users.User, parent_message_key=unicode)
def delete_chat(service_user, parent_message_key):
    def trans():
        message = _get_and_validate_message(service_user, parent_message_key, message_required=False)
        if message:
            run_job(_get_chat_members, [ChatMembers, parent_message_key], _delete_chat_message, [],
                    qry_transactional=True)

        return bool(message)

    return db.run_in_transaction(trans)


@returns()
@arguments(service_user=users.User, parent_message_key=unicode, members=[(unicode, MemberTO)], status=unicode)
def update_chat_members(service_user, parent_message_key, members, status):
    # Changes reader members to writer members, or vice versa.
    # If a member is not in the chat members, that member is NOT added to the chat.

    if status not in ChatMemberStatus.all():
        raise InvalidChatMemberStatusException(status)

    if not members:
        return

    def trans():
        message = _get_and_validate_message(service_user, parent_message_key)
        service_identity_user = add_slash_default(message.sender)
        user_members = {m.member.email(): m for m in member_list_to_usermember_list(service_identity_user,
                                                                                    members,
                                                                                    alert_flags=message.alert_flags,
                                                                                    read_only=False)}

        read_only = ChatMemberStatus.is_read_only(status)
        chat_members_list = ChatMembers.list_by_thread_and_chat_members(parent_message_key, user_members.keys())

        chat_members_cache = dict()
        cls = ChatReaderMembers if read_only else ChatWriterMembers
        job_guid = str(uuid.uuid4())
        to_put = set()
        for chat_members_model in chat_members_list:
            i = len(chat_members_model.members)
            for email in reversed(chat_members_model.members):
                i -= 1
                if read_only == chat_members_model.is_read_only():
                    logging.debug("Chat member %s was already a %s", email, status)
                    continue

                user_member = user_members.get(email)
                if user_member:
                    other_status_chat_members_model = chat_members_cache.get(cls)
                    if not other_status_chat_members_model:
                        other_status_chat_members_model = cls.get_last_by_thread(parent_message_key)
                    if not other_status_chat_members_model \
                            or other_status_chat_members_model.members_size() + len(email) > MAX_CHAT_MEMBERS_SIZE:
                        # need to create a new model because there was no model yet, or the model became too big
                        other_status_chat_members_model = cls(parent=cls.create_parent_key(parent_message_key))

                    chat_members_cache[cls] = other_status_chat_members_model

                    other_status_chat_members_model.members.append(email)
                    chat_members_model.members.pop(i)
                    to_put.add(other_status_chat_members_model)
                    to_put.add(chat_members_model)
                    logging.debug('Updated %s to %s', email, status)

                    to_put.add(UpdateChatMemberJob(parent=UpdateChatMemberJob.create_parent_key(parent_message_key),
                                                   guid=job_guid,
                                                   user=user_member.member,
                                                   read_only=read_only))

        if to_put:
            put_and_invalidate_cache(*to_put)
            deferred.defer(_run_update_chat_members_job, parent_message_key, job_guid, _transactional=True)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


@returns()
@arguments(parent_message_key=unicode, job_guid=unicode)
def _run_update_chat_members_job(parent_message_key, job_guid):
    run_job(_get_chat_job_qry, [UpdateChatMemberJob, parent_message_key, job_guid],
            _send_update_chat_member, [])


@returns()
@arguments(job=UpdateChatMemberJob)
def _send_update_chat_member(job):
    parent_message = get_message(job.parent_message_key, None)
    last_child_message = None if not parent_message.childMessages else parent_message.childMessages[-1].name()

    flags = parent_message.flags
    if job.read_only:
        flags &= ~Message.FLAG_ALLOW_REPLY
        flags &= ~Message.FLAG_ALLOW_REPLY_ALL

    # update every message in the chat
    request = UpdateMessageRequestTO.create(parent_message_key=parent_message.mkey,
                                            message_key=None,
                                            last_child_message=last_child_message,
                                            flags=flags)

    updateMessage(update_message_response_handler, logError, job.user, request=request)


@returns(bool)
@arguments(service_identity_user=users.User, parent_message_key=unicode, members=[users.User])
def service_delete_conversation(service_identity_user, parent_message_key, members):
    # We will send a delete conversation call to each member of this message.
    # We send this call even when the thread does not exists on the server.
    # This is because the first message of a local flow is not stored on the server until you have acknowledged it.

    def run():
        parent_message = get_message(parent_message_key, None)
        if parent_message:
            if remove_slash_default(service_identity_user) != parent_message.sender:
                raise ParentMessageNotFoundException()
            for m in members:
                if m not in parent_message.members:
                    human_user, app_id = get_app_user_tuple(m)
                    raise MemberNotFoundException(human_user.email(), app_id)
            return True
        return False

    r = db.run_in_transaction(run)

    for m in members:
        delete_conversation(m, parent_message_key, True)

    return r

@returns(NoneType)
@arguments(user=users.User, parent_message_key=unicode, force=bool, delete_status=int)
def delete_conversation(user, parent_message_key, force=False, delete_status=MemberStatus.STATUS_DELETED):
    def _update_member_status(msg):
        if not user in msg.members:
            raise ResponseReceivedFromNonMemberException("user '%s' not found in message '%s'" % (user, msg.mkey))
        ms = msg.memberStatusses[msg.members.index(user)]
        ms.status |= delete_status
        msg.removeStatusIndex(user, (Message.MEMBER_INDEX_STATUS_NOT_DELETED, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX))

    def run():
        parent_message = get_message(parent_message_key, None)
        if parent_message:
            if is_flag_set(Message.FLAG_DYNAMIC_CHAT, parent_message.flags):
                _unsubscribed_from_chat(user, parent_message)
            else:
                _update_member_status(parent_message)
                puts = [parent_message]
                for key in parent_message.childMessages:
                    message = Message.get(key)
                    _update_member_status(message)
                    puts.append(message)
                db.put(puts)
        return parent_message

    if is_tmp_key(parent_message_key):
        logging.warning('Doing delete_conversation for tmp key %s' % parent_message_key)
        return
    xg_on = db.create_transaction_options(xg=True)
    parent_message = db.run_in_transaction_options(xg_on, run)
    if delete_status == MemberStatus.STATUS_DELETED and (parent_message or force):
        _send_deleted(user, parent_message_key)


def _unsubscribed_from_chat(app_user, parent_message):
    from rogerthat.service.api.messaging import chat_deleted
    parent_message_key = parent_message.mkey
    logging.debug('Unsubscribing %s from chat %s', app_user.email(), parent_message_key)
    azzert(db.is_in_transaction())
    for result in ChatMembers.all().ancestor(ChatMembers.create_parent_key(parent_message_key)).filter('members =', app_user.email()):
        result.members.remove(app_user.email())
        result.put()

        up = get_user_profile(app_user)
        if up:
            service_user, identity = get_service_identity_tuple(parent_message.sender)
            service_profile = get_service_profile(service_user)
            if service_profile:
                chat_deleted(chat_deleted_response_handler, logServiceError,
                             service_profile,
                             parent_message_key=parent_message_key,
                             member=UserDetailsTO.fromUserProfile(up),
                             tag=parent_message.tag,
                             timestamp=now(),
                             service_identity=identity)
        return
    logging.debug('Did not find %s in the chat members of chat %s', app_user.email(), parent_message_key)


@mapping('message.chat_deleted.response_handler')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=NoneType)
def chat_deleted_response_handler(context, result):
    pass


@returns(NoneType)
@arguments(user=users.User, parent_message=Message, exclude_children=[db.Key], _run_in_transaction=bool)
def recover_conversation(user, parent_message, exclude_children, _run_in_transaction=True):
    logging.debug("Undo thread delete %s for user %s" % (parent_message.mkey, user.email()))
    def _update_member_status(msg):
        if not user in msg.members:
            raise ResponseReceivedFromNonMemberException("user '%s' not found in message '%s'" % (user, msg.mkey))
        ms = msg.memberStatusses[msg.members.index(user)]
        ms.status &= ~MemberStatus.STATUS_DELETED
        msg.addStatusIndex(user, (Message.MEMBER_INDEX_STATUS_NOT_DELETED))

    def run():
        _update_member_status(parent_message)
        puts = [parent_message]
        for key in parent_message.childMessages:
            if key in exclude_children:
                continue
            message = Message.get(key)
            _update_member_status(message)
            puts.append(message)
        db.put(puts)

    if _run_in_transaction:
        db.run_in_transaction(run)
    else:
        run()

@returns(None)
@arguments(user=users.User, mobile=Mobile, message=Message, puts=list, send_status_updates=bool)
def _resend_message(user, mobile, message, puts, send_status_updates=False):
    kwargs = dict(MOBILE_ACCOUNT=mobile, DO_NOT_SAVE_RPCCALL_OBJECTS=True)

    def _send_message(message, puts):
        is_chat = is_flag_set(message.FLAG_DYNAMIC_CHAT, message.flags)
        request = NewMessageRequestTO()
        request.message = MessageTO.fromMessage(message)
        if not is_chat:
            ms = message.memberStatusses[message.members.index(user)]
            if (ms.status & MemberStatus.STATUS_READ) == MemberStatus.STATUS_READ:
                # silence the message when already read
                request.message.alert_flags = Message.ALERT_FLAG_SILENT
        ctxs = newMessage(new_message_response_handler, logError, user, request=request, **kwargs)
        for ctx in ctxs:
            ctx.is_chat = is_chat
            ctx.message = message.key()
        puts.extend(ctxs)

        if not is_chat and send_status_updates and is_flag_set(MemberStatus.STATUS_ACKED, ms.status):
            # making sure that client dirty and needs_my_answer flags are correct for old clients
            status_request = MemberStatusUpdateRequestTO.fromMessageAndMember(message, user)
            ctxs = updateMessageMemberStatus(message_member_response_handler, logError, user, request=status_request, **kwargs)
            puts.extend(ctxs)

    def _send_form_message(fm, puts):
        w_descr = WIDGET_MAPPING[fm.form.type]
        request = w_descr.new_req_to_type()
        request.form_message = w_descr.fm_to_type.fromFormMessage(fm)
        ms = fm.memberStatusses[fm.members.index(user)]
        if (ms.status & MemberStatus.STATUS_READ) == MemberStatus.STATUS_READ:
            # silence the message when already read
            request.form_message.alert_flags = Message.ALERT_FLAG_SILENT
        ctxs = w_descr.new_form_call(new_message_response_handler, logError, user, request=request, **kwargs)
        for ctx in ctxs:
            ctx.message = fm.key()
        puts.extend(ctxs)

        if send_status_updates and (ms.status & MemberStatus.STATUS_ACKED) == MemberStatus.STATUS_ACKED:
            # making sure that client dirty and needs_my_answer flags are correct for old clients
            status_request = w_descr.form_updated_req_to_type.fromMessageAndMember(message, user)
            ctxs = w_descr.form_updated_call(form_updated_response_handler, logError, user, request=status_request, **kwargs)
            puts.extend(ctxs)

    if message.TYPE == Message.TYPE_FORM_MESSAGE:
        _send_form_message(message, puts)
    else:
        _send_message(message, puts)

@returns(BooleanType)
@arguments(user=users.User, parent_message_key=unicode, offset=unicode)
def get_conversation(user, parent_message_key, offset=None):
    def run():
        parent_message = get_message(parent_message_key, None)

        read_only = False
        is_chat = is_flag_set(Message.FLAG_DYNAMIC_CHAT, parent_message.flags)
        if is_chat:
            chat_members_containing_user = list(ChatMembers.list_by_thread_and_chat_member(parent_message_key, user.email()))
            if not chat_members_containing_user:
                logging.warn("%s requested a chat message, but is not in the members list. Doing nothing.",
                             user.email())
                # Need to raise an exception here such that the client can re-request this conversation
                raise ApiWarning('Denied')
            read_only = all(c.is_read_only() for c in chat_members_containing_user)
        else:
            if not user in parent_message.members:
                logging.warn("%s requested a message thread, but is not in the members list. Doing nothing.",
                             user.email())
                return False
            ms = parent_message.memberStatusses[parent_message.members.index(user)]
            if is_flag_set(MemberStatus.STATUS_ACCOUNT_DELETED, ms.status):
                logging.warn("%s requested a message thread, but an account with the same email address was previously deleted. Doing nothing.")
                return False
            if not parent_message.hasStatusIndex(user, Message.MEMBER_INDEX_STATUS_NOT_DELETED):
                logging.warn("%s requested a message thread, but this thread was deleted. Doing nothing.",
                             user.email())
                return False

        deferred.defer(_send_conversation, user, parent_message_key, read_only, offset, _transactional=True)
        return True

    return db.run_in_transaction(run)


@returns()
@arguments(user=users.User, parent_message_key=unicode, read_only=bool, offset=unicode)
def _send_conversation(user, parent_message_key, read_only, offset=None):
    def trans():
        parent_message = get_message(parent_message_key, None)
        is_chat = is_flag_set(Message.FLAG_DYNAMIC_CHAT, parent_message.flags)

        offset_index = -1
        if offset:
            if offset == parent_message_key:
                offset_index = 0
            else:
                offset_index = parent_message.childMessages.index(get_message_key(offset, parent_message_key))

        now_ = now()

        if is_chat:
            context = None
            if offset_index == -1:
                _distribute_chat_message_to_recipients([user], parent_message, None, context, read_only)

            for message in db.get(parent_message.childMessages[max(0, offset_index):]):
                if message.timeout and message.timeout < now_:
                    continue  # message timed out
                _distribute_chat_message_to_recipients([user], message, parent_message, context, read_only)
        else:
            puts = list()
            mobile = users.get_current_mobile()
            if offset_index == -1:
                _resend_message(user, mobile, parent_message, puts, send_status_updates=False)
            for message in db.get(parent_message.childMessages[max(0, offset_index):]):
                if message.timeout and message.timeout < now_:
                    continue  # message timed out
                _resend_message(user, mobile, message, puts, send_status_updates=False)

            db.put(puts)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


@returns(tuple)
@arguments(user=users.User, messages=[Message])
def _arrange_messages(user, messages):
    child_messages = dict()
    parent_messages = list()
    for message in messages:
        if message.isRootMessage:
            parent_messages.append(message)
        else:
            if not message.pkey in child_messages:
                child_messages[message.pkey] = list()
            child_messages[message.pkey].append(message)

    for k, v in child_messages.items():
        child_messages[k] = sorted(v, key=lambda m: m.creationTimestamp)

    parent_messages = sorted(parent_messages, key=lambda m: m.timestamp)
    return parent_messages, child_messages

@returns(BooleanType)
@arguments(user=users.User, parent_message=Message, child_messages=[Message])
def _is_flow_completed(user, parent_message, child_messages):
    last_thread_message = child_messages[-1] if child_messages else parent_message
    ms = last_thread_message.memberStatusses[last_thread_message.members.index(user)]
    if (ms.status & MemberStatus.STATUS_ACKED) == 0:
        return False

    if ms.button_index == -1:
        ui_flags = last_thread_message.dismiss_button_ui_flags
    else:
        ui_flags = last_thread_message.buttons[ms.button_index].ui_flags

    return (ui_flags & Message.UI_FLAG_EXPECT_NEXT_WAIT_5) == 0

@returns(NoneType)
@arguments(mobile_key=db.Key)
def send_messages_after_registration(mobile_key):
    mobile = db.get(mobile_key)
    user = mobile.user
    app = get_app_by_user(user)
    if app.type == App.APP_TYPE_YSAAA:
        return

    # Mobile version is >1.0.111.I or >1.0.976.A
    parent_messages, child_messages = _arrange_messages(user, get_messages(user, None, 10)[0])

    for parent_message in reversed(parent_messages):
        # Skip completed message flows
        if parent_message.sender != MC_DASHBOARD and parent_message.sender_type == FriendDetail.TYPE_SERVICE \
                and _is_flow_completed(user, parent_message, child_messages.get(parent_message.key)):
            parent_messages.remove(parent_message)
        else:
            ms = parent_message.memberStatusses[parent_message.members.index(user)]
            if ms.status & (MemberStatus.STATUS_DELETED | MemberStatus.STATUS_ACCOUNT_DELETED) != 0:
                # message was deleted, or account was deleted
                parent_messages.remove(parent_message)

    now_ = now()
    # Append chats
    chat_parent_message_keys = set((chat_members_key.parent()
                                    for chat_members_key in ChatMembers.list_by_chat_member(user.email(), keys_only=True)))
    if chat_parent_message_keys:
        chat_parent_messages = db.get(chat_parent_message_keys)
        child_messages.update({ p.mkey : [m for m in db.get(p.childMessages) if not m.timeout or m.timeout > now_]
                                for p in chat_parent_messages })
        parent_messages.extend(chat_parent_messages)

    def run():
        puts = list()
        for parent_message in parent_messages:
            _resend_message(user, mobile, parent_message, puts, send_status_updates=False)
            for child_message in child_messages.get(parent_message.mkey, list()):
                if not child_message.timeout or child_message.timeout > now_:
                    _resend_message(user, mobile, child_message, puts, send_status_updates=False)

        db.put(puts)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, run)

@returns(NoneType)
@arguments(message_flow_name=unicode, emails=[unicode], email_admins=bool,
           steps=[object_factory("step_type", FLOW_STEP_MAPPING)], app_user=users.User,
           service_identity=unicode, service_user=users.User, parent_message_key=unicode, tag=unicode)
def send_message_flow_results_email(message_flow_name, emails, email_admins, steps, app_user, service_identity,
                                    service_user, parent_message_key, tag):
    service_identity_user = create_service_identity_user(service_user, service_identity)
    si = get_service_identity(service_identity_user)
    emails_to_send = set()
    if email_admins:
        logging.info("Sending results to admins, getting admin emails")
        admin_emails = si.metaData
        logging.info("Admin emails: %s" % admin_emails)
        if admin_emails:
            emails_to_send = {email.strip() for email in admin_emails.split(',') if email.strip()}
            logging.info("Parsed admin email addresses: %s" % emails_to_send)
    if emails:
        emails_to_send.update(emails)

    # make sure there are no empty emails
    emails_to_send = [email.strip() for email in emails_to_send if email.strip()]
    logging.info("Resolved emails: %s", emails_to_send)

    human_user, app_id = get_app_user_tuple(app_user)
    member = human_user.email()
    if emails_to_send:
        attachments = list()
        app_name = get_app_name_by_id(app_id)
        user_profile = get_user_profile(app_user)

        for i, step in enumerate(steps):
            if getattr(step, 'display_value', None):
                if step.display_value is MISSING:
                    step.display_value = u"-"
                elif "\n" in step.display_value:
                    # indent the display_value
                    step.display_value = "\n\t".join([""] + step.display_value.splitlines() + [""])
            if step.step_type == FormFlowStepTO.TYPE \
                    and step.answer_id == Form.POSITIVE \
                    and step.form_result.type == MyDigiPassWidgetResult.TYPE \
                    and step.form_result.result.eid_photo:
                attachments.append(('eid_photo_%s.jpg' % (i + 1),
                                    base64.b64decode(step.form_result.result.eid_photo)))

        context = {'steps':steps, 'member':member, 'timestamp':now(), 'message_flow_name':message_flow_name,
                   'name':user_profile.name, 'app_name':app_name, 'tag':tag}
        body = templates.render('flow_member_result', [user_profile.language], context)
        body_html = templates.render('flow_member_result_html', [user_profile.language], context)

        subject = localize(user_profile.language, "Flow result of %(user)s for %(flow)s",
                           user=member, flow=message_flow_name)
        hash_ = hashlib.sha256((u"%s-%s" % (member, parent_message_key)).encode('utf8')).hexdigest()
        from_ = "Rogerthat <%s.followup@%s.appspotmail.com>" % (hash_, app_identity.get_application_id())

        def trans():
            FlowResultMailFollowUp(key_name=hash_, member=app_user, parent_message_key=parent_message_key, \
                                   service_user=service_user, service_identity=service_identity, subject=subject, \
                                   addresses=emails_to_send).put()
            utils.send_mail(from_, emails_to_send, subject, body, html=body_html, attachments=attachments)
        db.run_in_transaction(trans)

@arguments(follow_up_id=unicode, from_=unicode, subject=unicode, body=unicode)
def process_mfr_email_reply(follow_up_id, from_, subject, body):
    mfr_fu = FlowResultMailFollowUp.get_by_key_name(follow_up_id)
    if not mfr_fu:
        logging.warn("FlowResultMailFollowUp not found with hash %s" % follow_up_id)
        return
    if follow_up_id in body:
        rogerthat = "Rogerthat <%s.followup@%s.appspotmail.com>" % (follow_up_id, app_identity.get_application_id())
        server_settings = get_server_settings()
        utils.send_mail(rogerthat, from_, u"ERROR: %s" % subject, """Dear,
Your message has not been forwarded to your Rogerthat contact because you forgot to clear the email.
Clearing the email is important because the entire email message will be forwarded to your contact via Rogerthat.

To reply to your contact, use the "reply" button in your mail client, then empty the message before you start entering your reply message.

If this is not clear contact %s for more information.

Regards,

The Rogerthat Team""" % server_settings.supportEmail)
        return
    service_identity_user = create_service_identity_user(mfr_fu.service_user, mfr_fu.service_identity)
    user_profile = get_user_profile(mfr_fu.member)
    reply = ButtonTO()
    reply.id = u'reply'
    reply.caption = localize(user_profile.language, u'Reply')
    reply.action = None
    reply.ui_flags = Message.UI_FLAG_EXPECT_NEXT_WAIT_5
    def trans():
        message = sendMessage(service_identity_user, [UserMemberTO(mfr_fu.member)], Message.FLAG_ALLOW_DISMISS, 0, mfr_fu.parent_message_key, \
                    body, [reply], None, None, REPLY_ON_FOLLOW_UP_MESSAGE)
        message.follow_up_id = follow_up_id
        message.put()
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)

@returns(NoneType)
@arguments(message=Message)
def process_mfr_email_reply_rogerthat_reply(message):
    azzert(hasattr(message, 'follow_up_id'), "Expected follow_up_id attribute on message object")
    mfr_fu = FlowResultMailFollowUp.get_by_key_name(message.follow_up_id)
    if not mfr_fu:
        logging.warn("FlowResultMailFollowUp not found with hash %s" % message.follow_up_id)
        return

    ms = message.memberStatusses[message.members.index(mfr_fu.member)]
    btn_index = ms.button_index
    if btn_index == -1:
        return
    if isinstance(message, FormMessage):
        if btn_index == message.buttons[Form.POSITIVE].index:
            from_ = "Rogerthat <%s.followup@%s.appspotmail.com>" % (message.follow_up_id, app_identity.get_application_id())
            utils.send_mail(from_, mfr_fu.addresses, "RE: %s" % mfr_fu.subject, ms.form_result.result.value)
        return
    service_identity_user = create_service_identity_user(mfr_fu.service_user, mfr_fu.service_identity)
    user_profile = get_user_profile(mfr_fu.member)
    form_message = localize(user_profile.language, "Enter your reply:")
    form = FormTO()
    form.type = TextBlockTO.TYPE_TEXT_BLOCK
    form.negative_button = localize(user_profile.language, "Cancel")
    form.negative_button_ui_flags = 0
    form.negative_confirmation = None
    form.positive_button = localize(user_profile.language, "Send reply")
    form.positive_button_ui_flags = 0
    form.positive_confirmation = None
    form.javascript_validation = None
    widget = TextBlockTO()
    widget.max_chars = 500
    widget.place_holder = None
    widget.value = None
    form.widget = widget
    def trans():
        msg = sendForm(service_identity_user, mfr_fu.parent_message_key, mfr_fu.member, form_message, form, 0, None, REPLY_ON_FOLLOW_UP_MESSAGE, 1)
        msg.follow_up_id = message.follow_up_id
        msg.put()
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)

@returns(NoneType)
@arguments(app_user=users.User, service_identity_user=users.User, parent_message_key=unicode, tag=unicode)
def check_test_flow_broadcast_ended(app_user, service_identity_user, parent_message_key, tag):
    if tag and tag.startswith("{") and tag.endswith("}"):
        try:
            tag_dict = json.loads(tag)
        except:
            pass
        else:
            if Broadcast.TAG_MC_BROADCAST in tag_dict:
                from rogerthat.bizz.service.broadcast import flow_test_person_ended
                flow_test_person_ended(app_user, parent_message_key, service_identity_user, tag_dict[Broadcast.TAG_MC_BROADCAST])

@returns(NoneType)
@arguments(svc_user=users.User, service_identity=unicode, message_flow_run_id=unicode, parent_message_key=unicode,
           app_user=users.User, steps=[object_factory("step_type", FLOW_STEP_MAPPING)], flush_id=unicode,
           end_id=unicode, tag=unicode)
def send_message_flow_member_result(svc_user, service_identity, message_flow_run_id, parent_message_key, app_user,
                                    steps, end_id, flush_id, tag):
    from rogerthat.service.api.messaging import flow_member_result

    for step in steps:
        if step.step_id[0:7] == "base64:":
            id_struct = json.loads(base64.b64decode(step.step_id[7:]))
            step.step_id = id_struct["id"]
            step.message_flow_id = id_struct["mfd"]
        else:
            step.message_flow_id = None

        if step.step_type == FormFlowStepTO.TYPE:
            auto_complete_func = step.form_result not in (None, MISSING) and step.form_result.result \
                    and getattr(step.form_result.result, 'auto_complete', None)
            if auto_complete_func:
                auto_complete_func()

    end_message_flow_id = None
    if end_id and end_id[0:7] == "base64:":
        id_struct = json.loads(base64.b64decode(end_id[7:]))
        end_id = id_struct["id"]
        end_message_flow_id = id_struct["mfd"]
    flush_message_flow_id = None
    if flush_id and flush_id[0:7] == "base64:":
        id_struct = json.loads(base64.b64decode(flush_id[7:]))
        flush_id = id_struct["id"]
        flush_message_flow_id = id_struct["mfd"]
    result_key = unicode(uuid.uuid4())

    if tag == ServiceMenuDef.TAG_MC_BROADCAST_SETTINGS:
        from rogerthat.bizz.service.broadcast import process_broadcast_settings_flow_result
        service_identity_user = create_service_identity_user(svc_user, service_identity)
        try_or_defer(process_broadcast_settings_flow_result, service_identity_user, app_user, steps)

    member = get_human_user_from_app_user(app_user).email()
    fmr_call = flow_member_result(message_service_flow_member_result_response_handler, logServiceError,
                                  get_service_profile(svc_user), message_flow_run_id=message_flow_run_id, member=member,
                                  steps=steps, end_id=end_id, end_message_flow_id=end_message_flow_id,
                                  parent_message_key=parent_message_key, tag=tag, result_key=result_key,
                                  flush_id=flush_id, flush_message_flow_id=flush_message_flow_id,
                                  DO_NOT_SAVE_RPCCALL_OBJECTS=True, service_identity=service_identity,
                                  user_details=[UserDetailsTO.fromUserProfile(get_user_profile(app_user))])
    if fmr_call:  # None if messaging.flow_member_result is not implemented
        fmr_call.parent_message_key = parent_message_key
        fmr_call.result_key = result_key
        fmr_call.member = app_user
        fmr_call.put()

@mapping('com.mobicage.capi.message.new_message_response_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=NewMessageResponseTO)
def new_message_response_handler(context, result):
    if getattr(context, 'is_chat', False):
        return  # not interested in status updates of chats

    if result:  # result can be None if client does not support forms
        app_user = users.get_current_user()
        timestamp = result.received_timestamp
        message_key = context.message
        message_received(app_user, message_key, timestamp)


@returns(NoneType)
@arguments(user=users.User, message_key=db.Key, timestamp=int)
def message_received(user, message_key, timestamp):
    def run():
        message = Message.get(message_key)

        if not (user == message.sender or user in message.members):
            raise ResponseReceivedFromNonMemberException('User [%s] is not a message member for message [%s]. Sender is [%s]. Members are [%s]' % (user, message_key, message.sender, message.members))

        # Check if thread was deleted and recover if needed
        parent_key = message.parent_key()
        if parent_key:
            parent_message = Message.get(parent_key)
            ms = parent_message.memberStatusses[parent_message.members.index(user)]
            if ms and ms.status & MemberStatus.STATUS_DELETED == MemberStatus.STATUS_DELETED:
                try:
                    puts = recover_conversation(user, parent_message, [message_key], _run_in_transaction=False)
                    if puts:
                        db.put(puts)
                except:
                    logging.exception("Failed to undo deletion of thread %s for user %s" % (parent_message.mkey, user.email()))
        else:
            parent_message = None

        ms = message.memberStatusses[message.members.index(user)]
        if not ms or ms.status & MemberStatus.STATUS_RECEIVED == MemberStatus.STATUS_RECEIVED:
            return
        ms.status |= MemberStatus.STATUS_RECEIVED
        ms.received_timestamp = timestamp
        message.removeStatusIndex(user, Message.MEMBER_INDEX_STATUS_NOT_RECEIVED)
        message.put()

        if message.step_id:
            bump_flow_statistics_for_message_update(user, [FlowStatistics.STATUS_RECEIVED], message, parent_message)

        return message, ms

    result = db.run_in_transaction(run)
    if result:
        message, ms = result
        _send_updates(user, message, ms, False, ServiceProfile.CALLBACK_MESSAGING_RECEIVED)
        if message.broadcast_guid and not message.parent_key():
            slog(msg_="Broadcast stats received", function_=log_analysis.BROADCAST_STATS, service=message.sender.email(), type_=log_analysis.BROADCAST_STATS_RECEIVED, broadcast_guid=message.broadcast_guid)


def _validate_members(sender, sender_is_service_identity, members):
    # Check whether the members are friends of the sender
    if sender_is_service_identity:
        for m in members:
            if not get_friend_serviceidentity_connection(friend_user=m, service_identity_user=sender):
                human_user, app_id = get_app_user_tuple(m)
                raise CanOnlySendToFriendsException(human_user.email(), app_id)
    else:
        # sender is a human user
        friendMap = get_friends_map_cached(sender)
        friends = list(friendMap.friends)
        friends.append(sender)
        friend_set = set(friends)
        if not set(members).issubset(friend_set):
            for m in members:
                if not m in friend_set:
                    human_user, app_id = get_app_user_tuple(m)
                    raise CanOnlySendToFriendsException(human_user.email(), app_id)
    # Check if there are no duplicates
    if len(members) != len(set(members)):
        raise DuplicateMembersException()
    # Check if the members are not services
    a = are_service_identity_users(members)
    if any(a):
        i = a.index(True)
        human_user, app_id = get_app_user_tuple(members[i])
        raise CanNotSendToServicesException(human_user.email(), app_id)

def _validateFlags(flags, members):
    if flags > sum(Message.FLAGS):
        raise InvalidFlagsException()
    if flags & Message.FLAG_AUTO_LOCK == Message.FLAG_AUTO_LOCK and len(members) > 1:
        raise AutoLockCanOnlyHaveOneMemberInMessageException()

def _validate_dismiss_ui_flags(dismiss_button_ui_flags, message_flags):
    if dismiss_button_ui_flags > sum(Message.UI_FLAGS):
        raise UnknownDismissButtonUiFlagException()
    if dismiss_button_ui_flags and message_flags & Message.FLAG_ALLOW_DISMISS == 0:
        raise DismissUiFlagWithoutAllowDismissException()

def _validate_button_ui_flags(ui_flags, button_id):
    if ui_flags > sum(Message.UI_FLAGS):
        raise UnknownUiFlagException(button=button_id)

def _validate_alert_flags(members):
    for alert_flags in (m.alert_flags for m in members):
        if alert_flags > sum(Message.ALERT_FLAGS):
            raise UnknownMessageAlertFlagException()
        def count_flags(flag_set):
            flag_count = 0
            for flag in flag_set:
                if flag & alert_flags == flag:
                    flag_count += 1
            return flag_count
        if count_flags(Message.RING_ALERT_FLAGS) > 1:
            raise RingAlertFlagsAreNotCombinableException()
        if count_flags(Message.INTERVAL_ALERT_FLAGS) > 1:
            raise IntervalAlertFlagsAreNotCombinableException()

def _validateSenderReply(sender_reply, buttons, members, sender):
    sender_in_members = sender in members
    if sender_reply:
        if not sender_in_members or not buttons:
            raise InvalidSenderReplyValue()
        if sender_reply not in map(lambda b:b.id, buttons):
            raise InvalidSenderReplyValue()

def _validate_text_widget(widget):
    if widget.max_chars == MISSING or widget.max_chars <= 0:
        raise InvalidWidgetValueException(property_='max_chars')
    if widget.place_holder == MISSING:
        widget.place_holder = None
    if widget.value == MISSING:
        widget.value = None
    if widget.value and len(widget.value) > widget.max_chars:
        raise ValueTooLongException()

def _validate_choice_labels(labels):
    for l in labels:
        if labels.count(l) > 1:
            raise DuplicateChoiceLabelException(label=l)

def _validate_choice_values(values, max_chars=0):
    for v in values:
        if values.count(v) > 1:
            raise DuplicateChoiceValueException(value=v)
        if max_chars and len(v) > max_chars:
            raise SuggestionTooLongException(index=values.index(v))

def _validate_choices(choices):
    if choices == MISSING or not choices:
        raise NoChoicesSpecifiedException()
    _validate_choice_labels([c.label for c in choices])
    _validate_choice_values([c.value for c in choices])

def _validate_select(values, choices):
    choice_values = [c.value for c in choices]
    for value in values:
        if value and not value in choice_values:
            raise ValueNotInChoicesException(value=value)
        if values.count(value) > 1:
            raise DuplicateValueException(value=value)

def _validate_slider_bounds(min_, max_, value):
    if min_ > max_:
        raise InvalidBoundariesException()
    if value < min_ or value > max_:
        raise ValueNotWithinBoundariesException()

def _validate_slider_step(min_, max_, step):
    if step > max_ - min_:
        raise InvalidStepValue()

def _validate_slider_properties(widgetTO):
    if widgetTO.unit == MISSING:
        widgetTO.unit = None

    if widgetTO.precision == MISSING:
        widgetTO.precision = 0
    elif widgetTO.precision < 0:
        raise InvalidWidgetValueException(property_='precision')

    if widgetTO.step == MISSING:
        widgetTO.step = 1
    elif widgetTO.step <= 0:
        raise InvalidWidgetValueException(property_='step')

def validate_text_line(widgetTO):
    _validate_text_widget(widgetTO)

def validate_text_block(widgetTO):
    _validate_text_widget(widgetTO)

def validate_auto_complete(widgetTO):
    _validate_text_widget(widgetTO)
    _validate_choice_values(widgetTO.suggestions, max_chars=widgetTO.max_chars)
    if widgetTO.choices != MISSING:
        _validate_choice_values(widgetTO.choices, max_chars=widgetTO.max_chars)

def validate_single_select(widgetTO):
    if len(widgetTO.choices) < 2:
        raise MultipleChoicesNeededException()
    _validate_choices(widgetTO.choices)

    if widgetTO.value == MISSING:
        widgetTO.value = None
    else:
        _validate_select([widgetTO.value], widgetTO.choices)

def validate_multi_select(widgetTO):
    _validate_choices(widgetTO.choices)

    if widgetTO.values == MISSING:
        widgetTO.values = list()
    else:
        _validate_select(widgetTO.values, widgetTO.choices)

def validate_date_select(widgetTO):
    if widgetTO.min_date not in [MISSING, None] and widgetTO.max_date not in [MISSING, None] and widgetTO.max_date < widgetTO.min_date:
        raise InvalidBoundariesException()

    if widgetTO.date not in [MISSING, None]:
        if widgetTO.min_date not in [MISSING, None] and widgetTO.date < widgetTO.min_date:
            raise ValueNotWithinBoundariesException()
        if widgetTO.max_date not in [MISSING, None] and widgetTO.date > widgetTO.max_date:
            raise ValueNotWithinBoundariesException()

    if not (widgetTO.unit in [MISSING, None] or "<value/>" in widgetTO.unit):
        raise InvalidUnitException(missing_tag="<value/>")

    if widgetTO.mode not in DateSelect.MODES:
        raise InvalidDateSelectModeException()

    if widgetTO.mode == DateSelect.MODE_DATE:
        for value in [widgetTO.min_date, widgetTO.max_date, widgetTO.date]:
            if value not in [MISSING, None] and value % 86400 != 0:
                raise InvalidValueInDateSelectWithModeDate()
    elif widgetTO.mode == DateSelect.MODE_TIME:
        for value in [widgetTO.min_date, widgetTO.max_date, widgetTO.date]:
            if value not in [MISSING, None] and (value < 0 or value > 86400):
                raise InvalidValueInDateSelectWithModeTime()

    if widgetTO.minute_interval not in [MISSING, None]:
        if widgetTO.minute_interval <= 0 or widgetTO.minute_interval > 30:
            raise InvalidDateSelectMinuteIntervalException()
        if 60.0 % widgetTO.minute_interval != 0:
            raise MinuteIntervalNotEvenlyDividedInto60Exception()

    minute_interval = widgetTO.minute_interval if widgetTO.minute_interval not in [MISSING, None] else DateSelect.DEFAULT_MINUTE_INTERVAL
    if minute_interval != 1:
        for value in [widgetTO.min_date, widgetTO.max_date, widgetTO.date]:
            if value not in [MISSING, None] and (value % minute_interval != 0):
                raise DateSelectValuesShouldBeMultiplesOfMinuteInterval(minute_interval=minute_interval)

def validate_single_slider(widgetTO):
    _validate_slider_properties(widgetTO)

    if not (widgetTO.unit is None or "<value/>" in widgetTO.unit):
        raise InvalidUnitException(missing_tag="<value/>")

    if widgetTO.value == MISSING:
        widgetTO.value = widgetTO.min
    else:
        _validate_slider_bounds(widgetTO.min, widgetTO.max, widgetTO.value)

    _validate_slider_step(widgetTO.min, widgetTO.max, widgetTO.step)

def validate_range_slider(widgetTO):
    _validate_slider_properties(widgetTO)

    if not (widgetTO.unit is None or "<low_value/>" in widgetTO.unit):
        raise InvalidUnitException(missing_tag="<low_value/>")
    if not (widgetTO.unit is None or "<high_value/>" in widgetTO.unit):
        raise InvalidUnitException(missing_tag="<high_value/>")

    if widgetTO.low_value == MISSING:
        widgetTO.low_value = widgetTO.min
    else:
        _validate_slider_bounds(widgetTO.min, widgetTO.max, widgetTO.low_value)

    if widgetTO.high_value == MISSING:
        widgetTO.high_value = widgetTO.max
    else:
        _validate_slider_bounds(widgetTO.min, widgetTO.max, widgetTO.high_value)

    if widgetTO.low_value > widgetTO.high_value:
        raise InvalidRangeException()

    _validate_slider_step(widgetTO.min, widgetTO.max, widgetTO.step)

def validate_photo_upload(widgetTO):
    if widgetTO.quality is MISSING:
        widgetTO.quality = None

    if widgetTO.gallery is MISSING:
        widgetTO.gallery = False

    if widgetTO.camera is MISSING:
        widgetTO.camera = False

    if not widgetTO.camera and not widgetTO.gallery:
        raise InvalidPhotoUploadSourceException()

    if not (widgetTO.quality == PhotoUpload.QUALITY_BEST or widgetTO.quality == PhotoUpload.QUALITY_USER):
        if not(is_numeric_string(widgetTO.quality)):  # Quality can be a number (Max size)
            raise InvalidPhotoUploadQualityException()

    if widgetTO.ratio is MISSING:
        widgetTO.ratio = None
    elif widgetTO.ratio is not None:
        photo_ratio = widgetTO.ratio.split('x')
        if(len(photo_ratio) != 2 or not (is_numeric_string(photo_ratio[0]) and is_numeric_string(photo_ratio[1]))):
            raise InvalidPhotoUploadRatioException()
        if photo_ratio[0] == 0 or photo_ratio[1] == 0:
            if not (photo_ratio[0] == 0 and photo_ratio[1] == 0):
                raise InvalidPhotoUploadRatioException()

def validate_gps_location(widgetTO):
    if widgetTO.gps is MISSING:
        widgetTO.gps = False

def validate_my_digi_pass(widgetTO):
    if not widgetTO.scope:
        raise InvalidMyDigiPassScopeException(scope=widgetTO.scope)
    invalid_scopes = [scope for scope in widgetTO.scope.split(' ') if scope not in MdpScope.all()]
    if invalid_scopes:
        raise InvalidMyDigiPassScopeException(scope=" ".join(invalid_scopes))


def validate_my_digi_pass_support(service_user):
    # checking if all the apps of this service support MDP
    app_ids = set()
    unsupported = list()
    for si in get_service_identities(service_user):
        app_ids.update(si.appIds)

    try:
        app_ids.remove(App.APP_ID_OSA_LOYALTY)
    except KeyError:
        pass  # osa-loyalty not in app_ids

    app_ids = list(app_ids)
    for app_id, app in zip(app_ids, db.get([App.create_key(app_id) for app_id in app_ids])):
        azzert(app)
        if not app.supports_mdp:
            unsupported.append(app_id)
    if unsupported:
        from rogerthat.bizz.service import MyDigiPassNotSupportedException
        unsupported = sorted(unsupported)
        logging.info('MYDIGIPASS is not supported by %s', unsupported)
        raise MyDigiPassNotSupportedException(unsupported)

def validate_advanced_order(widgetTO):
    from rogerthat.bizz.service import InvalidValueException, DuplicateCategoryIdException, DuplicateItemIdException

    if widgetTO.currency == MISSING:
        widgetTO.currency = None
    if widgetTO.categories == MISSING:
        widgetTO.categories = list()

    if not widgetTO.currency:
        raise InvalidValueException("currency", "Currency is a required argument")
    if not widgetTO.categories:
        raise InvalidValueException("categories", "You need to add at least 1 category.")

    category_ids = list()
    for c in widgetTO.categories:
        if c.id == MISSING:
            c.id = None
        if c.name == MISSING:
            c.name = None

        if not c.id:
            raise InvalidValueException("id", "Id is a required argument in category")
        if c.id in category_ids:
            raise DuplicateCategoryIdException(c.id)
        category_ids.append(c.id)
        if not c.name:
            raise InvalidValueException("name", "Name is a required argument for category with id '%s'" % c.id)
        if not c.items:
            raise InvalidValueException("items", "You need to add at least 1 item for category with id '%s'" % c.id)

        item_ids = list()
        for i in c.items:
            if i.id == MISSING:
                i.id = None
            if i.name == MISSING:
                i.name = None
            if not i.id:
                raise InvalidValueException("id", "Id is a required argument in item for category with id '%s'" % c.id)
            if i.id in item_ids:
                raise DuplicateItemIdException(c.id, i.id)
            item_ids.append(i.id)
            if not i.name:
                raise InvalidValueException("name", "Name is a required argument in item with id '%s' for category with id '%s'" % (i.id, c.id))
            if not i.value and i.value != 0:
                raise InvalidValueException("value", "Value is a required argument in item with id '%s' for category with id '%s'" % (i.id, c.id))
            if i.value < 0:
                raise InvalidValueException("value", "Value should be greater then 0 in item with id '%s' for category with id '%s'" % (i.id, c.id))
            if not i.unit:
                raise InvalidValueException("unit", "Unit is a required argument in item with id '%s' for category with id '%s'" % (i.id, c.id))
            if not i.unit_price and i.has_price:
                raise InvalidValueException("unit_price", "Unit price is a required argument in item with id '%s' for category with id '%s'" % (i.id, c.id))
            if not i.step:
                raise InvalidValueException("step", "Step is a required argument in item with id '%s' for category with id '%s'" % (i.id, c.id))
            if i.step_unit_conversion and not i.step_unit:
                raise InvalidValueException("step_unit", "Step unit is a required argument when step unit conversion is given in item with id '%s' for category with id '%s'" % (i.id, c.id))
            elif i.step_unit and not i.step_unit_conversion:
                raise InvalidValueException("step_unit_conversion", "Step unit conversion is a required argument when step unit is given in item with id '%s' for category with id '%s'" % (i.id, c.id))


def _ack_message(message_key, message_parent_key, responder, timestamp, button_id, custom_reply, is_form=False):
    message = get_message(message_key, message_parent_key)
    if message.flags & Message.FLAG_LOCKED == Message.FLAG_LOCKED:
        raise MessageLockedException()

    is_chat = is_flag_set(Message.FLAG_DYNAMIC_CHAT, message.flags)
    if is_chat and responder not in message.members:
        ms = MemberStatus()
        if not message.memberStatusses:
            message.memberStatusses = MemberStatuses()
            ms.index = 0
        else:
            ms.index = len(message.memberStatusses.values())
        ms.custom_reply = None
        ms.dismissed = False
        ms.status = 0
        ms.received_timestamp = 0
        ms.acked_timestamp = 0
        ms.button_index = -1
        ms.form_result = None
        ms.ack_device = None
        message.memberStatusses.add(ms)
        message.members.append(responder)

    locked = False
    if is_chat:
        if len(message.members) >= CHAT_MAX_BUTTON_REPLIES:
            message.flags |= Message.FLAG_LOCKED
            locked = True

    ms = message.memberStatusses[message.members.index(responder)]
    added_flow_statuses = list()
    for ms_status, flow_status in ((MemberStatus.STATUS_ACKED, FlowStatistics.STATUS_ACKED),
                                   (MemberStatus.STATUS_RECEIVED, FlowStatistics.STATUS_RECEIVED),
                                   (MemberStatus.STATUS_READ, FlowStatistics.STATUS_READ)):
        if not is_flag_set(ms_status, ms.status):
            ms.status |= ms_status
            added_flow_statuses.append(flow_status)
    message.removeStatusIndex(responder, (Message.MEMBER_INDEX_STATUS_NOT_RECEIVED,
                                          Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX))
    if ms.received_timestamp == 0:
        ms.received_timestamp = timestamp
    ms.acked_timestamp = timestamp
    ms.ack_device = u"mobile" if get_current_mobile() else u"web"
    if not button_id and not custom_reply:
        if ms.dismissed:
            return False  # nothing happened
        # [Roger that!] btn pressed
        ms.dismissed = True
        ms.button_index = -1
    else:
        if button_id:
            button_index = message.buttons[button_id].index
            if button_index == ms.button_index and not is_form:
                return False  # nothing happened
            ms.button_index = button_index
        else:
            if custom_reply == ms.custom_reply:
                return False
            ms.custom_reply = custom_reply
        ms.dismissed = False
    message.generation += 1
    if message.flags & Message.FLAG_AUTO_LOCK == Message.FLAG_AUTO_LOCK:
        message.flags |= Message.FLAG_LOCKED
        locked = True
    message.removeStatusIndex(responder, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX)
    if message.sender_type == FriendDetail.TYPE_USER and message.sender != MC_DASHBOARD:
        message.addStatusIndex(message.sender, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX)

    if message.step_id:
        parent_message = get_message(message_parent_key, None) if message_parent_key else None
        bump_flow_statistics_for_message_update(responder, added_flow_statuses, message, parent_message, button_id)

    return message, ms, locked


def _validate_attachments(attachmentTOs):
    if attachmentTOs is None or attachmentTOs is MISSING:
        attachmentTOs = list()

    for i, a in enumerate(attachmentTOs):
        if a.download_url is None or not (a.download_url.startswith("http://")
                                          or a.download_url.startswith("https://")):
            raise InvalidAttachmentException(reason="Invalid download_url (%s) for attachment %s. "
                                             "It must be reachable over http or https" % (a.download_url, i))

        if a.content_type not in AttachmentTO.CONTENT_TYPES:
            raise InvalidAttachmentException(reason="Invalid content_type (%s) for attachment %s. "
                                             "Valid content_types are: %s" % (a.content_type, i,
                                                                              AttachmentTO.CONTENT_TYPES))
        if a.size is MISSING or a.size is None:
            a.size = -1
    return attachmentTOs

def _add_attachments(attachmentTOs, message):
    message.attachments = Attachments()
    for i, a in enumerate(attachmentTOs):
        attachment = Attachment()
        attachment.index = i
        attachment.content_type = a.content_type
        attachment.download_url = a.download_url
        attachment.name = a.name
        attachment.size = a.size
        message.attachments.add(attachment)


def _addButtons(buttons, message):
    message.buttons = Buttons()
    button_index = 0
    for b in buttons:
        button = Button()
        button.id = unicode(b.id)
        button.index = button_index
        button.caption = b.caption
        button.action = b.action
        button.ui_flags = b.ui_flags
        message.buttons.add(button)
        button_index += 1

def convert_unicode_widget_result(wrTO):
    wr = UnicodeWidgetResult()
    wr.value = wrTO.value
    return wr

def convert_unicode_list_widget_result(wrTO):
    wr = UnicodeListWidgetResult()
    wr.values = wrTO.values
    return wr

def convert_long_widget_result(wrTO):
    wr = LongWidgetResult()
    wr.value = wrTO.value
    return wr

def convert_long_list_widget_result(wrTO):
    wr = LongListWidgetResult()
    wr.values = wrTO.values
    return wr

def convert_float_widget_result(wrTO):
    wr = FloatWidgetResult()
    wr.value = wrTO.value
    return wr

def convert_float_list_widget_result(wrTO):
    wr = FloatListWidgetResult()
    wr.values = wrTO.values
    return wr

def convert_location_widget_result(wrTO):
    wr = LocationWidgetResult()
    wr.horizontal_accuracy = wrTO.horizontal_accuracy
    wr.vertical_accuracy = wrTO.vertical_accuracy
    wr.latitude = wrTO.latitude
    wr.longitude = wrTO.longitude
    wr.altitude = wrTO.altitude
    wr.timestamp = wrTO.timestamp
    return wr

def convert_mydigipass_widget_result(wrTO):
    # No conversion needed. wrTO inherits from MyDigiPassWidgetResult.
    return wrTO

def convert_advanced_order_widget_result(wrTO):
    # No conversion needed. wrTO inherits from AdvancedOrderWidgetResult.
    return wrTO

def convert_text_line(widgetTO):
    widget = TextLine()
    widget.max_chars = widgetTO.max_chars
    widget.place_holder = widgetTO.place_holder
    widget.value = widgetTO.value
    return widget

def convert_text_block(widgetTO):
    widget = TextBlock()
    widget.max_chars = widgetTO.max_chars
    widget.place_holder = widgetTO.place_holder
    widget.value = widgetTO.value
    return widget

def convert_auto_complete(widgetTO):
    widget = AutoComplete()
    widget.suggestions = list(widgetTO.suggestions)
    widget.max_chars = widgetTO.max_chars
    widget.place_holder = widgetTO.place_holder
    widget.value = widgetTO.value
    return widget

def convert_single_select(widgetTO):
    widget = SingleSelect()
    widget.choices = [ Choice(label=c.label, value=c.value) for c in widgetTO.choices ]
    widget.value = widgetTO.value
    return widget

def convert_multi_select(widgetTO):
    widget = MultiSelect()
    widget.choices = [ Choice(label=c.label, value=c.value) for c in widgetTO.choices ]
    widget.values = list(widgetTO.values)
    return widget

def convert_date_select(widgetTO):
    widget = DateSelect()
    widget.has_date = widgetTO.date not in [MISSING, None]
    widget.date = widgetTO.date if widget.has_date else None
    widget.has_max_date = widgetTO.max_date not in [MISSING, None]
    widget.max_date = widgetTO.max_date if widget.has_max_date else None
    widget.has_min_date = widgetTO.min_date not in [MISSING, None]
    widget.min_date = widgetTO.min_date if widget.has_min_date else None
    widget.minute_interval = widgetTO.minute_interval if widgetTO.minute_interval not in [MISSING, None] else DateSelect.DEFAULT_MINUTE_INTERVAL
    widget.mode = widgetTO.mode
    widget.unit = widgetTO.unit if widgetTO.unit not in [MISSING, None] else DateSelect.DEFAULT_UNIT
    return widget

def convert_single_slider(widgetTO):
    widget = SingleSlider()
    widget.max = widgetTO.max
    widget.min = widgetTO.min
    widget.precision = widgetTO.precision
    widget.step = widgetTO.step
    widget.unit = widgetTO.unit
    widget.value = widgetTO.value
    return widget

def convert_range_slider(widgetTO):
    widget = RangeSlider()
    widget.high_value = widgetTO.high_value
    widget.low_value = widgetTO.low_value
    widget.max = widgetTO.max
    widget.min = widgetTO.min
    widget.precision = widgetTO.precision
    widget.step = widgetTO.step
    widget.unit = widgetTO.unit
    return widget

def convert_photo_upload(widgetTO):
    widget = PhotoUpload()
    widget.quality = widgetTO.quality
    widget.gallery = widgetTO.gallery
    widget.camera = widgetTO.camera
    widget.ratio = widgetTO.ratio
    return widget

def convert_gps_location(widgetTO):
    widget = GPSLocation()
    widget.gps = widgetTO.gps
    return widget

def convert_my_digi_pass(widgetTO):
    widget = MyDigiPass()
    widget.scope = widgetTO.scope
    return widget

def convert_advanced_order(widgetTO):
    widget = AdvancedOrder()
    widget.currency = widgetTO.currency
    widget.leap_time = widgetTO.leap_time
    widget.categories = []
    for c in widgetTO.categories:
        advancedOrderCategory = AdvancedOrderCategory()
        advancedOrderCategory.id = c.id
        advancedOrderCategory.name = c.name
        advancedOrderCategory.items = c.items
        widget.categories.append(advancedOrderCategory)
    return widget

def _add_form(formTO, fm):
    pos_btn = Button()
    pos_btn.action = u"confirm://%s" % formTO.positive_confirmation if formTO.positive_confirmation else None
    pos_btn.caption = formTO.positive_button
    pos_btn.ui_flags = formTO.positive_button_ui_flags
    pos_btn.id = Form.POSITIVE
    pos_btn.index = 0

    neg_btn = Button()
    neg_btn.action = u"confirm://%s" % formTO.negative_confirmation if formTO.negative_confirmation else None
    neg_btn.caption = formTO.negative_button
    neg_btn.ui_flags = formTO.negative_button_ui_flags
    neg_btn.id = Form.NEGATIVE
    neg_btn.index = 1

    fm.buttons = Buttons()
    fm.buttons.add(pos_btn)
    fm.buttons.add(neg_btn)

    form = Form()
    form.type = formTO.type
    form.widget = WIDGET_MAPPING[formTO.type].to_model_conversion(formTO.widget)
    form.javascript_validation = formTO.javascript_validation
    fm.form = form

def _send_form_updated(responder, message, parent_message_key, ms, button_id):
    from rogerthat.service.api.messaging import form_acknowledged

    sender_svc_user, identifier = get_service_identity_tuple(message.sender)
    sender_svc_profile = get_service_profile(sender_svc_user)

    parent_message_key = message.mkey if message.isRootMessage else message.parent_key().name()
    kwargs = dict(status=ms.status,
                  form_result=ms.form_result,
                  answer_id=button_id,
                  member=get_human_user_from_app_user(responder).email(),
                  message_key=message.mkey,
                  tag=message.tag,
                  received_timestamp=ms.received_timestamp,
                  acked_timestamp=ms.acked_timestamp,
                  parent_message_key=parent_message_key,
                  service_identity=identifier,
                  user_details=[UserDetailsTO.fromUserProfile(get_user_profile(responder))])
    if message.flags & Message.FLAG_SENT_BY_MFR == Message.FLAG_SENT_BY_MFR:
        kwargs[TARGET_MFR] = True

    result_key = unicode(uuid.uuid4())
    kwargs['result_key'] = result_key
    kwargs[DO_NOT_SAVE_RPCCALL_OBJECTS] = True

    # kwargs should contain service_identity
    form_ack_call = form_acknowledged(message_service_form_update_response_handler, logServiceError, sender_svc_profile, **kwargs)
    if form_ack_call:  # None if messaging.form_update is not implemented
        form_ack_call.result_key = result_key
        form_ack_call.member = responder
        form_ack_call.parent_message_key = parent_message_key
        form_ack_call.put()

    # Send updates to web/phone
    w_descr = WIDGET_MAPPING[message.form.type]
    req = w_descr.form_updated_req_to_type.fromMessageAndMember(message, responder)

    current_mobile = users.get_current_mobile()
    # Send updates to phone
    kwargs = {CAPI_KEYWORD_ARG_PRIORITY: PRIORITY_HIGH}
    if current_mobile:
        kwargs[SKIP_ACCOUNTS] = current_mobile.account
    w_descr.form_updated_call(form_updated_response_handler, logError, responder, request=req, **kwargs)
    if current_mobile:
        # Send updates to web client
        channel.send_message(responder, u'rogerthat.messaging.formUpdate', \
                             update=serialize_complex_value(req, w_descr.form_updated_req_to_type, False))

def _get_chat_members_for_update(message):
    # its to heavy to send updates to chats bigger then MAX_CHAT_MEMBER_UPDATE_SIZE
    # because its number of updates multiplies by member

    members = set()
    for chat_members in ChatMembers.all().ancestor(message.parent_key() or message.key()):
        for m in chat_members.members:
            members.add(m)
            if len(members) > MAX_CHAT_MEMBER_UPDATE_SIZE:
                break
        else:
            continue  # we did not break, len(members) <= MAX_CHAT_MEMBER_UPDATE_SIZE

        # len(members) > MAX_CHAT_MEMBER_UPDATE_SIZE
        break

    if len(members) > MAX_CHAT_MEMBER_UPDATE_SIZE:
        members = list()
    else:
        members = map(users.User, members)

    return members

def _send_updates(user, message, ms, force_push_to_sender, service_api_code):
    from rogerthat.service.api.messaging import received, acknowledged

    request = MemberStatusUpdateRequestTO.fromMessageAndMember(message, user)

    button_text = _ellipsize_for_json(message.buttons[ms.button_index].caption, 30, cut_on_spaces=False) if request.button_id else None

    # create list of recipients
    current_mobile = users.get_current_mobile()
    if is_flag_set(Message.FLAG_DYNAMIC_CHAT, message.flags):
        if is_flag_set(MemberStatus.STATUS_ACKED, ms.status) and message.buttons and len(message.buttons) > 0:
            members = _get_chat_members_for_update(message)
        else:
            members = list()
    else:
        if message.sharedMembers or user == message.sender:
            members = list(message.members)
            members.append(message.sender)
            members = set(members)
        else:
            members = set([user, message.sender])

    # remove system user
    members = [m for m in members if m != MC_DASHBOARD]

    # address services
    if message.sender != MC_DASHBOARD:
        service_identity_user = None
        remove_sender = False
        if is_service_identity_user(message.sender):
            service_identity_user = message.sender
            remove_sender = True
        elif message.service_api_updates:
            service_identity_user = message.service_api_updates
        if service_identity_user:
            sender_svc_user, identifier = get_service_identity_tuple(service_identity_user)
            sender_service_profile = get_service_profile(sender_svc_user)
            parent_message_key = message.mkey if message.isRootMessage else message.parent_key().name()
            member = get_human_user_from_app_user(user).email()
            kwargs = dict(status=ms.status, answer_id=request.button_id, received_timestamp=ms.received_timestamp, \
                member=member, message_key=message.mkey, tag=message.tag, acked_timestamp=ms.acked_timestamp, \
                parent_message_key=parent_message_key, service_identity=identifier,
                user_details=[UserDetailsTO.fromUserProfile(get_user_profile(user))])
            if message.flags & Message.FLAG_SENT_BY_MFR == Message.FLAG_SENT_BY_MFR:
                kwargs[TARGET_MFR] = True
            if service_api_code == ServiceProfile.CALLBACK_MESSAGING_RECEIVED:
                received(message_service_received_update_response_handler, logServiceError, sender_service_profile, **kwargs)
            elif service_api_code == ServiceProfile.CALLBACK_MESSAGING_ACKNOWLEDGED:
                result_key = unicode(uuid.uuid4())
                kwargs['result_key'] = result_key
                kwargs[DO_NOT_SAVE_RPCCALL_OBJECTS] = True
                ack_call = acknowledged(message_service_acknowledged_update_response_handler, logServiceError, sender_service_profile, **kwargs)
                if ack_call:  # None if message.update (acknowledge) is not implemented
                    ack_call.result_key = result_key
                    ack_call.parent_message_key = parent_message_key
                    ack_call.member = user
                    ack_call.put()
            else:
                raise ValueError(service_api_code)

            if remove_sender and message.sender in members:
                members.remove(message.sender)


    for member in members:
        priority = PRIORITY_HIGH if force_push_to_sender and ((message.sender == member and user != message.sender) or message.sender == user) and ms.button_index >= 0 else PRIORITY_NORMAL
        kwargs = {CAPI_KEYWORD_ARG_PRIORITY: priority}
        if ms.status & MemberStatus.STATUS_ACKED == MemberStatus.STATUS_ACKED and priority == PRIORITY_HIGH:
            user_profile = get_user_profile(user)
            from_ = _ellipsize_for_json(user_profile.name or user.email(), 30, cut_on_spaces=False)
            mezz = message.message
            kwargs[CAPI_KEYWORD_ARG_APPLE_PUSH_MESSAGE] = base64.encodestring(\
                construct_push_notification('MA', [from_, mezz, button_text], 'a.aiff', \
                    lambda args, too_big: [from_, _ellipsize_for_json(args[1], _len_for_json(args[1]) - too_big), button_text],
                    a=message.key().name()))
        if current_mobile and current_mobile.user == member:
            kwargs[SKIP_ACCOUNTS] = [current_mobile.account]
        updateMessageMemberStatus(message_member_response_handler, logError, member, request=request, **kwargs)

    # address regular users
    if members:
        if not current_mobile and user in members:
            members.remove(user)
        channel.send_message(members, u'rogerthat.messaging.memberUpdate', \
                             update=serialize_complex_value(request, MemberStatusUpdateRequestTO, False))

def _send_locked(message, dirty_behavior):
    request = MessageLockedRequestTO.fromMessage(message)
    request.dirty_behavior = dirty_behavior
    current_mobile = users.get_current_mobile()

    # create list of recipients
    if is_flag_set(Message.FLAG_DYNAMIC_CHAT, message.flags):
        members = _get_chat_members_for_update(message)
    else:
        members = list(message.members)
        members.append(message.sender)
        members = set(members)

    human_members = [m for m in members if m != MC_DASHBOARD]
    allow_chat_buttons = is_flag_set(Message.FLAG_DYNAMIC_CHAT | Message.FLAG_ALLOW_CHAT_BUTTONS, message.flags)
    if not allow_chat_buttons:
        if message.sender in human_members and is_service_identity_user(message.sender):
            human_members.remove(message.sender)

    channel.send_message(human_members, u'rogerthat.messaging.messageLocked', request=serialize_complex_value(request, MessageLockedRequestTO, False))
    if not current_mobile or allow_chat_buttons:
        messageLocked(message_locked_response_handler, logError, human_members, request=request)
    else:
        messageLocked(message_locked_response_handler, logError, human_members, request=request, SKIP_ACCOUNTS=[current_mobile.account])


@returns([RpcCAPICall])
@arguments(user=users.User, parent_message_key=unicode)
def _send_deleted(user, parent_message_key):
    request = ConversationDeletedRequestTO()
    request.parent_message_key = parent_message_key

    current_mobile = users.get_current_mobile()
    if current_mobile:
        channel.send_message(user, u'rogerthat.messaging.conversationDeleted', parent_message_key=parent_message_key)
        return conversationDeleted(conversation_deleted_response_handler, logError, user, request=request,
                                   SKIP_ACCOUNTS=[current_mobile.account])
    else:
        return conversationDeleted(conversation_deleted_response_handler, logError, user, request=request)

@mapping('com.mobicage.capi.message.message_member_status_update_response_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=MemberStatusUpdateResponseTO)
def message_member_response_handler(context, result):
    pass

@mapping('com.mobicage.capi.message.message_locked_response_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=MessageLockedResponseTO)
def message_locked_response_handler(context, result):
    pass

@mapping('com.mobicage.capi.message.conversation_deleted_response_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=ConversationDeletedResponseTO)
def conversation_deleted_response_handler(context, result):
    pass

@mapping('com.mobicage.capi.message.form_updated_response_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=UpdateFormResponseTO)
def form_updated_response_handler(context, result):
    pass

@mapping('com.mobicage.capi.message.transfer_completed_response_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=TransferCompletedResponseTO)
def transfer_completed_response_handler(context, result):
    pass

@mapping('message.received.response_handler')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=NoneType)
def message_service_received_update_response_handler(context, result):
    pass

@mapping('message.new_chat_message.response_handler')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=NoneType)
def new_chat_message_response_handler(context, result):
    pass

@mapping('message.acknowledged.response_handler')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=MessageAcknowledgedCallbackResultTO)
def message_service_acknowledged_update_response_handler(context, result):
    from rogerthat.bizz.service import handle_fast_callback
    return handle_fast_callback(context, result)

@mapping('message.form_update.response_handler')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=FormAcknowledgedCallbackResultTO)
def message_service_form_update_response_handler(context, result):
    from rogerthat.bizz.service import handle_fast_callback
    return handle_fast_callback(context, result)

@mapping('message.flow_member_result.response_handler')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=FlowMemberResultCallbackResultTO)
def message_service_flow_member_result_response_handler(context, result):
    from rogerthat.bizz.service import handle_fast_callback
    return handle_fast_callback(context, result)

def _validate_tag(tag, allow_reserved_tag=False):
    if not tag:
        return

    if len(tag) > 500:
        raise TagTooLargeException()

    if not allow_reserved_tag and tag.startswith(MC_RESERVED_TAG_PREFIX):
        raise ReservedTagException()

def _validate_buttons(buttons, flags):
    if buttons:
        buttonids = list()
        for b in buttons:
            if b.action:
                scheme, _, _, _, _, _ = urllib2.urlparse.urlparse(b.action)
                if not scheme in ('http', 'https', 'geo', 'tel', 'mailto', 'confirm'):
                    raise UnsupportedActionTypeException(scheme)
                if b.action.startswith("mailto:") and not b.action.startswith("mailto://"):
                    b.action = "mailto://" + b.action[7:]
            if isinstance(b, AnswerTO) and b.type != "button":
                raise UnknownAnswerWidgetType(b.type)
            if not b.id or not b.caption:
                raise IncompleteButtonException()
            if b.ui_flags == MISSING:
                b.ui_flags = 0
            else:
                _validate_button_ui_flags(b.ui_flags, b.id)
            buttonids.append(b.id)
        if len(buttonids) != len(set(buttonids)):
            raise DuplicateButtonIdException()
    else:
        if Message.FLAG_ALLOW_DISMISS & flags != Message.FLAG_ALLOW_DISMISS:
            raise UnDismissableMessagesNeedAnswersException()


def _validate_priority(priority):
    if priority not in Message.PRIORITIES:
        raise InvalidPriorityException(priority)


def _validate_step_id(step_id, flags, member_users):
    if step_id and not (is_flag_set(Message.FLAG_AUTO_LOCK, flags) and len(member_users) <= 1):
        logging.debug('member_users: %s', member_users)
        logging.debug('flags: %s', flags)
        raise StepIdForbiddenException()

    from rogerthat.bizz.service.mfd import get_printable_id_from_b64id
    return get_printable_id_from_b64id(step_id)


def _validate_branding(branding_hash, sender):
    if sender != MC_DASHBOARD and branding_hash:
        branding = get_branding(branding_hash)
        if not branding:
            logging.debug("Branding %s not found" % branding_hash)
            raise BrandingNotFoundException()
        if branding.type != Branding.TYPE_NORMAL:
            raise InvalidBrandingException()


def _validate_form(formTO, service_user):
    if not formTO.type:
        raise InvalidFormException("Form has no or empty attribute 'type'.")
    if not formTO.widget or formTO.widget is MISSING:
        raise InvalidFormException("Form has no or empty attribute 'widget'.")
    WIDGET_MAPPING[formTO.type].to_validate(formTO.widget)
    if formTO.type == MyDigiPassTO.TYPE:
        validate_my_digi_pass_support(service_user)
    if formTO.positive_button == MISSING or formTO.positive_button == None or not formTO.positive_button.strip():
        raise IncompleteButtonException()
    if formTO.negative_button == MISSING or formTO.negative_button == None or not formTO.negative_button.strip():
        raise IncompleteButtonException()
    if formTO.positive_confirmation == MISSING:
        formTO.positive_confirmation = None
    if formTO.negative_confirmation == MISSING:
        formTO.negative_confirmation = None

    if formTO.positive_button_ui_flags == MISSING:
        formTO.positive_button_ui_flags = 0
    else:
        _validate_button_ui_flags(formTO.positive_button_ui_flags, Form.POSITIVE)

    if formTO.negative_button_ui_flags == MISSING:
        formTO.negative_button_ui_flags = 0
    else:
        _validate_button_ui_flags(formTO.negative_button_ui_flags, Form.NEGATIVE)

    if formTO.javascript_validation == MISSING:
        formTO.javascript_validation = None

def _len_for_json(unicode_str):
    return len(json.dumps(unicode_str)) - 2

def _ellipsize_for_json(unicode_str, max_json_byte_length, cut_on_spaces=True):

    json_str = json.dumps(unicode_str)[1:-1]
    if len(json_str) <= max_json_byte_length:
        return unicode_str

    if max_json_byte_length < 4:
        return '.' * max(0, max_json_byte_length)

    m = json_str[:max_json_byte_length - 3]
    if cut_on_spaces and " " in m:
        encoded_bytes = list(m)
        encoded_bytes.reverse()
        encoded_bytes = encoded_bytes[encoded_bytes.index(" ") + 1:]
        encoded_bytes.reverse()
        shorter_json_str = '"' + "".join(encoded_bytes) + '..."'
        return json.loads(shorter_json_str)
    else:
        # Note: we might have cut halfway through an encoded character \n or \u1234
        while m:
            try:
                shorter_json_str = '"' + m + '..."'
                return json.loads(shorter_json_str)
            except:
                # Cut off one byte
                m = m[:-1]
        logging.warn('json squashing error: %s (max_json_byte_length: %s)', json_str, max_json_byte_length)
        return ''

def _generate_push_json(message, parent_message, recipient_app_user, sender_is_service_identity=False):
    from rogerthat.bizz.profile import get_profile_info_name
    if sender_is_service_identity:
        sender_user = add_slash_default(message.sender)
    else:
        sender_user = message.sender
    sender_name = get_profile_info_name(sender_user, get_app_id_from_app_user(recipient_app_user))
    if not sender_name:
        logging.error("Msg sender has no name: %s" % message.sender.email())
        sender_name = message.sender.email()
    from_ = _ellipsize_for_json(sender_name, 30, cut_on_spaces=False)
    is_chat = is_flag_set(Message.FLAG_DYNAMIC_CHAT, message.flags)
    if is_chat and not parent_message:
        # 1st chat message is a JSON dict
        mezz = json.loads(message.message)['t']
    else:
        mezz = message.message

    silent = is_flag_set(Message.ALERT_FLAG_SILENT, message.alert_flags)
    if parent_message:
        if is_chat:
            # 1st chat message is a JSON dict
            pmezz = json.loads(parent_message.message)['t']
        else:
            pmezz = parent_message.message

        return base64.encodestring(\
                construct_push_notification('RM', [from_, mezz, pmezz], None if silent else 'r.aiff', \
                    lambda args, too_big: [from_, _ellipsize_for_json(args[1], _len_for_json(args[1]) - (too_big / 2) - too_big % 2), _ellipsize_for_json(args[2], _len_for_json(args[2]) - too_big / 2 - too_big % 2)],
                    r=message.key().name()))
    else:
        return base64.encodestring(\
                construct_push_notification('NM', [from_, mezz], None if silent else 'n.aiff', \
                    lambda args, too_big: [from_, _ellipsize_for_json(args[1], _len_for_json(args[1]) - too_big)],
                    n=message.key().name()))


@returns(NoneType)
@arguments(user=users.User, service_identity_user=users.User, parent_message_key=unicode, message_key=unicode,
           total_chunks=int, number=int, content=unicode, photo_hash=unicode, content_type=unicode)
def store_chunk(user, service_identity_user, parent_message_key, message_key, total_chunks, number, content, photo_hash,
                content_type):
    if service_identity_user:
        azzert("/" in service_identity_user.email())

    logging.debug("Storing chunk %s/%s (%.3f kb)" % (number, total_chunks, len(content) / 1000.0))

    def run():
        now_ = now()
        puts = list()
        transfer_result = get_transfer_result(parent_message_key, message_key)
        if not transfer_result or total_chunks != -1:  # first chunk and last chunk
            transfer_result = TransferResult(key=TransferResult.create_key(parent_message_key, message_key),
                                             total_chunks=total_chunks,
                                             photo_hash=photo_hash.upper() if photo_hash else None,
                                             status=TransferResult.STATUS_PENDING,
                                             service_identity_user=service_identity_user,
                                             timestamp=now_,
                                             content_type=content_type)
            puts.append(transfer_result)

        chunk = TransferChunk(key_name=str(number),
                              parent=transfer_result,
                              content=db.Blob(str(content)),
                              number=number,
                              timestamp=now_)
        puts.append(chunk)
        db.put(puts)
        if transfer_result.total_chunks != -1:
            logging.debug("Scheduling transfer verification")
            deferred.defer(_verify_transfer, user, transfer_result.key(), _transactional=True)

    db.run_in_transaction(run)

@returns(str)
@arguments(transfer_result_key=db.Key)
def assemble_transfer_from_chunks(transfer_result_key):
    stream = StringIO()

    for photo_upload_chunk in get_transfer_chunks(transfer_result_key):
        stream.write(photo_upload_chunk.content)

    try:
        zipped_image = base64.b64decode(stream.getvalue())
        image = zlib.decompress(zipped_image)
    except:
        logging.exception("Could not unzip assembled chunks")
        raise BusinessException("Could not unzip assembled chunks")
    return image

@returns(NoneType)
@arguments(user=users.User, transfer_result_key=db.Key)
def _verify_transfer(user, transfer_result_key):

    def trans():
        transfer_result = db.get(transfer_result_key)
        if transfer_result.status in (TransferResult.STATUS_VERIFIED, TransferResult.STATUS_FAILED):
            # already verified
            return True, transfer_result.status == TransferResult.STATUS_VERIFIED, transfer_result
        key = TransferResult.create_key(transfer_result.parent_message_key, transfer_result.message_key)
        db_chunk_count = count_transfer_chunks(key)
        logging.debug("Got %s/%s chunks" % (db_chunk_count, transfer_result.total_chunks))
        if db_chunk_count == transfer_result.total_chunks:
            transfer = assemble_transfer_from_chunks(transfer_result_key)
            hash_ = hashlib.sha256(transfer).hexdigest().upper()

            if hash_ == transfer_result.photo_hash:
                transfer_result.status = TransferResult.STATUS_VERIFIED
                transfer_result.put()

                req = TransferCompletedRequestTO()
                req.parent_message_key = transfer_result.parent_message_key
                req.message_key = transfer_result.message_key
                req.result_url = u"%s/unauthenticated/mobi/service/photo/download/" % get_server_settings().baseUrl
                json_params = {'parent_message_key' : transfer_result.parent_message_key or ""}
                json_params['message_key'] = transfer_result.message_key
                if transfer_result.service_identity_user:
                    service_user = get_service_user_from_service_identity_user(transfer_result.service_identity_user)
                    service_profile = get_service_profile(service_user, False)
                    if service_profile.callBackURI == "mobidick":
                        @db.non_transactional()
                        def _get_api_keys():
                            return iter(get_api_keys(service_user)).next().api_key

                        json_params['X-Nuntiuz-API-Key'] = _get_api_keys()

                req.result_url += base64.b64encode(json.dumps(json_params))
                transferCompleted(transfer_completed_response_handler, logError, user, request=req)
                return True, True, transfer_result
            else:
                logging.error("Could not verify TransferResult: %s \nCalculated hash server: %s\nSupplied hash via client: %s"
                              % (transfer_result_key.name(), hash_, transfer_result.photo_hash))
                transfer_result.status = TransferResult.STATUS_FAILED
                transfer_result.put()
                return True, False, transfer_result
        return False, False, transfer_result

    xg_on = db.create_transaction_options(xg=True)
    complete, verified, transfer_result = db.run_in_transaction_options(xg_on, trans)
    if complete and not verified:
        language = get_user_profile(user).language
        si = get_service_identity(transfer_result.service_identity_user)
        translator = get_translator(si.service_user, ServiceTranslation.IDENTITY_TYPES, language)
        service_name = translator.translate(ServiceTranslation.IDENTITY_TEXT, si.name, language)
        msg = localize(language, u"Failed to upload the photo to %(service_name)s", service_name=service_name)
        dashboardNotification(user, msg, False, "DASHBOARD_" + transfer_result.message_key)


@returns(str)
@arguments(app_user=users.User, thread_key=unicode, avatar_hash=unicode)
def get_conversation_avatar(app_user, thread_key, avatar_hash):
    model = get_thread_avatar(thread_key)
    if model:
        if model.avatar_hash == avatar_hash:
            return str(model.avatar)
        else:
            logging.debug('Thread avatar hash mismatch. %s requested by the client. %s in the dataStore',
                          avatar_hash, model.avatar_hash)

    return None


HUMAN_READABLE_TAG_REGEX = re.compile('(.*?)\\s*\\{.*\\}')


@returns(unicode)
@arguments(tag=unicode)
def parse_to_human_readable_tag(tag):
    if tag is None:
        return None

    if tag.startswith('{') and tag.endswith('}'):
        try:
            tag_dict = json.loads(tag)
        except:
            return tag
        return tag_dict.get('%s.tag' % MC_RESERVED_TAG_PREFIX, tag)

    m = HUMAN_READABLE_TAG_REGEX.match(tag)
    if m:
        return m.group(1)

    return tag


def _get_flow_stats_breadcrumbs(parent_message_datastore_key, child_message_datastore_keys):
    '''Builds a list of messages (excluding the un-acked messages)'''
    azzert(db.is_in_transaction())

    breadcrumbs = list()
    messages = Message.get([parent_message_datastore_key] + child_message_datastore_keys)
    parent_message = messages.pop(0)
    if messages and messages[-1].key() != parent_message.childMessages[-1]:
        logging.warn("previous message was not the last message of the thread (0)")
        messages = Message.get(parent_message.childMessages)

    def append_breadcrumb(message):
        azzert(len(message.memberStatusses) == 1)
        ms = message.memberStatusses[0]
        if message.step_id and is_flag_set(MemberStatus.STATUS_ACKED, ms.status):
            breadcrumbs.append(message.step_id)
            if ms.button_index == -1:
                breadcrumbs.append('')
            else:
                breadcrumbs.append(message.buttons[ms.button_index].id)

    append_breadcrumb(parent_message)
    map(append_breadcrumb, messages)

    tag = parse_to_human_readable_tag(parent_message.tag)
    service_identity_user = add_slash_default(parent_message.sender)

    return breadcrumbs, service_identity_user, tag, parent_message, messages[-1] if messages else parent_message


@returns()
@arguments(app_user=users.User, flow_stats_statuses=[unicode], message=Message, parent_message=Message, btn_id=unicode)
def bump_flow_statistics_for_message_update(app_user, flow_stats_statuses, message, parent_message=None, btn_id=None):
    if parent_message:
        breadcrumbs, service_identity_user, tag, _, _ = \
            _get_flow_stats_breadcrumbs(parent_message.key(), parent_message.childMessages)
    else:
        breadcrumbs = list()
        service_identity_user = add_slash_default(message.sender)
        tag = parse_to_human_readable_tag(message.tag)

    on_trans_committed(bump_flow_statistics, app_user, service_identity_user, tag, today(), breadcrumbs,
                       flow_stats_statuses, message.step_id, btn_id)


@returns()
@arguments(app_user=users.User, service_identity_user=users.User, tag=unicode, today=int,
           breadcrumbs=[unicode], current_step_id=unicode, member_status=MemberStatusTO)
def bump_flow_statistics_by_member_status(app_user, service_identity_user, tag, today, breadcrumbs, current_step_id,
                                          member_status):
    statuses = [FlowStatistics.STATUS_SENT]
    current_btn_id = None
    if member_status:
        if is_flag_set(MemberStatus.STATUS_RECEIVED, member_status.status):
            statuses.append(FlowStatistics.STATUS_RECEIVED)
        if is_flag_set(MemberStatus.STATUS_READ, member_status.status):
            statuses.append(FlowStatistics.STATUS_READ)
        if is_flag_set(MemberStatus.STATUS_ACKED, member_status.status):
            statuses.append(FlowStatistics.STATUS_ACKED)
            current_btn_id = member_status.button_id

    bump_flow_statistics(app_user, service_identity_user, tag, today, breadcrumbs, statuses, current_step_id,
                         current_btn_id)


@returns()
@arguments(app_user=users.User, service_identity_user=users.User, tag=unicode, today=int,
           breadcrumbs=[unicode], statuses=[unicode], current_step_id=unicode, current_btn_id=unicode)
def bump_flow_statistics(app_user, service_identity_user, tag, today, breadcrumbs, statuses, current_step_id,
                         current_btn_id=None):

    slog(msg_=u'Bump flow statistics',
         function_=log_analysis.FLOW_STATS,
         app_user=app_user.email(),
         service_identity_user=service_identity_user.email(),
         tag=tag,
         today=today,
         breadcrumbs=breadcrumbs,
         statuses=statuses,
         current_step_id=current_step_id,
         current_btn_id=current_btn_id)
