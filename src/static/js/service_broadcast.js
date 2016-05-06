/*
 * Copyright 2016 Mobicage NV
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * @@license_version:1.1@@
 */

var broadcastScript = function() {
    var container = "#serviceBroadcastContainer";
    var lj = mctracker.getLocaljQuery(container);

    var BROADCAST_STATUS_ALL_PENDING = 1;
    var BROADCAST_STATUS_PENDING = 2;
    var BROADCAST_STATUS_APPROVED = 3;
    var BROADCAST_STATUS_DECLINED = 4;

    var TEST_PERSON_TEMPLATE = "${name} &lt;${email}&gt;";
    var TEST_PERSON_REGEXP = /.*? <(.*)>/

    var NOTIFICATION_TEMPLATE = '<li>' + //
    '    <b>${broadcast_type} - ${name}</b>: <i>${status_string}</i> ' + //
    '    <br> &nbsp;&nbsp;&nbsp;Created on: ${timestamp_string}' + //
    '    |' + //
    '    {{if sent}}<b><i>Sent</i></b>' + //
    '    {{else}}{{if scheduled_at != 0}}Scheduled at: ${scheduled_timestamp_string}{{else}}<a href="#"class="action-link" key="${key}" action="sendBroadcast">Send</a> | <input name="when" style="display: none;"/> <a href="#" class="action-link" key="${key}" action="scheduleBroadcast">Schedule</a>{{/if}}{{/if}}' + //
    // ' |' + //
    // ' <a class="action-link" key="${key}" action="showBroadcastStats">Statistics</a>' + //
    '    |' + //
    '    <a class="action-link" key="${key}" action="removeBroadcast">Remove</a>' + //
    '    <br> <br>' + // 
    '</li>';

    var broadcastTypes = [];
    var testPersons = {};
    var messageFlows = [];
    var broadcasts = [];
    var warnings = [];
    
    var applyJQueryInUI = function() {
        lj(".panel").panel({
            collapsible : false,
            helpIcon : "/static/images/help.png"
        });

        lj("#testNewBroadcast").button().click(testNewBroadcastClicked);
    };

    var loadMessageFlows = function() {
        mctracker.call({
            url : "/mobi/rest/mfd/list_valid",
            type : "GET",
            hideProcessing : true,
            success : function(data) {
                messageFlows = data.message_flows;
                initNewBroadcastPanel();
            }
        });
    };

    var loadData = function(onSuccess, hideProcessing) {
        mctracker.call({
            url : "/mobi/rest/service/broadcast_configuration",
            type : "GET",
            hideProcessing : hideProcessing,
            success : function(data) {
                testPersons = {};
                $.each(data.test_persons, function(i, friend) {
                    testPersons[friend.email] = friend.name;
                });
                broadcastTypes = data.broadcast_types;

                $.each(data.broadcasts, function(i, broadcast) {
                    broadcast.timestamp_string = mctracker.formatDate(broadcast.creation_time, true, false);
                    broadcast.scheduled_timestamp_string = broadcast.scheduled_at ? mctracker.formatDate(broadcast.scheduled_at, true, false) : "";
                });
                mctracker.sort(data.broadcasts, function(b) {
                    return b.creation_time;
                });
                broadcasts = data.broadcasts.reverse();

                warnings = data.warnings;

                var warningsDiv = lj("#row_warnings");
                var warningsList = lj("#warnings").empty();
                if (warnings && warnings.length > 0) {
                    warningsDiv.show();
                    $.each(warnings, function(i, warning) {
                        warningsList.append($("<li>" + mctracker.htmlize(warning) + "</li>"));
                    });
                } else {
                    warningsDiv.hide();
                }

                initTestersPanel();
                initBroadcastTypesPanel();
                initNewBroadcastPanel();
                initBroadcastsPanel();

                if (onSuccess) {
                    onSuccess();
                }
            }
        });
    };

    var testNewBroadcastClicked = function() {
        if (mctracker.size(testPersons) == 0) {
            return mctracker.alert("There are no test persons.<br>Please add a test person first.", function() {
                lj("#newTestPersonEmail").focus();
            }, null, null, true);
        }

        var broadcastType = lj("#broadcastTypeSelect").val();
        if (!broadcastType) {
            if (broadcastTypes.length == 0) {
                return mctracker.alert("There are no broadcast types.<br>Please add a broadcast type first.",
                        function() {
                            lj("#newBroadcastTypeName").focus();
                        }, null, null, true);
            } else {
                return mctracker.alert("Please select a broadcast type.", function() {
                    lj("#broadcastTypeSelect").focus();
                });
            }
        }

        var broadcastFlow = lj("#broadcastFlowSelect").val();
        if (!broadcastFlow) {
            if (messageFlows.length == 0) {
                return mctracker.alert("There are no (valid) message flows.<br>Please create a message flow first.",
                        null, null, null, true);
            } else {
                return mctracker.alert("Please select a message flow.", function() {
                    lj("#broadcastFlowSelect").focus()
                });
            }
        }

        if (warnings && warnings.length > 0) {
            return mctracker.alert("Can not send broadcast.<br>" + lj("#warnings").html(), null, null, null, true);
        }

        var creationTime = mctracker.now();
        var creationTimeString = mctracker.formatDate(creationTime, true, false)
        var broadcastName = lj("#newBroadcastName").val() || "New broadcast";
        var broadcastTag = lj("#newBroadcastTag").val() || null;

        mctracker.call({
            url : "/mobi/rest/service/test_broadcast",
            type : "POST",
            data : {
                data : JSON.stringify({
                    name : broadcastName,
                    broadcast_type : broadcastType,
                    tag : broadcastTag,
                    message_flow_id : broadcastFlow
                })
            },
            success : function(data) {
                if (data.success) {
                    data.broadcast.timestamp_string = mctracker.formatDate(data.broadcast.creation_time, true, false);
                    broadcasts.unshift(data.broadcast);

                    initBroadcastsPanel();

                    lj("#broadcastTypeSelect").val("");
                    lj("#broadcastFlowSelect").val("");
                    lj("#newBroadcastName").val("");
                    lj("#newBroadcastTag").val("");
                } else {
                    mctracker.alert(data.errormsg);
                }
            }
        });
    };

    var renderPersonString = function(person) {
        return $.tmpl(TEST_PERSON_TEMPLATE, person).text();
    };

    var initTestersPanel = function() {
        var ul = lj("#testPersonList").empty();

        var testPersonStrings = [];
        $.each(testPersons, function(email, name) {
            testPersonStrings.push(renderPersonString({
                email : email,
                name : name
            }));
        });

        $.each(mctracker.sort(testPersonStrings), function(i, testPersonString) {
            var testPersonHTML = mctracker.htmlize(testPersonString);
            var removeLink = $('<a style="float: right;" class="action-link">Remove</a>').click(
                    function() {
                        mctracker.confirm("Are you sure you wish to remove test person '<i>" + testPersonHTML
                                + "</i>'?", function() {
                            var m = TEST_PERSON_REGEXP.exec(testPersonString);
                            if (!m)
                                return;
                            var email = m[1];
                            mctracker.call({
                                url : "/mobi/rest/service/rm_broadcast_test_person",
                                type : "POST",
                                data : {
                                    data : JSON.stringify({
                                        email : email
                                    })
                                },
                                success : function(data) {
                                    if (data.success) {
                                        delete testPersons[email];
                                        initTestersPanel();
                                    } else {
                                        mctracker.alert(data.errormsg);
                                    }
                                }
                            });
                        }, null, "Yes", "No", null, true);
                    });
            ul.append($("<li></li>").append(testPersonHTML).append(removeLink));
        });

        var newTestPersonLink = lj("#addNewTestPerson").unbind('click').click(
                function() {
                    mctracker.input("Lookup a connected user using his name or Rogerthat account (email):", function(
                            testPerson) {
                        // This function is called when the dialog is closed with the Ok button.
                        if (!testPerson) {
                            return mctracker.alert("Please lookup a connected user.");
                        }
                        var m;
                        var email = (m = TEST_PERSON_REGEXP.exec(testPerson)) ? m[1] : testPerson;

                        if (testPersons[email]) {
                            lj("#newTestPersonEmail").val("");
                            return;
                        }

                        mctracker.call({
                            url : "/mobi/rest/service/add_broadcast_test_person",
                            type : "POST",
                            data : {
                                data : JSON.stringify({
                                    email : email
                                })
                            },
                            success : function(data) {
                                if (data.success) {
                                    testPersons[email] = data.user_details.name;
                                    initTestersPanel();
                                    lj("#newTestPersonEmail").val("");
                                } else if (data.errormsg) {
                                    mctracker.alert(data.errormsg);
                                }
                            }
                        });
                        return true; // Close dialog.
                    }, function(request, responseCallback) {
                        // This function is called by the autocomplete widget
                        // See http://jqueryui.com/autocomplete/#remote
                        mctracker.call({
                            url : "/mobi/rest/service/search_connected_users",
                            type : "GET",
                            data : {
                                name_or_email_term : request.term
                            },
                            hideProcessing : true,
                            success : function(data) {
                                var result = [];
                                $.each(data, function(i, friend) {
                                    if (!testPersons[friend.email])
                                        result.push(renderPersonString(friend))
                                });
                                responseCallback(result);
                            }
                        });
                    });
                });

        // TODO: disable when all connected users are testers
        // newTestPersonAutocomplete.attr('disabled', candidateStrings.length == 0);
        // newTestPersonLink.attr('disabled', candidateStrings.length == 0);
    };

    var deleteBroadcastType = function(broadcastType, force) {
        mctracker.call({
            url : "/mobi/rest/service/rm_broadcast_type",
            type : "POST",
            data : {
                data : JSON.stringify({
                    broadcast_type : broadcastType,
                    force : force
                })
            },
            success : function(data) {
                if (data.success) {
                    var i = broadcastTypes.indexOf(broadcastType);
                    if (i != -1) {
                        broadcastTypes.splice(i, 1);
                        initBroadcastTypesPanel();
                    }
                } else if (data.errormsg) {
                    mctracker.alert(data.errormsg);
                } else if (data.confirmation) {
                    mctracker.confirm(data.confirmation, function() {
                        deleteBroadcastType(broadcastType, true);
                    }, null, "Yes", "No", null, true);
                }
            }
        });
    }

    var initBroadcastTypesPanel = function() {
        mctracker.sort(broadcastTypes);

        var ul = lj("#broadcastTypeList").empty();
        $.each(broadcastTypes, function(i, broadcastType) {
            var removeLink = $('<a style="float: right;" class="action-link">Remove</a>').click(
                    function() {
                        mctracker.confirm("Are you sure you wish to remove broadcast type '<i>" + broadcastType
                                + "</i>'?", function() {
                            deleteBroadcastType(broadcastType, false);
                        }, null, "Yes", "No", null, true);
                    });
            ul.append($("<li>" + mctracker.htmlize(broadcastType) + "</li>").append(removeLink));
        });

        lj("#addNewBroadcastType").unbind("click").click(function() {
            mctracker.input("Enter the name for the new broadcast type:", function(broadcastType) {
                if (!broadcastType) {
                    return mctracker.alert("Please enter a broadcast type");
                }
                if (broadcastTypes.indexOf(broadcastType) == -1) {
                    mctracker.call({
                        url : "/mobi/rest/service/add_broadcast_type",
                        type : "POST",
                        data : {
                            data : JSON.stringify({
                                broadcast_type : broadcastType
                            })
                        },
                        success : function(data) {
                            if (data.success) {
                                broadcastTypes.push(broadcastType);
                                initBroadcastTypesPanel();
                                initNewBroadcastPanel();
                                lj("#newBroadcastTypeName").val("");
                            } else if (data.errormsg) {
                                mctracker.alert(data.errormsg, function() {
                                    lj("#newBroadcastTypeName").select();
                                });
                            }
                        }
                    });
                }
                return true;
            });
        });
    };

    var initNewBroadcastPanel = function() {
        var flowSelect = lj("#broadcastFlowSelect");
        var emptyFlowOption = $('option[value=""]', flowSelect);
        flowSelect.empty().append(emptyFlowOption);
        $.each(messageFlows, function(i, messageFlow) {
            flowSelect.append('<option value="' + messageFlow.id + '">' + messageFlow.name + '</option>');
        });

        var typeSelect = lj("#broadcastTypeSelect");
        var emptyTypeOption = $('option[value=""]', typeSelect);
        typeSelect.empty().append(emptyTypeOption);
        $.each(broadcastTypes, function(i, broadcastType) {
            typeSelect.append('<option value="' + broadcastType + '">' + broadcastType + '</option>');
        });
    };

    var initBroadcastsPanel = function() {
        var broadcastList = lj("#broadcastList").empty();
        $.each(broadcasts, function(i, broadcast) {
            var li = $.tmpl(NOTIFICATION_TEMPLATE, broadcast);

            $('a[action="sendBroadcast"]', li).click(function() {
                sendBroadcastClicked(broadcast);
            });
            var datetime = $('input[name=when]', li).datetimepicker({
            	'minDateTime': new Date()
            });
            $('a[action="scheduleBroadcast"]', li).click(function() {
                scheduleBroadcastClicked(broadcast, datetime);
            });
            $('a[action="removeBroadcast"]', li).click(function() {
                removeBroadcastClicked(broadcast);
            });
            $('a[action="showBroadcastStats"]', li).click(function() {
                showBroadcastStatsClicked(broadcast);
            });

            broadcastList.append(li);
        });
    };
    
    var scheduleBroadcastClicked = function(broadcast, datetime) {
    	if (!datetime.is(":visible")) {
    		datetime.show();
    		datetime.focus();
    		return;
    	}
        var selectedDate = datetime.datetimepicker('getDate');
        if (selectedDate < new Date()) {
        	return mctracker.alert("Can not schedule broadcast in the past.", null, null,
                    null, true);
        }

        if (broadcast.status == BROADCAST_STATUS_ALL_PENDING) {
            return mctracker.alert("Can not schedule broadcast.<br>Broadcast is not yet processed by anyone.", null, null,
                    null, true);
        }
        
        var broadcastString = "'<i>" + broadcast.broadcast_type + " - " + broadcast.name + "</i>'";
        var m;
        if (broadcast.status == BROADCAST_STATUS_DECLINED) {
            m = "Broadcast was <b>declined</b>.<br>Are you really sure you wish to schedule " + broadcastString + "?";
        } else if (broadcast.status == BROADCAST_STATUS_PENDING) {
            m = "Broadcast is not yet processed by everyone.<br>Are you really sure you wish to schedule "
                    + broadcastString + "?";
        } else {
            m = "Are you sure you wish to schedule " + broadcastString + "?";
        }
        mctracker.confirm(m, function() {
        	scheduleBroadcast(broadcast, Math.round(selectedDate.getTime() / 1000));
        }, null, "Yes", "No", null, true);
    };

    var scheduleBroadcast = function(broadcast, timestamp) {
        mctracker.call({
            url : "/mobi/rest/service/schedule_broadcast",
            type : "POST",
            data : {
                data : JSON.stringify({
                    broadcast_key : broadcast.key,
                    timestamp: timestamp
                })
            },
            success : function(data) {
                if (data.success) {
                    broadcast.scheduled_at = timestamp;
                    broadcast.scheduled_timestamp_string = mctracker.formatDate(broadcast.scheduled_at, true, false);
                    initBroadcastsPanel();
                } else {
                    mctracker.alert(data.errormsg);
                }
            }
        });
    };

    
    var sendBroadcast = function(broadcast) {
        mctracker.call({
            url : "/mobi/rest/service/send_broadcast",
            type : "POST",
            data : {
                data : JSON.stringify({
                    broadcast_key : broadcast.key
                })
            },
            success : function(data) {
                if (data.success) {
                    broadcast.sent = true;
                    initBroadcastsPanel();
                } else {
                    mctracker.alert(data.errormsg);
                }
            }
        });
    };

    var sendBroadcastClicked = function(broadcast) {
        if (broadcast.status == BROADCAST_STATUS_ALL_PENDING) {
            return mctracker.alert("Can not send broadcast.<br>Broadcast is not yet processed by anyone.", null, null,
                    null, true);
        }

        var broadcastString = "'<i>" + broadcast.broadcast_type + " - " + broadcast.name + "</i>'";
        var m;
        if (broadcast.status == BROADCAST_STATUS_DECLINED) {
            m = "Broadcast was <b>declined</b>.<br>Are you really sure you wish to send " + broadcastString + "?";
        } else if (broadcast.status == BROADCAST_STATUS_PENDING) {
            m = "Broadcast is not yet processed by everyone.<br>Are you really sure you wish to send "
                    + broadcastString + "?";
        } else {
            m = "Are you sure you wish to send " + broadcastString + "?";
        }
        mctracker.confirm(m, function() {
            sendBroadcast(broadcast);
        }, null, "Yes", "No", null, true);
    };

    var removeBroadcastClicked = function(broadcast) {
        var broadcastString = "'<i>" + broadcast.broadcast_type + " - " + broadcast.name + "</i>'";
        mctracker.confirm("Are you sure you wish to remove " + broadcastString + "?", function() {
            mctracker.call({
                url : "/mobi/rest/service/rm_broadcast",
                type : "POST",
                data : {
                    data : JSON.stringify({
                        broadcast_key : broadcast.key
                    })
                },
                success : function(data) {
                    if (data.success) {
                        var i = broadcasts.indexOf(broadcast);
                        if (i != -1) {
                            broadcasts.splice(i, 1);
                            initBroadcastsPanel();
                        }
                    } else {
                        mctracker.alert(data.errormsg);
                    }
                }
            });
        }, null, "Yes", "No", null, true);
    };

    var showBroadcastStatsClicked = function(broadcast) {

    };

    var initScreen = function() {
        loadData(function() {
            loadMessageFlows();
        });

        applyJQueryInUI();
        initTestersPanel();
        initBroadcastTypesPanel();
        initNewBroadcastPanel();
        initBroadcastsPanel();
    };

    var processMessage = function(data) {
        if (data.type == "rogerthat.mfd.changes") {
            loadMessageFlows();
        } else if (data.type == "rogerthat.broadcast.changes") {
            loadData(null, true);
        }
    };

    return function() {
        mctracker.registerMsgCallback(processMessage);
        initScreen();
    };
}

mctracker.registerLoadCallback("serviceBroadcastContainer", broadcastScript());