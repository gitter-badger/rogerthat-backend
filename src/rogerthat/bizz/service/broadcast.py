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

import json
import logging
from types import NoneType
from uuid import uuid4

from rogerthat.bizz.features import Features
from rogerthat.bizz.i18n import get_translator
from rogerthat.bizz.job.service_broadcast import schedule_service_broadcast
from rogerthat.bizz.job.update_friends import schedule_update_all_friends_of_service_user, send_update_friend_request
from rogerthat.bizz.messaging import sendMessage
from rogerthat.bizz.service import bump_menuGeneration_of_all_identities_and_update_friends, \
    CanNotDeleteBroadcastTypesException, InvalidBroadcastTypeException, DuplicateBroadcastTypeException
from rogerthat.bizz.service.mfd import to_xml_unicode, compress_js_flow_definition, create_json_id, \
    get_printable_id_from_b64id, parse_message_flow_definition_set_xml
from rogerthat.bizz.service.mfd.mfd_javascript import generate_js_flow
from rogerthat.bizz.service.mfd.sub import MessageFlowDefinitionSub, FormMessageSub, contentType1Sub, EndSub, \
    ResultsFlushSub, FormSub, SelectMultiWidgetSub, ChoiceSub, MessageFlowDefinitionSetSub, FlowCodeSub, \
    OutletSub, javascriptCodeTypeSub, ValueSub
from rogerthat.bizz.service.mfr import start_flow
from rogerthat.consts import MC_RESERVED_TAG_PREFIX, SCHEDULED_QUEUE
from rogerthat.dal import parent_key, put_and_invalidate_cache
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.profile import get_service_profile, get_user_profile
from rogerthat.dal.service import get_broadcast_settings_items, get_friend_serviceidentity_connection
from rogerthat.models import UserProfile, ServiceIdentity, FriendServiceIdentityConnection, Broadcast, \
    MessageFlowDesign, Message, ServiceMenuDef, ServiceTranslation, CustomMessageFlowDesign, \
    BroadcastSettingsFlowCache, App, BroadcastStatistic
from rogerthat.rpc import users
from rogerthat.rpc.service import BusinessException
from rogerthat.to.friends import UpdateFriendRequestTO
from rogerthat.to.messaging import UserMemberTO, ButtonTO
from rogerthat.to.messaging.flow import FLOW_STEP_MAPPING
from rogerthat.translations import localize
from rogerthat.utils import bizz_check, now, channel, azzert, xml_escape
from rogerthat.utils.app import get_app_user_tuple
from rogerthat.utils.channel import send_message
from rogerthat.utils.crypto import md5_hex
from rogerthat.utils.service import get_service_user_from_service_identity_user, add_slash_default, \
    remove_slash_default
from rogerthat.utils.transactions import on_trans_committed, run_in_transaction
from google.appengine.ext import db, deferred
from mcfw.properties import object_factory
from mcfw.rpc import returns, arguments


BROADCAST_ACCEPT_ID = u"accept"
BROADCAST_DECLINE_ID = u"decline"
BROADCAST_RETRY_ID = u"retry"

BROADCAST_TEST_MESSAGE_ID = u"%s.btm" % MC_RESERVED_TAG_PREFIX


class ConfirmationNeededException(BusinessException):
    pass


@returns(NoneType)
@arguments(service_user=users.User, broadcast_types=[unicode], force=bool)
def set_broadcast_types(service_user, broadcast_types, force=False):
    for bt in broadcast_types:
        if not bt:
            raise InvalidBroadcastTypeException(bt)
        if broadcast_types.count(bt) > 1:
            raise DuplicateBroadcastTypeException(bt)

    def trans():
        service_profile = get_service_profile(service_user, False)

        update_scheduled = False
        bc_settings_items = get_broadcast_settings_items(service_user, -1)
        if not broadcast_types:
            if bc_settings_items:
                if not force:
                    raise CanNotDeleteBroadcastTypesException()
                db.delete(bc_settings_items)
                bump_menuGeneration_of_all_identities_and_update_friends(service_user)
                update_scheduled = True

        service_profile.broadcastTypes = broadcast_types
        service_profile.version += 1
        service_profile.put()

        if not update_scheduled and bc_settings_items:
            schedule_update_all_friends_of_service_user(service_profile, force)

    run_in_transaction(trans)

@returns(NoneType)
@arguments(service_user=users.User, broadcast_type=unicode)
def add_broadcast_type(service_user, broadcast_type):
    def trans():
        service_profile = get_service_profile(service_user, False)
        bizz_check(broadcast_type not in service_profile.broadcastTypes,
                   u"Duplicate broadcast type: %s" % broadcast_type)

        service_profile.broadcastTypes.append(broadcast_type)
        set_broadcast_types(service_user, service_profile.broadcastTypes)

    db.run_in_transaction(trans)

@returns(NoneType)
@arguments(service_user=users.User, broadcast_type=unicode, force=bool)
def delete_broadcast_type(service_user, broadcast_type, force):
    def trans():
        service_profile = get_service_profile(service_user, False)
        if not broadcast_type in service_profile.broadcastTypes:
            return

        service_profile.broadcastTypes.remove(broadcast_type)
        set_broadcast_types(service_user, service_profile.broadcastTypes)

    db.run_in_transaction(trans)

@returns(UserProfile)
@arguments(service_user=users.User, test_user=users.User)
def add_broadcast_test_person(service_user, test_user):
    def trans():
        service_profile = get_service_profile(service_user, False)
        user_profile = get_user_profile(test_user, False)
        bizz_check(user_profile, u"No user found with e-mail '%s'" % test_user.email())
        bizz_check(not test_user in service_profile.broadcastTestPersons,
                   u"Duplicate test person: %s" % test_user.email())
        service_profile.broadcastTestPersons.append(test_user)
        service_profile.put()
        return user_profile
    xg_on = db.create_transaction_options(xg=True)
    return db.run_in_transaction_options(xg_on, trans)

@returns(NoneType)
@arguments(service_user=users.User, test_user=users.User)
def delete_broadcast_test_person(service_user, test_user):
    service_profile = get_service_profile(service_user, False)
    if not test_user in service_profile.broadcastTestPersons:
        return
    service_profile.broadcastTestPersons.remove(test_user)
    service_profile.put()

@returns(Broadcast)
@arguments(service_user=users.User, broadcast_key=unicode)
def send_broadcast(service_user, broadcast_key):
    def trans():
        broadcast = Broadcast.get(broadcast_key)
        bizz_check(broadcast, u"Broadcast not found")
        azzert(broadcast.service_user == service_user)
        service_profile = get_service_profile(service_user, False)
        mfd = MessageFlowDesign.get(broadcast.message_flow)
        bizz_check(mfd, u"Broadcast message flow not found")
        bizz_check(broadcast.type_ in service_profile.broadcastTypes, u"Unknown broadcast type: %s" % broadcast.type_)
        broadcast_guid = schedule_service_broadcast(service_user, broadcast.message_flow, broadcast.type_, broadcast.tag)
        stats = BroadcastStatistic(key=BroadcastStatistic.create_key(broadcast_guid, service_user), timestamp=now())
        stats.put()
        broadcast.sent_time = now()
        db.put([broadcast, stats])
        on_trans_committed(send_message, service_user, "rogerthat.broadcast.changes")
        return broadcast
    return db.run_in_transaction(trans)

@returns(Broadcast)
@arguments(service_user=users.User, broadcast_key=unicode, timestamp=(int, long))
def schedule_broadcast(service_user, broadcast_key, timestamp):

    bizz_check(timestamp > now(), u"Cannot schedule broadcasts in the past.")

    def trans():
        broadcast = Broadcast.get(broadcast_key)
        bizz_check(broadcast, u"Broadcast not found")
        azzert(broadcast.service_user == service_user)
        broadcast.scheduled_at = timestamp
        deferred.defer(send_broadcast, service_user, broadcast_key,
                       _transactional=True, _countdown=timestamp - now(), _queue=SCHEDULED_QUEUE)
        broadcast.put()
        return broadcast

    return db.run_in_transaction(trans)

def _check_flow_end_modules(mfd):
    # Adds a flush before every end block if no flush or send_mail is connected to this end block.
    mf_defs = parse_message_flow_definition_set_xml(mfd.xml.encode('utf-8'))

    flushes_connected_to_ends = dict()
    ends_patched = list()

    azzert(mf_defs.definition)
    for mf_def in mf_defs.definition:

        def patch_end(end_id):
            logging.info("%s. [%s] patching end reference %s", len(ends_patched), mf_def.language, get_printable_id_from_b64id(end_id))
            ends_patched.append(end_id)

            connected_flushes = flushes_connected_to_ends.get(end_id)
            if connected_flushes:
                # Reusing connected flush
                flush = flushes_connected_to_ends[end_id][0]
            else:
                # Connecting new flush to end
                flush = ResultsFlushSub(reference=end_id, id=create_json_id(mfd, "flush_", str(uuid4())))
                flushes_connected_to_ends[end_id] = [flush]
                mf_def.resultsFlush.append(flush)

            return flush.id

        flushes_connected_to_ends = dict([(end.id, list()) for end in mf_def.end])
        end_ids = flushes_connected_to_ends.keys()

        for flush in mf_def.resultsFlush:
            if flush.reference in flushes_connected_to_ends:
                flushes_connected_to_ends[flush.reference].append(flush)

        # Look for message/formMessage/code modules connected to one of the end modules
        for message in mf_def.message:
            if message.dismissReference in end_ids:
                message.dismissReference = patch_end(message.dismissReference)
            for answer in message.answer:
                if answer.reference in end_ids:
                    answer.reference = patch_end(answer.reference)
        for fm in mf_def.formMessage:
            if fm.positiveReference in end_ids:
                fm.positiveReference = patch_end(fm.positiveReference)
            if fm.negativeReference in end_ids:
                fm.negativeReference = patch_end(fm.negativeReference)
        for results_email in mf_def.resultsEmail:
            if results_email.reference in end_ids:
                results_email.reference = patch_end(results_email.reference)

    if ends_patched:
        new_xml = to_xml_unicode(mf_defs, 'messageFlowDefinitionSet', True)
        logging.info("new xml: %s" % new_xml)

        # Protection in case extra modules are added: every end_id should have len(connected_flushes) + 1 occurrences
        for end_id, connected_flushes in flushes_connected_to_ends.iteritems():
            end_id_count = new_xml.count(end_id)
            expected_count = len(connected_flushes) + 1
            azzert(expected_count == end_id_count,
                   u"Excepted %s occurrences of %s in new_xml, got %s" % (expected_count, end_id, end_id_count))

        return new_xml
    return None

def _send_broadcast_to_test_persons(broadcast):
    testers_to_find = list(broadcast.test_persons)
    si_mapped_to_testers = dict()
    for si in ServiceIdentity.all().ancestor(parent_key(broadcast.service_user)).run():
        keys = [FriendServiceIdentityConnection.createKey(u, si.user) for u in testers_to_find]
        for fsic in db.get(keys):
            if fsic:
                if not si in si_mapped_to_testers:
                    si_mapped_to_testers[si] = list()
                si_mapped_to_testers[si].append(fsic.friend)
                testers_to_find.remove(fsic.friend)
            if not testers_to_find:
                break
        if not testers_to_find:
            break
    bizz_check(not testers_to_find,
               u"Could not find a connected service identity for %s" % [x.email() for x in broadcast.test_persons])
    mfd = MessageFlowDesign.get(broadcast.message_flow)

    # Make sure all end modules are connected with a flush
    new_xml = _check_flow_end_modules(mfd)
    if new_xml:
        mfd = CustomMessageFlowDesign()
        mfd.xml = new_xml

    for si, testers in si_mapped_to_testers.iteritems():
        deferred.defer(start_flow, si.user, message_parent_key=None, flow=mfd, members=testers,
                       check_friends=False, result_callback=False,
                       tag=json.dumps({Broadcast.TAG_MC_BROADCAST: unicode(broadcast.key()),
                                       '%s.tag' % MC_RESERVED_TAG_PREFIX: broadcast.tag}),
                       _transactional=db.is_in_transaction(), broadcast_type=broadcast.type_)


@returns(Broadcast)
@arguments(service_user=users.User, name=unicode, broadcast_type=unicode, message_flow_id=unicode, tag=unicode)
def test_broadcast(service_user, name, broadcast_type, message_flow_id, tag):
    def trans():
        service_profile = get_service_profile(service_user, False)
        mfd = MessageFlowDesign.get(message_flow_id)
        bizz_check(mfd, u"Selected message flow design not found")
        bizz_check(broadcast_type in service_profile.broadcastTypes, u"Unknown broadcast type: %s" % broadcast_type)
        azzert(service_profile.broadcastTestPersons)
        broadcast = Broadcast.create(service_user)
        broadcast.name = name
        broadcast.tag = tag
        broadcast.type_ = broadcast_type
        broadcast.creation_time = now()
        broadcast.message_flow = str(mfd.key())
        broadcast.test_persons = service_profile.broadcastTestPersons
        broadcast.test_persons_statuses = [Broadcast.TEST_PERSON_STATUS_UNDECIDED] * len(broadcast.test_persons)
        broadcast.put()
        _send_broadcast_to_test_persons(broadcast)
        return broadcast
    xg_on = db.create_transaction_options(xg=True)
    return db.run_in_transaction_options(xg_on, trans)


@returns(NoneType)
@arguments(test_person=users.User, parent_message_key=unicode, service_identity_user=users.User, broadcast_key=unicode)
def flow_test_person_ended(test_person, parent_message_key, service_identity_user, broadcast_key):
    members = [UserMemberTO(test_person)]
    timeout = 0

    accept_btn = ButtonTO()
    accept_btn.action = None
    accept_btn.caption = u"Approve broadcast"
    accept_btn.id = BROADCAST_ACCEPT_ID
    accept_btn.ui_flags = 0

    decline_btn = ButtonTO()
    decline_btn.action = None
    decline_btn.caption = u"Decline broadcast"
    decline_btn.id = BROADCAST_DECLINE_ID
    decline_btn.ui_flags = 0

    retry_btn = ButtonTO()
    retry_btn.action = None
    retry_btn.caption = u"Resend broadcast"
    retry_btn.id = BROADCAST_RETRY_ID
    retry_btn.ui_flags = 1

    msg = u"You have reached the end of the broadcast message flow.\n\nDo you want to approve or decline the broadcast, or do you wish to receive it again?"

    message = sendMessage(service_identity_user, members, Message.FLAG_AUTO_LOCK, timeout,
                          parent_message_key, msg, answers=[accept_btn, decline_btn, retry_btn], sender_answer=None,
                          branding=None, tag=BROADCAST_TEST_MESSAGE_ID, allow_reserved_tag=True)

    message.broadcast_key = broadcast_key
    message.broadcast_test_person = test_person
    message.put()


@returns(NoneType)
@arguments(message=Message)
def ack_test_broadcast(message):
    test_person = message.broadcast_test_person
    logging.info(u"%s answered broadcast flow" % test_person.email())

    btn_index = message.memberStatusses[message.members.index(test_person)].button_index
    if btn_index == message.buttons[BROADCAST_RETRY_ID].index:
        flow = Broadcast.get(message.broadcast_key).message_flow
        start_flow(add_slash_default(message.sender), message_parent_key=message.pkey, flow=flow, members=[test_person],
                   check_friends=False, result_callback=False,
                   tag=json.dumps({Broadcast.TAG_MC_BROADCAST: message.broadcast_key}), broadcast_type=message.broadcast_type)
    else:
        accepted = btn_index == message.buttons[BROADCAST_ACCEPT_ID].index

        def txn_update_tester_status():
            broadcast = Broadcast.get(message.broadcast_key)
            if broadcast:
                status = Broadcast.TEST_PERSON_STATUS_ACCEPTED if accepted else Broadcast.TEST_PERSON_STATUS_DECLINED
                broadcast.set_status(test_person, status)
                broadcast.put()
            return bool(broadcast)

        if db.run_in_transaction(txn_update_tester_status):
            channel.send_message(get_service_user_from_service_identity_user(message.sender),
                                 u'rogerthat.broadcast.changes', broadcast_key=message.broadcast_key)

@returns(NoneType)
@arguments(service_user=users.User, broadcast_key=unicode)
def delete_broadcast(service_user, broadcast_key):
    broadcast = Broadcast.get(broadcast_key)
    azzert(broadcast.service_user == service_user)
    logging.debug('Deleting Broadcast %s', db.to_dict(broadcast))
    db.delete(broadcast)

@returns(MessageFlowDefinitionSetSub)
@arguments(service_identity_user=users.User, user_profile=UserProfile)
def generate_broadcast_settings_flow_def(service_identity_user, user_profile):
    service_user = get_service_user_from_service_identity_user(service_identity_user)
    service_profile = get_service_profile(service_user)
    if not service_profile.broadcastTypes:
        logging.debug("%s has no broadcast types", service_user)
        return None

    friend_user = user_profile.user
    _, app_id = get_app_user_tuple(friend_user)
    if app_id == App.APP_ID_OSA_LOYALTY:
        logging.debug("No broadcast flow needed for osa loyalty app")
        return None

    broadcast_branding = service_profile.broadcastBranding
    friend_service_identity_connection = get_friend_serviceidentity_connection(friend_user, service_identity_user)
    if friend_service_identity_connection is None:
        logging.warn("No friend connection between %s and %s", friend_user, service_identity_user)
        return None
    if friend_service_identity_connection.disabled_broadcast_types is None:
        friend_service_identity_connection.disabled_broadcast_types = list()
    if friend_service_identity_connection.enabled_broadcast_types is None:
        friend_service_identity_connection.enabled_broadcast_types = list()
    enabled_broadcast_types = friend_service_identity_connection.enabled_broadcast_types

    translator = get_translator(service_user, ServiceTranslation.BROADCAST_TYPES, language=user_profile.language)
    bt_translate = lambda bt: translator.translate(ServiceTranslation.BROADCAST_TYPE, bt, user_profile.language)

    end = EndSub(id="end_1", waitForFollowUpMessage=False)

    flush = ResultsFlushSub(id="flush_1", reference=end.id)

    w = SelectMultiWidgetSub()
    w.set_extensiontype_('SelectMultiWidget')
    w.value = [ ValueSub(value=bt) for bt in enabled_broadcast_types ]
    w.choice = [ ChoiceSub(label=bt_translate(bt), value=bt) for bt in service_profile.broadcastTypes ]
# Sorting of broadcast types screws up logic for broadcast_types that should stick together
#    w.choice.sort(key=lambda c: c.label)

    # set broadcast types via flow code
    form = FormSub()
    form.positiveButtonCaption = localize(user_profile.language, u"Save")
    form.positiveButtonConfirmation = ""
    form.negativeButtonCaption = localize(user_profile.language, u"Cancel")
    form.negativeButtonConfirmation = ""
    form.widget = w

    js_code_get_broadcast_types_sub = javascriptCodeTypeSub()
    js_code_get_broadcast_types_sub.valueOf_ = '''function run(rogerthat, messageFlowRun){
    var appVersion = rogerthat.system.appVersion.split(".");
    var supported = false;
    if(rogerthat.system.os === 'android'){
        if (parseInt(appVersion[0]) > 1 || parseInt(appVersion[1]) > %(android_major)s || parseInt(appVersion[2]) >= %(android_minor)s){
            supported = true;
        }
    }else if(rogerthat.system.os === 'ios'){
        if (parseInt(appVersion[0]) > 1 || parseInt(appVersion[1]) > %(ios_major)s || parseInt(appVersion[2]) >= %(ios_minor)s){
            supported = true;
        }
    }
    var nextStepResult = {};
    if(supported){
        var selectedBroadcastTypes = messageFlowRun.steps[messageFlowRun.steps.length - 1].form_result.result.values;
        var availableBroadcastTypes = rogerthat.service.data.__rt__broadcastTypes;
        var disabledBroadcastTypes = [];
        for(var i = 0; i < availableBroadcastTypes.length; i++){
            if(selectedBroadcastTypes.indexOf(availableBroadcastTypes[i]) === -1){
                disabledBroadcastTypes.push(availableBroadcastTypes[i]);
            }
        }
        rogerthat.user.data.__rt__disabledBroadcastTypes = disabledBroadcastTypes;
        rogerthat.user.put();
        nextStepResult.outlet = "%(end_id)s";
    }else{
        nextStepResult.outlet = "%(flush_id)s";
    }
    return nextStepResult;
}
''' % dict(end_id=end.id,
           flush_id=flush.id,
           android_major=Features.BROADCAST_VIA_FLOW_CODE.android.major,  # @UndefinedVariable
           android_minor=Features.BROADCAST_VIA_FLOW_CODE.android.minor,  # @UndefinedVariable
           ios_major=Features.BROADCAST_VIA_FLOW_CODE.ios.major,  # @UndefinedVariable
           ios_minor=Features.BROADCAST_VIA_FLOW_CODE.ios.minor)  # @UndefinedVariable

    flow_code_put_user_data = FlowCodeSub(id='flow_code_put_user_data',
                                          exceptionReference=flush.id,
                                          javascriptCode=js_code_get_broadcast_types_sub)  # use old method on failure
    flow_code_put_user_data.add_outlet(OutletSub(reference=end.id, name=end.id, value=end.id))

    fm = FormMessageSub(id="message_1")
    fm.brandingKey = broadcast_branding
    fm.vibrate = False
    fm.alertType = 'SILENT'
    fm.alertIntervalType = 'NONE'
    fm.autoLock = True
    fm.content = contentType1Sub()
    fm.content.valueOf_ = xml_escape(localize(user_profile.language, u"Which type of broadcasts do you wish to receive?")).strip()
    fm.form = form
    fm.positiveReference = flow_code_put_user_data.id
    fm.negativeReference = end.id

    js_code_fill_broadcast_types = '''function run(rogerthat, messageFlowRun){
    var availableBroadcastTypes = rogerthat.service.data.__rt__broadcastTypes;
    var disabledBroadcastTypes = rogerthat.user.data.__rt__disabledBroadcastTypes;
    var enabledBroadcastTypes = [];
    for(var i = 0; i < availableBroadcastTypes.length; i++){
        if(disabledBroadcastTypes.indexOf(availableBroadcastTypes[i]) === -1){
            enabledBroadcastTypes.push(availableBroadcastTypes[i]);
        }
    }
    return {
        defaultValue: enabledBroadcastTypes,
        outlet: "flow_code_broadcast_types_outlet"
    };
}'''
    flow_code_user_data_sub = javascriptCodeTypeSub()
    flow_code_user_data_sub.valueOf_ = js_code_fill_broadcast_types
    flow_code = FlowCodeSub(id="flow_code_fill_broadcast_types", exceptionReference=fm.id,
                            javascriptCode=flow_code_user_data_sub)
    flow_code.add_outlet(OutletSub(reference=fm.id, name='flow_code_broadcast_types_outlet',
                                   value='flow_code_broadcast_types_outlet'))

    mfd = MessageFlowDefinitionSub()
    mfd.name = ServiceMenuDef.TAG_MC_BROADCAST_SETTINGS
    mfd.language = user_profile.language
    mfd.startReference = flow_code.id
    mfd.add_flowCode(flow_code)
    mfd.add_formMessage(fm)
    mfd.add_flowCode(flow_code_put_user_data)
    mfd.add_end(end)
    mfd.add_resultsFlush(flush)

    mfds = MessageFlowDefinitionSetSub()
    mfds.add_definition(mfd)

    return mfds

@returns(unicode)
@arguments(service_identity_user=users.User, app_user=users.User)
def generate_broadcast_settings_static_flow(service_identity_user, app_user):

    cache_key = BroadcastSettingsFlowCache.create_key(app_user, service_identity_user)
    cache = db.get(cache_key)
    if cache:
        logging.info("Returning BroadcastSettingsFlowCache from cache")
        return cache.static_flow

    user_profile = get_user_profile(app_user)

    mfds = generate_broadcast_settings_flow_def(service_identity_user, user_profile)
    if mfds is None:
        return None

    xml = to_xml_unicode(mfds, 'messageFlowDefinitionSet', True)

    js_flow_definition_dict = generate_js_flow(get_service_user_from_service_identity_user(service_identity_user), xml)
    flow_definition = js_flow_definition_dict[user_profile.language][0]

    static_flow = compress_js_flow_definition(flow_definition)
    BroadcastSettingsFlowCache(key=cache_key, static_flow=static_flow, timestamp=now()).put()
    return static_flow

@returns(unicode)
@arguments(service_identity_user=users.User, app_user=users.User)
def get_broadcast_settings_static_flow_hash(service_identity_user, app_user):
    static_flow = generate_broadcast_settings_static_flow(service_identity_user, app_user)
    if static_flow:
        return unicode(md5_hex(static_flow))
    return None

# This method it deprecated since we used serviceData, userData and flowCode to update the disabled broadcast types
@returns(NoneType)
@arguments(service_identity_user=users.User, friend_user=users.User, steps=[object_factory("step_type", FLOW_STEP_MAPPING)])
def process_broadcast_settings_flow_result(service_identity_user, friend_user, steps):
    azzert(len(steps) == 1)
    _, app_id = get_app_user_tuple(friend_user)
    azzert(app_id != App.APP_ID_OSA_LOYALTY)
    enabled_broadcast_types = steps[0].form_result.result.values

    service_profile = get_service_profile(get_service_user_from_service_identity_user(service_identity_user))

    def trans():
        friend_service_identity_connection = get_friend_serviceidentity_connection(friend_user, service_identity_user)
        if not friend_service_identity_connection:
            logging.warning("Cannot store notification settings of non friend user!")
            return

        for attr in ('disabled_broadcast_types', 'enabled_broadcast_types'):
            if getattr(friend_service_identity_connection, attr) is None:
                setattr(friend_service_identity_connection, attr, list())

        # Prevent loosing previously disabled broadcast types
        friend_service_identity_connection.disabled_broadcast_types = list((set(friend_service_identity_connection.disabled_broadcast_types) | set(service_profile.broadcastTypes)) - set(enabled_broadcast_types))
        friend_service_identity_connection.enabled_broadcast_types = enabled_broadcast_types

        friend_map = get_friends_map(friend_user)
        friend_detail = friend_map.friendDetails[remove_slash_default(service_identity_user).email()]
        friend_detail.relationVersion += 1
        db.delete_async(BroadcastSettingsFlowCache.create_key(friend_user, service_identity_user))

        put_and_invalidate_cache(friend_service_identity_connection, friend_map)

        deferred.defer(send_update_friend_request, friend_user, service_identity_user,
                       UpdateFriendRequestTO.STATUS_MODIFIED, bump_friend_map_generation=True,
                       _transactional=True, _countdown=1)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)
