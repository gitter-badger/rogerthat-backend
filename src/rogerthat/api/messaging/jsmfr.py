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

from rogerthat.dal.mfd import get_message_flow_run_record
from rogerthat.models import Message, ServiceMenuDefTagMap, MessageFlowRunRecord
from rogerthat.rpc import users
from rogerthat.rpc.rpc import expose
from rogerthat.to.messaging import UserMemberTO
from rogerthat.to.messaging.jsmfr import MessageFlowMemberResultResponseTO, MessageFlowMemberResultRequestTO, \
    MessageFlowFinishedResponseTO, MessageFlowFinishedRequestTO, NewFlowMessageResponseTO, NewFlowMessageRequestTO, \
    MessageFlowErrorResponseTO, MessageFlowErrorRequestTO, FlowStartedResponseTO, FlowStartedRequestTO
from rogerthat.utils.app import get_app_id_from_app_user, create_app_user
from rogerthat.utils.service import add_slash_default, get_service_identity_tuple, create_service_identity_user, \
    get_service_user_from_service_identity_user
from mcfw.consts import MISSING
from mcfw.rpc import returns, arguments


@expose(('api',))
@returns(MessageFlowMemberResultResponseTO)
@arguments(request=MessageFlowMemberResultRequestTO)
def messageFlowMemberResult(request):
    from rogerthat.bizz.messaging import send_message_flow_member_result, send_message_flow_results_email
    from rogerthat.dal import parent_key
    from rogerthat.dal.service import get_service_interaction_def
    app_user = users.get_current_user()
    run = request.run
    sender = add_slash_default(users.User(run.sender))
    svc_user, service_identity = get_service_identity_tuple(sender)
    tag = None
    if run.hashed_tag != MISSING:
        mapped_tag = ServiceMenuDefTagMap.get_by_key_name(run.hashed_tag, parent=parent_key(svc_user))
        if mapped_tag:
            tag = mapped_tag.tag
    elif run.service_action != MISSING:
        if "?" in run.service_action:
            # strip off the query parameters added by shortner.py
            run.service_action = run.service_action[:run.service_action.index("?")]
        sid = get_service_interaction_def(svc_user, int(run.service_action))
        if sid:
            tag = sid.tag
    elif run.message_flow_run_id:
        message_flow_run = MessageFlowRunRecord.get_by_key_name(MessageFlowRunRecord.createKeyName(svc_user, run.message_flow_run_id))
        if message_flow_run:
            tag = message_flow_run.tag

    if request.end_id:
        from rogerthat.bizz.messaging import check_test_flow_broadcast_ended
        check_test_flow_broadcast_ended(app_user, create_service_identity_user(svc_user, service_identity),
                                        run.parent_message_key, tag)

    if request.results_email and request.results_email is not MISSING:
        send_message_flow_results_email(request.message_flow_name, request.emails, request.email_admins,
                                        run.steps, app_user, service_identity, svc_user, run.parent_message_key, tag)
    else:
        send_message_flow_member_result(svc_user, service_identity, run.message_flow_run_id, run.parent_message_key,
                                        app_user, run.steps, request.end_id, request.flush_id,
                                        tag=tag)

@expose(('api',))
@returns(MessageFlowFinishedResponseTO)
@arguments(request=MessageFlowFinishedRequestTO)
def messageFlowFinished(request):
    pass

@expose(('api',))
@returns(MessageFlowErrorResponseTO)
@arguments(request=MessageFlowErrorRequestTO)
def messageFlowError(request):
    from rogerthat.bizz.system import logErrorBizz
    request.errorMessage = "%s\njs_command: %s\njs_stack_trace: %s" \
            % (request.errorMessage, request.jsCommand, request.stackTrace)

    logErrorBizz(request, users.get_current_user())

@expose(('api',))
@returns(NewFlowMessageResponseTO)
@arguments(request=NewFlowMessageRequestTO)
def newFlowMessage(request):
    app_user = users.get_current_user()
    sender = add_slash_default(users.User(request.message.sender))
    message = request.message
    tag = sender_answer = step_id = None
    if MISSING not in (request.message_flow_run_id, request.step_id):
        step_id = request.step_id
        mfrr = get_message_flow_run_record(get_service_user_from_service_identity_user(sender),
                                           request.message_flow_run_id)
        if mfrr:
            tag = mfrr.tag

    is_mfr = False
    alert_flags = Message.ALERT_FLAG_SILENT
    flags = message.flags | Message.FLAG_LOCKED
    if message.message_type == Message.TYPE_FORM_MESSAGE:
        from rogerthat.bizz.messaging import sendForm

        auto_complete_func = request.form_result and request.form_result.result \
                and getattr(request.form_result.result, 'auto_complete', None)
        if auto_complete_func:
            auto_complete_func()

        auto_complete_func = getattr(message.form.widget, 'auto_complete', None)
        if auto_complete_func:
            auto_complete_func()

        message.member.member = create_app_user(users.User(message.member.member),
                                                get_app_id_from_app_user(app_user)).email()
        sendForm(sender, message.parent_key, app_user, message.message, message.form, flags,
                 message.branding, tag, alert_flags, message.context, message.key, is_mfr,
                 forced_member_status=message.member, forced_form_result=request.form_result, step_id=step_id,
                 allow_reserved_tag=True)
    else:
        from rogerthat.bizz.messaging import sendMessage
        message.members[0].member = create_app_user(users.User(message.members[0].member),
                                                    get_app_id_from_app_user(app_user)).email()
        sendMessage(sender, [UserMemberTO(app_user, alert_flags)], flags, message.timeout, message.parent_key,
                    message.message, message.buttons, sender_answer, message.branding, tag,
                    message.dismiss_button_ui_flags, message.context, message.key, is_mfr,
                    forced_member_status=message.members[0], step_id=step_id, allow_reserved_tag=True)


@expose(('api',))
@returns(FlowStartedResponseTO)
@arguments(request=FlowStartedRequestTO)
def flowStarted(request):
    pass
