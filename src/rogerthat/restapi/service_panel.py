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

import logging
from types import NoneType

from rogerthat.bizz.branding import BrandingInUseException
from rogerthat.bizz.friends import invite, ORIGIN_USER_INVITE
from rogerthat.bizz.i18n import DummyTranslator
from rogerthat.bizz.service import InvalidValueException, BeaconAlreadyCoupledException, \
    get_and_validate_app_id_for_service_identity_user, valididate_app_id_for_service_identity_user
from rogerthat.bizz.service.broadcast import ConfirmationNeededException
from rogerthat.dal import parent_key
from rogerthat.dal.app import get_visible_apps
from rogerthat.dal.mfd import get_service_message_flow_designs, get_service_message_flow_design_key_by_name, \
    get_message_flow_designs_by_status
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.service import get_service_log, get_service_interaction_defs, get_service_identity, \
    get_service_identities, get_users_connected_to_service_identity, get_service_identity_not_cached
from rogerthat.models import Branding, QRTemplate, ServiceIdentity, MessageFlowDesign
from rogerthat.rpc import users
from rogerthat.rpc.service import BusinessException
from rogerthat.to import ReturnStatusTO, RETURNSTATUS_TO_SUCCESS
from rogerthat.to.app import AppTO
from rogerthat.to.branding import BrandingTO
from rogerthat.to.friends import WebServiceMenuTO
from rogerthat.to.qr import QRReturnStatusTO
from rogerthat.to.qrtemplates import QRTemplateTO
from rogerthat.to.roles import RoleTO, GrantTO
from rogerthat.to.service import ServiceConfigurationTO, ServiceLogTO, GetServiceUsersResponseTO, ServiceUserTO, \
    GetServiceInteractionDefsResponseTO, ServiceInteractionDefTO, MessageFlowDesignTO, LibraryMenuIconTO, \
    ServiceIdentityDetailsTO, ServiceIdentitySummaryTO, ServiceLanguagesTO, MessageFlowListTO, \
    ServiceBroadCastConfigurationTO, BroadcastTestPersonReturnStatusTO, UserDetailsTO, TestBroadcastReturnStatusTO, \
    BroadcastTO, DeleteBroadcastTypeReturnStatusTO
from rogerthat.utils import azzert
from rogerthat.utils.app import create_app_user, create_app_user_by_email
from rogerthat.utils.service import create_service_identity_user
from mcfw.restapi import rest
from mcfw.rpc import arguments, returns


@rest("/mobi/rest/service/get_configuration", "get")
@returns(ServiceConfigurationTO)
@arguments()
def get_configuration():
    from rogerthat.bizz.service import get_configuration as get_configuration_bizz
    user = users.get_current_user()
    return get_configuration_bizz(user)

@rest("/mobi/rest/service/get_translation_configuration", "get")
@returns(ServiceLanguagesTO)
@arguments()
def get_translation_configuration():
    from rogerthat.bizz.service import get_service_translation_configuration
    service_user = users.get_current_user()
    return get_service_translation_configuration(service_user)

@rest("/mobi/rest/service/configure_mobidick", "post")
@returns(NoneType)
@arguments(user=users.User)
def configure_mobidick(user):
    from rogerthat.bizz.service import configure_mobidick as configure_mobidick_bizz
    service_user = users.get_current_user()
    return configure_mobidick_bizz(service_user)

@rest("/mobi/rest/service/convert_to_service", "post")
@returns(NoneType)
@arguments()
def convert_to_service():
    from rogerthat.bizz.service import convert_user_to_service as convert_user_to_service_bizz
    user = users.get_current_user()
    return convert_user_to_service_bizz(user)

@rest("/mobi/rest/service/generate_api_key", "post")
@returns(ServiceConfigurationTO)
@arguments(name=unicode)
def generate_api_key(name):
    from rogerthat.bizz.service import generate_api_key as generate_api_key_bizz
    service_user = users.get_current_user()
    return generate_api_key_bizz(service_user, name)

@rest("/mobi/rest/service/delete_api_key", "post")
@returns(ServiceConfigurationTO)
@arguments(key=unicode)
def delete_api_key(key):
    from rogerthat.bizz.service import delete_api_key as delete_api_key_bizz
    service_user = users.get_current_user()
    return delete_api_key_bizz(service_user, key)

@rest("/mobi/rest/service/enable", "post")
@returns(ServiceConfigurationTO)
@arguments()
def enable_service():
    from rogerthat.bizz.service import enable_service as enable_service_bizz
    service_user = users.get_current_user()
    return enable_service_bizz(service_user)

@rest("/mobi/rest/service/disable", "post")
@returns(ServiceConfigurationTO)
@arguments()
def disable_service():
    from rogerthat.bizz.service import disable_service as disable_service_bizz
    service_user = users.get_current_user()
    return disable_service_bizz(service_user, "Administrator intervention of %s." % service_user.email())

@rest("/mobi/rest/service/update_callback_configuration", "post")
@returns(ServiceConfigurationTO)
@arguments(httpURI=unicode, xmppJID=unicode)
def update_callback_configuration(httpURI, xmppJID):
    from rogerthat.bizz.service import update_callback_configuration as update_callback_configuration_bizz
    service_user = users.get_current_user()
    return update_callback_configuration_bizz(service_user, httpURI, xmppJID)

@rest("/mobi/rest/service/enable_callback", "post")
@returns(NoneType)
@arguments(callback=int, enabled=bool)
def enable_callback(callback, enabled):
    from rogerthat.bizz.service import enable_callback as enable_callback_bizz
    service_user = users.get_current_user()
    enable_callback_bizz(service_user, callback, enabled)

@rest("/mobi/rest/service/set_supported_language", "post")
@returns(ServiceConfigurationTO)
@arguments(language=unicode, enabled=bool)
def set_supported_language(language, enabled):
    from rogerthat.bizz.service import set_supported_language as set_supported_language_bizz
    service_user = users.get_current_user()
    return set_supported_language_bizz(service_user, language, enabled)

@rest("/mobi/rest/service/regenerate_sik", "post")
@returns(ServiceConfigurationTO)
@arguments()
def regenerate_sik():
    from rogerthat.bizz.service import regenerate_sik as regenerate_sik_bizz
    service_user = users.get_current_user()
    return regenerate_sik_bizz(service_user)

@rest("/mobi/rest/service/perform_test_callback", "post")
@returns(ServiceConfigurationTO)
@arguments()
def perform_test_callback():
    from rogerthat.bizz.service import perform_test_callback as perform_test_callback_bizz
    service_user = users.get_current_user()
    from google.appengine.api.memcache import set  # @UnresolvedImport
    set(service_user.email() + "_interactive_logs", True, 300)
    return perform_test_callback_bizz(service_user)

@rest("/mobi/rest/branding/list", "get", silent_result=True)
@returns([BrandingTO])
@arguments(filtered_type=int)
def get_branding_list(filtered_type=Branding.TYPE_NORMAL):
    service_user = users.get_current_user()
    query = Branding.all().filter("user =", service_user)
    if filtered_type > 0:
        query.filter("type =", filtered_type)
    brandings = [BrandingTO.fromDBBranding(branding) for branding in query if branding.timestamp > 0]
    return sorted(brandings, key=lambda i: (i.description.upper(), -i.timestamp))

@rest("/mobi/rest/qrtemplates/list", "get")
@returns([QRTemplateTO])
@arguments()
def get_qr_template_list():
    service_user = users.get_current_user()
    templates = [QRTemplateTO.fromDBQRTemplate(template) for template in QRTemplate.gql("WHERE deleted = False AND ANCESTOR is :1", parent_key(service_user))]
    return sorted(templates, key=lambda i:i.description.upper())

@rest("/mobi/rest/branding/delete", "post")
@returns(unicode)
@arguments(key=unicode)
def delete_branding(key):
    from rogerthat.bizz.branding import delete_branding as bizz_delete_branding
    service_user = users.get_current_user()
    try:
        bizz_delete_branding(service_user, key)
    except BrandingInUseException, e:
        return e.message

@rest("/mobi/rest/qrtemplates/delete", "post")
@returns(NoneType)
@arguments(key=unicode)
def delete_qr_template(key):
    service_user = users.get_current_user()
    template = QRTemplate.get_by_id(int(key[2:], 16), parent_key(service_user))
    azzert(template.user == users.get_current_user())
    template.deleted = True
    template.put()

@rest("/mobi/rest/service/logs", "get")
@returns([ServiceLogTO])
@arguments(timestamp=int)
def get_logs(timestamp):
    service_user = users.get_current_user()
    return [ServiceLogTO.fromServiceLog(sl) for sl in get_service_log(service_user, timestamp)]

@rest("/mobi/rest/service/identities", "get")
@returns([ServiceIdentitySummaryTO])
@arguments()
def get_identities():
    service_user = users.get_current_user()
    return [ServiceIdentitySummaryTO.fromServiceIdentity(si) for si in get_service_identities(service_user)]

@rest("/mobi/rest/service/users", "get")
@returns(GetServiceUsersResponseTO)
@arguments(service_identity=unicode, cursor=unicode)
def get_users(service_identity, cursor):
    service_user = users.get_current_user()
    service_identity_user = create_service_identity_user(service_user, service_identity)

    fsics, cursor = get_users_connected_to_service_identity(service_identity_user, cursor)
    result = GetServiceUsersResponseTO()
    result.users = [ServiceUserTO.fromFriendServiceIdentityConnection(fsic) for fsic in fsics]
    result.cursor = unicode(cursor)
    return result

@rest("/mobi/rest/service/admin/roles", "get")
@returns([unicode])
@arguments()
def get_admin_roles():
    from rogerthat.bizz.roles import ROLES
    return list(ROLES)

@rest("/mobi/rest/service/admin/roles/grant", "post")
@returns(ReturnStatusTO)
@arguments(user_email=unicode, role=unicode, identity=unicode)
def grant_admin_role(user_email, role, identity):
    service_user = users.get_current_user()
    service_identity_user = create_service_identity_user(service_user, identity)
    from rogerthat.bizz.roles import grant_role as grant_role_bizz
    try:
        grant_role_bizz(service_identity_user, users.User(user_email), role)
        return RETURNSTATUS_TO_SUCCESS
    except BusinessException, e:
        return ReturnStatusTO.create(False, e.message)

@rest("/mobi/rest/service/admin/roles/revoke", "post")
@returns(NoneType)
@arguments(user_email=unicode, role=unicode, identity=unicode)
def revoke_admin_role(user_email, role, identity):
    service_user = users.get_current_user()
    service_identity_user = create_service_identity_user(service_user, identity)
    from rogerthat.bizz.roles import revoke_role as revoke_role_bizz
    revoke_role_bizz(service_identity_user, users.User(user_email), role)

@rest("/mobi/rest/service/grants", "get")
@returns([GrantTO])
@arguments()
def get_service_grants():
    from rogerthat.dal.roles import get_service_grants as get_service_grants_dal
    service_user = users.get_current_user()
    return get_service_grants_dal(service_user)

@rest("/mobi/rest/service/roles/create", "post")
@returns(long)
@arguments(name=unicode, type_=unicode)
def create_service_role(name, type_):
    service_user = users.get_current_user()
    from rogerthat.bizz.roles import create_service_role as create_service_role_bizz
    role = create_service_role_bizz(service_user, name, type_)
    return role.role_id

@rest("/mobi/rest/service/roles/delete", "post")
@returns(ReturnStatusTO)
@arguments(role_id=(int, long))
def delete_service_role(role_id):
    service_user = users.get_current_user()
    from rogerthat.bizz.roles import delete_service_role as delete_service_role_bizz
    try:
        delete_service_role_bizz(service_user, role_id)
        return RETURNSTATUS_TO_SUCCESS
    except BusinessException, be:
        return ReturnStatusTO.create(False, be.message)

@rest("/mobi/rest/service/roles/grant", "post")
@returns(NoneType)
@arguments(identity=unicode, app_user_email=unicode, role_id=(int, long))
def grant_service_role(identity, app_user_email, role_id):
    service_user = users.get_current_user()
    app_user = create_app_user_by_email(*app_user_email.rsplit(':', 1))
    from rogerthat.bizz.roles import grant_service_role as grant_service_role_bizz
    grant_service_role_bizz(service_user, identity, app_user, role_id)

@rest("/mobi/rest/service/roles/revoke", "post")
@returns(NoneType)
@arguments(identity=unicode, app_user_email=unicode, role_id=(int, long))
def revoke_service_role(identity, app_user_email, role_id):
    service_user = users.get_current_user()
    app_user = create_app_user_by_email(*app_user_email.rsplit(':', 1))
    from rogerthat.bizz.roles import revoke_service_role as revoke_service_role_bizz
    revoke_service_role_bizz(service_user, identity, app_user, role_id)

@rest("/mobi/rest/service/roles", "get")
@returns([RoleTO])
@arguments()
def list_service_roles():
    service_user = users.get_current_user()
    from rogerthat.dal.roles import list_service_roles as list_service_roles_dal
    return map(RoleTO.fromServiceRole, list_service_roles_dal(service_user))

@rest("/mobi/rest/qr/create", "post")
@returns(QRReturnStatusTO)
@arguments(description=unicode, tag=unicode, template_key=unicode, service_identity=unicode, static_flow=unicode,
           branding=unicode)
def qr_create(description, tag, template_key, service_identity, static_flow, branding=None):
    from rogerthat.bizz.service import create_qr
    service_user = users.get_current_user()
    r = QRReturnStatusTO()
    try:
        r.qr_details = create_qr(service_user, description, tag, template_key, service_identity, static_flow, branding)
        r.success = True
        r.errormsg = None
    except BusinessException, be:
        r.qr_details = None
        r.success = False
        r.errormsg = be.message.decode('UTF-8') if be.message is not None else None
    return r

@rest("/mobi/rest/qr/delete", "post")
@returns(NoneType)
@arguments(sid=(int, long))
def qr_delete(sid):
    from rogerthat.bizz.service import delete_qr
    service_user = users.get_current_user()
    delete_qr(service_user, sid)

@rest("/mobi/rest/qr/edit", "post")
@returns(ReturnStatusTO)
@arguments(sid=(int, long), description=unicode, tag=unicode, static_flow=unicode, branding=unicode)
def qr_edit(sid, description, tag, static_flow, branding):
    from rogerthat.bizz.service import update_qr
    service_user = users.get_current_user()
    update_qr(service_user, sid, description, tag, static_flow, branding)
    return RETURNSTATUS_TO_SUCCESS

@rest("/mobi/rest/qr/list", "get")
@returns(GetServiceInteractionDefsResponseTO)
@arguments(cursor=unicode, identifier=unicode)
def qr_list(cursor, identifier=None):
    svc_user = users.get_current_user()
    result = get_service_interaction_defs(svc_user, identifier, cursor)
    defs = result['defs']
    cursor = result['cursor']
    result = GetServiceInteractionDefsResponseTO()
    result.defs = [ServiceInteractionDefTO.fromServiceInteractionDef(sid) for sid in defs]
    result.cursor = unicode(cursor)
    return result

@rest("/mobi/rest/mfd/list", "get")
@returns(MessageFlowListTO)
@arguments(with_design_only=bool)
def message_flow_designs(with_design_only=False):
    service_user = users.get_current_user()
    mfds = (mfd for mfd in get_service_message_flow_designs(service_user) if not with_design_only or mfd.definition)
    result = MessageFlowListTO()
    result.message_flows = sorted(map(MessageFlowDesignTO.fromMessageFlowDesign, mfds),
                                  key=lambda mfd: (not mfd.multilanguage, mfd.name.upper()))
    result.service_languages = get_service_profile(service_user).supportedLanguages
    return result

@rest("/mobi/rest/mfd/list_valid", "get")
@returns(MessageFlowListTO)
@arguments()
def valid_message_flow_designs():
    service_user = users.get_current_user()
    mfds = get_message_flow_designs_by_status(service_user, MessageFlowDesign.STATUS_VALID)
    result = MessageFlowListTO()
    result.message_flows = sorted(map(MessageFlowDesignTO.fromMessageFlowDesign, mfds),
                                  key=lambda mfd: mfd.name.upper())
    result.service_languages = []
    return result

@rest("/mobi/rest/mfd/test", "post")
@returns(unicode)
@arguments(message_flow_design_name=unicode, member=unicode, force_language=unicode, app_id=unicode)
def test_message_flow(message_flow_design_name, member, force_language=None, app_id=None):
    from rogerthat.bizz.service.mfr import start_flow, MessageFlowNotValidException, NonFriendMembersException
    service_user = users.get_current_user()
    default_service_identity_user = create_service_identity_user(service_user, ServiceIdentity.DEFAULT)
    app_id = get_and_validate_app_id_for_service_identity_user(default_service_identity_user, app_id)
    app_user = create_app_user(users.User(member), app_id)
    try:
        start_flow(default_service_identity_user, None, unicode(get_service_message_flow_design_key_by_name(service_user, message_flow_design_name)), \
               [app_user], True, False, force_language=force_language)
    except MessageFlowNotValidException, e:
        return "Message flow could not be started!\n%s" % (e.fields['error'] or '')
    except NonFriendMembersException, e:
        try:
            invite(default_service_identity_user, member, "", "", None, None, origin=ORIGIN_USER_INVITE, app_id=app_id)
            return "Message flow could not be started!\n%s is not a user of this service. An invitation has been sent." % member
        except Exception, e:
            logging.exception("Invite failed.")
            return "Message flow could not be started!\n%s is not a user of this service. Rogerthat tried to send an invitation, but this failed with message '%s'!" % (member, unicode(e))
    except BusinessException, be:
        return "Message flow could not be started!\n%s" % be.message

@rest("/mobi/rest/service/icon-library/list", "get", silent_result=True)
@returns([LibraryMenuIconTO])
@arguments()
def list_icon_library():
    from rogerthat.bizz.service import list_icon_library as list_icon_library_bizz
    return list_icon_library_bizz(users.get_current_user())

@rest("/mobi/rest/service/menu/create", "post")
@returns(ReturnStatusTO)
@arguments(icon_name=unicode, icon_color=unicode, label=unicode, tag=unicode, coords=[int], screen_branding=unicode,
           static_flow=unicode, is_broadcast_settings=bool, broadcast_branding=unicode, requires_wifi=bool,
           run_in_background=bool, roles=[(int, long)])
def create_menu_item(icon_name, icon_color, label, tag, coords, screen_branding, static_flow, is_broadcast_settings,
                     broadcast_branding, requires_wifi, run_in_background, roles):
    from rogerthat.bizz.service import create_menu_item as create_menu_item_bizz
    service_user = users.get_current_user()
    try:
        create_menu_item_bizz(service_user, icon_name, icon_color, label, tag, coords, screen_branding, static_flow,
                              requires_wifi, run_in_background, roles, is_broadcast_settings, broadcast_branding)
        return RETURNSTATUS_TO_SUCCESS
    except InvalidValueException, e:
        return ReturnStatusTO.create(False, e.fields.get('reason') or e.message)
    except BusinessException, be:
        return ReturnStatusTO.create(False, be.message)

@rest("/mobi/rest/service/menu/move", "post")
@returns(NoneType)
@arguments(source_coords=[int], target_coords=[int])
def move_menu_item(source_coords, target_coords):
    from rogerthat.bizz.service import move_menu_item as move_menu_item_bizz
    service_user = users.get_current_user()
    move_menu_item_bizz(service_user, source_coords, target_coords)

@rest("/mobi/rest/service/menu/delete", "post")
@returns(NoneType)
@arguments(coords=[int])
def delete_menu_item(coords):
    from rogerthat.bizz.service import delete_menu_item as delete_menu_item_bizz
    service_user = users.get_current_user()
    delete_menu_item_bizz(service_user, coords)

@rest("/mobi/rest/service/menu/item_label", "post")
@returns(NoneType)
@arguments(column=int, label=unicode)
def set_reserved_item_caption(column, label):
    from rogerthat.bizz.service import set_reserved_item_caption as set_reserved_item_caption_bizz
    service_user = users.get_current_user()
    set_reserved_item_caption_bizz(service_user, column, label)

@rest("/mobi/rest/service/menu", "get")
@returns(WebServiceMenuTO)
@arguments(identifier=unicode)
def get_menu(identifier):
    service_user = users.get_current_user()
    service_identity_user = create_service_identity_user(service_user, identifier)
    service_identity = get_service_identity(service_identity_user)
    dummy_translator = DummyTranslator(get_service_profile(service_user).defaultLanguage)
    sm = WebServiceMenuTO.fromServiceIdentity(service_identity, dummy_translator.default_language, dummy_translator)
    return sm

@rest("/mobi/rest/service/identity", "get")
@returns(ServiceIdentityDetailsTO)
@arguments(identifier=unicode)
def get_service_identity_details(identifier):
    azzert(identifier)
    service_user = users.get_current_user()
    service_identity_user = create_service_identity_user(service_user, identifier)
    service_identity = get_service_identity_not_cached(service_identity_user)
    service_profile = get_service_profile(service_user, cached=False)
    return ServiceIdentityDetailsTO.fromServiceIdentity(service_identity, service_profile)

@rest("/mobi/rest/service/identity_create", "post")
@returns(ReturnStatusTO)
@arguments(details=ServiceIdentityDetailsTO)
def create_service_identity(details):
    from rogerthat.bizz.service import create_service_identity as create_service_identity_bizz

    try:
        create_service_identity_bizz(users.get_current_user(), details)
    except BusinessException, be:
        logging.warn(be.message, exc_info=True)
        return ReturnStatusTO.create(False, be.message)
    except:
        logging.exception("Error")
        return ReturnStatusTO.create(False, "An error occurred")

    return RETURNSTATUS_TO_SUCCESS


@rest("/mobi/rest/service/identity_update", "post")
@returns(ReturnStatusTO)
@arguments(details=ServiceIdentityDetailsTO)
def update_service_identity(details):
    from rogerthat.bizz.service import update_service_identity as update_service_identity_bizz

    try:
        update_service_identity_bizz(users.get_current_user(), details)
    except InvalidValueException, ive:
        reason = ive.fields['reason']
        logging.debug("%s: %s", ive.message, ive.fields, exc_info=True)
        return ReturnStatusTO.create(False, reason)
    except BeaconAlreadyCoupledException, bace:
        reason = u"This beacon is already assigned to another service.\nUUID: %s\nMajor: %s\nMinor: %s" % \
                                        (bace.fields['uuid'], \
                                         bace.fields['major'], \
                                         bace.fields['minor'])
        logging.debug("%s: %s", bace.message, bace.fields, exc_info=True)
        return ReturnStatusTO.create(False, reason)
    except BusinessException, be:
        logging.warn(be.message, exc_info=True)
        return ReturnStatusTO.create(False, be.message)
    except:
        logging.exception("Error")
        return ReturnStatusTO.create(False, "An error occurred")

    return RETURNSTATUS_TO_SUCCESS


@rest("/mobi/rest/service/identity_delete", "post")
@returns(ReturnStatusTO)
@arguments(identifier=unicode)
def delete_service_identity(identifier):
    from rogerthat.bizz.service import delete_service_identity as delete_service_identity_bizz

    try:
        delete_service_identity_bizz(users.get_current_user(), identifier)
    except BusinessException, be:
        logging.warn(be.message, exc_info=True)
        return ReturnStatusTO.create(False, be.message)
    except:
        logging.exception("Error")
        return ReturnStatusTO.create(False, "An error occurred")

    return RETURNSTATUS_TO_SUCCESS


@rest("/mobi/rest/service/broadcast_configuration", "get")
@returns(ServiceBroadCastConfigurationTO)
@arguments()
def get_broadcast_configuration():
    from rogerthat.dal.service import list_broadcasts as dal_list_broadcasts
    service_user = users.get_current_user()
    service_profile = get_service_profile(service_user)
    broadcasts = dal_list_broadcasts(users.get_current_user())
    return ServiceBroadCastConfigurationTO.fromServiceProfile(service_profile, broadcasts)

@rest("/mobi/rest/service/add_broadcast_type", "post")
@returns(ReturnStatusTO)
@arguments(broadcast_type=unicode)
def add_broadcast_type(broadcast_type):
    from rogerthat.bizz.service.broadcast import add_broadcast_type as bizz_add_broadcast_type
    try:
        bizz_add_broadcast_type(users.get_current_user(), broadcast_type)
        return RETURNSTATUS_TO_SUCCESS
    except BusinessException, be:
        return ReturnStatusTO.create(False, be.message)

@rest("/mobi/rest/service/rm_broadcast_type", "post")
@returns(ReturnStatusTO)
@arguments(broadcast_type=unicode, force=bool)
def rm_broadcast_type(broadcast_type, force):
    from rogerthat.bizz.service.broadcast import delete_broadcast_type
    r = DeleteBroadcastTypeReturnStatusTO()
    try:
        delete_broadcast_type(users.get_current_user(), broadcast_type, force)
    except ConfirmationNeededException, e:
        r.success = False
        r.errormsg = None
        r.confirmation = e.message.decode('UTF-8') if e.message is not None else None
    except BusinessException, be:
        r.success = False
        r.errormsg = be.message.decode('UTF-8') if be.message is not None else None
        r.confirmation = None
    else:
        r.success = True
        r.errormsg = None
        r.confirmation = None
    return r

@rest("/mobi/rest/service/add_broadcast_test_person", "post")
@returns(BroadcastTestPersonReturnStatusTO)
@arguments(email=unicode, app_id=unicode)
def add_broadcast_test_person(email, app_id=None):
    from rogerthat.bizz.service.broadcast import add_broadcast_test_person as bizz_add_broadcast_test_person
    r = BroadcastTestPersonReturnStatusTO()
    service_user = users.get_current_user()
    default_service_identity_user = create_service_identity_user(service_user, ServiceIdentity.DEFAULT)
    app_id = get_and_validate_app_id_for_service_identity_user(default_service_identity_user, app_id)
    try:
        user_profile = bizz_add_broadcast_test_person(service_user, create_app_user(users.User(email), app_id))
        r.user_details = UserDetailsTO.fromUserProfile(user_profile)
        r.success = True
        r.errormsg = None
    except BusinessException, be:
        r.user_details = None
        r.success = False
        r.errormsg = be.message.decode('UTF-8') if be.message is not None else None
    return r

@rest("/mobi/rest/service/rm_broadcast_test_person", "post")
@returns(ReturnStatusTO)
@arguments(email=unicode, app_id=unicode)
def rm_broadcast_test_person(email, app_id=None):
    from rogerthat.bizz.service.broadcast import delete_broadcast_test_person
    service_user = users.get_current_user()
    default_service_identity_user = create_service_identity_user(service_user, ServiceIdentity.DEFAULT)
    app_id = get_and_validate_app_id_for_service_identity_user(default_service_identity_user, app_id)
    try:
        delete_broadcast_test_person(users.get_current_user(), create_app_user(users.User(email), app_id))
        return RETURNSTATUS_TO_SUCCESS
    except BusinessException, be:
        return ReturnStatusTO.create(False, be.message)

@rest("/mobi/rest/service/search_connected_users", "get")
@returns([UserDetailsTO])
@arguments(name_or_email_term=unicode, app_id=unicode, service_identity=unicode)
def search_connected_users(name_or_email_term, app_id=None, service_identity=None):
    from rogerthat.bizz.profile import search_users_via_friend_connection_and_name_or_email
    service_user = users.get_current_user()
    if service_identity is None:
        service_identity = ServiceIdentity.DEFAULT
    service_identity_user = create_service_identity_user(service_user, service_identity)
    if app_id is not None:
        valididate_app_id_for_service_identity_user(service_identity_user, app_id)

    return search_users_via_friend_connection_and_name_or_email(service_user.email() if service_identity is None else service_identity_user.email(), name_or_email_term, app_id)

@rest("/mobi/rest/service/search_users", "get")
@returns([UserDetailsTO])
@arguments(term=unicode, app_id=unicode, admin=bool)
def search_users(term, app_id=None, admin=False):
    from rogerthat.bizz.profile import search_users_via_name_or_email
    service_user = users.get_current_user()
    default_service_identity_user = create_service_identity_user(service_user, ServiceIdentity.DEFAULT)
    if not admin and app_id is not None:
        valididate_app_id_for_service_identity_user(default_service_identity_user, app_id)
    return sorted(search_users_via_name_or_email(term, app_id),
                  key=lambda x: (x.app_id, x.name.upper()))

@rest("/mobi/rest/service/send_broadcast", "post")
@returns(ReturnStatusTO)
@arguments(broadcast_key=unicode)
def send_broadcast(broadcast_key):
    from rogerthat.bizz.service.broadcast import send_broadcast as bizz_send_broadcast
    try:
        bizz_send_broadcast(users.get_current_user(), broadcast_key)
        return RETURNSTATUS_TO_SUCCESS
    except BusinessException, be:
        return ReturnStatusTO.create(False, be.message)

@rest("/mobi/rest/service/schedule_broadcast", "post")
@returns(ReturnStatusTO)
@arguments(broadcast_key=unicode, timestamp=int)
def schedule_broadcast(broadcast_key, timestamp):
    from rogerthat.bizz.service.broadcast import schedule_broadcast as bizz_schedule_broadcast
    try:
        bizz_schedule_broadcast(users.get_current_user(), broadcast_key, timestamp)
        return RETURNSTATUS_TO_SUCCESS
    except BusinessException, be:
        return ReturnStatusTO.create(False, be.message)

@rest("/mobi/rest/service/test_broadcast", "post")
@returns(TestBroadcastReturnStatusTO)
@arguments(name=unicode, broadcast_type=unicode, message_flow_id=unicode, tag=unicode)
def test_broadcast(name, broadcast_type, message_flow_id, tag):
    from rogerthat.bizz.service.broadcast import test_broadcast as bizz_test_broadcast
    serivce_user = users.get_current_user()
    r = TestBroadcastReturnStatusTO()
    try:
        broadcast = bizz_test_broadcast(serivce_user, name, broadcast_type, message_flow_id, tag)
        r.broadcast = BroadcastTO.fromBroadcast(broadcast)
        r.success = True
        r.errormsg = None
    except BusinessException, be:
        r.broadcast = None
        r.success = False
        r.errormsg = be.message.decode("UTF-8") if be.message is not None else None
    return r

@rest("/mobi/rest/service/rm_broadcast", "post")
@returns(ReturnStatusTO)
@arguments(broadcast_key=unicode)
def rm_broadcast(broadcast_key):
    from rogerthat.bizz.service.broadcast import delete_broadcast
    try:
        delete_broadcast(users.get_current_user(), broadcast_key)
        return RETURNSTATUS_TO_SUCCESS
    except BusinessException, be:
        return ReturnStatusTO.create(False, be.message)

@rest("/mobi/rest/service/publish_changes", "post")
@returns(NoneType)
@arguments()
def publish_changes():
    from rogerthat.bizz.service import publish_changes as bizz_publish_changes
    bizz_publish_changes(users.get_current_user())


@rest("/mobi/rest/service/apps", "get")
@returns([AppTO])
@arguments()
def get_service_visible_apps():
    return sorted(map(AppTO.fromModel, get_visible_apps()), key=lambda app: app.name.lower())
