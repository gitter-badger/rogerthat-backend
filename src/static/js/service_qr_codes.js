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

var serviceQRCodesScript = function () {
	var container = "#serviceQRCodesContainer";
	var lj = mctracker.getLocaljQuery(container);
	var cursor = "";
	var createQRCodeDialog = null;
	
	var user_lines_template = 
		'{{each defs}}'+
		'    <tr style="height: 85px;">'+
		'        <td style="width: 75px;"><a href="${url}" target="_blank"><img src="${url}" style="width: 75px;"/></a></td>'+
		'        <td>{{if service_identifier == defaultIdentity}}[default]{{else}}${service_identifier}{{/if}}</td>' +
		'        <td>${description}</td>'+
		'        <td>${tag}</td>'+
		'        <td><a class="action-link show_link" tag="${description}">Show&nbsp;links</a><div style="display: none;">Link to QR-Code image:<br><span style="color: yellow;">${url}</span><br><br>Link to use in email messages:<br><span style="color: yellow;">${email_url}</span><br><br>Link to use in sms messages:<br><span style="color: yellow;">${sms_url}</span><br><br>Link to embed  in your custom designed QR-Code:<br><span style="color: yellow;">${embed_url}</span></div>'+
		'            <br>'+
		'            <a class="action-link statistics" tag="${description}">Show&nbsp;statistics</a><div style="display: none;">'+
		'                # total scans:&nbsp;<span style="color: yellow;">${total_scan_count}</span><br>'+
		'                # Rogerthat scans:&nbsp;<span style="color: yellow;">${scanned_from_rogerthat_count}</span><br>'+
		'                # supported platform scans:&nbsp;<span style="color: yellow;">${scanned_from_outside_rogerthat_on_supported_platform_count}</span><br>'+
		'                # unsupported platform scans:&nbsp;<span style="color: yellow;">${scanned_from_outside_rogerthat_on_unsupported_platform_count}</span><br></div>'+
		'            <br>'+
		'            <a class="action-link edit" sidid="${id_}">Edit</a>' +
        '            <br>'+
        '            <a class="action-link delete" sidid="${id_}">Delete</a></td></tr>{{/each}}';

	var validateInput = function (sid) {
        var template_key = $('#template', createQRCodeDialog).val();
        var description = $("#cq_new_description", createQRCodeDialog).val();
        var tag = $("#cq_new_tag", createQRCodeDialog).val();
        var branding = $("#cq_new_branding", createQRCodeDialog).val() || null;

        var ok = true;

        if (!sid && !template_key) {
            $('#template_required', createQRCodeDialog).fadeIn('slow');
            ok = false;
        } else {
            $('#template_required', createQRCodeDialog).fadeOut('slow');
        }
        
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
            return false;

        var sf = null;
        if ($('#qr_radio_start_flow', createQRCodeDialog).prop('checked')) {
            sf = $("#static_flow", createQRCodeDialog).val() || null;
        }
        
        var r = {
            description: description,
            tag: tag,
            static_flow: sf,
            branding: branding
        };

        if (sid) {
            r.sid = sid.id_;
        } else {
            r.template_key = template_key;
            r.service_identity = $("#identities", createQRCodeDialog).val();
        }

        return r;
	};

	var createOrEditQRClickHandler = function (sid) {
	    return function () {
            var data = validateInput(sid);
            if (!data)
                return;

            mctracker.call({
                url: sid ? '/mobi/rest/qr/edit' : '/mobi/rest/qr/create',
                type: 'post',
                data: {
                    data: JSON.stringify(data)
                }, 
                success: function (data) {
                    if (data.success) {
                        createQRCodeDialog.dialog('close');
                        mctracker.broadcast({
                             type: 'rogerthat.service.qr.created'
                        });
                    } else {
                        mctracker.alert(data.errormsg);
                    }
                }
            });
	    };
	};

	var initScreen = function () {
		load_more();
		lj("#more").click(load_more);
		lj("#reload").click(re_load);
		createQRCodeDialog = lj("#createQRCodeDialog").dialog({
			autoOpen: false,
			width: 410,
			modal: true
		});
		$("input[name='qr_behavior']", createQRCodeDialog).change(function () {
            if ($('#qr_radio_start_flow', createQRCodeDialog).prop('checked')) {
                $("#qr_behavior_start_flow", createQRCodeDialog).show();
            } else {
                $("#qr_behavior_start_flow", createQRCodeDialog).hide();
            }
		});
		lj("#create_new").click(function () {
			mctracker.call({
				url: '/mobi/rest/qrtemplates/list',
				type: 'GET',
				success: function  (data, textStatus, XMLHttpRequest) {
				    if (data.length == 0) {
						mctracker.alert('Error: Cannot create QR code. You should first create a QR code template.');
						return;
					}
					var template = $("#template", createQRCodeDialog).empty();
					$.each(data, function(i, o) {
						template.append($("<option></option>").val(o.id).text(o.description));
					});

					showQRDialog();
				}
			});

		});
	};

	var showQRDialog = function (sid) {
        var identitiesLoaded = !!sid;
        var messageFlowsLoaded = false;
        var brandingsLoaded = false;

        if (sid) {
            $("#identities_row", createQRCodeDialog).hide();
        } else {
            $("#identities_row", createQRCodeDialog).show();
            var identities = $("#identities ", createQRCodeDialog).empty().val(DEFAULT_SERVICE_IDENTITY);
            mctracker.call({
                url: '/mobi/rest/service/identities',
                type: 'GET',
                success: function (data) {
                    $.each(data, function(i, o) {
                        var text = o.identifier == DEFAULT_SERVICE_IDENTITY ? "[default]" : o.identifier;
                        identities.append($("<option></option>").val(o.identifier).text(text));
                        
                        identitiesLoaded = true;
                        
                        if (identitiesLoaded && messageFlowsLoaded && brandingsLoaded) {
                            $(".mcerror", createQRCodeDialog).hide();
                            createQRCodeDialog.dialog('open');
                        }
                    });
                }
            });
        }

        var staticFlowSelect = $("#static_flow", createQRCodeDialog).empty();
        staticFlowSelect.append($("<option></option>").attr('value', '').text('no message flow'));
        mctracker.call({
            url: "/mobi/rest/mfd/list_valid",
            success: function (data) {
                $.each(data.message_flows, function (i, mfd) {
                    staticFlowSelect.append($("<option></option>").attr('value', mfd.name).text(mfd.name + " [" + mctracker.formatDate(mfd.timestamp) + "]"));
                });

                if (sid && sid.static_flow_name)
                    staticFlowSelect.val(sid.static_flow_name);

                messageFlowsLoaded = true;

                if (identitiesLoaded && messageFlowsLoaded && brandingsLoaded) {
                    $(".mcerror", createQRCodeDialog).hide();
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

                if (sid)
                    brandingSelect.val(sid.branding);

                if (identitiesLoaded && messageFlowsLoaded && brandingsLoaded) {
                    $(".mcerror", createQRCodeDialog).hide();
                    createQRCodeDialog.dialog('open');
                }
            }
        });

        if (sid) {
            createQRCodeDialog.dialog('option', {
                title: 'Edit QR code',
                buttons: {
                    Edit: createOrEditQRClickHandler(sid),
                    Cancel: function () {
                        createQRCodeDialog.dialog('close');
                    }
                }
            });
            $("#template_row", createQRCodeDialog).hide();
            $("#cq_new_description", createQRCodeDialog).val(sid.description);
            $("#cq_new_tag", createQRCodeDialog).val(sid.tag);
            $(sid.static_flow_name ? '#qr_radio_start_flow' : '#qr_radio_web_callback', createQRCodeDialog).prop('checked', true);
        } else {
            createQRCodeDialog.dialog('option', {
                title: 'Create new QR code',
                buttons: {
                    Create: createOrEditQRClickHandler(),
                    Cancel: function () {
                        createQRCodeDialog.dialog('close');
                    }
                }
            });
            $("#template_row", createQRCodeDialog).show();
            $("#cq_new_description, #cq_new_tag, #identities", createQRCodeDialog).val('');
            $('#qr_radio_web_callback', createQRCodeDialog).prop('checked', true);
        }
        $("input[name='qr_behavior']", createQRCodeDialog).change();
	};

	var re_load = function () {
		lj("#table_body").empty();
		cursor = "";
		load_more();
	};
	
	var load_more = function () {
		mctracker.call({
			url: '/mobi/rest/qr/list',
			data: {
				cursor: cursor
			},
			success: function (data) {
				var table_body = lj("#table_body");
				var html = $.tmpl(user_lines_template, {defs: data.defs, defaultIdentity:DEFAULT_SERVICE_IDENTITY});
				$("a.action-link.delete", html).click(function () {
					var a = $(this);
					mctracker.confirm("Are you sure you want to delete this QR code?",
						function () {
							var sidid = new Number(a.attr("sidid"));
							mctracker.call({
								url: '/mobi/rest/qr/delete',
								type: 'POST',
								data: {
									data: JSON.stringify({ sid: sidid })
								},
								success: function () {
									a.closest('tr').fadeOut('slow', function () {
										$(this).detach();
									});
									mctracker.broadcast({
		                                type: 'rogerthat.service.qr.deleted'
		                            });
								}
							});

					});
				});
				$("a.show_link", html).each(function () {
					var a = $(this);
					var dialog = a.next().dialog({
						title: 'QR-Code links for tag "'+ a.attr('tag') +'"',
						autoOpen: false,
						width: 650,
						height: 300
					});
					a.click(function () {
						dialog.dialog('open');
					});
				});
                $("a.statistics", html).each(function () {
                    var a = $(this);
                    var dialog = a.next().dialog({
                        title: 'Statistics for qr code "'+ a.attr('tag') +'"',
                        autoOpen: false,
                        width: 300,
                        height: 150
                    });
                    a.click(function () {
                        dialog.dialog('open');
                    });
                });
                $("a.edit", html).click(function () {
                    var a = $(this);
                    var sid;
                    var sidID = a.attr("sidid");
                    $.each(data.defs, function (i, s) {
                        if (s.id_ == sidID) {
                            sid = s;
                            return false;
                        }
                    });
                    showQRDialog(sid);
                });
				table_body.append(html);
				cursor = data.cursor;
				if (! cursor) {
					lj("#more").fadeOut();
				} else {
					lj("#more").fadeIn();
				}
			},
			error: mctracker.showAjaxError
		});
	};
	
    var processMessage = function (data) {
        if (data.type == 'rogerthat.service.qr.created') {
        	re_load();
        }
    };

	return function() {
        mctracker.registerMsgCallback(processMessage);

		initScreen();
	};
};

mctracker.registerLoadCallback("serviceQRCodesContainer", serviceQRCodesScript());