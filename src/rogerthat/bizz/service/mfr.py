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
import hashlib
import json
import logging
import uuid
from xml.dom.minidom import parseString, parse

from google.appengine.api import urlfetch
from google.appengine.ext import db

from rogerthat.bizz.i18n import get_translator
from rogerthat.bizz.messaging import sendMessage, sendForm, ReservedTagException, _ellipsize_for_json, _len_for_json
from rogerthat.bizz.service import get_mfr_sik, get_mfr_api_key
from rogerthat.bizz.service.mfd import message_flow_design_to_xml, get_message_flow_design_context, \
    get_message_flow_by_key_or_name, compress_js_flow_definition
from rogerthat.bizz.service.mfd.mfd_javascript import generate_js_flow
from rogerthat.bizz.service.mfd.sub import MessageFlowRunSub, MemberRunSub
from rogerthat.capi.messaging import startFlow
from rogerthat.consts import MC_RESERVED_TAG_PREFIX
from rogerthat.dal.profile import get_profile_infos, get_service_profile
from rogerthat.dal.service import get_service_identity
from rogerthat.models import MessageFlowDesign, MessageFlowRunRecord, UserProfile, FriendServiceIdentityConnection, \
    ServiceTranslation, CustomMessageFlowDesign, UserData
from rogerthat.rpc import users
from rogerthat.rpc.models import RpcCAPICall, Mobile
from rogerthat.rpc.rpc import logError, mapping, kicks
from rogerthat.rpc.service import ServiceApiException
from rogerthat.settings import get_server_settings
from rogerthat.to.messaging import UserMemberTO, BaseMemberTO, StartFlowRequestTO, StartFlowResponseTO
from rogerthat.to.messaging.service_callback_results import FlowStartResultCallbackResultTO, \
    MessageCallbackResultTypeTO, FormCallbackResultTypeTO
from rogerthat.utils import azzert, try_or_defer, now, bizz_check, get_full_language_string
from rogerthat.utils.app import get_app_user_tuple
from rogerthat.utils.crypto import md5_hex
from rogerthat.utils.iOS import construct_push_notification
from rogerthat.utils.service import get_service_user_from_service_identity_user, \
    get_identity_from_service_identity_user, remove_slash_default
from mcfw.consts import MISSING
from mcfw.rpc import returns, arguments, parse_complex_value, serialize_complex_value


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

class MessageFlowNotFoundException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE_FLOW + 1,
                                     "Message flow definition not found!")

class NonFriendMembersException(ServiceApiException):
    def __init__(self, non_members):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE_FLOW + 2,
                                     "Non-friend members supplied!", non_members=non_members)

class MessageFlowNotValidException(ServiceApiException):
    def __init__(self, error):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE_FLOW + 3,
                                     "Message flow is not valid and cannot be executed in its current state!", error=error)

class MessageParentKeyCannotBeUsedWithMultipleParents(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE_FLOW + 4,
                                     "You can not use the message parent key with multiple members.")

class NoMembersException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE_FLOW + 5,
                                     "No members supplied!")

class MessageFlowDesignInUseException(ServiceApiException):
    def __init__(self, reason):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE_FLOW + 6,
                                     "Message flow can not be deleted", reason=reason)

class InvalidMessageFlowXmlException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE_FLOW + 7,
                                     "The XML is not conform to the message flow design XML schema")

class MessageFlowDesignValidationException(ServiceApiException):
    def __init__(self, message_flow_design):
        self.message_flow_design = message_flow_design
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE_FLOW + 8,
                                     "Message flow design is not valid: %s" % message_flow_design.validation_error,
                                     validation_error=message_flow_design.validation_error)

class InvalidMessageFlowLanguageException(ServiceApiException):
    def __init__(self, expected_language, current_language):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE_FLOW + 9,
                                     "Unexpected language specified in message flow design XML. Expected language '%s', got language '%s'." % (expected_language, current_language),
                                     expected_language=expected_language, current_language=current_language)

class InvalidMessageAttachmentException(ServiceApiException):
    def __init__(self, reason):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_MESSAGE_FLOW + 10, reason)


def _validate_start_flow(service_identity_user, parent_message_key, members, check_friends=True,
                         tag=None, allow_reserved_tag=False):
    if not members:
        raise NoMembersException()

    if parent_message_key and len(members) > 1:
        raise MessageParentKeyCannotBeUsedWithMultipleParents()

    if tag and not allow_reserved_tag and tag.startswith(MC_RESERVED_TAG_PREFIX):
        raise ReservedTagException()

    # Create list with ServiceFriendKeys for the members
    if check_friends:
        fsic_keys = [FriendServiceIdentityConnection.createKey(member, service_identity_user) for member in members]
        fsics = db.get(fsic_keys)  # db.get returns a list of found and None
        non_friends = []
        for (member, fsic) in zip(members, fsics):
            if not fsic:
                m = BaseMemberTO()
                human_user, m.app_id = get_app_user_tuple(member)
                m.member = human_user.email()
                non_friends.append(m)

        if non_friends:
            raise NonFriendMembersException(serialize_complex_value(non_friends, BaseMemberTO, True))


def _create_message_flow_run(service_user, service_identity_user, message_flow_run_key=None, result_callback=True,
                             tag=None):
    message_flow_run_id = message_flow_run_key or str(uuid.uuid4())
    mfr = MessageFlowRunRecord(key_name=MessageFlowRunRecord.createKeyName(service_user, message_flow_run_id))
    mfr.post_result_callback = result_callback
    mfr.tag = tag
    mfr.creationtime = now()
    mfr.service_identity = service_identity_user.email()
    mfr.put()
    return mfr


@returns(unicode)
@arguments(service_identity_user=users.User, message_parent_key=unicode,
           flow=(str, unicode, MessageFlowDesign, CustomMessageFlowDesign),
           members=[users.User], check_friends=bool, result_callback=bool, tag=unicode, context=unicode, key=unicode,
           force_language=unicode, allow_reserved_tag=bool, broadcast_type=unicode, broadcast_guid=unicode)
def start_flow(service_identity_user, message_parent_key, flow, members, check_friends, result_callback, tag=None, \
               context=None, key=None, force_language=None, allow_reserved_tag=False, broadcast_type=None, \
               broadcast_guid=None):
    # key is in fact a force_message_flow_run_id
    svc_user = get_service_user_from_service_identity_user(service_identity_user)

    if isinstance(flow, (str, unicode)):
        mfd = get_message_flow_by_key_or_name(svc_user, flow)
        if not mfd or not mfd.user == svc_user:
            raise MessageFlowNotFoundException()

        if mfd.status != MessageFlowDesign.STATUS_VALID:
            raise MessageFlowNotValidException(mfd.validation_error)
    else:
        mfd = flow

    _validate_start_flow(service_identity_user, message_parent_key, members, check_friends, tag, allow_reserved_tag)
    mfr = _create_message_flow_run(svc_user, service_identity_user, key, result_callback, tag)
    message_flow_run_id = mfr.messageFlowRunId

    d = hashlib.sha256(message_flow_run_id)
    d.update('key for first message in flow!')

    try_or_defer(_execute_flow, service_identity_user, mfd, mfr, members, message_parent_key, context, d.hexdigest(),
                 force_language=force_language, broadcast_type=broadcast_type, tag=tag,
                 _transactional=db.is_in_transaction())

    return message_flow_run_id

@returns(unicode)
@arguments(service_identity_user=users.User, thread_key=unicode, xml=unicode, members=[users.User],
           tag=unicode, context=unicode, force_language=unicode, download_attachments_upfront=bool,
           push_message=unicode, parent_message_key=unicode)
def start_local_flow(service_identity_user, thread_key, xml, members, tag=None, context=None,
                     force_language=None, download_attachments_upfront=False, push_message=None,
                     parent_message_key=None):
    from rogerthat.rpc.calls import HIGH_PRIORITY
    _validate_start_flow(service_identity_user, thread_key, members, tag=tag)
    service_user = get_service_user_from_service_identity_user(service_identity_user)

    js_flow_dict = generate_js_flow(service_user, xml, context, minify=False, parent_message_key=parent_message_key,
                                    must_validate=True)
    # js_flow_dict = { language : (<compiled JS flow>, brandings, attachments) }
    if force_language and force_language is not MISSING:
        if force_language not in js_flow_dict:
            raise InvalidMessageFlowLanguageException(json.dumps(js_flow_dict.keys()), force_language)
        forced_flow = js_flow_dict[force_language]
    else:
        forced_flow = None

    profile_infos = {profile_info.user: profile_info for profile_info in get_profile_infos(members + [service_identity_user])}

    mfr = _create_message_flow_run(service_user, service_identity_user, result_callback=False, tag=tag)
    message_flow_run_id = mfr.messageFlowRunId

    for app_user in members:
        if forced_flow:
            flow_definition, brandings, attachments = forced_flow
        else:
            target_language = profile_infos[app_user].language
            if target_language not in js_flow_dict:
                # fall back to service default language
                target_language = get_service_profile(service_user).defaultLanguage
                if target_language not in js_flow_dict:
                    raise InvalidMessageFlowLanguageException(json.dumps(js_flow_dict.keys()), target_language)

            flow_definition, brandings, attachments = js_flow_dict[target_language]

        force_skip_attachments_download = False
        if push_message:
            for mobile_detail in profile_infos[app_user].mobiles:
                if mobile_detail.type_ == Mobile.TYPE_IPHONE_HTTP_APNS_KICK and mobile_detail.pushId:
                    force_skip_attachments_download = True
                    break

        request = StartFlowRequestTO()
        request.attachments_to_dwnl = attachments if download_attachments_upfront and not force_skip_attachments_download else list()
        request.brandings_to_dwnl = brandings
        request.service = remove_slash_default(service_identity_user).email()
        request.static_flow = compress_js_flow_definition(flow_definition)
        request.static_flow_hash = unicode(md5_hex(flow_definition))
        request.parent_message_key = thread_key
        request.message_flow_run_id = message_flow_run_id
        startFlow(start_flow_response_handler, logError, app_user, request=request)

        if push_message:
            sender_name = _ellipsize_for_json(profile_infos[service_identity_user].name, 30, cut_on_spaces=False)

            for mobile_detail in profile_infos[app_user].mobiles:
                if mobile_detail.type_ == Mobile.TYPE_IPHONE_HTTP_APNS_KICK and mobile_detail.pushId:
                    cbd = dict(r=mobile_detail.account,
                               p=HIGH_PRIORITY,
                               t=["apns"],
                               kid=str(uuid.uuid4()),
                               a=mobile_detail.app_id)
                    cbd['d'] = mobile_detail.pushId
                    cbd['m'] = base64.encodestring(construct_push_notification('NM', [sender_name, push_message], 'n.aiff',
                                                                               lambda args, too_big: [sender_name, _ellipsize_for_json(args[1], _len_for_json(args[1]) - too_big)]))
                    logging.debug('Sending push notification along with start_local_flow.\n%s', cbd)
                    kicks.append(json.dumps(cbd))

    return message_flow_run_id


@mapping('com.mobicage.capi.message.start_flow_response_handler')
@returns()
@arguments(context=RpcCAPICall, result=StartFlowResponseTO)
def start_flow_response_handler(context, result):
    pass


def _create_message_flow_run_xml_doc(service_identity_user, message_flow_design, message_flow_run_record, members,
                                     force_language):
    service_user = get_service_user_from_service_identity_user(service_identity_user)

    if not message_flow_design.xml:
        # Must regenerate xml
        subflowdict = get_message_flow_design_context(message_flow_design)
        translator = get_translator(service_user, ServiceTranslation.MFLOW_TYPES)
        definition_doc = parseString(message_flow_design_to_xml(service_user, message_flow_design, translator, subflowdict)[0].encode('utf-8'))
        message_flow_design.xml = definition_doc.toxml('utf-8')
        message_flow_design.put()
        logging.warning("Message flow design with empty xml property discovered!!!\nkey = %s" % message_flow_design.key())
    else:
        definition_doc = parseString(message_flow_design.xml.encode('utf-8'))

    run = MessageFlowRunSub(launchTimestamp=message_flow_run_record.creationtime)
    si = get_service_identity(service_identity_user)
    run.set_serviceName(si.name)
    run.set_serviceDisplayEmail(si.qualifiedIdentifier or si.user.email())
    run.set_serviceEmail(si.user.email())
    if si.serviceData:
        run.set_serviceData(json.dumps(si.serviceData.to_json_dict()))
    else:
        run.set_serviceData(si.appData)
    fallback_language = force_language or get_service_profile(service_user).defaultLanguage

    mf_languages = list()
    if definition_doc.documentElement.localName == 'messageFlowDefinitionSet':
        for definition_element in definition_doc.documentElement.childNodes:
            if definition_element.localName == 'definition':
                mf_languages.append(definition_element.getAttribute('language'))
    elif definition_doc.documentElement.localName == 'definition':
        mf_languages.append(fallback_language)
    else:
        azzert(False, "Unexpected tag name: %s" % definition_doc.documentElement.localName)

    # if force_language supplied, check if it's in mf_languages
    if force_language:
        bizz_check(force_language in mf_languages, "Can not run in %s." % get_full_language_string(force_language))

    userprofiles = get_profile_infos(members, expected_types=[UserProfile] * len(members))
    user_datas = db.get([UserData.createKey(member, service_identity_user) for member in members])
    for i, p in enumerate(userprofiles):
        member_run_language = force_language or (p.language if p.language in mf_languages else fallback_language)
        human_user, app_id = get_app_user_tuple(p.user)

        if user_datas[i]:
            if user_datas[i].userData:
                user_data = json.dumps(user_datas[i].userData.to_json_dict())
            else:
                user_data = user_datas[i].data
        else:
            user_data = None
        run.add_memberRun(MemberRunSub(status="SUBMITTED", email=human_user.email(), name=p.name, language=member_run_language, appId=app_id, avatarUrl=p.avatarUrl, userData=user_data))

    xml = StringIO()
    xml.write("""<?xml version="1.0" encoding="utf-8"?>\n""")
    run.export(xml, 0, namespace_='', namespacedef_='xmlns="https://rogerth.at/api/1/MessageFlow.xsd"', name_='messageFlowRun')
    xml.reset()
    xml_doc = parse(xml)
    for member_run_child_node in xml_doc.documentElement.childNodes:
        if member_run_child_node.localName == "memberRun":
            break
    else:
        azzert(False, "No child nodes of type 'memberRun' found for xml:\n%s" % xml)

    # put memberRun in xml
    if definition_doc.documentElement.localName == 'messageFlowDefinitionSet':
        for definition_element in definition_doc.documentElement.childNodes:
            if definition_element.localName == 'definition':
                xml_doc.documentElement.insertBefore(definition_element, member_run_child_node)
    elif definition_doc.documentElement.localName == 'definition':
        xml_doc.documentElement.insertBefore(definition_doc.documentElement, member_run_child_node)
    else:
        azzert(False, "Unexpected tag name: %s" % definition_doc.documentElement.localName)

    return xml_doc

def _execute_flow(service_identity_user, message_flow_design, message_flow_run_record, members, message_parent_key,
                  context=None, resultKey=None, force_language=None, broadcast_type=None, broadcast_guid=None, tag=None):
    logging.info("Executing message flow for %s with force_language %s" % (service_identity_user.email(), force_language))

    xml_doc = _create_message_flow_run_xml_doc(service_identity_user, message_flow_design, message_flow_run_record,
                                               members, force_language)
    logging.info(xml_doc.toxml())
    xml = xml_doc.toxml("utf-8")

    settings = get_server_settings()

    headers = {
        'X-Nuntiuz-Service-Identifier-Key': get_mfr_sik(service_identity_user).sik,
        'X-Nuntiuz-Service-Identity': base64.b64encode(get_identity_from_service_identity_user(service_identity_user)),
        'X-Nuntiuz-Service-API-Key': get_mfr_api_key(service_identity_user).key().name(),
        'X-Nuntiuz-Shared-Secret': settings.secret,
        'X-Nuntiuz-MessageFlowRunId': message_flow_run_record.messageFlowRunId,
        'X-Nuntiuz-MessageParentKey': message_parent_key if message_parent_key else "",
        'X-Nuntiuz-Context': context if context else "",
        'X-Nuntiuz-ResultKey': resultKey,
        'Content-type': 'text/xml'
    }

    if broadcast_guid:
        headers['X-Nuntiuz-BroadcastGuid'] = broadcast_guid
    if tag:
        headers['X-Nuntiuz-Tag'] = tag

    result = urlfetch.fetch("%s/api" % settings.messageFlowRunnerAddress, xml, "POST", headers, False, False, deadline=10 * 60)
    if result.status_code != 200:
        raise Exception("MFR returned status code %d !" % result.status_code)
    if len(members) == 1 and result.content:
        try:
            flow_start_result = parse_complex_value(FlowStartResultCallbackResultTO, json.loads(result.content), False)
            if isinstance(flow_start_result.value, MessageCallbackResultTypeTO):
                sendMessage(service_identity_user, [UserMemberTO(members[0], flow_start_result.value.alert_flags)],
                            flow_start_result.value.flags, 0, message_parent_key, flow_start_result.value.message,
                            flow_start_result.value.answers, None, flow_start_result.value.branding,
                            flow_start_result.value.tag, flow_start_result.value.dismiss_button_ui_flags, context,
                            key=resultKey, is_mfr=True, broadcast_type=broadcast_type, broadcast_guid=broadcast_guid,
                            attachments=flow_start_result.value.attachments,
                            step_id=None if flow_start_result.value.step_id is MISSING else flow_start_result.value.step_id)
            elif isinstance(flow_start_result.value, FormCallbackResultTypeTO):
                sendForm(service_identity_user, message_parent_key, members[0], flow_start_result.value.message,
                         flow_start_result.value.form, flow_start_result.value.flags, flow_start_result.value.branding,
                         flow_start_result.value.tag, flow_start_result.value.alert_flags, context, key=resultKey,
                         is_mfr=True, broadcast_type=broadcast_type, attachments=flow_start_result.value.attachments,
                         broadcast_guid=broadcast_guid,
                         step_id=None if flow_start_result.value.step_id is MISSING else flow_start_result.value.step_id)
        except:
            logging.exception("Failed to parse result from message flow runner.")
