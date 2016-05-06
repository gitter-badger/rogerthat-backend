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

$(function () {
	
	var getParameterByName = function (name) {
	    var match = RegExp('[?&]' + name + '=([^&]*)').exec(window.location.search);
	    return match && decodeURIComponent(match[1].replace(/\+/g, ' '));
	};
	
	var htmlEncode = function (value) {
		value = value.replace("\r", "");
		var lines = value.split(/\n/);
		var paragraphs = [];
		$.each(lines, function (i, str) {
			paragraphs.push($('<div/>').text(str).html());
		});
		return paragraphs.join('<br>');
	};
	
	var lat_center = getParameterByName('lat');
	var lon_center = getParameterByName('lon');
	var center = lat_center && lon_center ? new google.maps.LatLng(parseFloat(lat_center), parseFloat(lon_center)) : new google.maps.LatLng(50.623211, 4.438007);
	var zoom = parseInt(getParameterByName('zoom') || '8');
	
    var mapOptions = {
    		zoom: zoom,
    		center: center
	};
    var map = new google.maps.Map(document.getElementById('map-canvas'), 
    		mapOptions);
    
    var app_id = getParameterByName("app_id") || null;
    var markers = {};
    var infoWindow = null;
    
    var last_call = new Date().getTime();
    
    var getSearchCriteria = function () {
    	last_call = new Date().getTime();
        var center = map.getCenter();
        var map_bounds = map.getBounds();
        var distance = google.maps.geometry.spherical.computeDistanceBetween(map_bounds.getNorthEast(), map_bounds.getSouthWest());
        var radius_in_km = Math.round(distance/2000,0) + 1;
        var params = {
			lat: center.lat(),
			lon: center.lng(),
			distance: radius_in_km,
			last_call: last_call
        };
        if (app_id)
        	params['app_id'] = app_id;
        return params;
    };
    
    var getServices = function (search_criteria, cursor) {
    	if (search_criteria.last_call != last_call)
    		return;
        if (cursor)
        	search_criteria['cursor'] = cursor;
        $.ajax({
        	url: '/mobi/rest/service_map/load',
        	data: search_criteria,
        	success: function (data) {
        		if (data.cursor && search_criteria.last_call == last_call)
        			getServices(search_criteria, data.cursor);
        		$.each(data.services, function (i,service) {
            		var marker = markers[service.hash];
            		if (!marker) {
            			var coords = new google.maps.LatLng(service.lat, service.lon);
            			marker = new google.maps.Marker({
            				position: coords,
                  	      	map: map,
                  	      	cursor: 'pointer'
                  	  	});
            			markers[service.hash] = marker;
            			
            			google.maps.event.addListener(marker, 'click', function() {
            				if (infoWindow)
            					infoWindow.close()
            				infoWindow = new google.maps.InfoWindow({
            					content: '<div id="content">'+
            				      '<div id="siteNotice">'+
            				      '</div>'+
            				      '<h1 id="firstHeading" class="firstHeading">'+ htmlEncode(service.name) +'</h1>'+
            				      '<div id="bodyContent">'+
            				      '<p>'+ htmlEncode(service.description) +'</p>'+
            				      '</div>'+
            				      '</div>'
            				});
            				google.maps.event.addListener(map, 'closeclick', function () {
            					infoWindow = null;
            			    });
            				infoWindow.open(map, marker);
            			});
            		}
        		});
        		
        	},
        	error: function () {
        		if (console)
        			console.log("An error occurred while loading data. Please reload your browser.");
        	}
        });
    };
    google.maps.event.addListener(map, 'bounds_changed', function () {
    	getServices(getSearchCriteria(), null);
    });
    
});