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

var friendMapScript = function () {
	var container = "#friendMapContainer";
	var lj = mctracker.getLocaljQuery(container);
	var locations = [];
	var locationMap;
	var lastPollTime;
	var date;
	
	function applyJQueryInUI() {
		date = lj("#date");
		// Display map of New York City
		var myOptions = {
			mapTypeId: google.maps.MapTypeId.ROADMAP
		};
		locationMap = new google.maps.Map(lj("#map").get(0), myOptions);
		setZoomLevel([], locationMap);
		
		// Now notify the server to ping the users for their location
		mctracker.call({
			url: "/mobi/rest/location/get_friend_locations",
			success : function (data) {
				if (data == 0) {
					mctracker.alert("You don't seem to have any friends which share their location. Request your friends to share their location via the 'My friends' panel.");
				} else {
					$.gritter.add({
						title: "Location",
						text: "The server has contacted all your location sharing friends to calculate their location. Please hang on ..."
					});
				}
				lastPollTime = new Date().getTime();
				window.setTimeout(timer, 1000);
			},
			error: mctracker.showAjaxError
		});
		
		lj("#poll").click(function () {
			mctracker.call({
				url: "/mobi/rest/location/get_friend_locations",
				success : function () {
					lastPollTime = new Date().getTime();
				},
				error: mctracker.showAjaxError
			});
		});
	};
	
	var timer = function () {
		date.text(mctracker.intToHumanTime((new Date().getTime()-lastPollTime)/1000));
		window.setTimeout(timer, 1000);
	};
	
	var redrawMap = function () {
		$.each(locations, function (index, data) {
			if (data.onMap) {
				data.locationMarker.setPosition(new google.maps.LatLng(data.location.latitude/1000000, data.location.longitude/1000000));
				data.locationAccuracyCircle.setRadius(data.location.accuracy);
			} else {
				data.onMap = true;
				data.friendObject = getFriendByEmail(data.friend);
				data.image = new google.maps.MarkerImage("/unauthenticated/mobi/cached/avatar/"+data.friendObject.avatarId,
					// This marker is 50 pixels wide by 50 pixels tall.
					new google.maps.Size(50, 50),
					// The origin for this image is 0,0.
					new google.maps.Point(0,0),
					// The anchor for this image is the base of the flagpole at 25,25.
					new google.maps.Point(25,25));
	            data.locationMarker = new google.maps.Marker({
					position: new google.maps.LatLng(data.location.latitude/1000000, data.location.longitude/1000000),
					map: locationMap,
					title: getFriendName(data.friendObject) + " on " + Date(data.location.timestamp *1000),
	                icon: data.image
	            });
	            data.locationAccuracyCircle = new google.maps.Circle({
	                    map: locationMap,
	                    radius: data.location.accuracy
	            });
	            data.locationAccuracyCircle.bindTo('center', data.locationMarker, 'position');
			}
			setZoomLevel($.map(locations, function (data, index) {
            	return {
            		latitude: data.location.latitude / 1000000,
            		longitude: data.location.longitude / 1000000
            	}
            }), locationMap);
		});
	};
	
	var processMessage = function (data) {
		if (data.type == 'rogerthat.location.location_response') {
			var location = mctracker.get(locations, function (location, index) {return data.friend == location.friend});
			if (location)
				location.location = data.location;
			else
				locations.push(data);
			redrawMap();
		}
	};
		
	return {
		applyJQueryInUI: applyJQueryInUI,
		init: function () {
			mctracker.registerMsgCallback(processMessage);
			
			mctracker.loadGoogleMaps();
		}
	};
};

var thizzzzz = friendMapScript();
mctracker.registerLoadCallback("friendMapContainer", thizzzzz.init);

mctracker.mapsLoadedCallbacks.push(function() {thizzzzz.applyJQueryInUI();});