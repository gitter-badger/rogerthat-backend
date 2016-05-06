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

var serviceLogsScript = function () {
	var container = "#serviceLogsContainer";
	var lj = mctracker.getLocaljQuery(container);
	var timestamp = new Date().getTime() * 10;
	var status = {
		'1': {caption:'Success',color:'#b4fe00'},
		'2': {caption:'Error',color:'#300000'},
		'3': {caption:'Waiting for response',color:'#ffe400'}
	};
	var type = {
		'1': 'Callback',
		'2': 'Call'
	};
		
	var initScreen = function () {
		load_more();
		lj("#more").click(load_more);
		lj("#reload").click(function(){
			timestamp = new Date().getTime() * 10;
			lj("#table_body").empty();
			load_more();
		});
		lj("#detail").dialog({
			draggable: true,
			autoOpen: false,
			title: "Request details",
			width: 500,
			modal: true 
		}).attr('dialog', container);
	};
	
	var load_more = function () {
		var line_template = lj("#row_template").html().replace("<!--", "").replace("-->","");
		var detail_template = lj("#request_details_template").html().replace("<!--", "").replace("-->","");
		mctracker.call({
			url: '/mobi/rest/service/logs',
			data: {
				timestamp: timestamp
			},
			success: function (data) {
				var table_body = lj("#table_body");
				$.each(data, function (index, log){
					var html = $.tmpl(line_template);
					$(".log_timestamp", html).text(mctracker.formatDate(log.timestamp/1000, true));
					$(".log_type", html).text(type[log.type+""]);
					var sto = status[log.status+""];
					var stat = sto.caption;
					if (log.status == 2) 
						stat += "<br>Error code: " + log.errorCode + "<br>Message: " + log.errorMessage;
					$(".log_status", html).html(stat).css("color", sto.color);
					var f = log['function'];
					try {
						var resp  = JSON.parse(log.response);
						if (resp.result.type == "flow") 
							f += " ==> messaging.start_flow";
						else if (resp.result.type == "message")
							f += " ==> messaging.send";
						else if (resp.result.type == "form")
							f += " ==> messaging.send_form";
					} catch (err) {	}
					$(".log_function", html).text(f);
					
					var expanded = false;
					var details = null;
					var link = $("div.expander", html)
					html.click(function () {
						expanded = !expanded;
						if (expanded) {
							link.text("-");
							details = $.tmpl(detail_template);
							html.after(details);
							var request = CodeMirror.fromTextArea($("div.api_request > textarea", details).get()[0], {
								mode:  {name: "javascript", json: true},
							    lineNumbers: true,
							    readOnly: true,
							    lineWrapping: true
							});
							request.setValue(log.request || "");
							var response = CodeMirror.fromTextArea($("div.api_response > textarea", details).get()[0], {
								mode:  {name: "javascript", json: true},
							    lineNumbers: true,
							    readOnly: "nocursor",
							    lineWrapping: true
							});
							response.setValue(log.response || "");
						} else {
							link.text("+");
							details.remove();
						}
					});
					table_body.append(html);
					if (timestamp>log.timestamp)
						timestamp = log.timestamp;
				});
			},
			error: mctracker.showAjaxError
		});
	};

	return function() {
		initScreen();
	};
};

mctracker.registerLoadCallback("serviceLogsContainer", serviceLogsScript());