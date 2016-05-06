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

var settingsScript = function () {
	var general = true;
	var mobile = 0;
	var upToDate = true;
	var tab = null;
	var mobileColor = null;
	var debuggingDialog;
	var autoScrollDebuggingDialog = true;
	
	var container = "#settingsContainer";
	var lj = mctracker.getLocaljQuery(container);

	var resetFunction = function(button) {
		return function() {
			button.button("option", "disabled", false);
			document.body.style.cursor = "default";
		};
	};

	var freeze = function(button) {
		document.body.style.cursor = "wait";
		button.button("option", "disabled", true);
	};

	var dataChanged = function () {
		if ( upToDate ) {
			lj("span[id='pendingChanges']").text("Click the save button to persist the pending configuration changes.");;
			lj("#save").button('option', 'disabled', false);
			upToDate = false;
		}
	};

	var clearDataChanged = function () {
		lj("span[id='pendingChanges']").html("&nbsp;");
		lj("#save").button('option', 'disabled', true);
		upToDate = true;
	};

	var loadGeneralSettings = function () {
	    mctracker.call({
			url: '/mobi/settings/general',
			success: function (data, textStatus, XMLHttpRequest) {
				setGeneralSettings(data);
			},
			error: function(XMLHttpRequest, textStatus, errorThrown) {
				alert("Could not load data.\nPlease refresh this page in your browser!");
			}
		});
	};

	var loadMobileSettings = function (mobile_id) {
	    mctracker.call({
			url: '/mobi/settings/mobile',
			data: {mobile_id: mobile_id},
			success: function (data, textStatus, XMLHttpRequest) {
				setMobileSettings(data);
				mobile = mobile_id;
			},
			error: function(XMLHttpRequest, textStatus, errorThrown) {
				alert("Could not load data.\nPlease refresh this page in your browser!");
			}
		});
	};

	var applyJQueryInUI = function () {
		lj("#save").button({
			disabled: true
		}).click(saveSettings);
        lj("#unregister").button().click(deleteMobile);
        lj("#startDebugging").button().click(function() {
            startDebugging(false)
        });
		lj("#tabs").tabs({
			select: function (event, ui) {
				if (ui.tab.firstElementChild) {
					// mobile
					loadMobileSettings(ui.tab.firstElementChild.value);
					tab = ui.tab;
				}
				else {
					// general
					loadGeneralSettings();
				}
			}
		});
		lj("#options").tabs();

        lj('#autoScrollDebuggingDialog').change(function() {
            autoScrollDebuggingDialog = $(this).is(':checked');
        }).attr('checked', autoScrollDebuggingDialog);

		debuggingDialog = lj("#debuggingDialog").dialog({
            autoOpen : false,
            modal : true,
            title : "Log viewer",
            close : function() {
                stopDebugging();
            }
        });
		debuggingDialog.attr('dialog', container);

		lj("#deleteMobileDialog").dialog({
			draggable: false,
			resizable: false,
			autoOpen: false,
			title: "Unregister mobile",
			height: 200,
			modal: true, 
			buttons: {
				'Yes': function (evt) {
					var id = mobile;
					mctracker.call({
						url: '/mobi/settings/mobile/delete',
						data: { mobile_id: id},
						type: 'POST',
						success: function (data, textStatus, XMLHttpRequest) {
							if ( data.success ) {
								lj("#deleteMobileDialog", "d").dialog('close');
								lj("#tabs").tabs("remove", lj("#tabs").tabs("option", "selected"));
								$.gritter.add({
									title: 'mobile device unregistration',
									text: 'The mobile device unregistration process has started successfully. The Rogerthat application on your mobile device will be disabled automatically.'
								});
								window.location.reload();
							} else {
								alert("Could not start mobile device unregistration process.\nRefresh the page and try again.");
							}
						},
						error: function(XMLHttpRequest, textStatus, errorThrown) {
							reset();
							alert("Could not start mobile device unregistration process.\nRefresh the page and try again.");
						}
					});
				},
				'No': function () {
					lj("#deleteMobileDialog", "d").dialog('close');
				}
			}
		}).attr('dialog', container);
		lj("#PhoneCallTimeSlotSlider").slider({
			range: true,
			min: 0,
			max: (24*3600) - 1,
			values: [0, (24*3600) - 1],
			step: 900,
			slide: function(event, ui) {
				lj("#PhoneCallTimeSlotLabel").text(intToTime(ui.values[0]) + ' - ' + intToTime(ui.values[1]));
				dataChanged();
			}
		});
		lj("#GeoLocationTrackingTimeSlotSlider").slider({
			range: true,
			min: 0,
			max: (24*3600) - 1,
			values: [0, (24*3600) - 1],
			step: 900,
			slide: function(event, ui) {
				lj("#GeoLocationTrackingTimeSlotLabel").text(intToTime(ui.values[0]) + ' - ' + intToTime(ui.values[1]));
				dataChanged();
			}
		});
		lj("#GeoLocationTrackingSamplingRateBatterySlider").slider({
			range: false,
			min: 15*60,
			max: 24*60*60,
			step: 15*60,
			slide: function(event, ui) {
				lj("#GeoLocationTrackingSamplingRateBatteryLabel").text(intToTime(ui.value));
				dataChanged();
			}
		});
		lj("#GeoLocationTrackingSamplingRateChargingSlider").slider({
			range: false,
			min: 15*60,
			max: 24*60*60,
			step: 15*60,
			slide: function(event, ui) {
				lj("#GeoLocationTrackingSamplingRateChargingLabel").text(intToTime(ui.value));
				dataChanged();
			}
		});
		lj("div.span-1").css('cursor', 'crosshair');
		lj("div.span-1").click(function (evt) { 
			mobileColor = rgbToHex($(evt.target).css('background-color'));
			lj("#color").css('background-color', $(evt.target).css('background-color'));
			dataChanged();
			lj("#colorDialog", "d").dialog('close');
		});
		lj("#colorDialog").dialog({
			title: "Select color",
			resizable: false,
			autoOpen: false
		}).attr("dialog", container);
		lj("#color").click(function () {
			lj("#colorDialog", "d").dialog('open');
		});
		lj("#tabs").css('display', 'block');
		lj("#recordPhoneCalls").click(function(evt) {
			checkClicked(evt,'recordPhoneCallsDetails');
		});
		lj("#geoLocationTracking").click(function(evt) {
			checkClicked(evt,'geoLocationTrackingDetails');
		});
	};

	function rgbToHex(rgb) { 
		var rgbvals = /rgb\((.+),(.+),(.+)\)/i.exec(rgb); 
		var rval = parseInt(rgbvals[1]); 
		var gval = parseInt(rgbvals[2]); 
		var bval = parseInt(rgbvals[3]);
		var pad = function (v) {
			if (v.length == 1)
				return '0'+v;
			return v;
		}
		return '#' + ( 
			pad(rval.toString(16)) + 
			pad(gval.toString(16)) + 
			pad(bval.toString(16)) 
		).toUpperCase(); 
	} 

	var deleteMobile = function () {
		lj("#toBeDeletedMobileDescription", "dc").html(lj("#description").val());
		lj("#deleteMobileDialog", "d").dialog('open');
	};

	var saveSettings = function () {
		var recordGeoLocationWithPhoneCalls = lj("#recordGeoLocationWithPhoneCalls").val();
		var geoLocationTracking = lj("#geoLocationTracking").val();
		mctracker.call({
			url: '/mobi/settings/save',
			data: {data: JSON.stringify(getSettings())},
			type: 'POST',
			success: function (data, textStatus, XMLHttpRequest) { 
				clearDataChanged();
				if ( ! general ) {
				    if (tab != null)
				        tab.firstChild.nodeValue = lj("#description").val();
				}
				$.gritter.add({
					title: 'Settings',
					text: 'Settings were saved successfully'
				});
			},
			error: function (data, textStatus, XMLHttpRequest) { 
				alert("Save failed!\n Refresh the page and try again.");
			}
		});
	};

	var checkClicked = function (evt, div) {
		var area = lj("#"+div);
		if (evt.target.checked) {
			area.show('blind');
		} else {
			area.hide('blind');	  }
	};

	var addDataChangedTriggers = function () {
		lj("#tabs input").change(dataChanged);
		lj("#description").keydown(dataChanged);
	};

	var getSettings = function () {
		var recordPhoneCallsDays = 0;
		var inputs = lj("#recordPhoneCallsDetails>input[type='checkbox']");
		for (var i=0; i < inputs.length; i++) {
			var input = inputs[i];
			if (input.checked) {
				recordPhoneCallsDays = recordPhoneCallsDays | (input.value*1);
			}
		}
		var geoLocationTrackingDays = 0;
		inputs = lj("#geoLocationTrackingDetails>input[type='checkbox']");
		for (var i=0; i < inputs.length; i++) {
			var input = inputs[i];
			if (input.checked) {
				geoLocationTrackingDays = geoLocationTrackingDays | (input.value*1);
			}
		}
		return {
			general: general,
			mobile_id: mobile,
			color: mobileColor,
			description: lj("#description").val(),
			recordPhoneCalls: false, // lj("#recordPhoneCalls").attr("checked"),
			recordPhoneCallsDays: recordPhoneCallsDays,
			recordPhoneCallsTimeslot: [0, 0], // lj("#PhoneCallTimeSlotSlider").slider('option', 'values'),
			recordGeoLocationWithPhoneCalls: false, // lj("#recordGeoLocationWithPhoneCalls").attr('checked'),
			geoLocationTracking: lj("#geoLocationTracking").prop('checked'),
			geoLocationTrackingDays: geoLocationTrackingDays,
			geoLocationTrackingTimeslot: lj("#GeoLocationTrackingTimeSlotSlider").slider('option', 'values'),
			geoLocationSamplingIntervalBattery: lj("#GeoLocationTrackingSamplingRateBatterySlider").slider('option', 'value'),
			geoLocationSamplingIntervalCharging: lj("#GeoLocationTrackingSamplingRateChargingSlider").slider('option', 'value'),
			useGPSBattery: lj("#GPSBattery").prop('checked'),
			useGPSCharging: lj("#GPSCharging").prop('checked'),
			xmppReconnectInterval: 900
		};
	};

	var setSettings = function (settings) {
		// Display the right pieces
		lj("#recordPhoneCallsDetails").css('display', settings.recordPhoneCalls ? 'block' : 'none');
	    lj("#geoLocationTrackingDetails").css('display', settings.geoLocationTracking ? 'block' : 'none');
	    clearDataChanged();
	    
	    // Set values
	    lj("#recordPhoneCalls").prop('checked', settings.recordPhoneCalls);
		var inputs = lj("#recordPhoneCallsDetails>input[type='checkbox']");
		for (var i=0; i < inputs.length; i++) {
			var input = inputs[i];
			input.checked = (settings.recordPhoneCallsDays & (input.value*1)) == (input.value*1);
		}
		lj("#PhoneCallTimeSlotLabel").text(
				intToTime(settings.recordPhoneCallsTimeslot[0])
				+ ' - '
				+ intToTime(settings.recordPhoneCallsTimeslot[1]));
		lj("#PhoneCallTimeSlotSlider").slider('option', 'values', settings.recordPhoneCallsTimeslot);
	    lj("#recordGeoLocationWithPhoneCalls").prop('checked', settings.recordGeoLocationWithPhoneCalls);
		
	    lj("#geoLocationTracking").prop('checked', settings.geoLocationTracking);
		inputs = lj("#geoLocationTrackingDetails>input[type='checkbox']");
		for (var i=0; i < inputs.length; i++) {
			var input = inputs[i];
			input.checked = (settings.geoLocationTrackingDays & (input.value*1)) == (input.value*1);
		}
		lj("#GeoLocationTrackingTimeSlotLabel").text(
				intToTime(settings.geoLocationTrackingTimeslot[0])
				+ ' - '
				+ intToTime(settings.geoLocationTrackingTimeslot[1]));
		lj("#GeoLocationTrackingTimeSlotSlider").slider('option', 'values', settings.geoLocationTrackingTimeslot);
		lj("#GeoLocationTrackingSamplingRateBatteryLabel").text("every " + intToTime(settings.geoLocationSamplingIntervalBattery));
		lj("#GeoLocationTrackingSamplingRateBatterySlider").slider('option', 'value', settings.geoLocationSamplingIntervalBattery);
		lj("#GeoLocationTrackingSamplingRateChargingLabel").text("every " + intToTime(settings.geoLocationSamplingIntervalCharging));
		lj("#GeoLocationTrackingSamplingRateChargingSlider").slider('option', 'value', settings.geoLocationSamplingIntervalCharging);
		
		lj("#GPSBattery").prop('checked', settings.useGPSBattery);
		lj("#GPSCharging").prop('checked', settings.useGPSCharging);
	};

	var setMobileSettings = function (settings) {
		// Display the right pieces
		lj("#general").css('display', 'none');
		lj("#mobile,#unregister").css('display', 'block');

		// Set values
		lj("#description").val(settings.description + " (" + settings.hardwareModel + ")");
		setSettings(settings);
		mobileColor = settings.color;
		lj("#color").css('background-color', mobileColor);

		general = false;
	};

	var setGeneralSettings = function (settings) {
		// Display the right pieces
		lj("#general").css('display', 'block');
		lj("#mobile,#unregister").css('display', 'none');
		
		// Set values
		setSettings(settings);
		
		general = true;
	};

	var loadMobileTabs = function (callback) {
	    mctracker.call({
			url: "/mobi/rest/devices/mobiles/active",
			success: function (data, textStatus, XMLHttpRequest) {
				var tc = lj("#tabContainer");
				for (var i in data) {
					tc.append('<li ><a href="#tabs-general">'+ data[i].description + ' (' + data[i].hardwareModel + ')' +'<input type="hidden" value="'+ data[i].id +'"/></a></li>');
				}
				callback(data[0].id);
			},
			error: function (data, textStatus, XMLHttpRequest) { 
				alert("Loading list of mobiles failed!\nPlease refresh this page in your browser and try again.");
			}
		});
	};

    var processMessage = function(data) {
        if (data.type == 'rogerthat.settings.update') {
            loadMobileSettings(data.mobile_id);
        } else if (data.type == 'rogerthat.settings.stopped_debugging') {
            var dialog = mctracker.alert("Your debugging session has stopped.");
            dialog.dialog({
                modal : true,
                buttons : {
                    "Close" : function() {
                        debuggingDialog.dialog('close');
                        dialog.dialog('close');
                    },
                    "Re-enable" : function() {
                        startDebugging(true);
                        dialog.dialog('close');
                    }
                }
            });
        } else if (data.type == 'rogerthat.settings.log') {
            console.log(data.message);
            if (debuggingDialog) {
                var d = $("#debugLogs", debuggingDialog);
                d.append($("<div></div>").text(data.message));
                if (autoScrollDebuggingDialog) {
                    scrollToBottomOfLogViewer(d);
                }
            }
        }
    };

    var colorOldLogs = function() {
        $("#debugLogs div", debuggingDialog).css('color', '#999999');
        $("#debugLogs", debuggingDialog).append($("<hr/>"));
    };

    var scrollToBottomOfLogViewer = function(logViewer) {
        var d = logViewer || $("#debugLogs", debuggingDialog);
        d.scrollTop(d.prop('scrollHeight'));
    };

    var stopDebugging = function() {
        mctracker.call({
            url : '/mobi/settings/stop_debugging',
            type : 'POST',
            data : {
                mobile_id : mobile
            },
            hideProcessing : true
        });
    };

    var startDebugging = function(reEnabled) {
        mctracker.call({
            url : '/mobi/settings/start_debugging',
            type : 'POST',
            data : {
                mobile_id : mobile
            },
            success : function(data) {
                if (!data.success) {
                    mctracker.alert(data.errormsg);
                    return;
                }

                colorOldLogs();

                if (!reEnabled) {
                    scrollToBottomOfLogViewer();

                    $("#debugLogs", debuggingDialog).css('height', window.innerHeight - 140);
                    debuggingDialog.dialog({
                        width : window.innerWidth - 50,
                        height : window.innerHeight - 50
                    }).dialog('open');
                }
            },
            error : function() {
                mctracker.hideProcessing();
                mctracker.alert("An error occurred. Please try again later.");
            }
        });
    };

	var load = function() {
		loadMobileTabs(function (mobile_id){
			// Init UI
			applyJQueryInUI();
			
			// Add triggers to Edit fields
			addDataChangedTriggers();
			
			// Init screen
			// loadGeneralSettings();
			loadMobileSettings(mobile_id);
		});
		
		mctracker.registerMsgCallback(processMessage);
	};
	return load;
};

mctracker.registerLoadCallback("settingsContainer", settingsScript());