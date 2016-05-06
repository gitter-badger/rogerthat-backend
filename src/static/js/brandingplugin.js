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

(function( $ ){
	
	var dummy = function () {};
	
	var settings = {
		branding: null,
		message: null,
		timestamp: null,
		height: null,
		loader: {
			progress: dummy,
			addTaskCount: dummy,
			taskDone: dummy
		},
		onBrandingConfig: dummy,
		onPokeClicked: dummy
	};

	var init = function (options) {
		$.each(settings, function (key, value) {
			if (options[key] == undefined)
				options[key] = value;
		});
		return this.each(function () {
			var iframe = $(this);
			if (! iframe.is('iframe')) {
				alert("Incorrect usage of brandingplugin. Only iframe elements are supported.");
				return false;
			}
			if (! options.branding) {
				alert("Incorrect usage of brandingplugin. Option branding is required.");
				return false;
			}
	    	var iframeLoadCallBackSet = false;
	    	options.loader.addTaskCount(3)
	    	iframe.show().attr('src', '/branding/' + options.branding + '/branding.html');
	        if (!iframeLoadCallBackSet) {
	            iframe.load(function () {
	            	options.loader.taskDone();
		        	options.loader.progress(10);
	                var branding_doc = iframe.get(0).contentWindow.document;
	                var color_scheme = $("meta[property=\"rt:style:color-scheme\"]", branding_doc).attr("content");
	                var background_color = $("meta[property=\"rt:style:background-color\"]", branding_doc).attr("content");
	                var show_header = $("meta[property=\"rt:style:show-header\"]", branding_doc).attr("content");
	                show_header = show_header && show_header.toLowerCase() == 'true';

	                if (!color_scheme)
	                    color_scheme = 'light';
	                
	                if (!background_color)
	                	background_color = color_scheme == 'light' ? 'white' : 'gray';
	                
	                options.onBrandingConfig({
	                	color_scheme: color_scheme,
	                	background_color: background_color,
	                	show_header: show_header
	                });

	                if (options.message)
                        $("nuntiuz_message", iframe.contents()).replaceWith($('<span>'+mctracker.htmlize(options.message)+'</span>'));
	                if (options.timetamp)
	                	$("nuntiuz_timestamp", iframe.contents()).replaceWith($('<span>'+mctracker.formatDate(options.timestamp)+'</span>'));
                    if (options.identityName)
                        $("nuntiuz_identity_name", iframe.contents()).replaceWith($('<span>'+mctracker.htmlize(options.identityName)+'</span>'));
	                
	                $('a[href]', iframe.contents()).each(function () {
	                    var thizz = $(this);
	                    var href = thizz.attr('href');
	                    if (href.indexOf("poke://") == 0) {
	                        thizz.attr('href', '#');
	                        thizz.click(function () {
	                            options.onPokeClicked(href.substring(7));
	                        });
	                    } else if (href.indexOf("tel:") == 0) {
                            thizz.attr('href', '#');
	                        thizz.click(function () {
	                            mctracker.alert("Call " + href.substring(4));
	                        });
	                    }
	                });

	                if (options.height == null) {
	                    var body = this.contentWindow.document.body;
	                    setTimeout(function () {
	                        options.loader.taskDone();
	                        options.loader.progress(10);
	                        var iframe_height = $(body).height();
	                        iframe.height(iframe_height);
	                        setTimeout(function () {
	                            options.loader.progress(10);
	                            iframe_height = body.scrollHeight;
	                            iframe.height(iframe_height);
	                            options.loader.taskDone();
	                        }, 50);
	                    }, 50);
	                } else {
	                    iframe.height(options.height);
	                    options.loader.taskDone();
	                    options.loader.taskDone();
	                    options.loader.progress(20);
	                }
	            });
	            iframeLoadCallBackSet = true;
	        }			
		});
	};
	
	var methods = {
		init : init
	};

	$.fn.mcbranding = function( method ) {
		// Method calling logic
		if ( methods[method] ) {
			return methods[ method ].apply( this, Array.prototype.slice.call( arguments, 1 ));
		} else if ( typeof method === 'object' || ! method ) {
			return methods.init.apply( this, arguments );
		} else {
			$.error( 'Method ' +  method + ' does not exist on jQuery.mcbranding' );
		}
	};

})( jQuery );