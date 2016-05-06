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

var qrTemplateScript = function () {
	var container = "#qrTemplatesContainer";
	var lj = mctracker.getLocaljQuery(container);
	var color_test = /^([a-fA-F0-9]{2})([a-fA-F0-9]{2})([a-fA-F0-9]{2})$/;
	var createQRCodeDialog = null;
	var createTemplateKey = null;
	
	var qr_template_list_template = 
		"<br>"+
		"  <table>{{each templates}}"+
		"    <tr><td style=\"width: 105px;\"><img src=\"/mobi/service/qrtemplate/example?template_id=${$value.id}\" style=\"width: 100px;\" /></td>"+
		"        <td><b>${$value.description}</b><br>"+
		"        key: ${$value.id}<br>"+
		"        color: ${$value.color}<br>"+
		"        created on: ${$value.timestamp} <br>" +
		"        <a class=\"action-link\" name=\"delete\" key=\"${$value.id}\" description=\"${$value.description}\">Delete</a> | <a class=\"action-link\" href=\"/mobi/service/qrtemplate/example?template_id=${$value.id}\" target=\"_blank\">Preview</a> | <a class=\"action-link\" name=\"create\" key=\"${$value.id}\">Create new QR code from this template</a></td>"+
		"    </tr>{{/each}}</table>";
	
	function applyJQueryInUI() {
		lj("#uploadContainer").panel({
	        collapsible:false
	    });
		lj("#qrTemplateListContainer").panel({
	        collapsible:false
	    });
		lj("#upload_button").button().click(upload);
		lj("#color").keyup(function () {
			var color = $(this).val();
			if (color_test.test(color)) {
				lj("#color_preview").css('background-color', '#'+color);
				lj("#color_preview").show('slow');
				lj("#color_error").fadeOut('slow');
			} else {
				lj("#color_preview").hide('slow');
				lj("#color_error").fadeIn('slow');
			}
		});
		createQRCodeDialog = lj("#createQRCodeDialog").dialog({
			title: 'Create a new QR code',
			modal: true,
			width: 410,
			autoOpen: false,
			buttons: {
				Create: function() {
					var description = $("#cq_new_description", createQRCodeDialog).val();
					var tag = $("#cq_new_tag", createQRCodeDialog).val();
					var branding = $("#cq_new_branding", createQRCodeDialog).val() || null;
					var ok = true;
                    if (!description) {
                        $('#description_required', createQRCodeDialog).fadeIn('slow');
                        ok = false;
                    } else {
                        $('#description_required', createQRCodeDialog).fadeOut('slow');
                    }

                    if (!tag) {
                        $('#tag_required', createQRCodeDialog).fadeIn('slow');
                        ok = false;
                    } else {
                        $('#tag_required', createQRCodeDialog).fadeOut('slow')
                    }

                    if (!ok)
                        return;

                    var sf = null;
                    if ($('#qrt_radio_start_flow', createQRCodeDialog).prop('checked')) {
                        sf = $("#static_flow", createQRCodeDialog).val() || null;
                    }

                    mctracker.call({
						url: '/mobi/rest/qr/create',
						type: 'post',
						data: {
							data: JSON.stringify({
								description: description,
								branding : branding,
								tag: tag,
								template_key: createTemplateKey,
								static_flow: sf,
                                service_identity: $("#identities", createQRCodeDialog).val()
							})
						},
						success: function (data) {
							$('<div>Your QR code is available at:<br></div>')
						        .append($('<a class="link" style="color: #fff;" target="blank" href="' + data.qr_details.image_uri + '">' + data.qr_details.image_uri + '</a>'))
						        .append($('<br>'))
						        .append($('<img src="' + data.qr_details.image_uri + '"></img>'))
						        .dialog({
						            title: "Your new qr code.",
						            width: 370
						        });
							createQRCodeDialog.dialog('close');
							mctracker.broadcast({
								type: 'rogerthat.service.qr.created'
							});
						}
					});
				},
				Cancel: function() {
					createQRCodeDialog.dialog('close');
				}
			}
		});
        $(".mcerror", createQRCodeDialog).hide();
        $("input[name='qrt_behavior']", createQRCodeDialog).change(function () {
            if ($('#qrt_radio_start_flow', createQRCodeDialog).prop('checked')) {
                $("#qrt_behavior_start_flow", createQRCodeDialog).show();
            } else {
                $("#qrt_behavior_start_flow", createQRCodeDialog).hide();
            }
        });
	};
	
	var upload = function() {
		if (! lj("#description").val()) {
			lj("#description_error").fadeIn('slow');
			return;
		}
		var color = lj("#color").val();
		if (! color || ! color_test.test(color)) {
			lj("#color_error").fadeIn('slow');
			return;
		}
		mctracker.showProcessing();
		lj("#upload").submit();
		lj("#color_error, #description_error").fadeOut('slow');
	};
	
	var loadQRTemplateList = function () {
		mctracker.call({
			url: '/mobi/rest/qrtemplates/list',
			type: 'GET',
			success: function  (data, textStatus, XMLHttpRequest) {
				$.each(data, function(i, o) {
					o.timestamp = new Date(o.timestamp*1000);
				});
				var html = $.tmpl(qr_template_list_template, {templates:data});
				$("a[name='delete']", html).click(deleteQRTemplate);
				$("a[name='create']", html).click(createQRTemplate);
				lj("#qr_template_list").empty().append(html);
			},
			error: function (data, textStatus, XMLHttpRequest) { 
				mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
			}
		});
	};
	

	var createQRTemplate = function() {
        var key = $(this).attr('key');
        $("#cq_new_description", createQRCodeDialog).val('');
        $("#cq_new_tag", createQRCodeDialog).val('');
        $("#cq_new_branding", createQRCodeDialog).val('');
        createTemplateKey = key;

        var identitiesLoaded = false;
        var messageFlowsLoaded = false;
        var brandingsLoaded = false;

        mctracker.call({
            url : '/mobi/rest/service/identities',
            type : 'GET',
            success : function(data) {
                var identities = $("#identities ", createQRCodeDialog).empty().val(DEFAULT_SERVICE_IDENTITY);
                $.each(data, function(i, o) {
                    var text = o.identifier == DEFAULT_SERVICE_IDENTITY ? "[default]" : o.identifier;
                    identities.append($("<option></option>").val(o.identifier).text(text));

                    identitiesLoaded = true;

                    if (identitiesLoaded && messageFlowsLoaded && brandingsLoaded) {
                        createQRCodeDialog.dialog('open');
                    }
                });
            }
        });

        $('#qrt_radio_web_callback', createQRCodeDialog).prop('checked', true);
        $("input[name='qrt_behavior']", createQRCodeDialog).change();
        var staticFlowSelect = $("#static_flow", createQRCodeDialog).empty();
        mctracker.call({
            url : "/mobi/rest/mfd/list_valid",
            success : function(data) {
                staticFlowSelect.append($("<option></option>").attr('value', '').text('no message flow'));

                $.each(data.message_flows, function(i, mfd) {
                    staticFlowSelect.append($("<option></option>").attr('value', mfd.name).text(
                            mfd.name + " [" + mctracker.formatDate(mfd.timestamp) + "]"));
                });

                messageFlowsLoaded = true;

                if (identitiesLoaded && messageFlowsLoaded && brandingsLoaded) {
                    createQRCodeDialog.dialog('open');
                }
            }
        });

        var brandingSelect = $("#cq_new_branding", createQRCodeDialog).empty().append(
                $("<option></option>").val('').text('[Identity description branding]'));
        mctracker.call({
            hideProcessing : true,
            url : "/mobi/rest/branding/list",
            success : function(data) {
                $.each(data.sort(descriptionSort), function(i, brand) {
                    var formattedDate = mctracker.formatDate(brand.timestamp, true);
                    brandingSelect.append($("<option></option>").val(brand.id).text(
                            brand.description + " [" + formattedDate + "]"));
                });

                brandingsLoaded = true;

                if (identitiesLoaded && messageFlowsLoaded && brandingsLoaded) {
                    createQRCodeDialog.dialog('open');
                }
            }
        });
    };
	
	var deleteQRTemplate = function () {
		var key = $(this).attr('key');
		var description = $(this).attr('description');
		mctracker.confirm(
			"Are you sure you want to delete '" + description + "' template?", 
			function () {
			mctracker.call({
				url: '/mobi/rest/qrtemplates/delete',
				type: 'POST',
				data: {
					data: JSON.stringify({
						key: key
					})
				},
				success: function  (data, textStatus, XMLHttpRequest) {
					loadQRTemplateList();
				},
				error: function (data, textStatus, XMLHttpRequest) { 
					mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
				}
			});
		});
	};
	
	var processMessage = function (data) {
		if ( data.type == "rogerthat.store_qr_template.post_result" ) {
			if (data.error) {
				mctracker.hideProcessing();
				lj("#upload_error").empty().append($("<br>"));
				lj("#upload_error").append("There was an error while posting your template!").append($("<br>"));
				if (data.error_code) {
					lj("#upload_error").append("Error code: "+data.error_code).append($("<br>"));
				}
				lj("#upload_error").append("Error description: "+data.error).fadeIn('slow');
			} else {
				lj("#upload_error").fadeOut('slow');
				loadQRTemplateList();
                                lj('#upload_button_container').html('<input id="file" type="file" name="file" accept="*.png" />');
                                lj('#description').val('');
                                lj('#color').val('000000');
                                lj('#color_preview').css('background-color', '#000');
			}
		}
	};
	
	return function () {
		mctracker.registerMsgCallback(processMessage);
		
		applyJQueryInUI();
		
		loadQRTemplateList();
	};
};

mctracker.registerLoadCallback("qrTemplatesContainer", qrTemplateScript());