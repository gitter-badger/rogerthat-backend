# -*- coding: utf-8 -*-
# Copyright 2016 Mobicage NV
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

import base64
import json

from rogerthat.dal.beacon import get_beacons
from rogerthat.dal.profile import get_search_config, get_profile_infos
from rogerthat.dal.service import get_broadcast_settings_items
from rogerthat.models import ServiceIdentity, ServiceTranslation, MessageFlowDesign, UserProfile, Broadcast
from rogerthat.settings import get_server_settings
from rogerthat.to import ReturnStatusTO
from rogerthat.to.activity import GeoPointWithTimestampTO
from rogerthat.to.beacon import BeaconTO
from rogerthat.to.friends import GetUserInfoRequestTO, GetUserInfoResponseTO, ServiceMenuItemTO
from rogerthat.to.profile import SearchConfigTO
from rogerthat.translations import localize
from rogerthat.utils import is_flag_set, azzert
from rogerthat.utils.app import get_human_user_from_app_user
from rogerthat.utils.service import remove_slash_default, get_identity_from_service_identity_user
from mcfw.properties import long_property, unicode_property, typed_property, bool_property, unicode_list_property, \
    long_list_property
from mcfw.rpc import arguments


class APIKeyTO(object):
    timestamp = long_property('1')
    name = unicode_property('2')
    key = unicode_property('3')

    @staticmethod
    def fromDBAPIKey(model):
        m = APIKeyTO()
        m.key = model.key().name()
        m.name = unicode(model.name)
        m.timestamp = model.timestamp
        return m

class ServiceLanguagesTO(object):
    allLanguages = unicode_list_property('1')
    allLanguagesStr = unicode_list_property('2')
    nonDefaultSupportedLanguages = unicode_list_property('3')
    defaultLanguage = unicode_property('4')
    defaultLanguageStr = unicode_property('5')

class ServiceConfigurationInfoTO(object):
    apiKeys = typed_property('1', APIKeyTO, True)
    sik = unicode_property('3')
    autoLoginUrl = unicode_property('4')

class ServiceConfigurationTO(ServiceConfigurationInfoTO):
    callBackURI = unicode_property('51')
    callBackJid = unicode_property('52')
    enabled = bool_property('53')
    actions = unicode_list_property('54')
    callBackFromJid = unicode_property('55')
    needsTestCall = bool_property('56')
    callbacks = long_property('57')
    mobidickUrl = unicode_property('58')
    autoUpdating = bool_property('59')
    updatesPending = bool_property('60')

class ServiceCallbackConfigurationTO(object):
    uri = unicode_property('1')
    jid = unicode_property('2')
    functions = unicode_list_property('3')

class ServiceLogTO(object):
    timestamp = long_property('1')
    type = long_property('2')
    status = long_property('3')
    function = unicode_property('4')
    request = unicode_property('5')
    response = unicode_property('6')
    errorCode = long_property('7')
    errorMessage = unicode_property('8')

    @staticmethod
    def fromServiceLog(sl):
        slt = ServiceLogTO()
        slt.timestamp = sl.timestamp
        slt.type = sl.type
        slt.status = sl.status
        slt.function = sl.function
        try:
            slt.request = json.dumps(json.loads(sl.request), indent=2, ensure_ascii=False)
        except:
            slt.request = None
        try:
            slt.response = json.dumps(json.loads(sl.response), indent=2, ensure_ascii=False)
        except:
            slt.response = None
        slt.errorCode = sl.error_code
        slt.errorMessage = sl.error_message
        return slt

class ServiceIdentitySummaryTO(object):
    created = long_property('1')
    identifier = unicode_property('2')
    name = unicode_property('3')
    menu_branding = unicode_property('4')

    @staticmethod
    def fromServiceIdentity(service_identity, to=None):
        to = to or ServiceIdentitySummaryTO()
        to.created = service_identity.creationTimestamp
        to.identifier = service_identity.identifier
        to.name = service_identity.name
        to.menu_branding = service_identity.menuBranding
        return to


class ServiceIdentityDetailsTO(ServiceIdentitySummaryTO):
    INHERITANCE_PROPERTIES = ('description_use_default', 'description_branding_use_default', 'phone_number_use_default',
                              'phone_call_popup_use_default', 'search_use_default', 'app_ids_use_default')

    description = unicode_property('100')
    description_use_default = bool_property('101')
    description_branding = unicode_property('102')
    description_branding_use_default = bool_property('103')
    menu_branding_use_default = bool_property('105')
    phone_number = unicode_property('106')
    phone_number_use_default = bool_property('107')
    phone_call_popup = unicode_property('108')
    phone_call_popup_use_default = bool_property('109')
    recommend_enabled = bool_property('110')
    admin_emails = unicode_list_property('111')
    search_use_default = bool_property('112')
    search_config = typed_property('113', SearchConfigTO, False)
    qualified_identifier = unicode_property('114')
    app_data = unicode_property('115')
    email_statistics_use_default = bool_property('116')
    email_statistics = bool_property('117')
    beacons = typed_property('118', BeaconTO, True)
    app_ids_use_default = bool_property('119')
    app_ids = unicode_list_property('120')
    app_names = unicode_list_property('121')
    can_edit_supported_apps = bool_property('122')
    beacon_auto_invite = bool_property('123')
    content_branding_hash = unicode_property('124')

    @staticmethod
    def fromServiceIdentity(service_identity, service_profile):
        identifier = get_identity_from_service_identity_user(service_identity.user)
        if identifier == ServiceIdentity.DEFAULT:
            azzert(service_identity.inheritanceFlags == 0,
                   "inheritanceFlags of default must be 0, not %s" % service_identity.inheritanceFlags)

        details = ServiceIdentitySummaryTO.fromServiceIdentity(service_identity, ServiceIdentityDetailsTO())

        details.description_use_default = is_flag_set(ServiceIdentity.FLAG_INHERIT_DESCRIPTION,
                                                      service_identity.inheritanceFlags)
        details.description = service_identity.description

        details.description_branding_use_default = is_flag_set(ServiceIdentity.FLAG_INHERIT_DESCRIPTION_BRANDING,
                                                               service_identity.inheritanceFlags)
        details.description_branding = service_identity.descriptionBranding

        details.menu_branding_use_default = is_flag_set(ServiceIdentity.FLAG_INHERIT_MENU_BRANDING,
                                                        service_identity.inheritanceFlags)

        details.phone_number_use_default = is_flag_set(ServiceIdentity.FLAG_INHERIT_PHONE_NUMBER,
                                                       service_identity.inheritanceFlags)
        details.phone_number = service_identity.mainPhoneNumber

        details.phone_call_popup_use_default = is_flag_set(ServiceIdentity.FLAG_INHERIT_PHONE_POPUP_TEXT,
                                                           service_identity.inheritanceFlags)
        details.phone_call_popup = service_identity.callMenuItemConfirmation

        details.recommend_enabled = bool(service_identity.shareEnabled)

        details.admin_emails = list() if service_identity.metaData is None else [e.strip() for e in service_identity.metaData.split(',') if e.strip()]

        if service_identity.serviceData:
            service_data = service_identity.serviceData.to_json_dict()
            details.app_data = json.dumps(service_data).decode('utf-8') if service_data else None
        else:
            details.app_data = service_identity.appData

        details.search_use_default = is_flag_set(ServiceIdentity.FLAG_INHERIT_SEARCH_CONFIG,
                                                 service_identity.inheritanceFlags)
        sc, locs = get_search_config(service_identity.user)
        details.search_config = SearchConfigTO.fromDBSearchConfig(sc, locs)

        details.qualified_identifier = service_identity.qualifiedIdentifier

        details.email_statistics_use_default = is_flag_set(ServiceIdentity.FLAG_INHERIT_EMAIL_STATISTICS,
                                                           service_identity.inheritanceFlags)
        details.email_statistics = service_identity.emailStatistics

        details.beacons = map(BeaconTO.fromModel, get_beacons(service_identity.service_user, identifier))

        details.app_ids_use_default = is_flag_set(ServiceIdentity.FLAG_INHERIT_APP_IDS,
                                                  service_identity.inheritanceFlags)
        details.app_ids = list()
        details.app_names = list()
        from rogerthat.models import App
        for app in App.get(map(App.create_key, service_identity.appIds)):
            if app:
                details.app_ids.append(app.app_id)
                details.app_names.append(app.name)
        details.can_edit_supported_apps = service_profile.canEditSupportedApps
        details.beacon_auto_invite = service_identity.beacon_auto_invite
        details.content_branding_hash = service_identity.contentBrandingHash
        return details

class ServiceIdentityListResultTO(object):
    cursor = unicode_property('1')
    identities = typed_property('2', ServiceIdentityDetailsTO, True)

class ServiceUserTO(object):
    name = unicode_property('1')
    email = unicode_property('2')
    avatarId = long_property('3')
    app_id = unicode_property('4')

    @staticmethod
    def fromFriendServiceIdentityConnection(fsic):
        su = ServiceUserTO()
        su.name = fsic.friend_name
        su.email = get_human_user_from_app_user(fsic.friend).email()  # human friend
        su.avatarId = fsic.friend_avatarId
        su.app_id = fsic.app_id
        return su

class GetServiceUsersResponseTO(object):
    users = typed_property('1', ServiceUserTO, True)
    cursor = unicode_property('2')

class GetServiceActionInfoRequestTO(GetUserInfoRequestTO):
    action = unicode_property('100')

class GetServiceActionInfoResponseTO(GetUserInfoResponseTO):
    actionDescription = unicode_property('100')
    staticFlowHash = unicode_property('101')
    staticFlow = unicode_property('102')
    staticFlowBrandings = unicode_list_property('103')

class StartServiceActionRequestTO(object):
    email = unicode_property('1')
    action = unicode_property('2')
    context = unicode_property('3')
    static_flow_hash = unicode_property('4')
    message_flow_run_id = unicode_property('5')
    timestamp = long_property('6')

class StartServiceActionResponseTO(object):
    pass

class PokeServiceRequestTO(object):
    email = unicode_property('1')
    hashed_tag = unicode_property('2')
    context = unicode_property('3')
    timestamp = long_property('4')

class PokeServiceResponseTO(object):
    pass

class GetMenuIconRequestTO(object):
    service = unicode_property('1')
    coords = long_list_property('2')
    size = long_property('3')

class GetMenuIconResponseTO(object):
    icon = unicode_property('1')
    iconHash = unicode_property('2')

class GetStaticFlowRequestTO(object):
    service = unicode_property('1')
    coords = long_list_property('2')
    staticFlowHash = unicode_property('3')

class GetStaticFlowResponseTO(object):
    staticFlow = unicode_property('1')

class PressMenuIconRequestTO(object):
    service = unicode_property('1')
    coords = long_list_property('2')
    context = unicode_property('3')
    generation = long_property('4')
    message_flow_run_id = unicode_property('5')
    static_flow_hash = unicode_property('6')
    hashed_tag = unicode_property('7')
    timestamp = long_property('8')

class PressMenuIconResponseTO(object):
    pass

class ShareServiceRequestTO(object):
    service_email = unicode_property('1')
    recipient = unicode_property('2')

class ShareServiceResponseTO(object):
    pass

class FindServiceRequestTO(object):
    search_string = unicode_property('1')
    geo_point = typed_property('2', GeoPointWithTimestampTO, False)
    organization_type = long_property('3')
    cursor = unicode_property('4', default=None)
    avatar_size = long_property('5', default=50)

class FindServiceItemTO(object):
    email = unicode_property('1')
    name = unicode_property('2')
    description = unicode_property('3')
    avatar = unicode_property('4')
    description_branding = unicode_property('5')
    qualified_identifier = unicode_property('6')
    avatar_id = long_property('7')
    detail_text = unicode_property('8', default=None)

    @staticmethod
    @arguments(p=ServiceIdentity, target_language=unicode, distance=int, avatar_size=int)
    def fromServiceIdentity(p, target_language, distance=-1, avatar_size=50):
        from rogerthat.pages.profile import get_avatar_cached
        from rogerthat.bizz.i18n import get_translator

        translator = get_translator(p.service_user, ServiceTranslation.IDENTITY_TYPES, target_language)

        entry = FindServiceItemTO()
        entry.email = remove_slash_default(p.user).email()
        entry.avatar_id = p.avatarId  # Web support
        entry.avatar = unicode(base64.b64encode(get_avatar_cached(p.avatarId, avatar_size)))
        entry.description_branding = translator.translate(ServiceTranslation.IDENTITY_BRANDING, p.descriptionBranding, target_language)
        entry.description = translator.translate(ServiceTranslation.IDENTITY_TEXT, p.description, target_language)
        entry.name = translator.translate(ServiceTranslation.IDENTITY_TEXT, p.name, target_language)
        entry.qualified_identifier = translator.translate(ServiceTranslation.IDENTITY_TEXT, p.qualifiedIdentifier, target_language)
        entry.detail_text = None if distance < 0 else localize(target_language, 'Distance: %(distance)s km',
                                                               distance=distance)
        return entry

class FindServiceCategoryTO(object):
    category = unicode_property('1')
    items = typed_property('2', FindServiceItemTO, True)
    cursor = unicode_property('3', default=None)

class FindServiceResponseTO(object):
    error_string = unicode_property('1')
    matches = typed_property('2', FindServiceCategoryTO, True)


class SendApiCallRequestTO(object):
    '''Request sent by mobile'''
    service = unicode_property('1')
    id = long_property('2')
    method = unicode_property('3')
    params = unicode_property('4')
    hashed_tag = unicode_property('5')

class SendApiCallResponseTO(object):
    '''Response of request sent by mobile'''
    pass


class SendApiCallCallbackResultTO(object):
    '''Result sent by TPS'''
    result = unicode_property('1')
    error = unicode_property('2')


class ReceiveApiCallResultRequestTO(object):
    '''Result sent to mobile'''
    id = long_property('1')
    result = unicode_property('2')
    error = unicode_property('3')

class ReceiveApiCallResultResponseTO(object):
    '''Response of request sent to mobile'''
    pass


class UpdateUserDataRequestTO(object):
    service = unicode_property('1')
    user_data = unicode_property('2', default=None)
    app_data = unicode_property('3', default=None)

class UpdateUserDataResponseTO(object):
    pass


class ServiceInteractionDefTO(object):
    url = unicode_property('1')
    description = unicode_property('2')
    tag = unicode_property('3')
    timestamp = long_property('4')
    id_ = long_property('5')
    embed_url = unicode_property('6')
    email_url = unicode_property('7')
    sms_url = unicode_property('8')
    total_scan_count = long_property('9')
    scanned_from_rogerthat_count = long_property('10')
    scanned_from_outside_rogerthat_on_supported_platform_count = long_property('11')
    scanned_from_outside_rogerthat_on_unsupported_platform_count = long_property('12')
    service_identifier = unicode_property('13')
    static_flow_name = unicode_property('14')
    branding = unicode_property('15')

    @staticmethod
    def urlFromServiceInteractionDef(sid):
        from rogerthat.bizz.friends import userCode
        return u"%s/si/%s/%s" % (get_server_settings().baseUrl, userCode(sid.user), sid.key().id())

    @staticmethod
    def emailUrl(sid):
        from rogerthat.bizz.service import get_service_interact_short_url
        return get_service_interact_short_url(sid) + "?email"

    @staticmethod
    def smsUrl(sid):
        from rogerthat.bizz.service import get_service_interact_short_url
        return get_service_interact_short_url(sid)

    @staticmethod
    def fromServiceInteractionDef(sid):
        from rogerthat.bizz.service import get_service_interact_qr_code_url
        to = ServiceInteractionDefTO()
        to.url = ServiceInteractionDefTO.urlFromServiceInteractionDef(sid)
        to.description = sid.description
        to.tag = sid.tag
        to.service_identifier = sid.service_identity
        to.timestamp = sid.timestamp
        to.id_ = sid.key().id()
        to.embed_url = get_service_interact_qr_code_url(sid)
        to.email_url = ServiceInteractionDefTO.emailUrl(sid)
        to.sms_url = ServiceInteractionDefTO.smsUrl(sid)
        to.total_scan_count = sid.totalScanCount
        to.scanned_from_rogerthat_count = sid.scannedFromRogerthatCount
        to.scanned_from_outside_rogerthat_on_supported_platform_count = sid.scannedFromOutsideRogerthatOnSupportedPlatformCount
        to.scanned_from_outside_rogerthat_on_unsupported_platform_count = sid.scannedFromOutsideRogerthatOnUnsupportedPlatformCount
        to.static_flow_name = MessageFlowDesign.get(sid.staticFlowKey).name if sid.staticFlowKey else None
        to.branding = sid.branding
        return to

class GetServiceInteractionDefsResponseTO(object):
    defs = typed_property('1', ServiceInteractionDefTO, True)
    cursor = unicode_property('2')

class MessageFlowDesignTO(object):
    id = unicode_property('1')
    name = unicode_property('2')
    status = long_property('3')
    validation_error = unicode_property('4')
    timestamp = long_property('5')
    broken_sub_flows = unicode_list_property('6')
    multilanguage = bool_property('7')
    i18n_warning = unicode_property('8')
    no_definition = bool_property('9')

    @staticmethod
    def fromMessageFlowDesign(mfd):
        mfdt = MessageFlowDesignTO()
        mfdt.id = unicode(mfd.key())
        mfdt.name = mfd.name
        mfdt.status = mfd.status
        mfdt.validation_error = mfd.validation_error
        mfdt.timestamp = mfd.design_timestamp
        mfdt.broken_sub_flows = [k.name() for k in (mfd.broken_sub_flows or [])]
        mfdt.multilanguage = mfd.multilanguage
        mfdt.i18n_warning = mfd.i18n_warning
        mfdt.no_definition = mfd.definition is None
        return mfdt

class MessageFlowListTO(object):
    message_flows = typed_property(1, MessageFlowDesignTO, True)
    service_languages = unicode_list_property('2')

class ServicePanelMenuItemTO(ServiceMenuItemTO):
    iconName = unicode_property('50')
    iconColor = unicode_property('51')
    iconUrl = unicode_property('52')
    tag = unicode_property('53')
    staticFlowName = unicode_property('54')
    isBroadcastSettings = bool_property('55')
    roles = long_list_property('56')

    @staticmethod
    def fromServiceMenuDef(smd, translator, language, target_user_profile, service_identity_user, existence=0):
        smi = ServicePanelMenuItemTO()
        smi.__dict__ = ServiceMenuItemTO.fromServiceMenuDef(smd, translator, language, list(), target_user_profile, service_identity_user, existence).__dict__
        smi.iconName = smd.iconName
        smi.iconColor = smd.iconColor
        if not smi.iconColor:
            from rogerthat.bizz.service import calculate_icon_color_from_branding
            smi.iconColor = calculate_icon_color_from_branding(service_identity_user, target_user_profile)
        smi.iconUrl = "/mobi/service/menu/icons/lib/" + smd.iconName
        smi.tag = smd.tag
        smi.staticFlowName = MessageFlowDesign.get(smd.staticFlowKey).name if smd.staticFlowKey else None
        smi.isBroadcastSettings = smd.isBroadcastSettings
        smi.roles = list() if smd.roles is None else smd.roles
        return smi


class LibraryMenuIconTO(object):
    name = unicode_property('1')
    label = unicode_property('2')


class UserDetailsTO(object):
    # Used in ServiceApiCallbacks
    email = unicode_property('1')
    name = unicode_property('2')
    language = unicode_property('3')
    avatar_url = unicode_property('4')
    app_id = unicode_property('5')

    @classmethod
    def create(cls, email, name, language, avatar_url, app_id):
        to = cls()
        to.email = email
        to.name = name
        to.language = language
        to.avatar_url = avatar_url
        to.app_id = app_id
        return to

    @classmethod
    def fromUserProfile(cls, user_profile):
        to = cls()
        to.email = get_human_user_from_app_user(user_profile.user).email()
        to.name = user_profile.name
        to.language = user_profile.language
        to.avatar_url = user_profile.avatarUrl
        to.app_id = user_profile.app_id
        return to

    def toAppUser(self):
        from rogerthat.utils.app import create_app_user_by_email
        return create_app_user_by_email(self.email, self.app_id)


class ServiceStatusTO(object):
    enabled = bool_property('1')
    test_callback_needed = bool_property('2')
    auto_updating = bool_property('3')
    updates_pending = bool_property('4')

class BroadcastTO(object):
    STATUS_ALL_PENDING = 1
    STATUS_PENDING = 2
    STATUS_APPROVED = 3
    STATUS_DECLINED = 4

    key = unicode_property('1')
    name = unicode_property('2')
    broadcast_type = unicode_property('3')
    creation_time = long_property('4')
    sent = bool_property('5')
    status_string = unicode_property('6')
    status = long_property('7')
    sent_time = long_property('8')
    scheduled_at = long_property('9')

    @staticmethod
    def fromBroadcast(broadcast):
        to = BroadcastTO()
        to.key = unicode(broadcast.key())
        to.name = broadcast.name
        to.broadcast_type = broadcast.type_
        to.creation_time = broadcast.creation_time
        to.sent = broadcast.sent
        to.sent_time = broadcast.sent_time
        if broadcast.declined:
            to.status_string = u"Declined"
            to.status = BroadcastTO.STATUS_DECLINED
        elif broadcast.approved:
            to.status_string = u"Approved by all"
            to.status = BroadcastTO.STATUS_APPROVED
        else:
            all_count = len(broadcast.test_persons)
            approved_count = broadcast.get_status_count(Broadcast.TEST_PERSON_STATUS_ACCEPTED)
            pending_count = broadcast.get_status_count(Broadcast.TEST_PERSON_STATUS_UNDECIDED)
            to.status_string = u"Pending approval (%s/%s)" % (approved_count, all_count)
            to.status = BroadcastTO.STATUS_ALL_PENDING if pending_count == all_count else BroadcastTO.STATUS_PENDING
        to.scheduled_at = broadcast.scheduled_at
        return to


class ServiceBroadCastConfigurationTO(object):
    broadcast_types = unicode_list_property('1')
    test_persons = typed_property('2', UserDetailsTO, True)
    broadcasts = typed_property('3', BroadcastTO, True)
    warnings = unicode_list_property('4')

    @staticmethod
    def fromServiceProfile(service_profile, broadcasts):
        to = ServiceBroadCastConfigurationTO()
        to.broadcast_types = service_profile.broadcastTypes
        user_profiles = get_profile_infos(service_profile.broadcastTestPersons,
                                          expected_types=len(service_profile.broadcastTestPersons) * [UserProfile],
                                          allow_none_in_results=True)
        to.test_persons = [UserDetailsTO.fromUserProfile(user_profile) for user_profile in filter(None, user_profiles)]
        to.broadcasts = map(BroadcastTO.fromBroadcast, broadcasts)
        to.warnings = list()
        if not get_broadcast_settings_items(service_profile.user, 1):
            to.warnings.append(u"There is no 'Broadcast settings' service menu item.")
        return to


class DeleteBroadcastTypeReturnStatusTO(ReturnStatusTO):
    confirmation = unicode_property('51')


class BroadcastTestPersonReturnStatusTO(ReturnStatusTO):
    user_details = typed_property('51', UserDetailsTO, False)


class TestBroadcastReturnStatusTO(ReturnStatusTO):
    broadcast = typed_property('51', BroadcastTO, False)
