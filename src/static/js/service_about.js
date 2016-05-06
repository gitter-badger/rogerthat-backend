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

var serviceAboutScript = function (containerId, serviceEmail, serviceName, serviceDescriptionBranding) {

    var lj = mctracker.getLocaljQuery('#' + containerId);
    var is_dashboard = /^dashboard.*@rogerth\.at$/i;
    var MIN_HEIGHT = 500;
    var color_scheme = "dark";
    var removeServiceDialog;
    var iframeLoadCallBackSet = false;

    var applyJQueryInUI = function () {
        removeServiceDialog = lj(".removeServiceDialog").dialog({
            autoOpen: false,
            modal: true,
            dragable: false,
            resizable: false,
            title: 'Disconnect service',
            buttons: {
                'Yes': function () {
                    removeService();
                    removeServiceDialog.dialog('close');
                },
                'No': function () {
                    removeServiceDialog.dialog('close');
                }
            }
        }).attr('dialog', containerId);
    };

    var loadScreen = function() {
        console.log("Rendering service about page for " + serviceEmail);
        color_scheme = "dark";
        if (is_dashboard.test(serviceEmail))
            lj(".breakFriendShip").hide();
        else
            lj(".breakFriendShip").click(function () {
                removeServiceDialog.dialog('open');
            });

        if (serviceDescriptionBranding) {
            var iframe = lj(".serviceDescriptionBranding")
                .attr('src', "/branding/" + serviceDescriptionBranding + "/branding_web.html");
            if (!iframeLoadCallBackSet) {
                iframe.load(function () {
                    $("nuntiuz_message", $(this).contents()).after(lj('.serviceDescription').html().replace(/\n/g, "<br>"));

                    var branding_doc = iframe.get(0).contentWindow.document;
                    color_scheme = $("meta[property=\"rt:style:color-scheme\"]", branding_doc).attr("content");
                    var background_color = $("meta[property=\"rt:style:background-color\"]", branding_doc).attr("content");
                    
                    if (!color_scheme)
                        color_scheme = "dark";
                    
                    if ( color_scheme == "light" ) {
                        lj(".dark").removeClass("dark").addClass("light");
                    } else {
                        lj(".light").removeClass("light").addClass("dark");
                    }
                    if (background_color) {
                        lj(".servicesContainer").css('background', background_color);
                    } else {
                        lj(".servicesContainer").css('background', '116895');
                    }

                    iframe.show();
                    iframe.height(MIN_HEIGHT - 5);
                    var h = iframe.contents().get(0).height + 5;
                    if (h > MIN_HEIGHT)
                        iframe.height(h);
                });
                iframeLoadCallBackSet = true;
            }
        }
    };

    var removeService = function() {
        mctracker.call({
            url: "/mobi/rest/friends/break",
            type: "post",
            data: {
                data: JSON.stringify({
                    friend: serviceEmail
                })
            },
            success: function  (data, textStatus, XMLHttpRequest) {
                mctracker.loadContainer("messagingContainer");
                mctracker.removeContainer(containerId);
            },
            error: function (data, textStatus, XMLHttpRequest) { 
                mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
            }
        });
    };
    
    var processMessage = function (data) {
        if (data.type == 'rogerthat.friend.breakFriendShip') {
            if (data.friend.email == serviceEmail) {
                if (mctracker.isCurrentContainer(containerId))
                    mctracker.loadContainer("messagingContainer");
                mctracker.removeContainer(containerId);
            }
        } else if (data.type == 'rogerthat.friends.update') {
            if (data.friend.email == serviceEmail) {
                lj('.serviceDescriptionBranding').empty().hide();
                lj('.serviceDescription').empty().hide();
                serviceName = data.friend.name ? data.friend.name : data.friend.email;
                serviceDescriptionBranding = data.friend.descriptionBranding;

                lj('.serviceName').text(serviceName);
                lj('.serviceDescription').text(data.friend.description);
                lj('.serviceAvatar').attr('src', '/unauthenticated/mobi/avatar/' + data.friend.avatarId);
                if (!serviceDescriptionBranding)
                    lj('.serviceDescription').show();

                loadScreen();
            }
        }
    };
    
    return function () {
        mctracker.registerMsgCallback(processMessage);
        applyJQueryInUI();
        loadScreen();
    };
}