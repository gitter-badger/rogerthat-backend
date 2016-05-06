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

var serviceIdentitiesScript = function() {
    var IDENTITY_LINES_TEMPLATE = '{{each identities}}'
            + '<tr>'
            + '<td>{{if identifier == defaultIdentity}}[default]{{else}}${identifier}{{/if}}</td>'
            + '<td>${name}</td>'
            + '<td>${formattedCreationTimestamp}</td>'
            + '<td><a class="action-link show_users" identifier="${identifier}">Show users</a></td>'
            + '<td><a class="action-link edit" identifier="${identifier}">Edit</a></td>'
            + '<td>{{if identifier != defaultIdentity}}<a class="action-link delete" identifier="${identifier}">Delete</a>{{/if}}</td>'
            + '</tr>' //
            + '{{/each}}';

    var container = "#serviceIdentitiesContainer";
    var lj = mctracker.getLocaljQuery(container);

    var onIdentitySaved = function(success, errormsg) {
        if (success) {
            createIdentityDialog.dialog('close');
        } else {
            var dialog = mctracker.alert(mctracker.htmlize(errormsg), null, null, null, true);
            dialog.dialog({width: 400});
        }
    };

    var deleteServiceIdentity = function(identifier) {
        mctracker.confirm("Are you sure you want to delete service identity " + identifier + "?", function() {
            mctracker.call({
                url : '/mobi/rest/service/identity_delete',
                type : 'POST',
                data : {
                    data : JSON.stringify({
                        identifier : identifier,
                    })
                },
                success : function(data) {
                    if (data.success) {
                        loadServiceIdentities();
                    } else {
                        mctracker.alert(data.errormsg);
                    }
                }
            });
        });
    };

    var loadServiceIdentityForEditing = function(identifier) {
        mctracker.call({
            url : "/mobi/rest/service/identity",
            data : {
                identifier : identifier
            },
            success : function(serviceIdentityToBeEdited) {
                if (serviceIdentityToBeEdited.identifier == DEFAULT_SERVICE_IDENTITY) {
                    setDefaultServiceIdentity(serviceIdentityToBeEdited);
                    openEditServiceIdentityDialog(serviceIdentityToBeEdited, onIdentitySaved);
                } else {
                    // Load default identity
                    mctracker.call({
                        url : "/mobi/rest/service/identity",
                        data : {
                            identifier : DEFAULT_SERVICE_IDENTITY
                        },
                        success : function(defaultServiceIdentityForEditing) {
                            setDefaultServiceIdentity(defaultServiceIdentityForEditing);
                            openEditServiceIdentityDialog(serviceIdentityToBeEdited, onIdentitySaved);
                        }
                    });
                }
            }
        });
    };

    var loadServiceIdentities = function() {
        var tableBody = lj("#table_body");
        mctracker.call({
            url : '/mobi/rest/service/identities',
            success : function(identities) {
                identities = identities.sort(sortServiceIdentities);
                $.each(identities, function(i, serviceIdentity) {
                    serviceIdentity.formattedCreationTimestamp = mctracker.formatDate(serviceIdentity.created);
                });

                tableBody.empty().append($.tmpl(IDENTITY_LINES_TEMPLATE, {
                    identities : identities,
                    defaultIdentity : DEFAULT_SERVICE_IDENTITY
                }));

                lj("a.edit").click(function() {
                    loadServiceIdentityForEditing($(this).attr('identifier'));
                });

                lj("a.delete").click(function() {
                    deleteServiceIdentity($(this).attr('identifier'));
                });

                lj("a.show_users").click(
                        function() {
                            var identifier = $(this).attr('identifier');
                            mctracker.loadContainer("serviceUsersContainer_" + CryptoJS.MD5(identifier),
                                    "/mobi/service/users?identifier=" + encodeURIComponent(identifier));
                        });
            }
        });
    };

    var initScreen = function() {
        lj("#create_new").click(function() {
            // Load default identity
            mctracker.call({
                url : "/mobi/rest/service/identity",
                data : {
                    identifier : DEFAULT_SERVICE_IDENTITY
                },
                success : function(defaultServiceIdentityForEditing) {
                    setDefaultServiceIdentity(defaultServiceIdentityForEditing);
                    openCreateServiceIdentityDialog(onIdentitySaved);
                }
            });
        });

        lj("#reload").click(function() {
            loadServiceIdentities();
        });

        loadServiceIdentities();
    };

    return function() {
        initScreen();
        mctracker.registerMsgCallback(function(data) {
            if (data.type == 'rogerthat.services.identity.refresh') {
                loadServiceIdentities();
            }
        });
    };
};

mctracker.registerLoadCallback("serviceIdentitiesContainer", serviceIdentitiesScript());