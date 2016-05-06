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

var friendsScript = function () {
	var container = "#friendsContainer";
	var lj = mctracker.getLocaljQuery(container);
	var friends = null;
	var otherFriendzz = null;
	var canShareLocation = null;
        
	var template = [
	    '<div class="span-18 last mcfriendbox">',
        '    <div class="span-4 info mark">',
        '        <div class="span-4 last mccenter">',
        '            <div name="friendAvatar"></div>',
        '        </div>',
        '        <div class="span-4 last mccenter ellipsis  name">',
        '            ${friend.name}',
        '        </div>',
        '        <br />',
        '        <div class="span-4 last mccenter ellipsis mail">',
        '            ${friend.email}',
        '        </div>',   
        '         <div class="span-4 last mccenter remove">',
        '            <a name="breakFriendShip" class="action-link">unfriend</a>',
        '        </div>',
        '        <br/>',
        '        {{if friend.type == 1}}', // friend is user not service
        '        <div class="actions">',
        '          <div class="span-13 last">',
        '            {{if friend.sharesLocation}}',
        '                <div style="margin-right: 10px;">Shares location with me</div>',
        '            {{else}}',
        '                <a name="inviteLocationSharing" class="action-link">Request location sharing</a>',
        '            {{/if}}',
        '          </div>',
        '          {{if canShareLocation}}',
        '          <label class="sp">|</label>',
        '          <div class="span-13 last">',
        '            <label for="chkCanSeeMyLocation${friend.name}">Can see my location</label>',
        '            <input type="checkbox" name="canSeeMyLocation" id="chkCanSeeMyLocation${friend.name}" {{if friend.shareLocation}}CHECKED{{/if}} />',
        '          </div>',
        '          {{/if}}',
        '        </div>',
        '        {{/if}}',
        '    </div>',
        '    {{if friend.type == 1}}',
        '    <div class="span-13 info last info">',
        '        <div class="span-13 last info">',
        '            <div class="span-13 last info">',
        '                  {{if friend.name}}${friend.name}{{else}}${friend.email}{{/if}} common friends :',
        '            </div>',
        '            <div class="span-13 last avt">',
        '                {{each commonFriends}}<div name="friendFriendAvatar" friend="${$value.email}"></div>{{/each}}',
        '            </div>',
        '        </div>',
        '        <div class="span-13 last info">',
        '            <div class="span-13 last info">',
        '                Other friends of {{if friend.name}}${friend.name}{{else}}${friend.email}{{/if}} :',
        '            </div>',
        '            <div class="span-13 last avt">',
        '                {{each otherFriends}}<div name="otherFriendAvatar" friend="${$value.email}"></div>{{/each}}',
        '            </div>',
        '        </div>',
        '        <br />',
        '    </div>',
        '    {{/if}}',
        '</div>'].join('');
	
	var fof_tooltip_template = [
	    '<div><span style="background-color: #fff">',
	    '    <span style="font-weight: bold;">Click to invite ${of.name}<br>${of.name} is also friends with:<br></span>',
	    '    <table style="width: 300px; background-color: #000; color: #fff;">',
	    '    {{each friends}}<tr><td><div friend="${$value.friend.email}"></div></td><td>${$value.friend.name}</td></tr>{{/each}}',
	    '</table></span></div>'].join('');
	
	var applyJQueryInUI = function () {
		lj("#inviteLocationSharing").dialog({
			autoOpen: false,
			modal: true,
			dragable: false,
			resizable: false,
			title: 'Invite location sharing friend',
			width: 430,
			buttons: {
				'Cancel': function () {
					lj("#inviteLocationSharing", "d").dialog('close');
				},
				'Invite': function () {
					var friend = lj("#inviteLocationSharing", "d").data("friend");
					var inviteText = lj("#friendShareLocationInviteText", "dc").val();
					mctracker.call({
						type: "POST",
						url: "/mobi/rest/friends/requestLocationSharing",
						data: {
							data: JSON.stringify({
								friend: friend.friend.email,
								message: inviteText
							})
						},
						success: function  (data, textStatus, XMLHttpRequest) {
							lj("#inviteLocationSharing", "d").dialog('close');
							var name = friendName(friend);
							$.gritter.add({
								title: 'Location sharing request',
								image: '/unauthenticated/mobi/cached/avatar/'+friend.friend.avatarId,
								text: 'Request was sent successfully to ' + name
							});
						},
						error: function (data, textStatus, XMLHttpRequest) { 
							alert("Invitation failed.\nPlease refresh your browser and try again.");
						}
					});
				}
			}
		}).attr('dialog', container);
		lj("#removeFriendDialog").dialog({
			autoOpen: false,
			modal: true,
			dragable: false,
			resizable: false,
			title: 'Remove friend from friendslist',
			buttons: {
				'Yes': function () {
					var friend = lj("#removeFriendDialog", "d").data("friend");
					removeFriend(friend);
					lj("#removeFriendDialog", "d").dialog('close');
				},
				'No': function () {
					lj("#removeFriendDialog", "d").dialog('close');
				}
			}
		}).attr('dialog', container);
		lj("#chkMyFriendsCanSeeMyRelations").change(setShareContacts);
	};
	
	var loadScreen = function() {
		mctracker.call({
			url: "/mobi/rest/friends/get_full",
			success: function (data, textStatus, XMLHttpRequest) {
				friends = data.friends;
				if (friends.length == 0) {
					mctracker.confirm("You don't seem to have any Rogerthat friends. Add your friends to Rogerthat via the 'Add friends' panel.", function () {
						mctracker.loadContainer("addfriendsContainer", "/static/parts/addfriends.html");
					});
				}
				canShareLocation = data.canShareLocation;
				// Set chkMyFriendsCanSeeMyRelations
				lj("#chkMyFriendsCanSeeMyRelations").prop("checked", data.shareContacts);
				friends = friends.sort(function (l,r) { 
					var ln = getFriendName(l.friend).toLowerCase(); 
					var rn = getFriendName(r.friend).toLowerCase(); 
					if (ln == rn) 
						return 0; 
					else 
						return ln < rn ? -1 : 1;
					});
				// Render the friends
				otherFriendzz = {};
				for (var i in friends) {
					var friend = friends[i];
					analyzeFriends(friend);
					$.each(friend.otherFriends, function (i, of) {
						if (! otherFriendzz[of.email])
							otherFriendzz[of.email] = {of:of, friends: []};
						otherFriendzz[of.email].friends.push(friend);
					});
					lj("#fcfriends").append(renderFriend(friend));
				}
				// Render friendsOfFriends
				otherFriendzz = $.map(otherFriendzz, function (fof, i) {
					return fof;
				});
				otherFriendzz = otherFriendzz.sort(function (l,r) {
					if ( l.length == r.length )
						return 0;
					else
						return l.length < r.length ? -1 : 1;
				});
				var fof = lj("#fof").empty();
				$.each(otherFriendzz, function (i, of) {
					var tooltip = $.tmpl(fof_tooltip_template, of);
					$("div", tooltip).each(function () {
						var div = $(this);
						div.avatar({
							friend: getFriendByEmail(div.attr('friend')),
							resize: true
						});
					});
					fof.append($('<div></div>').avatar({
						friend: of.of,
						resize: false,
						click: function() {inviteFriend(of.of.email, of.of.name)},
						tooltip: tooltip.html(),
						speed: 0
					}));
				});
			},
			error: mctracker.showAjaxError
		});
	};
	
	var analyzeFriends = function (friend) {
		var commonFriends = [];
		var otherFriends = [];
		for (var j in friend.friends) {
			var friend_friend = friend.friends[j];
			if (isFriend(friend_friend.email)) {
				commonFriends.push(friend_friend);
			} else {
				if (friend_friend.email != loggedOnUserEmail) {
					otherFriends.push(friend_friend);
				}
			}
		}
		friend.commonFriends = commonFriends;
		friend.otherFriends = otherFriends;
	}
	
	var setShareContacts = function () {
		var enabled = lj("#chkMyFriendsCanSeeMyRelations").prop("checked");
		mctracker.call({
			url: '/mobi/rest/friends/setShareContacts',
			type: 'POST',
			data: {
				data: JSON.stringify({
					enabled: enabled
				})
			},
			success: function  (data, textStatus, XMLHttpRequest) {
				$.gritter.add({
					title: 'Friends',
					text: enabled ? "Your friends can now see your entire friend list" : "Your friends can no longer see your friend list"
				});

			},
			error: function (data, textStatus, XMLHttpRequest) { 
				mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
			}
		});
	};
	
	var renderFriend = function(friend) {
		var getFriendFriend = function (thizz) {
			var email = thizz.attr('friend'); 
			if (! email) 
				return;
			var friendFriend = null;
			for (var i in friend.friends) {
				if (friend.friends[i].email == email) {
					friendFriend = friend.friends[i];
					break;
				}
			}
			return friendFriend;
		};
		friend.canShareLocation = canShareLocation;
		var friendHtml = $.tmpl(template, friend);
		friendHtml.attr("friend", friend.friend.email);
		jQuery("*", friendHtml).data("friend", friend);
		jQuery("input[name='canSeeMyLocation']", friendHtml).change(changeShareLocation);
		jQuery("a[name='inviteLocationSharing']", friendHtml).click(requestShareLocation);
		jQuery("a[name='breakFriendShip']", friendHtml).click(openRemoveFriendDialog);
		jQuery("div[name='friendAvatar']", friendHtml).append(renderAvatar(friend.friend, true, friendName(friend), undefined, true));
		jQuery("div[name='friendFriendAvatar']", friendHtml).each(function (index) {
			var thizz = $(this);
			var f = getFriendFriend(thizz);
			thizz.replaceWith(renderAvatar(f, true, friendName({friend:f}), true, true));
		});
		jQuery("div[name='otherFriendAvatar']", friendHtml).each(function (index) {
			var thizz = $(this);
			var f = getFriendFriend(thizz);
			thizz.replaceWith(renderAvatar(f, false, friendName({friend:f}), true, true));
		});
		return friendHtml;
	};
	
	var isFriend = function(email) {
		for (var i=0; i<friends.length; i++) {
			if (friends[i].friend.email == email)
				return true;
		}
		return false;
	};
	
	var getFriend = function(email) {
		for (var i=0; i<friends.length; i++) {
			if (friends[i].friend.email == email)
				return friends[i];
		}
		return false;
	};
	
	var getFriendDocument = function(email) {
		return lj("div[friend='"+email+"']");
	};
	
	var removeFriendDocument = function(email) {
		getFriendDocument(email).fadeOut('slow', function () {
			$(this).detach();
		});
		$("img[friend='"+email+"']", $("#friends")).fadeOut('slow', function () {
			$(this).detach();
		});
	};
	
	var friendName = function(friend) {
		return friend.friend.name ? friend.friend.name : friend.friend.email;
	};
	
	var requestShareLocation = function(evt) {
		var a = $(evt.target);
		var friend = a.data("friend");
		lj("#inviteLocationSharing", "d").data("friend", friend);
		lj("#inviteLocationSharing", "d").dialog('option', 'title', 'Invite ' + friendName(friend) + ' to share his/her location.');
		lj("#inviteLocationSharing", "d").dialog('open');
	};
	
	var openRemoveFriendDialog = function(evt) {
		var a = $(evt.target);
		var friend = a.data("friend");
		lj("#friendToRemove", "dc").text(friendName(friend));
		lj("#removeFriendDialog", "d").data("friend", friend);
		lj("#removeFriendDialog", "d").dialog('open');
	};
	
	var removeFriend = function(friend) {
		var name = friendName(friend);
		mctracker.call({
			url: "/mobi/rest/friends/break",
			type: "post",
			data: {
				data: JSON.stringify({
					friend: friend.friend.email
				})
			},
			success: function  (data, textStatus, XMLHttpRequest) {
				removeFriendDocument(friend.friend.email);
			},
			error: function (data, textStatus, XMLHttpRequest) { 
				mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
			}
		});
	};
	
	var changeShareLocation = function(evt) {
		var input = $(evt.target);
		var friend = input.data("friend");
		var enabled = input.prop('checked');
		mctracker.call({
			url: "/mobi/rest/friends/shareLocation",
			type: 'post',
			data: {
				data: JSON.stringify({
					friend: friend.friend.email,
					enabled: enabled
				})
			},
			success: function  (data, textStatus, XMLHttpRequest) {
				friend.shareLastLocation = enabled;
				var name = friendName(friend);
				$.gritter.add({
					title: 'Location sharing',
					image: '/unauthenticated/mobi/cached/avatar/'+friend.friend.avatarId,
					text: enabled ? name + ' can now track your location ' : name + ' can no longer track your location'
				});
			},
			error: function (data, textStatus, XMLHttpRequest) { 
				mctracker.showAjaxError(XMLHttpRequest, textStatus, data);
			}
		});
	};
	
	var processMessage = function (data) {
		if (data.type == 'rogerthat.friend.shareLocation' 
			|| data.type == 'rogerthat.friend.ackRequestLocationSharing'
			|| data.type == 'rogerthat.friend.shareLocationUpdate'
			|| data.type == 'rogerthat.friend.ackRequestLocationSharingUpdate') {
			var friend = getFriend(data.friend.email);
			friend.friend = data.friend;
			var currentFriendHTML = lj("div.mcfriendbox[friend='"+data.friend.email+"']");
			var newFriendHTML = renderFriend(friend);
			newFriendHTML.insertAfter(currentFriendHTML);
			currentFriendHTML.detach();
		} else if (data.type == 'rogerthat.friend.breakFriendShip') {
		    if (data.friend.type == 1)
		        removeFriendDocument(data.friend.email);
		} else if (data.type == 'rogerthat.friend.ackInvitation') {
			if (data.friend.type == 1) {
				friends.push(data);
				analyzeFriends(data);
				lj("#friends").append(renderFriend(data));
			}
		}
	};
	
	return function () {
		mctracker.registerMsgCallback(processMessage);
		
		applyJQueryInUI();
		
		loadScreen();
	};
}

mctracker.registerLoadCallback("friendsContainer", friendsScript());