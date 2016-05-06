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

// Editing service identities

var SEARCH_LOCATION_TEMPLATE = '<tr>' //
        + '  <td>${address}</td>' //
        + '  <td>lat: ${latitude}<br>lon: ${longitude}</td>' //
        + '  <td><a action="show" class="action-link" target="blank" href="https://maps.google.com/maps?q=${coords}">Show</a></td>' //
        + '  <td><a action="remove" class="action-link" style="float: right">Remove</a></td>' //
        + '</tr>';

var BEACON_TEMPLATE = '<tr>' //
        + '  <td>${beacon_uuid}</td>' //
        + '  <td>${beacon_major}</td>' //
        + '  <td>${beacon_minor}</td>' //
        + '  <td>${beacon_tag}</td>' //
        + '  <td><a action="remove" class="action-link" style="float: right">Remove</a></td>' //
        + '</tr>';

var ADMIN_EMAIL_TEMPLATE = '<tr>' //
        + '  <td>${admin_email}</td>' //
        + '  <td><a action="remove" class="action-link" style="float: right">Remove</a></td>' //
        + '</tr>';

var SUPPORTED_APPS_TEMPLATE = '{{each apps}}' //
        + '<input type="checkbox" id="supported-app-${$value.id}" value="${$value.id}" app_name="${$value.name}" {{if $value.supported}}checked="true"{{/if}}>' //
        + '<label for="supported-app-${$value.id}">${$value.name}</label>' //
        + '<br>' //
        + '{{/each}}';

var HREF_GEOCODE_RESULT_PREFIX = 'http://maps.google.com/maps?q=geo%20code%20result@';

var DEFAULT_SERVICE_IDENTITY = "+default+";

var sortServiceIdentities = function(l, r) {
    // Default service identity first
    if (l.identifier == DEFAULT_SERVICE_IDENTITY)
        return -1;
    if (r.identifier == DEFAULT_SERVICE_IDENTITY)
        return 1;
    lLower = l.name.toLowerCase();
    rLower = r.name.toLowerCase();
    if (lLower == rLower)
        return 0;
    else
        return lLower < rLower ? -1 : 1;
};

var descriptionSort = function(left, right) {
    var l = left.description.toLowerCase();
    var r = right.description.toLowerCase();
    if (l < r)
        return -1;
    else if (l == r)
        return 0;
    else
        return 1;
};

var qrCodes = [];
var defaultServiceIdentity;
var searchLocations = [];
var beacons = [];
var adminEmails = [];
var canEditSupportedApps = false;

var createIdentityDialog;
var supportedAppsDialog;
var addressLookupDialog;
var addressGpsCoords;
var coordsHelpDialog;
var addBeaconDialog;
var addAdminEmailDialog;

var elemIdentityIdentifier;
var elemIdentityName;
var elemIdentityDescription;
var elemIdentityDescriptionBranding;
var elemIdentityQualifiedIdentifier;
var elemIdentitySupportedApps;
var elemIdentitySupportedAppsHidden;
var elemIdentityUpdateSupportedApps;
var elemIdentityMenuBranding;
var elemIdentityPhoneNumber;
var elemIdentityPhonePopupText;
var elemIdentityShareEnabled;
var elemIdentitySearchEnabled;
var elemIdentitySearchKeywords;
var elemIdentitySearchLocations;
var elemIdentityAddSearchLocation;
var elemIdentityAddBeacon;
var elemIdentityBeacons;
var elemIdentityAddAdminEmail;
var elemIdentityAdminEmails;

var elemIdentitySupportedAppsCheckbox;
var elemIdentityDescriptionCheckbox;
var elemIdentityDescriptionBrandingCheckbox;
var elemIdentityMenuBrandingCheckbox;
var elemIdentityPhoneNumberCheckbox;
var elemIdentityPhonePopupTextCheckbox;

var elemIdentityIdentifierRequired;
var elemIdentityNameRequired;

var elemIdentityEmailStatistics;
var elemIdentityEmailStatisticsCheckbox;

var createOrEditServiceIdentity = function(url, identifier, successCallback) {
    var ok = true;
    if (!identifier) {
        elemIdentityIdentifierRequired.fadeIn('slow');
        ok = false;
    } else {
        elemIdentityIdentifierRequired.fadeOut('slow');
    }

    if (!elemIdentityName.val()) {
        elemIdentityNameRequired.fadeIn('slow');
        ok = false;
    } else {
        elemIdentityNameRequired.fadeOut('slow');
    }

    if (!ok)
        return;

    mctracker.call({
        url : url,
        type : 'POST',
        data : {
            data : JSON.stringify({
                details : {
                    identifier : identifier,
                    name : elemIdentityName.val(),
                    description : elemIdentityDescription.val(),
                    description_use_default : elemIdentityDescriptionCheckbox.is(':checked'),
                    description_branding : elemIdentityDescriptionBranding.val(),
                    description_branding_use_default : elemIdentityDescriptionBrandingCheckbox.is(':checked'),
                    app_ids : elemIdentitySupportedAppsHidden.val().split(','),
                    app_ids_use_default : elemIdentitySupportedAppsCheckbox.is(':checked'),
                    menu_branding : elemIdentityMenuBranding.val(),
                    menu_branding_use_default : elemIdentityMenuBrandingCheckbox.is(':checked'),
                    phone_number : elemIdentityPhoneNumber.val(),
                    phone_number_use_default : elemIdentityPhoneNumberCheckbox.is(':checked'),
                    phone_call_popup : elemIdentityPhonePopupText.val(),
                    phone_call_popup_use_default : elemIdentityPhonePopupTextCheckbox.is(':checked'),
                    qualified_identifier : elemIdentityQualifiedIdentifier.val(),
                    admin_emails : adminEmails,
                    recommend_enabled : elemIdentityShareEnabled.is(':checked'),
                    search_use_default : elemIdentitySearchCheckbox.is(':checked'),
                    search_config : {
                        enabled : elemIdentitySearchEnabled.is(':checked'),
                        keywords : elemIdentitySearchKeywords.val(),
                        locations : searchLocations
                    },
                    email_statistics : elemIdentityEmailStatistics.is(':checked'),
                    email_statistics_use_default : elemIdentityEmailStatisticsCheckbox.is(':checked'),
                    beacons : beacons
                }
            })
        },
        success : function(data) {
            successCallback(data.success, data.errormsg);
        }
    });
};

var openCreateServiceIdentityDialog = function(successCallback) {
    searchLocations = [];
    beacons = [];
    adminEmails = [];
    displayBeacons(beacons);

    $(".hidefordefault", createIdentityDialog).show();
    $(".showfordefault", createIdentityDialog).hide();

    elemIdentityIdentifier.val('').attr('disabled', false).focus();
    elemIdentityName.val('');
    elemIdentityQualifiedIdentifier.val('');
    elemIdentityShareEnabled.attr('checked', false);
    elemIdentityEmailStatistics.attr('checked', false);

    elemIdentityIdentifierRequired.hide();
    elemIdentityNameRequired.hide();

    // Following lines simulate toggles of 'use default' checkBoxes so default values will be filled in nicely
    elemIdentitySupportedAppsCheckbox.attr('checked', true).show().change();
    elemIdentityDescriptionCheckbox.attr('checked', true).show().change();
    elemIdentityDescriptionBrandingCheckbox.attr('checked', true).show().change();
    elemIdentityMenuBrandingCheckbox.attr('checked', true).show().change();
    elemIdentityPhoneNumberCheckbox.attr('checked', true).show().change();
    elemIdentityPhonePopupTextCheckbox.attr('checked', true).show().change();
    elemIdentitySearchCheckbox.attr('checked', true).show().change();
    elemIdentityEmailStatisticsCheckbox.attr('checked', true).show().change();

    createIdentityDialog.dialog(
            {
                title : 'Create new service identity',
                buttons : {
                    Create : function() {
                        createOrEditServiceIdentity("/mobi/rest/service/identity_create", elemIdentityIdentifier.val(),
                                successCallback);
                    },
                    Cancel : function() {
                        createIdentityDialog.dialog('close');
                    }
                }
            }).dialog('open');
};

var openEditServiceIdentityDialog = function(serviceIdentity, successCallback) {
    searchLocations = serviceIdentity.search_config.locations;
    beacons = serviceIdentity.beacons;
    adminEmails = serviceIdentity.admin_emails;
    canEditSupportedApps = serviceIdentity.can_edit_supported_apps;

    createIdentityDialog.dialog({
        title : "Edit service identity",
        buttons : {
            Save : function() {
                createOrEditServiceIdentity("/mobi/rest/service/identity_update", serviceIdentity.identifier,
                        successCallback);
            },
            Cancel : function() {
                createIdentityDialog.dialog('close');
            }
        }
    });

    elemIdentityIdentifierRequired.hide();
    elemIdentityNameRequired.hide();

    var identifier = serviceIdentity.identifier == DEFAULT_SERVICE_IDENTITY ? "[default]" : serviceIdentity.identifier;
    elemIdentityIdentifier.val(identifier).attr('disabled', true);
    elemIdentityName.val(serviceIdentity.name).focus();
    elemIdentityQualifiedIdentifier.val(serviceIdentity.qualified_identifier);
    elemIdentityShareEnabled.attr('checked', serviceIdentity.recommend_enabled);
    elemIdentitySupportedApps.text(serviceIdentity.app_names.join(', '));
    elemIdentitySupportedAppsHidden.val(serviceIdentity.app_ids.join(','));

    elemIdentityDescription.val(serviceIdentity.description).attr('disabled', false);
    elemIdentityDescriptionBranding.val(serviceIdentity.description_branding).attr('disabled', false);
    elemIdentityMenuBranding.val(serviceIdentity.menu_branding).attr('disabled', false);
    elemIdentityPhoneNumber.val(serviceIdentity.phone_number).attr('disabled', false);
    elemIdentityPhonePopupText.val(serviceIdentity.phone_call_popup).attr('disabled', false);
    elemIdentitySearchKeywords.val(serviceIdentity.search_config.keywords).attr('disabled', false);
    elemIdentitySearchEnabled.attr('checked', serviceIdentity.search_config.enabled).attr('disabled', false);
    elemIdentityEmailStatistics.attr('checked', serviceIdentity.email_statistics).attr('disabled', false);
    elemIdentityAddSearchLocation.show();
    if (canEditSupportedApps) {
        elemIdentityUpdateSupportedApps.show();
    } else {
        elemIdentityUpdateSupportedApps.hide();
    }
    $('a[action="remove"]', elemIdentitySearchLocations).show();

    displayLocations(searchLocations);
    displayBeacons(beacons);
    displayAdminEmails(adminEmails);

    elemIdentityDescriptionCheckbox.attr('checked', serviceIdentity.description_use_default);
    elemIdentityDescriptionBrandingCheckbox.attr('checked', serviceIdentity.description_branding_use_default);
    elemIdentitySupportedAppsCheckbox.attr('checked', serviceIdentity.app_ids_use_default);
    elemIdentityMenuBrandingCheckbox.attr('checked', serviceIdentity.menu_branding_use_default);
    elemIdentityPhoneNumberCheckbox.attr('checked', serviceIdentity.phone_number_use_default);
    elemIdentityPhonePopupTextCheckbox.attr('checked', serviceIdentity.phone_call_popup_use_default);
    elemIdentitySearchCheckbox.attr('checked', serviceIdentity.search_use_default);
    elemIdentityEmailStatisticsCheckbox.attr('checked', serviceIdentity.email_statistics_use_default);

    if (serviceIdentity.identifier == DEFAULT_SERVICE_IDENTITY) {
        $(".hidefordefault", createIdentityDialog).hide();
        $(".showfordefault", createIdentityDialog).show();
    } else {
        $(".hidefordefault", createIdentityDialog).show();
        $(".showfordefault", createIdentityDialog).hide();

        // Following lines simulate toggles of 'use default' checkBoxes so default values will be filled in nicely
        if (serviceIdentity.description_use_default)
            elemIdentityDescriptionCheckbox.change();

        if (serviceIdentity.description_branding_use_default)
            elemIdentityDescriptionBrandingCheckbox.change();

        if (serviceIdentity.app_ids_use_default)
            elemIdentitySupportedAppsCheckbox.change();

        if (serviceIdentity.menu_branding_use_default)
            elemIdentityMenuBrandingCheckbox.change();

        if (serviceIdentity.phone_number_use_default)
            elemIdentityPhoneNumberCheckbox.change();

        if (serviceIdentity.phone_call_popup_use_default)
            elemIdentityPhonePopupTextCheckbox.change();

        if (serviceIdentity.search_use_default)
            elemIdentitySearchCheckbox.change();

        if (serviceIdentity.email_statistics_use_default)
            elemIdentityEmailStatisticsCheckbox.change();
    }

    createIdentityDialog.dialog('open');
};

var roundTo3Decimals = function(value) {
    return Math.round(value * 1000) / 1000;
};

var geoCodeAddress = function() {
    $("#address_error", addressLookupDialog).text("");
    var address = $("#address", addressLookupDialog).val();
    var geoCoder = new google.maps.Geocoder();
    geoCoder.geocode({
        'address' : address
    }, function(results, status) {
        if (status == google.maps.GeocoderStatus.OK) {
            addressGpsCoords = results[0].geometry.location;
            var coordsStr = roundTo3Decimals(addressGpsCoords.lat()) + "," + roundTo3Decimals(addressGpsCoords.lng());
            $("#coords", addressLookupDialog).val(coordsStr);
            $("#map_result", addressLookupDialog).show().attr('href', HREF_GEOCODE_RESULT_PREFIX + coordsStr);
        } else {
            $("#address_error", addressLookupDialog).text("The address could not be geocoded.");
        }
    });
};

var displayLocations = function(locations) {
    elemIdentitySearchLocations.empty();
    $.each(locations, function(i, location) {
        var latitude = location.lat / 1000000;
        var longitude = location.lon / 1000000;
        var html = $.tmpl(SEARCH_LOCATION_TEMPLATE, {
            address : location.address,
            latitude : roundTo3Decimals(latitude),
            longitude : roundTo3Decimals(longitude),
            coords : latitude + "," + longitude
        });
        elemIdentitySearchLocations.append(html);

        $('a[action="remove"]', html).click(function() {
            var index = searchLocations.indexOf(location);
            if (index != -1) {
                searchLocations.splice(index, 1);
                html.remove();
            }
        });
    });
};

var displayBeacons = function(local_beacons) {
    elemIdentityBeacons.empty();
    $.each(local_beacons, function(i, beacon) {
        var html = $.tmpl(BEACON_TEMPLATE, {
            beacon_uuid : beacon.uuid,
            beacon_major : beacon.major,
            beacon_minor : beacon.minor,
            beacon_tag : beacon.tag
        });
        elemIdentityBeacons.append(html);

        $('a[action="remove"]', html).click(function() {
            var index = beacons.indexOf(beacon);
            if (index != -1) {
                beacons.splice(index, 1);
                html.remove();
            }
        });
    });
};

var displayAdminEmails = function(admin_emails) {
    elemIdentityAdminEmails.empty();
    $.each(admin_emails, function(i, admin_email) {
        var html = $.tmpl(ADMIN_EMAIL_TEMPLATE, {
            admin_email : admin_email
        });
        elemIdentityAdminEmails.append(html);

        $('a[action="remove"]', html).click(function() {
            var index = adminEmails.indexOf(admin_email);
            if (index != -1) {
                adminEmails.splice(index, 1);
                html.remove();
            }
        });
    });
};

var loadBrandings = function() {
    elemIdentityDescriptionBranding.empty().append($("<option></option>").val('').text('[No branding]'));
    elemIdentityMenuBranding.empty().append($("<option></option>").val('').text('[No branding]'));
    mctracker.call({
        hideProcessing : true,
        url : "/mobi/rest/branding/list",
        success : function(data) {
            $.each(data.sort(descriptionSort), function(i, brand) {
                var formattedDate = mctracker.formatDate(brand.timestamp, true);
                elemIdentityDescriptionBranding.append($("<option></option>").val(brand.id).text(
                        brand.description + " [" + formattedDate + "]"));
                elemIdentityMenuBranding.append($("<option></option>").val(brand.id).text(
                        brand.description + " [" + formattedDate + "]"));
            });
        }
    });
};

var setDefaultServiceIdentity = function(value) {
    defaultServiceIdentity = value;

    elemIdentityDescription.attr('placeholder', defaultServiceIdentity.description);
    elemIdentityPhoneNumber.attr('placeholder', defaultServiceIdentity.phone_number);
    elemIdentityPhonePopupText.attr('placeholder', defaultServiceIdentity.phone_call_popup)
    elemIdentitySearchKeywords.attr('placeholder', defaultServiceIdentity.search_config.keywords);
};

$(function() {
    createIdentityDialog = $("#createIdentityDialog").dialog({
        width : 800,
        autoOpen : false,
        modal : true,
        resizable : false
    });

    elemIdentityIdentifier = $("#identity_identifier", createIdentityDialog);
    elemIdentityName = $("#identity_name", createIdentityDialog);
    elemIdentityDescription = $("#identity_description", createIdentityDialog);
    elemIdentityDescriptionBranding = $("#identity_description_branding", createIdentityDialog);
    elemIdentityQualifiedIdentifier = $("#identity_qualified_identifier", createIdentityDialog);
    elemIdentitySupportedApps = $("#identity_supported_apps", createIdentityDialog);
    elemIdentitySupportedAppsHidden = $("#identity_supported_apps_hidden", createIdentityDialog);
    elemIdentityMenuBranding = $("#identity_menu_branding", createIdentityDialog);
    elemIdentityPhoneNumber = $("#identity_phone_number", createIdentityDialog);
    elemIdentityPhonePopupText = $("#identity_phone_popup_text", createIdentityDialog);
    elemIdentityShareEnabled = $("#identity_share_enabled", createIdentityDialog);
    elemIdentitySearchEnabled = $("#identity_search_enabled", createIdentityDialog);
    elemIdentitySearchKeywords = $("#identity_search_keywords", createIdentityDialog);
    elemIdentitySearchLocations = $("#identity_search_locations", createIdentityDialog);
    elemIdentityEmailStatistics = $("#identity_email_statistics", createIdentityDialog);
    elemIdentityBeacons = $("#identity_beacons", createIdentityDialog);
    elemIdentityAdminEmails = $("#identity_admin_emails", createIdentityDialog);

    elemIdentityIdentifierRequired = $('#identity_identifier_required', createIdentityDialog);
    elemIdentityNameRequired = $('#identity_name_required', createIdentityDialog);

    elemIdentityDescriptionCheckbox = $("#identity_description_checkbox", createIdentityDialog).change(function() {
        if ($(this).is(':checked')) {
            elemIdentityDescription.attr('disabled', true).val('');
        } else {
            elemIdentityDescription.attr('disabled', false).val(defaultServiceIdentity.description);
        }
    });
    elemIdentityDescriptionBrandingCheckbox = $("#identity_description_branding_checkbox", createIdentityDialog)
            .change(
                    function() {
                        if ($(this).is(':checked')) {
                            elemIdentityDescriptionBranding.attr('disabled', true).val(
                                    defaultServiceIdentity.description_branding);
                        } else {
                            elemIdentityDescriptionBranding.attr('disabled', false);
                        }
                    });

    elemIdentitySupportedAppsCheckbox = $("#identity_supported_apps_checkbox", createIdentityDialog).change(function() {
        if ($(this).is(':checked')) {
            elemIdentitySupportedApps.text(defaultServiceIdentity.app_names.join(', '));
            elemIdentitySupportedAppsHidden.val(defaultServiceIdentity.app_ids.join(','));
            elemIdentityUpdateSupportedApps.hide();
        } else if (canEditSupportedApps) {
            elemIdentityUpdateSupportedApps.show();
        } else {
            elemIdentityUpdateSupportedApps.hide();
        }
    });
    elemIdentityMenuBrandingCheckbox = $("#identity_menu_branding_checkbox", createIdentityDialog).change(function() {
        if ($(this).is(':checked')) {
            elemIdentityMenuBranding.attr('disabled', true).val(defaultServiceIdentity.menu_branding);
        } else {
            elemIdentityMenuBranding.attr('disabled', false);
        }
    });
    elemIdentityPhoneNumberCheckbox = $("#identity_phone_number_checkbox", createIdentityDialog).change(function() {
        if ($(this).is(':checked')) {
            elemIdentityPhoneNumber.attr('disabled', true).val('');
        } else {
            elemIdentityPhoneNumber.attr('disabled', false).val(defaultServiceIdentity.phone_number);
        }
    });
    elemIdentityPhonePopupTextCheckbox = $("#identity_phone_popup_text_checkbox", createIdentityDialog).change(
            function() {
                if ($(this).is(':checked')) {
                    elemIdentityPhonePopupText.attr('disabled', true).val('');
                } else {
                    elemIdentityPhonePopupText.attr('disabled', false).val(defaultServiceIdentity.phone_call_popup);
                }
            });
    elemIdentitySearchCheckbox = $("#identity_search_checkbox", createIdentityDialog).change(function() {
        var useDefault = $(this).is(':checked');

        if (useDefault) {
            elemIdentitySearchEnabled.attr('checked', defaultServiceIdentity.search_config.enabled);
            elemIdentitySearchKeywords.val(defaultServiceIdentity.search_config.keywords);
            elemIdentityAddSearchLocation.hide();
            displayLocations(defaultServiceIdentity.search_config.locations);
            $('#identity_search_locations a[action="remove"]', createIdentityDialog).hide();

        } else {
            elemIdentityAddSearchLocation.show();
            searchLocations = [];
            displayLocations(searchLocations);
            $('#identity_search_locations a[action="remove"]', createIdentityDialog).show();
        }

        elemIdentitySearchEnabled.attr('disabled', useDefault);
        elemIdentitySearchKeywords.attr('disabled', useDefault);
    });

    elemIdentityEmailStatisticsCheckbox = $("#identity_email_statistics_checkbox", createIdentityDialog).change(
            function() {
                var useDefault = $(this).is(':checked');
                if (useDefault) {
                    elemIdentityEmailStatistics.attr('checked', defaultServiceIdentity.email_statistics);
                }
                elemIdentityEmailStatistics.attr('disabled', useDefault);
            });

    addressLookupDialog = $("#addressLookupDialog").dialog({
        width : 300,
        title : "Add location",
        resizable : false,
        modal : true,
        autoOpen : false,
        open : function() {
            addressGpsCoords = null;
            $("#address_error", addressLookupDialog).text("");
            $("#address", addressLookupDialog).text("");
        }
    });

    $("#coords_help", addressLookupDialog).click(function() {
        coordsHelpDialog.dialog('open');
    });

    coordsHelpDialog = $("#coordsHelpDialog").dialog({
        width : 400,
        title : "Info",
        modal : true,
        autoOpen : false
    });

    supportedAppsDialog = $("#supportedAppsDialog").dialog({
        width : 300,
        title : "Select supported apps",
        resizable : false,
        modal : true,
        autoOpen : false,
        buttons : {
            Save : function() {
                var selectedAppIds = [];
                var selectedAppNames = [];
                $('input[type="checkbox"]:checked', supportedAppsDialog).map(function() {
                    selectedAppIds.push(this.value);
                    selectedAppNames.push(this.attributes['app_name'].value);
                });
                if (selectedAppIds.length == 0) {
                    mctracker.alert("There must be at least one supported app");
                    return;
                }
                elemIdentitySupportedAppsHidden.val(selectedAppIds.join(","));
                elemIdentitySupportedApps.text(selectedAppNames.join(", "));
                supportedAppsDialog.dialog('close');
            },
            Cancel : function() {
                supportedAppsDialog.dialog('close');
            }
        }
    });

    var getSelectedSupportedAppIds = function() {
        return elemIdentitySupportedAppsHidden.val().split(',');
    };

    elemIdentityUpdateSupportedApps = $("#identity_supported_apps_update", createIdentityDialog).click(function() {
        mctracker.call({
            url : "/mobi/rest/service/apps",
            type : "get",
            success : function(apps) {
                var supportedApps = getSelectedSupportedAppIds();
                $.each(apps, function(i, app) {
                    app.supported = supportedApps.indexOf(app.id) != -1;
                });
                $("#appsContainer", supportedAppsDialog).empty().append($.tmpl(SUPPORTED_APPS_TEMPLATE, {
                    apps : apps
                }));
                supportedAppsDialog.dialog('open');
            }
        });
    });

    elemIdentityAddSearchLocation = $("#identity_add_search_location", createIdentityDialog).click(function() {
        var showDialog = function() {
            addressLookupDialog.dialog({
                modal : true,
                buttons : {
                    Add : function() {
                        if (!addressGpsCoords) {
                            $("#address_error", addressLookupDialog).text("Coordinates is a required field.");
                            return;
                        }
                        var location = {
                            address : $("#address", addressLookupDialog).val(),
                            lat : Math.round(addressGpsCoords.lat() * 1000000, 0),
                            lon : Math.round(addressGpsCoords.lng() * 1000000, 0)
                        };
                        searchLocations.push(location);

                        displayLocations(searchLocations);
                        addressLookupDialog.dialog('close');
                    },
                    Cancel : function() {
                        addressLookupDialog.dialog('close');
                    }
                }
            }).dialog('open');
        };

        $("#address", addressLookupDialog).val("");
        $("#coords", addressLookupDialog).val("");
        $("#map_result", addressLookupDialog).hide();
        $("#address_error", addressLookupDialog).text("");

        try {
            new google.maps.Geocoder();
            showDialog();
        } catch (err) {
            // We need to load google maps first
            mctracker.showProcessing();
            mctracker.mapsLoadedCallbacks.push(function() {
                mctracker.hideProcessing();
                showDialog();
            });
            mctracker.loadGoogleMaps();
        }
    });

    $("#coords", addressLookupDialog).focusin(function(event) {
        $("#address_error", addressLookupDialog).text("");
        $("#map_result", addressLookupDialog).show();
    }).focusout(function() {
        var coords = $(this).val();
        if (!(coords && coords.match("-?\\d+(\\.\\d*)?,-?\\d+(\\.\\d*)?"))) {
            $("#map_result", addressLookupDialog).hide();
            addressGpsCoords = null;
            if (coords)
                $("#address_error", addressLookupDialog).text("Invalid coordinates.");
            return;
        }

        var splitted = coords.split(',');
        addressGpsCoords = new google.maps.LatLng(Number(splitted[0]), Number(splitted[1]));
        $("#map_result", addressLookupDialog).attr('href', HREF_GEOCODE_RESULT_PREFIX + coords);
    });

    $("#address", addressLookupDialog).keypress(function(event) {
        if (event.keyCode == '13') {
            geoCodeAddress();
        }
    });

    $("#lookup_address", addressLookupDialog).click(geoCodeAddress);

    addAdminEmailDialog = $("#addAdminEmailDialog").dialog({
        width : 400,
        title : "Add admin email",
        resizable : false,
        modal : true,
        autoOpen : false,
        open : function() {
            $("#admin_email_error", addBeaconDialog).text("");
        }
    });

    elemIdentityAddAdminEmail = $("#identity_add_admin_email", createIdentityDialog).click(function() {
        var showDialog = function() {
            addAdminEmailDialog.dialog({
                modal : true,
                buttons : {
                    Add : function() {
                        var newAdminEmail = $("#admin_email", addAdminEmailDialog).val();
                        if (newAdminEmail == "") {
                            $("#admin_email_error", addAdminEmailDialog).text("Email is a required field.");
                            return;
                        }

                        adminEmails.push(newAdminEmail);

                        displayAdminEmails(adminEmails);

                        addAdminEmailDialog.dialog('close');
                    },
                    Cancel : function() {
                        addAdminEmailDialog.dialog('close');
                    }
                }
            }).dialog('open');
        };

        $("#admin_email", addAdminEmailDialog).val("");

        showDialog();
    });

    addBeaconDialog = $("#addBeaconDialog").dialog({
        width : 400,
        title : "Add beacon",
        resizable : false,
        modal : true,
        autoOpen : false,
        open : function() {
            $("#beacon_error", addBeaconDialog).text("");
        }
    });

    elemIdentityAddBeacon = $("#identity_add_beacon", createIdentityDialog).click(function() {
        var showDialog = function() {
            addBeaconDialog.dialog({
                modal : true,
                buttons : {
                    Add : function() {
                        var uuid = $("#beacon_uuid", addBeaconDialog).val();
                        var major = $("#beacon_major", addBeaconDialog).val();
                        var minor = $("#beacon_minor", addBeaconDialog).val();
                        var tag = $("#beacon_tag", addBeaconDialog).val();
                        if (uuid == "") {
                            $("#beacon_error", addBeaconDialog).text("UUID is a required field.");
                            return;
                        }
                        if (major == "") {
                            $("#beacon_error", addBeaconDialog).text("Major is a required field.");
                            return;
                        }
                        if (!mctracker.isPositiveInteger(major)) {
                            $("#beacon_error", addBeaconDialog).text("Major should be a number.");
                            return;
                        }
                        if (minor == "") {
                            $("#beacon_error", addBeaconDialog).text("Minor is a required field.");
                            return;
                        }
                        if (!mctracker.isPositiveInteger(minor)) {
                            $("#beacon_error", addBeaconDialog).text("Minor should be a number.");
                            return;
                        }

                        beacons.push({
                            uuid : uuid,
                            major : parseInt(major),
                            minor : parseInt(minor),
                            tag : tag
                        });
                        displayBeacons(beacons);

                        addBeaconDialog.dialog('close');
                    },
                    Cancel : function() {
                        addBeaconDialog.dialog('close');
                    }
                }
            }).dialog('open');
        };

        $("#beacon_uuid", addBeaconDialog).val("");
        $("#beacon_major", addBeaconDialog).val("");
        $("#beacon_minor", addBeaconDialog).val("");
        $("#beacon_tag", addBeaconDialog).val("");
        $("#beacon_error", addBeaconDialog).text("");

        showDialog();
    });

    loadBrandings();

    mctracker.registerMsgCallback(function(data) {
        if (data.type == "rogerthat.service.branding.refresh") {
            loadBrandings();
        }
    });
});