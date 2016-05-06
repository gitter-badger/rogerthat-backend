JsMfrFlowCodeTest = TestCase("JsMfrFlowCodeTest");

JsMfrFlowCodeTest.prototype.testPath1 = function() {
    
    var state = {
        "member" : "jane.doe@foo.com",
        "user": {"name": "Ruben",
                 "language": "en",
                 "avatarUrl": "",
                 "account": "jane.doe@foo.com",
            "data": {}
        },
        "service": {"name": "Ruben",
                    "email": "service1@foo.com",
                    "account": "s1@foo.com",
                    "data": null},
        "system": {"os": "android",
                   "version": "19",
                   "appVersion": "1.0.1.A",
                   "appName": "1.0.1.A",
                   "appId": "rogerthat"}
    };

    var userInput1 = {
        "request" : {
            "hashed_tag" : "fd61a03af4f77d870fc21e05e7e80678095c92d808cfb3b5c279ee04c74aca13",
            "static_flow_hash" : "811a44c5e305c14e020c4928bbd8da61",
            "coords" : [ 2, 2, 0 ],
            "service" : "s1@foo.com",
            "message_flow_run_id" : null,
            "context" : "MENU_d5ef2846-6d7c-4f2a-87fb-0a7285b8a0d0",
            "generation" : 63
        },
        "func" : "com.mobicage.api.services.pressMenuItem"
    };

    var r1 = transition('1.0.140.i', state, userInput1);
    assertNotNull(r1.local_actions);
    assertSame('com.mobicage.capi.messaging.newMessage', r1.local_actions[0].f);

    var parentMessage1 = r1.local_actions[0].a.request.message;
    assertSame('message 1\n\nmessage 1', parentMessage1.message);
    assertSame(256, (parentMessage1.flags & 256));
    assertSame(1, parentMessage1.dismiss_button_ui_flags);
    assertSame('jane.doe@foo.com', parentMessage1.members[0].member);
    assertSame('s1@foo.com', parentMessage1.sender);
    
    var reply1_key = r1.local_actions[0].a.request.message.key;
    
    var userInput2 = {
            func: 'com.mobicage.api.ackMessage',
            request : {
                message_key : reply1_key,
                parent_message_key : null,
                button_id : null,
                timestamp : now()
            }
         };
      
    var r2 = transition('1.0.140.i', state, userInput2);
    assertNotNull(r2.local_actions);
    assertSame('com.mobicage.capi.messaging.newTextLineForm', r2.local_actions[0].f);
    
    var parentMessage2 = r2.local_actions[0].a.request.form_message;
    assertSame('text line 2\n\ntext line 2', parentMessage2.message);
    assertSame(256, (parentMessage2.flags & 256));
    assertSame('s1@foo.com', parentMessage2.sender);
        
    var reply2_key = r2.local_actions[0].a.request.form_message.key;
    var userInput3 = {
            func: 'com.mobicage.api.submitTextLineForm',
            request : {
                message_key : reply2_key,
                parent_message_key : reply1_key,
                button_id : FORM_POSITIVE,
                result : {
                    type : 'unicode_result',
                    value : '0' // Exception
                },
                timestamp : now()
            }
         };
    
    var r3 = transition('1.0.140.i', state, userInput3);
    assertNotNull(r3.local_actions);
    var userDataAction = r3.local_actions.filter(function (a) {
        return a.f == CAPI_UPDATE_USER_DATA;
    })[0];
    assertNotUndefined(userDataAction);
    assertEquals(['Events', 'Nieuws', 'Test'], JSON.parse(userDataAction.a.request.user_data).__rt__disabledBroadcastTypes);

    var newMessageAction = r3.local_actions.filter(function (a) {
        return a.f == 'com.mobicage.capi.messaging.newMessage';
    })[0];
    assertNotUndefined(newMessageAction);

    var parentMessage3 = newMessageAction.a.request.message;
    assertSame('message 4\n\nmessage 4', parentMessage3.message);
    assertSame(256, (parentMessage3.flags & 256));
    assertSame(0, parentMessage3.dismiss_button_ui_flags); // NO followup message
    assertSame('jane.doe@foo.com', parentMessage3.members[0].member);
    assertSame('s1@foo.com', parentMessage3.sender);

    var reply3_key = newMessageAction.a.request.message.key;
    
    var userInput4 = {
            func: 'com.mobicage.api.ackMessage',
            request : {
                message_key : reply3_key,
                parent_message_key : null,
                button_id : null,
                timestamp : now()
            }
         };
      
    var r4 = transition('1.0.140.i', state, userInput4);
    assertNotNull(r4.local_actions);
    assertSame('com.mobicage.capi.messaging.endMessageFlow', r4.local_actions[0].f);
};

JsMfrFlowCodeTest.prototype.testPath2 = function() {
    
    var state = {
        "member" : "jane.doe@foo.com",
        "user": {"name": "Ruben",
                 "language": "en",
                 "avatarUrl": "",
                 "account": "jane.doe@foo.com",
            "data": {}
        },
        "service": {"name": "Ruben",
                    "email": "service1@foo.com",
                    "account": "s1@foo.com",
                    "data": null},
        "system": {"os": "android",
                   "version": "19",
                   "appVersion": "1.0.1.A",
                   "appName": "1.0.1.A",
                   "appId": "rogerthat"}
    };

    var userInput1 = {
        "request" : {
            "hashed_tag" : "fd61a03af4f77d870fc21e05e7e80678095c92d808cfb3b5c279ee04c74aca13",
            "static_flow_hash" : "811a44c5e305c14e020c4928bbd8da61",
            "coords" : [ 2, 2, 0 ],
            "service" : "s1@foo.com",
            "message_flow_run_id" : null,
            "context" : "MENU_d5ef2846-6d7c-4f2a-87fb-0a7285b8a0d0",
            "generation" : 63
        },
        "func" : "com.mobicage.api.services.pressMenuItem"
    };

    var r1 = transition('1.0.140.i', state, userInput1);
    assertNotNull(r1.local_actions);
    assertSame('com.mobicage.capi.messaging.newMessage', r1.local_actions[0].f);

    var parentMessage1 = r1.local_actions[0].a.request.message;
    assertSame('message 1\n\nmessage 1', parentMessage1.message);
    assertSame(256, (parentMessage1.flags & 256));
    assertSame(1, parentMessage1.dismiss_button_ui_flags);
    assertSame('jane.doe@foo.com', parentMessage1.members[0].member);
    assertSame('s1@foo.com', parentMessage1.sender);
    
    var reply1_key = r1.local_actions[0].a.request.message.key;
    
    var userInput2 = {
            func: 'com.mobicage.api.ackMessage',
            request : {
                message_key : reply1_key,
                parent_message_key : null,
                button_id : null,
                timestamp : now()
            }
         };
      
    var r2 = transition('1.0.140.i', state, userInput2);
    assertNotNull(r2.local_actions);
    assertSame('com.mobicage.capi.messaging.newTextLineForm', r2.local_actions[0].f);
    
    var parentMessage2 = r2.local_actions[0].a.request.form_message;
    assertSame('text line 2\n\ntext line 2', parentMessage2.message);
    assertSame(256, (parentMessage2.flags & 256));
    assertSame('s1@foo.com', parentMessage2.sender);
        
    var reply2_key = r2.local_actions[0].a.request.form_message.key;
    var userInput3 = {
            func: 'com.mobicage.api.submitTextLineForm',
            request : {
                message_key : reply2_key,
                parent_message_key : reply1_key,
                button_id : FORM_POSITIVE,
                result : {
                    type : 'unicode_result',
                    value : '1' // Default
                },
                timestamp : now()
            }
         };
    
    var r3 = transition('1.0.140.i', state, userInput3);
    assertNotNull(r3.local_actions);

    var newTextLineAction = r3.local_actions.filter(function (a) {
        return a.f == 'com.mobicage.capi.messaging.newTextLineForm';
    })[0];
    assertNotUndefined(newTextLineAction);

    var parentMessage3 = newTextLineAction.a.request.form_message;
    assertSame('text line 6\n\ntext line 6', parentMessage3.message);
    assertSame(256, (parentMessage3.flags & 256));
    assertSame('s1@foo.com', parentMessage3.sender);

    var reply3_key = newTextLineAction.a.request.form_message.key;

    var userInput4 = {
            func: 'com.mobicage.api.submitTextLineForm',
            request : {
                message_key : reply3_key,
                parent_message_key : reply2_key,
                button_id : FORM_POSITIVE,
                result : {
                    type : 'unicode_result',
                    value : '1' // Exception
                },
                timestamp : now()
            }
         };

    var r4 = transition('1.0.140.i', state, userInput4);
    assertNotNull(r4.local_actions);
    assertSame('com.mobicage.capi.messaging.newMessage', r4.local_actions[0].f);

    var parentMessage4 = r4.local_actions[0].a.request.message;
    assertSame('message 4\n\nmessage 4', parentMessage4.message);
    assertSame(256, (parentMessage4.flags & 256));
    assertSame(0, parentMessage4.dismiss_button_ui_flags);
    assertSame('jane.doe@foo.com', parentMessage4.members[0].member);
    assertSame('s1@foo.com', parentMessage4.sender);

    var reply4_key = r4.local_actions[0].a.request.message.key;

    var userInput5 = {
            func: 'com.mobicage.api.ackMessage',
            request : {
                message_key : reply4_key,
                parent_message_key : null,
                button_id : null,
                timestamp : now()
            }
         };

    var r5 = transition('1.0.140.i', state, userInput5);
    assertNotNull(r5.local_actions);
    assertSame('com.mobicage.capi.messaging.endMessageFlow', r5.local_actions[0].f);
};

JsMfrFlowCodeTest.prototype.setUp = function() {
    flowDefinition = JsMfrFlowCodeTest.prototype.flowDefinition;
};