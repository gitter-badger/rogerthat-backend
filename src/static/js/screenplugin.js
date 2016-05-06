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
	
	var screenTemplate = ['<div class="mc_screen">',
	                      '    <div class="mc_toolbar">',
	                      '        <button style="display: none;" class="mc_back_button">Back</button>',
	                      '        <button style="display: none;" class="mc_left_button">Left</button>',
	                      '        <button style="display: none;" class="mc_right_button">Right</button>',
	                      '    </div>',
	                      '    <div class="mc_screen_container mc_screen_content mcoutofscreen">',
	                      '        <div class="mc_screen_container_content"></div>',
	                      '    </div>',
	                      '    <div class="mc_screen_nothing_to_display mc_screen_content">',
	                      '        <div class="mc_screen_centered">Nothing to display</div>',
	                      '    </div>',
	                      '    <div style="display: none;" class="mc_screen_loading mc_screen_content">',
	                      '        <div class="mc_screen_centered">',
	                      '            Loading ...<br>',
	                      '            <div class="mc_screen_loading_pb"></div>',
	                      '        </div>',
	                      '    </div>',
	                      '    <div style="display: none;" class="mc_screen_waiting mc_screen_content">',
	                      '        <div class="mc_screen_progress_popup">',
	                      '            <div class="mc_screen_waiting_label">processing ...</div>',
	                      '            <div class="mc_screen_waiting_pb"></div>',
	                      '        </div>',
	                      '    </div>',
	                      '</div>'].join('\n');
	
// example button setting:
//	var settings = {
//		title: null,
//		leftButton: {
//			text: 'Disconnect',
//			click: function () { alert('test'); }
//		},
//		rightButton: null
//	};
	
	var configureButton = function (control, config) {
		var click = function() {
			$(this).mouseout();
			config.click.apply(this, arguments);
		};
		control.text(config.text).show().unbind("click").click(click).data('click', click).removeAttr('disabled');
	};
	
	var configureButtons = function (context, newLeftButton, newRightButton, backHandler) {
		var screen_stack = context.data('screen_stack');
		context.data('back_handler', backHandler);
		var leftButtonControl = $("div.mc_toolbar button.mc_left_button", context);
		var rightButtonControl = $("div.mc_toolbar button.mc_right_button", context);
		var backButtonControl = $("div.mc_toolbar button.mc_back_button", context);		
		if (screen_stack.length) {
			leftButtonControl.hide();
			backButtonControl.show().removeAttr('disabled');
		} else {
			backButtonControl.hide();
			if (newLeftButton) {
				configureButton(leftButtonControl, newLeftButton);
			} else {
				leftButtonControl.hide();
			}
		}
		if (newRightButton) {
			configureButton(rightButtonControl, newRightButton);
		} else {
			rightButtonControl.hide();
		}
	};
	
	var goBack = function (context, screen_stack, back_button) {
		var screen_content = $("div.mc_screen_container div.mc_screen_container_content", context);
		var screen_container = $("div.mc_screen_container", context);
		var running = false;
		return function () {
			if (running) return;
			back_button.attr('disabled', 'disabled');
			running = true;
			var backHandler = context.data('back_handler');
			if (backHandler)
				backHandler();
			screen_content.fadeOut('fast', function () {
				$("div.mc_screen_container div.mc_screen_container_content > div:not(.hidden)", context).remove();
				if (screen_stack.length) {
					var frame = screen_stack.pop();
					frame.html.removeClass("hidden");
					screen_content.fadeIn('fast', function () {
						screen_container.scrollTop(frame.scrollTop);
					});
					configureButtons(context, frame.leftButton, frame.rightButton);
				} else {
					screen_container.addClass("mcoutofscreen");
					screen_content.show();
					$("div.mc_screen_nothing_to_display", context).show();
					configureButtons(context, null, null);
				}
				back_button.attr('disabled', '');
				running = false;
			});
		};
	};	
	
	var back = function () {
		$(this).mouseout();
		$(this).data('back')();
	};
	
	var settings = {
		title: null,
		leftButton: null,
		rightButton: null,
		slimScroll: true
	};

	var init = function (options) {
		$.each(settings, function (key, value) {
			if (options[key] == undefined)
				options[key] = value;
		});
		return this.each(function () {
			var thizz = $(this);
			var html = $.tmpl(screenTemplate);
			thizz.append(html);
			if (options.slimScroll) {
				$("div.mc_screen_container_content", html).slimScroll({
					height: '504px',
					width: '320px'
				});
			}
			$("div.mc_screen_loading_pb, div.mc_screen_waiting_pb", html).progressbar({ value: 0 });
			var screen_stack = [];
			thizz.data('screen_stack', screen_stack);
			var leftButtonControl = $("div.mc_toolbar button.mc_left_button", thizz).button().text("Left");
			var rightButtonControl = $("div.mc_toolbar button.mc_right_button", thizz).button().text("Right");
			var backButtonControl = $("div.mc_toolbar button.mc_back_button", thizz).button().text("Back");		
			var back = goBack(thizz, screen_stack, backButtonControl);
			thizz.data('back', back);
			backButtonControl.click(back);
			configureButtons(thizz, options.leftButton, options.rightButton);			
		});
	};
	
	var load = function (mode, newLeftButton, newRightButton, keepContent, backHandler) {
		var thizz = $(this);
		var previous_loader = thizz.data('loader');
		if (previous_loader) previous_loader.release();
		var screen_stack = thizz.data('screen_stack');		
		var leftButtonControl = $("div.mc_toolbar button.mc_left_button", thizz);
		var rightButtonControl = $("div.mc_toolbar button.mc_right_button", thizz);
		var backButtonControl = $("div.mc_toolbar button.mc_back_button", thizz);		
		var screen_container = $("div.mc_screen_container", thizz);
		var screen_loading = $("div.mc_screen_loading", thizz);
		var screen_content = $("div.mc_screen_container div.mc_screen_container_content", thizz);

		var leftButton = null;
		leftButtonControl.attr('disabled', true);
		if (leftButtonControl.is(":visible")) {
			leftButton = {
				text: leftButtonControl.text(),
				click: leftButtonControl.data('click')
			};
		}

		var rightButton = null;
		rightButtonControl.attr('disabled', true);
		if (rightButtonControl.is(":visible")) {
			rightButton = {
				text: rightButtonControl.text(),
				click: rightButtonControl.data('click')
			};
		}

		backButtonControl.attr('disabled', true);

		$("div.mc_screen_nothing_to_display", thizz).hide();
		if (! mode) mode = "load";
		if (mode == "load") {
			screen_container.addClass("mcoutofscreen");
			screen_loading.show();
			var position = 0;
			var pb = $("div.mc_screen_loading_pb", thizz);
			pb.progressbar("value", position);
			var content = $("div.mc_screen_container div.mc_screen_container_content > div:not(.hidden)", thizz);
			if (content.length) {
				screen_stack.push({
					scrollTop: screen_container.scrollTop(),
					html: content.addClass("hidden"),
					leftButton: leftButton,
					rightButton : rightButton
				});
			}
			var done = false;
			var tasks = 0;
			var whenDone = [];
			var doneHandler = function () {
				if (done) return;
				done = true;
				$.each(whenDone, function (i,f) { f(); });
				screen_loading.hide();
				screen_container.removeClass('mcoutofscreen');
				configureButtons(thizz, newLeftButton, newRightButton, backHandler);
			};
			var loader = {
				container: screen_content,
				progress: function (progress) {
					if (done) return;
					position += progress;
					pb.progressbar("value", position);
				},
				addTaskCount: function (count) {
					if (done) return;
					if (! count)
						count = 1;
					tasks += count;
					console.log("Task load count: "+tasks);
				},
				taskDone: function () {
					if (done) return;
					tasks --;
					console.log("Task load count: "+tasks);
					if (tasks == 0)
						doneHandler();
				},
				done: doneHandler,
				onDone: function (handler) { whenDone.push(handler); },
				taskCount: function () { return tasks; },
				release: function () { done = true; }
			};
			thizz.data('loader', loader);
			return loader;
		} else if (mode == "wait") {
			var mc_screen_waiting = $("div.mc_screen_waiting", thizz);
			mc_screen_waiting.fadeIn('slow');
			var position = 0;
			var pb = $("div.mc_screen_waiting_pb", thizz);
			pb.progressbar("value", position);
			var status = "waiting";
			var done = false;
			var simulate = function () {
				if (done) return;
				if (status == "waiting") {
					position ++;
					pb.progressbar("value", position);
					setTimeout(simulate, 100);
				}
			};
			setTimeout(simulate, 100);
			var content = $("div.mc_screen_container div.mc_screen_container_content > :not(.hidden)", thizz);
			var whenDone = [];			
			var tasks = 0;
			var doneHandler = function () {
				if (done) return;
				done = true;
				if (! keepContent) {
					console.log("Animating .... " + content.length + " objects.");
					content.animate({'margin-top': -504}, {
						duration: 500,
						complete: function () {
							content.remove();
							mc_screen_waiting.fadeOut('fast');
							configureButtons(thizz, newLeftButton, newRightButton, backHandler);
							$.each(whenDone, function (i,f) { f(); });
						}
					});
				} else {
					mc_screen_waiting.fadeOut('fast');
					configureButtons(thizz, newLeftButton, newRightButton, backHandler);
					$.each(whenDone, function (i,f) { f(); });
				}
			};
			var loader = {
				container: screen_content,
				status: function (new_status) {
					if (done) return;
					status = new_status;
					if (new_status == "rendering") {
						position = 50;
						pb.progressbar("value", position);
					}
				},
				progress: function (progress) {
					if (done) return;
					position += progress;
					pb.progressbar("value", position);
				},
				addTaskCount: function (count) {
					if (done) return;
					if (! count)
						count = 1;
					tasks += count;
					console.log("Task wait count: "+tasks);
				},
				taskDone: function () {
					if (done) return;
					tasks --;
					console.log("Task wait count: "+tasks);
					if (tasks == 0)
						doneHandler();
				},
				done: doneHandler,
				onDone: function (handler) { whenDone.push(handler); },
				taskCount: function () { return tasks; },
				release: function () { done = true; }
			};
			thizz.data('loader', loader);
			return loader;
		}
	};
	
	var clear = function () {
		var thizz = $(this);
		var screen_stack = thizz.data('screen_stack');		
		screen_stack.splice(0, screen_stack.length);
		$("div.mc_screen_loading, div.mc_screen_waiting", thizz).hide();
		$("div.mc_screen_container", thizz).addClass("mcoutofscreen");
		$("div.mc_screen_nothing_to_display", thizz).show();
		$("div.mc_screen_container div.mc_screen_container_content", thizz).empty();
		$("div.mc_toolbar button.mc_back_button", thizz).hide();
		$("div.mc_toolbar button.mc_left_button", thizz).hide();
		$("div.mc_toolbar button.mc_right_button", thizz).hide();
	};

	var methods = {
		init: init,
		load: load,
		clear: clear, 
		back: back
	};

	$.fn.mcscreen = function (method) {
		// Method calling logic
		if ( methods[method] ) {
			return methods[ method ].apply( this, Array.prototype.slice.call( arguments, 1 ));
		} else if ( typeof method === 'object' || ! method ) {
			return methods.init.apply( this, arguments );
		} else {
			$.error( 'Method ' +  method + ' does not exist on jQuery.mcscreen' );
		}    
	};

})( jQuery );