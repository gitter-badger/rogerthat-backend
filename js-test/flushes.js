JsMfrFlushTest = TestCase("JsMfrFlushTest");

JsMfrFlushTest.prototype.testFlushPlusMessage = function() {
    var state = {
        member : 'john.doe@foo.com',
        run : null
    };

    var userInput1 = {
        func : API_PRESS_MENU_ICON,
        request : {
            context : 'context',
            coords : [1, 0, 0],
            generation : 1,
            service : 's1@foo.com'
        }
    };

    var r1 = transition('1.0.118.i', state, userInput1);

    var userInput2 = {
            func: 'com.mobicage.api.messaging.ackMessage',
            request : {
                message_key : r1.newstate.run.steps[0].message_key,
                parent_message_key : r1.newstate.run.parent_message_key,
                button_id : null
            }
        };

    var r2 = transition('1.0.118.i', r1.newstate, userInput2);

    var fmrRequest;
    for (var i in r2.server_actions) {
        var apiCall = r2.server_actions[i];
        if (apiCall.f == API_FLOW_MEMBER_RESULT) {
            fmrRequest = apiCall.a.request;
            break;
        }
    }

    console.log(fmrRequest);
    
    assertSame(1, fmrRequest.run.steps.length);
};

JsMfrFlushTest.prototype.setUp = function () {
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
            reference: 'message_b'
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
                            message_type: MESSAGE_TYPE_MESSAGE,
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
            },
            dismiss_reference: 'end_1',
            message_type: MESSAGE_TYPE_MESSAGE,
            getAction: function (parent_key, key, sender, member_email, context, timestamp) {
                return {
                    func: 'com.mobicage.capi.messaging.newMessage',
                    request: {
                        message: {
                            alert_flags: 2,
                            branding: null,
                            buttons: [],
                            context: context,
                            dismiss_button_ui_flags: getUIFlagsByButtonReferenceId('end_1'),
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
                            message: 'B',
                            message_type: MESSAGE_TYPE_MESSAGE,
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
    };
};
