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

var messagingScript = function () {
    var container = "#messagingContainer";
    var mainWidgetId = "mainWidget";
    var lj = mctracker.getLocaljQuery(container);
    var messagesByIndex = [];
    var address_lookup_dialog = null;
    var address_gps_coords = null;
    var button_detail_dialog = null;
    var button_confirmation_dialog = null;
    var messageHtmlTemplate = null;
    var formWidgetHtmlTemplate = null;
    var expandedMessages = [];
    var maxtabindex = 0;
    var reply_boxes_opened = [];
    var pending_updates = [];
    var tmprenderingarea = null;
    var threadsToBeMarkedAsRead = [];

    var prepareNewMessageWidget = function () {
        lj("#new_button_widget input").keypress(function (event) {
            if (event.keyCode == '13') {
                var input = $(event.target);
                if (input.val().replace(input.attr("placeholder"), "").replace(" ", "") != "") {
                    var message = input.data('message');
                    var widget = $(this).parent().parent().parent();
                    $("#newmessage_buttons", widget).append(createButton(message, input.val(), widget));
                    if ( ! message.parent_key )
                        sizeSendButton(widget);
                    input.val("");
                }
            }
        });
        var newMessageTextarea = lj("#newmessage_widget.messaging_widget textarea");
        mctracker.fixTextareaPlaceholderForIE(newMessageTextarea);
        newMessageTextarea.keyup(function (event) {
            var textarea = $(event.target);
            var cc = 500 - textarea.val().length;
            if (cc < 0) {
                textarea.val(textarea.val().substring(0, 500));
                cc = 500 - textarea.val().length;
            }
            $("#charsleft", textarea.parent()).text(cc);
        });
        var newButtonWidget = lj("#new_button_widget").clone(true).attr("id", null).show();
        newButtonWidget.focusin(function () {
            var input = $("input#new_button_caption", this);
            var tooltip = $("div#new_button_widget_tooltip", this);
            tooltip.css('top', (input.css('top') + input.css('height') + 5) + "px");
            tooltip.css('left', Math.round((input.css('left') + (input.css('width') / 2) - (tooltip.css('width') / 2))) + "px");
            tooltip.fadeIn('slow');
        }).focusout(function () {
            var tooltip = $("div#new_button_widget_tooltip", this);
            tooltip.fadeOut('slow');
        });
        lj("#newmessage_widget #new_button_area").append(newButtonWidget);
    };
    
    var getCreateMessageWidget = function (context) {
        var element = context;
        while (!element.hasClass("messaging_widget")) {
            element = element.parent();
        }
        return element;
    };

    var getSendMessageClickHandler = function (callback) {
        return function () {
            var context = getCreateMessageWidget($(this));
            var message = context.data('message');
            var members = $.map(message.members, function (member) { return member.email; });
            members.push(loggedOnUserEmail);
            var flags = FLAG_ALLOW_CUSTOM_REPLY | FLAG_ALLOW_DISMISS | FLAG_ALLOW_REPLY;
            flags |= FLAG_ALLOW_REPLY_ALL | FLAG_SHARED_MEMBERS;
            var buttons = [];
            var sender_reply = null;
            for (b in message.buttons) {
                var button = message.buttons[b];
                buttons.push({
                    id: button.id,
                    caption: button.caption,
                    action: button.action
                });
                if (button.my_selection) {
                    sender_reply = button.id;
                }
            }
            message.message = $("#newmessage_message", context).val();

            if (message.members.length == 0) {
                $("#errormessage", context).text("Add recipients!");
                $("#errormessage:hidden", context).slideDown();
            	$("#to", context).focus();
                return;
            } else if (message.message.replace($("#newmessage_message", context).attr("placeholder"), "")
                    .replace(" ", "") == "" && buttons.length == 0) {
                $("#errormessage", context).text("Add a message text!");
                $("#errormessage:hidden", context).slideDown();
                $("#newmessage_message", context).focus();
                return;
            } else if ($("#new_button_caption", context).val()
                    .replace($("#new_button_caption", context).attr("placeholder"), "").replace(" ", "") != "") {
                $("#errormessage", context).text("Add the button or empty the new button field!");
                $("#errormessage:hidden", context).slideDown();
                $("#new_button_caption", context).focus();
                return;
            }

            mctracker.call({
                url: "/mobi/rest/messaging/send",
                type: "POST",
                data: {
                    data: JSON.stringify({
                        request: {
                            members: members,
                            flags: flags,
                            timeout: 0,
                            parent_key: message.parent_key,
                            message: message.message,
                            buttons: buttons,
                            sender_reply: sender_reply
                        }
                    })
                },
                success: function (data, textStatus, XMLHttpRequest) {
                },
            });

            if (callback) {
                callback(context);
            }

            var thread = messagesByIndex[message.parent_key];
            if (thread && thread.threadNeedsMyAnswer)
                dismissConversation(message.parent_key);
        };
    };

    var createNewMessageWidget = function (parent_key, callback, id) {
        var message = {
            members: [],
            buttons: [],
            parent_key: parent_key
        };
        var newMessage = lj("#newmessage_widget").clone(true).attr("id", null).watermark().show();
        if (id)
            newMessage.attr("id", id);
        maxtabindex ++;
        var to = $("#to", newMessage).autocomplete({
            source: autoCompleteMembers,
            minLength: 1,
            delay: 0,
            select: memberSelected
        }).attr('tabindex', maxtabindex);
        if (! $.browser.msie)
        	to.focus();
        $("*", newMessage).data('message', message);
        newMessage.data('message', message);
        maxtabindex ++;
        var text_area = $("textarea", newMessage).attr('tabindex', maxtabindex).attr('last_typing', '0').keydown(function () {
        	text_area.attr('last_typing', ''+new Date().getTime());
        });
        mctracker.fixTextareaPlaceholderForIE(text_area);
        maxtabindex ++;
        $("#new_button_caption", newMessage).attr('tabindex', maxtabindex);
        maxtabindex ++;
        $("button.newmessage_send", newMessage)
        	.text("send").click(getSendMessageClickHandler(callback)).attr('tabindex', maxtabindex).button();
        newMessage.addClass("messaging_widget");
        return newMessage;
    };

    var applyJQueryInUI = function () {
    	tmprenderingarea = lj("#tmprenderingarea");
        $("a#logo").removeAttr('href').click(function () {
            mctracker.loadContainer("messagingContainer", "/static/parts/messaging.html");    
        });
        prepareNewMessageWidget();
        var renewWidgetAfterSend = function (widget) {
        	var new_widget = createNewMessageWidget(null, renewWidgetAfterSend, mainWidgetId);
            widget.before(new_widget).detach();
            $("textarea", new_widget).BetterGrow({
            	initial_height: 36,
            	on_resize: function (new_height) {
            		$("div.messagebox", new_widget).height(new_height);
            		sizeSendButton(new_widget);
            	}
            });
            sizeSendButton(new_widget);
        }
        var new_widget = createNewMessageWidget(null, renewWidgetAfterSend, mainWidgetId);
        lj("#newmessage").replaceWith(new_widget);
        sizeSendButton(new_widget);
        
        $("textarea", new_widget).BetterGrow({
        	initial_height: 36,
        	on_resize: function (new_height) {
        		$("div.messagebox", new_widget).height(new_height);
        		sizeSendButton(new_widget);
        	}
        });

        lj("#address").keypress(function (event) {
            if (event.keyCode == '13') {
                geoCodeAddress();
            }
        });
        lj("#lookup_address").click(geoCodeAddress);

        lj("#open_address_lookup_dialog").click(function () { 
            try {
                new google.maps.Geocoder();
                address_lookup_dialog.dialog('open'); 
            } catch (err) {
                // We need to load google maps first
                mctracker.showProcessing();
                mctracker.mapsLoadedCallbacks.push(function () {
                    mctracker.hideProcessing();
                    address_lookup_dialog.dialog('open');
                });
                mctracker.loadGoogleMaps();
            }
        });

        button_detail_dialog = lj("#button_details_dialog").dialog({
            width: 500,
            autoOpen: false,
            title: "Configure button details",
            resizable: false,
            modal: true,
            open: function () { lj("#magic_action_error", "dc").hide(); },
            buttons: {
                'Cancel': function () {
                    button_detail_dialog.dialog('close');
                },
                'Ok': function () {
                    var action = lj("#magic_action", "dc").val().replace(" ", "");
                    if (!(action == '' || action.match("^(tel://|geo://|http://|https://|confirm://)"))) {
                        lj("#magic_action_error", "dc").show();
                        return;
                    }
                    var checked = lj("#sender_selection", "dc").prop("checked");
                    var button_properties = $(this).data('button_properties');
                    var thisButton = $("span[button_id='" + button_properties.id + "']");
                    if (checked) {
                        var context = thisButton.parent().parent();
                        $("span.selectedmessagebutton", context).removeClass("selectedmessagebutton").addClass("messagebutton");
                        for (var b in button_properties.message.buttons) {
                            button_properties.message.buttons[b].my_selection = false;
                        }
                        thisButton.removeClass("messagebutton").addClass("selectedmessagebutton");
                    } else {
                        thisButton.removeClass("selectedmessagebutton").addClass("messagebutton");
                    }
                    button_properties.action = action;
                    button_properties.my_selection = checked;
                    button_detail_dialog.dialog('close');
                }
            }
        }).attr('dialog', container);
        address_lookup_dialog = lj("#address_lookup_dialog").dialog({
            width: 300,
            autoOpen: false,
            title: "Lookup gps coordinates",
            resizable: false,
            modal: true,
            open: function () {
                address_gps_coords = null;
                lj("#address_error", "dc").text("");
                lj("#address", "dc").text("");
                lj("#map", "dc").hide();
            },
            buttons: {
                'Cancel': function () {
                    address_lookup_dialog.dialog('close');
                },
                'Ok': function () {
                    if (!address_gps_coords) {
                        lj("#address_error", "dc").text("no gps coordinates to return");
                        return;
                    };
                    lj("#magic_action", "dc").val("geo://" + address_gps_coords.lat() + "," + address_gps_coords.lng());
                    address_lookup_dialog.dialog('close');
                }
            }
        }).attr('dialog', container);
        button_confirmation_dialog = lj("#button_confirmation_dialog").dialog({
            width:300,
            autoOpen: false,
            title: "Please confirm",
            resizable: false,
            modal: true,
            buttons: {
                'No': function () {
                    button_confirmation_dialog.dialog('close');
                },
                'Yes': function () {
                    var message = jQuery.data(button_confirmation_dialog, "message");
                    var button_id = jQuery.data(button_confirmation_dialog, "button_id");
                    ackMessage(message, getButtonById(message, button_id), function (message) {
                        if (message.parent_key) {
                            var parentMessage = messagesByIndex[message.parent_key];
                            parentMessage.threadNeedsMyAnswer = parentMessage.threadNeedsMyAnswer && threadNeedsAnswer(parentMessage);
                            if (parentMessage.threadNeedsMyAnswer) {
                                dismissConversation(message.parent_key, function () {
                                    updateMessageDisplay(message);
                                });
                            }
                        }
                        updateMessageDisplay(message);
                    });
                    button_confirmation_dialog.dialog('close');
                }
            }
        }).attr('dialog', container);
        lj("#older_messages").click(loadOlderMessages);
    };

    var geoCodeAddress = function () {
        lj("#address_error", "dc").text("");
        var address = lj("#address", "dc").val();
        var geoCoder = new google.maps.Geocoder();
        geoCoder.geocode({ 'address': address }, function (results, status) {
            if (status == google.maps.GeocoderStatus.OK) {
                lj("#map", "dc").show();
                address_gps_coords = results[0].geometry.location
                lj("#address_result", "dc").text("lat: " + address_gps_coords.lat() + " lon: " + address_gps_coords.lng());
                lj("#map_result", "dc")
                    .text("check result")
                    .attr('href', 'http://maps.google.com/maps?q=geo%20code%20result@' + address_gps_coords.lat() + ',' + address_gps_coords.lng());
            } else {
                lj("#address_result", "dc").text("The address could not be geocoded.");
            }
        });
    };

    var autoCompleteMembers = function (request, callback) {
        var result = [];
        for (var fi in friendCache) {
            var friend = friendCache[fi];
            if (friend.type != FRIEND_TYPE_USER)
                continue;
            if (friend.email.toLowerCase().match(request.term.toLowerCase()) || (friend.name && friend.name.toLowerCase().match(request.term.toLowerCase()))) {
                result.push({
                    value: friend.email,
                    label: getFriendName(friend),
                    friend: friend
                });
            }
        }
        callback(result);
    };

    var memberSelected = function (event, ui) {
        addRecipient(lj("div#" + mainWidgetId), ui.item.friend, true);
        $(this).val('');
        ui.item.value = '';
    };

    var createButton = function (message, caption, widget) {
        var button_properties = {
            id: mctracker.uuid(),
            caption: caption,
            action: null,
            my_selection: false,
            message: message
        };
        message.buttons.push(button_properties);
        var button = lj("#button_widget").clone(true).attr('id', null).show();
        $(".mcbuttontext", button).text(caption).click(function () {
            lj("#magic_action", "dc").val(button_properties.action);
            lj("#sender_selection", "dc").prop("checked", button_properties.my_selection);
            button_detail_dialog.data('button_properties', button_properties);
            button_detail_dialog.dialog('open');
        });
        $("*", button).data('button_properties', button_properties);
        button.attr("button_id", button_properties.id);
        var badge = $("img.messagebutton_badge_delete", button);
        badge.click(function () {
            for (var b in message.buttons) {
                if (message.buttons[b] == button_properties) {
                    message.buttons.splice(b, 1);
                    break;
                }
            }
            button.fadeOut('slow', function () {
                button.detach();
                sizeSendButton(widget);
            });
        });
        button.mouseenter(function () {
            badge.fadeIn('slow');
        }).mouseleave(function () {
            badge.fadeOut('slow');
        });
        return button;
    };

    var schrink = function (html, spans, amount) {
        for (var index in spans) {
            var class_ = "span-" + spans[index];
            var new_class = "span-" + (spans[index] - amount);
            $("." + class_, html).removeClass(class_).addClass(new_class);
            if (html.hasClass(class_))
                html.removeClass(class_).addClass(new_class);
        }
        return html;
    };

    var loadOlderMessages = function () {
        var timestamp = 0;
        if (messages.length != 0) {
            timestamp = messages[messages.length - 1].threadTimestamp;
        }
        mctracker.call({
            url: "/mobi/rest/messaging/get",
            data: {
                cursor: messages_cursor
            },
            success: function (data, textStatus, XMLHttpRequest) {
                messages_cursor = data.cursor;
                $.each(data, function (i, message) {
                    messages.push(message);
                });
                addMessagesToScreen(data.messages);
            },
            error: mctracker.showAjaxError
        });
    };
    
    var addMessagesToScreen = function (data) {
        var messageInsertionPoint = lj("#lastMessagePlaceholder");
        for (var m in data) {
            var message = data[m];
            messagesByIndex[message.key] = message;
            flagRootmessageAndSubmessagesAsReceived(message)
            renderRootMessage(message, true, function (html) {
            	messageInsertionPoint.before(html);
            });
        }
        if (data.length != messages_limit) {
            lj("#lastMessagePlaceholder").hide();
        }
    };
    
    var flagRootmessageAndSubmessagesAsReceived = function (message) {
        var member = getMyMemberStatus(message);
        if (member && (member.status & STATUS_RECEIVED) != STATUS_RECEIVED) {
            messageReceived(message);
        }
        $.each(message.messages, function (index, message) {
            member = getMyMemberStatus(message);
            if (member && (member.status & STATUS_RECEIVED) != STATUS_RECEIVED) {
                messageReceived(message);
            }
        });
    };
    
    var needsAnswer = function (message) {
        var myMember = getMyMemberStatus(message);
        return (message.flags & FLAG_LOCKED) != FLAG_LOCKED 
            && myMember
            && (myMember.status & STATUS_ACKED) != STATUS_ACKED
            && myMember.member != message.sender;
    };
    
    var threadNeedsAnswer = function (parentMessage) {
        var addDismissThreadButton = (parentMessage.flags & FLAG_ALLOW_DISMISS) == FLAG_ALLOW_DISMISS && needsAnswer(parentMessage);
        if (!addDismissThreadButton) {
            $.each(parentMessage.messages, function (i, child) {
                if ((child.flags & FLAG_ALLOW_DISMISS) == FLAG_ALLOW_DISMISS && needsAnswer(child)) {
                    addDismissThreadButton = true;
                    return false; // break
                }
            });
        }
        return addDismissThreadButton;
    };

    var renderRootMessage = function (message, renderChildMessages, htmlReturner) {
    	if (message.sender != "dashboard@rogerth.at" || $.browser.msie)
    		message.branding = null;
    	console.log("Rendering message: "+message.key);
        addHelperFlags(message);
        var html = $.tmpl($("#tab_without_menu #root_message_template").html().replace("<!--","").replace("-->",""), {
            message: message,
            needsAnswer: needsAnswer(message),
            addDismissThreadButton: message.threadNeedsMyAnswer && message.messages.length == 0
        });
        if (htmlReturner) {
        	var sub = htmlReturner(html);
        	if (sub)
        	    html=sub;
        }
        var myMemberStatus = getMemberStatus(message, loggedOnUserEmail);
        var expanded = (myMemberStatus.status & STATUS_ACKED) != STATUS_ACKED;
        // render root message
        renderMessage(message, html, !renderChildMessages);
        var messagesPlaceholder = $("#messagesPlaceholder", html);
        if (renderChildMessages) {
            // render child messages
        	var childMessageHiddenCount = 0;
            $.each(message.messages, function (index, childMessage) {       
            	if (!expanded) {
                    var myMemberStatus = getMemberStatus(childMessage, loggedOnUserEmail);
                    expanded = (myMemberStatus.status & STATUS_ACKED) != STATUS_ACKED;
            	}
                if ( !expanded && index < message.messages.length - 2 && ! messageIsExpanded(message)) {
                	messagesPlaceholder.before($("<div></div>")
                			.addClass("hidden_child_message")
                			.attr("child_message_key", childMessage.key)
                			.attr("parent_message_key", childMessage.parent_key));
                	childMessageHiddenCount++;
                } else {
                    renderChildMessage(childMessage, false, function (childMessageHtml) {
                    	messagesPlaceholder.before(childMessageHtml);
                    });                	
                }
            });
            var vam = $("#viewAllMessages", html)
                .text("View all "+message.messages.length+" messages")
                .click( function () {
                    expandedMessages[message.key] = true;
                    vam.slideUp('slow', function () {$("#messagesToolbar", html).remove();});
                    $("div.hidden_child_message", html).each(function (index, element) {
                    	var parentMessage = messagesByIndex[$(element).attr('parent_message_key')];
                    	var childMessage = null;
                    	var childMessageKey = $(element).attr('child_message_key');
                    	$.each(parentMessage.messages, function (index, message) {
                    		if (message.key == childMessageKey) {
                    			childMessage = message;
                    		}
                    	});
                        renderChildMessage(childMessage, false, function (childMessageHtml) {
                        	$(element).replaceWith(childMessageHtml);
                        });
                    });
                });
            if ( !childMessageHiddenCount ) {
                $("#messagesToolbar", html).remove();
            }
        }
        // Add member summary
        var membersWithoutSender = mctracker.filter(message.members, function(m) {return m.member != message.sender;});
        $("span.member-summary", html)
            .text(', '+$.map(membersWithoutSender, function (m) {return getFriendName(getFriendByEmail(m.member));}).join(", "))
            .ThreeDots({max_rows:1});
        return html;
    };
    
    var enhanceMemberInformation = function (message) {
        var received = 0;
        var answered = 0;
        var isMember = false;
        var memberCount = 0;
        $.each(message.buttons, function (index, button) {
            button.members = [];
            $.each(message.members, function (index,member) {
                if (member.button_id == button.id) 
                    button.members.push(member);
            });            
        });
        $.each(message.members, function (index,member) {
            member.textstatus = "not_yet"; 
            if (member.member == loggedOnUserEmail) {
                isMember = true;
                message.myMember = member
            }
            member.isSender = member.member == message.sender;
            member.showInMembers = ! member.isSender || STATUS_ACKED == (member.status & STATUS_ACKED);
            member.hasReceived = (member.status & STATUS_RECEIVED) == STATUS_RECEIVED;
            member.timestatus = '';
            if (member.hasReceived) {
                received ++;
                member.received_at = mctracker.formatDate(member.received_timestamp);
                member.textstatus = "received"; 
                member.timestatus = '@ ' + mctracker.formatDate(member.received_timestamp);
            }
            member.hasAcked = (member.status & STATUS_ACKED) == STATUS_ACKED;
            if (member.hasAcked) {
                member.answer = getAnswer(message, member);
                answered ++;
                member.answered_at = mctracker.formatDate(member.acked_timestamp);
                member.textstatus = "acknowlegded"; 
                member.timestatus = '@ ' + mctracker.formatDate(member.acked_timestamp);
            }
            if (member.showInMembers) memberCount ++;
        });
        message.received = received;
        message.answered = answered;
        message.numberOfMembers = memberCount;
        return isMember;
    };
    
    var messageIsExpanded = function (message) {
        return expandedMessages[message.key];
    };
    
    var dismissConversation = function (threadKey, afterSubmit) {
        var timestamp = mctracker.nowUTC();
        var parentMessage = messagesByIndex[threadKey];
        if (! parentMessage.threadNeedsMyAnswer) {
            console.log('WARNING: Not dismissing conversation because it does not need my answer');
            return;
        }
        var ackedMessages = [];
        var ackedMessageKeys = [];
        var run = function (message) {
            if (needsAnswer(message) && (message.flags & FLAG_ALLOW_DISMISS) == FLAG_ALLOW_DISMISS) {
                ackedMessageKeys.push(message.key);
                ackedMessages.push(message);
            }
        };

        run(parentMessage);
        $.each(parentMessage.messages, function (i, message) {
            run(message);
        });

        mctracker.call({
            hideProcessing: true,
            url: "/mobi/rest/messaging/dismiss_conversation",
            type: "POST",
            data: {
                data: JSON.stringify({
                    parent_message_key: threadKey,
                    message_keys: ackedMessageKeys,
                    timestamp: timestamp
                })
            },
            success: function (data, textStatus, XMLHttpRequest) {
            }
        });

        // Update Model
        parentMessage.threadNeedsMyAnswer = false;
        $.each(ackedMessages, function (i, msg) {
            var ms = getMyMemberStatus(msg);
            ms.status |= STATUS_ACKED;
            ms.acked_timestamp = timestamp;
            ms.button_id = null;
        });
        // Update UI
        $.each(ackedMessages, function (i, msg) {
            updateMessageDisplay(msg);
        });

        if (afterSubmit) {
            afterSubmit();
        }
    };

    var addHelperFlags = function (message) {
        if (message.parent_key == null) {
            message.threadNeedsMyAnswer = threadNeedsAnswer(message);
        }
        var isMember = enhanceMemberInformation(message);
        message.isLocked = (message.flags & FLAG_LOCKED) == FLAG_LOCKED;
        message.enableButtons = ! message.isLocked && isMember;
        if (message.message)
        	message.htmlizedMessage = $("<div></div>").text(message.message).html().replace(/\n/g, "<br>");
        else
        	message.message = "";
        message.canReply = (message.flags & FLAG_ALLOW_REPLY) == FLAG_ALLOW_REPLY || (message.flags & FLAG_ALLOW_REPLY_ALL) == FLAG_ALLOW_REPLY_ALL;
    };

    var renderChildMessage = function (message, replace, htmlReturner) {
    	if (message.sender != "dashboard@rogerth.at")
    		message.branding = null;
    	console.log("Rendering message: " + message.parent_key + " " + message.key);
        addHelperFlags(message); 
        var na = needsAnswer(message);
        var parentMessage = messagesByIndex[message.parent_key];
        if (!parentMessage)
        	return;
        var addDismissThreadButton = parentMessage.threadNeedsMyAnswer && message == parentMessage.messages[parentMessage.messages.length - 1];
        var html = $.tmpl($("#tab_without_menu #child_message_template").html().replace("<!--","").replace("-->",""),
                { message: message, needsAnswer: na, addDismissThreadButton: addDismissThreadButton });
        if (htmlReturner) {
        	var sub = htmlReturner(html);
        	if (sub)
        	    html=sub;
        }
        html = renderMessage(message, html, true);
        if (replace) {
        	var m = getMessageByKey(message.parent_key);
        	if (m)
        		m.updateMemberStatusses();
        }
        $("span#answered, span#received", html).mouseenter(function(e) {
            $("#answered_popup, #received_popup", $(this)).fadeIn('slow').mouseleave(function(e){
                $(this).fadeOut('slow');
            });
        });
        return html;
    };

    var recentTypingActivity = function () {
    	var recent = 0;
    	$.each(reply_boxes_opened, function (index, widget) {
    		var last_typing = new Number(widget.attr('last_typing'));
    		if (last_typing > recent)
    			recent = last_typing;
    	});
    	return new Date().getTime() - recent < 5000;
    };

    var replyWidgetClosed = function (reply_link, widget){
    	var index = mctracker.indexOf(reply_boxes_opened, widget);
    	reply_boxes_opened.splice(index, 1);
    	if (! recentTypingActivity()) {
    		$.each(pending_updates, function (i, update) {
    			processMessage(update, true);
    		});
    		pending_updates = [];
    		$("#pending").fadeOut('slow');
    	}
    	reply_link.text("reply");
    };
    
    var markThreadAsRead = function (parentMessage) {
        var dirtyMessageKeys = [];
        var dirtyMessages = [];
        if (is_message_dirty(parentMessage)) {
            dirtyMessages.push(parentMessage);
            dirtyMessageKeys.push(parentMessage.key);
        }
        for (var i in parentMessage.messages) {
            if (is_message_dirty(parentMessage.messages[i])) {
                dirtyMessages.push(parentMessage.messages[i]);
                dirtyMessageKeys.push(parentMessage.messages[i].key);
            }
        }
        if (dirtyMessages.length == 0)
            return;

        mctracker.call({
            hideProcessing: true,
            url: "/mobi/rest/messaging/mark_messages_as_read",
            type: "POST",
            data: {
                data: JSON.stringify({
                    message_keys: dirtyMessageKeys,
                    parent_message_key: parentMessage.key
                })
            },
            success: function (data, textStatus, XMLHttpRequest) {}
        });
        $.each(dirtyMessages, function (i, message) {
            var myMember = getMyMemberStatus(message);
            myMember.status |= STATUS_READ;
        });
        decrease_p2p_badge();
    };

    var renderMessage = function (message, html, renderaschild) {
        // render avatars
        var avatar = function (resize, for_member_overview) {
            return function () {
                var div = $(this);
                var email = div.attr('friend') || div.attr('sender') || div.attr('member');
                var friend = getFriendByEmail(email);
                var member = getMemberStatus(message, email);
                var badge_url = '';
                if (for_member_overview) {
                	if (message.sender == email) 
                		member = {status: STATUS_ACKED};
                	else
                		member = JSON.parse(JSON.stringify(member));
                	$.each(message.messages, function (i, cmessage) {
            			var status = cmessage.sender == email ? STATUS_ACKED : getMemberStatus(cmessage, email).status;
            			if (status < member.status) {
            				member.status = status;
            			}
                	});
	                if ((member.status & STATUS_ACKED) == STATUS_ACKED) {
	                    badge_url = "/static/images/site/ackn.png";
	                } else if ((member.status & STATUS_RECEIVED) == STATUS_RECEIVED) {
	                	badge_url = "/static/images/site/accept.png";
	                } else {
	                	badge_url = "/static/images/site/no-rec.png";
	                }
                }
                var isMyFriend = isFriend(email);
                var tooltip = isMyFriend ? mctracker.htmlEncode((getFriendName(friend, true))) : email;
                if (member)
                    tooltip += ' ' + member.timestatus;
                div.avatar({
                    friend: friend,
                    left: true,
                    resize: resize,
                    tooltip: tooltip,
                    badge_url: badge_url,
                    click: function () {
                        if (! isMyFriend && email != loggedOnUserEmail) {
                            inviteFriend(email);
                        }
                    }
                });
            }
        };
        $(".mcmessagecontent div[friend]", html).each(avatar(true, false));
        if (renderaschild) {
            $(".mcmessagecontent div[sender]", html).each(avatar(renderaschild, false));
        } else {
            $(".mcrootsenderavatar div[sender]", html).each(avatar(false, false));
            message.updateMemberStatusses = function () {
            	lj("div[messagekey="+message.key+"] .mcthreadsummary div[member]").empty().each(avatar(true, true));
            };
            message.updateMemberStatusses();
        }
        // render timestamp
        $("span.mcmessagetimestamp", html).text(mctracker.formatDate(Math.abs(message.timestamp)));
        // render sender
        $("span.mcmessagesender", html).text(getFriendName(getFriendByEmail(message.sender)));
        // Add click handlers
        $("div.messagebutton.mcclickable, div.messagebutton.mcrogerthat", html).each(getClickHandlerForQuickReplyButtons(message, html));
        
        var messagemembers = $("div.mcmessagemembers", html);
       	var mcmc = $("div.mcmessagecontent", html);
        var message_members_height = messagemembers.height();
        
        // handle branded messages
        if (message.branding) {
            var iframe = $("iframe", html).load(function (){
                if (iframe.attr('mcloaded') == 'true')
                    return;
                iframe.attr('mcloaded','true');
                $("nuntiuz_message", $(this).contents()).replaceWith($('<span>'+message.htmlizedMessage+'</span>'));
                $("nuntiuz_timestamp", $(this).contents()).replaceWith($('<span>'+mctracker.formatDate(message.timestamp)+'</span>'));
                $("meta[property='rt:style:background-color']", $(this).contents()).each(function() {
                	if (message.parent_key == null)
                		$(".mcrootmessage", html).css('background-color', $(this).attr('content'));
                	else
                		$(".mcmessagecontent", html).css('background-color', $(this).attr('content'));
                });
                $("meta[property='rt:style:color-scheme']", $(this).contents()).each(function() {
                	$(".mcmessagecontent", html).addClass('mccolorscheme'+ $(this).attr('content'));
                });
                var body = this.contentWindow.document.body;
                setTimeout(function () {
                    var iframe_height = $(body).height();
                    iframe.height(iframe_height);
                    setTimeout(function () {
                        iframe_height = body.scrollHeight;
                        iframe.height(iframe_height);
                        console.log(message.parent_key + " - " + message.key + "\nmessage_members_height: " + message_members_height +"\niframe_height: " + iframe_height);
                        var new_height = iframe_height > message_members_height ? iframe_height : (message_members_height + 5);
                        console.log("Setting iframe height to " + new_height);
                        iframe.height(new_height);
                        html.removeClass('mcoutofscreen');
            			if ($.browser.msie) {
                    		message_members_height = messagemembers.height();
            				$("#msg", mcmc).css('margin-top', "-" + message_members_height + "px");
            			}
                    }, 100);
                }, 100);
            });
        } else {
        	var mcmc_height = mcmc.height();
        	if (message_members_height + 5 > mcmc_height)
        		mcmc.height(message_members_height + 5);
        }
        // make lock image clickable
        var messageLocked = (message.flags & FLAG_LOCKED) == FLAG_LOCKED;
        var locked = $(".mclock", html);
        if (!messageLocked && loggedOnUserEmail == message.sender) {
            locked.addClass("action-link").attr('title', 'Lock this message').click(function () {
                var request = {
                    message_key: message.key,
                    message_parent_key: message.parent_key
                };
                mctracker.call({
                	"hideProcessing":true,
                    url: "/mobi/rest/messaging/lock",
                    type: "POST",
                    data: {
                        data: JSON.stringify({
                            request: request
                        })
                    },
                    success: function (data, textStatus, XMLHttpRequest) {
                    },
                });
                message.flags = message.flags | FLAG_LOCKED;
                updateMessageDisplay(message);
            });
        } else if (messageLocked) {
            locked.show();
        } else {
            locked.hide();
        }
        // render reply button
        var showReplyBox = function () {
        	var widget = $("div.messaging_widget", html);
            if (widget.length == 0) {
                var newMessageWidget = createNewMessageWidget(message.key, function () {
                    newMessageWidget.detach();
                    replyWidgetClosed(reply, newMessageWidget);
                    showReplyBox();
                });
            	reply_boxes_opened.push(newMessageWidget); 
                schrink(newMessageWidget, [9, 13, 17, 18], 1);
                $("#recipients", newMessageWidget).hide();
                var newMessage = newMessageWidget.data('message');
                for (var m in message.members) {
                    var member = message.members[m];
                    if (member.member != loggedOnUserEmail) {
                        newMessage.members.push({ email: member.member });
                    }
                }
                if (loggedOnUserEmail != message.sender) {
                    newMessage.members.push({ email: message.sender });
                }
                $("div.replyPlaceholder", html).append(newMessageWidget);
                $("div.replyPlaceholder textarea", html).BetterGrow({
                	initial_height: 36,
                	on_resize: function (new_height) {
                		$("button.newmessage_send", newMessageWidget).height(new_height+54);
                	}
                });
                $("button.newmessage_send", newMessageWidget).height(36+54);
                reply.text('hide');
                $("#newmessage_message", html).focus();            
            } else {
                reply.text('reply');
                widget.slideUp(function(){
                	widget.detach();                	
                	replyWidgetClosed(reply, widget);
                });
            }
        };
        
        var reply = $("#reply", html).unbind('click').click(showReplyBox);
        renderFormWidget("#msg_widget", message, html);
        
        if (!message.parent_key) {
            $("#delete", html).click(function () {
            	mctracker.call({
            		url: '/mobi/rest/messaging/delete_conversation',
            		hideProcessing: true,
            		type: 'post',
            		data: {
            			data: JSON.stringify ({
            				parent_message_key: message.key
            			})
            		},
            		success: function () {}
            	});
            	html.slideUp('slow', function () {html.remove();});
            	removeMessageFromCaches(message.key);
            });
        }

        $('#msg', html).appear(function () {
            var parentMessage = messagesByIndex[message.parent_key || message.key];
            // Check if message is the last message of the thread
            var isLastThreadMessage = false;
            if (message.parent_key == null) {
                isLastThreadMessage = message.messages.length == 0;
            } else {
                isLastThreadMessage = message.key == parentMessage.messages[parentMessage.messages.length - 1].key;
            }
            if (isLastThreadMessage && is_thread_dirty(parentMessage)) {
                if (selectedTab == TAB_FRIENDS_AND_ME) {
                    markThreadAsRead(parentMessage);
                } else {
                    threadsToBeMarkedAsRead.push(parentMessage);
                }
            }
        }, {one: true, threshold: -30});

        return html;
    };

    var getClickHandlerForQuickReplyButtons = function (message, html) {
        return function () {
            var button_id = $(this).attr("button");
            button_id = button_id == "" ? null : button_id;
            $(this).click(function () {
                var button = getButtonById(message, button_id);

                if (button && button.action && button.action.match(/^confirm:\/\//)) {
                    jQuery.data(button_confirmation_dialog, "message", message);
                    jQuery.data(button_confirmation_dialog, "button_id", button_id);
                    lj("#button_confirmation_text", "dc").html(button.action.substr("confirm://".length).replace(/\n/g, "<br>"));
                    button_confirmation_dialog.dialog('open');
                } else if (button) {
                    ackMessage(message, button, function (message) {
                        if (message.parent_key) {
                            var parentMessage = messagesByIndex[message.parent_key];
                            parentMessage.threadNeedsMyAnswer = parentMessage.threadNeedsMyAnswer && threadNeedsAnswer(parentMessage);
                            if (parentMessage.threadNeedsMyAnswer) {
                                dismissConversation(message.parent_key, function () {
                                    updateMessageDisplay(message);
                                });
                            }
                        }
                        updateMessageDisplay(message);
                    });
                } else {
                    // Roger that button
                    dismissConversation(message.parent_key || message.key);
                }
            });
        }
    };
    
    var getButtonById = function (message, button_id) {
        var foundButton = null;
        $.each(message.buttons, function (i, button) {
            if (button.id == button_id) {
                foundButton = button;
                return false;
            };
        });
        return foundButton;
    };

   var getAnswer = function (message, member) {
        if (member.status != 3)
            return "&nbsp;";
        if (member.custom_reply) {
            return member.custom_reply;
        } else if (member.button_id) {
            for (var b in message.buttons) {
                var button = message.buttons[b];
                if (button.id == member.button_id) {
                    return button.caption;
                }
            }
        } else return "";
    };

    var getMessageByKey = function (message_key) {
    	return mctracker.get(messages, function (m, i) {return m.key == message_key;});
    };
    
    var removeMessageFromCaches = function (message_key) {
    	messagesByIndex[message_key] = undefined;
    	var index = false;
    	$.each(messages, function (i, message) {
    		if (message.key == message_key)
    			index = i;
    		return false; // break loop
    	});
    	if (index !== false)
    		messages.splice(index, 1);
    };

    var addNewMessage = function (message, render) {
        messagesByIndex[message.key] = message;
        // Add a messages list if message has no parent_key
        if (!message.parent_key) {
            if (message.messages == undefined)
                message.messages = [];
            // Add message to loaded messages
            messages.unshift(message);
            if (render) {
                // Add message to screen
                renderRootMessage(message, true, function (html) {
                    lj("#newIncommingMessagePlaceholder").after(html);
                });
            }
        } else {
            var rootMessage = getMessageByKey(message.parent_key);
            if (rootMessage) {
                rootMessage.messages.push(message);
                if (rootMessage.threadTimestamp < Math.abs(message.threadTimestamp)) {
                    rootMessage.threadTimestamp = Math.abs(message.threadTimestamp);
                }
                rootMessage.threadNeedsMyAnswer = rootMessage.threadNeedsMyAnswer || needsAnswer(message);
                var rootMessageDisplay = lj("div[messagekey='" + rootMessage.key + "']");
                $(".mcrogerthat", rootMessageDisplay).hide();
                renderChildMessage(message, false, function (childMessageHtml) {
                    $("#messagesPlaceholder", rootMessageDisplay).before(childMessageHtml);
                });
            } else {
                mctracker.call({
                	hideProcessing:true,
                    url: '/mobi/rest/messaging/get_root_message',
                    data: {
                        message_key: message.parent_key
                    },
                    success: function (data, textStatus, XMLHttpRequest) {
                        addNewMessage(data, true);
                    },
                    error: mctracker.showAjaxError
                });
            }
        }
        messageReceived(message);
    };
    
    var messageReceived = function (message) {
        if (message.sender && message.sender == loggedOnUserEmail)
            return;
        var myMember = getMyMemberStatus(message);
        if (! myMember)
            return;
        if ((myMember.status & STATUS_RECEIVED) == STATUS_RECEIVED)
            return;
        var timestamp = mctracker.nowUTC();
        mctracker.call({
        	hideProcessing: true,
            url: "/mobi/rest/messaging/received",
            type: "POST",
            data: {
                data: JSON.stringify({
                    request: {
                        message_key: message.key,
                        message_parent_key: message.parent_key,
                        received_timestamp: timestamp
                    }
                })
            },
            success: function (data, textStatus, XMLHttpRequest) {
            }
        });
        for (var m in message.members) {
            var member = message.members[m];
            if (member.member == loggedOnUserEmail) {
                member.received_timestamp = timestamp;
                member.status = member.status | STATUS_RECEIVED;
                updateMessageDisplay(message);
                break;
            }
        }
    };
    
    var updateMessageDisplay = function (message) {
        var currentMessageDisplay = lj("div[messagekey='" + message.key + "']");
        if (currentMessageDisplay.length == 0)
        	return;
        if (message.parent_key) {
            // child message
            var html = renderChildMessage(message, true, function (childMessageHtml) {
                if (message.branding) {
                	$("div.mcmessagemembers", currentMessageDisplay).empty().append($("div.mcmessagemembers", childMessageHtml).children());
                	$("div.msg_widget", currentMessageDisplay).empty().append($("div.msg_widget", childMessageHtml).children());
                } else
                    $("div.mcmessagecontent", currentMessageDisplay).empty().append($("div.mcmessagecontent", childMessageHtml).children());
                return currentMessageDisplay;
            });
            if ((message.myMember.status & STATUS_ACKED) == STATUS_ACKED)
            	$("div.mcmessagecontent", currentMessageDisplay).removeClass('mcneedsanswer');
            var pmessage = getMessageByKey(message.parent_key);
            pmessage.updateMemberStatusses();            
        } else {
            // root message
            var html = renderRootMessage(message, false, function (rootMessageHtml) {
                if (message.branding) {
                    $("div.mcrootmessage > div.mcmessagecontent > div.mcmessagemembers", currentMessageDisplay).empty().append($("div.mcmessagemembers", rootMessageHtml).children());
                    $("div.mcrootmessage > div.mcmessagecontent > div.msg_widget", currentMessageDisplay).empty().append($("div.msg_widget", rootMessageHtml).children());
                } else
                    $("div.mcrootmessage > div.mcmessagecontent", currentMessageDisplay).empty().append($("div.mcmessagecontent", rootMessageHtml).children());
                return currentMessageDisplay;
            });
            if ((message.myMember.status & STATUS_ACKED) == STATUS_ACKED)
            	$("div.mcrootmessage > div.mcmessagecontent", currentMessageDisplay).removeClass('mcneedsanswer');
            message.updateMemberStatusses();
        }
        mctracker.loopContainers(function(container, html, intf) {
           if (intf && intf.updateMessageDisplay)
               intf.updateMessageDisplay(message);
        });
    };
    
    var updateFormMessage = function (update) {
        var run = function (message) {
            if (message.key == update.message_key) {
                if (update.result)
                    updateFormWithResult(message, update.result);
                for (var m in message.members) {
                    var member = message.members[m];
                    member.status = STATUS_ACKED | STATUS_RECEIVED;
                    member.received_timestamp = update.received_timestamp;
                    member.acked_timestamp = update.acked_timestamp;
                    member.button_id = update.button_id;
                    member.custom_reply = null;
                }
                updateMessageDisplay(message);
                return true;
            }
            return false;
        };
        // lookup message in message cache
        var message = messagesByIndex[update.message];
        if (message && run(message))
            return;
        // not found in the index, we have to loop :(
        for (var m in messages) {
            var message = messages[m];
            if (run(message))
                return;
            for (var cm in message.messages) {
                var childMessage = message.messages[cm];
                if (run(childMessage))
                    return;
            }
        }
    };

    var updateMessage = function (update) {
        var run = function (message) {
            if (message.key == update.message) {
                for (var m in message.members) {
                    var member = message.members[m];
                    if (member.member == update.member) {
                        member.status = update.status;
                        member.received_timestamp = update.received_timestamp;
                        member.acked_timestamp = update.acked_timestamp;
                        member.button_id = update.button_id;
                        member.custom_reply = update.custom_reply;
                        updateMessageDisplay(message);
                        if (update.member != loggedOnUserEmail && (update.button_id || update.custom_reply)) {
                            var mp = message.message;
                            if (mp && mp.length > 30) {
                                mp = "<br>&gt; " + mp.substring(0,30) + "...";                      
                            } else if ( mp )
                                mp = "<br>&gt; " + mp;
                            else mp = "";
                            $.gritter.add({
                                title: 'Message reply',
                                sticky: false,
                                image: '/unauthenticated/mobi/cached/avatar/' + getFriendByEmail(member.member).avatarId,
                                text: getAnswer(message, member) + mp
                            });
                        }
                        return true;
                    }
                }
            }
            return false;
        }
        // lookup message in message cache
        var message = messagesByIndex[update.message];
        if (message && run(message))
            return;
        // not found in the index, we have to loop :(
        for (var m in messages) {
            var message = messages[m];
            if (run(message))
                return;
            for (var cm in message.messages) {
                var childMessage = message.messages[cm];
                if (run(childMessage))
                    return;
            }
        }
    };
    
    var messageLocked = function (request) {
        var run = function (message) {
            if (message && message.key == request.message_key) {
                message.flags |= FLAG_LOCKED;
                message.members = request.members;
                updateMessageDisplay(message);
                return true;
            }
            return false;
        }
        // lookup message in message cache
        if (run(messagesByIndex[request.message_key]))
            return;
        // not found in the index, we have to loop :(
        for (var m in messages) {
            var message = messages[m];
            if (run(message))
                return;
            for (var cm in message.messages) {
                var childMessage = message.messages[cm];
                if (run(childMessage))
                    return;
            }
        }
    };
       
    var processMessage = function (data, force) {
    	if (recentTypingActivity() && ! force) {
    		pending_updates.push(data);
    		var pending = $("#pending");
    		if (pending.css('display') == "none")
    			pending.fadeIn('slow');
    		return;
    	}
        if (data.type == 'rogerthat.messaging.newMessage') {
        	var sender = getFriendByEmail(data.message.sender);
            if (sender.type != FRIEND_TYPE_SERVICE) {
                addNewMessage(data.message, true);
                recalculate_p2p_badge();
            }
        } else if (data.type == 'rogerthat.messaging.conversationDeleted') {
        	lj("div.topic[messagekey='"+data.parent_message_key+"']").fadeOut('slow', function() {$(this).remove();});
        } else if (data.type == 'rogerthat.messaging.memberUpdate') {
            updateMessage(data.update);
            if (data.update.member == loggedOnUserEmail)
                recalculate_p2p_badge();
        } else if (data.type == 'rogerthat.messaging.formUpdate') {
            updateFormMessage(data.update);
        } else if (data.type == 'rogerthat.messaging.messageLocked') {
            messageLocked(data.request);
            recalculate_p2p_badge();
        } else if (data.type == 'rogerthat.ui.changedTab') {
            if (data.tab == TAB_FRIENDS_AND_ME) {
                $.each(threadsToBeMarkedAsRead, function (i, message) {
                    markThreadAsRead(message);
                });
                threadsToBeMarkedAsRead = [];
            }
        }
    };

    var addRecipient = function (widget, friend, keepCurrentFocus) {
        var message = widget.data('message');
        // Check wether this person is already added as a member
        for (var m in message.members) {
            if (message.members[m] == friend) {
                return;
            }
        }
        // Generate avatar
        var member = $('<div/>');
        member.avatar({
            friend: friend,
            left: true,
            resize: true,
            tooltip: "Remove " + getFriendName(friend, true) + "<br>from this message.",
            click: function () {
                member.fadeOut('slow', function () {
                    member.detach();
                    for (var m in message.members) {
                        if (message.members[m] == friend) {
                            message.members.splice(m, 1);
                            break;
                        }
                    }
                    sizeSendButton(widget);
                });
            }
        }).hide();
        member.addClass("mcrecipient");
        $("#newmessage_members", widget).append(member);
        member.fadeIn('slow');
        message.members.push(friend);
        if (! keepCurrentFocus)
            $("#newmessage_message", widget).focus();
        sizeSendButton(widget);
    };
    
    var sizeSendButton = function (widget) {
        $("button.newmessage_send", widget).css("height", 0);
        $("button.newmessage_send", widget).css("height", widget.height() - 10);
    };

    return function () {
        mctracker.registerMsgCallback(processMessage);

        applyJQueryInUI();

        addMessagesToScreen(messages);

        return {
            addRecipient: function (friend) {
                var widget = lj("div#" + mainWidgetId);
                var screen = $('body');
                if (screen.scrollTop() == 0) {
                    addRecipient(widget, friend);
                } else {
                    screen.animate({ scrollTop: 0 }, 'fast', function () {
                        addRecipient(widget, friend);
                    });
                }
            },
            getMessage: getMessageByKey,
            addMessageToCache: function (msg) {
                if (messagesByIndex[msg.key]) {
                    return false;
                }
                messagesByIndex[msg.key] = msg;
                return true;
            },
            renderRootMessage: renderRootMessage,
            renderChildMessage: renderChildMessage,
            getMyMemberStatus: getMyMemberStatus,
            messageIsExpanded: messageIsExpanded,
            addNewMessage: addNewMessage
        }
    };
}

mctracker.registerLoadCallback("messagingContainer", messagingScript());