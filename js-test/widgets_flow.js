JsMfrWidgetsTest = TestCase("JsMfrWidgetsTest");

JsMfrWidgetsTest.prototype.testStartStep = function() {
    var state = {
        member : 'john.doe@foo.com',
        run : null
    };

    var userInput = {
        func : API_PRESS_MENU_ICON,
        request : {
            context : 'context',
            service : 's1@foo.com',
            coords : [1, 0, 0],
            generation : 1
        }
    };
    var r = transition('1.0.118.i', state, userInput);

    assertNotNull(r.local_actions);
    assertSame('com.mobicage.capi.messaging.newMessage', r.local_actions[0].f);

    var parentMessage = r.local_actions[0].a.request.message;
    assertSame('a_1', parentMessage.message);
    assertSame(256, (parentMessage.flags & 256));
    assertSame(1, parentMessage.dismiss_button_ui_flags);
    assertSame('john.doe@foo.com', parentMessage.members[0].member);
    assertSame('s1@foo.com', parentMessage.sender);

    assertSame(1, r.newstate.run.steps.length);
    var firstStep = r.newstate.run.steps[0];
    assertSame(flowDefinition.start, firstStep.step_id);
    assertNotNull(firstStep.message_key);
};

JsMfrWidgetsTest.prototype.test2ndStep = function () {
    var parent_key = GUID();
    var state = {
        member : 'john.doe@foo.com',
        run : {
            sender : 's1@foo.com',
            message_flow_run_id: GUID(),
            steps : [ {
                message_key : parent_key,
                step_id : 'base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9hXzEifQ=='
            } ]
        }
    };

    var userInput = {
       func: 'com.mobicage.api.ackMessage',
       request : {
           message_key : parent_key,
           parent_message_key : null,
           button_id : null,
           timestamp : now()
       }
    };

    var r = transition('1.0.118.i', state, userInput);

    assertNotNull(r.local_actions);
    assertSame('com.mobicage.capi.messaging.newTextLineForm', r.local_actions[0].f);

    assertSame(null, r.newstate.run.steps[0].answer_id);
};

JsMfrWidgetsTest.prototype.testFullRun = function () {
    var parent_key = GUID();
    var reply1_key = GUID();
    var message_flow_run_id = GUID();
    var state = {
        member : 'john.doe@foo.com',
        run : {
            parent_message_key : parent_key,
            sender : 's1@foo.com',
            message_flow_run_id : message_flow_run_id,
            steps : [ {
                message_key : parent_key,
                step_id : 'base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9hXzEifQ=='
            }, {
                message_key : reply1_key,
                step_id : 'base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgMCJ9'
            } ]
        }
    };

    var userInput1 = {
       func: 'com.mobicage.api.submitTextLineForm',
       request : {
           message_key : reply1_key,
           parent_message_key : parent_key,
           button_id : FORM_POSITIVE,
           result : {
               type : 'unicode_result',
               value : 'text line'
           },
           timestamp : now()
       }
    };

    var r1 = transition('1.0.118.i', state, userInput1);

    assertNotNull(1, r1.local_actions);
    assertSame('com.mobicage.capi.messaging.newTextBlockForm', r1.local_actions[0].f);

    assertSame(FORM_POSITIVE, r1.newstate.run.steps[1].answer_id);
    assertSame('text line', r1.newstate.run.steps[1].form_result.result.value);
    assertSame('text line', r1.newstate.run.steps[1].display_value);
    assertSame(userInput1.request.timestamp, r1.newstate.run.steps[1].acknowledged_timestamp);

    var reply2_key = r1.local_actions[0].a.request.form_message.key;
    var userInput2 = {
        func: 'com.mobicage.api.submitTextLineForm',
        request : {
            message_key : reply2_key,
            parent_message_key : parent_key,
            button_id : FORM_NEGATIVE,
            result : null,
            timestamp : now()
        }
    };

    var r2 = transition('1.0.118.i', state, userInput2);

    assertSame(FORM_NEGATIVE, r2.newstate.run.steps[2].answer_id);
    assertNull(r2.newstate.run.steps[2].form_result.result);
    assertNull(r2.newstate.run.steps[2].display_value);

    var reply3_key = r2.local_actions[0].a.request.form_message.key;
    var userInput3 = {
        func: 'com.mobicage.api.submitAutoCompleteForm',
        request : {
            message_key : reply3_key,
            parent_message_key : parent_key,
            button_id : FORM_POSITIVE,
            result : {
                type : 'unicode_result',
                value : 'auto complete'
            },
            timestamp : now()
        }
    };

    var r3 = transition('1.0.118.i', state, userInput3);

    assertSame(FORM_POSITIVE, r3.newstate.run.steps[3].answer_id);
    assertSame('auto complete', r3.newstate.run.steps[3].form_result.result.value);
    assertSame('auto complete', r3.newstate.run.steps[3].display_value);

    var reply4_key = r3.local_actions[0].a.request.form_message.key;
    var userInput4 = {
        func: 'com.mobicage.api.submitSingleSelectForm',
        request : {
            message_key : reply4_key,
            parent_message_key : parent_key,
            button_id : FORM_POSITIVE,
            result : {
                type : 'unicode_result',
                value : 'b'
            },
            timestamp : now()
        }
    };

    var r4 = transition('1.0.118.i', state, userInput4);

    assertSame(FORM_POSITIVE, r4.newstate.run.steps[4].answer_id);
    assertSame('b', r4.newstate.run.steps[4].form_result.result.value);
    assertSame('B', r4.newstate.run.steps[4].display_value);

    var reply5_key = r4.local_actions[0].a.request.form_message.key;
    var userInput5 = {
        func: 'com.mobicage.api.submitMultiSelectForm',
        request : {
            message_key : reply5_key,
            parent_message_key : parent_key,
            button_id : FORM_POSITIVE,
            result : {
                type : 'unicode_list_result',
                values : ['a', 'b', 'd']
            },
            timestamp : now()
        }
    };

    var r5 = transition('1.0.118.i', state, userInput5);

    assertSame(FORM_POSITIVE, r5.newstate.run.steps[5].answer_id);
    assertEquals(['a', 'b', 'd'], r5.newstate.run.steps[5].form_result.result.values);
    assertSame('A\nB\nD', r5.newstate.run.steps[5].display_value);

    var reply6_key = r5.local_actions[0].a.request.form_message.key;
    var userInput6 = {
        func: 'com.mobicage.api.submitDateSelectForm',
        request : {
            message_key : reply6_key,
            parent_message_key : parent_key,
            button_id : FORM_NEGATIVE,
            result : null,
            timestamp : now()
        }
    };

    var r6 = transition('1.0.118.i', state, userInput6);

    assertSame(FORM_NEGATIVE, r6.newstate.run.steps[6].answer_id);
    assertNull(r6.newstate.run.steps[6].form_result.result);
    assertNull(r6.newstate.run.steps[6].display_value);

    var reply7_key = r6.local_actions[0].a.request.form_message.key;
    var userInput7 = {
        func: 'com.mobicage.api.submitSingleSliderForm',
        request : {
            message_key : reply7_key,
            parent_message_key : parent_key,
            button_id : FORM_NEGATIVE,
            result : null,
            timestamp : now()
        }
    };

    var r7 = transition('1.0.118.i', state, userInput7);

    assertSame(FORM_NEGATIVE, r7.newstate.run.steps[7].answer_id);
    assertNull(r7.newstate.run.steps[7].form_result.result);
    assertNull(r7.newstate.run.steps[7].display_value);

    var reply8_key = r7.local_actions[0].a.request.form_message.key;
    var userInput8 = {
        func: 'com.mobicage.api.submitSingleSliderForm',
        request : {
            message_key : reply8_key,
            parent_message_key : parent_key,
            button_id : FORM_POSITIVE,
            result : {
                type : 'float_list_result',
                values : [0, 1]
            },
            timestamp : now()
        }
    };

    var r8 = transition('1.0.118.i', state, userInput8);

    assertSame(FORM_POSITIVE, r8.newstate.run.steps[8].answer_id);
    assertEquals([0, 1], r8.newstate.run.steps[8].form_result.result.values);
    assertEquals("0 - 1", r8.newstate.run.steps[8].display_value);

    assertSame(4, r8.server_actions.length); // newFlowMessage + flowEnded + 2x flowMemberResult

    var fmrRequest1, fmrRequest2, ffRequest, nfmRequest;
    for (var i in r8.server_actions) {
        var apiCall = r8.server_actions[i];
        if (apiCall.f == API_FLOW_MEMBER_RESULT) {
            if (!fmrRequest1) {
                fmrRequest1 = apiCall.a.request;
            } else {
                fmrRequest2 = apiCall.a.request;
            }
        } else if (apiCall.f == API_FLOW_FINISHED) {
            ffRequest = apiCall.a.request;
        } else if (apiCall.f == API_NEW_FLOW_MESSAGE) {
            nfmRequest = apiCall.a.request;
        } else {
            fail('Unexpected action: ' + apiCall.func);
        }
    }
    assertNotSame(undefined, fmrRequest1);
    assertNotSame(undefined, fmrRequest2);
    assertNotSame(undefined, ffRequest);
    assertNotSame(undefined, nfmRequest);

    assertSame(9, fmrRequest1.run.steps.length);
    assertSame(null, fmrRequest1.end_id);
    assertSame('base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAiZmx1c2hfMSJ9',
                fmrRequest1.flush_id);
    assertSame(message_flow_run_id, fmrRequest1.run.message_flow_run_id);
    assertSame(parent_key, fmrRequest1.run.parent_message_key);

    assertSame(fmrRequest1.run.steps.length, fmrRequest2.run.steps.length);
    assertSame(fmrRequest1.run.message_flow_run_id, fmrRequest2.run.message_flow_run_id);
    assertSame(fmrRequest1.run.parent_message_key, fmrRequest2.run.parent_message_key);
    assertSame('base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAiZW5kXzEifQ==',
                fmrRequest2.end_id);
    assertSame('base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAiZmx1c2hfMiJ9',
                fmrRequest2.flush_id);
};

JsMfrWidgetsTest.prototype.setUp = function () {
    flowDefinition = JsMfrWidgetsTest.prototype.flowDefinition;
};
