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

from mcfw.consts import MISSING
from mcfw.properties import unicode_property, long_property, unicode_list_property, typed_property, object_factory, \
    bool_property
from rogerthat.dal.app import get_app_by_id
from rogerthat.models import Message, ServiceTranslation, App
from rogerthat.models.properties.forms import FormResult
from rogerthat.rpc import users
from rogerthat.to import MESSAGE_TYPE_TO_MAPPING, ROOT_MESSAGE_TYPE_TO_MAPPING
from rogerthat.to.service import UserDetailsTO
from rogerthat.utils.app import create_app_user, remove_app_id, get_human_user_from_app_user, get_app_user_tuple
from rogerthat.utils.service import remove_slash_default, get_service_user_from_service_identity_user


class ButtonTO(object):
    id = unicode_property('1')  # @ReservedAssignment
    caption = unicode_property('2')
    action = unicode_property('3')
    ui_flags = long_property('4', default=0)


class AttachmentTO(object):
    CONTENT_TYPE_IMG_PNG = u"image/png"
    CONTENT_TYPE_IMG_JPG = u"image/jpeg"
    CONTENT_TYPE_PDF = u"application/pdf"
    CONTENT_TYPE_VIDEO_MP4 = u"video/mp4"

    CONTENT_TYPES = (CONTENT_TYPE_IMG_PNG,
                     CONTENT_TYPE_IMG_JPG,
                     CONTENT_TYPE_PDF,
                     CONTENT_TYPE_VIDEO_MP4)

    content_type = unicode_property('1')
    download_url = unicode_property('2')
    name = unicode_property('3')
    size = long_property('4')

    @staticmethod
    def fromModel(attachment_model):
        a = AttachmentTO()
        a.content_type = attachment_model.content_type
        a.download_url = attachment_model.download_url
        a.size = attachment_model.size
        a.name = attachment_model.name
        return a


class AnswerTO(ButtonTO):
    type = unicode_property('50')  # @ReservedAssignment

    @staticmethod
    def fromButtonTO(button):
        a = AnswerTO()
        a.__dict__ = button.__dict__
        a.type = u'button'
        return a


class BroadcastResultTO(object):
    statistics_key = unicode_property('1')


class MemberStatusUpdateRequestTO(object):
    parent_message = unicode_property('0')
    message = unicode_property('1')
    member = unicode_property('2')
    status = long_property('3')
    received_timestamp = long_property('4')
    acked_timestamp = long_property('5')
    button_id = unicode_property('6')
    custom_reply = unicode_property('7')
    flags = long_property('8', default=-1)

    @staticmethod
    def fromMessageAndMember(message, user):
        ms = message.memberStatusses[message.members.index(user)]
        request = MemberStatusUpdateRequestTO()
        request.message = message.mkey
        request.parent_message = message.pkey
        request.member = get_human_user_from_app_user(user).email()
        request.status = ms.status
        request.received_timestamp = ms.received_timestamp
        request.acked_timestamp = ms.acked_timestamp
        request.button_id = None if ms.button_index < 0 else message.buttons[ms.button_index].id
        request.custom_reply = ms.custom_reply
        request.flags = message.flags
        return request


class MemberStatusUpdateResponseTO(object):
    pass


class SendMessageRequestTO(object):
    members = unicode_list_property('1')
    flags = long_property('2')
    timeout = long_property('3')
    parent_key = unicode_property('4')
    message = unicode_property('5')
    buttons = typed_property('6', ButtonTO, True)
    sender_reply = unicode_property('7')
    attachments = typed_property('8', AttachmentTO, True, default=list())
    priority = long_property('9')


class SendMessageResponseTO(object):
    key = unicode_property('1')
    timestamp = long_property('2')


class AckMessageRequestTO(object):
    message_key = unicode_property('1')
    parent_message_key = unicode_property('2')
    button_id = unicode_property('3')
    custom_reply = unicode_property('4')
    timestamp = long_property('5')


class AckMessageResponseTO(object):
    result = long_property('1')


class MarkMessagesAsReadRequestTO(object):
    parent_message_key = unicode_property('1')
    message_keys = unicode_list_property('2')


class MarkMessagesAsReadResponseTO(object):
    pass


class MemberStatusTO(object):
    member = unicode_property('1')
    status = long_property('2')
    received_timestamp = long_property('3')
    acked_timestamp = long_property('4')
    button_id = unicode_property('5')
    custom_reply = unicode_property('6')

    @staticmethod
    def fromMessageMemberStatus(message, memberStatus):
        ms = MemberStatusTO()
        ms.member = remove_app_id(remove_slash_default(message.members[memberStatus.index], warn=True)).email()
        ms.acked_timestamp = memberStatus.acked_timestamp
        if memberStatus.button_index != -1:
            ms.button_id = message.buttons[memberStatus.button_index].id
        else:
            ms.button_id = None
        ms.custom_reply = memberStatus.custom_reply
        ms.received_timestamp = memberStatus.received_timestamp
        ms.status = memberStatus.status
        return ms


class FormResultMemberStatusTO(MemberStatusTO):
    form_result = typed_property('51', FormResult)


class BaseMessageTO(object):
    # Don't forget to update the fromFormMessage function in Message.java & MCTMessage.m when adding properties
    key = unicode_property('1')
    parent_key = unicode_property('2')
    sender = unicode_property('3')
    message = unicode_property('5')
    flags = long_property('6')
    timestamp = long_property('9')
    branding = unicode_property('10')
    threadTimestamp = long_property('11')
    alert_flags = long_property('12')
    message_type = long_property('13')
    context = unicode_property('14')
    thread_size = long_property('15')
    broadcast_type = unicode_property('16', default=None)
    attachments = typed_property('17', AttachmentTO, True, default=[])
    thread_avatar_hash = unicode_property('18', default=None)
    thread_background_color = unicode_property('19', default=None)
    thread_text_color = unicode_property('20', default=None)
    priority = long_property('21', default=Message.PRIORITY_NORMAL)
    default_priority = long_property('22', default=Message.PRIORITY_NORMAL)
    default_sticky = bool_property('23', default=False)

    def __init__(self):
        self.context = None
        self.thread_size = 0

    @staticmethod
    def _populateTO(message, msgTO, member=None):
        msgTO.key = message.mkey
        pk = message.parent_key()
        if pk:
            msgTO.parent_key = pk.name()
        else:
            msgTO.parent_key = None
        msgTO.sender = remove_app_id(remove_slash_default(message.sender, warn=True)).email()
        msgTO.flags = message.flags
        msgTO.timestamp = message.creationTimestamp
        msgTO.threadTimestamp = message.timestamp
        msgTO.message = u"" if message.message is None else message.message
        branding = message.branding
        if branding:
            from rogerthat.bizz.branding import OLD_SYSTEM_BRANDING_HASHES
            if branding in OLD_SYSTEM_BRANDING_HASHES:
                branding = get_app_by_id(App.APP_ID_ROGERTHAT).core_branding_hash
            else:
                branding = unicode(branding)
        msgTO.branding = branding
        msgTO.alert_flags = message.alert_flags if message.alert_flags != None else Message.ALERT_FLAG_VIBRATE
        msgTO.message_type = message.TYPE
        if member and message.broadcast_type:
            from rogerthat.bizz.i18n import get_translator
            from rogerthat.dal.profile import get_user_profile
            lang = get_user_profile(member).language
            translator = get_translator(get_service_user_from_service_identity_user(message.sender),
                                        [ServiceTranslation.BROADCAST_TYPE], lang)
            msgTO.broadcast_type = translator.translate(ServiceTranslation.BROADCAST_TYPE, message.broadcast_type, lang)
        else:
            msgTO.broadcast_type = None
        msgTO.attachments = map(AttachmentTO.fromModel, sorted(message.attachments or list(), key=lambda a: a.index))

        msgTO.thread_avatar_hash = message.thread_avatar_hash
        msgTO.thread_background_color = message.thread_background_color
        msgTO.thread_text_color = message.thread_text_color
        msgTO.priority = Message.PRIORITY_NORMAL if message.priority is None else message.priority
        msgTO.default_priority = Message.PRIORITY_NORMAL if message.default_priority is None else message.default_priority
        msgTO.default_sticky = False if message.default_sticky is None else message.default_sticky
        return msgTO


class MessageTO(BaseMessageTO):
    members = typed_property('51', MemberStatusTO, True)
    timeout = long_property('52')
    buttons = typed_property('53', ButtonTO, True)
    dismiss_button_ui_flags = long_property('54', default=0)

    @staticmethod
    def fromMessage(message, member=None):
        m = MessageTO()
        BaseMessageTO._populateTO(message, m, member)
        member = remove_app_id(member)
        m.timeout = message.timeout
        m.dismiss_button_ui_flags = message.dismiss_button_ui_flags or 0
        m.buttons = list()
        for b in sorted(message.buttons, key=lambda x: x.index):
            button = ButtonTO()
            button.id = b.id
            button.caption = b.caption
            button.action = b.action
            button.ui_flags = b.ui_flags
            m.buttons.append(button)
        m.members = list()
        for mem in message.memberStatusses:
            current_member = remove_app_id(remove_slash_default(message.members[mem.index]))
            if current_member != message.sender and member and member != current_member:
                continue
            m.members.append(MemberStatusTO.fromMessageMemberStatus(message, mem))
        return m


class BaseRootMessageTO(object):
    messages = typed_property('1000', object_factory("message_type", MESSAGE_TYPE_TO_MAPPING), True)
    message_type = long_property('1001')


class RootMessageTO(MessageTO, BaseRootMessageTO):
    @staticmethod
    def fromMessage(message, member=None):
        rm = RootMessageTO()
        rm.__dict__.update(MessageTO.fromMessage(message, member).__dict__)
        rm.messages = list()
        rm.message_type = message.TYPE
        return rm


class RootMessageListTO(object):
    messages = typed_property('1', object_factory("message_type", ROOT_MESSAGE_TYPE_TO_MAPPING), True)
    cursor = unicode_property('2')
    batch_size = long_property('3')


class MessageListTO(object):
    messages = typed_property('1', object_factory("message_type", MESSAGE_TYPE_TO_MAPPING), True)
    cursor = unicode_property('2')
    batch_size = long_property('3')


class NewMessageRequestTO(object):
    message = typed_property('1', MessageTO, False)


class NewMessageResponseTO(object):
    received_timestamp = long_property('1')


class UpdateMessageRequestTO(object):
    message_key = unicode_property('1')
    parent_message_key = unicode_property('2')
    last_child_message = unicode_property('3')
    has_flags = bool_property('4')
    flags = long_property('5')
    has_existence = bool_property('6')
    existence = long_property('7')
    message = unicode_property('8', default=None)
    thread_avatar_hash = unicode_property('9', default=None, doc=u"If None, then field was not updated. "
                                                                 "If '', then the client should go back to the default behavior.")
    thread_background_color = unicode_property('10', default=None, doc=u"If None, then field was not updated. "
                                                                       "If '', then the client should go back to the default behavior.")
    thread_text_color = unicode_property('11', default=None, doc=u"If None, then this field was not updated. "
                                                                 "If '', then the client should go back to the default behavior.")

    @classmethod
    def create(cls, parent_message_key, message_key, last_child_message, flags=MISSING, existence=MISSING, message=None,
               thread_avatar_hash=None, thread_background_color=None, thread_text_color=None):
        to = cls()
        to.parent_message_key = parent_message_key
        to.message_key = message_key
        to.last_child_message = last_child_message
        to.message = message

        to.has_flags = flags is not MISSING
        if to.has_flags:
            to.flags = flags
        else:
            to.flags = 0

        to.has_existence = existence is not MISSING
        if to.has_existence:
            to.existence = existence
        else:
            to.existence = 0

        to.thread_avatar_hash = thread_avatar_hash
        to.thread_background_color = thread_background_color
        to.thread_text_color = thread_text_color

        return to


class UpdateMessageResponseTO(object):
    pass


class DirtyBehavior(object):
    NORMAL = 1
    MAKE_DIRTY = 2
    CLEAR_DIRTY = 3
    ALL = (NORMAL, MAKE_DIRTY, CLEAR_DIRTY)


class LockMessageRequestTO(object):
    message_key = unicode_property('1')
    message_parent_key = unicode_property('2')


class LockMessageResponseTO(object):
    members = typed_property('1', MemberStatusTO, True)

    @staticmethod
    def fromMessage(message):
        lmr = LockMessageResponseTO()
        lmr.members = list()
        for mem in message.memberStatusses:
            lmr.members.append(MemberStatusTO.fromMessageMemberStatus(message, mem))
        return lmr


class MessageLockedRequestTO(object):
    parent_message_key = unicode_property('0')
    message_key = unicode_property('1')
    members = typed_property('2', MemberStatusTO, True)
    dirty_behavior = long_property('3')

    @staticmethod
    def fromMessage(message):
        mlr = MessageLockedRequestTO()
        mlr.message_key = message.mkey
        pk = message.parent_key()
        mlr.parent_message_key = pk.name() if pk else None
        mlr.members = list()
        for mem in message.memberStatusses:
            mlr.members.append(MemberStatusTO.fromMessageMemberStatus(message, mem))
        return mlr


class MessageLockedResponseTO(object):
    pass


class MessageReceivedRequestTO(object):
    message_key = unicode_property('1')
    message_parent_key = unicode_property('2')
    received_timestamp = long_property('3')


class MessageReceivedResponseTO(object):
    pass


class BaseMemberTO(object):
    member = unicode_property('1')
    app_id = unicode_property('2')

    @classmethod
    def from_user(cls, app_user):
        memberTO = cls()
        app_user, memberTO.app_id = get_app_user_tuple(app_user)
        memberTO.member = app_user.email()
        return memberTO

    @classmethod
    def create(cls, member, app_id):
        memberTO = cls()
        memberTO.member = member
        memberTO.app_id = app_id
        return memberTO


class MemberTO(BaseMemberTO):
    alert_flags = long_property('51')

    @classmethod
    def from_user(cls, app_user, alert_flags=Message.ALERT_FLAG_VIBRATE):
        memberTO = super(MemberTO, cls).from_user(app_user)
        memberTO.alert_flags = alert_flags
        return memberTO


class UserMemberTO(object):
    member = typed_property('1', users.User, False)
    alert_flags = long_property('2')
    read_only = bool_property('3', default=False)

    def __init__(self, member, alert_flags=Message.ALERT_FLAG_VIBRATE, read_only=False):
        self.member = member
        self.alert_flags = alert_flags
        self.read_only = read_only

    @staticmethod
    def fromMemberTO(m, readonly=False):
        u = users.User(m.member) if m.app_id is MISSING else create_app_user(users.User(m.member), m.app_id)
        return UserMemberTO(u, m.alert_flags, readonly)


class GetConversationAvatarRequestTO(object):
    avatar_hash = unicode_property('1')
    thread_key = unicode_property('2')


class GetConversationAvatarResponseTO(object):
    avatar = unicode_property('1')


class DeleteConversationRequestTO(object):
    parent_message_key = unicode_property('1')


class DeleteConversationResponseTO(object):
    pass


class ConversationDeletedRequestTO(object):
    parent_message_key = unicode_property('1')


class ConversationDeletedResponseTO(object):
    pass


class GetConversationRequestTO(object):
    parent_message_key = unicode_property('1')
    offset = unicode_property('2', default=None)


class GetConversationResponseTO(object):
    conversation_sent = bool_property('1')


class EndMessageFlowRequestTO(object):
    parent_message_key = unicode_property('1')
    message_flow_run_id = unicode_property('2')
    wait_for_followup = bool_property('3', default=False)


class EndMessageFlowResponseTO(object):
    pass


class UploadChunkRequestTO(object):
    service_identity_user = unicode_property('0')
    parent_message_key = unicode_property('1')
    message_key = unicode_property('2')
    number = long_property('3')
    total_chunks = long_property('4')
    chunk = unicode_property('5')
    photo_hash = unicode_property('6')
    content_type = unicode_property('7')


class UploadChunkResponseTO(object):
    pass


class TransferCompletedRequestTO(object):
    parent_message_key = unicode_property('1')
    message_key = unicode_property('2')
    result_url = unicode_property('3')


class TransferCompletedResponseTO(object):
    pass


class BroadcastTargetAudienceTO(object):
    min_age = long_property('0')
    max_age = long_property('1')
    gender = unicode_property('2')
    app_id = unicode_property('3')


class StartFlowRequestTO(object):
    service = unicode_property('1')
    static_flow = unicode_property('2')
    static_flow_hash = unicode_property('3')
    brandings_to_dwnl = unicode_list_property('4',
                                              doc="The client must download these brandings before starting the flow")
    attachments_to_dwnl = unicode_list_property('5',
                                                doc="The client must download these attachments before starting the flow")
    parent_message_key = unicode_property('6')
    message_flow_run_id = unicode_property('7')


class StartFlowResponseTO(object):
    pass


class KeyValueTO(object):
    key = unicode_property('1')
    value = unicode_property('2')

    @classmethod
    def create(cls, key, value):
        to = cls()
        to.key = key
        to.value = value
        return to


class ChatMessageTO(object):
    sender = typed_property('1', UserDetailsTO)
    parent_message_key = unicode_property('2')
    message_key = unicode_property('3')
    message = unicode_property('4')
    timestamp = long_property('5')

    @classmethod
    def from_model(cls, message, user_profile):
        to = cls()
        to.parent_message_key = message.pkey
        to.message_key = message.mkey
        to.message = message.message
        to.timestamp = message.creationTimestamp
        to.sender = UserDetailsTO.fromUserProfile(user_profile) if user_profile else None
        return to


class ChatMessageListResultTO(object):
    cursor = unicode_property('1')
    messages = typed_property('2', ChatMessageTO, True)

    @classmethod
    def from_model(cls, cursor, messages, user_profiles):
        to = cls()
        to.cursor = cursor
        to.messages = [ChatMessageTO.from_model(m, user_profiles.get(m.sender)) for m in messages]
        return to
