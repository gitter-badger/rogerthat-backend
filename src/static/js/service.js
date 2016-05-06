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

var serviceScript = function () {
	var container = "#servicePanelContainer";
	var container_name = "servicePanelContainer";
	var lj = mctracker.getLocaljQuery(container);
	var apiKeyToDeleteDetails = null;
	
	var ak_template = '<li><span class="mcdata">${name}</span><br><span style="font-family: monospace;">${key}</span><br>Generated on ${date} <a class="action-link">Delete</a></li>';
	var ai_template = '{{each actions}}<li class="mcwarning">${$value}</li>{{/each}}';
	
	var applyJQueryInUI = function () {
		lj("#apiKeysContainer").panel({
	        collapsible:false
	    });
		lj("#callbackRpcDetailsContainer").panel({
	        collapsible:false
		});
		lj("#serviceStatusContainer").panel({
	        collapsible:false
		});
		lj("#interactiveLoggingDialog").dialog({
			autoOpen: false,
			modal: false,
			width: '400px',
			title: "Test callback response logs"
		}).attr('dialog', container);
		lj("#serviceAdministratorsContainer").panel({
			collapsible: false
		});
		lj("#addAdministratorDialog #email").autocomplete({
            source: function (request, response) {
                mctracker.call({
                    url: "/mobi/rest/service/search_users",
                    hideProcessing: true,
                    data: {
                        admin: true,
                        app_id: "rogerthat",
                        term: request.term
                    },
                    success: function (data, textStatus, XMLHttpRequest) {
                        result = [];
                        $.each(data, function (i, user) {
                          result.push({label: user.name + '<'+ user.email+'>', value: user.email});  
                        });
                        response(result);
                    },
                    error: function () {
                        response([]);
                    }
                })
            },
            minLength: 3,
            select: function( event, ui ) {
                $(this).val(ui.item.value);
            }
	    });
		mctracker.call({
		   url: '/mobi/rest/service/admin/roles',
		   success: function  (data, textStatus, XMLHttpRequest) {
               var templ = "{{each roles}}<option value=\"${$value}\">${$value}</option>{{/each}}";
               lj("#role", "dc").append( $.tmpl(templ, {roles:data}) );
		   }
		});
		lj("#addAdministratorDialog").dialog({
			autoOpen: false,
			modal: true,
			width: '400px',
			title: "Add administrator",
			open: function () {
				lj("#email", "dc").val('').focus();
				lj("#role", "dc").val('');
			},
			buttons: {
				'Grant': function () {
					var email = $.trim(lj("#email", "dc").val());
					if (!email) {
						lj("#email_required", "dc").show();
						lj("#email", "dc").focus();
						return;
					}
					var role = lj("#role", "dc").val();
					mctracker.call({
						url: '/mobi/rest/service/admin/roles/grant',
						type: 'POST',
						data: {
							data: JSON.stringify({
							    user_email: email, 
							    role: role, 
							    identity: '+default+'
							})
						},
						success: function  (data, textStatus, XMLHttpRequest) {
						    if (!data.success) {
						        mctracker.alert(data.errormsg);
						        return;
						    }
							lj("#addAdministratorDialog", "d").dialog('close');
							mctracker.alert("Administrator added successfully.");
						}
					});
				},
				'Cancel': function () {
					lj("#addAdministratorDialog", "d").dialog('close');
				}
			}
		}).attr('dialog', container);
		lj("#getNameForAPIKeyDialog").dialog({
			autoOpen: false,
			modal: true,
			width: '400px',
			title: "Generate new api key",
			open: function () {
				lj("#keyName", "dc").focus();
			},
			buttons: {
				'Generate': function () {
					var name = $.trim(lj("#keyName", "dc").val());
					if (!name) {
						lj("#name_required", "dc").show();
						lj("#keyName", "dc").focus();
						return;
					}
					mctracker.call({
						url: '/mobi/rest/service/generate_api_key',
						type: 'POST',
						data: {
							data: JSON.stringify({
								name: name
							})
						},
						success: function  (data, textStatus, XMLHttpRequest) {
							lj("#getNameForAPIKeyDialog", "d").dialog('close');
							configuration2Screen(data);
						}
					});
				},
				'Cancel': function () {
					lj("#getNameForAPIKeyDialog", "d").dialog('close');
				}
			}
		}).attr('dialog', container);
		lj("#deleteAPIKey").dialog({
			autoOpen: false,
			modal: true,
			width: '400px',
			title: "Delete api key",
			buttons: {
				'Delete': function () {
					mctracker.call({
						url: '/mobi/rest/service/delete_api_key',
						type: 'POST',
						data: {
							data: JSON.stringify({
								key: apiKeyToDeleteDetails.key
							})
						},
						success: function  (data, textStatus, XMLHttpRequest) {
							lj("#deleteAPIKey", "d").dialog('close');
							configuration2Screen(data);
						},
						error: function (data, textStatus, XMLHttpRequest) { 
							mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
						}
					});
				},
				'Cancel': function () {	lj("#deleteAPIKey", "d").dialog('close'); }
			}
		}).attr('dialog', container);
		lj("#generateKey").button().click(function () {
			lj("#name_required", "dc").hide();
			lj("#keyName", "dc").val("");
			lj("#getNameForAPIKeyDialog", "d").dialog('open');
		});
		lj("#saveConfiguration").button().click(saveConfiguration);
		lj("#testConfiguration").button().click(testConfiguration);
		lj("#addAdministrator").button().click(addAdministrator);
		$("input", lj("#callBackMethods")).change(enabledSaveConfiguration).keypress(enabledSaveConfiguration);
		lj("#httpCallBackURI").change(showHTTPWarning).keypress(showHTTPWarning);
		lj("#generateSIK").click(regenerateSIK);
		lj("#chkEnabled").change(toggleEnabled);
		lj("*").attr('disabled', true).not(lj("#noAPIKeys")).fadeTo(0, 0.6);

		$("#svcUpdatesPending").click(publishPendingChanges);
	};
	
	var addAdministrator = function () {
		lj("#addAdministratorDialog", "d").dialog('open');
	};
	
	var toggleEnabled = function () {
		mctracker.call({
			url: '/mobi/rest/service/' + (lj("#chkEnabled").prop("checked") ? 'enable' : 'disable'),
			type: 'POST',
			data: {
				data: JSON.stringify({})
			},
			success: function  (data, textStatus, XMLHttpRequest) {
				configuration2Screen(data);
			},
			error: function (data, textStatus, XMLHttpRequest) { 
				mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
			}
		});
	};
	
	var showHTTPWarning = function () {
		var uri = lj("#httpCallBackURI").val();
		if ( uri.length > 5 && uri.substring(0, 5) == "http:")
			lj("#httpCallBackURIWarning").text("* Using plain http for callbacks is insecure as it sends your service identification key unencrypted over the internet.");
		else
			lj("#httpCallBackURIWarning").text("");
	};
	
	var enabledSaveConfiguration = function () {
		lj("#saveConfiguration").removeAttr('disabled').fadeTo('slow', 1);
	};
	
	var regenerateSIK = function () {
		mctracker.call({
			url: '/mobi/rest/service/regenerate_sik',
			type: 'POST',
			data: {
				data: JSON.stringify({})
			},
			success: function  (data, textStatus, XMLHttpRequest) {
				configuration2Screen(data);
			},
			error: function (data, textStatus, XMLHttpRequest) { 
				mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
			}
		});
	};
	
	var testConfiguration = function () {
		var textarea = lj("#logWindow", "dc");
		textarea.val("Launching testcallback...\n");
		lj("#interactiveLoggingDialog", "d").dialog('open');
		mctracker.call({
			url: '/mobi/rest/service/perform_test_callback',
			type: 'POST',
			data: {
				data: JSON.stringify({})
			},
			success: function  (data, textStatus, XMLHttpRequest) {
				textarea.val(textarea.val()+"Succesfully launched test callback, result will be posted.\n");
			},
			error: function (data, textStatus, XMLHttpRequest) { 
				mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
			}
		});
	};
	
	var saveConfiguration = function () {
		//Validate configuration
		lj("#validationError").text("");
		if (! (lj("#httpCallBackMethod").prop("checked") || lj("#xmppCallBackMethod").prop("checked"))) {
			lj("#validationError").text("Select the way the callbacks are delivered. HTTP(s)/XMPP");
			return;
		}
//		var httpPattern = /^(http|https):\/\/[\w\-_]+(\.[\w\-_]+)+([\w\-\.,@?^=%&amp;:/~\+#]*[\w\-\@?^=%&amp;/~\+#])?$/g;
//		if ( lj("#httpCallBackMethod").prop("checked") && ! lj("#httpCallBackURI").val().match(httpPattern) ) {
//			lj("#validationError").text("The http address is not valid.");
//			lj("#httpCallBackMethod").focus();
//			return;
//		}
		var xmppPattern = /^(?:([^@\/<>'"]+)@)?([^@\/<>'"]+)(?:\/([^<>'"]*))?$/g;
		if ( lj("#xmppCallBackMethod").attr("prop") && ! lj("#xmppCallBackJid").val().match(xmppPattern) ) {
			lj("#validationError").text("The jid is not valid.");
			lj("#xmppCallBackMethod").focus();
			return;
		}
		mctracker.call({
			url: '/mobi/rest/service/update_callback_configuration',
			type: 'POST',
			data: {
				data: JSON.stringify({
					httpURI: lj("#httpCallBackMethod").prop("checked") ? lj("#httpCallBackURI").val() : null,
					xmppJID: lj("#xmppCallBackMethod").prop("checked") ? lj("#xmppCallBackJid").val() : null
				})
			},
			success: function  (data, textStatus, XMLHttpRequest) {
				configuration2Screen(data);
			},
			error: function (data, textStatus, XMLHttpRequest) { 
				mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
			}
		});
	};
	
	var addAPIKeyToUI = function (ak) {
		ak.date = mctracker.formatDate(ak.timestamp);
		var gatml = $.tmpl(ak_template, ak);
		gatml.hide();
		lj("#apiKeys").append(gatml);
		gatml.fadeIn('slow');
		$("a", gatml).click(function () {
			lj("#apiKeyNameLabel", "dc").text(ak.name);
			apiKeyToDeleteDetails = ak;
			lj("#deleteAPIKey", "d").dialog('open');
		});
	};
	
	var configuration2Screen = function (configuration) {
		lj("#validationError").empty();
		lj("#apiKeys").empty();
		var elements = lj("*").removeAttr('disabled')
			.not(lj("#chkEnabled"))
			.not(lj("#testConfiguration"))
			.not(lj("#saveConfiguration"));
		if (! configuration.apiKeys || configuration.apiKeys.length == 0) {
			elements.fadeTo('slow', 1);
		} else {
			elements.not(lj("#noAPIKeys").hide()).fadeTo('slow', 1);
			$.each(configuration.apiKeys, function(index, val) {addAPIKeyToUI(val);});
		}
		lj("#apiActionPoints").empty().append($.tmpl(ai_template, configuration));
		var canBeEnabled = configuration.actions.length == 0;
		if (canBeEnabled)
			lj("#actionPoints, #apiActionPoints").hide();
		lj("#actionPoints").css('display', canBeEnabled ? 'none':'block');
		lj("#chkEnabled").prop('checked', configuration.enabled).attr('disabled', ! canBeEnabled).fadeTo('slow', canBeEnabled ? 1:0.6);
		lj("#chkEnabledLabel").fadeTo('slow', canBeEnabled ? 1:0.6);
		lj("#testConfiguration").attr('disabled', ! configuration.needsTestCall).fadeTo('slow', configuration.needsTestCall ? 1:0.6);
		if ( configuration.needsTestCall ) 
			lj("#testConfiguration").removeAttr('disabled');
		lj("#saveConfiguration").attr('disabled', true).fadeTo('slow', 0.6);
		lj("#httpCallBackSecret").text(configuration.sik);
		lj("#callBackFromJid").text(configuration.callBackFromJid);
		if (configuration.callBackURI) {
			lj("#httpCallBackMethod").prop("checked", true);
			lj("#httpCallBackURI").val(configuration.callBackURI);
			lj("#xmppCallBackJid").val("");
		}
		if (configuration.callBackJid) {
			lj("#xmppCallBackMethod").prop("checked", true);
			lj("#xmppCallBackJid").val(configuration.callBackJid);
			lj("#httpCallBackURI").val("");
		}
		lj("#callbackRpcDetailsContainer input[type=checkbox]").each(function () {
			var code = $(this).attr('code');
			if (code) {
				code = new Number(code);
				$(this).attr('checked', ((configuration.callbacks & code) == code)).change(function () {
					mctracker.call({
						url: '/mobi/rest/service/enable_callback',
						type: 'post',
						data: {
							data: JSON.stringify({
								callback: code,
								enabled: $(this).prop('checked')
							})
						}
					});
				});
			}
		});
		if (configuration.enabled) {
			if (configuration.mobidickUrl) {
				lj("#mobidick").show();
				lj("#mobidick_link")
					.text("Open Mobidick sample service control panel")
					.attr("href", configuration.mobidickUrl)
					.attr("target", "_blanc");
			} else {
				lj("#mobidick").hide();
			}
		} else {
			if (! (configuration.callBackURI || configuration.callBackJid )) {
				lj("#mobidick").show();
				lj("#mobidick_link")
					.text("Use Mobidick sample service")
					.click(configure_mobidick);
			} else {
				lj("#mobidick").hide();
			}
		}
		if (configuration.updatesPending) {
		    $("#svcUpdatesPending").fadeIn('slow');
		    $("#svcIsTrial").fadeOut('fast');
		} else {
		    $("#svcUpdatesPending").fadeOut('fast');
		    $("#svcIsTrial").fadeIn('slow');
		}
	};
	
	var configure_mobidick = function () {
		mctracker.call({
			url: '/mobi/rest/service/configure_mobidick',
			type: 'POST',
			data: {
				data: JSON.stringify({})
			},	
			success: function  (data, textStatus, XMLHttpRequest) {
				window.location = "/";
			},
			error: function (data, textStatus, XMLHttpRequest) { 
				mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
			}
		});

	};
	
	var loadScreen = function () {
		mctracker.call({
			url: '/mobi/rest/service/get_configuration',
			type: 'GET',
			success: function  (data, textStatus, XMLHttpRequest) {
				if (data) {
					configuration2Screen(data);
				} else {
					lj("#user", "dc").text(loggedOnUserEmail);
					lj("#convertAccountToServiceDialog", "d").dialog('open');
				}
			},
			error: function (data, textStatus, XMLHttpRequest) { 
				mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
			}
		});
		loadAdmins();
	};
	
	var loadAdmins = function () {
		mctracker.call({
			url: '/mobi/rest/service/grants',
			type: 'GET',
			success: function  (data, textStatus, XMLHttpRequest) {
			    var admins = [];
			    $.each(data, function (i, grant){
			       if (grant.role_type == "admin") {
			           admins.push(grant);
			       } 
			    });
				var templ = "{{each admins}}<li>${$value.user_name} &lt;${$value.user_email}&gt; (${$value.role}) <a class=\"action-link\" admin_email=\"${$value.user_email}\" admin_role=\"${$value.role}\" service_identity=\"${$value.identity}\">revoke</a></li>{{/each}}";
				$("a", lj("#serviceAdministrators").empty().append($.tmpl(templ, {admins:admins}))).click(function () {
					var admin_email = $(this).attr("admin_email");
					var admin_role = $(this).attr("admin_role");
					var service_identity = $(this).attr("service_identity");
					mctracker.call({
						url: '/mobi/rest/service/admin/roles/revoke',
						type: 'POST',
						data: {
							data: JSON.stringify({
							    user_email: admin_email, 
							    role: admin_role, 
							    identity: service_identity
							})
						},
						success: function  (data, textStatus, XMLHttpRequest) {
						}
					});
				});
			}
		});
	};

    var publishPendingChanges = function() {
        mctracker.confirm("Are you sure you wish to publish the changes?", function() {
            mctracker.call({
                url : '/mobi/rest/service/publish_changes',
                type : 'POST',
                data : {
                    data : JSON.stringify({})
                },
                success : function(data, textStatus, XMLHttpRequest) {
                    $("#svcUpdatesPending").fadeOut('fast');
                    $("#svcIsTrial").fadeIn('slow');
                },
                error : mctracker.showAjaxError
            });
        });
    };

	var processMessage = function (data) {
		if (data.type == 'rogerthat.service.testCallSucceeded') {
			lj("#testConfiguration").attr('disabled', true).fadeTo('slow', 0.6);
			alert('Test callback round trip succeeded !');
			window.location = "/";
		} else if (data.type == 'rogerthat.service.interactive_logs') {
			var textarea = lj("#logWindow", "dc");			
			textarea.val(textarea.val()+"Status: "+ data.status +"\nContent-type: "+ data.content_type +"\nResult url: "+ data.result_url +"\n\n"+ data.body);
		} else if (data.type == 'rogerthat.service.adminsChanged') {
			loadAdmins();
		} else if (data.type == 'rogerthat.service.updatesPendingChanged') {
		    if (data.updatesPending) {
		        $("#svcUpdatesPending").fadeIn('slow');
		        $("#svcIsTrial").fadeOut('fast');
		    } else {
		        $("#svcUpdatesPending").fadeOut('fast');
		        $("#svcIsTrial").fadeIn('slow');
		    }
		}
	};
	
	return function () {
		mctracker.registerMsgCallback(processMessage);
		mctracker.setOnLoadContainer(function (container) {
			if (container == container_name)
				loadScreen();
		});
		
		applyJQueryInUI();
	};
};

mctracker.registerLoadCallback("servicePanelContainer", serviceScript());