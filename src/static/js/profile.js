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

var profileScript = function () {
	var container = "#profileContainer";
	var lj = mctracker.getLocaljQuery(container);
	var avatar_selection = null;
	var avatar_tmp_key = null;
	var avatar_scale_factor_x = null;
	var avatar_scale_factor_y = null;
	var cleaning_up = false;
	var avatar_dialog = null;
	var isService = false;
	
	var applyJQueryInUI = function () {
	    lj("#avatar").attr('src', "/mobi/profile/my_avatar?user="+encodeURIComponent(loggedOnUserEmail));
		lj("button.save_button").button().click(save);
		lj("#change_pwd").button().click(function () {
			window.location = "/resetpassword?email=" + loggedOnUserEmail;
		});
		lj("#newAvatar").change(uploadAvatar);
		avatar_dialog = lj("#createAvatarDialog").dialog({
			draggable: false,
			autoOpen: false,
			title: "Create profile picture",
			width: 400,
			height: 420,
			modal: true, 
			buttons: {
				'Ok': acceptAvatar,
				'Cancel': rejectAvatar
			},
			open: function (event, ui) {
				lj("#newAvatar", "dc").val("");
				lj("#avatarUpload", "dc").show();
				lj("#avatarSelectionArea", "dc").imgAreaSelect({
					aspectRatio: '1:1',
					onSelectChange: preview,
					onSelectEnd: select,
					handles: true,
		            minWidth: 50,
		            minHeight: 50,
		            persistent: true
				}).hide();
			},
			close: cleanUpImgAreaSelect,
			position: { my: "center top", at: "center top", of: window}
		}).attr('dialog', container);
		lj("#avatar_div").click(function () {
			lj("#createAvatarDialog", "d").dialog("open");
		});
        lj("#email").text(loggedOnUserEmail);
	};

	var save = function () {
	    var name = null;
	    var language = null;
	    if (!isService) {
            name = trim(lj("#name").val());
            if (! name || name.search(/@/) != -1  || name.length > 50) {
                lj("#nameErrorMsg").show();
                return;
            }
            lj("#nameErrorMsg").hide();
            language = lj("#language").val();
        }

		var x1 = 0;
		var y1 = 0;
		var x2 = 0;
		var y2 = 0;
		if (avatar_selection && avatar_tmp_key) {
			x1 = avatar_selection.x1 / avatar_scale_factor_x;
			x2 = avatar_selection.x2 / avatar_scale_factor_x;
			y1 = avatar_selection.y1 / avatar_scale_factor_y;
			y2 = avatar_selection.y2 / avatar_scale_factor_y;
		};
		
		mctracker.call({
			url: "/mobi/rest/profile/update",
			data: { 
				data: JSON.stringify({
					name: name,
					language: language,
					tmp_avatar_key: avatar_tmp_key,
					x1: x1,
					y1: y1,
					x2: x2,
					y2: y2
				})
			},
			type: 'POST',
			success: function (data, textStatus, XMLHttpRequest) {
				if (! data)
					window.location = "/";
				else
					mctracker.alert("Could not persist your profile.\nRefresh the page and try again.\nError: "+data);
			},
			error: function(XMLHttpRequest, textStatus, errorThrown) {
			    mctracker.alert("Could not persist your profile.\nRefresh the page and try again.\nError: "+errorThrown);
			}
		});
	};
	
	var cleanUpImgAreaSelect = function () {
		cleaning_up = true;
		lj("#avatarSelectionArea", "dc").imgAreaSelect({
			remove: true,
			onSelectChange: null,
			onSelectEnd:null
		});
		cleaning_up = false;
	};
	
	var acceptAvatar = function () {
		if ( avatar_selection == null ) {
			lj("#errormessage", "dc").text("No avatar selection made!").show();
		} else {
			lj("#createAvatarDialog", "d").dialog('close');
		}
	};
	
	var rejectAvatar = function () {
		avatar_selection = null;
		lj("#avatar_div").empty();
		lj("#avatar_div").append($('<img id="avatar" style="position: relative" class="avatar" src="/mobi/profile/my_avatar?user='+encodeURIComponent(loggedOnUserEmail)+'"/>'));
		lj("#createAvatarDialog", "d").dialog('close');
	};
	
	var uploadAvatar = function () {
		if (! lj("#newAvatar", "dc").val())
			return;
		mctracker.showProcessing();
		lj("#uploadForm", "dc").submit();
	};
	
	var loadProfile = function () {
		mctracker.call({
			url: "/mobi/rest/profile/get",
			success: function (data, textStatus, XMLHttpRequest) {
				if (data) {
				    isService = data.isService;
					if (isService) {
						lj(".human_users_only").hide();
                        lj(".service_users_only").show();
                        lj("#organization_type").val(data.organizationType);
					} else {
                        lj(".service_users_only").hide();
                        lj(".human_users_only").show();
					    lj("#name").val(data.name).focus();
						lj("#passport").attr('src', '/invite?code='+data.userCode).parent().attr('href', '/q/i'+data.userCode);
						
						var language = data.userLanguage ? data.userLanguage : 'en';
						
						var select = lj("#language");
				        for (var i = 0; i < data.allLanguages.length; i++) {
				            var short_lang = data.allLanguages[i];
				            var long_lang = data.allLanguagesStr[i];
				            select.append($('<option></option>').attr('value', short_lang).text(long_lang));
				        }
				        $("option[value='"+language+"']", select).attr('selected', '');
					}
				}
			},
			error: mctracker.showAjaxError		
		});
	};
	
	var preview = function (img, selection) {
		if (cleaning_up)
			return;
		lj("#errormessage", "dc").hide();
		var scale = 50 / (selection.width || 1); 
		
		lj('#avatar').css({ 
			width: Math.round(scale * img.width) + 'px', 
			height: Math.round(scale * img.height) + 'px', 
			marginLeft: '-' + Math.round(scale * selection.x1) + 'px', 
			marginTop: '-' + Math.round(scale * selection.y1) + 'px' 
		}); 
	};
	
	var select = function (img, selection) {
		if (cleaning_up)
			return;
		avatar_selection = selection;
		avatar_scale_factor_x = img.width;
		avatar_scale_factor_y = img.height;
	};
	
	var processMessage = function (data) {
		if ( data.type == "rogerthat.profile.avatar_uploaded" ) {
			avatar_tmp_key = data.key;
			lj("#avatarUpload", "dc").hide();
			var url = "/mobi/profile/tmp_avatar?key=" + encodeURIComponent(data.key);
			var addInitialSelection = function () {
				var img = $(this);
				img.show();
				
                img.css('min-width', 'none').css('min-height', 'none');
                var height = img.height();
                var width = img.width();
                var scale_height = 250 / height;
                var scale_width = 500 / width;
                if (scale_height > 1 && scale_width > 1) {
                    if (scale_height < scale_width) {
                        img.css('min-height', '250px');
                    } else {
                        img.css('min-width', '500px');
                    }
                    height = img.height();
                    width = img.width();
                }
                var size = (height < width ? height : width) / 2;
                var start = size / 2;
                var end = start + size;
				
                avatar_dialog.dialog('option', 'width', 530);
                avatar_dialog.dialog('option', 'height', 420+img.height()-210);

                var imgAreaSelect = img.imgAreaSelect({ instance: true });
				imgAreaSelect.setSelection(50, 50, 150, 150, true);
				imgAreaSelect.setOptions({ show: true });
				imgAreaSelect.update();
				var selection = {
					x1: 50,
					y1: 50,
					x2: 150,
					y2: 150,
					height: 100,
					width: 100
				};
				select(this, selection);
				preview(this, selection);
			};
			lj("#avatarSelectionArea", "dc").attr("src", url).load(addInitialSelection);
			lj("#avatar").attr("src", url);
            mctracker.hideProcessing();
		} else if ( data.type == "rogerthat.profile.avatar_upload_failed" ) {
		    mctracker.alert("The upload of your message failed for the following reason:\n\n"+data.error);
            mctracker.hideProcessing();
		}
	};
	
	return function () {
		mctracker.registerMsgCallback(processMessage);
		
		applyJQueryInUI();
		
		loadProfile();
	};
}

mctracker.registerLoadCallback("profileContainer", profileScript());