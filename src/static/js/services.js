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

var FLAG_ALLOW_DISMISS = 1;
var FLAG_ALLOW_CUSTOM_REPLY = 2;
var FLAG_ALLOW_REPLY = 4;
var FLAG_ALLOW_REPLY_ALL = 8;
var FLAG_SHARED_MEMBERS = 16;
var FLAG_LOCKED = 32;
var FLAG_AUTO_LOCK = 64;

var STATUS_RECEIVED = 1;
var STATUS_ACKED = 2;
var STATUS_READ = 4;
var STATUS_DELETED = 8;

var FRIEND_TYPE_USER = 1;
var FRIEND_TYPE_SERVICE = 2;

var FRIEND_EXISTENCE_ACTIVE = 0;
var FRIEND_EXISTENCE_DELETE_PENDING = 1;
var FRIEND_EXISTENCE_DELETED = 2;
var FRIEND_EXISTENCE_NOT_FOUND = 3;
var FRIEND_EXISTENCE_INVITE_PENDING = 4;

var TYPE_MESSAGE = 1;
var TYPE_FORM_MESSAGE = 2;

var FORM_TEXT_LINE = "text_line";
var FORM_TEXT_BLOCK = "text_block";
var FORM_AUTO_COMPLETE = "auto_complete";
var FORM_SINGLE_SELECT = "single_select";
var FORM_MULTI_SELECT = "multi_select";
var FORM_DATE_SELECT = "date_select";
var FORM_SINGLE_SLIDER = "single_slider";
var FORM_RANGE_SLIDER = "range_slider";
var FORM_PHOTO_UPLOAD = "photo_upload";

var FORM_POSITIVE = "positive";
var FORM_NEGATIVE = "negative";

var FORM_MODE_DATE = "date";
var FORM_MODE_TIME = "time";
var FORM_MODE_DATE_TIME = "date_time";

var UI_FLAG_EXPECT_NEXT_WAIT_5 = 1;

var MENU_COL_COUNT = 4;
var MENU_ROW_COUNT = 3;

var COLOR_SCHEME_LIGHT = "light";
var COLOR_SCHEME_DARK = "dark";
var COLOR_SCHEME_DEFAULT = COLOR_SCHEME_LIGHT;

var DIRTY_BEHAVIOR_NORMAL = 1;
var DIRTY_BEHAVIOR_MAKE_DIRTY = 2;
var DIRTY_BEHAVIOR_CLEAN_DIRTY = 3;

var LOCK_RESULT_DID_NOTHING = 0;
var LOCK_RESULT_ADDED_TO_INBOX = 1;
var LOCK_RESULT_REMOVED_FROM_INBOX = 2;

var svc_list = null;
var svc_menu = null;
var svc_display = null;
var svc_display_waiting_info = null;

var button_confirm_dialog = null;

var photo_upload_download_url = null;

$(function() {
    svc_list = $("#tab_services #svc_list").mcscreen({
        title : 'Services',
        slimScroll : false
    });
    svc_menu = $("#tab_services #svc_menu").mcscreen({});
    svc_display = $("#tab_services #svc_display").mcscreen({});
    button_confirm_dialog = $("#button_confirm_dialog").dialog({
        width : 300,
        autoOpen : false,
        title : "Please confirm",
        resizable : false,
        modal : true,
        buttons : {
            'No' : function() {
                button_confirm_dialog.dialog('close');
            },
            'Yes' : function() {
                var message = jQuery.data(button_confirm_dialog, "message");
                var button = jQuery.data(button_confirm_dialog, "button");
                var afterSubmit = jQuery.data(button_confirm_dialog, "afterSubmit");
                var beforeSubmit = jQuery.data(button_confirm_dialog, "beforeSubmit");
                ackMessage(message, button, afterSubmit, true, beforeSubmit);
                button_confirm_dialog.dialog('close');
            }
        }
    });
});

var triggerUpdates = function(type, key, data) {
    $('.' + type.replace(/\./g, '-') + "-" + key).each(function() {
        var f = $(this).data(type);
        if (f)
            f(data);
    });
};

var removeServiceFromCache = function(email) {
    $.each(serviceCache, function(i, service) {
        if (service.email == email) {
            serviceCache.splice(i, 1);
            return false; // break
        }
    });
};

var updateServiceInCache = function(update) {
    var svc_found_in_cache = false;
    $.each(serviceCache, function(i, service) {
        if (service.email == update.email) {
            $.each(update, function(attr, value) {
                service[attr] = update[attr];
            });
            svc_found_in_cache = true;
            return false; // break
        }
    });
    if (!svc_found_in_cache)
        serviceCache.push(update);
};

var classSafeEmail = function(email) {
    return email.replace(/\./g, '-').replace(/@/g, '-').replace(/\//g, '--');
};

var processMessage = function(data, force) {
    if (data.type == 'rogerthat.messaging.newMessage') {
        var sender = getFriendByEmail(data.message.sender);
        if (sender.type == FRIEND_TYPE_SERVICE) {
            if (svc_display_waiting_info && svc_display_waiting_info.type == "follow_up"
                    && svc_display_waiting_info.thread_key == data.message.parent_key) {
                svc_display_waiting_info.loader.status('rendering');
                displayMessage(data.message, svc_display_waiting_info.loader, svc_display_waiting_info.section);
                svc_display_waiting_info = null;
            } else if (svc_display_waiting_info && svc_display_waiting_info.type == "menu_press"
                    && svc_display_waiting_info.context == data.message.context) {
                displayMessage(data.message, svc_display_waiting_info.loader, svc_display_waiting_info.section);
                svc_display_waiting_info.waiting = false;
                svc_display_waiting_info = null;
            } else if (svc_display_waiting_info && svc_display_waiting_info.type == "poke_from_branding"
                    && svc_display_waiting_info.context == data.message.context) {
                svc_display_waiting_info.loader.status('rendering');
                displayMessage(data.message, svc_display_waiting_info.loader, svc_display_waiting_info.section);
                svc_display_waiting_info = null;
            }
            messageReceived(data.message);
            // Trigger thread updates
            triggerUpdates('rogerthat.messaging.newMessage', (data.message.parent_key ? data.message.parent_key
                    : data.message.key), data.message);
            // Trigger new threads
            if (!data.message.parent_key)
                triggerUpdates('rogerthat.messaging.newMessage', classSafeEmail(data.message.sender), data.message);
            // Trigger new service_inbox items
            triggerUpdates('rogerthat.messaging.newMessage', "service-inbox", data.message);
        }
    } else if (data.type == 'rogerthat.messaging.memberUpdate') {
        // Trigger message updates
        triggerUpdates('rogerthat.messaging.memberUpdate', data.update.message, data.update);
    } else if (data.type == 'rogerthat.messaging.formUpdate') {
        // Trigger form updates
        triggerUpdates('rogerthat.messaging.formUpdate', data.update.message_key, data.update);
    } else if (data.type == 'rogerthat.messaging.messageLocked') {
        // Trigger message locked
        triggerUpdates('rogerthat.messaging.messageLocked', data.request.message_key, data.request);
        // Trigger locked service_inbox items
        triggerUpdates('rogerthat.messaging.messageLocked', "service-inbox", data.request);
    } else if (data.type == 'rogerthat.friend.breakFriendShip') {
        if (data.friend.type == FRIEND_TYPE_SERVICE) {
            removeServiceFromCache(data.friend.email);
            triggerUpdates('rogerthat.friend.breakFriendShip', classSafeEmail(data.friend.email), data.friend);
        }
    } else if (data.type == 'rogerthat.friend.ackInvitation') {
        if (data.friend.type == FRIEND_TYPE_SERVICE) {
            data.friend.existence = FRIEND_EXISTENCE_ACTIVE;
            updateServiceInCache(data.friend);
            triggerUpdates('rogerthat.friend.ackInvitation', classSafeEmail(data.friend.email), data.friend);
            triggerUpdates('rogerthat.friend.ackInvitation', 'newService', data.friend);
        }
    } else if (data.type == 'rogerthat.friends.update') {
        if (data.friend.type == FRIEND_TYPE_SERVICE) {
            if (data.friend.existence == undefined)
                data.friend.existence = FRIEND_EXISTENCE_ACTIVE;
            updateServiceInCache(data.friend);
            triggerUpdates('rogerthat.friends.update', classSafeEmail(data.friend.email), data.friend);
        }
    } else if (data.type == "rogerthat.messaging.photo_upload_done") {
        photo_upload_download_url = data.downloadUrl;
        mctracker.hideProcessing();
    }
};

mctracker.registerMsgCallback(processMessage);

var getMyMemberStatus = function(message) {
    return getMemberStatus(message, loggedOnUserEmail);
};

var getMemberStatus = function(message, email) {
    return getMemberStatusFromMembers(message.members, email);
};

var getMemberStatusFromMembers = function(members, email) {
    for ( var m in members) {
        var member = members[m];
        if (member.member == email) {
            return member;
        }
    }
    return null;
};

var showSearchServices = function() {
    $("div.serviceItem", svc_list).removeClass("svc_selected");
    clear_menu_and_display();

    var loader = svc_list.mcscreen('load', null, null, null, false, clear_menu_and_display);
    var html = $.tmpl($("#svc_search_template"));
    loader.container.append(html);
    loader.done();

    var search_results = $("div.svc_search_results", html);

    search_results.slimScroll({
        height : '464px',
        width : '320px'
    });

    $("button.svc_search_button", html).button().click(function() {
        var search_string = $("input.svc_search_textfield", html).val();
        if (!search_string) {
            mctracker.alert("Enter your search query");
            return;
        }

        var loader = svc_list.mcscreen('load', 'wait', null, null, true);

        search_results.empty();

        mctracker.call({
            hideProcessing : true,
            url : "/mobi/rest/services/find",
            type : "post",
            data : {
                data : JSON.stringify({
                    search_string : search_string
                })
            },
            success : function(data, textStatus, XMLHttpRequest) {
                if (data.error_string) {
                    loader.done();
                    mctracker.alert(data.error_string, function() {
                        $("input.svc_search_textfield", html).focus();
                    });
                    return;
                }
                loader.status('rendering');

                $.each(data.matches, function(m, match) {
                    search_results.append($('<div/>').text(match.category).addClass("category"));

                    $.each(match.items, function(i, item) {
                        var service;
                        $.each(serviceCache, function(i, svc) {
                            if (item.email == svc.email) {
                                service = svc;
                                return false; // break;
                            }
                        });

                        if (!service) {
                            service = {
                                email : item.email,
                                qualifiedIdentifier : item.qualified_identifier,
                                name : item.name,
                                avatarId : item.avatar_id,
                                description : item.description,
                                descriptionBranding : item.description_branding,
                                existence : FRIEND_EXISTENCE_NOT_FOUND,
                                type : FRIEND_TYPE_SERVICE
                            };
                        }

                        addServiceToList(service, search_results, 'search', loader);
                    });
                });
                if (loader.taskCount() == 0)
                    loader.done(); // Force loader to stop if no search results were returned.
            }
        });
    });
};

var getMessageAnswer = function(message, member) {
    if (message.message_type == TYPE_MESSAGE) {
        if ((member.status & STATUS_ACKED) != STATUS_ACKED)
            return "";
        if (member.custom_reply) {
            return member.custom_reply;
        } else if (member.button_id) {
            for ( var b in message.buttons) {
                var button = message.buttons[b];
                if (button.id == member.button_id) {
                    return button.caption;
                }
            }
        } else
            return "Roger that";
    } else {
        if (member.button_id == FORM_NEGATIVE)
            return message.form.negative_button;
        if (message.form.type == FORM_SINGLE_SELECT) {
            var r = "";
            $.each(message.form.widget.choices, function(index, choice) {
                if (choice.value == message.form.widget.value) {
                    r = choice.label;
                    return false; // break
                }
            });
            return r || message.form.positive_button;
        } else if (message.form.type == FORM_MULTI_SELECT) {
            if (message.form.widget.values) {
                var choices = [];
                $.each(message.form.widget.choices, function(index, choice) {
                    if (mctracker.indexOf(message.form.widget.values, choice.value) !== -1)
                        choices.push(choice.label);
                });
                return choices.join(", ") || message.form.positive_button;
            }
        } else if ([ FORM_TEXT_LINE, FORM_TEXT_BLOCK, FORM_AUTO_COMPLETE ].indexOf(message.form.type) != -1) {
            return message.form.widget.value || message.form.positive_button;
        } else if (message.form.type == FORM_DATE_SELECT) {
            var d = new Date((mctracker.timezoneOffset + message.form.widget.date) * 1000);
            var timeString = function(d) {
                var minutes = d.getMinutes();
                if (minutes < 10)
                    minutes = "0" + minutes;
                return d.getHours() + ":" + minutes;
            };

            var dateString = function(d) {
                if (FORM_MODE_DATE == message.form.widget.mode)
                    return d.toLocaleDateString();
                if (FORM_MODE_TIME == message.form.widget.mode)
                    return timeString(d);
                return d.toLocaleDateString() + " " + timeString(d);
            };

            if (message.form.widget.unit) {
                return message.form.widget.unit.replace("<value/>", dateString(d));
            } else {
                return dateString(d);
            }
        } else if (message.form.type == FORM_SINGLE_SLIDER) {
            if (message.form.widget.unit == null)
                return message.form.widget.value;
            else
                return message.form.widget.unit.replace("<value/>", message.form.widget.value);
        } else if (message.form.type == FORM_RANGE_SLIDER) {
            var p = message.form.widget.precision;
            if (message.form.widget.unit == null)
                return message.form.widget.low_value.toFixed(p) + " - " + message.form.widget.high_value.toFixed(p);
            else
                return message.form.widget.unit.replace("<low_value/>", message.form.widget.low_value.toFixed(p))
                        .replace("<high_value/>", message.form.widget.high_value.toFixed(p));
        } else if (message.form.type == FORM_PHOTO_UPLOAD) {
            return message.form.widget.value;
        }
    }
    return "";
};

var getWidgetId = function(message) {
    return message.form.type + "_" + message.key;
};

var renderFormWidget = function(widgetContainerSelector, message, html) {
    if (message.message_type != TYPE_FORM_MESSAGE)
        return;

    if (message.form.widget.choices) {
        $.each(message.form.widget.choices, function(index, choice) {
            choice.encoded_value = encodeURIComponent(choice.value);
        });
    }

    if (message.form.type == FORM_SINGLE_SELECT) {
        if (message.form.widget.value) {
            $.each(message.form.widget.choices, function(index, choice) {
                if (choice.value == message.form.widget.value)
                    choice._selected = true;
            });
        }

    } else if (message.form.type == FORM_MULTI_SELECT) {
        if (message.form.widget.values) {
            $.each(message.form.widget.choices, function(index, choice) {
                if (mctracker.indexOf(message.form.widget.values, choice.value) !== -1)
                    choice._selected = true;
            });
        }
    }

    var widget_id = getWidgetId(message);
    var widget_html = $.tmpl($("#tab_without_menu #message_form_template").html().replace("<!--", "")
            .replace("-->", ""), {
        message : message,
        widgetId : widget_id
    });
    $(widgetContainerSelector, html).append(widget_html);
    var widget = $("#" + widget_id, html);
    var locked = (message.flags & FLAG_LOCKED) == FLAG_LOCKED;

    if (message.form.type == FORM_TEXT_LINE || message.form.type == FORM_TEXT_BLOCK) {
        if (locked)
            widget.attr('disabled', 'disabled');
        if (message.form.type == FORM_TEXT_BLOCK)
            mctracker.fixTextareaPlaceholderForIE(widget);
    } else if (message.form.type == FORM_AUTO_COMPLETE) {
        widget.autocomplete({
            source : message.form.widget.choices,
            disabled : locked
        });
    } else if (message.form.type == FORM_DATE_SELECT) {
        var maxDate = message.form.widget.has_max_date ? new Date(
                (mctracker.timezoneOffset + message.form.widget.max_date) * 1000) : null;
        var minDate = message.form.widget.has_min_date ? new Date(
                (mctracker.timezoneOffset + message.form.widget.min_date) * 1000) : null;

        // Defines whether we need to check if the selected time should be checked against max/min date
        var shouldCheckTimeRange = function(d) {
            if (message.form.widget.mode == FORM_MODE_DATE)
                return false;
            if (!maxDate && !minDate)
                return false;
            if (message.form.widget.mode == FORM_MODE_DATE_TIME) {
                if (maxDate.getFullYear() == d.getFullYear() && maxDate.getMonth() == d.getMonth()
                        && maxDate.getDate() == d.getDate())
                    return true;
                if (minDate.getFullYear() == d.getFullYear() && minDate.getMonth() == d.getMonth()
                        && minDate.getDate() == d.getDate())
                    return true;
                return false;
            }
            return true;
        }

        var correctDateForMinMaxDates = function(d) {
            if (maxDate && d > maxDate) {
                d.setTime(maxDate.getTime());
            } else if (minDate && d < minDate) {
                d.setTime(minDate.getTime());
            }
        }

        // Returns date object, rounded to day/minuteInterval and between min and max date
        var now = function() {
            var d = new Date();
            d.setSeconds(0);
            if (message.form.widget.mode == FORM_MODE_DATE || message.form.widget.mode == FORM_MODE_DATE_TIME) {
                if (maxDate && maxDate < d)
                    return new Date(maxDate);
                else if (minDate && minDate > d)
                    return new Date(minDate);
            }
            if (message.form.widget.mode == FORM_MODE_DATE)
                return new Date(d.getFullYear(), d.getMonth(), d.getDate());

            if (shouldCheckTimeRange(d)) {
                var d2 = new Date(d);
                correctDateForMinMaxDates(d2);
                if (d2.getTime() != d.getTime())
                    return d2;
            }
            return new Date(d.getFullYear(), d.getMonth(), d.getDate(), d.getHours(), d.getMinutes() - d.getMinutes()
                    % message.form.widget.minute_interval);
        }

        var changingDate = false;
        var onDateSelected = function(dateText, inst) {
            if (!changingDate) {
                var origDate = widget.datepicker("getDate");
                var d = new Date(origDate);
                if (shouldCheckTimeRange(d)) {
                    correctDateForMinMaxDates(d);
                    if (d.getTime() != origDate.getTime()) {
                        changingDate = true;
                        widget.datepicker("setDate", d);
                        changingDate = false;
                    }
                }
                setLabelText(d);
            }
        };

        var onChangeMonthYear = function(year, month, inst) {
            if (!changingDate) {
                changingDate = true;
                var d = widget.datepicker("getDate");
                var daysInMonth = new Date(year, month, 0).getDate();
                if (d.getDate() > daysInMonth || d.getMonth() + 1 != month) {
                    d.setDate(daysInMonth)
                }
                d.setMonth(month - 1);
                d.setYear(year);
                widget.datepicker("setDate", d);
                setLabelText(d);
                changingDate = false;
            }
        };

        var timeString = function(d) {
            var minutes = d.getMinutes();
            if (minutes < 10)
                minutes = "0" + minutes;
            return d.getHours() + ":" + minutes;
        };

        var dateString = function(d) {
            if (FORM_MODE_DATE == message.form.widget.mode)
                return d.toLocaleDateString();
            if (FORM_MODE_TIME == message.form.widget.mode)
                return timeString(d);
            return d.toLocaleDateString() + " " + timeString(d);
        };

        var setLabelText = function(d) {
            var label = $("#" + getWidgetId(message) + "_label", html);
            if (message.form.widget.unit) {
                label.text(message.form.widget.unit.replace("<value/>", dateString(d)));
            } else {
                label.text(dateString(d));
            }
        };

        var date = message.form.widget.has_date ? new Date((mctracker.timezoneOffset + message.form.widget.date) * 1000)
                : now();
        setLabelText(date);

        if (!locked) {
            window.setTimeout(function() {
                if (FORM_MODE_DATE == message.form.widget.mode) {
                    widget.datepicker({
                        showButtonPanel : false,
                        changeYear : true,
                        changeMonth : true,
                        showButtonPanel : true,
                        firstDay : 1,
                        defaultDate : date,
                        maxDate : maxDate,
                        minDate : minDate,
                        onChangeMonthYear : onChangeMonthYear,
                        onSelect : onDateSelected,
                        disabled : locked
                    });
                } else if (FORM_MODE_TIME == message.form.widget.mode) {
                    widget.timepicker({
                        showButtonPanel : false,
                        stepSecond : 60,
                        hour : date.getHours(),
                        minute : date.getMinutes(),
                        stepMinute : message.form.widget.minute_interval,
                        hourMin : minDate ? minDate.getHours() : 0,
                        hourMax : maxDate ? maxDate.getHours() : 23,
                        onChangeMonthYear : onChangeMonthYear,
                        onSelect : onDateSelected,
                        disabled : locked
                    });
                } else {
                    widget.datetimepicker({
                        showButtonPanel : false,
                        changeYear : true,
                        changeMonth : true,
                        firstDay : 1,
                        defaultDate : date,
                        hour : date.getHours(),
                        minute : date.getMinutes(),
                        maxDate : maxDate,
                        minDate : minDate,
                        stepMinute : message.form.widget.minute_interval,
                        stepSecond : 60,
                        onChangeMonthYear : onChangeMonthYear,
                        onSelect : onDateSelected,
                        disabled : locked
                    });
                }
            });
        }

    } else if (message.form.type == FORM_SINGLE_SLIDER) {
        var setSingleSliderLabelText = function(value) {
            var label = $("#" + getWidgetId(message) + "_label", html);
            if (message.form.widget.unit == null)
                label.text(value);
            else
                label.text(message.form.widget.unit.replace("<value/>", value));
        };

        widget.slider({
            range : "min",
            disabled : locked,
            min : message.form.widget.min,
            max : message.form.widget.max,
            step : message.form.widget.step,
            value : message.form.widget.value,
            slide : function(event, ui) {
                setSingleSliderLabelText(ui.value);
            },
            create : function(event, ui) {
                setSingleSliderLabelText(message.form.widget.value);
            }
        });

    } else if (message.form.type == FORM_RANGE_SLIDER) {
        var setRangeSliderLabelText = function(low, high) {
            var p = message.form.widget.precision;
            var label = $("#" + getWidgetId(message) + "_label", html);
            if (message.form.widget.unit == null)
                label.text(low.toFixed(p) + " - " + high.toFixed(p));
            else
                label.text(message.form.widget.unit.replace("<low_value/>", low.toFixed(p)).replace("<high_value/>",
                        high.toFixed(p)));
        };

        widget.slider({
            range : true,
            disabled : locked,
            min : message.form.widget.min,
            max : message.form.widget.max,
            step : message.form.widget.step,
            values : [ message.form.widget.low_value, message.form.widget.high_value ],
            slide : function(event, ui) {
                setRangeSliderLabelText(ui.values[0], ui.values[1]);
            },
            create : function(event, ui) {
                setRangeSliderLabelText(message.form.widget.low_value, message.form.widget.high_value);
            }
        });
    } else if (message.form.type == FORM_PHOTO_UPLOAD) {
        newPhotoUploadActionUrl();
        $("#newPhotoUpload").change(newPhotoUpload);
    }
};

var newPhotoUploadActionUrl = function() {
    var form = $("#photoUploadForm");
    mctracker.call({
        hideProcessing : true,
        url : "/mobi/rest/messaging/new_photo_upload_url",
        type : "GET",
        success : function(data, textStatus, XMLHttpRequest) {
            form.attr("action", data);
        }
    });
};

var newPhotoUpload = function() {
    if (!$("#newPhotoUpload").val()) {
        photo_upload_download_url = null;
        return;
    }
    $("#photoUploadForm").submit();
    mctracker.showProcessing();
    newPhotoUploadActionUrl();
};

var getTextWidgetResult = function(message) {
    message.form.widget.value = $("#" + getWidgetId(message)).val();
    return {
        "value" : message.form.widget.value
    };
};

var getSelectWidgetResult = function(message, multi) {
    var values = [];
    var widgets = $("input[name=" + getWidgetId(message) + "]");
    widgets.each(function() {
        var widget = $(this);
        if (widget.attr('checked'))
            values.push(decodeURIComponent(widget.attr('encoded_value')));
    });
    if (multi) {
        message.form.widget.values = values;
        return {
            "values" : message.form.widget.values
        };
    } else {
        if (values.length == 0) {
            message.form.widget.value = null;
            return {
                "value" : null
            };
        } else {
            message.form.widget.value = values[0];
            return {
                "value" : message.form.widget.value
            };
        }
    }
};

var getDateSelectWidgetResult = function(message) {
    var date = $("#" + getWidgetId(message)).datepicker('getDate');
    if (date) {
        message.form.widget.date = Math.floor(date.getTime() / 1000) - mctracker.timezoneOffset;
        message.form.widget.has_date = true;
    }
    return {
        "value" : message.form.widget.date
    };
};

var getSingleSliderWidgetResult = function(message) {
    message.form.widget.value = $("#" + getWidgetId(message)).slider('value');
    return {
        "value" : message.form.widget.value
    };
};

var getRangeSliderWidgetResult = function(message) {
    var values = $("#" + getWidgetId(message)).slider('values');
    message.form.widget.low_value = values[0];
    message.form.widget.high_value = values[1];
    return {
        "values" : values
    };
};

var getPhotoUploadWidgetResult = function(message) {
    message.form.widget.value = "http://" + location.host + photo_upload_download_url;
    photo_upload_download_url = null;
    return {
        "value" : message.form.widget.value
    };
};

var getFormResult = function(buttonId, message) {
    var result = null;
    if (buttonId == FORM_POSITIVE) {
        if (mctracker.indexOf([ FORM_TEXT_LINE, FORM_TEXT_BLOCK, FORM_AUTO_COMPLETE ], message.form.type) > -1)
            result = getTextWidgetResult(message);

        else if (mctracker.indexOf([ FORM_SINGLE_SELECT, FORM_MULTI_SELECT ], message.form.type) > -1)
            result = getSelectWidgetResult(message, FORM_MULTI_SELECT == message.form.type);

        else if (FORM_DATE_SELECT == message.form.type)
            result = getDateSelectWidgetResult(message);

        else if (FORM_SINGLE_SLIDER == message.form.type)
            result = getSingleSliderWidgetResult(message);

        else if (FORM_RANGE_SLIDER == message.form.type)
            result = getRangeSliderWidgetResult(message);

        else if (FORM_PHOTO_UPLOAD == message.form.type)
            result = getPhotoUploadWidgetResult(message);
    }

    return result;
};

var updateFormWithResult = function(message, form_result) {
    if (mctracker.indexOf([ FORM_TEXT_LINE, FORM_TEXT_BLOCK, FORM_AUTO_COMPLETE, FORM_SINGLE_SELECT,
            FORM_SINGLE_SLIDER, FORM_PHOTO_UPLOAD ], message.form.type) > -1)
        message.form.widget.value = form_result.value;

    else if (message.form.type == FORM_MULTI_SELECT)
        message.form.widget.values = form_result.values;

    else if (message.form.type == FORM_DATE_SELECT)
        message.form.widget.date = form_result.value;

    else if (message.form.type == FORM_RANGE_SLIDER) {
        message.form.widget.low_value = form_result.values[0];
        message.form.widget.high_value = form_result.values[1];
    }
};

var getSubmitFormURL = function(form_type) {
    if (form_type == FORM_TEXT_LINE)
        return "/mobi/rest/messaging/submitTextLineForm";
    if (form_type == FORM_TEXT_BLOCK)
        return "/mobi/rest/messaging/submitTextBlockForm";
    if (form_type == FORM_AUTO_COMPLETE)
        return "/mobi/rest/messaging/submitAutoCompleteForm";
    if (form_type == FORM_SINGLE_SELECT)
        return "/mobi/rest/messaging/submitSingleSelectForm";
    if (form_type == FORM_MULTI_SELECT)
        return "/mobi/rest/messaging/submitMultiSelectForm";
    if (form_type == FORM_DATE_SELECT)
        return "/mobi/rest/messaging/submitDateSelectForm";
    if (form_type == FORM_SINGLE_SLIDER)
        return "/mobi/rest/messaging/submitSingleSliderForm";
    if (form_type == FORM_RANGE_SLIDER)
        return "/mobi/rest/messaging/submitRangeSliderForm";
    if (form_type == FORM_PHOTO_UPLOAD)
        return "/mobi/rest/messaging/submitPhotoUploadForm";
    return null;
}

var ackMessage = function(message, button, afterSubmit, confirmed, beforeSubmit) {
    if (button && !confirmed && button.action && button.action.match(/^confirm:\/\//)) {
        jQuery.data(button_confirm_dialog, "message", message);
        jQuery.data(button_confirm_dialog, "button", button);
        jQuery.data(button_confirm_dialog, "afterSubmit", afterSubmit);
        jQuery.data(button_confirm_dialog, "beforeSubmit", beforeSubmit);
        $("#button_confirmation_text", button_confirm_dialog).html(
                mctracker.htmlize(button.action.substr("confirm://".length)));
        button_confirm_dialog.dialog('open');
        return;
    }

    if (button && button.id == FORM_POSITIVE) {
        if (FORM_PHOTO_UPLOAD == message.form.type) {
            if (photo_upload_download_url == null) {
                mctracker.alert("Please select a photo first!");
                return;
            }
        }
    }

    if (beforeSubmit)
        beforeSubmit();

    var member = getMyMemberStatus(message);

    var onSuccess = function() {
        if ((message.flags & FLAG_AUTO_LOCK) == FLAG_AUTO_LOCK)
            message.flags |= FLAG_LOCKED;
        member.acked_timestamp = request.timestamp;
        member.button_id = button ? button.id : null;
        member.custom_reply = null;
        member.status |= STATUS_ACKED;
        if (afterSubmit)
            afterSubmit(message);
    };

    if (message.message_type == TYPE_FORM_MESSAGE) {
        var result = getFormResult(button.id, message);
        var request = {
            message_key : message.key,
            parent_message_key : message.parent_key,
            button_id : button ? button.id : null,
            result : result,
            timestamp : mctracker.nowUTC()
        };

        mctracker.call({
            hideProcessing : true,
            url : getSubmitFormURL(message.form.type),
            type : "POST",
            data : {
                data : JSON.stringify({
                    request : request
                })
            },
            success : function(data, textStatus, XMLHttpRequest) {
                onSuccess();
            }
        });
        mctracker.broadcast({
            type : 'rogerthat.messaging.formUpdate',
            update : {
                parent_message_key : message.parent_key,
                message_key : message.key,
                result : result,
                member : loggedOnUserEmail,
                status : member.status | STATUS_ACKED,
                received_timestamp : member.received_timestamp,
                acked_timestamp : mctracker.nowUTC(),
                button_id : button ? button.id : null
            }
        });
    } else {
        var request = {
            message_key : message.key,
            parent_message_key : message.parent_key,
            button_id : button ? button.id : null,
            custom_reply : null,
            timestamp : mctracker.nowUTC()
        };
        mctracker.call({
            hideProcessing : true,
            url : "/mobi/rest/messaging/ack",
            type : "POST",
            data : {
                data : JSON.stringify({
                    request : request
                })
            },
            success : function(data, textStatus, XMLHttpRequest) {
                onSuccess();
                if (!button)
                    return;
                if (button.action && (button.action.match(/^https?:\/\//))) {
                    console.log('launching ' + button.action);
                    window.open(button.action);
                } else if (button.action && (button.action.match(/^mailto:\/\//))) {
                    window.open(button.action.replace('mailto://', 'mailto:'));
                } else if (button.action && button.action.match(/^geo:\/\//)) {
                    window.open('http://maps.google.com/maps?q=passed%20location@' + button.action.substring(6));
                } else if (button.action && button.action.match(/^tel:\/\//)) {
                    mctracker.alert('Call ' + button.action.substring(6));
                }
                ;
            }
        });
        mctracker.broadcast({
            type : 'rogerthat.messaging.memberUpdate',
            update : {
                parent_message : message.parent_key,
                message : message.key,
                member : loggedOnUserEmail,
                status : member.status | STATUS_ACKED,
                received_timestamp : member.received_timestamp,
                acked_timestamp : mctracker.nowUTC(),
                button_id : button ? button.id : null,
                custom_reply : null
            }
        });
    }
};

var displayMessage = function(message, loader, section) {
    var html = $.tmpl($("#tab_without_menu #message_template"), message);
    loader.onDone(function() {
        markMessageAsRead(message);
        $('input:eq(0), textarea:eq(0)', html).focus();
    });
    loader.container.append(html);
    var color_scheme = "light";
    var message_acked = false;
    var renderHeader = function() {
        var sender = getFriendByEmail(message.sender);
        $("div.sender_avatar", html).avatar({
            friend : sender,
            resize : false,
            rounded : true,
            loader : loader
        });
        $("div.sender_name", html).text(sender.name);
        $("div.timestamp", html).text(mctracker.formatDate(Math.abs(message.timestamp)));
    };
    var removeHeader = function() {
        $("div.header", html).remove();
    };
    var attachAvatars = function(button, avatar_container) {
        $.each(message.members, function(i, member) {
            if ((member.status & STATUS_ACKED) != STATUS_ACKED)
                return;
            if ((!button && !member.button_id) || (button && button.id && member.button_id == button.id)) {
                var avatar_html = $("<div></div>").avatar({
                    friend : getFriendByEmail(member.member),
                    resize : true,
                    rounded : true,
                    loader : loader
                }).addClass("member_avatar");
                avatar_container.append(avatar_html);
                message_acked = true;
            }
        });
    };
    var buttons_container = $("div.message_buttons", html);
    var form_container = $("div.message_form", html);
    var display = function() {
        buttons_container.empty();
        form_container.empty();
        if (message.message_type == TYPE_MESSAGE) {
            form_container.remove();
            $.each(message.buttons, function(i, button) {
                var bu = $("<button></button>").html(mctracker.htmlize(button.caption)).addClass("message_button")
                        .button();
                bu.click(function() {
                    var beforeSubmit = function() {
                        if ((button.ui_flags & UI_FLAG_EXPECT_NEXT_WAIT_5) == UI_FLAG_EXPECT_NEXT_WAIT_5) {
                            var display_loader = section.mcscreen("load", "wait");
                            svc_display_waiting_info = {
                                type : "follow_up",
                                loader : display_loader,
                                thread_key : message.parent_key || message.key,
                                section : section
                            };
                        } else {
                            section.mcscreen("back");
                        }
                    };
                    ackMessage(message, button, display, false, beforeSubmit);
                });
                if ((message.flags & FLAG_LOCKED) == FLAG_LOCKED)
                    bu.attr('disabled', 'disabled');
                var avs = $("<div></div>");
                attachAvatars(button, avs);
                buttons_container.append($("<div></div>").append(bu).append(avs));
                loader.progress(10);
            });
            if ((message.flags & FLAG_ALLOW_DISMISS) == FLAG_ALLOW_DISMISS) {
                var bu = $("<button></button>").text("Roger that!").addClass("message_rt_button").button();
                bu
                        .click(function() {
                            var beforeSubmit = function() {
                                if ((message.dismiss_button_ui_flags & UI_FLAG_EXPECT_NEXT_WAIT_5) == UI_FLAG_EXPECT_NEXT_WAIT_5) {
                                    var display_loader = section.mcscreen("load", "wait");
                                    svc_display_waiting_info = {
                                        type : "follow_up",
                                        loader : display_loader,
                                        thread_key : message.parent_key || message.key,
                                        section : section
                                    };
                                } else {
                                    section.mcscreen("back");
                                }
                            };
                            ackMessage(message, null, display, false, beforeSubmit);
                        });
                if ((message.flags & FLAG_LOCKED) == FLAG_LOCKED)
                    bu.attr('disabled', 'disabled');
                var avs = $("<div></div>");
                attachAvatars(undefined, avs);
                buttons_container.append($("<div></div>").append(bu).append(avs));
                loader.progress(10);
            }
        } else {
            renderFormWidget("div.message_form", message, html);
            $.each(message.buttons, function(i, button) {
                var bu = $("<button></button>").text(button.caption).addClass("message_button").addClass(button.id)
                        .button();
                bu.click(function() {
                    var beforeSubmit = function() {
                        if ((button.ui_flags & UI_FLAG_EXPECT_NEXT_WAIT_5) == UI_FLAG_EXPECT_NEXT_WAIT_5) {
                            var display_loader = section.mcscreen("load", "wait");
                            svc_display_waiting_info = {
                                type : "follow_up",
                                loader : display_loader,
                                thread_key : message.parent_key || message.key,
                                section : section
                            };
                        } else {
                            section.mcscreen("back");
                        }
                    };
                    ackMessage(message, button, display, false, beforeSubmit);
                });
                if ((message.flags & FLAG_LOCKED) == FLAG_LOCKED)
                    bu.attr('disabled', 'disabled');
                var avs = $("<div></div>");
                attachAvatars(button, avs);
                buttons_container.append($("<div></div>").append(bu).append(avs));
                loader.progress(10);
            });
        }
        if (message_acked)
            html.addClass("acked");
    };
    display();

    // Redraw on lock
    html.data('rogerthat.messaging.messageLocked', function(update) {
        display();
    });
    html.addClass('rogerthat-messaging-messageLocked-' + message.key);

    var iframe = $("iframe#message_branding", html);
    if (!message.branding) {
        iframe.remove();
        renderHeader();
        loader.progress(10);
        $("div.message_text", html).html($("<div></div>").text(message.message).html().replace(/\n/g, "<br>"));
    } else {
        $("div.message_text", html).remove();
        var service = getFriendByEmail(message.sender);
        iframe.mcbranding({
            identityName : service.name || service.qualifiedIdentifier || service.email,
            branding : message.branding,
            message : message.message,
            timestamp : message.timestamp,
            loader : loader,
            onBrandingConfig : function(config) {
                if (config.color_scheme == "light") {
                    $(".dark", html).removeClass("dark").addClass("light");
                } else {
                    $(".light", html).removeClass("light").addClass("dark");
                }
                html.css('background-color', config.background_color);
                if (config.show_header)
                    renderHeader();
                else
                    removeHeader();
            }
        });
    }
};

var updateMember = function(update, member) {
    member.status = update.status;
    member.received_timestamp = update.received_timestamp;
    member.acked_timestamp = update.acked_timestamp;
    member.button_id = update.button_id;
    member.custom_reply = null;
};

var displayThread = function(service, svc_friend, message) {
    var loader = svc_display.mcscreen('load');
    var thread_template = $("#tab_without_menu #message_thread_details_template");
    var message_template = $("#tab_without_menu #message_thread_message_template");

    var thread = $.tmpl(thread_template);
    var thread_messages = $("div.thread_messages", thread);
    loader.container.append(thread);
    loader.progress(5);

    var renderThreadMessage = function(message) {
        var html = $.tmpl(message_template);
        $("div.thread_message_timestamp", html).text(mctracker.formatDate(Math.abs(message.timestamp)));
        var msg_div = $("div.thread_message", html).text(message.message);
        var member = getMyMemberStatus(message);
        if ((member.status & STATUS_ACKED) != STATUS_ACKED)
            msg_div.addClass("new");
        var answer = getMessageAnswer(message, member);
        if (answer != null)
            $("span.thread_message_answer", html).text(answer);
        else
            $("span.thread_message_answer", html).hide();
        html.click(function() {
            displayMessage(message, svc_display.mcscreen('load'), svc_display);
        });
        // Update message in case of member updates
        html.data('rogerthat.messaging.memberUpdate', function(update) {
            $.each(message.members, function(i, member) {
                if (member.member == update.member) {
                    updateMember(update, member);
                    return false; // Break loop.
                }
            });
            html.replaceWith(renderThreadMessage(message));
        });
        html.addClass('rogerthat-messaging-memberUpdate-' + message.key);
        // Update message in case of form updates
        html.data('rogerthat.messaging.formUpdate', function(update) {
            if (update.result)
                updateFormWithResult(message, update.result);
            $.each(message.members, function(i, member) {
                updateMember(update, member);
            });
            html.replaceWith(renderThreadMessage(message));
        });
        html.addClass('rogerthat-messaging-formUpdate-' + message.key);
        return html;
    };

    // Add new messages to the thread list dynamically
    thread.data('rogerthat.messaging.newMessage', function(message) {
        thread_messages.append(renderThreadMessage(message));
    });
    thread.addClass('rogerthat-messaging-newMessage-' + (message.parent_key ? message.parent_key : message.key));

    // Load thread from server
    mctracker.call({
        hideProcessing : true,
        url : '/mobi/rest/messaging/thread',
        data : {
            thread_key : message.parent_key ? message.parent_key : message.key
        },
        success : function(data) {
            $.each(data, function(i, message) {
                thread_messages.append(renderThreadMessage(message));
            });
            loader.done();
        }
    });

    // Render thread header
    loader.progress(5);
    $("div.thread_sender_avatar", thread).avatar({
        friend : svc_friend,
        resize : false,
        rounded : true,
        loader : loader
    });
    loader.progress(5);
    $("div.thread_recipients", thread).text(svc_friend.name + " >> " + $.map(message.members, function(m) {
        return getFriendByEmail(m.member, true).name;
    }).join(", "));
    loader.progress(5);
};

var poke = function(service, tag) {
    var loader = svc_display.mcscreen('load', 'wait');
    var context = "SP_" + mctracker.uuid();
    mctracker.call({
        hideProcessing : true,
        url : "/mobi/rest/services/poke_by_hashed_tag",
        type : "POST",
        data : {
            data : JSON.stringify({
                email : service.email,
                hashed_tag : tag,
                context : context
            })
        },
        success : function(data, textStatus, XMLHttpRequest) {
        }
    });
    svc_display_waiting_info = {
        type : "poke_from_branding",
        loader : loader,
        context : context,
        waiting : true,
        time : 0,
        section : svc_display
    };
    var loading = function() {
        if (!svc_display_waiting_info)
            return;
        svc_display_waiting_info.time++;
        if (svc_display_waiting_info.time > 50 || !svc_display_waiting_info.waiting)
            return;
        svc_display_waiting_info.loader.progress(1);
        setTimeout(loading, 200);
    };
    setTimeout(loading, 200);

    loader.progress(10);
};

var pressMenuItem = function(service, item) {
    svc_display.mcscreen('clear');
    var loader = svc_display.mcscreen('load');
    var context = '__web__' + mctracker.uuid();
    mctracker.call({
        hideProcessing : true,
        url : "/mobi/rest/services/press_menu_item",
        type : "POST",
        data : {
            data : JSON.stringify({
                service : service.email,
                generation : service.generation,
                context : context,
                coords : [ item.x, item.y, item.z ]
            })
        },
        success : function(data, textStatus, XMLHttpRequest) {
        }
    });
    if (item.screenBranding) {
        var iframe = $("<iframe></iframe>").attr("scrolling", "no").addClass("screen-branding");
        loader.container.append(iframe);
        iframe.mcbranding({
            identityName : service.name || service.qualifiedIdentifier || service.email,
            branding : item.screenBranding,
            height : loader.container.height(),
            loader : loader,
            onPokeClicked : function(tag) {
                poke(service, tag);
            }
        });
    } else {
        svc_display_waiting_info = {
            type : "menu_press",
            loader : loader,
            context : context,
            waiting : true,
            time : 0,
            section : svc_display
        };
        var loading = function() {
            if (!svc_display_waiting_info)
                return;
            svc_display_waiting_info.time++;
            if (svc_display_waiting_info.time > 50 || !svc_display_waiting_info.waiting)
                return;
            svc_display_waiting_info.loader.progress(1);
            setTimeout(loading, 200);
        };
        setTimeout(loading, 200);
    }
    loader.progress(10);
};

var displayServiceHistory = function(service) {
    svc_display.mcscreen('clear');
    var loader = svc_display.mcscreen('load');
    var template = $("#tab_without_menu #message_thread_template");
    var svc_friend = getFriendByEmail(service.email);
    var batch_size = 20;
    var cursor = null;
    var more = null;

    var parent_div = $("<div></div>");
    loader.container.append(parent_div);

    var renderMessage = function(message) {
        var html = $.tmpl(template);
        var member = getMyMemberStatus(message);
        var msg_div = $("div.thread_message", html);
        if ((member.status & STATUS_ACKED) != STATUS_ACKED)
            msg_div.addClass("new");
        $("div.thread_recipients", html).text(" >> " + $.map(message.members, function(m) {
            return getFriendByEmail(m.member, true).name;
        }).join(", "));
        $("div.thread_timestamp", html).text(mctracker.formatDate(Math.abs(message.timestamp)));
        msg_div.text(message.message);
        if (message.thread_size > 1) {
            $("div.thread_message_count", html).text(message.thread_size);
        } else {
            $("div.thread_message_count", html).hide();
        }
        html.click(function() {
            if ((member.status & STATUS_ACKED) != STATUS_ACKED)
                displayMessage(message, svc_display.mcscreen('load'), svc_display);
            else
                displayThread(service, svc_friend, message);
        });

        // Update message in case of member updates
        html.data('rogerthat.messaging.memberUpdate', function(update) {
            $.each(message.members, function(i, member) {
                if (member.member == update.member) {
                    updateMember(update, member);
                    return false; // Break loop.
                }
            });
            html.replaceWith(renderMessage(message));
        });
        html.addClass('rogerthat-messaging-memberUpdate-' + message.key);
        // Update message in case of form updates
        html.data('rogerthat.messaging.formUpdate', function(update) {
            if (update.result)
                updateFormWithResult(message, update.result);
            $.each(message.members, function(i, member) {
                updateMember(update, member);
            });
            html.replaceWith(renderMessage(message));
        });
        html.addClass('rogerthat-messaging-formUpdate-' + message.key);
        // Replace message when new message is added to thread
        html.data('rogerthat.messaging.newMessage', function(new_message) {
            $.each(new_message, function(prop, value) {
                message[prop] = value;
            });
            html.replaceWith(renderMessage(new_message));
        });
        html.addClass('rogerthat-messaging-newMessage-' + (message.parent_key ? message.parent_key : message.key));
        return html;
    };

    parent_div.data('rogerthat.messaging.newMessage', function(message) {
        parent_div.prepend(renderMessage(message));
    });
    parent_div.addClass('rogerthat-messaging-newMessage-' + classSafeEmail(service.email));

    var load = function() {
        mctracker.call({
            hideProcessing : true,
            url : '/mobi/rest/messaging/history',
            type : 'post',
            data : {
                data : JSON.stringify({
                    query_param : service.email,
                    cursor : cursor,
                    batch_size : batch_size
                })
            },
            success : function(data) {
                if (!more)
                    loader.progress(10);
                $.each(data.messages, function(i, message) {
                    parent_div.append(renderMessage(message));
                    loader.progress(3);
                });
                if (data.messages.length == batch_size) {
                    parent_div.append($("<div></div>").addClass("more_threads").text("... more ...").click(function() {
                        more = true;
                        svc_display_content.css('cursor', 'progress');
                        $(this).css('cursor', 'progress');
                        load();
                        more = $(this);
                    }));
                }
                loader.container.css('cursor', '');
                cursor = data.cursor;
                if (more)
                    more.detach();
                else
                    loader.done();
            }
        });
        if (!more)
            loader.progress(10);
    };
    load();
};

var displayServiceAboutScreen = function(service, container, loader, status) {
    if (!loader) {
        container.mcscreen('clear');
        loader = container.mcscreen('load');
    }
    var template = $("#tab_without_menu #service_about_template");
    var html = $.tmpl(template);
    loader.container.append(html);
    $("div.service_avatar", html).avatar({
        friend : service,
        resize : false,
        rounded : true,
        loader : loader
    });
    $("div.service_details", html).addClass(COLOR_SCHEME_DEFAULT);
    $("div.service_name", html).text(service.name);
    $("div.service_email", html).text(service.qualifiedIdentifier || service.email);
    loader.progress(10);
    if (service.descriptionBranding) {
        $("div.service_description", html).remove();
        $("#service_about_branding", html).mcbranding({
            identityName : service.name || service.qualifiedIdentifier || service.email,
            branding : service.descriptionBranding,
            height : loader.container.height() - $("div.service_details", html).height() - 16,
            message : service.description,
            loader : loader,
            onBrandingConfig : function(config) {
                if (config.color_scheme == COLOR_SCHEME_LIGHT) {
                    $(".dark", html).removeClass("dark").addClass("light");
                } else {
                    $(".light", html).removeClass("light").addClass("dark");
                }
                html.css('background', config.background_color);
                $("#service_about_branding", html).css('margin-top', '0px');
            }
        });
    } else {
        $("div.service_description", html).html(mctracker.htmlize(service.description));
        $("#service_about_branding", html).remove();
    }
    if (status == 'search') {
        // Update service in case it gets connected
        html.data('rogerthat.friend.ackInvitation', function(update) {
            serviceSelected(update, 0, status);
        });
        html.addClass('rogerthat-friend-ackInvitation-' + classSafeEmail(service.email));
    }
};

var clear_display = function() {
    svc_display.mcscreen('clear');
};

var clear_menu_and_display = function() {
    svc_menu.mcscreen('clear');
    clear_display();
};

var onConnectService = function(service) {
    return function() {
        $(this).hide();
        service.existence = FRIEND_EXISTENCE_INVITE_PENDING;
        mctracker.broadcast({
            type : 'rogerthat.friends.update',
            friend : service
        });
        mctracker.call({
            hideProcessing : true,
            url : "/mobi/rest/friends/invite",
            type : "post",
            data : {
                data : JSON.stringify({
                    email : service.email,
                    message : null,
                    tag : null
                })
            },
            success : function(data, textStatus, XMLHttpRequest) {
                // Service is added via channel-api callback
            }
        });
    };
};

var onDisconnectService = function(service) {
    return function() {
        mctracker.confirm("Are you sure you wish to disconnect " + service.name, function() {
            mctracker.call({
                hideProcessing : true,
                url : "/mobi/rest/friends/break",
                type : "post",
                data : {
                    data : JSON.stringify({
                        friend : service.email
                    })
                },
                success : function(data, textStatus, XMLHttpRequest) {
                }
            });
            mctracker.broadcast({
                type : 'rogerthat.friend.breakFriendShip',
                friend : service
            });
        }, null, "Yes", "No");
    };
};

var serviceSelected = function(service, page, status) {
    var service_connected = service.existence == FRIEND_EXISTENCE_ACTIVE;
    var newRightButton = {
        text : service_connected ? 'Disconnect' : 'Connect',
        click : service_connected ? onDisconnectService(service) : onConnectService(service)
    };
    clear_menu_and_display();
    var loader = svc_menu.mcscreen('load', null, null, newRightButton);
    if (service_connected) {
        var svc_menu_container = $.tmpl($("#svc_menu_template"));
        loader.container.append(svc_menu_container);
        var svc_menu_items = $('.svc_menu_items', svc_menu_container);
        var title = $('.svc_menu_title', svc_menu_container); // XXX: Add to mcscreen title
        var iframe = $('.svc_menu_branding', svc_menu_container);
        var svc_pages = $('.svc_pages', svc_menu_container);

        // Remove friend on disconnect
        svc_menu_container.data('rogerthat.friend.breakFriendShip', function(update) {
            clear_menu_and_display();
        });
        svc_menu_container.addClass('rogerthat-friend-breakFriendShip-' + classSafeEmail(service.email));
        // Update
        svc_menu_container.data('rogerthat.friends.update', function(update) {
            serviceSelected(service, page, status);
        });
        svc_menu_container.addClass('rogerthat-friends-update-' + classSafeEmail(service.email));

        var color_scheme = COLOR_SCHEME_DEFAULT;
        var populateMenu = function(service) {
            var generateMenuPage = function(page) {
                var table = $('<table/>').addClass('menu_' + page).addClass(page % 2 ? 'right' : 'left').addClass(
                        color_scheme);
                if (pageCount == page + 1 || (pageCount % 2 == 0 && pageCount == page + 2)) {
                    table.addClass('bottom');
                }
                for ( var row = 0; row < MENU_ROW_COUNT; row++) {
                    var tr = $('<tr/>');
                    for ( var col = 0; col < MENU_COL_COUNT; col++) {
                        tr.append($('<td/>').addClass('smi_' + col + 'x' + row + 'x' + page).append('&nbsp;'));
                    }
                    table.append(tr);
                }
                return table;
            };

            var img_ready = function() {
                loader.progress(3);
                loader.taskDone();
            };

            var addMenuItemToTable = function(item) {
                loader.addTaskCount();
                var src = null;
                if (item.z == 0 && item.y == 0) {
                    switch (item.x) {
                    case 0:
                        src = '/static/images/menu_info.png';
                        break;
                    case 1:
                        src = '/static/images/menu_history.png';
                        break;
                    case 2:
                        src = '/static/images/menu_phone.png';
                        break;
                    case 3:
                        src = '/static/images/menu_shared.png';
                        break;
                    default:
                        break;
                    }
                } else {
                    src = '/mobi/service/menu/icons?coords=' + item.x + 'x' + item.y + 'x' + item.z + '&service='
                            + service.email;
                }
                var img = $('<img/>').attr('src', src).load(img_ready).error(img_ready);
                var lbl = $('<div/>').text(item.label).addClass('smi_lbl');
                var table = $("table", svc_menu_items);
                var td = $('.smi_' + item.x + 'x' + item.y + 'x' + item.z, svc_menu_container).addClass(
                        'smi_used_' + color_scheme);
                td.empty();
                var itemHTML = $('<div/>').addClass('item').append(img).append(lbl);
                itemHTML.click(function() {
                    $("td.selected", table).removeClass("selected");
                    if (item.z == 0 && item.y == 0) {
                        switch (item.x) {
                        case 0: // About
                            td.addClass("selected");
                            displayServiceAboutScreen(service, svc_display);
                            break;
                        case 1: // Messages
                            td.addClass("selected");
                            displayServiceHistory(service);
                            break;
                        case 2: // Call
                            mctracker.alert(service.actionMenu.callConfirmation || "Call "
                                    + service.actionMenu.phoneNumber);
                            break;
                        case 3: // Share
                            alert("Share");
                            break;
                        }
                    } else {
                        pressMenuItem(service, item);
                    }
                });
                td.append(itemHTML);
            };

            var showPage = function(num) {
                svc_menu_items.empty().append(generateMenuPage(num));
                if (num == 0) {
                    addMenuItemToTable({
                        'z' : 0,
                        'y' : 0,
                        'x' : 0,
                        'label' : service.actionMenu.aboutLabel || 'About'
                    });
                    addMenuItemToTable({
                        'z' : 0,
                        'y' : 0,
                        'x' : 1,
                        'label' : service.actionMenu.messagesLabel || 'History'
                    });

                    if (service.actionMenu.phoneNumber)
                        addMenuItemToTable({
                            'z' : 0,
                            'y' : 0,
                            'x' : 2,
                            'label' : service.actionMenu.callLabel || 'Call'
                        });
                    if (service.actionMenu.share)
                        addMenuItemToTable({
                            'z' : 0,
                            'y' : 0,
                            'x' : 3,
                            'label' : service.actionMenu.shareLabel || 'Recommend'
                        });
                }
                $.each(service.actionMenu.items, function(i, item) {
                    if (item.z == num)
                        addMenuItemToTable(item);
                });
                if (pageCount == 1)
                    svc_pages.hide();
                else {
                    svc_pages.show().empty();
                    var i = 0;
                    for (i = 0; i < pageCount; i++) {
                        var img = $("<img/>");
                        img.load(img_ready).error(img_ready);
                        if (i == num) {
                            img.attr("src", color_scheme == COLOR_SCHEME_DARK ? "/static/images/current_page.png"
                                    : "/static/images/current_page_light.png")
                        } else {
                            img.attr("src", color_scheme == COLOR_SCHEME_DARK ? "/static/images/other_page.png"
                                    : "/static/images/other_page_light.png");
                            var create_click_handler = function(page_num) {
                                return function() {
                                    service.existence = FRIEND_EXISTENCE_ACTIVE;
                                    serviceSelected(service, page_num, status);
                                }
                            }
                            img.addClass("svc_other_menu_page").click(create_click_handler(i));
                        }
                        loader.addTaskCount(1);
                        svc_pages.append(img);
                    }
                }
                svc_menu_items.removeClass("mcoutofscreen");
                svc_menu_container.css('cursor', '');
            };

            var pageCount = 1;
            $.each(service.actionMenu.items, function(i, item) {
                item.x = item.coords[0];
                item.y = item.coords[1];
                item.z = item.coords[2];
                pageCount = Math.max(pageCount, item.z + 1);
            });

            showPage(page ? page : 0);
            // Show branding
            if (service.actionMenu.branding) {
                title.hide();
                iframe.mcbranding({
                    identityName : service.name || serivce.qualifiedIdentifier || service.email,
                    branding : service.actionMenu.branding,
                    loader : loader,
                    onBrandingConfig : function(br) {
                        color_scheme = br.color_scheme;
                        if (color_scheme == COLOR_SCHEME_LIGHT) {
                            $(".dark", svc_menu_container).removeClass("dark").addClass("light");
                            $(".smi_used_dark", svc_menu_container).removeClass("smi_used_dark").addClass(
                                    "smi_used_light");
                        } else {
                            $(".light", svc_menu_container).removeClass("light").addClass("dark");
                            $(".smi_used_light", svc_menu_container).removeClass("smi_used_light").addClass(
                                    "smi_used_dark");
                        }
                        svc_menu_container.css('background-color', br.background_color);
                    }
                });
                loader.onDone(function() {
                    svc_pages.css('margin-top', 480 - iframe.height() - svc_menu_items.height());
                });
            } else {
                iframe.remove();
                title.show().text(service.name);
                svc_pages.css('margin-top', 480 - title.height() - svc_menu_items.height());
                svc_menu_container.css('background-color', 'white');
                $(".dark", svc_menu_container).removeClass("dark").addClass("light");
            }
            loader.progress(10);
        };

        mctracker.call({
            hideProcessing : true,
            url : "/mobi/rest/services/get_full_service",
            data : {
                service : service.email
            },
            success : function(data) {
                loader.progress(10);
                populateMenu(data);
            }
        });
        loader.progress(10);
    } else {
        displayServiceAboutScreen(service, svc_menu, loader, status);
    }
};

var addServiceToList = function(service, list, status, loader) {
    var renderServiceItem = function(service) {
        var html = $.tmpl($("#svc_service_list_item"));
        $("div.serviceAvatar", html).avatar({
            friend : service,
            left : true,
            resize : false,
            rounded : true,
            loader : loader
        });
        $("div.serviceName", html).text(getFriendName(service));
        loader.addTaskCount();
        var img = $("div.serviceStatus > img", html).load(loader.taskDone).error(loader.taskDone);
        if (service.existence == FRIEND_EXISTENCE_ACTIVE) {
            img.attr('src', status == 'search' ? '/static/images/checkmark.png' : '/static/images/arrow_right.png');
        } else if (service.existence == FRIEND_EXISTENCE_INVITE_PENDING) {
            img.attr('src', '/static/images/snake.gif');
            img.css('margin', '7px 8px 0px 0px');
        } else {
            img.attr('src', '/static/images/arrow_right.png');
        }
        html.click(function() {
            serviceSelected(service, 0, status);
            $("div.svc_selected", list).removeClass("svc_selected");
            html.addClass("svc_selected");
        });
        html.attr("service", service.email);

        var update = function(update) {
            html.replaceWith(renderServiceItem(update));
        };

        // Update service in case of service updates
        html.data('rogerthat.friends.update', update);
        html.addClass('rogerthat-friends-update-' + classSafeEmail(service.email));

        // Update service in case it gets connected
        html.data('rogerthat.friend.ackInvitation', update);
        html.addClass('rogerthat-friend-ackInvitation-' + classSafeEmail(service.email));

        if (status != 'search') {
            // Remove friend on disconnect
            html.data('rogerthat.friend.breakFriendShip', function(update) {
                html.remove();
            });
            html.addClass('rogerthat-friend-breakFriendShip-' + classSafeEmail(service.email));
        }
        return html;
    }
    list.append(renderServiceItem(service));
};

var renderInboxMessage = function(message, loader, inbox) {
    var no_messages = $("div.no_messages", inbox).hide();
    var html = $.tmpl($("#service_inbox_message_template")).attr('message_key', message.key);
    var sender = getFriendByEmail(message.sender);
    $("div.sender_avatar", html).avatar({
        friend : sender,
        resize : false,
        rounded : true,
        loader : loader
    });
    $("div.inbox_message_recipients", html).text(getFriendName(sender) + " >> " + $.map(message.members, function(m) {
        return getFriendByEmail(m.member, true).name;
    }).join(", "));
    $("div.inbox_message_timestamp", html).text(mctracker.formatDate(Math.abs(message.timestamp)));
    $("div.inbox_message_message", html).text(message.message);
    html.click(function() {
        clear_menu_and_display();
        displayMessage(message, svc_menu.mcscreen('load'), svc_menu);
        html.fadeOut('slow', function() {
            html.remove();
        });
    });
    html.data('rogerthat.messaging.memberUpdate', function(update) {
        if (update.member == loggedOnUserEmail && (update.status & STATUS_READ) == STATUS_READ)
            html.fadeOut('slow', function() {
                decrease_a2p_badge();
                html.remove();
                if ($("div.inbox_message", inbox).length == 0)
                    no_messages.show();
            });
    });
    html.addClass('rogerthat-messaging-memberUpdate-' + message.key);
    html.data('rogerthat.friend.breakFriendShip', function(update) {
        html.remove();
    });
    html.addClass('rogerthat-friend-breakFriendShip-' + classSafeEmail(message.sender));
    html.data('rogerthat.messaging.messageLocked', function(request) {
        if (request.dirty_behavior != DIRTY_BEHAVIOR_CLEAN_DIRTY)
            return;

        html.fadeOut('slow', function() {
            html.remove();
            if ($("div.inbox_message", inbox).length == 0)
                no_messages.show();
            decrease_a2p_badge();
        });
    });
    html.addClass('rogerthat-messaging-messageLocked-' + message.key);

    return html;
};

var messageReceived = function(message) {
    var myMember = getMyMemberStatus(message);
    if (!myMember)
        return;
    if ((myMember.status & STATUS_RECEIVED) == STATUS_RECEIVED)
        return;
    var timestamp = mctracker.nowUTC();
    mctracker.call({
        hideProcessing : true,
        url : "/mobi/rest/messaging/received",
        type : "POST",
        data : {
            data : JSON.stringify({
                request : {
                    message_key : message.key,
                    message_parent_key : message.parent_key,
                    received_timestamp : timestamp
                }
            })
        },
        success : function(data, textStatus, XMLHttpRequest) {
        }
    });
    myMember.status |= STATUS_RECEIVED;
    mctracker.broadcast({
        type : 'rogerthat.messaging.memberUpdate',
        update : {
            parent_message : message.parent_key,
            message : message.key,
            member : myMember.member,
            status : myMember.status,
            received_timestamp : myMember.received_timestamp,
            acked_timestamp : myMember.acked_timestamp,
            button_id : myMember.button_id,
            custom_reply : null
        }
    });
};

var markMessageAsRead = function(message) {
    var myMember = getMyMemberStatus(message);
    if (!myMember)
        return;
    if ((myMember.status & STATUS_READ) == STATUS_READ)
        return;
    var timestamp = mctracker.nowUTC();
    mctracker.call({
        hideProcessing : true,
        url : "/mobi/rest/messaging/mark_messages_as_read",
        type : "POST",
        data : {
            data : JSON.stringify({
                message_keys : [ message.key ],
                parent_message_key : message.parent_key ? message.parent_key : message.key
            })
        },
        success : function(data, textStatus, XMLHttpRequest) {
        }
    });
    myMember.status |= STATUS_READ;
    mctracker.broadcast({
        type : 'rogerthat.messaging.memberUpdate',
        update : {
            parent_message : message.parent_key,
            message : message.key,
            member : myMember.member,
            status : myMember.status,
            received_timestamp : myMember.received_timestamp,
            acked_timestamp : myMember.acked_timestamp,
            button_id : myMember.button_id,
            custom_reply : null
        }
    });
};

var loadStartScreen = function(svc_inbox) {
    svc_list.mcscreen('clear');
    var loader = svc_list.mcscreen('load', null, null, {
        text : 'Add Services',
        click : showSearchServices
    });
    clear_menu_and_display();
    var html = $.tmpl($("#svc_start_screen_template"));
    loader.container.append(html);

    $("div.svc_inbox", html).slimScroll({
        height : '190px',
        width : '320px'
    });
    $("div.svc_service_list", html).slimScroll({
        height : '257px',
        width : '320px'
    });

    var list = $("div.svc_service_list", html);
    $.each(serviceCache, function(i, service) {
        addServiceToList(service, list, null, loader);
    });
    // Update service in case it gets connected
    list.data('rogerthat.friend.ackInvitation', function(update) {
        if ($("div[service='" + update.email + "']", list).length == 0) {
            addServiceToList(update, list, null, loader);
        }
    });
    list.addClass('rogerthat-friend-ackInvitation-newService');

    var inbox = $("div.svc_inbox", html);
    if (svc_inbox.messages.length != 0) {
        $.each(svc_inbox.messages, function(i, message) {
            messageReceived(message);
            inbox.append(renderInboxMessage(message, loader, inbox));
        });
    }
    // Add new messages to the inbox list dynamically
    html.data('rogerthat.messaging.newMessage', function(message) {
        var myMember = getMemberStatusFromMembers(message.members, loggedOnUserEmail);
        if (myMember && (myMember.status & STATUS_READ) != STATUS_READ) {
            inbox.prepend(renderInboxMessage(message, loader, inbox));
            increase_a2p_badge();
        }
    });
    html.addClass('rogerthat-messaging-newMessage-service-inbox');
    html.data('rogerthat.messaging.messageLocked', function(request) {
        var dirty_behavior = request.dirty_behavior;
        if (dirty_behavior == DIRTY_BEHAVIOR_NORMAL) {
            var myMember = getMemberStatusFromMembers(request.members, loggedOnUserEmail);
            if (myMember && (myMember.status & STATUS_ACKED) != STATUS_ACKED) {
                dirty_behavior = DIRTY_BEHAVIOR_MAKE_DIRTY;
            }
        }

        if (dirty_behavior != DIRTY_BEHAVIOR_MAKE_DIRTY)
            return;

        if ($('div.svc_inbox [message_key="' + request.message_key + '"]').length == 0) {
            // Add to svc_inbox
            mctracker.call({
                hideProcessing : true,
                url : "/mobi/rest/messaging/get_single",
                type : "POST",
                data : {
                    data : JSON.stringify({
                        message_key : request.message_key,
                        parent_message_key : request.parent_message_key
                    })
                },
                success : function(data, textStatus, XMLHttpRequest) {
                    inbox.prepend(renderInboxMessage(data, loader, inbox));
                    increase_a2p_badge();
                }
            });
        }
    });
    html.addClass('rogerthat-messaging-messageLocked-service-inbox');

    if (loader.taskCount() == 0)
        loader.done();
}