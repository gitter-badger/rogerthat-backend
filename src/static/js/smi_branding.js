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

var brandingScript = function (containerId, serviceEmail, smiBranding) {

    var MIN_HEIGHT = 500;

    var lj = mctracker.getLocaljQuery('#' + containerId);

    var loadScreen = function () {
        var iframe = lj(".smiBranding")
            .attr('src', '/branding/' + smiBranding + '/branding_web.html')
            .css('height', '')
            .load(function () {
                iframe.show();
                iframe.height(MIN_HEIGHT - 5);
                var h = iframe.contents().get(0).height + 5;
                if (h > MIN_HEIGHT)
                    iframe.height(h);
            });
    };

    var processMessage = function (data) {
        if (data.type == 'rogerthat.friend.breakFriendShip') {
            if (data.friend.email == serviceEmail) {
                if (mctracker.isCurrentContainer(containerId))
                    mctracker.loadContainer("messagingContainer");
                mctracker.removeContainer(containerId);
            }
        }
    }

    return function () {
        mctracker.registerMsgCallback(processMessage);
        loadScreen();
    };
};