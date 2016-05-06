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
from types import NoneType

from rogerthat.bizz.i18n import DummyTranslator
from rogerthat.bizz.profile import update_service_avatar
from rogerthat.bizz.roles import create_service_role, delete_service_role, grant_service_role, revoke_service_role
from rogerthat.bizz.rtemail import generate_auto_login_url
from rogerthat.bizz.service import get_and_validate_service_identity_user, create_menu_item, \
    delete_menu_item as bizz_delete_menu_item, set_reserved_item_caption, create_service, validate_and_get_solution, \
    set_user_data, enable_callback_by_function, validate_app_admin, InvalidAppIdException, get_app_data, set_app_data
from rogerthat.bizz.service.broadcast import set_broadcast_types
from rogerthat.bizz.service.i18n import translation_export, translation_import
from rogerthat.bizz.service.mfd import delete_message_flow, get_message_flow_by_key_or_name, save_message_flow_by_xml
from rogerthat.bizz.user import delete_account
from rogerthat.dal.profile import get_service_profile, get_service_or_user_profile
from rogerthat.dal.roles import get_service_grants
from rogerthat.dal.service import get_service_identity, get_service_identities
from rogerthat.models import MessageFlowDesign, Branding, ServiceIdentity, ServiceProfile, App
from rogerthat.pages.profile import get_avatar_cached
from rogerthat.rpc import users
from rogerthat.rpc.service import service_api, service_api_callback
from rogerthat.to.branding import BrandingTO, UpdatedBrandingTO
from rogerthat.to.friends import WebServiceMenuTO, ServiceMenuDetailTO
from rogerthat.to.messaging import BaseMemberTO
from rogerthat.to.messaging.flow import MessageFlowDesignTO
from rogerthat.to.roles import RoleTO
from rogerthat.to.service import ServiceIdentityDetailsTO, ServiceStatusTO, ServiceIdentityListResultTO, \
    ServiceConfigurationInfoTO, APIKeyTO, UserDetailsTO, SendApiCallCallbackResultTO, ServiceCallbackConfigurationTO
from rogerthat.to.statistics import ServiceIdentityStatisticsTO, FlowStatisticsTO, FlowStatisticsListResultTO
from rogerthat.to.system import ServiceIdentityInfoTO, TranslationSetTO, LanguagesTO
from rogerthat.translations import DEFAULT_LANGUAGE
from rogerthat.utils.app import create_app_user, create_app_user_by_email
from rogerthat.utils.crypto import decrypt, encrypt
from google.appengine.ext import deferred
from mcfw.consts import MISSING
from mcfw.rpc import returns, arguments
from rogerthat.utils.service import get_service_identity_tuple


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

@service_api(function=u"system.get_info", cache_result=False)
@returns(ServiceIdentityInfoTO)
@arguments(service_identity=unicode)
def get_info(service_identity=None):
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    service_identity = get_service_identity(service_identity_user)
    return ServiceIdentityInfoTO.fromServiceIdentity(service_identity)

@service_api(function=u"system.get_identity", cache_result=False)
@returns(ServiceIdentityDetailsTO)
@arguments(service_identity=unicode)
def get_identity(service_identity=None):
    service_user = users.get_current_user()
    service_identity_user = get_and_validate_service_identity_user(service_user, service_identity)
    service_identity = get_service_identity(service_identity_user)
    service_profile = get_service_profile(service_user)
    return ServiceIdentityDetailsTO.fromServiceIdentity(service_identity, service_profile)

@service_api(function=u"system.put_identity")
@returns(NoneType)
@arguments(identity=ServiceIdentityDetailsTO)
def put_identity(identity):
    from rogerthat.bizz.service import create_or_update_service_identity
    if identity.identifier is MISSING:
        identity.identifier = ServiceIdentity.DEFAULT
    create_or_update_service_identity(users.get_current_user(), identity)

@service_api(function=u"system.delete_identity")
@returns(NoneType)
@arguments(identifier=unicode)
def delete_identity(identifier):
    from rogerthat.bizz.service import delete_service_identity
    delete_service_identity(users.get_current_user(), identifier)

@service_api(function=u"system.list_identities", cache_result=False)
@returns(ServiceIdentityListResultTO)
@arguments(cursor=unicode)
def list_identities(cursor=None):
    service_user = users.get_current_user()
    if cursor:
        try:
            cursor = decrypt(service_user, cursor)
        except:
            from rogerthat.bizz.exceptions import InvalidCursorException
            raise InvalidCursorException()
    from rogerthat.dal.service import get_service_identities_query
    qry = get_service_identities_query(service_user)
    qry.with_cursor(cursor)
    identities = qry.fetch(1000)
    # prevent extra roundtrip by trying to detect whether there are more results to fetch
    if len(identities) < 1000 and cursor:
        extra_identities = qry.fetch(10)
        if len(extra_identities) == 0:
            cursor = None
        else:
            identities.extend(extra_identities)
            cursor = qry.cursor()

    service_profile = get_service_profile(service_user)
    result = ServiceIdentityListResultTO()
    result.cursor = unicode(encrypt(service_user, cursor)) if cursor else None
    result.identities = [ServiceIdentityDetailsTO.fromServiceIdentity(i, service_profile) for i in identities]
    return result

@service_api(function=u"system.list_message_flows", cache_result=False)
@returns([MessageFlowDesignTO])
@arguments()
def list_message_flows():
    from rogerthat.dal.mfd import get_message_flow_designs_by_status
    service = users.get_current_user()
    return map(MessageFlowDesignTO.fromMessageFlowDesign, get_message_flow_designs_by_status(service, MessageFlowDesign.STATUS_VALID))

@service_api(function=u"system.list_brandings", cache_result=False)
@returns([BrandingTO])
@arguments()
def list_brandings():
    brandings = [BrandingTO.fromDBBranding(branding) for branding in Branding.all().filter("user =", users.get_current_user()) if branding.timestamp > 0]
    return sorted(brandings, key=lambda i:i.timestamp)

@service_api(function=u"system.store_branding")
@returns(BrandingTO)
@arguments(description=unicode, content=unicode)
def store_branding(description, content):
    from rogerthat.bizz.branding import store_branding as store_branding_bizz
    service = users.get_current_user()
    zip_stream = StringIO()
    zip_stream.write(base64.b64decode(content))
    zip_stream.seek(0)
    return BrandingTO.fromDBBranding(store_branding_bizz(service, zip_stream, description))

@service_api(function=u"system.store_pdf_branding")
@returns(BrandingTO)
@arguments(description=unicode, content=unicode)
def store_pdf_branding(description, content):
    from rogerthat.bizz.branding import store_branding_pdf as store_branding_bizz
    service = users.get_current_user()
    zip_stream = StringIO()
    zip_stream.write(base64.b64decode(content))
    zip_stream.seek(0)
    return BrandingTO.fromDBBranding(store_branding_bizz(service, zip_stream, description))


@service_api_callback(function="system.brandings_updated", code=ServiceProfile.CALLBACK_SYSTEM_BRANDINGS_UPDATED)
@returns(NoneType)
@arguments(brandings=[UpdatedBrandingTO], reason=unicode)
def brandings_updated(brandings, reason):
    pass


@service_api(function=u"system.validate_callback_configuration", available_when_disabled=True)
@returns(NoneType)
@arguments(enable_on_success=bool)
def validate_callback_configuration(enable_on_success):
    from rogerthat.bizz.service import perform_test_callback
    perform_test_callback(users.get_current_user(), enable_on_success)

@service_api(function=u"system.get_status", available_when_disabled=True, cache_result=False)
@returns(ServiceStatusTO)
@arguments()
def get_status():
    service = users.get_current_user()
    profile = get_service_profile(service, cached=False)
    status = ServiceStatusTO()
    status.enabled = True if profile.enabled else False  # Prevent sending None
    status.test_callback_needed = profile.testCallNeeded
    status.auto_updating = profile.autoUpdating
    status.updates_pending = profile.updatesPending
    return status

@service_api(function=u"system.put_callback")
@returns(NoneType)
@arguments(function=unicode, enabled=bool)
def put_callback(function, enabled):
    enable_callback_by_function(users.get_current_user(), function, enabled)

@service_api(function=u"system.publish_changes")
@returns(NoneType)
@arguments()
def publish_changes():
    from rogerthat.bizz.service import publish_changes as bizz_publish_changes
    bizz_publish_changes(users.get_current_user())

@service_api(function=u"system.list_broadcast_types", cache_result=False)
@returns([unicode])
@arguments()
def list_broadcast_types():
    service = users.get_current_user()
    profile = get_service_profile(service)
    return profile.broadcastTypes

@service_api(function=u"system.put_broadcast_types")
@returns(NoneType)
@arguments(broadcast_types=[unicode], force=bool)
def put_broadcast_types(broadcast_types, force=False):
    set_broadcast_types(users.get_current_user(), broadcast_types, force)

@service_api(function=u"system.get_menu_item", cache_result=False)
@returns(WebServiceMenuTO)
@arguments(service_identity=unicode)
def get_menu_item(service_identity=None):
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    si = get_service_identity(service_identity_user)
    dummy_translator = DummyTranslator(get_service_profile(si.service_user).defaultLanguage)
    sm = WebServiceMenuTO.fromServiceIdentity(si, dummy_translator.default_language, dummy_translator)
    return sm

@service_api(function=u"system.put_menu_item")
@returns(NoneType)
@arguments(icon_name=unicode, label=unicode, tag=unicode, coords=[int], icon_color=unicode, screen_branding=unicode,
           static_flow=unicode, requires_wifi=bool, run_in_background=bool, is_broadcast_settings=bool,
           broadcast_branding=unicode, roles=[(int, long)])
def put_menu_item(icon_name, label, tag, coords, icon_color=None, screen_branding=None, static_flow=None,
                  requires_wifi=False, run_in_background=True, is_broadcast_settings=False, broadcast_branding=None,
                  roles=None):
    service_user = users.get_current_user()
    static_flow_name = get_message_flow_by_key_or_name(service_user, static_flow).name if static_flow else None
    if roles in (None, MISSING):
        roles = list()
    create_menu_item(service_user, icon_name.replace(' ', '_'), icon_color, label, tag, coords, screen_branding,
                     static_flow_name, requires_wifi, run_in_background, roles, is_broadcast_settings,
                     broadcast_branding)

@service_api(function=u"system.delete_menu_item")
@returns(bool)
@arguments(coords=[(int, long)])
def delete_menu_item(coords):
    coords = map(int, coords)
    return bizz_delete_menu_item(users.get_current_user(), coords)

@service_api(function=u"system.get_menu", cache_result=False)
@returns(ServiceMenuDetailTO)
@arguments()
def get_menu():
    from rogerthat.bizz.service import get_menu as bizz_get_menu
    return bizz_get_menu(users.get_current_user())

@service_api(function=u"system.put_reserved_menu_item_label")
@returns(NoneType)
@arguments(column=int, label=unicode)
def put_reserved_menu_item_label(column, label):
    set_reserved_item_caption(users.get_current_user(), column, label)

@service_api(function=u"system.get_translations")
@returns(TranslationSetTO)
@arguments()
def get_translations():
    return translation_export(users.get_current_user())

@service_api(function=u"system.put_translations")
@returns(NoneType)
@arguments(translations=TranslationSetTO)
def put_translations(translations):
    translation_import(users.get_current_user(), translations)

@service_api(function=u"system.put_flow")
@returns(MessageFlowDesignTO)
@arguments(xml=unicode, multilanguage=bool)
def put_flow(xml, multilanguage=True):
    mfd = save_message_flow_by_xml(users.get_current_user(), xml, multilanguage)
    return MessageFlowDesignTO.fromMessageFlowDesign(mfd)

@service_api(function=u"system.delete_flow", cache_result=False)
@returns(bool)
@arguments(flow=unicode)
def delete_flow(flow):
    service_user = users.get_current_user()
    return delete_message_flow(service_user, get_message_flow_by_key_or_name(service_user, flow))

@service_api(function=u'system.put_user_data')
@returns(NoneType)
@arguments(email=unicode, user_data=unicode, service_identity=unicode, app_id=unicode)
def put_user_data(email, user_data, service_identity=None, app_id=None):
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    if app_id is None:
        app_id = get_service_identity(service_identity_user).app_id
    set_user_data(service_identity_user, create_app_user(users.User(email), app_id), user_data)

@service_api(function=u'system.del_user_data')
@returns(NoneType)
@arguments(email=unicode, user_data_keys=[unicode], service_identity=unicode, app_id=unicode)
def del_user_data(email, user_data_keys, service_identity=None, app_id=None):
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    if app_id is None:
        app_id = get_service_identity(service_identity_user).app_id
    set_user_data(service_identity_user,
                  create_app_user(users.User(email), app_id),
                  json.dumps({key: None for key in user_data_keys}))

@service_api(function=u'system.get_user_data', cache_result=False)
@returns(unicode)
@arguments(email=unicode, user_data_keys=[unicode], service_identity=unicode, app_id=unicode)
def get_user_data(email, user_data_keys, service_identity=None, app_id=None):
    from rogerthat.bizz.service import get_user_data as get_user_data_bizz
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    if app_id is None:
        app_id = get_service_identity(service_identity_user).app_id
    return get_user_data_bizz(service_identity_user, create_app_user(users.User(email), app_id), user_data_keys)

@service_api(function=u'system.put_service_data')
@returns(NoneType)
@arguments(data=unicode, service_identity=unicode)
def put_service_data(data, service_identity=None):
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    set_app_data(service_identity_user, data)

@service_api(function=u'system.del_service_data')
@returns(NoneType)
@arguments(keys=[unicode], service_identity=unicode)
def del_service_data(keys, service_identity=None):
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    set_app_data(service_identity_user, json.dumps({key: None for key in keys}))

@service_api(function=u'system.get_service_data', cache_result=False)
@returns(unicode)
@arguments(keys=[unicode], service_identity=unicode)
def get_service_data(keys, service_identity=None):
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    return get_app_data(service_identity_user, keys)

#############################################
# DO NOT DOCUMENT THIS SERVICE API FUNCTION #
# DJMATIC SOLUTION ONLY                     #
@service_api(function=u'system.put_service')
@returns(ServiceConfigurationInfoTO)
@arguments(email=unicode, name=unicode, password=unicode, languages=[unicode], category_id=unicode,
           organization_type=int, fail_if_exists=bool, supported_apps=[unicode],
           callback_configuration=ServiceCallbackConfigurationTO, beacon_auto_invite=bool)
def put_service(email, name, password, languages=None, category_id=None,
                organization_type=ServiceProfile.ORGANIZATION_TYPE_PROFIT, fail_if_exists=True, supported_apps=None,
                callback_configuration=None, beacon_auto_invite=True):
    service_user = users.get_current_user()
    solution = validate_and_get_solution(service_user)
    if languages is None:
        languages = [DEFAULT_LANGUAGE]
    sik, api_key = create_service(email, name, password, languages, solution, category_id, organization_type,
                                  fail_if_exists, supported_app_ids=supported_apps,
                                  callback_configuration=callback_configuration, beacon_auto_invite=beacon_auto_invite)
    cfg = ServiceConfigurationInfoTO()
    cfg.apiKeys = map(APIKeyTO.fromDBAPIKey, [api_key])
    cfg.sik = sik.key().name()
    cfg.autoLoginUrl = generate_auto_login_url(users.User(email))
    return cfg
#############################################

#############################################
# DO NOT DOCUMENT THIS SERVICE API FUNCTION #
# APP ADMIN ONLY                            #
@service_api(function=u'system.delete_service')
@returns(NoneType)
@arguments(email=unicode)
def delete_service(email):
    from rogerthat.bizz.job import delete_service as job_delete_service
    service_user = users.get_current_user()

    delete_service_user = users.User(email)
    app_ids = set()
    for si in get_service_identities(delete_service_user):
        for app_id in si.appIds:
            app_ids.add(app_id)
    app_ids = list(app_ids)
    validate_app_admin(service_user, app_ids)
    job_delete_service.job(service_user, users.User(email))

@service_api_callback(function="system.service_deleted", code=ServiceProfile.CALLBACK_SYSTEM_SERVICE_DELETED)
@returns(NoneType)
@arguments(email=unicode, success=bool)
def service_deleted(email, success):
    pass
#############################################

#############################################
# DO NOT DOCUMENT THIS SERVICE API FUNCTION #
# APP ADMIN ONLY                            #
@service_api(function=u'system.delete_users')
@returns(NoneType)
@arguments(members=[BaseMemberTO])
def delete_users(members):
    service_user = users.get_current_user()
    app_ids = set()
    app_user_emails = set()
    for m in members:
        if m.app_id in (None, MISSING):
            raise InvalidAppIdException(m.app_id)
        app_ids.add(m.app_id)
        if m.app_id != App.APP_ID_ROGERTHAT:
            app_user_emails.add("%s:%s" % (m.member, m.app_id))
        else:
            app_user_emails.add(m.member)
    app_ids = list(app_ids)
    validate_app_admin(service_user, app_ids)
    for app_user_email in app_user_emails:
        deferred.defer(delete_account, users.User(app_user_email))
#############################################

@service_api(function=u'system.get_languages', cache_result=False)
@returns(LanguagesTO)
@arguments()
def get_languages():
    service_user = users.get_current_user()
    service_profile = get_service_profile(service_user)
    languages = LanguagesTO()
    languages.default_language = service_profile.defaultLanguage
    languages.supported_languages = service_profile.supportedLanguages[1:]
    return languages

# @service_api(function=u"system.put_supported_languages")

@service_api(function=u'system.put_avatar')
@returns(NoneType)
@arguments(image=unicode)
def put_avatar(image):
    service_user = users.get_current_user()
    image1 = base64.b64decode(image)
    update_service_avatar(service_user, image1)

@service_api(function=u'system.get_avatar', silent_result=True)
@returns(unicode)
@arguments()
def get_avatar():
    service_user = users.get_current_user()
    profile = get_service_or_user_profile(service_user)
    avatarId = -1 if not profile or not profile.avatarId else profile.avatarId
    return base64.b64encode(get_avatar_cached(avatarId))

@service_api_callback(function="system.api_call", code=ServiceProfile.CALLBACK_SYSTEM_API_CALL)
@returns(SendApiCallCallbackResultTO)
@arguments(email=unicode, method=unicode, params=unicode, tag=unicode, service_identity=unicode,
           user_details=[UserDetailsTO])
def api_call(email, method, params, tag, service_identity, user_details):
    pass

@service_api(function=u'system.get_statistics', cache_result=False, silent_result=True)
@returns(ServiceIdentityStatisticsTO)
@arguments(service_identity=unicode)
def get_statistics(service_identity):
    from rogerthat.bizz.service.statistics import get_statistics as get_statistics_bizz
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    return get_statistics_bizz(service_identity_user)


@service_api(function=u"system.get_flow_statistics")
@returns(FlowStatisticsListResultTO)
@arguments(tags=[unicode], views=(int, long), time_span=(int, long), group_by=unicode, cursor=unicode,
           service_identity=unicode)
def get_flow_statistics(tags, views, time_span, group_by=FlowStatisticsTO.GROUP_BY_DAY, cursor=None,
                        service_identity=None):
    from rogerthat.bizz.service.statistics import get_flow_statistics as get_flow_statistics_bizz
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    stats, new_cursor = get_flow_statistics_bizz(service_identity_user, tags, cursor)
    flow_statistics = filter(None, stats)
    flow_stats_to = [FlowStatisticsTO.from_model(flow_stats, views, time_span, group_by) for flow_stats in
                     flow_statistics]
    return FlowStatisticsListResultTO.create(flow_stats_to, new_cursor)


@service_api(function=u"system.export_flow_statistics")
@returns(unicode)
@arguments(service_identity=unicode)
def export_flow_statistics(service_identity=None):
    from rogerthat.bizz.service.statistics import get_flow_statistics_excel
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    return base64.b64encode(get_flow_statistics_excel(service_identity_user))


@service_api(function=u'system.list_roles', cache_result=False)
@returns([RoleTO])
@arguments()
def list_roles():
    service_user = users.get_current_user()
    from rogerthat.dal.roles import list_service_roles as list_service_roles_dal
    return map(RoleTO.fromServiceRole, list_service_roles_dal(service_user))

@service_api(function=u'system.put_role')
@returns(long)
@arguments(name=unicode, role_type=unicode)
def put_role(name, role_type):
    service_user = users.get_current_user()
    role = create_service_role(service_user, name, role_type)
    return role.role_id

@service_api(function=u'system.delete_role')
@returns(NoneType)
@arguments(role_id=(int, long), cleanup_members=bool)
def delete_role(role_id, cleanup_members=False):
    service_user = users.get_current_user()
    delete_service_role(service_user, role_id, cleanup_members)

@service_api(function=u'system.add_role_member')
@returns(NoneType)
@arguments(role_id=(int, long), member=BaseMemberTO, service_identity=unicode)
def add_role_member(role_id, member, service_identity=None):
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    service_user, service_identity = get_service_identity_tuple(service_identity_user)
    app_id = get_service_identity(service_identity_user).app_id if member.app_id is MISSING else member.app_id
    app_user = create_app_user_by_email(member.member, app_id)
    grant_service_role(service_user, service_identity, app_user, role_id)

@service_api(function=u'system.delete_role_member')
@returns(NoneType)
@arguments(role_id=(int, long), member=BaseMemberTO, service_identity=unicode)
def delete_role_member(role_id, member, service_identity=None):
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    service_user, service_identity = get_service_identity_tuple(service_identity_user)
    app_id = get_service_identity(service_identity_user).app_id if member.app_id is MISSING else member.app_id
    app_user = create_app_user_by_email(member.member, app_id)
    revoke_service_role(service_user, service_identity, app_user, role_id)

@service_api(function=u'system.list_role_members')
@returns([BaseMemberTO])
@arguments(role_id=(int, long), service_identity=unicode)
def list_role_members(role_id, service_identity=None):
    from rogerthat.bizz.roles import ROLE_TYPE_SERVICE
    service_identity_user = get_and_validate_service_identity_user(users.get_current_user(), service_identity)
    service_user, service_identity = get_service_identity_tuple(service_identity_user)
    return [BaseMemberTO.create(g.user_email, g.app_id)
            for g in get_service_grants(service_user,
                                        filtered_service_identity=service_identity,
                                        filtered_role_id=role_id,
                                        filtered_role_type=ROLE_TYPE_SERVICE)]
