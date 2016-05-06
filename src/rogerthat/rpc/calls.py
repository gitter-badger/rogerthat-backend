# -*- coding: utf-8 -*-  # Copyright 2016 Mobicage NV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @@license_version:1.1@@

from collections import defaultdict

from rogerthat.api import messaging
from rogerthat.api.activity import logCall, logLocations
from rogerthat.api.friends import getFriendsList, shareLocation, breakFriendship, requestLocationSharing, invite, \
    getAvatar, getUserInfo, getFriendInvitationSecrets, ackInvitationByInvitationSecret, logInvitationSecretSent, \
    findRogerthatUsersViaEmail, findRogerthatUsersViaFacebook, getCategory, getFriendEmails, getFriend, getGroups, \
    getGroupAvatar, putGroup, deleteGroup, findFriend, userScanned
from rogerthat.api.location import get_friend_location, get_friend_locations, beacon_discovered, beacon_in_reach, \
    beacon_out_of_reach, getBeaconRegions
from rogerthat.api.messaging import jsmfr
from rogerthat.api.services import getActionInfo, startAction, getMenuIcon, pressMenuItem, shareService, findService, \
    pokeService, getStaticFlow, sendApiCall, updateUserData
from rogerthat.api.system import logError as logClientError, saveSettings, heartBeat, getIdentity, \
    updateApplePushDeviceToken, unregisterMobile as unregisterMobile_api, getIdentityQRCode, setMobilePhoneNumber, \
    editProfile, getJsEmbedding
from rogerthat.bizz.beacon import update_beacon_regions_response
from rogerthat.bizz.branding import brandings_updated_response_handler
from rogerthat.bizz.friends import update_friend_response, invite_result_response_receiver, \
    broke_friendship_response_receiver, invited_response_receiver, became_friends_response, in_reach_response_receiver, \
    out_of_reach_response_receiver, update_friend_set_response, update_groups_response, is_in_roles_response_receiver, \
    register_result_response_receiver
from rogerthat.bizz.job.update_friends import friend_update_response_receiver
from rogerthat.bizz.js_embedding.mapping import update_jsembedding_response
from rogerthat.bizz.location import get_location_response_handler, get_location_result_response_handler, \
    get_location_response_error_handler, delete_beacon_discovery_response, \
    location_fix_response_receiver, track_location_response_handler, track_location_response_error_handler
from rogerthat.bizz.messaging import new_message_response_handler, message_locked_response_handler, \
    message_member_response_handler, message_service_form_update_response_handler, form_updated_response_handler, \
    message_service_received_update_response_handler, message_service_acknowledged_update_response_handler, \
    message_service_flow_member_result_response_handler, conversation_deleted_response_handler, \
    transfer_completed_response_handler, \
    new_chat_message_response_handler, update_message_response_handler, chat_deleted_response_handler
from rogerthat.bizz.service import test_callback_response_receiver, poke_service_callback_response_receiver, \
    receive_api_call_result_response_handler, send_api_call_response_receiver, update_user_data_response_handler
from rogerthat.bizz.service.mfr import start_flow_response_handler
from rogerthat.bizz.system import unregister_mobile_success_callback, update_settings_response_handler, \
    update_available_response_handler, identity_update_response_handler, forward_logs_response_handler, \
    system_service_deleted_response_handler
from rogerthat.capi.friends import updateFriend, becameFriends, updateFriendSet, updateGroups
from rogerthat.capi.location import getLocation, locationResult, deleteBeaconDiscovery, updateBeaconRegions, \
    trackLocation
from rogerthat.capi.messaging import newMessage, updateMessageMemberStatus, messageLocked, newTextLineForm, \
    newAutoCompleteForm, newTextBlockForm, newSingleSelectForm, newMultiSelectForm, newRangeSliderForm, \
    newSingleSliderForm, \
    updateTextLineForm, updateTextBlockForm, updateAutoCompleteForm, updateSingleSelectForm, updateMultiSelectForm, \
    updateSingleSliderForm, updateRangeSliderForm, newDateSelectForm, updateDateSelectForm, conversationDeleted, \
    endMessageFlow, newPhotoUploadForm, updatePhotoUploadForm, transferCompleted, newGPSLocationForm, \
    updateGPSLocationForm, \
    startFlow, updateMessage, updateMyDigiPassForm, newMyDigiPassForm, newAdvancedOrderForm, updateAdvancedOrderForm
from rogerthat.capi.services import receiveApiCallResult, updateUserData as capi_updateUserData
from rogerthat.capi.system import unregisterMobile as unregisterMobile_capi, updateSettings, updateAvailable, \
    identityUpdate, forwardLogs, updateJsEmbedding
from rogerthat.rpc.rpc import logError, dismissError
from rogerthat.rpc.service import logServiceError
from rogerthat.service.api.friends import broke_friendship, invited, invite_result, in_reach, out_of_reach, \
    is_in_roles, update, location_fix, register, register_result
from rogerthat.service.api.messaging import poke, flow_member_result, received, acknowledged, form_acknowledged, \
    new_chat_message, chat_deleted
from rogerthat.service.api.system import api_call, service_deleted, brandings_updated
from rogerthat.service.api.test import test

mapping = {
    u'com.mobicage.api.activity.logCall': logCall,
    u'com.mobicage.api.activity.logLocations': logLocations,
    u'com.mobicage.api.location.getFriendLocation': get_friend_location,
    u'com.mobicage.api.location.getFriendLocations': get_friend_locations,
    u'com.mobicage.api.location.beaconDiscovered': beacon_discovered,
    u'com.mobicage.api.location.beaconInReach': beacon_in_reach,
    u'com.mobicage.api.location.beaconOutOfReach': beacon_out_of_reach,
    u'com.mobicage.api.location.getBeaconRegions': getBeaconRegions,
    u'com.mobicage.api.friends.getFriends': getFriendsList,
    u'com.mobicage.api.friends.getFriendEmails': getFriendEmails,
    u'com.mobicage.api.friends.getFriend': getFriend,
    u'com.mobicage.api.friends.shareLocation': shareLocation,
    u'com.mobicage.api.friends.requestShareLocation': requestLocationSharing,
    u'com.mobicage.api.friends.breakFriendShip': breakFriendship,
    u'com.mobicage.api.friends.invite': invite,
    u'com.mobicage.api.friends.getAvatar': getAvatar,
    u'com.mobicage.api.friends.getUserInfo': getUserInfo,
    u'com.mobicage.api.friends.getFriendInvitationSecrets': getFriendInvitationSecrets,
    u'com.mobicage.api.friends.ackInvitationByInvitationSecret': ackInvitationByInvitationSecret,
    u'com.mobicage.api.friends.logInvitationSecretSent': logInvitationSecretSent,
    u'com.mobicage.api.friends.findRogerthatUsersViaFacebook': findRogerthatUsersViaFacebook,
    u'com.mobicage.api.friends.findRogerthatUsersViaEmail': findRogerthatUsersViaEmail,
    u'com.mobicage.api.friends.getCategory': getCategory,
    u'com.mobicage.api.friends.getGroups': getGroups,
    u'com.mobicage.api.friends.getGroupAvatar': getGroupAvatar,
    u'com.mobicage.api.friends.putGroup': putGroup,
    u'com.mobicage.api.friends.deleteGroup': deleteGroup,
    u'com.mobicage.api.friends.findFriend': findFriend,
    u'com.mobicage.api.friends.userScanned': userScanned,
    u'com.mobicage.api.services.getMenuIcon': getMenuIcon,
    u'com.mobicage.api.services.getStaticFlow': getStaticFlow,
    u'com.mobicage.api.services.pressMenuItem': pressMenuItem,
    u'com.mobicage.api.services.getActionInfo': getActionInfo,
    u'com.mobicage.api.services.shareService': shareService,
    u'com.mobicage.api.services.findService': findService,
    u'com.mobicage.api.services.pokeService': pokeService,
    u'com.mobicage.api.services.startAction': startAction,
    u'com.mobicage.api.services.sendApiCall': sendApiCall,
    u'com.mobicage.api.services.updateUserData': updateUserData,
    u'com.mobicage.api.system.saveSettings': saveSettings,
    u'com.mobicage.api.system.unregisterMobile': unregisterMobile_api,
    u'com.mobicage.api.system.heartBeat': heartBeat,
    u'com.mobicage.api.system.logError': logClientError,
    u'com.mobicage.api.system.getIdentity': getIdentity,
    u'com.mobicage.api.system.getIdentityQRCode': getIdentityQRCode,
    u'com.mobicage.api.system.setMobilePhoneNumber': setMobilePhoneNumber,
    u'com.mobicage.api.system.editProfile': editProfile,
    u'com.mobicage.api.system.updateApplePushDeviceToken': updateApplePushDeviceToken,
    u'com.mobicage.api.system.getJsEmbedding': getJsEmbedding,
    u'com.mobicage.api.messaging.sendMessage': messaging.sendMessage,
    u'com.mobicage.api.messaging.ackMessage': messaging.ackMessage,
    u'com.mobicage.api.messaging.lockMessage': messaging.lockMessage,
    u'com.mobicage.api.messaging.deleteConversation': messaging.deleteConversation,
    u'com.mobicage.api.messaging.getConversation': messaging.getConversation,
    u'com.mobicage.api.messaging.getConversationAvatar': messaging.getConversationAvatar,
    u'com.mobicage.api.messaging.markMessagesAsRead': messaging.markMessagesAsRead,
    u'com.mobicage.api.messaging.submitTextLineForm': messaging.submitTextLineForm,
    u'com.mobicage.api.messaging.submitTextBlockForm': messaging.submitTextBlockForm,
    u'com.mobicage.api.messaging.submitAutoCompleteForm': messaging.submitAutoCompleteForm,
    u'com.mobicage.api.messaging.submitSingleSelectForm': messaging.submitSingleSelectForm,
    u'com.mobicage.api.messaging.submitMultiSelectForm': messaging.submitMultiSelectForm,
    u'com.mobicage.api.messaging.submitDateSelectForm': messaging.submitDateSelectForm,
    u'com.mobicage.api.messaging.submitSingleSliderForm': messaging.submitSingleSliderForm,
    u'com.mobicage.api.messaging.submitRangeSliderForm': messaging.submitRangeSliderForm,
    u'com.mobicage.api.messaging.uploadChunk': messaging.uploadChunk,
    u'com.mobicage.api.messaging.submitPhotoUploadForm': messaging.submitPhotoUploadForm,
    u'com.mobicage.api.messaging.submitGPSLocationForm': messaging.submitGPSLocationForm,
    u'com.mobicage.api.messaging.submitMyDigiPassForm': messaging.submitMyDigiPassForm,
    u'com.mobicage.api.messaging.submitAdvancedOrderForm': messaging.submitAdvancedOrderForm,
    u'com.mobicage.api.messaging.jsmfr.flowStarted': jsmfr.flowStarted,
    u'com.mobicage.api.messaging.jsmfr.newFlowMessage': jsmfr.newFlowMessage,
    u'com.mobicage.api.messaging.jsmfr.messageFlowMemberResult': jsmfr.messageFlowMemberResult,
    u'com.mobicage.api.messaging.jsmfr.messageFlowFinished': jsmfr.messageFlowFinished,
    u'com.mobicage.api.messaging.jsmfr.messageFlowError': jsmfr.messageFlowError,
}

LOW_PRIORITY = 0
NORMAL_PRIORITY = 5
HIGH_PRIORITY = 10

capi_priority_mapping = defaultdict(lambda: NORMAL_PRIORITY)
capi_priority_mapping.update({u'com.mobicage.capi.system.forwardLogs': HIGH_PRIORITY})

client_mapping = {
    u'com.mobicage.capi.friends.updateFriend': updateFriend,
    u'com.mobicage.capi.friends.updateFriendSet': updateFriendSet,
    u'com.mobicage.capi.friends.becameFriends': becameFriends,
    u'com.mobicage.capi.friends.updateGroups': updateGroups,
    u'com.mobicage.capi.system.identityUpdate': identityUpdate,
    u'com.mobicage.capi.system.forwardLogs': forwardLogs,
    u'com.mobicage.capi.system.updateSettings': updateSettings,
    u'com.mobicage.capi.system.unregisterMobile': unregisterMobile_capi,
    u'com.mobicage.capi.system.updateAvailable': updateAvailable,
    u'com.mobicage.capi.system.updateJsEmbedding': updateJsEmbedding,
    u'com.mobicage.capi.messaging.newMessage': newMessage,
    u'com.mobicage.capi.messaging.newTextLineForm': newTextLineForm,
    u'com.mobicage.capi.messaging.newTextBlockForm': newTextBlockForm,
    u'com.mobicage.capi.messaging.newAutoCompleteForm': newAutoCompleteForm,
    u'com.mobicage.capi.messaging.newSingleSelectForm': newSingleSelectForm,
    u'com.mobicage.capi.messaging.newMultiSelectForm': newMultiSelectForm,
    u'com.mobicage.capi.messaging.newDateSelectForm': newDateSelectForm,
    u'com.mobicage.capi.messaging.newSingleSliderForm': newSingleSliderForm,
    u'com.mobicage.capi.messaging.newRangeSliderForm': newRangeSliderForm,
    u'com.mobicage.capi.messaging.newPhotoUploadForm': newPhotoUploadForm,
    u'com.mobicage.capi.messaging.newGPSLocationForm': newGPSLocationForm,
    u'com.mobicage.capi.messaging.newMyDigiPassForm': newMyDigiPassForm,
    u'com.mobicage.capi.messaging.newAdvancedOrderForm': newAdvancedOrderForm,
    u'com.mobicage.capi.messaging.updateTextLineForm': updateTextLineForm,
    u'com.mobicage.capi.messaging.updateTextBlockForm': updateTextBlockForm,
    u'com.mobicage.capi.messaging.updateAutoCompleteForm': updateAutoCompleteForm,
    u'com.mobicage.capi.messaging.updateSingleSelectForm': updateSingleSelectForm,
    u'com.mobicage.capi.messaging.updateMultiSelectForm': updateMultiSelectForm,
    u'com.mobicage.capi.messaging.updateDateSelectForm': updateDateSelectForm,
    u'com.mobicage.capi.messaging.updateSingleSliderForm': updateSingleSliderForm,
    u'com.mobicage.capi.messaging.updateRangeSliderForm': updateRangeSliderForm,
    u'com.mobicage.capi.messaging.updatePhotoUploadForm': updatePhotoUploadForm,
    u'com.mobicage.capi.messaging.updateGPSLocationForm': updateGPSLocationForm,
    u'com.mobicage.capi.messaging.updateMyDigiPassForm': updateMyDigiPassForm,
    u'com.mobicage.capi.messaging.updateAdvancedOrderForm': updateAdvancedOrderForm,
    u'com.mobicage.capi.messaging.updateMessage': updateMessage,
    u'com.mobicage.capi.messaging.updateMessageMemberStatus': updateMessageMemberStatus,
    u'com.mobicage.capi.messaging.messageLocked': messageLocked,
    u'com.mobicage.capi.messaging.conversationDeleted': conversationDeleted,
    u'com.mobicage.capi.messaging.endMessageFlow': endMessageFlow,
    u'com.mobicage.capi.messaging.startFlow': startFlow,
    u'com.mobicage.capi.messaging.transferCompleted': transferCompleted,
    u'com.mobicage.capi.location.getLocation': getLocation,
    u'com.mobicage.capi.location.locationResult': locationResult,
    u'com.mobicage.capi.location.trackLocation': trackLocation,
    u'com.mobicage.capi.location.deleteBeaconDiscovery': deleteBeaconDiscovery,
    u'com.mobicage.capi.location.updateBeaconRegions': updateBeaconRegions,
    u'com.mobicage.capi.services.receiveApiCallResult': receiveApiCallResult,
    u'com.mobicage.capi.services.updateUserData': capi_updateUserData,
}

service_callback_mapping = {
    u'test.test': test,
    u'friend.invite_result': invite_result,
    u'friend.broke_up': broke_friendship,
    u'friend.invited': invited,
    u'friend.update': update,
    u'friend.in_reach': in_reach,
    u'friend.out_of_reach': out_of_reach,
    u'friend.is_in_roles': is_in_roles,
    u'friend.location_fix': location_fix,
    u'friend.register': register,
    u'friend.register_result': register_result,
    u'messaging.update': (received, acknowledged),
    u'messaging.form_update': form_acknowledged,
    u'messaging.poke': poke,
    u'messaging.flow_member_result': flow_member_result,
    u'messaging.new_chat_message': new_chat_message,
    u'messaging.chat_deleted': chat_deleted,
    u'system.api_call': api_call,
    u'system.brandings_updated': brandings_updated,
    u'system.service_deleted': service_deleted,
}

result_mapping = {
    u'com.mobicage.capi.system.unregisterMobileSuccessCallBack': unregister_mobile_success_callback,
    u'com.mobicage.capi.friends.update_friend_response': update_friend_response,
    u'com.mobicage.capi.friends.update_friend_set_response': update_friend_set_response,
    u'com.mobicage.capi.friends.became_friends_response': became_friends_response,
    u'com.mobicage.capi.friends.update_groups_response': update_groups_response,
    u'com.mobicage.rpc.error': logError,
    u'com.mobicage.rpc.dismiss_error': dismissError,
    u'com.mobicage.capi.message.new_message_response_handler': new_message_response_handler,
    u'com.mobicage.capi.message.update_message_response_handler': update_message_response_handler,
    u'com.mobicage.capi.message.form_updated_response_handler': form_updated_response_handler,
    u'com.mobicage.capi.message.message_member_status_update_response_handler': message_member_response_handler,
    u'com.mobicage.capi.message.message_locked_response_handler': message_locked_response_handler,
    u'com.mobicage.capi.message.conversation_deleted_response_handler': conversation_deleted_response_handler,
    u'com.mobicage.capi.message.transfer_completed_response_handler': transfer_completed_response_handler,
    u'com.mobicage.capi.message.start_flow_response_handler': start_flow_response_handler,
    u'com.mobicage.capi.services.receive_api_call_result_response_handler': receive_api_call_result_response_handler,
    u'com.mobicage.capi.services.update_user_data_response_handler': update_user_data_response_handler,
    u'com.mobicage.capi.system.updateSettingsResponseHandler': update_settings_response_handler,
    u'com.mobicage.capi.system.updateAvailableResponseHandler': update_available_response_handler,
    u'com.mobicage.capi.system.identityUpdateResponseHandler': identity_update_response_handler,
    u'com.mobicage.capi.system.forwardLogsResponseHandler': forward_logs_response_handler,
    u'com.mobicage.capi.system.update_jsembedding_response': update_jsembedding_response,
    u'com.mobicage.capi.location.get_location_response_handler': get_location_response_handler,
    u'com.mobicage.capi.location.get_location_result_response_handler': get_location_result_response_handler,
    u'com.mobicage.capi.location.get_location_response_error_handler': get_location_response_error_handler,
    u'com.mobicage.capi.location.track_location_response_handler': track_location_response_handler,
    u'com.mobicage.capi.location.track_location_response_error_handler': track_location_response_error_handler,
    u'com.mobicage.capi.location.deleteBeaconDiscovery_response': delete_beacon_discovery_response,
    u'com.mobicage.capi.location.update_beacon_regions_response': update_beacon_regions_response,
}

service_callback_result_mapping = {
    u'test_api_callback_response_handler': test_callback_response_receiver,
    u'friend.invite_result.response_receiver': invite_result_response_receiver,
    u'friend.broke_up.response_receiver': broke_friendship_response_receiver,
    u'friend.invited.response_receiver': invited_response_receiver,
    u'friend.update.response_receiver': friend_update_response_receiver,
    u'friend.in_reach.response_receiver': in_reach_response_receiver,
    u'friend.out_of_reach.response_receiver': out_of_reach_response_receiver,
    u'friend.is_in_roles.response_receiver': is_in_roles_response_receiver,
    u'friend.location_fix.response_receiver': location_fix_response_receiver,
    u'friend.register_result.response_receiver': register_result_response_receiver,
    u'message.received.response_handler': message_service_received_update_response_handler,
    u'message.acknowledged.response_handler': message_service_acknowledged_update_response_handler,
    u'message.new_chat_message.response_handler': new_chat_message_response_handler,
    u'message.chat_deleted.response_handler': chat_deleted_response_handler,
    u'message.form_update.response_handler': message_service_form_update_response_handler,
    u'message.flow_member_result.response_handler': message_service_flow_member_result_response_handler,
    u'message.poke.response_handler': poke_service_callback_response_receiver,
    u'system.api_call.response_handler': send_api_call_response_receiver,
    u'system.brandings_updated.response_handler': brandings_updated_response_handler,
    u'system.service_deleted.response_handler': system_service_deleted_response_handler,
    u'com.mobicage.rpc.error': logServiceError
}

high_priority_calls = [
    u'com.mobicage.api.system.finishRegistration',
    u'com.mobicage.api.system.unregisterMobile',
    u'com.mobicage.api.system.heartBeat',
    u'com.mobicage.api.system.saveSettings',
    u'com.mobicage.api.system.getIdentityQRCode',
    u'com.mobicage.api.system.updateApplePushDeviceToken',
    u'com.mobicage.api.friends.getFriends',
    u'com.mobicage.api.friends.shareLocation',
    u'com.mobicage.api.friends.breakFriendShip',
    u'com.mobicage.api.friends.requestShareLocation',
    u'com.mobicage.api.friends.invite',
    u'com.mobicage.api.friends.getAvatar',
    u'com.mobicage.api.friends.getUserInfo',
    u'com.mobicage.api.friends.getFriendInvitationSecrets',
    u'com.mobicage.api.friends.ackInvitationByInvitationSecret',
    u'com.mobicage.api.friends.logInvitationSecretSent',
    u'com.mobicage.api.friends.findRogerthatUsersViaEmail',
    u'com.mobicage.api.friends.findRogerthatUsersViaFacebook',
    u'com.mobicage.api.friends.getCategory',
    u'com.mobicage.api.friends.userScanned',
    u'com.mobicage.api.services.getActionInfo',
    u'com.mobicage.api.services.getMenuIcon',
    u'com.mobicage.api.services.pressMenuItem',
    u'com.mobicage.api.services.shareService',
    u'com.mobicage.api.services.findService',
    u'com.mobicage.api.services.pokeService',
    u'com.mobicage.api.services.startAction',
    u'com.mobicage.api.services.sendApiCall',
    u'com.mobicage.api.services.updateUserData',
    u'com.mobicage.api.location.getFriendLocation',
    u'com.mobicage.api.location.getFriendLocations',
    u'com.mobicage.api.messaging.sendMessage',
    u'com.mobicage.api.messaging.ackMessage',
    u'com.mobicage.api.messaging.submitTextLineForm',
    u'com.mobicage.api.messaging.submitTextBlockForm',
    u'com.mobicage.api.messaging.submitAutoCompleteForm',
    u'com.mobicage.api.messaging.submitSingleSelectForm',
    u'com.mobicage.api.messaging.submitMultiSelectForm',
    u'com.mobicage.api.messaging.submitDateSelectForm',
    u'com.mobicage.api.messaging.submitSingleSliderForm',
    u'com.mobicage.api.messaging.submitRangeSliderForm',
    u'com.mobicage.api.messaging.uploadChunk',
    u'com.mobicage.api.messaging.submitPhotoUploadForm',
    u'com.mobicage.api.messaging.submitGPSLocationForm',
    u'com.mobicage.api.messaging.lockMessage',
    u'com.mobicage.api.messaging.markMessagesAsRead',
    u'com.mobicage.api.messaging.deleteConversation',
    u'com.mobicage.api.messaging.getConversation',
    u'com.mobicage.api.messaging.getConversationAvatar',
]

low_reliability_calls = [
    u'com.mobicage.api.activity.logLocations'
]
