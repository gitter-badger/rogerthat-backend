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

var serviceUsersScript = function (container, service_identity) {
    var lj = mctracker.getLocaljQuery('#' + container);
    var cursor = "";

    var user_lines_template = '{{each users}}'
        + '<tr>'
        + '  <td><img src="/unauthenticated/mobi/cached/avatar/${avatarId}" style="width: 50px; height: 50px;" /></td>'
        + '  <td>${name}</td>'
        + '  <td>${email}</td>'
        + '  <td><a class="action-link disconnect" app_id="${app_id}" user="${email}">disconnect</a></td>'
        + '</tr>'
        + '{{/each}}';

    var initScreen = function () {
        load_more();
        lj("#more").click(load_more);
        lj("#reload").click(function(){
            lj("#table_body").empty();
            cursor = "";
            load_more();
        });
        lj("#identities").click(function(){
            mctracker.loadContainer('serviceIdentitiesContainer', '/static/parts/service_identities.html');
        });
        lj(".disconnect").click(function () {
            var user = $(this).attr('user');
            var app_id = $(this).attr('app_id');
            var row = $(this).parent().parent();
            mctracker.call({
                url: '/mobi/rest/friends/break',
                data: {
                    data: JSON.stringify ({ friend: user, app_id: app_id})
                },
                type: 'POST',
                success: function (data) {
                    row.slideUp('slow', function () { row.detach();});
                }
            });
        });
    };
    
    var load_more = function () {
        mctracker.call({
            url: '/mobi/rest/service/users',
            data: {
                service_identity: service_identity,
                cursor: cursor
            },
            success: function (data) {
                var table_body = lj("#table_body");
                table_body.append($.tmpl(user_lines_template, data));
                cursor = data.cursor;
                if (! cursor) {
                    lj("#more").fadeOut();
                } else {
                    lj("#more").fadeIn();
                }
                lj("a.disconnect").click(function () {
                    var user = $(this).attr('user');
                    var app_id = $(this).attr('app_id');
                    var row = $(this).parent().parent();
                    mctracker.call({
                        url: '/mobi/rest/friends/break',
                        data: {
                            data: JSON.stringify ({
                                service_identity: service_identity,
                                friend: user,
                                app_id: app_id
                            })
                        },
                        type: 'POST',
                        success: function (data) {
                            row.slideUp('slow', function () { row.detach();});
                        }
                    });
                });
            },
            error: mctracker.showAjaxError
        });
    };

    return function() {
        initScreen();
    };
};