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

var trackingScript = function () {
	var locationRecords = null;
	var locationMap = null;
	var locationMarkers = [];
	var mobileColors = null;
	var day = 0;
	var polyLines = [];
	
	var container = "#trackingContainer";
	var lj = mctracker.getLocaljQuery(container);

	var drawPolyLines = function () {
		for (var i in polyLines) {
			polyLines[i].setMap(null);
		}
		polyLines = [];
		var mobiles = [];
		for (var i in locationRecords) {
			var mobile = locationRecords[i].mobile;
			if ( ! mobiles[mobile]) {
				mobiles[mobile] = [];
			}
		}
		for (var mobile in mobiles) {
			for (var i in locationRecords) {
				var record = locationRecords[i];
				if ( record.mobile == mobile) {
					mobiles[mobile][mobiles[mobile].length] = new google.maps.LatLng(record.lat, record.lon);
				}
			}
			polyLines[mobile] = new google.maps.Polyline({
				map: locationMap,
				path: mobiles[mobile],
				strokeColor: mobileColors[mobile]
			});
		}
	};

	var hideMarkers = function () {
		for (var key in locationMarkers) {
			locationMarkers[key].marker.setVisible(false);
			locationMarkers[key].circle.setRadius(0);
		}
	};

	var locationMarker = function(key) {
		var marker = locationMarkers[key]; 
		if ( ! marker ) {
			marker = {
				marker: new google.maps.Marker({
					map: locationMap,
					title: key
				}),
				circle: new google.maps.Circle({
					map: locationMap
				})
			};
			marker.circle.bindTo('center', marker.marker, 'position');
			locationMarkers[key] = marker;
		}
		return marker;
	};

	var visibleMarkers = function(time) {
		var markers = [];
		var invisibleMarkers = [];
		for (var i=0; i < locationRecords.length && locationRecords[i].fromTimestamp - day <= time; i++) {
			var key = locationRecords[i].mobile;
			if ( ! markers[key] ) {
				if (! invisibleMarkers[key] && lj("#configuration ol input[value="+key+"]").prop('checked')) {
					markers[key] = {
						marker: locationMarker(key),
						record: locationRecords[i]
					};
				} else {
					invisibleMarkers[key] = "dummy"; // prevent dom lookup for next record
				}
			} else {
				markers[key].record = locationRecords[i];
			}
		}
		return markers;
	};

	var allMarkers = function () {
		var markers = [];
		for (var i=locationRecords.length - 1; i >= 0; i--) {
			var key = locationRecords[i].mobile;
			if ( ! markers[key] ) {
				if (lj("#configuration ol input[value="+key+"]").prop('checked')) {
					markers[key] = {
						marker: locationMarker(key),
						record: locationRecords[i]
					};
				}
			}
		}
		return markers;
	};

	var displayMarkers = function(markers) {
		for (var key in markers) {
			var marker = markers[key];
			marker.marker.marker.setPosition(new google.maps.LatLng(marker.record.lat, marker.record.lon));
			marker.marker.marker.setVisible(true);
			marker.marker.marker.setTitle(marker.record.mobile + " on " + Date(marker.record.fromTimestamp));
			marker.marker.marker.setIcon(
					new google.maps.MarkerImage(
							"http://chart.apis.google.com/chart?chst=d_fnote_title&chld=arrow_d|1|003058|h|" 
									+ escape(marker.record.mobile) 
									+ "|" 
									+ escape(intToTime(marker.record.fromTimestamp - day))
									+ "|"
									+ escape(intToTime(marker.record.tillTimestamp - day))));
			marker.marker.circle.setRadius(marker.record.accuracy);
		}
	};

	var handleMap = function () {
		if (locationMap == null) {
			var myOptions = {
				mapTypeId: google.maps.MapTypeId.ROADMAP
			};
			locationMap = new google.maps.Map(document.getElementById("map"), myOptions);
		}
	};

	var updateMap = function () {
		displayCheckboxes();
		handleMap();
		setZoomLevel(locationRecords, locationMap);
		hideMarkers();
		drawPolyLines();
		displayMarkers(allMarkers());
	};

	var updateMarkers = function () {
		var locValue = lj("#slider").slider("option","value");
		displayMarkers(visibleMarkers(locValue));
	};

	var loadTrackingData = function () {
		lj("#map").css("display", "none");
		lj("#loading").css('display', 'block');
		startLoading(lj("#loading"));
		day = mctracker.handleTimezone(lj("#date").datepicker("getDate").valueOf() / 1000);
		document.body.style.cursor = "wait";
		mctracker.call({
			url: '/mobi/loadtrackingdata?day='+day,
			success: function (data, textStatus, XMLHttpRequest) {
				locationRecords = data.records;
				for (var i in locationRecords) {
					var lr = locationRecords[i];
					lr.fromTimestamp = mctracker.handleTimezone(lr.fromTimestamp);
					lr.tillTimestamp = mctracker.handleTimezone(lr.tillTimestamp);
				}
				mobileColors = [];
				for (var i=0; i < data.colors.length; i++) {
					mobileColors[data.colors[i][0]] = data.colors[i][1];
				}
				var sliderObj = lj("#slider");
				if (locationRecords.length != 0) {
					var pos = locationRecords[locationRecords.length - 1].tillTimestamp - day
					sliderObj.slider("option", "disabled", false);
					sliderObj.slider("option", "max", 3600*24 - 1);
					sliderObj.slider("option", "value", pos);
					lj("#time").text(intToTime(pos));
				} else {
					sliderObj.slider("option", "disabled", true);
					sliderObj.slider("option", "value", 0);
					lj("#time").text("");
				}
				stopLoading();			
				lj("#loading").css('display', 'none');
				lj("#map").css("display", "block");
				updateMap();
				document.body.style.cursor = "default";
			},
			error: function(XMLHttpRequest, textStatus, errorThrown) {
				document.body.style.cursor = "default";
			}
		});
	};

	var displayCheckboxes = function () {
		var conf = lj("#configuration");
		conf.empty();
		conf.append('<ol />');
		var ol = lj("#configuration ol");
		for (var mobile in mobileColors) {
			ol.append('<li style="color: '+ mobileColors[mobile] +';"><input type="checkbox" value="'+ mobile +'" checked/>'+ mobile +'</li>');
		}
		ol.css('display', 'inline-table');
		lj("#configuration ol input").change(function (evt, ui) {
			var mobile = evt.target.value;
			if ( evt.target.checked ) {
				polyLines[mobile].setMap(locationMap);
			} else {
				polyLines[mobile].setMap(null);
				var marker = locationMarkers[mobile];
				if ( marker ) {
					marker.marker.setVisible(false);
					marker.circle.setRadius(0);
				}
			}
			updateMarkers();
		});
	};

	var load = function() {
		lj("#date").datepicker({
			onSelect: function(dateText, inst) {
				loadTrackingData();
			}
		});
		lj("#slider").slider({
			min: 0,
			max: 24*3600 - 1,
			step: 10,
			disabled: true,
			slide: function(event, ui) {
				updateMarkers();
				lj("#time").text(intToTime(ui.value));
			}
		});
		loadTrackingData();
	};
	
	return load;
};

mctracker.registerLoadCallback("trackingContainer", trackingScript());