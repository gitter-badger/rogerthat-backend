JsMfrTest = TestCase("JsMfrTest");

JsMfrTest.prototype.testStartStep = function() {
    var state = {
        member : 'john.doe@foo.com',
        run : null
    };

    var userInput = {
        func : API_PRESS_MENU_ICON,
        request : {
            context : 'context',
            coords : [1, 0, 0],
            generation : 1,
            service : 's1@foo.com'
        }
    };

    var r = transition('1.0.118.i', state, userInput);

    assertNotNull(r.local_action);
    assertSame('com.mobicage.capi.messaging.newMessage', r.local_actions[0].f);

    var parentMessage = r.local_actions[0].a.request.message;
    assertSame('A', parentMessage.message);
    assertSame(256, (parentMessage.flags & 256));
    assertSame(0, parentMessage.dismiss_button_ui_flags);
    assertSame('john.doe@foo.com', parentMessage.members[0].member);
    assertSame('s1@foo.com', parentMessage.sender);
    assertSame('context', parentMessage.context);

    assertSame(1, r.newstate.run.steps.length);
    var firstStep = r.newstate.run.steps[0];
    assertSame(flowDefinition.start, firstStep.step_id);
    assertNotNull(firstStep.message_key);
};

JsMfrTest.prototype.testStartServiceAction = function() {
    var state = {
        member : 'john.doe@foo.com',
        run : null
    };

    var userInput = {
        func : API_START_SVC_ACTION,
        request : {
            context : 'context',
            email : 's1@foo.com',
            action : 'action',
            static_flow_hash : 'static_flow_hash'
        }
    };

    var r = transition('1.0.118.i', state, userInput);

    assertNotNull(r.local_action);
    assertSame('com.mobicage.capi.messaging.newMessage', r.local_actions[0].f);

    var parentMessage = r.local_actions[0].a.request.message;
    assertSame('A', parentMessage.message);
    assertSame(256, (parentMessage.flags & 256));
    assertSame(0, parentMessage.dismiss_button_ui_flags);
    assertSame('john.doe@foo.com', parentMessage.members[0].member);
    assertSame('s1@foo.com', parentMessage.sender);
    assertSame('context', parentMessage.context);

    assertSame(1, r.newstate.run.steps.length);
    var firstStep = r.newstate.run.steps[0];
    assertSame(flowDefinition.start, firstStep.step_id);
    assertNotNull(firstStep.message_key);
};

JsMfrTest.prototype.testNextMessage = function() {
    var parent_key = GUID();

    var state = {
        member : 'john.doe@foo.com',
        run : {
            parent_message_key : parent_key,
            sender : 's1@foo.com',
            message_flow_run_id : GUID(),
            steps : [ {
                message_key : parent_key,
                step_id : 'message_a'
            } ]
        }
    };

    var userInput = {
        func: 'com.mobicage.api.messaging.ackMessage',
        request : {
            message_key : parent_key,
            parent_message_key : null,
            button_id : 'button_a',
            timestamp : now()
        }
    };

    var r = transition('1.0.118.i', state, userInput);

    assertSame(1, r.server_actions.length);
    assertSame('com.mobicage.api.messaging.jsmfr.newFlowMessage', r.server_actions[0].f);
    assertNull(r.server_actions[0].a.request.message.parent_key);
    assertSame(parent_key, r.server_actions[0].a.request.message.key);
    assertSame('john.doe@foo.com', r.server_actions[0].a.request.message.members[0].member);

    assertNotNull(r.local_action);
    assertSame('com.mobicage.capi.messaging.newSingleSliderForm', r.local_actions[0].f);
    assertSame(1, r.server_actions.length);
    
    var singleSliderMsg = r.local_actions[0].a.request.form_message;
    assertSame("single_slider", singleSliderMsg.form.type);
    assertSame(256, (singleSliderMsg.flags & 256));
    assertSame(0, singleSliderMsg.form.positive_button_ui_flags);
    assertSame(0, singleSliderMsg.form.negative_button_ui_flags);

    assertSame(2, r.newstate.run.steps.length);
    var firstStep = r.newstate.run.steps[0];
    var secondStep = r.newstate.run.steps[1];
    assertSame('button_a', firstStep.answer_id);
    assertSame('message_b', secondStep.step_id);
    assertNotNull(secondStep.message_key);
};

JsMfrTest.prototype.testEndViaMessage1 = function() {
    var parent_key = GUID();
    var message_flow_run_id = GUID();

    var state = {
        member : 'john.doe@foo.com',
        run : {
            parent_message_key : parent_key,
            sender : 's1@foo.com',
            message_flow_run_id : message_flow_run_id,
            steps : [ {
                message_key : parent_key,
                step_id : 'message_a',
                message : 'A',
                button : 'Roger that!',
                answer_id : null
            } ]
        }
    };

    var userInput = {
        func: 'com.mobicage.api.messaging.ackMessage',
        request : {
            message_key : parent_key,
            parent_message_key : null,
            button_id : null,
            timestamp : now()
        }
    };

    var r = transition('1.0.118.i', state, userInput);

//    assertSame('end_1', r.newstate.end_reference);
    assertSame(1, r.newstate.run.steps.length);
    assertSame(null, r.newstate.run.steps[0].answer_id);

    assertSame(3, r.server_actions.length); // newFlowMessage + flowEnded + flowMemberResult

    var fmrRequest, ffRequest, nfmRequest;
    for (var i in r.server_actions) {
        var apiCall = r.server_actions[i];
        if (apiCall.f == API_FLOW_MEMBER_RESULT)
            fmrRequest = apiCall.a.request;
        else if (apiCall.f == API_FLOW_FINISHED)
            ffRequest = apiCall.a.request;
        else if (apiCall.f == API_NEW_FLOW_MESSAGE)
            nfmRequest = apiCall.a.request;
        else
            fail('Unexpected action: ' + apiCall.func);
    }
    assertNotSame(undefined, fmrRequest);
    assertNotSame(undefined, ffRequest);
    assertNotSame(undefined, nfmRequest);

    assertSame(1, fmrRequest.run.steps.length);
    assertSame('end_1', fmrRequest.end_id);
    assertSame('flush_1', fmrRequest.flush_id);
    assertSame(message_flow_run_id, fmrRequest.run.message_flow_run_id);
    assertSame(parent_key, fmrRequest.run.parent_message_key);
    assertNull(fmrRequest.run.steps[0].answer_id);
    assertSame(ROGERTHAT_BUTTON_CAPTION, fmrRequest.run.steps[0].button);
    assertSame('A', fmrRequest.run.steps[0].message);
    assertSame('message_a', fmrRequest.run.steps[0].step_id);
};

JsMfrTest.prototype.testEndViaMessage2 = function() {
    var parent_key = GUID();
    var msg2_key = GUID();
    var message_flow_run_id = GUID();

    var state = {
        member : 'john.doe@foo.com',
        run : {
            parent_message_key : parent_key,
            sender : 's1@foo.com',
            message_flow_run_id : message_flow_run_id,
            steps : [ {
                message_key : parent_key,
                step_id : 'message_a',
                answer_id : 'button_a',
                message : 'A',
                button : 'Show single_slider'
            }, {
                message_key : msg2_key,
                step_id : 'message_b',
                message : 'B',
                button : 'Submit'
            } ]
        }
    };

    var userInput = {
        func: 'com.mobicage.api.messaging.submitSingleSliderForm',
        request : {
            message_key : msg2_key,
            parent_message_key : parent_key,
            button_id : FORM_POSITIVE,
            result : {
                value : 6
            },
            timestamp : now()
        }
    };

    var r = transition('1.0.118.i', state, userInput);

//    assertSame('end_1', r.newstate.end_reference);
    assertSame(2, r.newstate.run.steps.length);
    assertSame(FORM_POSITIVE, r.newstate.run.steps[1].answer_id);
    assertSame(6, r.newstate.run.steps[1].form_result.result.value);

    assertSame(3, r.server_actions.length); // newFlowMessage + flowEnded + flowMemberResult

    var fmrRequest, ffRequest, nfmRequest;
    for (var i in r.server_actions) {
        var apiCall = r.server_actions[i];
        if (apiCall.f == API_FLOW_MEMBER_RESULT)
            fmrRequest = apiCall.a.request;
        else if (apiCall.f == API_FLOW_FINISHED)
            ffRequest = apiCall.a.request;
        else if (apiCall.f == API_NEW_FLOW_MESSAGE)
            nfmRequest = apiCall.a.request;
        else
            fail('Unexpected action: ' + apiCall.func);
    }
    assertNotSame(undefined, fmrRequest);
    assertNotSame(undefined, ffRequest);
    assertNotSame(undefined, nfmRequest);

    assertSame(2, fmrRequest.run.steps.length);
    assertSame('end_1', fmrRequest.end_id);
    assertSame('flush_1', fmrRequest.flush_id);
    assertSame(message_flow_run_id, fmrRequest.run.message_flow_run_id);
    assertSame(parent_key, fmrRequest.run.parent_message_key);

    var step1 = fmrRequest.run.steps[0];
    assertSame('button_a', step1.answer_id);
    assertSame('Show single_slider', step1.button);
    assertSame('A', step1.message);
    assertSame('message_a', step1.step_id);
    
    var step2 = fmrRequest.run.steps[1];
    assertSame(FORM_POSITIVE, step2.answer_id);
    assertSame('Submit', step2.button);
    assertSame('B', step2.message);
    assertSame('message_b', step2.step_id);
};

JsMfrTest.prototype.setUp = function () {
    flowDefinition = {
        name: 'A',
        lang: 'en',
        start: 'message_a',
        "end_1": {
            step_type: STEP_TYPE_END,
            id: 'end_1',
            wff: false
        },
        "flush_1": {
            step_type: STEP_TYPE_FLUSH,
            id: 'flush_1',
            reference: 'end_1'
        },
        "message_a": {
            step_type: STEP_TYPE_MESSAGE,
            id: 'message_a',
            button_references: {
                'button_a': 'message_b',
            },
            dismiss_reference: 'flush_1',
            message_type: MESSAGE_TYPE_MESSAGE,
            getAction: function (parent_key, key, sender, member_email, context, timestamp) {
                return {
                    func: 'com.mobicage.capi.messaging.newMessage',
                    request: {
                        message: {
                            alert_flags: 2,
                            branding: null,
                            buttons: [{
                                id: 'button_a',
                                action: null,
                                caption: 'Show single_slider',
                                ui_flags: getUIFlagsByButtonReferenceId('message_b')
                            }],
                            context: context,
                            dismiss_button_ui_flags: getUIFlagsByButtonReferenceId('flush_1'),
                            flags: 1 | 64 | 256,
                            key: key,
                            members: [{
                                acked_timestamp: 0,
                                button_id: null,
                                custom_reply: null,
                                member: member_email,
                                received_timestamp: 0,
                                status: 0
                            }],
                            message: 'A',
                            message_type: 1,
                            parent_key: parent_key,
                            sender: sender,
                            threadTimestamp: 0,
                            thread_size: 0,
                            timeout: 0,
                            timestamp: timestamp
                        }
                    }
                }
            }
        },
        "message_b": {
            step_type: STEP_TYPE_MESSAGE,
            id: 'message_b',
            button_references: {
                positive: 'flush_1',
                negative: 'flush_1'
            },
            message_type: MESSAGE_TYPE_FORM,
            getAction: function (parent_key, key, sender, member_email, context, timestamp) {
                return {
                    func: 'com.mobicage.capi.messaging.newSingleSliderForm',
                    request: {
                        form_message: {
                            alert_flags: 2,
                            branding: null,
                            context: context,
                            flags: 1 | 64 | 256,
                            form: {
                                positive_button: 'Submit',
                                positive_confirmation: null,
                                javascript_validation: null,
                                positive_button_ui_flags: getUIFlagsByButtonReferenceId('flush_1'),
                                negative_button: 'Abort',
                                negative_confirmation: null,
                                negative_button_ui_flags: getUIFlagsByButtonReferenceId('flush_1'),
                                type: "single_slider",
                                widget: {
                                    max: 9,
                                    min: 0,
                                    precision: 1,
                                    step: 1,
                                    unit: null,
                                    value: 5
                                }
                            },
                            key: key,
                            member: {
                                acked_timestamp: 0,
                                button_id: null,
                                custom_reply: null,
                                member: member_email,
                                received_timestamp: 0,
                                status: 0
                            },
                            message: 'B',
                            message_type: 2,
                            parent_key: parent_key,
                            sender: sender,
                            threadTimestamp: 0,
                            thread_size: 0,
                            timestamp: timestamp
                        }
                    }
                }
            }
        },
    };
};
