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
	
	var friendWithTooltipTemplate = [
         '<div class="{{if left}}thumbnail-item-left{{else}}thumbnail-item{{/if}}" friend="${friend.email}">',
         '   <img src="/unauthenticated/mobi/cached/avatar/${friend.avatarId}" class="avatar thumbnail{{if resize}}-resize{{/if}} action-link" friend="${friend.email}"/>',
         '   {{if badge_url}}<img src="${badge_url}" class="avatar_badge"/>{{/if}}',
         '</div>'
     ].join('');
	
	var settings = {
		left : true,
		resize : true,
		tooltip : '',
		badge_url : '',
		speed : 'fast',
		size : 0,
		rounded : false,
		loader : null
	};

	var init = function (options) {
		if (! options)
			$.error('avatar plugin needs options');
		if ( ! options['friend'])
			$.error('friend option required');
		$.each(settings, function (key, value) {
			if (options[key] == undefined)
				options[key] = value;
		});
		var tooltip_html = $('<div class="tooltip mcblue"></div>').attr('friend', options.friend.email);
		if (options.tooltip)
			tooltip_html.html(options.tooltip);
		$("#tooltipArea").append(tooltip_html);
		return this.each(function () {
			var html = $.tmpl(friendWithTooltipTemplate, options);
		    var img = $("img.action-link", html).mouseenter(function(e) {
		    	if (! options.tooltip)
		    		return;
		        tooltip_html.css({'top': e.pageY + 10,'left': e.pageX + 20}).fadeIn(options.speed);
		    }).mousemove(function(e) {
		    	if (! options.tooltip)
		    		return;
		        // This line causes the tooltip will follow the mouse pointer
		        tooltip_html.css({'top': e.pageY + 10,'left': e.pageX + 20});
		    }).mouseleave(function() {
		    	if (! options.tooltip)
		    		return;
		        // Reset the z-index and hide the image tooltip
		    	tooltip_html.fadeOut(options.speed);
		    });
		    if (options.rounded)
		    	img.addClass('rounded');
		    if (options.size) 
		    	img.css('width', options.size +"px").css('height', options.size+"px");
		    if ( options['click'])
		    	img.click(options.click);
		    if (options.friend.email == 'dashboard@rogerth.at')
		    	img.attr('src', '/static/images/nuntiuz.png');
		    if (options.loader) {
		    	options.loader.addTaskCount();
		    	img.load(options.loader.taskDone).error(options.loader.taskDone);
		    }
		    $(this).empty().append(html).data('avatar', options.friend);
		});
	};

	var methods = {
		init : init,
		friend : function() {
			return $(this).data('avatar');
		}
	};

	$.fn.avatar = function( method ) {
    
		// Method calling logic
		if ( methods[method] ) {
			return methods[ method ].apply( this, Array.prototype.slice.call( arguments, 1 ));
		} else if ( typeof method === 'object' || ! method ) {
			return methods.init.apply( this, arguments );
		} else {
			$.error( 'Method ' +  method + ' does not exist on jQuery.avatar' );
		}    
	  
	};

})( jQuery );