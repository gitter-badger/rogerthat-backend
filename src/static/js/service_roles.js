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

var serviceRolesScript = function() {
    
    var ROLE_TEMPLATE = '{{each roles}}' //
        + '<tr>' //
        + '    <td>${name}</td>' //
        + '    <td>${type}</td>' //
        + '    <td>${formattedCreationTimestamp}</td>' //
        + '    <td>{{if type == "managed"}}<a class="action-link members" role_name="${name}" role_id="${id}">Members</a>{{/if}}</td>' //
        + '    <td><a class="action-link delete" role_name="${name}" role_id="${id} app_id={app_id}">Delete</a></td>' //
        + '</tr>'
        + '{{/each}}';

    var MEMBER_TEMPLATE = "{{each members}}<tr class=\"member\"><td><img src=\"/unauthenticated/mobi/cached/avatar/${user_avatar_id}\"/> ${user_name}</td><td>${identity_name}</td><td><a class=\"action-link revoke\" identity=\"${identity}\" role_id=\"${role_id}\" user_email=\"${user_email}:${app_id}\">Revoke</a></td>{{/each}}";
    var IDENTITY_OPTION_TEMPLATE = "{{each identities}}<option value=\"${identifier}\">${name}</option>{{/each}}";
    var container = "#serviceRolesContainer";
    var lj = mctracker.getLocaljQuery(container);
    var members_dialog = null;
    var new_role_dialog = null;
    var grants = null;
    var service_identity_select = null;
    var user_email_input = null;
    var identities = null;
    
    var load = function () {
        var tableBody = lj("#table_body");
        mctracker.call({
            url: '/mobi/rest/service/roles',
            success: function (roles) {
                $.each(roles, function (i, role) {
                    role.formattedCreationTimestamp = mctracker.formatDate(role.creation_time);
                });
                tableBody.empty().append($.tmpl(ROLE_TEMPLATE, {
                    roles : roles
                }));
                lj("a.members").click(function() {
                    var thizz = $(this);
                    members_dialog.attr('role_id', thizz.attr('role_id'));
                    load_role_members();
                    members_dialog.dialog('option', 'title', 'Edit ' + thizz.attr('role_name') + ' members')
                        .dialog('open');
                });
                lj("a.delete").click(function() {
                    var thizz = $(this);
                    mctracker.confirm(
                        "Are you sure you want to delete role '" + thizz.attr('role_name') + "'?",
                        function() {
                            var role_id = parseInt(thizz.attr('role_id'));
                            mctracker.call({
                                url : '/mobi/rest/service/roles/delete',
                                type : 'post',
                                data : {
                                    data : JSON.stringify({
                                        role_id : role_id
                                    })
                                },
                                success : function(data) {
                                    mctracker.alert(data.success ? "Role successfully deleted"
                                            : data.errormsg);
                                }
                            });
                        });
                });
            }
        });
    };
    
    var load_grants = function() {
        mctracker.call({
            url: '/mobi/rest/service/grants',
            success: function  (data, textStatus, XMLHttpRequest) {
                grants = data;
                load_role_members();
            }
        });
    };
    
    var load_identities = function () {
        mctracker.call({
            url : '/mobi/rest/service/identities',
            success : function(data) {
                identities = data.sort(sortServiceIdentities);
                service_identity_select.empty()
                    .append($("<option></option>").attr('value', '+default+').text("All identities"));
                var list = [];
                $.each(identities, function (i, identity) {
                    if (identity.identifier != "+default+")
                        list.push(identity);
                });
                service_identity_select.append($.tmpl(IDENTITY_OPTION_TEMPLATE, {
                    identities : list
                }));
            }
        })
    };
    
    var load_role_members = function() {
        var current_role_id = members_dialog.attr('role_id');
        if (current_role_id) {
            current_role_id = parseInt(current_role_id);
            $("tr.member", members_dialog).detach();
            var members = [];
            $.each(grants, function (i, grant){
                if (grant.role_type == "service" && grant.role_id == current_role_id) {
                    members.push(grant);
                    if (grant.identity == "+default+")
                        grant.identity_name = "All identities";
                    else {
                        $.each(identities, function (i, identity) {
                            if (grant.identity == identity.identifier) {
                                grant.identity_name = identity.name
                                return false;
                            }
                        });
                    }
                }
            });
            $("#table_body_members", members_dialog).prepend($.tmpl(MEMBER_TEMPLATE, {
                members : members
            }));
            $("a.revoke", members_dialog).click(function () {
                var thizz = $(this);
                var identity = thizz.attr('identity');
                var role_id = parseInt(thizz.attr('role_id'));
                var app_user_email = thizz.attr('user_email');
                mctracker.call({
                    url: '/mobi/rest/service/roles/revoke',
                    type: 'post',
                    data: {
                        data: JSON.stringify({
                            identity: identity,
                            app_user_email: app_user_email,
                            role_id: role_id
                        })
                    },
                    success: function () {
                        setTimeout(mctracker.showProcessing, 1);
                    }
                });
            });
        }
    };

    var initScreen = function() {
        service_identity_select = lj("#service_identity");
        user_email_input = lj("#user_email").autocomplete({
            source: function (request, response) {
                mctracker.call({
                    url: "/mobi/rest/service/search_users",
                    hideProcessing: true,
                    data: {
                        term: request.term
                    },
                    success: function (data) {
                        var result = [];
                        $.each(data, function(i, user) {
                            result.push({
                                label : user.name + '<' + user.email + '> (' + user.app_id + ')',
                                value : user.email + ':' + user.app_id
                            });
                        });
                        response(result);
                    },
                    error: function () {
                        response([]);
                    }
                })
            },
            minLength: 3,
            select: function( event, ui ) {
                $(this).val(ui.item.value);
                $(this).attr('app_id', ui.item.appId);
            }
        });
        lj("#add_member").click(function () {
            var role_id = parseInt(members_dialog.attr('role_id'));
            var app_user_email = user_email_input.val();
            var identity = service_identity_select.val();
            if (!(role_id && user_email && identity)) {
                mctracker.alert("Not all fields are set.");
                return;
            }
            mctracker.call({
                url: '/mobi/rest/service/roles/grant',
                type: 'post',
                data: {
                    data: JSON.stringify({
                        identity: identity,
                        app_user_email: app_user_email,
                        role_id: role_id
                    })
                },
                success: function () {
                    user_email_input.val('');
                    user_email_input.removeAttr('app_id');
                    service_identity_select.val('');
                    setTimeout(mctracker.showProcessing, 1);
                }
            });
        });
        members_dialog = lj("#edit_role_dialog").dialog({
            autoOpen: false,
            modal: true,
            width: '600px',
            title: "members",
            buttons: {
                'Close': function () {
                    members_dialog.dialog('close');
                }
            }
        }).attr('dialog', container);
        
        new_role_dialog = lj("#new_role_dialog").dialog({
            autoOpen: false,
            modal: true,
            width: '250px',
            title: 'New role',
            buttons: {
                'Add role': function () {
                    var name = lj("#role_name", 'dc').val();
                    var type = lj("#role_type", 'dc').val();
                    if (! name || ! type) {
                        mctracker.alert("Please provide a name and type for the new role!");
                        return;
                    }
                    mctracker.call({
                        url: '/mobi/rest/service/roles/create',
                        type: 'post',
                        data: {
                            data: JSON.stringify({
                                name: name,
                                type_: type
                            })
                        },
                        success: function () {
                            new_role_dialog.dialog('close');
                        },
                        error: function () {
                            mctracker.alert("The role was not created, probably a role with the same name already exists.");
                        }               
                     });
                },
                'Cancel': function () {
                    new_role_dialog.dialog('close');
                }
            }
        }).attr('dialog', container);
        
        load();
        load_grants();
        load_identities();
        lj("#create_new").click(function () {
            lj("#role_name", 'dc').val('');
            lj("#role_type", 'dc').val('');
            new_role_dialog.dialog('open');
        });
    };

    return function() {
        initScreen();
        mctracker.registerMsgCallback(function(data) {
            if (data.type == 'rogerthat.service.roles.updated') {
                load();
            } else if (data.type == 'rogerthat.service.role.grants.updated') {
                setTimeout(load_grants, 1000);
            } else if (data.type == 'rogerthat.services.identity.refresh') {
                load_identities();
            }
        });
    };
};

mctracker.registerLoadCallback("serviceRolesContainer", serviceRolesScript());