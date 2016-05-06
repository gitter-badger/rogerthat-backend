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

var feedbackScript = function () {
	var container = "#feedbackContainer";
	var lj = mctracker.getLocaljQuery(container);

	function applyJQueryInUI() {
		lj("#username").text(loggedOnUserName);
		lj("#thankyou").dialog({
			width: 300,
			modal: true,
			autoOpen: false,
			title: 'Rogerthat',
			buttons: {
				Ok : function () {
					lj("#thankyou", "d").dialog('close');
				}
			}
		}).attr('dialog', container);
		lj("#submit").button().click(function () {
			var subject = lj("#subject").val();
			if (! subject) {
				lj("#error").text("Please add a subject!");
				return;
			}
			var message = lj("#message").val();
			if (! message) {
				lj("#error").text("Please add a description!");
				return;
			}
			mctracker.call({
				url: '/mobi/rest/system/feedback',
				type: 'POST',
				data: {
					data: JSON.stringify({
						type_ : lj("input[name='type']:checked").val(),
						subject: subject,
						message: message
					})
				},
				success: function () {
					lj("#thankyou", "d").dialog('open');
					lj("#subject").val('');
					lj("#message").val('');
				}
			});
		});
		lj(".topbar").watermark();
	};
	
	return function () {
		applyJQueryInUI();
	};
};

mctracker.registerLoadCallback("feedbackContainer", feedbackScript());