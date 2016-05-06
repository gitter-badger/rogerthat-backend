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

var console = console || {};
console.log = console.log || function(){};
console.warn = console.warn || function(){};
console.error = console.error || function(){};
console.info = console.info || function(){};
console.trace = console.trace || function(){};

if ("1.6.1" != jQuery.fn.jquery) {
    throw Error("This monkey-patched code should be updated when using a jquery version other than 1.6.1");
}

jQuery.each(["bind", "one"], function( i, name ) {
	jQuery.fn[ name ] = function( type, data, fn ) {
		var handler;

		// Handle object literals
		if ( typeof type === "object" ) {
			for ( var key in type ) {
				this[ name ](key, data, type[key], fn);
			}
			return this;
		}

		if ( arguments.length === 2 || data === false ) {
			fn = data;
			data = undefined;
		}
		
		if (fn && ! fn.guid) fn.guid = jQuery.guid++;

		if ( name === "one" ) {
			handler = function( event ) {
				jQuery( this ).unbind( event, handler );
				try {
					return fn.apply( this, arguments );
				} catch (err) {
					mctracker.logError("Caught exception in '" + type + "' handler of " + this, err);
					throw err;
				}
			};
			handler.guid = fn.guid;
		} else {
			if (fn) {
				var origHandler = fn.handler ? fn.handler : fn;
				var newHandler = function() {
					try {
						return origHandler.apply( this, arguments );
					} catch (err) {
						mctracker.logError("Caught exception in '" + type + "' handler of " + this, err);
						throw err;
					}
				};
				if (fn.handler) {
					fn.handler = newHandler;
					handler = fn;
				} else {
					handler = newHandler;
					handler.guid = fn.guid;
				}
			} else 
				handler = fn;
		}

		if ( type === "unload" && name !== "one" ) {
			this.one( type, data, fn );

		} else {
			for ( var i = 0, l = this.length; i < l; i++ ) {
				jQuery.event.add( this[i], type, handler, data );
			}
		}

		return this;
	};
});


var create_lib = function () {
    var isIE10 = $.browser.msie && 10 == parseInt($.browser.version, 10);

    return {
        htmlize: function (value) {
            return $("<div></div>").text(value).html().replace(/\n/g, "<br>");
        },
        fixTextareaPlaceholderForIE: function (textarea) {
            // XXX: we could do some focus/blur magic for ie6-9
            if (isIE10 && textarea.attr('placeholder') == textarea.val()) {
                textarea.val('');
            }
        },
		day: 24*3600,
		months: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
		timezoneOffset: 60*new Date().getTimezoneOffset(),
		handleTimezone: function (timestamp) {
			return timestamp - mctracker.timezoneOffset;
		},
		nowUTC: function () {
			return Math.floor(new Date().getTime() / 1000);
		},
		now: function() {
			return mctracker.handleTimezone(mctracker.nowUTC());
		},
		formatDate: function (timestamp, time, includeSeconds) {
		    if (includeSeconds == undefined)
		        includeSeconds = true;
			var now = mctracker.nowUTC();
			if (mctracker.isSameDay(now, timestamp)) {
				return mctracker.intToTime(mctracker.handleTimezone(timestamp)%mctracker.day, time && includeSeconds);
			}
			var date = new Date(mctracker.handleTimezone(timestamp)*1000);
			if (mctracker.isSameYear(now, timestamp)) {
				return mctracker.months[date.getMonth()] + ' ' + date.getDate() + 
					(time ? " "+mctracker.intToTime(mctracker.handleTimezone(timestamp)%mctracker.day, includeSeconds):"");
			}
			return mctracker.months[date.getMonth()] + ' ' + date.getDate() + " " + date.getFullYear() + 
				(time ? " "+mctracker.intToTime(mctracker.handleTimezone(timestamp)%mctracker.day, includeSeconds):"");
		},
		isSameDay: function (timestamp1, timestamp2) {
			return Math.floor(timestamp1/mctracker.day) === Math.floor(timestamp2/mctracker.day);
		},
		isSameYear: function (timestamp1, timestamp2) {
			return new Date(timestamp1*1000).getFullYear() === new Date(timestamp2*1000).getFullYear();
		},
		intToTime: function (timestamp, includeSeconds) {
			var stub = function (number) {
				var string = ''+number;
				if (string.length == 1)
					return '0'+string;
				return string;
			};
			var hours = Math.floor(timestamp / 3600);
			var minutes = Math.floor((timestamp % 3600) / 60);
			if (includeSeconds) {
				var seconds = Math.floor((timestamp % 3600) % 60);
				return stub(hours) + ':' + stub(minutes) + ':' + stub(seconds);
			} else {
				return stub(hours) + ':' + stub(minutes);
			}
		},
		intToHumanTime: function (timestamp) {
			var hours = Math.floor(timestamp / 3600);
			var minutes = Math.floor((timestamp % 3600) / 60);
			var seconds = Math.floor((timestamp % 3600) % 60);
			if (hours > 0) {
				return hours + 'h ' + minutes + 'm ' + seconds + 's';
			} else if (minutes > 0) {
				return minutes + 'm ' + seconds + 's';
			} else {
				return seconds + 's';
			}
		},
		getLocaljQuery: function (container) {
			return function(query, type) {
				if ( type == undefined) {
					var qps = query.split(',');
					for (var i in qps) {
						qps[i] = container + ' ' + qps[i];
					}
					return $(qps.join(','));
				} else {
					if ( type == 'd' ) {
						var qps = query.split(',');
						for (var i in qps) {
							qps[i] = qps[i]+'[dialog="'+container+'"]';
						}
						return $(qps.join(','));
					} else if ( type == "dc" ) {
						var qps = query.split(',');
						for (var i in qps) {
							qps[i] = 'div[dialog="'+container+'"] '+qps[i];
						}
						return $(qps.join(','));
					}
				}
			};
		},
		_is_loading: true,
		mainHasLoaded: function () {
			mctracker._is_loading = false;
		},
		isLoading: function () {
			return mctracker._is_loading;
		},
		_loadedContainers: [],
		_contentContainer: null,
		_currentContainer: null,
		_loadContainer: $('<div style="display: none"></div>'),
		_loading: $('<div class="loading">loading</div>'),
		_loadCallbacks: [],
		_containerInterfaces: [],
		initContainers: function (current, content) {
			mctracker._currentContainer = current;
			mctracker._contentContainer = content;
			mctracker._contentContainer.append(mctracker._loading);
		},
		registerLoadCallback: function (container, funct) {
			mctracker._loadCallbacks[container] = funct;
		},
		_loadContainerFromServer: function (container, url, callback) {
			mctracker._is_loading = true;
			mctracker.call({
				"hideProcessing":true,
				'url': url,
				success: function (data, textStatus, XMLHttpRequest) {
					mctracker._loadContainer.html(data);
					var html = mctracker._loadContainer.children().detach();
					mctracker._contentContainer.append(html);
					mctracker._loadedContainers[container] = html;
					mctracker._containerInterfaces[container] = mctracker._loadCallbacks[container]();
					callback(html);
					mctracker._is_loading = false;
				},
				error: function(XMLHttpRequest, textStatus, errorThrown) {
					mctracker.showAjaxError(XMLHttpRequest, textStatus, errorThrown);
					mctracker._is_loading = false;
				}
			});
		},
		showAjaxError: function (XMLHttpRequest, textStatus, errorThrown) {
			mctracker.alert("Could not load from server. Please refresh your browser to continue");
		},
		logError: function (description, err) {
		    var stack_trace = (err && err instanceof Error) ? err + '\n' + printStackTrace({guess: true, e: err}).join('\n') : err;
		    console.log(description + (stack_trace ? ('\n' + stack_trace) : ''));
		    mctracker.call({
		        hideProcessing: true,
	            url: "/mobi/rest/system/log_error",
	            type: "post",
	            data: {
	                data: JSON.stringify({
	                    description: description,
	                    errorMessage: stack_trace,
	                    timestamp: mctracker.nowUTC(),
	                    user_agent: navigator.userAgent
	                })
	            },
	            success: function (data, textStatus, XMLHttpRequest) {},
                error: function (XMLHttpRequest, textStatus, errorThrown) {}
		    });
		},
		loadContainer: function (container, url, callback) {
			if ( mctracker.isLoading() ) {
				return false;
			}
			var get_display_function = function (loadingContainer) {
				return function (html) {
					stopLoading();
					loadingContainer.hide();
					mctracker._currentContainer = html;
					for (var i in mctracker._setOnLoadContainerCallbacks) {
						mctracker._setOnLoadContainerCallbacks[i](container);
					}
					if (callback)
						callback();
					$("#body").scrollTop(0);
				}
			}
			if (mctracker._currentContainer.attr('id') == container) {
				// container is already loaded
				return true;
			}
            window.location.hash = container;
            hash = window.location.hash;
			var newContainer = mctracker._loadedContainers[container];
			$(mctracker._currentContainer).addClass('mcoutofscreen');
			mctracker._loadedContainers[mctracker._currentContainer.attr('id')] = mctracker._currentContainer;
			if (newContainer) {
				mctracker._currentContainer = newContainer;
				newContainer.removeClass('mcoutofscreen');
				for (var i in mctracker._setOnLoadContainerCallbacks) {
					mctracker._setOnLoadContainerCallbacks[i](container);
				}
				$("#body").scrollTop(0);
			} else {
				var loadingContainer = mctracker._loading;
				loadingContainer.show();
				startLoading(loadingContainer);
				mctracker._loadContainerFromServer(container, url, get_display_function(loadingContainer));
			};
			return true;
		},
		isCurrentContainer: function (containerId) {
		    return mctracker._currentContainer.attr('id') == containerId;
		},
		removeContainer: function (containerId) {
			mctracker._loadedContainers[containerId].detach();
		    delete mctracker._loadedContainers[containerId];
		},
		_setOnLoadContainerCallbacks: [],
		setOnLoadContainer: function (callback) {
			mctracker._setOnLoadContainerCallbacks.push(callback);
		},
		getContainer: function (container, url, callback) {
			if ( mctracker._loadedContainers[container] ) {
				callback(mctracker._containerInterfaces[container]);
			} else {
				if ( mctracker.isLoading() || ! url) {
					return false;
				}
				mctracker._loadContainerFromServer(container, url, function (html) {
					callback(mctracker._containerInterfaces[container]);
				});
			}
			return true;
		},
		loopContainers: function (callback) {
		    for (var container in mctracker._loadedContainers) {
		       callback(container, mctracker._loadedContainers[container], mctracker._containerInterfaces[container]);
		    }
		},
		_processingDialog: null,
		showProcessing: function(modal, onClose, title) {
		    mctracker._processingDialog.dialog('option', 'modal', Boolean(modal));
		    mctracker._processingDialog.dialog('option', 'close', onClose);
		    mctracker._processingDialog.dialog('option', 'title', title || null);
			mctracker._processingDialog.dialog('open');
		},
		hideProcessing: function(status) {
			if (status) {
				var title = mctracker._processingDialog.dialog('option','title');
				mctracker._processingDialog.dialog('option','title', status);
				window.setTimeout(function() {
					mctracker._processingDialog.dialog('close');
					mctracker._processingDialog.dialog('option', 'title', title);
				}, 1000);
			} else 
				mctracker._processingDialog.dialog('close');
		},
		call: function(options) {
			var method = options.type;
			if (! method) method = "GET";
			method.toUpperCase();
			if (! options.hideProcessing)
				mctracker.showProcessing();
			var success = options.success;
			var error = options.error;
			options.success = function (data, textStatus, XMLHttpRequest) {
	            if (! options.hideProcessing)
	                mctracker.hideProcessing();
				try {
					if (success)
						success(data, textStatus, XMLHttpRequest);
				} catch (err) {
				    mctracker.logError('Caught exception in success handler of ' + options.url, err);
				}
			},
			options.error = function(XMLHttpRequest, textStatus, errorThrown) {
	            if (! options.hideProcessing)
	                mctracker.hideProcessing();
				if (error) {
				    try {
				        error(XMLHttpRequest, textStatus, errorThrown);
	                } catch (err) {
	                    mctracker.logError('Caught exception in error handler of ' + options.url, err);
	                }
				} else {
					mctracker.showAjaxError(XMLHttpRequest, textStatus, errorThrown);
				}
			}
			$.ajax(options);
		},
		_message_callbacks: [],
		registerMsgCallback: function(f) {
			mctracker._message_callbacks.push(f);
		},
		broadcast: function (data) {
			$.each(mctracker._message_callbacks, function (i, callback) {
				try {
					callback(data);
				} catch (err) {
                    mctracker.logError('Caught exception in mctracker.broadcast', err);
					mctracker.showAjaxError(null, null, err);
				}
			});
		},
		_on_message: function (msg) {
            console.log("--------- channel ---------\n"+msg.data);
            var process = function (raw_data) {
                var data = JSON.parse(raw_data);
                if ($.isArray(data)) {
                    $.each(data, function(i, d) {
                        mctracker.broadcast(d);
                    });
                } else {
                    mctracker.broadcast(data);
                }
            };
            if (msg.data.indexOf("large_object=") == 0) {
                var getLargeObjUrl = typeof (LARGE_CHANNEL_OBJECT_URL) != "undefined" ? LARGE_CHANNEL_OBJECT_URL : null;
            	$.ajax({
            		url: getLargeObjUrl || '/mobi/rest/channel',
            		data: { key: msg.data.substring(13) },
            		success: function (data) {
            			process(data);
            		},
            		error: function () {}
            	});
            } else {
            	process(msg.data);
            }
		},
		runChannel: function(token) {
			var _ = function(){};
			var channel = new goog.appengine.Channel(token);
			var _run = null;
			var onClose = function () {
				$("<div>Your live update connection has been terminated.<br>You need to reload your browser to continue.</div>")
					.dialog({
						autoOpen: true,
						modal: true,
						dragable: false,
						resizable: false,
						title: 'Need refresh',
						width: 430,
						buttons: {
							Reload: function () {
								$(this).dialog('close');
							}
						},
						close: function () {
							window.location = "/";
						}
					});
			};
			_run = function () {
				var socket = channel.open({
					'onopen': _,
					'onmessage': mctracker._on_message,
					'onerror': _,
					'onclose': onClose
				});
				socket.onopen = _;
				socket.onmessage = mctracker._on_message;
				socket.onerror = onClose;
				socket.onclose = onClose;

				mctracker.registerMsgCallback(function (data) {
					if (data.type == 'rogerthat.system.logout') {
						window.location.reload();
					}
					else if (data.type == 'rogerthat.system.dologout') {
						mctracker._is_loading = true;
						mctracker.call({
							"hideProcessing":true,
							'url': "/logout",
							success: function (data, textStatus, XMLHttpRequest) {
								mctracker._is_loading = false;
								window.location.reload();
							},
							error: function(XMLHttpRequest, textStatus, errorThrown) {
								mctracker._is_loading = false;
								window.location.reload();
							}
						});
					}
				});
			};
			_run();
		},
		uuid: function () {
			var S4 = function () {
			   return (((1+Math.random())*0x10000)|0).toString(16).substring(1);
			};
			return (S4()+S4()+"-"+S4()+"-"+S4()+"-"+S4()+"-"+S4()+S4()+S4());
		},
		filter: function (array, callback) {
			var result = [];
			for ( var index in array ) {
				if (callback(array[index], index)) {
					result.push(array[index]);
				}
	 		}
			return result;
		},
		any: function (array, callback) {
			for ( var index in array ) {
				if (callback(array[index], index)) {
					return true;
				}
	 		}
			return false;
		},
		map: function (array, callback) {
		    var result = [];
            for ( var index in array ) {
		        result.push(callback(array[index]));
		    }
		    return result;
		},
		get: function (array, callback) {
			for ( var index in array ) {
				if (callback(array[index], index)) {
					return array[index];
				}
	 		}
			return null;
		},
		reverse: function (array) {
			var result = [];
			var index = array.length - 1;
			while (index >= 0) {
				result.push(array[index]);
				index --;
			}
			return result;
		},
		toArray: function (object) {
			var result = [];
			for (var key in object) {
				result.push(object[key]);
			}
			return result
		},
		index: function (array, item) {
			for (var i in array) {
				if (array[i] === item)
					return Number(i);
			}
			return -1;
		},
		_encodeDiv: $('<div></div>'),
		htmlEncode: function (text) {
			mctracker._encodeDiv.empty();
			return mctracker._encodeDiv.html(text).text();
		},
		_mapsLoaded: false,
		loadGoogleMaps: function () {
			if (mctracker._mapsLoaded) {
				mapsLoaded();
				return;
			}
			var script = document.createElement("script");
			script.src = "https://www.google.com/jsapi?key=ABQIAAAAshIlGwX7DfSsZzoFiB2_kRTUZfFbKFGe739BTWJXaP6Uv4H-BhSPggJ-ZElM3aVNmYSyua9orlmH-Q&callback=loadMaps";
			script.type = "text/javascript";
			document.getElementsByTagName("head")[0].appendChild(script);
		},
		mapsLoadedCallbacks: [],
		confirm: function (message, onConfirm, onCancel, positiveCaption, negativeCaption, title, html, width) {
			var dialog = null;
			var buttons = {};
			buttons[positiveCaption || 'Yes'] = function () {
				dialog.dialog('close');
				if (onConfirm)
					onConfirm();
			};
			buttons[negativeCaption || 'No'] = function () {
				dialog.dialog('close');
				if (onCancel)
					onCancel();
			};
			dialog = $('<div></div>');
			if (html) dialog.html(message); else dialog.text(message);
			var options = {
				modal: true,
				title: title || "Confirm",
				zindex: 1002,
				buttons: buttons
			}
			if (width)
				options.width = width;
			dialog.dialog(options);
		},
		input: function (message, onOk, autoCompleteFunction, block) {
			var dlg = $('<div></div>').text(message);
			var onOkFunction = function () {
                if (onOk(control.val(), dlg))
                    dlg.dialog('close');
            }; 
            var control = null;
            if (block) {
                control = $('<textarea></textarea').css('width', '250px').css('height', '150px');
            } else {
                control = $('<input/>').attr('type', 'text').css('width', '200px').keypress(function (event) {
                    if (event.which == 13) {
                        event.preventDefault();
                        onOkFunction();
                    }
                });
            }
			 
			if (autoCompleteFunction)
				control.autocomplete({source: autoCompleteFunction, minLength: 2});
			dlg.append($('<br>')).append(control);
			dlg.dialog({
				modal: true,
				title: "Input",
				zindex: 1001,
				buttons: {
					Ok: onOkFunction,
					Cancel: function () {
						dlg.dialog('close');
					}
				}
			}).dialog('open');
		},
		alert: function (message, onClose, title, timeout, html) {
			if (! title)
				title = "Alert";
			var dialog = $('<div></div>');
			if (html)
				dialog.html(message);
			else
				dialog.text(message);
			dialog.dialog({
				modal: true,
				title: title,
				zindex: 1002,
				buttons: {
					Ok: function () {
						dialog.dialog('close');
						if (onClose)
							onClose();
					}
				}
			});
			if (timeout) 
				window.setTimeout(function() {dialog.dialog('close');}, timeout);
			return dialog;
		},
		indexOf: function (array, item, start) {
			if (!Array.prototype.indexOf) {
				for (var i = (start || 0), j = array.length; i < j; i++) {
					if (array[i] === item) return i;
				}
				return -1;
			} else {
				return array.indexOf(item, start);
			}
		},
        sort: function (array, key) {
            return array.sort(function (a,b) {
                var cmpA = (key ? key(a) : a);
                var cmpB = (key ? key(b) : b);
                
                if (mctracker.isNumber(cmpA) && mctracker.isNumber(cmpB)) {
                    if (cmpA == cmpB) {
                        return 0;
                    } else {
                        return cmpA < cmpB ? -1 : 1;
                    }
                }
                
                return cmpA.toLowerCase().localeCompare(cmpB.toLowerCase());
            });
        },
        isNumber: function (n) {
            return !isNaN(parseFloat(n)) && isFinite(n);
        },
        isPositiveInteger: function (n) {
            return 0 === n % (!isNaN(parseFloat(n)) && 0 <= ~~n);
        },
        size: function (obj) {
            var size = 0;
            for (var key in obj) {
                if (obj.hasOwnProperty(key)) size++;
            }
            return size;
        },
        uploadImage : function(popupHeader, postImageUrl, updateUrl, previewDiv, previewWidth, previewHeight,
                imageGetUrl, tmpImageGetUrl, channelApiDataType, onSaveHandler, onCancelHandler) {

            var TMPL_UPDATE_AVATAR = '<div id="createAvatarDialog" style="display: none;">'
                + '<span id="errormessage" class="mcerror"></span><br>'
                + '1: Upload image:'
                + '<iframe id="profileAvatarHiddenUploadFrame" name="profileAvatarHiddenUploadFrame" style="width: 0px; height: 0px; border: 0px; color: #fff; padding: 0px"></iframe>'
                + '<form id="uploadForm" target="profileAvatarHiddenUploadFrame" enctype="multipart/form-data" method="post" action="'+postImageUrl+'">'
                +   '<input id="newAvatar" name="newAvatar" type="file" />'
                + '</form><br>'
                + '2: Select area to use for your picture:<br>'
                +  '<img id="avatarUpload" style="width: 200px; border:1px; border-color: #000; border-style: solid;" src="/static/images/unknown_avatar.png"/>'
                +   '<img id="avatarSelectionArea" style="display: block; max-width: 500px; max-height: 250px; border:1px; border-color: #000; border-style: solid;"/>'
                + '</div>';
            
            var PREVIEW_HEIGHT = 250;
            var PREVIEW_WIDTH = 500;

            if (previewHeight > PREVIEW_HEIGHT || previewWidth > previewWidth) {
                throw new Exception("Invalid preview height or width");
            }

            var avatar_selection = null;
            var avatar_tmp_key = null;
            var avatar_scale_factor_x = null;
            var avatar_scale_factor_y = null;
            var cleaning_up = false;
            var avatar_dialog = null;
            var html = $.tmpl(TMPL_UPDATE_AVATAR, {
                header : popupHeader,
                postImageUrl : postImageUrl
            });

            var preview = function (img, selection) {
                if (cleaning_up)
                    return;

                var scale = previewWidth / (selection.width || 1);
                var css = {
                    width : Math.round(scale * img.width) + 'px',
                    height : Math.round(scale * img.height) + 'px',
                    marginLeft : '-' + Math.round(scale * selection.x1) + 'px',
                    marginTop : '-' + Math.round(scale * selection.y1) + 'px'
                };
                // console.log(css);
                $('img', previewDiv).css(css);
            };

            var select = function(img, selection) {
                if (cleaning_up)
                    return;
                avatar_selection = selection;
                avatar_scale_factor_x = img.width;
                avatar_scale_factor_y = img.height;
            };

            var acceptAvatar = function() {
                if (avatar_selection == null) {
                    mctracker.alert("No image selection made!");
                } else {
                    mctracker.alert("Save ...");
                }
            };

            var uploadAvatar = function() {
                if (!$("#newAvatar", html).val())
                    return;
                mctracker.showProcessing("Uploading image ...");
                $("#uploadForm", html).submit();
            };

            $("#newAvatar", html).val("");
            $("#avatarUpload", html).show();
            $("#avatarSelectionArea", html).imgAreaSelect({
                aspectRatio : previewWidth + ':' + previewHeight,
                onSelectChange : preview,
                onSelectEnd : select,
                handles : true,
                zIndex : 1100,
                minWidth: 50,
                minHeight: 50,
                persistent: true
            }).hide();
            $("#newAvatar", html).change(uploadAvatar);

            mctracker.registerMsgCallback(function(data) {
                if (data.type == channelApiDataType) {
                    if (!html.closest(document.documentElement))
                        return; // This function should not work anymore as its
                                // html is not in the dom anymore
                    avatar_tmp_key = data.key;
                    $("#avatarUpload", html).hide();
                    // random key to prevent caching when user selects a new image
                    var url = tmpImageGetUrl + "?key=" + encodeURIComponent(data.key) + "&r=" + mctracker.uuid();
                    var addInitialSelection = function() {
                        var img = $(this);
                        img.show();
                        img.css('min-width', 'none').css('min-height', 'none');
                        var height = img.height();
                        var width = img.width();
                        var scale_height = PREVIEW_HEIGHT / height;
                        var scale_width = PREVIEW_WIDTH / width;
                        if (scale_height > 1 && scale_width > 1) {
                            if (scale_height < scale_width) {
                                img.css('min-height', PREVIEW_HEIGHT + 'px');
                            } else {
                                img.css('min-width', PREVIEW_WIDTH + 'px');
                            }
                            height = img.height();
                            width = img.width();
                        }

                        var previewScaleHeight = previewHeight / height;
                        var previewScaleWidth = previewWidth / width;

                        var selectionHeight;
                        var selectionWidth;
                        if (previewScaleHeight > previewScaleWidth) {
                            selectionHeight = height / 2;
                            selectionWidth = selectionHeight * previewWidth / previewHeight;
                        } else {
                            selectionWidth = width / 2;
                            selectionHeight = selectionWidth * previewHeight / previewWidth;
                        }

                        var x1 = (width - selectionWidth) / 2;
                        var y1 = (height - selectionHeight) / 2;
                        var x2 = x1 + selectionWidth;
                        var y2 = y1 + selectionHeight;

                        var imgAreaSelect = img.imgAreaSelect({
                            instance : true
                        });
                        imgAreaSelect.setOptions({
                            show : true
                        });
                        imgAreaSelect.setSelection(x1, y1, x2, y2, true);
                        imgAreaSelect.update();
                        var selection = {
                            x1 : x1,
                            y1 : y1,
                            x2 : x2,
                            y2 : y2,
                            height : selectionHeight,
                            width : selectionWidth
                        };
                        select(this, selection);
                        preview(this, selection);
                        mctracker.hideProcessing();
                    };
                    $("#avatarSelectionArea", html).attr("src", url).unbind('load').load(addInitialSelection);
                    $('img', previewDiv).attr("src", url);
                }
            });
            
            var cleanUpImgAreaSelect = function() {
                cleaning_up = true;
                $("#avatarSelectionArea", html).imgAreaSelect({
                    remove : true,
                    onSelectChange : null,
                    onSelectEnd : null
                });

                previewDiv.empty().append($('<img style="position: relative" src="' + imageGetUrl + '"/>'));

                cleaning_up = false;
            };
            
            var acceptAvatar = function() {
                if (!(avatar_tmp_key && avatar_selection)) {
                    mctracker.alert("No image selected yet!");
                    return;
                }
                var x1 = Math.min(1, Math.max(0, avatar_selection.x1 / avatar_scale_factor_x));
                var x2 = Math.min(1, Math.max(0, avatar_selection.x2 / avatar_scale_factor_x));
                var y1 = Math.min(1, Math.max(0, avatar_selection.y1 / avatar_scale_factor_y));
                var y2 = Math.min(1, Math.max(0, avatar_selection.y2 / avatar_scale_factor_y));
                
                mctracker.showProcessing("Saving ...");
                
                $.ajax({
                    url : updateUrl,
                    data : {
                        data : JSON.stringify({
                            tmp_avatar_key : avatar_tmp_key,
                            x1 : x1,
                            y1 : y1,
                            x2 : x2,
                            y2 : y2
                        })
                    },
                    type : 'POST',
                    success : function(errorMsg) {
                        mctracker.hideProcessing("Saving ...");
                        if (errorMsg) {
                            mctracker.alert(errorMsg, null, "Error");
                        } else {
                            html.dialog('close');
                            if (onSaveHandler) {
                                onSaveHandler();
                            }
                        }
                    },
                    error : mctracker.showAjaxError
                });
            };

            html.dialog({
                draggable: false,
                autoOpen: false,
                title: popupHeader,
                width: 550,
                height: 420,
                modal: true, 
                buttons: {
                    'Save': acceptAvatar,
                    'Cancel': function() {
                        html.dialog('close');
                        if (onCancelHandler)
                            onCancelHandler();
                    }
                },
                close: cleanUpImgAreaSelect,
                position: { my: "center top", at: "center top", of: window}
            }).dialog('open');
        }
	}
};
var mctracker = create_lib();

function mapsLoaded() {
	$.each(mctracker.mapsLoadedCallbacks, function (i, cb) {
		cb();
	});
	while (mctracker.mapsLoadedCallbacks.length > 0)
		mctracker.mapsLoadedCallbacks.pop();
	mctracker._mapsLoaded = true;
}

function loadMaps() {
	google.load("maps", "3", {other_params: "sensor=false", callback : mapsLoaded});
}

function intToTime(integer) {
	return mctracker.intToTime(integer, true);
};

var animating = false;
var animatingContainer = null;

function startLoading(container) {
	animatingContainer = container;
	animating = true;
	animateLoading();
}

function stopLoading() {
	animating = false;
}

var animateLoading = function () {
	var fadeIn = function () {
		if (animating) {
			animatingContainer.fadeIn(500, fadeOut);			
		}		
	};
	var fadeOut = function () {
		if (animating) {
			animatingContainer.fadeOut(500, fadeIn);			
		}
	};
	fadeOut();
};

function setZoomLevel(coordinates, map) {
	var mapUtil = {
		minLat: null,
		maxLat: null,
		minLng: null,
		maxLng: null,

		calculateBorders: function(latitude, longitude) {
			latitude = Number(latitude);
			longitude = Number(longitude); 
			if(typeof(latitude) == 'number' && typeof(longitude) == 'number') {
				if(mapUtil.minLat == null || mapUtil.minLat > latitude) {
					mapUtil.minLat = latitude;
				}
			
				if(mapUtil.maxLat == null || mapUtil.maxLat < latitude) {
					mapUtil.maxLat = latitude;
				}
				
				if(mapUtil.minLng == null || mapUtil.minLng > longitude) {
					mapUtil.minLng = longitude;
				}
				
				if(mapUtil.maxLng == null || mapUtil.maxLng < longitude) {
					mapUtil.maxLng = longitude;
				}
			}
		},

		zoomToViewAll: function() {
			var visibleBounds = mapUtil.getVisibleBounds();
			if (visibleBounds) {
				map.fitBounds(visibleBounds);
			}
		},

		getVisibleBounds: function() {
			if(mapUtil.maxLng) {
				var swLatLng = new google.maps.LatLng(mapUtil.minLat, mapUtil.minLng);
				var neLatLng = new google.maps.LatLng(mapUtil.maxLat, mapUtil.maxLng);
				var minBounds = new google.maps.LatLngBounds(swLatLng, neLatLng);
				return minBounds;
			} 
			return null; 
		}
	};
	if (coordinates.length > 1) {
		for (var i=0; i < coordinates.length; i++) {
			mapUtil.calculateBorders(coordinates[i].latitude, coordinates[i].longitude);
		}
		mapUtil.zoomToViewAll();
	} else if ( coordinates.length == 1) {
		map.setCenter(new google.maps.LatLng(coordinates[0].latitude, coordinates[0].longitude));
		map.setZoom(11);
	} else {
		map.setCenter(new google.maps.LatLng(40.7142691, -74.0059729));
		map.setZoom(11);
	}
}

function trim(stringToTrim) {
	return stringToTrim.replace(/^\s+|\s+$/g,"");
}
function ltrim(stringToTrim) {
	return stringToTrim.replace(/^\s+/,"");
}
function rtrim(stringToTrim) {
	return stringToTrim.replace(/\s+$/,"");
}

$(window).error(function (e) {
	
});

loadGoogleMaps = function () {
	var script = document.createElement("script");
	script.src = "https://www.google.com/jsapi?key=ABQIAAAAshIlGwX7DfSsZzoFiB2_kRTUZfFbKFGe739BTWJXaP6Uv4H-BhSPggJ-ZElM3aVNmYSyua9orlmH-Q&callback=loadMaps";
	script.type = "text/javascript";
	document.getElementsByTagName("head")[0].appendChild(script);
};

var hash = window.location.hash;
setInterval(function(){
    if (window.location.hash != hash) {
        hash = window.location.hash;
        var containerId = hash.substring(1);
        if (mctracker._loadedContainers[containerId]) {
            mctracker.loadContainer(containerId)
        }
    }
}, 100);


/*
 * CryptoJS v3.0.1 code.google.com/p/crypto-js (c) 2009-2012 by Jeff Mott. All rights reserved.
 * code.google.com/p/crypto-js/wiki/License
 */
var CryptoJS=CryptoJS||function(o,q){var l={},m=l.lib={},n=m.Base=function(){function a(){}return{extend:function(e){a.prototype=this;var c=new a;e&&c.mixIn(e);c.$super=this;return c},create:function(){var a=this.extend();a.init.apply(a,arguments);return a},init:function(){},mixIn:function(a){for(var c in a)a.hasOwnProperty(c)&&(this[c]=a[c]);a.hasOwnProperty("toString")&&(this.toString=a.toString)},clone:function(){return this.$super.extend(this)}}}(),j=m.WordArray=n.extend({init:function(a,e){a=
this.words=a||[];this.sigBytes=e!=q?e:4*a.length},toString:function(a){return(a||r).stringify(this)},concat:function(a){var e=this.words,c=a.words,d=this.sigBytes,a=a.sigBytes;this.clamp();if(d%4)for(var b=0;b<a;b++)e[d+b>>>2]|=(c[b>>>2]>>>24-8*(b%4)&255)<<24-8*((d+b)%4);else if(65535<c.length)for(b=0;b<a;b+=4)e[d+b>>>2]=c[b>>>2];else e.push.apply(e,c);this.sigBytes+=a;return this},clamp:function(){var a=this.words,e=this.sigBytes;a[e>>>2]&=4294967295<<32-8*(e%4);a.length=o.ceil(e/4)},clone:function(){var a=
n.clone.call(this);a.words=this.words.slice(0);return a},random:function(a){for(var e=[],c=0;c<a;c+=4)e.push(4294967296*o.random()|0);return j.create(e,a)}}),k=l.enc={},r=k.Hex={stringify:function(a){for(var e=a.words,a=a.sigBytes,c=[],d=0;d<a;d++){var b=e[d>>>2]>>>24-8*(d%4)&255;c.push((b>>>4).toString(16));c.push((b&15).toString(16))}return c.join("")},parse:function(a){for(var b=a.length,c=[],d=0;d<b;d+=2)c[d>>>3]|=parseInt(a.substr(d,2),16)<<24-4*(d%8);return j.create(c,b/2)}},p=k.Latin1={stringify:function(a){for(var b=
a.words,a=a.sigBytes,c=[],d=0;d<a;d++)c.push(String.fromCharCode(b[d>>>2]>>>24-8*(d%4)&255));return c.join("")},parse:function(a){for(var b=a.length,c=[],d=0;d<b;d++)c[d>>>2]|=(a.charCodeAt(d)&255)<<24-8*(d%4);return j.create(c,b)}},h=k.Utf8={stringify:function(a){try{return decodeURIComponent(escape(p.stringify(a)))}catch(b){throw Error("Malformed UTF-8 data");}},parse:function(a){return p.parse(unescape(encodeURIComponent(a)))}},b=m.BufferedBlockAlgorithm=n.extend({reset:function(){this._data=j.create();
this._nDataBytes=0},_append:function(a){"string"==typeof a&&(a=h.parse(a));this._data.concat(a);this._nDataBytes+=a.sigBytes},_process:function(a){var b=this._data,c=b.words,d=b.sigBytes,f=this.blockSize,i=d/(4*f),i=a?o.ceil(i):o.max((i|0)-this._minBufferSize,0),a=i*f,d=o.min(4*a,d);if(a){for(var h=0;h<a;h+=f)this._doProcessBlock(c,h);h=c.splice(0,a);b.sigBytes-=d}return j.create(h,d)},clone:function(){var a=n.clone.call(this);a._data=this._data.clone();return a},_minBufferSize:0});m.Hasher=b.extend({init:function(){this.reset()},
reset:function(){b.reset.call(this);this._doReset()},update:function(a){this._append(a);this._process();return this},finalize:function(a){a&&this._append(a);this._doFinalize();return this._hash},clone:function(){var a=b.clone.call(this);a._hash=this._hash.clone();return a},blockSize:16,_createHelper:function(a){return function(b,c){return a.create(c).finalize(b)}},_createHmacHelper:function(a){return function(b,c){return f.HMAC.create(a,c).finalize(b)}}});var f=l.algo={};return l}(Math);
(function(o){function q(b,f,a,e,c,d,g){b=b+(f&a|~f&e)+c+g;return(b<<d|b>>>32-d)+f}function l(b,f,a,e,c,d,g){b=b+(f&e|a&~e)+c+g;return(b<<d|b>>>32-d)+f}function m(b,f,a,e,c,d,g){b=b+(f^a^e)+c+g;return(b<<d|b>>>32-d)+f}function n(b,f,a,e,c,d,g){b=b+(a^(f|~e))+c+g;return(b<<d|b>>>32-d)+f}var j=CryptoJS,k=j.lib,r=k.WordArray,k=k.Hasher,p=j.algo,h=[];(function(){for(var b=0;64>b;b++)h[b]=4294967296*o.abs(o.sin(b+1))|0})();p=p.MD5=k.extend({_doReset:function(){this._hash=r.create([1732584193,4023233417,
2562383102,271733878])},_doProcessBlock:function(b,f){for(var a=0;16>a;a++){var e=f+a,c=b[e];b[e]=(c<<8|c>>>24)&16711935|(c<<24|c>>>8)&4278255360}for(var e=this._hash.words,c=e[0],d=e[1],g=e[2],i=e[3],a=0;64>a;a+=4)16>a?(c=q(c,d,g,i,b[f+a],7,h[a]),i=q(i,c,d,g,b[f+a+1],12,h[a+1]),g=q(g,i,c,d,b[f+a+2],17,h[a+2]),d=q(d,g,i,c,b[f+a+3],22,h[a+3])):32>a?(c=l(c,d,g,i,b[f+(a+1)%16],5,h[a]),i=l(i,c,d,g,b[f+(a+6)%16],9,h[a+1]),g=l(g,i,c,d,b[f+(a+11)%16],14,h[a+2]),d=l(d,g,i,c,b[f+a%16],20,h[a+3])):48>a?(c=
m(c,d,g,i,b[f+(3*a+5)%16],4,h[a]),i=m(i,c,d,g,b[f+(3*a+8)%16],11,h[a+1]),g=m(g,i,c,d,b[f+(3*a+11)%16],16,h[a+2]),d=m(d,g,i,c,b[f+(3*a+14)%16],23,h[a+3])):(c=n(c,d,g,i,b[f+3*a%16],6,h[a]),i=n(i,c,d,g,b[f+(3*a+7)%16],10,h[a+1]),g=n(g,i,c,d,b[f+(3*a+14)%16],15,h[a+2]),d=n(d,g,i,c,b[f+(3*a+5)%16],21,h[a+3]));e[0]=e[0]+c|0;e[1]=e[1]+d|0;e[2]=e[2]+g|0;e[3]=e[3]+i|0},_doFinalize:function(){var b=this._data,f=b.words,a=8*this._nDataBytes,e=8*b.sigBytes;f[e>>>5]|=128<<24-e%32;f[(e+64>>>9<<4)+14]=(a<<8|a>>>
24)&16711935|(a<<24|a>>>8)&4278255360;b.sigBytes=4*(f.length+1);this._process();b=this._hash.words;for(f=0;4>f;f++)a=b[f],b[f]=(a<<8|a>>>24)&16711935|(a<<24|a>>>8)&4278255360}});j.MD5=k._createHelper(p);j.HmacMD5=k._createHmacHelper(p)})(Math);