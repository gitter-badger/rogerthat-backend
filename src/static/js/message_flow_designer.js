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

var messageFlowDesignScript = function () {
	var container = "#messageFlowDesignContainer";
	var lj = mctracker.getLocaljQuery(container);

	var template = '<tr>'
	    + '  <td>${timestamp_date}</td>'
	    + '  <td style="word-break: break-all; float: left; width: 200px; word-wrap: break-word;">${id}</td>'
	    + '  <td>${name}</td>'
	    + '  <td>'
	    + '    <div style="color: ${status_color}"}>'
	    + '      ${status_description}'
	    + '    </div>'
	    + '    {{if error}}<ul style="color: orange;}";>{{each error}}<li>${$value}</li>{{/each}}</ul>{{/if}}'
	    + '  </td>'
	    + '</tr>';

	var applyJQueryInUI = function (data) {
		lj("#reload").click(load);
		lj("#open_designer").click(function () {
			if ( $.browser.msie ) {
				mctracker.alert("Message flow designer is not supported in your browser. Please use Chrome, Firefox or Safari.");
				return;
			}

			$("body").css("overflow", "hidden");
			$('iframe', $('<div><iframe id="message_flow_designer_frame" src="/static/mfd/index.html" style="height: 100%; width: 100%; display: none;"></iframe></div>').dialog({
				title: 'Message flow designer',
				width: window.innerWidth - 50,
				height: window.innerHeight - 50,
				modal: true,
				open: function () {
					mctracker.showProcessing();
				},
				close: function () {
					$("body").css("overflow", "auto");
				}
			})).load(function() {
				mctracker.hideProcessing();
				$(this).fadeIn('fast');
			});
		});
	};

	var processMessage = function (data) {
		if ( data.type == "rogerthat.mfd.changes" ) {
			load();
		}
	};

	var load = function (data) {
		var tb = lj("#table_body");
		mctracker.call({
			url: "/mobi/rest/mfd/list",
			success: function (data, textStatus, XMLHttpRequest) {
				$.each(data.message_flows, function (index, mfd){
					mfd.timestamp_date = mctracker.formatDate(mfd.timestamp);
                    mfd.error = null;
					if (mfd.status == 0) {
						if (mfd.multilanguage) {
							if (mfd.i18n_warning) {
								// Working flow, but some languages missing
								mfd.status_color = 'yellow';
								mfd.status_description = mfd.i18n_warning
							} else {
								// Perfect multi-language flow. Working flow, with all languages.
								mfd.status_color = 'white';
								mfd.status_description = 'Languages: ' + data.service_languages.join(", ");
							}
						} else {
							// Perfect single-language flow
							mfd.status_color = 'white';
							mfd.status_description = 'Languages: ' + data.service_languages[0];
						}
					} else {
						mfd.status_color = 'orange';
						mfd.status_description = 'Needs attention:';
						if (!mfd.error)
							mfd.error = [];
						if (mfd.status == 1) {
							mfd.error.push("Flow broken: " + mfd.validation_error);
						}
						if (mfd.status == 2) {
							mfd.error.push("Broken subflows: " + mfd.broken_sub_flows.join(", "));
						}
					}
					var html = $.tmpl(template, mfd);
					tb.append(html);
				});				
			}
		});
		tb.empty();
	};

	return function () {
		mctracker.registerMsgCallback(processMessage);

		applyJQueryInUI();

		load();
	};
}

mctracker.registerLoadCallback("messageFlowDesignContainer", messageFlowDesignScript());