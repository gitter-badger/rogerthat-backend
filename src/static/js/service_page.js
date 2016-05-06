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

var servicePageScript = function (containerId, serviceEmail) {

    var lj = mctracker.getLocaljQuery('#' + containerId);
    var service = null;
    var color_scheme; 
    var pageCount = 1;
    var context = null;
    var timer = null;

    var COL_COUNT = 4;
    var ROW_COUNT = 3;

    var iframeLoadCallBackSet = false;

    var renderPage = function () {
        color_scheme = "dark";
        pageCount = 1;
        $.each(service.actionMenu.items, function (i, item) {
            item.x = item.coords[0];
            item.y = item.coords[1];
            item.z = item.coords[2];
            pageCount = Math.max(pageCount, item.z + 1);
        });
        
        // Create pages
        for (var z = 0; z < pageCount; z++) {
            lj('.serviceActionMenus').append(generateMenuPage(z));
        }

        // Populate pages
        addMenuItemToTable({'z': 0, 'y': 0, 'x': 0, 'label': 'About'});
        addMenuItemToTable({'z': 0, 'y': 0, 'x': 1, 'label': 'Messages'});

        if (service.actionMenu.phoneNumber)
            addMenuItemToTable({'z': 0, 'y': 0, 'x': 2, 'label': 'Call'});
        if (service.actionMenu.share)
            addMenuItemToTable({'z': 0, 'y': 0, 'x': 3, 'label': 'Recommend'});

        $.each(service.actionMenu.items, function (i, item) {
            addMenuItemToTable(item);
        });

        // Show branding
        if (service.actionMenu.branding) {
            var iframe = lj('.serviceBranding').show().attr('src', '/branding/' + service.actionMenu.branding + '/branding_web.html');
            if (!iframeLoadCallBackSet) {
                iframe.load(function () {
                    var branding_doc = iframe.get(0).contentWindow.document;
                    color_scheme = $("meta[property=\"rt:style:color-scheme\"]", branding_doc).attr("content");
                    var background_color = $("meta[property=\"rt:style:background-color\"]", branding_doc).attr("content");

                    if (!color_scheme)
                        color_scheme = "dark";
                    
                    if ( color_scheme == "light" ) {
                        lj(".dark").removeClass("dark").addClass("light");
                        lj(".smi_used_dark").removeClass("smi_used_dark").addClass("smi_used_light");
                    } else {
                        lj(".light").removeClass("light").addClass("dark");
                        lj(".smi_used_light").removeClass("smi_used_light").addClass("smi_used_dark");
                    }
                    if (background_color) {
                        lj(".servicePage").css('background', background_color);
                    } else {
                        lj(".servicePage").css('background', '116895');
                    }

                    var body = this.contentWindow.document.body;
                    setTimeout(function () {
                        var iframe_height = $(body).height();
                        iframe.height(iframe_height);
                        setTimeout(function () {
                            iframe_height = body.scrollHeight;
                            iframe.height(iframe_height);
                            iframe.removeClass('mcoutofscreen');
                        }, 50);
                    }, 50);
                });
                iframeLoadCallBackSet = true;
            }
        } else {
            lj('.serviceBranding').hide();
        }
    };

    var addMenuItemToTable = function (item) {
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
            src = '/mobi/service/menu/icons?coords=' + item.x + 'x' + item.y + 'x' + item.z + '&service=' + service.email;
        }
        
        var img = lj('<img/>').attr('src', src);
        var lbl = lj('<div/>').text(item.label).addClass('smi_lbl');
        var td = lj('.smi_' + item.x + 'x' + item.y + 'x' + item.z).addClass('smi_used_' + color_scheme);
        td.empty();
        var itemHTML = lj('<div/>').addClass('item').append(img).append(lbl);
        itemHTML.click(function () {
            if (item.z == 0 && item.y == 0) {
                switch (item.x) {
                case 0: // About
                    mctracker.loadContainer('serviceAboutPageContainer_' + CryptoJS.MD5(service.email),
                                            '/mobi/service/about?service=' + service.email);
                    break;
                case 1: // Messages
                    mctracker.loadContainer('messageHistory_' + CryptoJS.MD5(service.email),
                                            '/mobi/message/history?cursor=&member=' + service.email);
                    break;
                case 2: // Call
                    mctracker.alert('Call ' + service.actionMenu.phoneNumber);
                    break;
                case 3: // Share
                    pressMenuItem(item);
                    break;
                }
            } else {
                pressMenuItem(item);
            }
            
        });
        td.append(itemHTML);
    };
    
    var pressMenuItem = function (item) {
        context = mctracker.uuid();
        mctracker.call({
            url: "/mobi/rest/services/press_menu_item",
            type: "POST",
            data: {
                data: JSON.stringify({
                    service: service.email,
                    generation: service.generation,
                    context: context,
                    coords: [item.x, item.y, item.z]
                })
            },
            success: function  (data, textStatus, XMLHttpRequest) {
                if (!item.screenBranding) {
                    mctracker.showProcessing(true, function () {
                        context = null;
                    });
                    timer = setTimeout(function () {
                        if (context) {
                            timer = null;
                            context = null;
                            if (mctracker.isCurrentContainer(containerId)) {
                                mctracker.hideProcessing();
                                mctracker.alert("Action sent successfully!");
                            }
                        }
                    }, 10000);
                }
            },
            error: function (data, textStatus, XMLHttpRequest) {
                if (!item.screenBranding)
                    alert("Connect failed.\nPlease refresh your browser and try again.");
            }
        });
        if (item.screenBranding) {
            mctracker.loadContainer("smi_branding_container_" + item.screenBranding,
                                    "/mobi/service/menu/item/branding?service=" + serviceEmail + "&branding=" + item.screenBranding);
        }
    };

    var generateMenuPage = function (page) {
        var table = lj('<table/>').addClass('menu_' + page).addClass(page % 2 ? 'right' : 'left').addClass('dark');
        if (pageCount == page + 1 || (pageCount % 2 == 0 && pageCount == page + 2)) {
            table.addClass('bottom');
        }
        for (var row = 0; row < ROW_COUNT; row++) {
            var tr = lj('<tr/>');
            for (var col = 0; col < COL_COUNT; col++) {
                tr.append(lj('<td/>').addClass('smi_' + col + 'x' + row + 'x' + page).append('&nbsp;'));
            }
            table.append(tr);
        }
        return table;
    };

    var processMessage = function (data) {
        if (data.type == 'rogerthat.friend.breakFriendShip') {
            if (data.friend.email == serviceEmail) {
                if (mctracker.isCurrentContainer(containerId))
                    mctracker.loadContainer("messagingContainer");
                mctracker.removeContainer(containerId);
                console.log("container removed");
            }
        } else if (data.type == 'rogerthat.friends.update') {
            if (data.friend.email == serviceEmail) {
                lj('.serviceActionMenus').empty();
                lj('.serviceBranding').empty().hide();
                service = data.friend;
                renderPage();
            }
        } else if (data.type == 'rogerthat.messaging.newMessage') {
            if (mctracker.isCurrentContainer(containerId)) {
                if (context && context == data.message.context) {
                    clearTimeout(timer);
                    timer = null;
                    context = null;
                    mctracker.hideProcessing();
                    mctracker.loadContainer("messagingContainer");
                }
            }
        }
    };

    var loadScreen = function () {
        mctracker.call({
            url: "/mobi/rest/services/get_full_service",
            data: { service: serviceEmail },
            success: function (data, textStatus, XMLHttpRequest) {
                service = data;
                renderPage();
            }
        });
    }

    return function () {
        mctracker.registerMsgCallback(processMessage);
        loadScreen();
    };
};