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

var messageQueryScript = function(containerId, queryType, queryParam) {

    var lj = mctracker.getLocaljQuery('#' + containerId);
    var MESSAGE_HISTORY = 'message_history';
    var TEXT_SEARCH = 'text_search';
    var messaging = null;
    var cursor = null;
    var STATUS_ACKED = 2;

    var loadScreen = function() {
        var url;
        if (queryType == MESSAGE_HISTORY) {
            url = "/mobi/rest/messaging/history"
        } else {
            console.log("unsupported queryType: " + queryType);
            return;
        }
        mctracker.call({
            url : url,
            type : "POST",
            data : {
                data : JSON.stringify({
                    cursor : cursor,
                    query_param : queryParam
                })
            },
            success : function(data, textStatus, XMLHttpRequest) {
                if (data.messages.length != 20) {
                    lj(".older_messages").hide();
                }
                cursor = data.cursor;
                displayMessages(data.messages);
            }
        });
    };

    var displayMessages = function(messages) {
        var bottom = lj(".bottom");
        $.each(messages, function(i, msg) {
            if (lj("div[messagekey='" + msg.key + "']").length == 0) {
                var cachedMsg = messaging.getMessage(msg.key);
                if (cachedMsg)
                    msg = cachedMsg;
                else
                    messaging.addMessageToCache(msg, false);
                var html = messaging.renderRootMessage(msg, true, function (html) {
                    bottom.before(html);
                });
                updateMessageHtml(msg, html);
                msg.html = html;
            }
        });
    };

    var updateMessageHtml = function(message, html) {
        $("div.mcmessage", html).parent().show();
    };

    var needsAck = function(message) {
        var member = messaging.getMyMemberStatus(message);
        return member && (member.status & STATUS_ACKED) != STATUS_ACKED && message.sender != loggedOnUserEmail;
    }

    var updateMessageDisplay = function(message) {
        if (message.parent_key)
            message = messaging.getMessage(message.parent_key);
        var html = messaging.renderRootMessage(message, true, function (html) {
            lj("div[messagekey='" + message.key + "']").replaceWith(html);
        });
        updateMessageHtml(message, html);
    };

    var processMessage = function(data) {
        if (queryType != MESSAGE_HISTORY)
            return;

        if (data.type == 'rogerthat.messaging.newMessage') {
            var msg = data.message;
            if (msg.sender == queryParam || mctracker.indexOf(msg.members, queryParam) != -1) {
                var top = lj(".top");
                if (lj("div[messagekey='" + msg.key + "']").length == 0) {
                    var cachedMsg = messaging.getMessage(msg.key);
                    if (cachedMsg)
                        msg = cachedMsg;
                    else
                        messaging.addMessageToCache(msg);
                    if (msg.parent_key) {
                        var html = messaging.renderChildMessage(msg);
                        var rootMessageDisplay = lj("div[messagekey='" + msg.parent_key + "']");
                        updateMessageHtml(msg, html);
                        $("#messagesPlaceholder", rootMessageDisplay).before(html);
                        msg.html = html;
                    } else {
                        var html = messaging.renderRootMessage(msg, true, function (html) {
                            top.after(html);
                        });
                        updateMessageHtml(msg, html);
                        msg.html = html;
                    }
                }
            }
        } else if (data.type == 'rogerthat.friend.breakFriendShip') {
            if (data.friend.email == queryParam) {
                if (mctracker.isCurrentContainer(containerId))
                    mctracker.loadContainer("messagingContainer");
                mctracker.removeContainer(containerId);
            }
        }
    };

    return function() {
        mctracker.registerMsgCallback(processMessage);

        mctracker.getContainer("messagingContainer", null, function(container) {
            messaging = container;
            loadScreen();
        });

        lj(".older_messages").click(function() {
            loadScreen();
        });

        return {
            updateMessageDisplay : updateMessageDisplay
        }
    };
}