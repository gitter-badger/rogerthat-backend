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
import logging
import os
import urllib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from types import NoneType
from zipfile import ZipFile

from google.appengine.api import images, search
from google.appengine.ext import db, deferred

from mcfw.cache import cached
from mcfw.consts import MISSING
from mcfw.imaging import recolor_png
from mcfw.rpc import arguments, returns, serialize_complex_value
from mcfw.utils import normalize_search_string, chunks
from rogerthat.bizz.beacon import update_beacons
from rogerthat.bizz.friends import userCode, invited_response_receiver, process_invited_response, \
    create_accept_decline_buttons, INVITE_SERVICE_ADMIN, _defer_update_friend
from rogerthat.bizz.i18n import check_i18n_status_of_message_flows, get_translator
from rogerthat.bizz.job.update_friends import schedule_update_all_friends_of_service_user, send_update_friend_request
from rogerthat.bizz.messaging import BrandingNotFoundException, sendMessage, sendForm
from rogerthat.bizz.messaging import ReservedTagException
from rogerthat.bizz.profile import update_friends, create_user_profile, update_password_hash, _validate_name, \
    create_service_profile
from rogerthat.bizz.qrtemplate import store_template
from rogerthat.bizz.rtemail import generate_auto_login_url, EMAIL_REGEX
from rogerthat.bizz.service.mfd import get_message_flow_by_key_or_name
from rogerthat.bizz.service.mfd.gen import MessageFlowRun
from rogerthat.bizz.system import unregister_mobile
from rogerthat.capi.services import receiveApiCallResult
from rogerthat.consts import MC_DASHBOARD
from rogerthat.consts import OFFICIALLY_SUPPORTED_LANGUAGES, \
    MC_RESERVED_TAG_PREFIX, FA_ICONS
from rogerthat.dal import parent_key, put_and_invalidate_cache
from rogerthat.dal.app import get_app_by_user, get_default_app, get_app_by_id
from rogerthat.dal.friend import get_friends_map, get_friends_map_key_by_user, get_friend_category_by_id
from rogerthat.dal.messaging import get_message, get_branding
from rogerthat.dal.mfd import get_service_message_flow_design_key_by_name
from rogerthat.dal.mobile import get_user_active_mobiles
from rogerthat.dal.profile import get_search_config, is_trial_service, get_service_profile, get_user_profile, \
    get_profile_infos, get_profile_info, is_service_identity_user, get_trial_service_by_account, get_search_locations, \
    get_service_or_user_profile, get_profile_key
from rogerthat.dal.roles import get_service_admins, get_service_identities_via_user_roles, get_service_roles_by_ids
from rogerthat.dal.service import get_api_keys, get_api_key, get_api_key_count, get_sik, get_service_interaction_def, \
    get_service_menu_item_by_coordinates, get_service_identity, get_friend_serviceidentity_connection, \
    get_default_service_identity, get_service_identity_not_cached, get_service_identities, get_child_identities, \
    get_service_interaction_defs, get_users_connected_to_service_identity, log_service_activity, \
    get_service_identities_by_service_identity_users
from rogerthat.models import Profile, APIKey, SIKKey, ServiceEmail, ServiceInteractionDef, ShortURL, \
    QRTemplate, Message, MFRSIKey, ServiceMenuDef, Branding, PokeTagMap, ServiceProfile, UserProfile, ServiceIdentity, \
    SearchConfigLocation, ProfilePointer, FacebookProfilePointer, MessageFlowDesign, ServiceTranslation, \
    ServiceMenuDefTagMap, UserData, FacebookUserProfile, App, MessageFlowRunRecord, \
    FriendServiceIdentityConnection
from rogerthat.models.properties.keyvalue import KVStore, InvalidKeyError
from rogerthat.rpc import users
from rogerthat.rpc.models import ServiceAPICallback, ServiceLog, RpcCAPICall
from rogerthat.rpc.rpc import mapping, logError
from rogerthat.rpc.service import logServiceError, ServiceApiException, ERROR_CODE_UNKNOWN_ERROR, \
    ERROR_CODE_WARNING_THRESHOLD, BusinessException, SERVICE_API_CALLBACK_MAPPING
from rogerthat.service.api.friends import invited
from rogerthat.service.api.test import test
from rogerthat.settings import get_server_settings
from rogerthat.templates import render
from rogerthat.to.activity import GeoPointWithTimestampTO, GEO_POINT_FACTOR
from rogerthat.to.friends import UpdateFriendRequestTO, FriendTO, ServiceMenuDetailTO
from rogerthat.to.messaging import UserMemberTO
from rogerthat.to.messaging.service_callback_results import PokeCallbackResultTO, FlowCallbackResultTypeTO, \
    MessageCallbackResultTypeTO, FormCallbackResultTypeTO
from rogerthat.to.profile import SearchConfigTO
from rogerthat.to.qr import QRDetailsTO
from rogerthat.to.service import ServiceConfigurationTO, APIKeyTO, LibraryMenuIconTO, FindServiceResponseTO, \
    FindServiceItemTO, FindServiceCategoryTO, ServiceIdentityDetailsTO, ServiceLanguagesTO, UserDetailsTO, \
    ReceiveApiCallResultResponseTO, ReceiveApiCallResultRequestTO, SendApiCallCallbackResultTO, \
    ServiceCallbackConfigurationTO, UpdateUserDataResponseTO
from rogerthat.translations import localize, DEFAULT_LANGUAGE
from rogerthat.utils import now, channel, generate_random_key, azzert, parse_color, slog, \
    is_flag_set, get_full_language_string, get_officially_supported_languages, try_or_defer, \
    bizz_check, send_mail_via_mime, base38
from rogerthat.utils.app import get_human_user_from_app_user, get_app_id_from_app_user
from rogerthat.utils.crypto import md5_hex, sha256_hex
from rogerthat.utils.languages import convert_web_lang_to_iso_lang
from rogerthat.utils.location import haversine, VERY_FAR
from rogerthat.utils.service import get_service_user_from_service_identity_user, create_service_identity_user, \
    get_service_identity_tuple, is_valid_service_identifier, remove_slash_default
from rogerthat.utils.transactions import run_in_transaction, run_in_xg_transaction, on_trans_committed

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

CURRENT_DIR = os.path.dirname(__file__)
ICON_LIBRARY_PATH = os.path.join(CURRENT_DIR, 'icons.zip')

SERVICE_INDEX = "SERVICE_INDEX"
SERVICE_LOCATION_INDEX = "SERVICE_LOCATION_INDEX"

SERVICE_IN_TROUBLE_TAG = u"service_trouble"
IGNORE_SERVICE_TROUBLE_ID = u"ignore_service_trouble"
DISABLE_SERVICE_TROUBLE_ID = u"disable_service_trouble"

MENU_ITEM_LABEL_ATTRS = ['aboutMenuItemLabel', 'messagesMenuItemLabel', 'callMenuItemLabel', 'shareMenuItemLabel']

QR_TEMPLATE_BLUE_PACIFIC = u"Blue Pacific"
QR_TEMPLATE_BROWN_BAG = u"Brown Bag"
QR_TEMPLATE_PINK_PANTHER = u"Pink Panther"
QR_TEMPLATE_BLACK_HAND = u"Black Hand"


class TestCallbackFailedException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_TEST + 0, "Test callback failed")


class ServiceIdentityDoesNotExistException(ServiceApiException):
    def __init__(self, service_identity):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 0,
                                     u"Service identity does not exist", service_identity=service_identity)


class InvalidValueException(ServiceApiException):
    def __init__(self, property_, reason):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 1,
                                     u"Invalid value", property=property_, reason=reason)


class InvalidMenuItemCoordinatesException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 2,
                                     u"A menu item has an x, y and page coordinate, with x and y smaller than 4")


class ReservedMenuItemException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 3,
                                     u"This menu item is reserved")


class CanNotDeleteBroadcastTypesException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 4,
                                     u"There are still broadcast settings menu items.")


class InvalidBroadcastTypeException(ServiceApiException):
    def __init__(self, broadcast_type):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 5,
                                     u"Invalid broadcast type", broadcast_type=broadcast_type)


class DuplicateBroadcastTypeException(ServiceApiException):
    def __init__(self, broadcast_type):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 6,
                                     u"Duplicate broadcast type", broadcast_type=broadcast_type)


class CreateServiceDeniedException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 7,
                                     u"No permission to create services")


class InvalidNameException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 8,
                                     u"Invalid name")


class ServiceAlreadyExistsException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 9,
                                     u"Service with that e-mail address already exists")


class UnsupportedLanguageException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 10,
                                     u"This language is not supported")


class FriendNotFoundException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 11,
                                     u"User not in friends list")


class InvalidJsonStringException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 12,
                                     u"Can not parse data as json object")


class AvatarImageNotSquareException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 13,
                                     u"Expected a square input image")


class CategoryNotFoundException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 14,
                                     u"Category not found")


class CallbackNotDefinedException(ServiceApiException):
    def __init__(self, function):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 15,
                                     u"Callback not defined", function=function)


class BeaconAlreadyCoupledException(ServiceApiException):
    def __init__(self, beacon_uuid, beacon_major, beacon_minor):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 16,
                                     u"Beacon already coupled", uuid=beacon_uuid, major=beacon_major,
                                     minor=beacon_minor)


class InvalidAppIdException(ServiceApiException):
    def __init__(self, app_id):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 17,
                                     u"Invalid app_id", app_id=app_id)


class UnsupportedAppIdException(ServiceApiException):
    def __init__(self, app_id):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 18,
                                     u"Unsupported app_id", app_id=app_id)


class RoleNotFoundException(ServiceApiException):
    def __init__(self, role_id):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 19,
                                     u"Role does not exist", role_id=role_id)


class RoleAlreadyExistsException(ServiceApiException):
    def __init__(self, name):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 20,
                                     u"Role with this name already exists", name=name)


class InvalidRoleTypeException(ServiceApiException):
    def __init__(self, type_):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 21,
                                     u"Invalid role type", type=type_)


class DeleteRoleFailedHasMembersException(ServiceApiException):
    def __init__(self, role_id):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 22,
                                     u"Cannot delete role which is still granted to people.", role_id=role_id)


class DeleteRoleFailedHasSMDException(ServiceApiException):
    def __init__(self, role_id):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 23,
                                     u"Cannot delete role which is still connected to a service menu item",
                                     role_id=role_id)


class UserWithThisEmailAddressAlreadyExistsException(ServiceApiException):
    def __init__(self, email):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 24,
                                     u"An account with this e-mail address already exists", email=email)


class AppOperationDeniedException(ServiceApiException):
    def __init__(self, app_id):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 25,
                                     u"No permission to manage app", app_id=app_id)


class ServiceWithEmailDoesNotExistsException(ServiceApiException):
    def __init__(self, service_identity_email):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 26,
                                     u"There is no service with this email",
                                     service_identity_email=service_identity_email)


class NoBeaconRegionFoundException(ServiceApiException):
    def __init__(self, beacon_uuid, beacon_major, beacon_minor):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 27,
                                     u"There is no beacon region for this beacon. Please contact Mobicage for support.",
                                     uuid=beacon_uuid, major=beacon_major, minor=beacon_minor)


class MyDigiPassNotSupportedException(ServiceApiException):
    def __init__(self, unsupported_app_ids):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 28,
                                     u"Not all supported apps of this service implement MYDIGIPASS.",
                                     unsupported_app_ids=unsupported_app_ids)


class AppFailedToResovelUrlException(ServiceApiException):
    def __init__(self, url):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 32,
                                     u"Failed to resolve url", url=url)


class AppFailedToCreateUserProfileWithExistingServiceException(ServiceApiException):
    def __init__(self, email):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 33,
                                     u"Failed to create user profile with the same email as a service account",
                                     email=email)


class InvalidKeyException(ServiceApiException):
    def __init__(self, key):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 34,
                                     u"Invalid key", key=key)


class DuplicateCategoryIdException(ServiceApiException):
    def __init__(self, category_id):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 35,
                                     u"Duplicate category id", category_id=category_id)


class DuplicateItemIdException(ServiceApiException):
    def __init__(self, category_id, item_id):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_SERVICE + 36,
                                     u"Duplicate item id", category_id=category_id, item_id=item_id)


@returns(users.User)
@arguments(service_user=users.User, service_identity=unicode)
def get_and_validate_service_identity_user(service_user, service_identity):
    if not service_identity or service_identity == MISSING:
        service_identity = ServiceIdentity.DEFAULT

    azzert(':' not in service_user.email(), "service_user.email() should not contain :")

    service_identity_user = create_service_identity_user(service_user, service_identity)

    if service_identity != ServiceIdentity.DEFAULT and get_service_identity(service_identity_user) is None:
        raise ServiceIdentityDoesNotExistException(service_identity=service_identity)

    return service_identity_user


@returns(NoneType)
@arguments(service_user=users.User, qualified_identifier=unicode)
def promote_trial_service(service_user, qualified_identifier):
    ts = get_trial_service_by_account(service_user)

    def trans():
        service_identity = get_default_service_identity(service_user)
        service_identity.qualifiedIdentifier = qualified_identifier
        service_identity.put()
        db.delete(ts)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


@returns(ServiceConfigurationTO)
@arguments(service_user=users.User)
def get_configuration(service_user):
    profile = get_service_profile(service_user)
    conf = ServiceConfigurationTO()
    conf.callBackURI = profile.callBackURI
    if not profile.sik:
        def trans():
            profile = get_service_profile(service_user, cached=False)
            profile.sik = unicode(generate_random_key())
            sik = SIKKey(key_name=profile.sik)
            sik.user = service_user
            sik.put()
            profile.put()
            return profile

        xg_on = db.create_transaction_options(xg=True)
        profile = db.run_in_transaction_options(xg_on, trans)
    conf.sik = profile.sik
    conf.callBackJid = profile.callBackJid
    conf.apiKeys = [APIKeyTO.fromDBAPIKey(k) for k in get_api_keys(service_user)]
    conf.enabled = profile.enabled
    conf.callBackFromJid = u"bot@callback.rogerth.at"
    conf.needsTestCall = profile.testCallNeeded
    conf.callbacks = profile.callbacks
    conf.autoUpdating = profile.autoUpdating
    conf.updatesPending = profile.updatesPending
    conf.autoLoginUrl = generate_auto_login_url(service_user)

    if profile.enabled and profile.callBackURI == "mobidick" and conf.apiKeys:
        settings = get_server_settings()
        conf.mobidickUrl = u"%s/create_session?%s" % (
            settings.mobidickAddress, urllib.urlencode((("ak", conf.apiKeys[0].key), ("sik", conf.sik))))
    else:
        conf.mobidickUrl = None
    conf.actions = [] if conf.mobidickUrl else list(get_configuration_actions(service_user))
    return conf


@returns(ServiceLanguagesTO)
@arguments(service_user=users.User)
def get_service_translation_configuration(service_user):
    service_profile = get_service_profile(service_user)
    translationTO = ServiceLanguagesTO()
    translationTO.defaultLanguage = service_profile.defaultLanguage
    translationTO.defaultLanguageStr = get_full_language_string(service_profile.defaultLanguage)
    translationTO.allLanguages = get_officially_supported_languages(iso_format=False)
    translationTO.allLanguagesStr = map(get_full_language_string, translationTO.allLanguages)
    translationTO.nonDefaultSupportedLanguages = sorted(service_profile.supportedLanguages[1:],
                                                        cmp=lambda x, y: 1 if get_full_language_string(
                                                            x) > get_full_language_string(y) else -1)
    return translationTO


@returns(NoneType)
@arguments(service_profile=ServiceProfile, jid=unicode, uri=unicode, callbacks=long)
def configure_profile(service_profile, jid, uri, callbacks=long):
    service_profile.testCallNeeded = True
    service_profile.enabled = False
    service_profile.callBackJid = jid
    service_profile.callBackURI = uri
    service_profile.callbacks = callbacks


@returns(NoneType)
@arguments(service_profile=ServiceProfile)
def configure_profile_for_mobidick(service_profile):
    service_profile.testCallNeeded = False
    service_profile.enabled = True
    service_profile.callBackJid = None
    service_profile.callBackURI = "mobidick"
    callbacks = 0
    for cb in ServiceProfile.CALLBACKS:
        callbacks |= cb
    service_profile.callbacks = callbacks


@returns(NoneType)
@arguments(service_user=users.User)
def configure_mobidick(service_user):
    api_keys = list(get_api_keys(service_user))
    if not api_keys:
        generate_api_key(service_user, "mobidick")

    def trans():
        profile = get_service_profile(service_user, cached=False)
        configure_profile_for_mobidick(profile)
        profile.put()

    db.run_in_transaction(trans)


@returns(NoneType)
@arguments(service_user=users.User, function=unicode, enabled=bool)
def enable_callback_by_function(service_user, function, enabled):
    if function in SERVICE_API_CALLBACK_MAPPING:
        enable_callback(service_user, SERVICE_API_CALLBACK_MAPPING[function], enabled)
    else:
        raise CallbackNotDefinedException(function)


@returns(NoneType)
@arguments(service_user=users.User, callback=int, enabled=bool)
def enable_callback(service_user, callback, enabled):
    azzert(callback in ServiceProfile.CALLBACKS)

    def trans():
        profile = get_service_profile(service_user)
        if enabled:
            profile.callbacks |= callback
        else:
            profile.callbacks &= ~callback
        profile.version += 1
        profile.put()

        if ServiceProfile.CALLBACK_FRIEND_IN_REACH == callback or ServiceProfile.CALLBACK_FRIEND_OUT_OF_REACH == callback:
            schedule_update_all_friends_of_service_user(profile)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


@returns(unicode)
@arguments(sid=ServiceInteractionDef)
def get_service_interact_short_url(sid):
    encoded_short_url = base38.encode_int(sid.shortUrl.key().id())
    return '%s/M/%s' % (get_server_settings().baseUrl, encoded_short_url)


@returns(unicode)
@arguments(sid=ServiceInteractionDef)
def get_service_interact_qr_code_url(sid):
    encoded_short_url = base38.encode_int(sid.shortUrl.key().id())
    return u'%s/S/%s' % (get_server_settings().baseUrl, encoded_short_url)


@returns([unicode])
@arguments(service_user=users.User)
def get_configuration_actions(service_user):
    profile = get_service_profile(service_user)
    if not get_api_key_count(service_user):
        yield u"Generate API keys to use from your service code."
    if not (profile.callBackURI or profile.callBackJid):
        yield u"Configure callback api."
    if not profile.sik:
        yield u"Generate your service identifier key."
    if profile.testCallNeeded:
        yield u"Execute the test callback, to validate the configuration."


@returns(NoneType)
@arguments(service_user=users.User)
def create_default_qr_templates(service_user):
    si = get_service_identity(create_service_identity_user(service_user, ServiceIdentity.DEFAULT))
    app = get_app_by_id(si.app_id)
    for k in app.qrtemplate_keys:
        qr_template = QRTemplate.get_by_key_name(k)
        azzert(qr_template, u"QRTemplate of %s with key %s did not exist" % (si.app_id, k))
        store_template(service_user, qr_template.blob, qr_template.description,
                       u"".join(("%X" % c).rjust(2, '0') for c in qr_template.body_color))


@returns(unicode)
@arguments(app_id=unicode, description=unicode)
def create_qr_template_key_name(app_id, description):
    return u"%s:%s" % (app_id, description)


@returns(tuple)
@arguments(key_name=unicode)
def get_qr_templete_key_name_info(key_name):
    info = key_name.split(":", 1)
    return info[0], info[1]


@returns(tuple)
@arguments(app_id=unicode, color=[int])
def get_default_qr_template_by_app_id(app_id, color=None):
    app = get_app_by_id(app_id)
    qr_template = QRTemplate.get_by_key_name(app.qrtemplate_keys[0])
    azzert(qr_template, u"Default QRTemplate of %s with key %s did not exist" % (app_id, app.qrtemplate_keys[0]))
    return qr_template, color or map(int, qr_template.body_color)


@returns(NoneType)
@arguments(service_user=users.User, identifier=unicode)
def delete_service_identity(service_user, identifier):
    if identifier == ServiceIdentity.DEFAULT:
        raise BusinessException("Delete failed. Cannot delete default Service Identity.")
    service_identity_user = create_service_identity_user(service_user, identifier)

    @db.non_transactional
    def _count_connected_users(service_identity_user):
        return len(get_users_connected_to_service_identity(service_identity_user, None, 1)[0])

    def trans():
        service_identity = get_service_identity(service_identity_user)
        if service_identity is None:
            raise BusinessException("Delete failed. This service identity does not exist!")
        if len(get_service_interaction_defs(service_user, identifier, None)["defs"]) > 0:
            raise BusinessException("Delete failed. This service identity still has QR codes pointing to it.")
        if _count_connected_users(service_identity_user) > 0:
            raise BusinessException("Delete failed. This service identity still has connected friends.")
        # cleanup any previous index entry
        email = service_identity_user.email()
        svc_index = search.Index(name=SERVICE_INDEX)
        loc_index = search.Index(name=SERVICE_LOCATION_INDEX)
        on_trans_committed(_cleanup_search_index, email, svc_index, loc_index)
        if service_identity.serviceData:
            service_identity.serviceData.clear()
        service_identity.delete()
        on_trans_committed(channel.send_message, service_user, u'rogerthat.services.identity.refresh')

    db.run_in_transaction(trans)


@returns(unicode)
@arguments(service_user=users.User, service_identifier=unicode, app_id=unicode, tag=unicode)
def _create_recommendation_qr_code(service_user, service_identifier, app_id, tag=ServiceInteractionDef.TAG_INVITE):
    logging.info("Creating recommendation QR for %s/%s" % (service_user.email(), service_identifier))
    qrtemplate, _ = get_default_qr_template_by_app_id(app_id)
    sid = _create_qr(service_user, service_identifier, u"Connect", tag, qrtemplate, None)[0]
    sid.deleted = True
    sid.put()
    return str(sid.key())


@returns(NoneType)
@arguments(to=ServiceIdentityDetailsTO, si=ServiceIdentity)
def _populate_service_identity(to, si):
    @db.non_transactional
    def get_supported_app_ids():
        default_app = get_default_app()
        return [default_app.app_id] if default_app else [App.APP_ID_ROGERTHAT]

    is_default = si.identifier == ServiceIdentity.DEFAULT
    # Comparing with True because values could be MISSING

    dsi = None
    for p in ServiceIdentityDetailsTO.INHERITANCE_PROPERTIES:
        if getattr(to, p) is True:
            if is_default:
                raise InvalidValueException(p)
            dsi = get_default_service_identity(si.service_user)
            break

    # Do not touch menuGeneration and creation timestamp

    if to.name is not MISSING:
        si.name = to.name

    # Do not update MISSING properties
    if to.description_use_default is True:
        si.description = dsi.description
    elif to.description is not MISSING:
        si.description = to.description

    if to.description_branding_use_default is True:
        si.descriptionBranding = dsi.descriptionBranding
    elif to.description_branding is not MISSING:
        si.descriptionBranding = to.description_branding

    if to.menu_branding_use_default is True:
        si.menuBranding = dsi.menuBranding
    elif to.menu_branding is not MISSING:
        si.menuBranding = to.menu_branding

    if to.phone_number_use_default is True:
        si.mainPhoneNumber = dsi.mainPhoneNumber
    elif to.phone_number is not MISSING:
        si.mainPhoneNumber = to.phone_number

    if to.phone_call_popup_use_default is True:
        si.callMenuItemConfirmation = dsi.callMenuItemConfirmation
    elif to.phone_call_popup is not MISSING:
        si.callMenuItemConfirmation = to.phone_call_popup

    if to.admin_emails is not MISSING:
        si.metaData = ",".join(to.admin_emails)
    if to.app_data is not MISSING:
        si.appData = None
        if to.app_data:
            try:
                data_object = json.loads(to.app_data)
            except:
                raise InvalidJsonStringException()
            if data_object is None:
                raise InvalidJsonStringException()
            if not isinstance(data_object, dict):
                raise InvalidJsonStringException()

            if si.serviceData is None:
                si.serviceData = KVStore(si.key())
            else:
                si.serviceData.clear()
            si.serviceData.from_json_dict(data_object)

    if to.qualified_identifier is not MISSING:
        si.qualifiedIdentifier = to.qualified_identifier
    if to.recommend_enabled is not MISSING:
        si.shareEnabled = to.recommend_enabled
    elif si.shareEnabled is None:
        si.shareEnabled = False  # in case shareEnabled is not set yet, set it to False

    if to.email_statistics_use_default is True:
        si.emailStatistics = dsi.emailStatistics
    elif to.email_statistics is not MISSING:
        si.emailStatistics = to.email_statistics

    if to.app_ids_use_default is True:
        si.appIds = dsi.appIds
    elif to.app_ids is not MISSING:
        si.appIds = to.app_ids or get_supported_app_ids()

    if to.beacon_auto_invite is not MISSING:
        si.beacon_auto_invite = to.beacon_auto_invite

    if to.content_branding_hash is not MISSING:
        si.contentBrandingHash = to.content_branding_hash

    si.inheritanceFlags = 0
    # Comparing with True again because values could be MISSING
    if to.description_use_default is True:
        si.inheritanceFlags |= ServiceIdentity.FLAG_INHERIT_DESCRIPTION
    if to.description_branding_use_default is True:
        si.inheritanceFlags |= ServiceIdentity.FLAG_INHERIT_DESCRIPTION_BRANDING
    if to.menu_branding_use_default is True:
        si.inheritanceFlags |= ServiceIdentity.FLAG_INHERIT_MENU_BRANDING
    if to.phone_number_use_default is True:
        si.inheritanceFlags |= ServiceIdentity.FLAG_INHERIT_PHONE_NUMBER
    if to.phone_call_popup_use_default is True:
        si.inheritanceFlags |= ServiceIdentity.FLAG_INHERIT_PHONE_POPUP_TEXT
    if to.search_use_default is True:
        si.inheritanceFlags |= ServiceIdentity.FLAG_INHERIT_SEARCH_CONFIG
    if to.email_statistics_use_default is True:
        si.inheritanceFlags |= ServiceIdentity.FLAG_INHERIT_EMAIL_STATISTICS
    if to.app_ids_use_default is True:
        si.inheritanceFlags |= ServiceIdentity.FLAG_INHERIT_APP_IDS


def _validate_service_identity(service_user, to, is_trial):
    if to.identifier is MISSING or not to.identifier or not is_valid_service_identifier(to.identifier):
        raise InvalidValueException(u"identifier", u"Identifier should contain lowercase characters a-z or 0-9 or .-_")
    if to.name is not MISSING:
        if not to.name:
            raise InvalidValueException(u"name", u"Name is a required field")
        if EMAIL_REGEX.match(to.name):
            raise InvalidValueException(u"name", u'Name cannot be an e-mail address')
    if is_trial and to.search_config is not MISSING and to.search_config and to.search_config.enabled:
        raise InvalidValueException(u"search_config", u'Service search & discovery is not supported for trial accounts')


@returns(ServiceIdentity)
@arguments(service_user=users.User, to=ServiceIdentityDetailsTO)
def create_service_identity(service_user, to):
    if to.identifier == ServiceIdentity.DEFAULT:
        raise InvalidValueException(u"identifier", u"Cannot create default Service Identity")
    if to.name is MISSING:
        raise InvalidValueException(u"name", u"Name is a required field")
    is_trial = is_trial_service(service_user)
    _validate_service_identity(service_user, to, is_trial)

    azzert(get_service_profile(service_user))
    service_identity_user = create_service_identity_user(service_user, to.identifier)

    default_svc_identity_user = create_service_identity_user(service_user, ServiceIdentity.DEFAULT)
    default_si = get_service_identity(default_svc_identity_user)
    default_share_sid = ServiceInteractionDef.get(default_si.shareSIDKey)
    app_id = to.app_ids[0] if to.app_ids is not MISSING and to.app_ids else get_default_app().app_id
    share_sid_key = _create_recommendation_qr_code(service_user, to.identifier, app_id, default_share_sid.tag)

    def trans():
        if get_service_identity_not_cached(service_identity_user) is not None:
            raise BusinessException("This service identity already exists!")

        si_key = ServiceIdentity.keyFromUser(service_identity_user)
        si = ServiceIdentity(key=si_key)
        si.serviceData = KVStore(si_key)
        _populate_service_identity(to, si)
        si.shareSIDKey = share_sid_key
        si.creationTimestamp = now()
        si.menuGeneration = 0
        si.version = 1
        si.put()
        ProfilePointer.create(si.user).put()
        if not is_trial:
            if to.search_use_default is True:
                default_search_config, default_locations = get_search_config(default_svc_identity_user)
                update_search_config(service_identity_user,
                                     SearchConfigTO.fromDBSearchConfig(default_search_config, default_locations))
            else:
                update_search_config(service_identity_user, to.search_config, accept_missing=True)

        update_beacons(service_identity_user, to.beacons, accept_missing=True)

        return si

    xg_on = db.create_transaction_options(xg=True)
    si = db.run_in_transaction_options(xg_on, trans)
    channel.send_message(service_user, u'rogerthat.services.identity.refresh')
    return si


@returns(ServiceIdentity)
@arguments(service_user=users.User, to=ServiceIdentityDetailsTO)
def update_service_identity(service_user, to):
    is_trial = is_trial_service(service_user)
    _validate_service_identity(service_user, to, is_trial)

    service_identity_user = create_service_identity_user(service_user, to.identifier)
    if get_service_identity(service_identity_user) is None:
        raise ServiceIdentityDoesNotExistException(to.identifier)

    if not to.menu_branding_use_default and to.menu_branding:
        b = get_branding(to.menu_branding)
        if b.type != Branding.TYPE_NORMAL:
            raise InvalidValueException(u"menu_branding", u"This branding can not be used as menu branding")

    if not to.description_branding_use_default and to.description_branding:
        b = get_branding(to.description_branding)
        if b.type != Branding.TYPE_NORMAL:
            raise InvalidValueException(u"description_branding",
                                        u"This branding can not be used as description branding")

    azzert(get_service_profile(service_user))

    def trans():
        si_key = ServiceIdentity.keyFromUser(service_identity_user)
        si = ServiceIdentity.get(si_key)
        _populate_service_identity(to, si)
        si.version += 1
        si.put()

        if not is_trial:
            if to.search_use_default is True:
                default_svc_identity_user = create_service_identity_user(service_user, ServiceIdentity.DEFAULT)
                default_search_config, default_locations = get_search_config(default_svc_identity_user)
                update_search_config(service_identity_user,
                                     SearchConfigTO.fromDBSearchConfig(default_search_config, default_locations))
            elif to.search_config is not MISSING:
                update_search_config(service_identity_user, to.search_config)

        if to.beacons is not MISSING:
            update_beacons(service_identity_user, to.beacons)

        update_friends(si)
        if to.identifier == ServiceIdentity.DEFAULT:
            deferred.defer(_update_inheriting_service_identities, si, is_trial, _transactional=True)
        return si

    xg_on = db.create_transaction_options(xg=True)
    si = db.run_in_transaction_options(xg_on, trans)
    channel.send_message(service_user, u'rogerthat.services.identity.refresh')
    return si


@returns(ServiceIdentity)
@arguments(service_user=users.User, to=ServiceIdentityDetailsTO)
def create_or_update_service_identity(service_user, to):
    if to.identifier is MISSING:
        to.identifier = ServiceIdentity.DEFAULT
    service_identity_user = create_service_identity_user(service_user, to.identifier)

    f = update_service_identity if get_service_identity(service_identity_user) else create_service_identity
    f(service_user, to)


@returns(NoneType)
@arguments(default_service_identity=ServiceIdentity, is_trial=bool)
def _update_inheriting_service_identities(default_service_identity, is_trial):
    azzert(default_service_identity.identifier == ServiceIdentity.DEFAULT)
    default_search_initialized = False
    default_search_config = default_locations = None

    service_identities_modified = []
    search_config_update_list = []

    for child_identity in get_child_identities(default_service_identity.service_user):
        if child_identity.inheritanceFlags & ~ServiceIdentity.FLAG_INHERIT_SEARCH_CONFIG != 0:
            if is_flag_set(ServiceIdentity.FLAG_INHERIT_DESCRIPTION, child_identity.inheritanceFlags):
                child_identity.description = default_service_identity.description
            if is_flag_set(ServiceIdentity.FLAG_INHERIT_DESCRIPTION_BRANDING, child_identity.inheritanceFlags):
                child_identity.descriptionBranding = default_service_identity.descriptionBranding
            if is_flag_set(ServiceIdentity.FLAG_INHERIT_MENU_BRANDING, child_identity.inheritanceFlags):
                child_identity.menuBranding = default_service_identity.menuBranding
            if is_flag_set(ServiceIdentity.FLAG_INHERIT_PHONE_NUMBER, child_identity.inheritanceFlags):
                child_identity.mainPhoneNumber = default_service_identity.mainPhoneNumber
            if is_flag_set(ServiceIdentity.FLAG_INHERIT_PHONE_POPUP_TEXT, child_identity.inheritanceFlags):
                child_identity.callMenuItemConfirmation = default_service_identity.callMenuItemConfirmation
            child_identity.version += 1
            service_identities_modified.append(child_identity)
        if not is_trial and is_flag_set(ServiceIdentity.FLAG_INHERIT_SEARCH_CONFIG, child_identity.inheritanceFlags):
            if not default_search_initialized:
                default_search_config, default_locations = get_search_config(default_service_identity.user)
                default_search_initialized = True
            search_config_update_list.append(
                (child_identity.user, SearchConfigTO.fromDBSearchConfig(default_search_config, default_locations)))

    if service_identities_modified:
        put_and_invalidate_cache(*service_identities_modified)
        map(update_friends, service_identities_modified)

    # Make sure to update search config only AFTER the service identities have been stored
    if not is_trial:
        for search_config_update_entry in search_config_update_list:
            update_search_config(*search_config_update_entry)


@returns(NoneType)
@arguments(service_identity_user=users.User, search_config=SearchConfigTO)
def update_search_config(service_identity_user, search_config):
    if search_config is MISSING or search_config is None:
        search_config = SearchConfigTO()
        search_config.enabled = False
        search_config.keywords = None
        search_config.locations = list()

    def trans():
        sc, locs = get_search_config(service_identity_user)
        sc.enabled = search_config.enabled
        sc.keywords = search_config.keywords
        db.delete_async(locs)
        if search_config.locations is not MISSING:
            for loc in search_config.locations:
                lc = SearchConfigLocation(parent=sc)
                lc.address = loc.address
                lc.lat = loc.lat
                lc.lon = loc.lon
                db.put_async(lc)
        deferred.defer(re_index, service_identity_user, _transactional=True)
        db.put_async(sc)

    if db.is_in_transaction():
        return trans()
    else:
        xg_on = db.create_transaction_options(xg=True)
        return db.run_in_transaction_options(xg_on, trans)


@returns(NoneType)
@arguments(user=users.User)
def convert_user_to_service(user):
    profile = get_user_profile(user)
    # Deny conversion when user has still friends
    friendMap = get_friends_map(user)
    if friendMap.friends:
        raise ValueError("Cannot convert to service when user still has friends!")
    # Unregister mobiles
    for mobile in get_user_active_mobiles(user):
        unregister_mobile(user, mobile)

    share_sid_key = _create_recommendation_qr_code(user, ServiceIdentity.DEFAULT, get_app_id_from_app_user(user))

    # Create ServiceProfile
    def trans():
        service_profile = ServiceProfile(key=profile.key())
        # Copy all properties of Profile
        for prop in (p for p in Profile.properties().iterkeys() if p != '_class'):
            setattr(service_profile, prop, getattr(profile, prop))
        service_profile.testCallNeeded = True
        service_profile.put()

        si = ServiceIdentity(
            key=ServiceIdentity.keyFromUser(create_service_identity_user(user, ServiceIdentity.DEFAULT)))
        si.shareSIDKey = share_sid_key
        si.shareEnabled = False
        si.name = profile.name
        si.appIds = [App.APP_ID_ROGERTHAT]
        si.put()
        ProfilePointer.create(si.user).put()

        # Create some default qr templates
        if QRTemplate.gql("WHERE ANCESTOR IS :1", parent_key(user)).count() == 0:
            deferred.defer(create_default_qr_templates, user, _transactional=True)

        return si

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)

    if isinstance(profile, FacebookUserProfile):
        db.delete(FacebookProfilePointer.all().filter("user =", user).fetch(None))


@returns(ServiceConfigurationTO)
@arguments(service_user=users.User, name=unicode)
def generate_api_key(service_user, name):
    _generate_api_key(name, service_user).put()
    return get_configuration(service_user)


@returns(MFRSIKey)
@arguments(service_identity_user=users.User)
def get_mfr_sik(service_identity_user):
    from rogerthat.dal.service import get_mfr_sik as get_mfr_sik_dal
    svc_user = get_service_user_from_service_identity_user(service_identity_user)
    sik = get_mfr_sik_dal(svc_user)
    if not sik:
        sik = MFRSIKey(key_name=svc_user.email(), parent=parent_key(svc_user))
        sik.sik = generate_random_key()
        sik.put()
    return sik


@returns(APIKey)
@arguments(service_identity_user=users.User)
def get_mfr_api_key(service_identity_user):
    from rogerthat.dal.service import get_mfr_api_key as get_mfr_api_key_dal
    svc_user = get_service_user_from_service_identity_user(service_identity_user)
    api_key = get_mfr_api_key_dal(svc_user)
    if not api_key:
        api_key = _generate_api_key("mfr_api_key", svc_user)
        api_key.mfr = True
        api_key.put()
    return api_key


@returns(ServiceConfigurationTO)
@arguments(service_user=users.User, key=unicode)
def delete_api_key(service_user, key):
    ak = get_api_key(key)
    if ak:
        azzert(ak.user == service_user)
        ak.delete()
        if not any(get_configuration_actions(service_user)):
            profile = get_service_profile(service_user)
            profile.testCallNeeded = True
            profile.enabled = False
            profile.put()
    return get_configuration(service_user)


def _disable_svc(service_user, admin_user):
    service_profile = get_service_profile(service_user)
    service_profile.enabled = False
    service_profile.put()
    logging.warning('Admin user %s disables troubled service %s' % (admin_user.email(), service_user.email()))


@returns(NoneType)
@arguments(message=Message)
def ack_service_in_trouble(message):
    azzert(message.tag == SERVICE_IN_TROUBLE_TAG)
    service_user = message.troubled_service_user
    admin_user = message.troubled_admin_user
    if message.memberStatusses[message.members.index(admin_user)].button_index == message.buttons[
        DISABLE_SERVICE_TROUBLE_ID].index:
        try_or_defer(_disable_svc, service_user, admin_user)
    else:
        logging.info('Admin user %s does not disable troubled service %s' % (admin_user.email(), service_user.email()))


@returns(ServiceConfigurationTO)
@arguments(service_user=users.User)
def enable_service(service_user):
    azzert(not any(get_configuration_actions(service_user)))

    def trans():
        # enable profile
        profile = get_service_profile(service_user, cached=False)
        profile.enabled = True
        # enable records for processing
        from rogerthat.bizz.job.reschedule_service_api_callback_records import run
        timestamp = now()
        deferred.defer(run, timestamp, service_user, _transactional=True)
        # send mail
        text = render("service_enabled", None, {})
        html = render("service_enabled_html", None, {})
        se = ServiceEmail(parent=parent_key(service_user), timestamp=timestamp, messageText=text, messageHtml=html,
                          subject="Your Rogerthat service has been enabled.")
        profile.put()  # XXX:
        se.put()  # These two puts should be done in one call
        return se  # But profile needs cache update support for this --> use put_and_invalidate cache

    se = db.run_in_transaction(trans)
    settings = get_server_settings()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = se.subject.encode('utf-8')
    msg['From'] = settings.senderEmail
    msg['To'] = service_user.email()
    msg.attach(MIMEText(se.messageText.encode('utf-8'), 'plain', 'utf-8'))
    msg.attach(MIMEText(se.messageHtml.encode('utf-8'), 'html', 'utf-8'))
    send_mail_via_mime(settings.senderEmail, service_user.email(), msg)
    return get_configuration(service_user)


@returns(NoneType)
@arguments(service_profile=ServiceProfile, reason=unicode)
def send_callback_delivery_warning(service_profile, reason):
    if service_profile.lastWarningSent and (service_profile.lastWarningSent + 3600) > now():
        return

    def trans():
        profile = get_service_profile(service_profile.user, cached=False)
        profile.lastWarningSent = now()
        profile.put()
        return profile

    db.run_in_transaction(trans)
    admins = [UserMemberTO(users.User(a.user_email), Message.ALERT_FLAG_VIBRATE | Message.ALERT_FLAG_RING_15) for a in
              get_service_admins(service_profile.user)]

    subject = "Rogerthat service %s will soon be disabled" % service_profile.user.email()
    text = render("service_soon_disabled", None, {"reason": reason})
    html = render("service_soon_disabled_html", None, {"reason": reason})

    settings = get_server_settings()
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = settings.senderEmail
    msg['To'] = ', '.join([a.member.email() for a in admins] + [service_profile.user.email()])
    msg.attach(MIMEText(text.encode('utf-8'), 'plain', 'utf-8'))
    msg.attach(MIMEText(html.encode('utf-8'), 'html', 'utf-8'))
    send_mail_via_mime(settings.senderEmail, [a.member.email() for a in admins] + [service_profile.user.email()], msg)


@returns(ServiceConfigurationTO)
@arguments(service_user=users.User, reason=unicode)
def disable_service(service_user, reason):
    def trans():
        # disable profile
        profile = get_service_profile(service_user, cached=False)
        profile.enabled = False
        # disable records for processing
        from rogerthat.bizz.job.unschedule_service_api_callback_records import run
        deferred.defer(run, service_user, _transactional=True)
        # send mail
        text = render("service_disabled", None, {"reason": reason})
        html = render("service_disabled_html", None, {"reason": reason})
        se = ServiceEmail(parent=parent_key(service_user), timestamp=now(), messageText=text, messageHtml=html,
                          subject="Rogerthat service %s has been disabled!" % profile.user.email())
        profile.put()  # XXX:
        se.put()  # These two puts should be done in one call
        return se  # But profile needs cache update support for this --> use put_and_invalidate cache

    se = db.run_in_transaction(trans)
    admins = [UserMemberTO(users.User(a.user_email),
                           Message.ALERT_FLAG_VIBRATE | Message.ALERT_FLAG_RING_5 | Message.ALERT_FLAG_INTERVAL_5) for a
              in get_service_admins(service_user)]
    settings = get_server_settings()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = se.subject
    msg['From'] = settings.senderEmail
    msg['To'] = ', '.join([a.member.email() for a in admins] + [service_user.email()])
    msg.attach(MIMEText(se.messageText.encode('utf-8'), 'plain', 'utf-8'))
    msg.attach(MIMEText(se.messageHtml.encode('utf-8'), 'html', 'utf-8'))
    send_mail_via_mime(settings.senderEmail, [a.member.email() for a in admins] + [service_user.email()], msg)
    return get_configuration(service_user)


@returns(ServiceConfigurationTO)
@arguments(service_user=users.User, httpURI=unicode, xmppJID=unicode)
def update_callback_configuration(service_user, httpURI, xmppJID):
    def trans():
        profile = get_service_profile(service_user, cached=False)
        profile.callBackURI = httpURI.strip() if httpURI else None
        profile.callBackJid = xmppJID.strip() if xmppJID else None
        if httpURI == "mobidick":
            profile.testCallNeeded = False
            profile.enabled = True
        else:
            profile.testCallNeeded = bool(httpURI) ^ bool(xmppJID)
            profile.enabled = False
        profile.put()

    db.run_in_transaction(trans)
    return get_configuration(service_user)


@returns(NoneType)
@arguments(service_user=users.User, language=unicode, enabled=bool)
def set_supported_language(service_user, language, enabled):
    if language not in OFFICIALLY_SUPPORTED_LANGUAGES:
        logging.error("Trying to set non-supported language %s for service %s" % (language, service_user.email()))
        return

    def trans():
        profile = get_service_profile(service_user, cached=False)
        if language in profile.supportedLanguages:
            # Language is currently supported
            if enabled:
                logging.warning(
                    "Trying to enable already enabled language %s of service %s" % (language, service_user.email()))
                return
            if profile.supportedLanguages.index(language) == 0:
                logging.error(
                    "Trying to modify status of default language %s of service %s" % (language, service_user.email()))
                return
            profile.supportedLanguages.remove(language)
            profile.put()
        else:
            # Language is currently not supported
            if not enabled:
                logging.warning(
                    "Trying to disable already disabled language %s of service %s" % (language, service_user.email()))
                return
            profile.supportedLanguages.append(language)
            profile.put()

    db.run_in_transaction(trans)
    deferred.defer(check_i18n_status_of_message_flows, service_user)


@returns(ServiceConfigurationTO)
@arguments(service_user=users.User)
def regenerate_sik(service_user):
    def trans():
        profile = get_service_profile(service_user, cached=False)
        if profile.sik:
            sik = get_sik(profile.sik)
            if sik:
                sik.delete()
        profile.sik = unicode(generate_random_key())
        sik = SIKKey(key_name=profile.sik)
        sik.user = service_user
        sik.put()
        profile.testCallNeeded = True
        profile.enabled = False
        profile.put()

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)
    return get_configuration(service_user)


@returns(NoneType)
@arguments(svc_user=users.User, sid_id=(int, long), description=unicode, tag=unicode, static_flow=unicode,
           branding_hash=unicode)
def update_qr(svc_user, sid_id, description, tag, static_flow, branding_hash=None):
    if branding_hash and not get_branding(branding_hash):
        raise BrandingNotFoundException()
    sid = get_service_interaction_def(svc_user, sid_id)
    sid.staticFlowKey = str(get_service_message_flow_design_key_by_name(svc_user, static_flow)) if static_flow else None
    sid.tag = tag
    sid.description = description
    sid.branding = branding_hash
    sid.put()


@returns(QRDetailsTO)
@arguments(svc_user=users.User, description=unicode, tag=unicode, template_key=unicode, service_identifier=unicode,
           static_flow=unicode, branding_hash=unicode)
def create_qr(svc_user, description, tag, template_key, service_identifier, static_flow, branding_hash=None):
    service_identity_user = create_service_identity_user(svc_user, service_identifier)
    azzert(is_service_identity_user(service_identity_user))

    if tag.startswith(MC_RESERVED_TAG_PREFIX):
        raise ReservedTagException()

    if branding_hash and not get_branding(branding_hash):
        raise BrandingNotFoundException()

    if template_key and template_key != MISSING:
        qr_template = QRTemplate.get_by_id(int(template_key[2:], 16), parent_key(svc_user))
    else:
        qr_template = None

    static_flow_key = str(get_service_message_flow_design_key_by_name(svc_user, static_flow)) if static_flow else None
    sid, id_, user_code = _create_qr(svc_user, service_identifier, description, tag, qr_template, static_flow_key,
                                     branding_hash)

    result = QRDetailsTO()
    result.image_uri = u"%s/si/%s/%s" % (get_server_settings().baseUrl, user_code, id_)
    result.content_uri = get_service_interact_qr_code_url(sid)
    result.email_uri = get_service_interact_short_url(sid) + "?email"
    result.sms_uri = get_service_interact_short_url(sid)
    return result


def get_shorturl_for_qr(service_user, sid_id):
    user_code = userCode(service_user)
    return ShortURL(full="/q/s/%s/%s" % (user_code, sid_id)), user_code


@returns(tuple)
@arguments(svc_user=users.User, service_identifier=unicode, description=unicode, tag=unicode, qr_template=QRTemplate,
           static_flow_key=unicode, branding=unicode)
def _create_qr(svc_user, service_identifier, description, tag, qr_template, static_flow_key, branding=None):
    sid = ServiceInteractionDef(parent=parent_key(svc_user), description=description, tag=tag, timestamp=now(),
                                service_identity=service_identifier, staticFlowKey=static_flow_key, branding=branding)
    sid.qrTemplate = qr_template
    sid.put()
    id_ = sid.key().id()
    su, user_code = get_shorturl_for_qr(svc_user, id_)
    su.put()
    sid.shortUrl = su
    sid.put()
    return sid, id_, user_code


@returns(NoneType)
@arguments(service_user=users.User, sid=(int, long))
def delete_qr(service_user, sid):
    sid = ServiceInteractionDef.get_by_id(sid, parent=parent_key(service_user))
    sid.deleted = True
    sid.put()


@returns(NoneType)
@arguments(app_user=users.User, service_identity_user=users.User, tag=unicode, context=unicode,
           message_flow_run_id=unicode, timestamp=(int, NoneType))
def poke_service_with_tag(app_user, service_identity_user, tag, context=None, message_flow_run_id=None,
                          timestamp=None):
    from rogerthat.bizz.service.mfr import _create_message_flow_run
    user_profile = get_user_profile(app_user)
    is_connected = (get_friend_serviceidentity_connection(app_user, service_identity_user) is not None)
    svc_user, identifier = get_service_identity_tuple(service_identity_user)
    human_user_email = get_human_user_from_app_user(app_user).email()
    if is_connected:
        from rogerthat.service.api.messaging import poke
        result_key = message_flow_run_id or str(uuid.uuid4())

        def trans():
            if message_flow_run_id:
                key_name = MessageFlowRunRecord.createKeyName(svc_user, message_flow_run_id)
                if not MessageFlowRunRecord.get_by_key_name(key_name):
                    _create_message_flow_run(svc_user, service_identity_user, message_flow_run_id, True, tag)

            poke_call = poke(poke_service_callback_response_receiver, logServiceError, get_service_profile(svc_user),
                             email=human_user_email, tag=tag, result_key=result_key, context=context,
                             service_identity=identifier, timestamp=timestamp or 0,
                             user_details=[UserDetailsTO.fromUserProfile(user_profile)],
                             DO_NOT_SAVE_RPCCALL_OBJECTS=True)
            if poke_call:  # None if poke callback is not implemented
                poke_call.message_flow_run_id = message_flow_run_id
                poke_call.result_key = result_key
                poke_call.member = app_user
                poke_call.context = context
                poke_call.put()

        xg_on = db.create_transaction_options(xg=True)
        db.run_in_transaction_options(xg_on, trans)
    else:
        language = user_profile.language or DEFAULT_LANGUAGE
        from rogerthat.bizz.friends import ORIGIN_USER_POKE
        def trans():
            if message_flow_run_id:
                key_name = MessageFlowRunRecord.createKeyName(svc_user, message_flow_run_id)
                if not MessageFlowRunRecord.get_by_key_name(key_name):
                    _create_message_flow_run(svc_user, service_identity_user, message_flow_run_id, True, tag)

            capi_call = invited(invited_response_receiver, logServiceError, get_service_profile(svc_user),
                                email=human_user_email, name=user_profile.name, message=None, tag=tag,
                                language=language, service_identity=identifier,
                                user_details=[UserDetailsTO.fromUserProfile(user_profile)],
                                origin=ORIGIN_USER_POKE, DO_NOT_SAVE_RPCCALL_OBJECTS=True)
            if capi_call:  # None if friend.invited callback is not implemented ==> invited_response_receiver
                capi_call.invitor = app_user
                capi_call.invitee = service_identity_user
                capi_call.servicetag = tag
                capi_call.poke = True
                capi_call.message_flow_run_id = message_flow_run_id
                capi_call.origin = ORIGIN_USER_POKE
                capi_call.context = context
                capi_call.put()
            else:
                deferred.defer(process_invited_response, svc_user, service_identity_user, identifier, app_user,
                               service_identity_user, tag, ORIGIN_USER_POKE, True, context, message_flow_run_id,
                               _transactional=True)

        xg_on = db.create_transaction_options(xg=True)
        db.run_in_transaction_options(xg_on, trans)

    slog('T', app_user.email(), "com.mobicage.api.services.startAction", service=service_identity_user.email(), tag=tag,
         context=context)


@returns(NoneType)
@arguments(user=users.User, service_identity_user=users.User, sid=unicode, context=unicode, message_flow_run_id=unicode,
           timestamp=(int, NoneType))
def poke_service(user, service_identity_user, sid, context=None, message_flow_run_id=None, timestamp=None):
    service_identity = get_service_identity(service_identity_user)
    azzert(service_identity)
    if sid:
        if "?" in sid:
            sid = sid[:sid.index("?")]  # strip off the query parameters added by shortner.py
        sid = get_service_interaction_def(service_identity.service_user, int(sid))
        azzert(sid)
    tag = sid.tag if sid else None

    poke_service_with_tag(user, service_identity_user, tag, context, message_flow_run_id, timestamp)


@returns(NoneType)
@arguments(user=users.User, service_identity_user=users.User, hashed_tag=unicode, context=unicode,
           timestamp=(int, NoneType))
def poke_service_by_hashed_tag(user, service_identity_user, hashed_tag, context=None, timestamp=None):
    service_identity = get_service_identity(service_identity_user)
    azzert(service_identity)
    mapped_poke = PokeTagMap.get_by_key_name(hashed_tag, parent=parent_key(service_identity.service_user))
    poke_service_with_tag(user, service_identity_user, mapped_poke.tag if mapped_poke else hashed_tag, context,
                          timestamp=timestamp)


@returns(NoneType)
@arguments(user=users.User, service_identity_user=users.User, coords=[int], context=unicode, menuGeneration=int,
           message_flow_run_id=unicode, hashed_tag=unicode, timestamp=(int, NoneType))
def press_menu_item(user, service_identity_user, coords, context, menuGeneration, message_flow_run_id=None,
                    hashed_tag=None, timestamp=None):
    service_identity = get_service_identity(service_identity_user)
    if service_identity.menuGeneration == menuGeneration:
        smd = get_service_menu_item_by_coordinates(service_identity_user, coords)
        if smd:
            from rogerthat.bizz.service.mfr import start_flow
            if smd.staticFlowKey and not message_flow_run_id:
                logging.info("User did not start static flow. Starting flow now.")
                message_flow_run_id = str(uuid.uuid4())
                start_flow(service_identity_user, None, smd.staticFlowKey, [user], False, True, smd.tag, context,
                           key=message_flow_run_id)
            elif not smd.staticFlowKey and not message_flow_run_id and smd.isBroadcastSettings:
                from rogerthat.bizz.service.broadcast import generate_broadcast_settings_flow_def
                from rogerthat.bizz.service.mfd import to_xml_unicode
                mfds = generate_broadcast_settings_flow_def(service_identity_user, get_user_profile(user))
                azzert(mfds, "Expected broadcast settings.")
                mfd = MessageFlowDesign()
                mfd.xml = to_xml_unicode(mfds, 'messageFlowDefinitionSet', True)
                start_flow(service_identity_user, None, mfd, [user], False, True, smd.tag, context,
                           key=message_flow_run_id, allow_reserved_tag=True)
            poke_service_with_tag(user, service_identity_user, smd.tag, context, message_flow_run_id, timestamp)
            from rogerthat.bizz import log_analysis
            slog(msg_="Press menu item", function_=log_analysis.SERVICE_STATS, service=service_identity_user.email(),
                 tag=smd.label, type_=log_analysis.SERVICE_STATS_TYPE_MIP)

        elif coords == [3, 0, 0]:  # coordinates of share
            pass
        else:
            logging.error("Generation match (%s == %s), but service menu icon %s not found."
                          % (menuGeneration, service_identity.menuGeneration, coords))

    elif message_flow_run_id and hashed_tag:
        logging.info("User started a static flow, but his menu was out of date")
        mapped_tag = ServiceMenuDefTagMap.get_by_key_name(hashed_tag, parent=parent_key(service_identity.service_user))
        if mapped_tag:
            poke_service_with_tag(user, service_identity_user, mapped_tag.tag, context, message_flow_run_id, timestamp)
        else:
            logging.error("Generation mismatch (%s != %s) and mapped tag %s not found."
                          % (menuGeneration, service_identity.menuGeneration, hashed_tag))

    else:
        deferred.defer(_warn_user_menu_outdated, service_identity_user, user, context,
                       _transactional=db.is_in_transaction())


@arguments(context=ServiceAPICallback, result=object)
def handle_fast_callback(context, result):
    capi_call = context

    if result:
        sender_service_identity_user = capi_call.service_identity_user

        error = None
        try:
            if isinstance(result.value, FlowCallbackResultTypeTO):
                type_ = FlowCallbackResultTypeTO
                from rogerthat.bizz.service.mfr import MessageFlowNotFoundException, MessageFlowNotValidException, \
                    start_local_flow
                if result.value.flow.startswith(u'<?xml'):
                    xml = result.value.flow
                else:
                    mfd = get_message_flow_by_key_or_name(capi_call.service_user, result.value.flow)
                    if not mfd or not mfd.user == capi_call.service_user:
                        raise MessageFlowNotFoundException()

                    if mfd.status != MessageFlowDesign.STATUS_VALID:
                        raise MessageFlowNotValidException(mfd.validation_error)
                    xml = mfd.xml

                start_local_flow(sender_service_identity_user, getattr(capi_call, 'parent_message_key', None),
                                 xml, [capi_call.member], None if result.value.tag == MISSING else result.value.tag,
                                 context=getattr(capi_call, 'context', None),
                                 force_language=None if result.value.force_language == MISSING else result.value.force_language,
                                 parent_message_key=getattr(capi_call, 'parent_message_key', None))


            elif isinstance(result.value, MessageCallbackResultTypeTO):
                type_ = MessageCallbackResultTypeTO
                parent_message_key = getattr(capi_call, 'parent_message_key', None)
                if not parent_message_key:
                    members = [UserMemberTO(capi_call.member, result.value.alert_flags)]
                else:
                    message_object = get_message(parent_message_key, None)
                    members = [UserMemberTO(member, result.value.alert_flags) for member in message_object.members]
                sendMessage(sender_service_identity_user, members,
                            result.value.flags, 0, parent_message_key, result.value.message,
                            result.value.answers, None, result.value.branding, result.value.tag,
                            result.value.dismiss_button_ui_flags, getattr(capi_call, 'context', None),
                            attachments=result.value.attachments,
                            key=capi_call.result_key, is_mfr=capi_call.targetMFR,
                            step_id=None if result.value.step_id is MISSING else result.value.step_id)

            elif isinstance(result.value, FormCallbackResultTypeTO):
                type_ = FormCallbackResultTypeTO
                sendForm(sender_service_identity_user, getattr(capi_call, 'parent_message_key', None), capi_call.member,
                         result.value.message, result.value.form, result.value.flags, result.value.branding,
                         result.value.tag, result.value.alert_flags, getattr(capi_call, 'context', None),
                         attachments=result.value.attachments,
                         key=capi_call.result_key, is_mfr=capi_call.targetMFR,
                         step_id=None if result.value.step_id is MISSING else result.value.step_id)

        except ServiceApiException, sae:
            if (sae.code >= ERROR_CODE_WARNING_THRESHOLD):
                logging.warning("Service api exception occurred", exc_info=1)
            else:
                logging.exception("Severe Service API Exception")
            error = {'code': sae.code, 'message': sae.message}
            error.update(sae.fields)
        except:
            server_settings = get_server_settings()
            erroruuid = str(uuid.uuid4())
            logging.exception("Unknown exception occurred: error id %s" % erroruuid)
            error = {'code': ERROR_CODE_UNKNOWN_ERROR,
                     'message': 'An unknown error occurred. Please contact %s and mention error id %s' % (
                         server_settings.supportEmail, erroruuid)}
        if error is not None:
            function = None
            request = json.dumps({'params': serialize_complex_value(result.value, type_, False, skip_missing=True)})
            response = json.dumps({'result': None, 'error': error})
            log_service_activity(capi_call.service_user, str(uuid.uuid4()), ServiceLog.TYPE_CALL,
                                 ServiceLog.STATUS_ERROR, function, request, response, error['code'], error['message'])


@mapping(u'message.poke.response_handler')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=PokeCallbackResultTO)
def poke_service_callback_response_receiver(context, result):
    if not getattr(context, "message_flow_run_id", None):
        handle_fast_callback(context, result)


@returns(ServiceConfigurationTO)
@arguments(service_user=users.User, enable_on_success=bool)
def perform_test_callback(service_user, enable_on_success=False):
    logging.info("Preparing service object by setting the test-value ...")

    def trans():
        profile = get_service_profile(service_user, cached=False)
        profile.testValue = unicode(uuid.uuid4())
        profile.put()
        return profile

    profile = db.run_in_transaction(trans)

    logging.info("Scheduling test-callback ...")
    context = test(test_callback_response_receiver, logServiceError, profile, value=profile.testValue)
    context.enable_on_success = enable_on_success
    context.put()


@mapping(u'test_api_callback_response_handler')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=unicode)
def test_callback_response_receiver(context, result):
    profile = get_service_profile(context.service_user)

    if profile.testValue != result:
        raise TestCallbackFailedException()

    azzert(profile.testValue == result)
    profile.testCallNeeded = False
    if hasattr(context, 'enable_on_success') and context.enable_on_success:
        profile.enabled = True
    profile.put()

    channel.send_message(context.service_user, u'rogerthat.service.testCallSucceeded')


@returns(bool)
@arguments(service=users.User, admin=users.User)
def invite_service_admin(service, admin):
    service_identity, admin_user_profile = get_profile_infos([service, admin],
                                                             expected_types=[ServiceIdentity, UserProfile],
                                                             allow_none_in_results=True)
    if not admin_user_profile:
        return False

    m = """Hi %s,
service %s wants to add you as an administrator.
""" % (admin_user_profile.name, service_identity.name)
    message = sendMessage(MC_DASHBOARD, [UserMemberTO(admin)], Message.FLAG_AUTO_LOCK, 0, None, m,
                          create_accept_decline_buttons(admin_user_profile.language), None,
                          get_app_by_user(admin).core_branding_hash, INVITE_SERVICE_ADMIN, is_mfr=False)
    message.service = service
    message.admin = admin
    message.put()
    return True


def _get_custom_icon_library(user):
    if user:
        custom_icons_filename = user.email().encode('utf-8').replace('@', '.')
        custom_icons_path = os.path.join(CURRENT_DIR, "%s.zip" % custom_icons_filename)
        if os.path.exists(custom_icons_path):
            return (custom_icons_path, unicode(custom_icons_filename + '-'))
    return None


@returns([LibraryMenuIconTO])
@arguments(user=users.User)
def list_icon_library(user=None):
    icon_libraries = []  # list with tuples: (<path to ZIP>, <icon name prefix>)
    custom_library = _get_custom_icon_library(user)
    if custom_library:
        icon_libraries.insert(0, custom_library)

    result = list()

    for lib, prefix in icon_libraries:
        zipf = ZipFile(lib)
        try:
            for file_name in zipf.namelist():
                if os.path.dirname(file_name) == '50':
                    smi = LibraryMenuIconTO()
                    smi.name = unicode(os.path.splitext(os.path.basename(file_name))[0])
                    if not smi.name:  # file_name is the directory
                        continue
                    smi.name = prefix + smi.name
                    smi.label = smi.name
                    result.append(smi)
        finally:
            zipf.close()

    for icon in FA_ICONS:
        name = icon.replace(u'fa-', u'').replace(u'-', u' ')
        iconTO = LibraryMenuIconTO()
        iconTO.name = icon
        iconTO.label = name
        result.append(iconTO)
    return sorted(result, key=lambda k: k.label)


@cached(1, lifetime=0, request=True, memcache=False, datastore="icon-from-library")
@returns(str)
@arguments(name=unicode, size=int)
def get_icon_from_library(name, size=512):
    if '-' in name:
        custom_libs = [f for f in os.listdir(CURRENT_DIR) if f != 'icons.zip' and f.endswith('.zip')]
        for custom_lib_file in custom_libs:
            custom_lib_name = os.path.splitext(custom_lib_file)[0]  # removing the .zip extension
            if name.startswith(custom_lib_name):
                icon_filename = name.split('-', 1)[1]
                zipf = ZipFile(os.path.join(CURRENT_DIR, custom_lib_file))
                try:
                    return zipf.read("%s/%s.png" % (size, icon_filename))
                except KeyError:
                    logging.exception("Did not found icon '%s'. Falling back to default library." % name)
                finally:
                    zipf.close()

    zipf = ZipFile(ICON_LIBRARY_PATH)
    try:
        return zipf.read("%s/%s.png" % (size, name))
    except KeyError:
        return zipf.read("%s/%s.png" % (size, "anonymous"))  # show question mark for custom icons
    finally:
        zipf.close()


def _validate_coordinates(coords):
    if not coords or len(coords) != 3:
        raise InvalidMenuItemCoordinatesException()
    if not (-1 < coords[0] < 4):
        raise InvalidMenuItemCoordinatesException()
    if not (-1 < coords[1] < 4):
        raise InvalidMenuItemCoordinatesException()
    if coords[2] < 0:
        raise InvalidMenuItemCoordinatesException()
    if coords[2] == 0 and coords[1] == 0:
        raise ReservedMenuItemException()


def _validate_roles(service_user, role_ids):
    for role_id, role in zip(role_ids, get_service_roles_by_ids(service_user, role_ids)):
        if not role:
            raise RoleNotFoundException(role_id)


@returns(NoneType)
@arguments(service_user=users.User, icon_name=unicode, icon_color=unicode, label=unicode, tag=unicode, coords=[int],
           screen_branding=unicode, static_flow_name=unicode, requires_wifi=bool, run_in_background=bool,
           roles=[(int, long)], is_broadcast_settings=bool, broadcast_branding=unicode)
def create_menu_item(service_user, icon_name, icon_color, label, tag, coords, screen_branding, static_flow_name,
                     requires_wifi, run_in_background, roles, is_broadcast_settings=False, broadcast_branding=None):
    _validate_coordinates(coords)
    _validate_roles(service_user, roles)
    if not icon_name:
        raise InvalidValueException(u"icon_name", u"Icon name required")
    if not label:
        raise InvalidValueException("label", u"Label required")
    azzert(service_user)

    if is_broadcast_settings:
        tag = ServiceMenuDef.TAG_MC_BROADCAST_SETTINGS
        channel.send_message(service_user, u'rogerthat.broadcast.changes')
    elif not tag:
        raise InvalidValueException("tag", u"Tag required")
    elif tag.startswith(MC_RESERVED_TAG_PREFIX):
        raise ReservedTagException()

    try:
        png_bytes = get_icon_from_library(icon_name)
    except:
        logging.exception("Failed to get icon '%s' from library.", icon_name)
        raise InvalidValueException("icon_name", u"Icon not found")

    if icon_color:
        if icon_color.startswith('#'):
            icon_color = icon_color[1:]
        try:
            color = parse_color(icon_color)
        except:
            raise InvalidValueException("icon_color", u"Invalid color")
        else:
            png_bytes = recolor_png(png_bytes, (0, 0, 0), color)
            icon_blob = db.Blob(png_bytes)
            icon_hash = md5_hex(png_bytes)
    else:
        icon_color = icon_blob = icon_hash = None

    static_flow_key = str(
        get_service_message_flow_design_key_by_name(service_user, static_flow_name)) if static_flow_name else None

    def trans():
        smd = ServiceMenuDef(key=ServiceMenuDef.createKey(coords, service_user), label=label,
                             tag=tag, timestamp=now(), icon=icon_blob, iconHash=icon_hash,
                             iconName=icon_name, iconColor=icon_color, screenBranding=screen_branding,
                             staticFlowKey=static_flow_key, isBroadcastSettings=is_broadcast_settings,
                             requiresWifi=requires_wifi, runInBackground=run_in_background, roles=roles)

        mapped_tag = ServiceMenuDefTagMap(key_name=smd.hashed_tag, parent=parent_key(service_user),
                                          timestamp=smd.timestamp, tag=smd.tag)
        to_put = [smd, mapped_tag]

        if is_broadcast_settings:
            service_profile = get_service_profile(service_user, cached=False)
            bizz_check(service_profile.broadcastTypes,
                       u"You can not create a broadcast settings menu item if there are no broadcast types. You can add new broadcast types at Broadcast center.")
            service_profile.broadcastBranding = broadcast_branding
            service_profile.addFlag(ServiceProfile.FLAG_CLEAR_BROADCAST_SETTINGS_CACHE)
            to_put.append(service_profile)

        put_and_invalidate_cache(*to_put)

        bump_menuGeneration_of_all_identities_and_update_friends(service_user)

    db.run_in_transaction(trans)


@returns(NoneType)
@arguments(service_user=users.User, source_coords=[int], target_coords=[int])
def move_menu_item(service_user, source_coords, target_coords):
    _validate_coordinates(source_coords)
    _validate_coordinates(target_coords)

    def trans():
        smd = get_service_menu_item_by_coordinates(service_user, source_coords)

        new_smd = ServiceMenuDef(key=ServiceMenuDef.createKey(target_coords, service_user))
        for prop in (p for p in ServiceMenuDef.properties().iterkeys() if p != '_class'):
            setattr(new_smd, prop, getattr(smd, prop))
        new_smd.put()

        smd.delete()
        bump_menuGeneration_of_all_identities_and_update_friends(service_user)

    db.run_in_transaction(trans)


@returns(NoneType)
@arguments(service_user=users.User, column=int, label=unicode)
def set_reserved_item_caption(service_user, column, label):
    if column < 0 or column > 3:
        raise InvalidMenuItemCoordinatesException()

    def trans():
        service_profile = get_service_profile(service_user)
        logging.info("Updating %s's %s to %s" % (service_user.email(), MENU_ITEM_LABEL_ATTRS[column], label))
        setattr(service_profile, MENU_ITEM_LABEL_ATTRS[column], label)
        service_profile.version += 1
        service_profile.put()
        schedule_update_all_friends_of_service_user(service_profile)

    db.run_in_transaction(trans)


@returns(bool)
@arguments(service_user=users.User, coords=[int])
def delete_menu_item(service_user, coords):
    _validate_coordinates(coords)

    def trans():
        smi = get_service_menu_item_by_coordinates(service_user, coords)
        if smi:
            smi.delete()
            bump_menuGeneration_of_all_identities_and_update_friends(service_user)
        return smi

    smi = run_in_transaction(trans)
    if smi and smi.isBroadcastSettings:
        channel.send_message(service_user, u'rogerthat.broadcast.changes')

    return bool(smi)


@returns(NoneType)
@arguments(service_user=users.User)
def bump_menuGeneration_of_all_identities_and_update_friends(service_user):
    service_identities = list(get_service_identities(service_user))
    for service_identity in service_identities:
        service_identity.menuGeneration += 1
        service_identity.version += 1
    put_and_invalidate_cache(*service_identities)
    if db.is_in_transaction():
        service_profile_or_user = get_service_profile(service_user, False)
    else:
        service_profile_or_user = service_user
    schedule_update_all_friends_of_service_user(service_profile_or_user)


@returns(ServiceMenuDetailTO)
@arguments(service_user=users.User)
def get_menu(service_user):
    service_identity_user = create_service_identity_user(service_user)
    service_identity = get_service_identity(service_identity_user)
    return ServiceMenuDetailTO.fromServiceIdentity(service_identity, False)


@returns(unicode)
@arguments(service_identity_user=users.User, target_user=(users.User, UserProfile))
def calculate_icon_color_from_branding(service_identity_user, target_user):
    icon_color = None
    si = get_service_identity(service_identity_user)
    if si.menuBranding:
        branding_hash = si.menuBranding
        if target_user:
            target_user_profile = target_user if isinstance(target_user, UserProfile) else get_user_profile(target_user)
            service_user = get_service_user_from_service_identity_user(service_identity_user)
            translator = get_translator(service_user, [ServiceTranslation.HOME_BRANDING], target_user_profile.language)
            branding_hash = translator.translate(ServiceTranslation.HOME_BRANDING, branding_hash,
                                                 target_user_profile.language)
        branding = get_branding(branding_hash)
        icon_color = branding.menu_item_color
    if not icon_color:
        icon_color = Branding.DEFAULT_MENU_ITEM_COLORS[Branding.DEFAULT_COLOR_SCHEME]
    return icon_color


@returns(tuple)
@arguments(smd=ServiceMenuDef, service_identity_user=users.User, target_user=(users.User, UserProfile))
def get_menu_icon(smd, service_identity_user, target_user=None):
    if smd.icon:
        return str(smd.icon), smd.iconHash

    icon_color = calculate_icon_color_from_branding(service_identity_user, target_user)

    icon = _render_dynamic_menu_icon_cached(smd.iconName, icon_color)
    icon_hash = get_menu_icon_hash(smd.iconName, icon_color)
    return icon, icon_hash


@db.non_transactional()
@cached(1, 0, datastore="dynamic_menu_icon")
@returns(str)
@arguments(icon_name=unicode, icon_color=unicode)
def _render_dynamic_menu_icon_cached(icon_name, icon_color):
    color = parse_color(icon_color)
    png_bytes = get_icon_from_library(icon_name)
    png_bytes = recolor_png(png_bytes, (0, 0, 0), color)
    return png_bytes


@returns(unicode)
@arguments(icon_name=str, icon_color=unicode)
def get_menu_icon_hash(icon_name, icon_color):
    return unicode(md5_hex(icon_name + icon_color))


@db.non_transactional()
@cached(1, 0, datastore="menu_icon")
@returns(str)
@arguments(icon=str, size=int)
def render_menu_icon(icon, size):
    return images.resize(icon, size, size)


@returns(NoneType)
@arguments(email=unicode, svc_index=search.Index, loc_index=search.Index)
def _cleanup_search_index(email, svc_index, loc_index):
    svc_index.delete([email])
    cursor = search.Cursor()
    while True:
        query = search.Query(query_string='service:"%s"' % email, options=search.QueryOptions(cursor=cursor, limit=10))
        search_result = loc_index.search(query)
        loc_index.delete([r.doc_id for r in search_result.results])
        if search_result.number_found != 10:
            break
        cursor = search_result.cursor


@returns(NoneType)
@arguments(service_identity_user=users.User)
def remove_service_identity_from_index(service_identity_user):
    svc_index = search.Index(name=SERVICE_INDEX)
    loc_index = search.Index(name=SERVICE_LOCATION_INDEX)

    email = service_identity_user.email()

    _cleanup_search_index(email, svc_index, loc_index)


@returns(NoneType)
@arguments(service_identity_user=users.User)
def re_index(service_identity_user):
    service_user = get_service_user_from_service_identity_user(service_identity_user)
    azzert(not is_trial_service(service_user))

    service_identity = db.run_in_transaction(get_service_identity, service_identity_user)

    svc_index = search.Index(name=SERVICE_INDEX)
    loc_index = search.Index(name=SERVICE_LOCATION_INDEX)

    email = service_identity_user.email()

    # cleanup any previous index entry
    _cleanup_search_index(email, svc_index, loc_index)

    # re-add if necessary
    sc, locs = get_search_config(service_identity_user)
    if not sc.enabled:
        return

    service_profile = get_service_profile(service_user)

    fields = [search.AtomField(name='service', value=email),
              search.TextField(name='qualified_identifier', value=service_identity.qualifiedIdentifier),
              search.TextField(name='name', value=service_identity.name.lower()),
              search.TextField(name='description', value=service_identity.description),
              search.TextField(name='keywords', value=sc.keywords),
              search.TextField(name='app_ids', value=" ".join(service_identity.appIds)),
              search.NumberField(name='organization_type', value=service_profile.organizationType)
              ]

    translator = get_translator(service_user, [ServiceTranslation.IDENTITY_TEXT])
    for language in translator.non_default_supported_languages:
        language = convert_web_lang_to_iso_lang(language)
        name = 'qualified_identifier_%s' % language
        value = translator.translate(ServiceTranslation.IDENTITY_TEXT, service_identity.qualifiedIdentifier, language)
        fields.append(search.TextField(name=name, value=value))

        name = 'name_%s' % language
        value = translator.translate(ServiceTranslation.IDENTITY_TEXT, service_identity.name, language)
        fields.append(search.TextField(name=name, value=value.lower()))

        name = 'description_%s' % language
        value = translator.translate(ServiceTranslation.IDENTITY_TEXT, service_identity.description, language)
        fields.append(search.TextField(name=name, value=value))

    svc_index.put(search.Document(doc_id=email, fields=fields))

    if locs:
        for loc in locs:
            loc_index.put(search.Document(
                fields=fields + [
                    search.GeoField(name='location', value=search.GeoPoint(float(loc.lat) / GEO_POINT_FACTOR,
                                                                           float(loc.lon) / GEO_POINT_FACTOR))
                ]))


@returns(FindServiceResponseTO)
@arguments(app_user=users.User, search_string=unicode, geo_point=GeoPointWithTimestampTO, organization_type=int,
           cursor_string=unicode, avatar_size=int)
def find_service(app_user, search_string, geo_point, organization_type, cursor_string=None, avatar_size=50):
    def get_name_sort_options():
        sort_expr = search.SortExpression(expression='name', direction=search.SortExpression.ASCENDING)
        return search.SortOptions(expressions=[sort_expr])

    def get_location_sort_options(lat, lon):
        loc_expr = "distance(location, geopoint(%f, %f))" % (lat, lon)
        sort_expr = search.SortExpression(expression=loc_expr,
                                          direction=search.SortExpression.ASCENDING,
                                          default_value=VERY_FAR)
        return search.SortOptions(expressions=[sort_expr])

    limit = 10  # limit per category (except 'My Services', this one has no limit)
    results = []
    results_cursor = None
    suggestions_nearby = []
    suggestions_nearby_cursor = None

    app_id = get_app_id_from_app_user(app_user)

    my_service_identities = dict()
    my_profile_info = get_profile_info(app_user, skip_warning=True)
    if my_profile_info.owningServiceEmails:
        my_owning_service_identity_users = [create_service_identity_user(users.User(owning_service_email)) for
                                            owning_service_email in my_profile_info.owningServiceEmails]
        for si in get_service_identities_by_service_identity_users(my_owning_service_identity_users):
            my_service_identities[si.service_identity_user.email()] = si
    for si in get_service_identities_via_user_roles(app_user, app_id, organization_type):
        my_service_identities[si.service_identity_user.email()] = si

    # cursor_string format:
    #     1/ not used anymore
    #     2(;search_string)/<search-string-without-location cursor>  # ;search_string is optional
    #     3(;lat;lon)/<search-nearby cursor>                         # ;lat;lon is optional

    if geo_point:
        lat, lon = geo_point.latitude_degrees, geo_point.longitude_degrees
    else:
        lat, lon = None, None

    if cursor_string:
        cursor_type, cursor_web_safe_string = cursor_string.split('/', 1)
        if cursor_type.startswith('2;'):  # search_string included in cursor
            cursor_type, search_string = cursor_type.split(';', 1)
            search_string = base64.b64decode(search_string).decode('utf-8')
        elif cursor_type.startswith('3;'):  # lat,lon included in cursor
            cursor_type, lat, lon = cursor_type.split(';', 2)
            lat, lon = float(lat), float(lon)
    else:
        cursor_type = cursor_web_safe_string = None

    if geo_point and (cursor_type in (None, '3')):
        the_index = search.Index(name=SERVICE_LOCATION_INDEX)
        # Query generic (not on search_string) for nearby services
        try:
            query_string = u"app_ids:%s" % app_id
            if organization_type != ServiceProfile.ORGANIZATION_TYPE_UNSPECIFIED:
                query_string += u" organization_type:%s" % organization_type

            query = search.Query(query_string=query_string,
                                 options=search.QueryOptions(returned_fields=['service', 'location'],
                                                             sort_options=get_location_sort_options(lat, lon),
                                                             limit=limit,
                                                             cursor=search.Cursor(cursor_web_safe_string,
                                                                                  per_result=True)))
            search_result = the_index.search(query)
            if search_result.results:
                suggestions_nearby.extend(search_result.results)
                suggestions_nearby_cursor = '3;%s;%s/%s' % (lat, lon, search_result.results[-1].cursor.web_safe_string)
            else:
                suggestions_nearby_cursor = None
        except:
            logging.error('Search query error', exc_info=True)

    # Search results
    if cursor_type in (None, '2'):
        the_index = search.Index(name=SERVICE_INDEX)
        try:
            query_string = u"%s app_ids:%s" % (normalize_search_string(search_string), app_id)
            if organization_type != ServiceProfile.ORGANIZATION_TYPE_UNSPECIFIED:
                query_string += u" organization_type:%s" % organization_type

            query = search.Query(query_string=query_string,
                                 options=search.QueryOptions(returned_fields=['service'],
                                                             sort_options=get_name_sort_options(),
                                                             limit=limit - len(results),
                                                             cursor=search.Cursor(cursor_web_safe_string,
                                                                                  per_result=True)))
            search_result = the_index.search(query)
            if search_result.results:
                results.extend(search_result.results)
                results_cursor = '2;%s/%s' % (base64.b64encode(search_string.encode('utf-8')),
                                              search_result.results[-1].cursor.web_safe_string)
            else:
                results_cursor = None
        except:
            logging.error('Search query error for search_string "%s"', search_string, exc_info=True)

    # Make dict of distances of results
    service_identity_closest_distances = dict()
    if geo_point:
        for result in suggestions_nearby + results:
            svc_identity_email = result.fields[0].value
            degrees = list()
            if len(result.fields) < 2:
                # No location found for this result
                if svc_identity_email not in service_identity_closest_distances:
                    for search_location in get_search_locations(users.User(svc_identity_email)):
                        degrees.append((float(search_location.lat) / GEO_POINT_FACTOR,
                                        float(search_location.lon) / GEO_POINT_FACTOR))
            else:
                degrees.append((result.fields[1].value.latitude, result.fields[1].value.longitude))

            for svc_latitude, svc_longitude in degrees:
                distance = haversine(lon, lat, svc_longitude, svc_latitude)
                service_identity_closest_distances[svc_identity_email] = \
                    min(distance, service_identity_closest_distances.get(svc_identity_email, VERY_FAR))

    def get_email_addresses_no_dups(results):
        # Can have lots of duplicates due to
        # 1. identities with multiple locations
        # 2. identities which are found both in location index and regular index
        service_identity_emails_dups = [result.fields[0].value for result in results]
        service_identity_emails_no_dups = []
        for email in service_identity_emails_dups:
            if email not in service_identity_emails_no_dups:
                service_identity_emails_no_dups.append(email)
        return service_identity_emails_no_dups

    search_result_full_email_addresses = get_email_addresses_no_dups(results)  # contains /+default+
    suggestions_nearby_full_email_addresses = get_email_addresses_no_dups(suggestions_nearby)  # contains /+default+

    users_ = list()
    users_.extend(map(users.User, search_result_full_email_addresses))
    users_.extend(map(users.User, suggestions_nearby_full_email_addresses))
    users_.append(app_user)

    profile_infos = get_profile_infos(users_, allow_none_in_results=True)
    user_profile = profile_infos.pop(-1)
    profile_info_dict = {p.user.email(): p for p in profile_infos if p and p.isServiceIdentity}

    def create_FindServiceItemTO(email):
        if not email in profile_info_dict:
            return None
        return FindServiceItemTO.fromServiceIdentity(profile_info_dict[email],
                                                     user_profile.language,
                                                     int(service_identity_closest_distances.get(email, -1)),
                                                     avatar_size=avatar_size)

    result = FindServiceResponseTO()
    result.matches = list()
    result.error_string = None

    if geo_point and cursor_type in (None, '3'):
        category_suggestions_nearby = FindServiceCategoryTO()
        category_suggestions_nearby.category = localize(user_profile.language, u"Nearby services")
        category_suggestions_nearby.items = [i for i in
                                             map(create_FindServiceItemTO, suggestions_nearby_full_email_addresses) if
                                             i]
        category_suggestions_nearby.cursor = suggestions_nearby_cursor
        result.matches.append(category_suggestions_nearby)

    # if cursor is not None, then don't add the "No matching services found" category
    if search_result_full_email_addresses or cursor_type in (None, '2'):
        category_search_results = FindServiceCategoryTO()
        category_search_results.cursor = results_cursor
        category_search_results.items = [i for i in map(create_FindServiceItemTO, search_result_full_email_addresses) if
                                         i]
        if not category_search_results.items and cursor_type is None:
            if search_string and search_string.strip():
                category_search_results.category = localize(user_profile.language, u"No matching service found")
            else:
                category_search_results.category = localize(user_profile.language, u"No service found")
        elif search_string and search_string.strip():
            category_search_results.category = localize(user_profile.language, u"Search results")
        else:
            category_search_results.category = u"A-Z"

        if search_string and search_string.strip():
            result.matches.insert(0, category_search_results)
        else:
            result.matches.append(category_search_results)

    if not cursor_string and my_service_identities:
        # show all my services; do not filter away those to which I am already connected
        category_my_services = FindServiceCategoryTO()
        category_my_services.category = localize(user_profile.language, u"My services")
        category_my_services.items = sorted([FindServiceItemTO.fromServiceIdentity(si, user_profile.language,
                                                                                   avatar_size=avatar_size)
                                             for si in my_service_identities.values()],
                                            key=lambda item: item.name)
        category_my_services.cursor = None
        result.matches.append(category_my_services)

    return result


def _generate_api_key(name, service_user, prefix="ak"):
    key = generate_random_key()
    ak = APIKey(key_name=prefix + key)
    ak.user = service_user
    ak.timestamp = now()
    ak.name = name
    return ak


def _warn_user_menu_outdated(service_identity_user, app_user, context):
    service_identity, user_profile = get_profile_infos([service_identity_user, app_user],
                                                       expected_types=[ServiceIdentity, UserProfile])

    if not user_profile.mobiles:
        return

    def trans():
        bump_friend_map_generation = get_service_profile(service_identity.service_user).updatesPending
        return send_update_friend_request(app_user, service_identity_user, UpdateFriendRequestTO.STATUS_MODIFIED,
                                          bump_friend_map_generation=bump_friend_map_generation)

    xg_on = db.create_transaction_options(xg=True)
    friendTO = db.run_in_transaction_options(xg_on, trans)

    if friendTO:
        # Send update request over channel API
        friend_dict = serialize_complex_value(friendTO, FriendTO, False)
        # Preventing "InvalidMessageError: Message must be no longer than 32767 chars"
        del friend_dict['appData']
        del friend_dict['userData']
        channel.send_message(app_user, u'rogerthat.friends.update',
                             friend=friend_dict)


@returns()
@arguments(app_user=users.User, service_identity_user=users.User, id_=int, method=unicode, params=unicode,
           hashed_tag=unicode)
def send_api_call(app_user, service_identity_user, id_, method, params, hashed_tag):
    try_or_defer(_send_api_call, app_user, service_identity_user, id_, method, params, hashed_tag)


@returns()
@arguments(app_user=users.User, service_identity_user=users.User, id_=int, method=unicode, params=unicode,
           hashed_tag=unicode)
def _send_api_call(app_user, service_identity_user, id_, method, params, hashed_tag):
    from rogerthat.service.api import system
    service_user, identifier = get_service_identity_tuple(service_identity_user)

    def trans():
        service_profile = get_service_profile(service_user)
        azzert(service_profile)

        bizz_check(get_friend_serviceidentity_connection(app_user, service_identity_user),
                   "Can not send api call to %s (there's no friend-service connection)" % service_identity_user.email())

        if hashed_tag:
            mapped_tag = ServiceMenuDefTagMap.get_by_key_name(hashed_tag, parent=parent_key(service_user))
            azzert(mapped_tag)
            tag = mapped_tag.tag
        else:
            tag = None

        context = system.api_call(send_api_call_response_receiver, logServiceError, service_profile,
                                  email=get_human_user_from_app_user(app_user).email(), method=method, params=params,
                                  tag=tag,
                                  service_identity=identifier,
                                  user_details=[UserDetailsTO.fromUserProfile(get_user_profile(app_user))],
                                  DO_NOT_SAVE_RPCCALL_OBJECTS=True)
        if context:
            context.human_user = app_user
            context.id = id_
            context.put()
        else:
            _send_api_call_result_request(app_user, id_, None, None)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


@mapping(u'system.api_call.response_handler')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=SendApiCallCallbackResultTO)
def send_api_call_response_receiver(context, result):
    try_or_defer(received_api_call_result, context.human_user, context.service_identity_user, context.id,
                 result.result if result else None, result.error if result else None)


def _send_api_call_result_request(app_user, id_, result, error):
    request = ReceiveApiCallResultRequestTO()
    request.id = id_
    request.result = result
    request.error = error
    receiveApiCallResult(receive_api_call_result_response_handler, logError, app_user, request=request)


@returns(NoneType)
@arguments(app_user=users.User, service_identity_user=users.User, id_=int, result=unicode, error=unicode)
def received_api_call_result(app_user, service_identity_user, id_, result, error):
    def trans():
        if not get_friend_serviceidentity_connection(app_user, service_identity_user):
            raise FriendNotFoundException()

        _send_api_call_result_request(app_user, id_, result, error)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


@mapping('com.mobicage.capi.services.receive_api_call_result_response_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=ReceiveApiCallResultResponseTO)
def receive_api_call_result_response_handler(context, result):
    pass


@mapping('com.mobicage.capi.services.update_user_data_response_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=UpdateUserDataResponseTO)
def update_user_data_response_handler(context, result):
    pass


@returns(NoneType)
@arguments(service_identity_user=users.User, friend_user=users.User, data_string=unicode, replace=bool)
def set_user_data(service_identity_user, friend_user, data_string, replace=False):
    def trans(json_dict):
        user_data_key = UserData.createKey(friend_user, service_identity_user)
        friend_map, user_data = db.get([get_friends_map_key_by_user(friend_user), user_data_key])
        if not friend_map:
            raise FriendNotFoundException()

        friend_detail_user = remove_slash_default(service_identity_user)
        if friend_detail_user not in friend_map.friends:
            raise FriendNotFoundException()

        if user_data:
            if replace:
                user_data.data = None
                if user_data.userData is None:
                    user_data.userData = KVStore(user_data_key)
                else:
                    user_data.userData.clear()
            elif user_data.userData is None:
                user_data.userData = KVStore(user_data_key)
                if user_data.data:
                    data = json.loads(user_data.data)
                    data.update(json_dict)
                    json_dict = data
                user_data.data = None
        else:
            user_data = UserData(key=user_data_key,
                                 data=None,
                                 userData=KVStore(user_data_key))

        puts = list()
        disabledBroadcastTypesKey = '%sdisabledBroadcastTypes' % MC_RESERVED_TAG_PREFIX
        if disabledBroadcastTypesKey in json_dict:
            service_profile, fsic = db.get(
                [get_profile_key(get_service_user_from_service_identity_user(service_identity_user)),
                 FriendServiceIdentityConnection.createKey(friend_user, service_identity_user)])
            fsic.disabled_broadcast_types = json_dict[disabledBroadcastTypesKey]
            fsic.enabled_broadcast_types = list(
                set(service_profile.broadcastTypes) - set(fsic.disabled_broadcast_types))
            puts.append(fsic)
            json_dict.pop(disabledBroadcastTypesKey)

        try:
            user_data.userData.from_json_dict(json_dict, remove_none_values=True)
        except InvalidKeyError, e:
            raise InvalidKeyException(key=e.key)

        friend_detail = friend_map.friendDetails[friend_detail_user.email()]
        if len(user_data.userData.keys()) > 0:
            puts.append(user_data)  # create or update UserData
            friend_detail.hasUserData = True
        else:
            db.delete_async(user_data_key)
            friend_detail.hasUserData = False
        friend_detail.relationVersion += 1
        friend_map.generation += 1

        puts.append(friend_map)

        put_and_invalidate_cache(*puts)

        # The mobile that triggered this request should not be updated.
        mobile = users.get_current_mobile()
        skip_mobiles = [mobile.account] if mobile else None

        # defer updateFriend capi call
        _defer_update_friend(friend_map, service_identity_user, UpdateFriendRequestTO.STATUS_MODIFIED,
                             skip_mobiles=skip_mobiles)

    json_dict = _get_json_dict_from_string(data_string)
    if not json_dict:
        return

    run_in_xg_transaction(trans, json_dict)


@returns(dict)
@arguments(kv_store=KVStore, keys=[unicode])
def _get_data_from_kv_store(kv_store, keys):
    result = dict()
    for key in keys:
        data = kv_store.get(key)
        if data:
            result[key] = data.getvalue() if hasattr(data, 'getvalue') else data
    return result


@returns(dict)
@arguments(json_str=unicode)
def _get_json_dict_from_string(json_str):
    try:
        json_dict = json.loads(json_str)
    except:
        raise InvalidJsonStringException()
    if json_dict is None:
        raise InvalidJsonStringException()
    if not isinstance(json_dict, dict):
        raise InvalidJsonStringException()
    return json_dict


@returns(unicode)
@arguments(service_identity_user=users.User, friend_user=users.User, user_data_keys=[unicode])
def get_user_data(service_identity_user, friend_user, user_data_keys):
    def trans():
        result = {key: None for key in user_data_keys}
        user_data = db.get(UserData.createKey(friend_user, service_identity_user))
        if user_data:
            if user_data.userData:
                result.update(_get_data_from_kv_store(user_data.userData, user_data_keys))
            else:
                data = json.loads(user_data.data)
                for key in user_data_keys:
                    result[key] = data.get(key)
        return result

    return json.dumps(db.run_in_transaction(trans))


@returns(unicode)
@arguments(service_identity_user=users.User, data_string=unicode)
def set_app_data(service_identity_user, data_string):
    def trans(json_dict):
        si = get_service_identity(service_identity_user)
        if not si.serviceData:
            si.serviceData = KVStore(si.key())

        if si.appData:
            old_app_data = json.loads(si.appData)
            old_app_data.update(json_dict)
            json_dict = old_app_data
        si.appData = None
        try:
            si.serviceData.from_json_dict(json_dict, remove_none_values=True)
        except InvalidKeyError, e:
            raise InvalidKeyException(e.key)
        si.put()

    json_dict = _get_json_dict_from_string(data_string)
    if not json_dict:
        return

    db.run_in_transaction(trans, json_dict)


@returns(unicode)
@arguments(service_identity_user=users.User, keys=[unicode])
def get_app_data(service_identity_user, keys):
    def trans():
        result = {key: None for key in keys}
        si = get_service_identity(service_identity_user)
        if si.serviceData:
            result.update(_get_data_from_kv_store(si.serviceData, keys))
        else:
            data = json.loads(si.appData)
            for key in keys:
                result[key] = data.get(key)
        return result

    return json.dumps(db.run_in_transaction(trans))


@returns(unicode)
@arguments(service_user=users.User)
def validate_and_get_solution(service_user):
    server_settings = get_server_settings()
    for solution, service_creator in chunks(server_settings.serviceCreators, 2):
        if service_user.email() == service_creator:
            return solution if solution else None
    raise CreateServiceDeniedException()


@returns()
@arguments(service_user=users.User, app_ids=[unicode])
def validate_app_admin(service_user, app_ids):
    app_keys = list()
    for app_id in app_ids:
        if not app_id:
            raise InvalidAppIdException(app_id=app_id)
        app_keys.append(App.create_key(app_id))

    apps = App.get(app_keys)
    for app_id, app in zip(app_ids, apps):
        if not app:
            from rogerthat.bizz.app import AppDoesNotExistException
            raise AppDoesNotExistException(app_id)
        if service_user.email() not in app.admin_services:
            raise AppOperationDeniedException(app.app_id)


@returns(tuple)
@arguments(email=unicode, name=unicode, password=unicode, languages=[unicode], solution=unicode, category_id=unicode, \
           organization_type=int, fail_if_exists=bool, supported_app_ids=[unicode],
           callback_configuration=ServiceCallbackConfigurationTO, beacon_auto_invite=bool, owner_user_email=unicode)
def create_service(email, name, password, languages, solution, category_id, organization_type, fail_if_exists=True,
                   supported_app_ids=None, callback_configuration=None, beacon_auto_invite=True, owner_user_email=None):
    service_email = email
    new_service_user = users.User(service_email)

    def update(service_profile, service_identity):
        # runs in transaction started in create_service_profile
        if callback_configuration:
            callbacks = 0
            for function in callback_configuration.functions:
                if function in SERVICE_API_CALLBACK_MAPPING:
                    callbacks |= SERVICE_API_CALLBACK_MAPPING[function]
                else:
                    raise CallbackNotDefinedException(function)
            configure_profile(service_profile, callback_configuration.jid, callback_configuration.uri, callbacks)
        else:
            configure_profile_for_mobidick(service_profile)
        service_profile.supportedLanguages = languages
        service_profile.passwordHash = sha256_hex(password)
        service_profile.lastUsedMgmtTimestamp = now()
        service_profile.termsAndConditionsVersion = 1
        service_profile.solution = solution
        service_profile.sik = unicode(generate_random_key())
        service_profile.category_id = category_id
        service_profile.organizationType = organization_type
        service_profile.version = 1

        service_identity.qualifiedIdentifier = owner_user_email
        service_identity.beacon_auto_invite = beacon_auto_invite
        service_identity.content_branding_hash = None

        sik = SIKKey(key_name=service_profile.sik)
        sik.user = new_service_user
        api_key = _generate_api_key(solution or "mobidick", new_service_user)

        to_put = [sik, api_key]

        if owner_user_email:
            user_profile = get_user_profile(users.User(owner_user_email), cached=False)
            if user_profile:
                logging.info('Coupling user %s to %s', owner_user_email, service_email)
                if service_email not in user_profile.owningServiceEmails:
                    user_profile.owningServiceEmails.append(service_email)
                if not user_profile.passwordHash:
                    user_profile.passwordHash = password_hash
                    user_profile.isCreatedForService = True
                to_put.append(user_profile)
            else:
                logging.info('Coupling new user %s to %s', owner_user_email, service_email)
                user_profile = create_user_profile(users.User(owner_user_email), owner_user_email, languages[0])
                user_profile.isCreatedForService = True
                user_profile.owningServiceEmails = [service_email]
                update_password_hash(user_profile, password_hash, now())

        put_and_invalidate_cache(*to_put)
        # service_profile and service_identity are put in transaction in create_service_profile
        return sik, api_key

    # Check that there are no users with this e-mail address
    profile = get_service_or_user_profile(users.User(service_email), cached=False)
    if profile and isinstance(profile, UserProfile):
        raise UserWithThisEmailAddressAlreadyExistsException(service_email)

    password_hash = sha256_hex(password)

    if get_service_profile(new_service_user, cached=False):
        if fail_if_exists:
            raise ServiceAlreadyExistsException()
        else:
            api_keys = list(get_api_keys(new_service_user))

            def trans():
                service_profile = get_service_profile(new_service_user)
                service_profile.passwordHash = password_hash
                service_profile.put()
                sik = SIKKey(key_name=service_profile.sik)
                if api_keys:
                    logging.info("api_keys set")
                    api_key = api_keys[0]
                else:
                    logging.info("api_keys not set")
                    ak = _generate_api_key("Main", new_service_user)
                    ak.put()
                    api_key = ak.ak
                return sik, api_key

            xg_on = db.create_transaction_options(xg=True)
            return db.run_in_transaction_options(xg_on, trans)

    if category_id and not get_friend_category_by_id(category_id):
        raise CategoryNotFoundException()

    try:
        name = _validate_name(name)
    except ValueError:
        logging.debug("Invalid name", exc_info=1)
        raise InvalidNameException()

    for language in languages:
        if language not in OFFICIALLY_SUPPORTED_LANGUAGES:
            raise UnsupportedLanguageException()

    if supported_app_ids:
        @db.non_transactional
        def validate_supported_apps():
            for app_id, app in zip(supported_app_ids, App.get(map(App.create_key, supported_app_ids))):
                if not app:
                    raise InvalidAppIdException(app_id)

        validate_supported_apps()

    sik, api_key = create_service_profile(new_service_user, name, False, update, supported_app_ids=supported_app_ids)[2]

    return sik, api_key


@returns(NoneType)
@arguments(service_user=users.User)
def publish_changes(service_user):
    # Leave service_profile.autoUpdating as it is, just send updates to the connected users if there are updates
    def trans():
        service_profile = get_service_profile(service_user, False)
        azzert(service_profile)

        if service_profile.updatesPending:
            service_profile.updatesPending = False
            service_profile.put()

            schedule_update_all_friends_of_service_user(service_profile, force=True)

        return service_profile

    service_profile = db.run_in_transaction(trans)
    channel.send_message(service_user, 'rogerthat.service.updatesPendingChanged',
                         updatesPending=service_profile.updatesPending)


@returns(NoneType)
@arguments(service_user=users.User, broadcast_type=unicode)
def validate_broadcast_type(service_user, broadcast_type):
    service_profile = get_service_profile(service_user, False)
    if broadcast_type not in service_profile.broadcastTypes:
        logging.debug('Unknown broadcast type: %s\nKnown broadcast types are: %s',
                      broadcast_type, service_profile.broadcastTypes)
        raise InvalidBroadcastTypeException(broadcast_type)


@returns(NoneType)
@arguments(service_identity=ServiceIdentity, app_id=unicode)
def valididate_app_id_for_service_identity(service_identity, app_id):
    if app_id not in service_identity.appIds:
        raise InvalidAppIdException(app_id)


@returns(NoneType)
@arguments(service_identity_user=users.User, app_id=unicode)
def valididate_app_id_for_service_identity_user(service_identity_user, app_id):
    valididate_app_id_for_service_identity(get_service_identity(service_identity_user), app_id)


@returns(unicode)
@arguments(service_identity=ServiceIdentity, app_id=unicode)
def get_and_validate_app_id_for_service_identity(service_identity, app_id):
    if not app_id or app_id is MISSING:
        return service_identity.app_id
    valididate_app_id_for_service_identity(service_identity, app_id)
    return app_id


@returns(unicode)
@arguments(service_identity_user=users.User, app_id=unicode)
def get_and_validate_app_id_for_service_identity_user(service_identity_user, app_id):
    return get_and_validate_app_id_for_service_identity(get_service_identity(service_identity_user), app_id)
