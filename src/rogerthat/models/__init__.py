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

from collections import namedtuple
import datetime
import hashlib
import json
import logging
import time
import urllib
import urlparse
import uuid
import zlib

from rogerthat.consts import MC_RESERVED_TAG_PREFIX, IOS_APPSTORE_IOS_URI_FORMAT, IOS_APPSTORE_WEB_URI_FORMAT, \
    ANDROID_MARKET_ANDROID_URI_FORMAT, ANDROID_MARKET_WEB_URI_FORMAT, ANDROID_BETA_MARKET_WEB_URI_FORMAT
from rogerthat.models.properties.app import AutoConnectedServicesProperty, AutoConnectedService
from rogerthat.models.properties.forms import FormProperty
from rogerthat.models.properties.friend import FriendDetailsProperty
from rogerthat.models.properties.keyvalue import KeyValueProperty
from rogerthat.models.properties.messaging import ButtonsProperty, MemberStatusesProperty, JsFlowDefinitionsProperty, \
    AttachmentsProperty, SpecializedList
from rogerthat.models.properties.profiles import MobileDetailsProperty
from rogerthat.models.utils import get_meta, add_meta
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile
from rogerthat.translations import DEFAULT_LANGUAGE, localize
from rogerthat.utils import azzert, base38, base65, llist, now, calculate_age_from_date, set_flag, unset_flag, \
    is_flag_set
from rogerthat.utils.crypto import sha256_hex, encrypt
from google.appengine.api.datastore_errors import ReferencePropertyResolveError
from google.appengine.ext import db
from google.appengine.ext.blobstore import blobstore
from google.appengine.ext.db import polymodel
from mcfw.cache import CachedModelMixIn, invalidate_cache
from mcfw.serialization import deserializer, ds_model, register, s_model, s_long, ds_long, serializer, \
    model_deserializer

class ArchivedModel(object):

    def archive(self, clazz):
        key = db.Key.from_path(clazz.kind(), self.key().id_or_name(), parent=self.parent_key())
        am = clazz(key=key)
        for propname, propobject in self.properties().iteritems():
            if propname == "_class" or get_meta(propobject, 'skip_on_archive', False):
                continue
            value = getattr(self, propname)
            setattr(am, propname, value)
        return am

    @staticmethod
    def constructArchivedModel(newClassName, originalClass):
        azzert(issubclass(originalClass, db.Model))

        properties = dict(originalClass.properties())
        if '_class' in properties:
            del properties['_class']
        NewClass = type(newClassName, (db.Model, ArchivedModel), properties)
        return NewClass

    @staticmethod
    def skip_on_archive(prop):
        add_meta(prop, skip_on_archive=True)


class AppSettings(CachedModelMixIn, db.Model):
    wifi_only_downloads = db.BooleanProperty(indexed=False, default=False)
    background_fetch_timestamps = db.ListProperty(int, indexed=False)  # seconds since midnight, UTC

    @property
    def app_id(self):
        return self.key().name()

    @classmethod
    def create_key(cls, app_id):
        return db.Key.from_path(cls.kind(), app_id)

    def invalidateCache(self):
        from rogerthat.dal.app import get_app_settings
        logging.info("App '%s' removed from cache." % self.app_id)
        invalidate_cache(get_app_settings, self.app_id)


class App(CachedModelMixIn, db.Model):
    APP_ID_ROGERTHAT = u"rogerthat"
    APP_ID_OSA_LOYALTY = u"osa-loyalty"

    APP_TYPE_ROGERTHAT = 0
    APP_TYPE_CITY_APP = 1
    APP_TYPE_ENTERPRISE = 2
    APP_TYPE_OSA_LOYALTY = 3
    APP_TYPE_YSAAA = 4

    TYPE_STRINGS = {APP_TYPE_ROGERTHAT: u"Rogerthat",
                    APP_TYPE_CITY_APP: u"CityApp",
                    APP_TYPE_ENTERPRISE: u"Enterprise",
                    APP_TYPE_OSA_LOYALTY: u"OSA Loyalty",
                    APP_TYPE_YSAAA: u"YSAAA",
                    }

    name = db.StringProperty(indexed=False)
    type = db.IntegerProperty(indexed=True)
    core_branding_hash = db.StringProperty(indexed=False)
    facebook_registration_enabled = db.BooleanProperty(indexed=False)
    facebook_app_id = db.IntegerProperty(indexed=False)
    facebook_app_secret = db.StringProperty(indexed=False)
    facebook_user_access_token = db.StringProperty(indexed=False)  # access token from the user who created the app. Valid for 60 days only.
    ios_app_id = db.StringProperty(indexed=False)
    android_app_id = db.StringProperty(indexed=False)
    user_regex = db.TextProperty(indexed=False)
    visible = db.BooleanProperty(indexed=True, default=True)
    creation_time = db.IntegerProperty(indexed=False)
    apple_push_cert = db.TextProperty(indexed=False)
    apple_push_key = db.TextProperty(indexed=False)
    apple_push_cert_valid_until = db.IntegerProperty()
    auto_connected_services = AutoConnectedServicesProperty()
    is_default = db.BooleanProperty(indexed=True)
    qrtemplate_keys = db.StringListProperty(indexed=False)
    dashboard_email_address = db.StringProperty(indexed=False)
    contact_email_address = db.StringProperty(indexed=False)
    admin_services = db.StringListProperty(indexed=False)
    beacon_major = db.IntegerProperty(indexed=False)
    beacon_last_minor = db.IntegerProperty(indexed=False)
    orderable_app_ids = db.StringListProperty(indexed=False)
    demo = db.BooleanProperty(indexed=True, default=False)
    beta = db.BooleanProperty(indexed=False, default=False)
    mdp_client_id = db.StringProperty(indexed=False)
    mdp_client_secret = db.StringProperty(indexed=False)

    def invalidateCache(self):
        from rogerthat.dal.app import get_app_by_id, get_app_and_translations_by_app_id
        logging.info("App '%s' removed from cache." % self.app_id)
        invalidate_cache(get_app_by_id, self.app_id)
        invalidate_cache(get_app_and_translations_by_app_id, self.app_id)

    def is_in_appstores(self):
        return self.android_app_id and self.ios_app_id

    @property
    def app_id(self):
        return self.key().name()

    @property
    def beacon_uuid(self):
        return u'f7826da6-4fa2-4e98-8024-bc5b71e0893e'

    @property
    def type_str(self):
        azzert(self.type in self.TYPE_STRINGS)
        return self.TYPE_STRINGS[self.type]

    @property
    def ios_appstore_web_uri(self):
        return IOS_APPSTORE_WEB_URI_FORMAT % self.ios_app_id

    @property
    def ios_appstore_ios_uri(self):
        return IOS_APPSTORE_IOS_URI_FORMAT % self.ios_app_id

    @property
    def android_market_android_uri(self):
        if self.beta:
            return ANDROID_BETA_MARKET_WEB_URI_FORMAT % self.android_app_id
        return ANDROID_MARKET_ANDROID_URI_FORMAT % self.android_app_id

    @property
    def android_market_web_uri(self):
        if self.beta:
            return ANDROID_BETA_MARKET_WEB_URI_FORMAT % self.android_app_id
        return ANDROID_MARKET_WEB_URI_FORMAT % self.android_app_id

    @property
    def supports_mdp(self):
        return self.mdp_client_id and self.mdp_client_secret

    def get_contact_email_address(self):
        return self.contact_email_address if self.contact_email_address else u"info@mobicage.com"

    def beacon_regions(self, keys_only=False):
        return BeaconRegion.all(keys_only=keys_only).ancestor(self)

    @staticmethod
    def create_key(app_id):
        return db.Key.from_path(App.kind(), app_id)


class AppTranslations(CachedModelMixIn, db.Model):
    """
    Contains a json object in this format:
    translations['en']['translation'] = 'test'
    """
    translations = db.BlobProperty()

    def invalidateCache(self):
        from rogerthat.dal.app import get_app_by_id, get_app_and_translations_by_app_id
        logging.info("App '%s' removed from cache." % self.app_id)
        invalidate_cache(get_app_by_id, self.app_id)
        invalidate_cache(get_app_and_translations_by_app_id, self.app_id)

    @classmethod
    def create_key(cls, app_id):
        return db.Key.from_path(cls.kind(), cls.kind(), parent=App.create_key(app_id))

    @classmethod
    def get_or_create(cls, app_id):
        translations = cls.get(cls.create_key(app_id))
        if not translations:
            translations = AppTranslations(parent=App.create_key(app_id))
            translations.put()
        return translations

    @classmethod
    def get_by_app_id(cls, app_id):
        return cls.get(cls.create_key(app_id))

    @property
    def translations_dict(self):
        translations_dict = getattr(self, '_translations_dict', None)
        if translations_dict is None:
            self._translations_dict = json.loads(zlib.decompress(self.translations)) if self.translations else None
        return self._translations_dict

    @property
    def app_id(self):
        return self.parent_key().name()

    def get_translation(self, lang, key, **kwargs):
        D = self.translations_dict
        if D is None:
            return None
        if not lang:
            lang = DEFAULT_LANGUAGE
        lang = lang.replace('-', '_')
        if lang not in D:
            if '_' in lang:
                lang = lang.split('_')[0]
                if lang not in D:
                    lang = DEFAULT_LANGUAGE
            else:
                lang = DEFAULT_LANGUAGE
        if lang not in D:
            return None
        langdict = D[lang]
        if key not in langdict:
            if lang == DEFAULT_LANGUAGE:
                return None
            # Fall back to default language
            logging.warn("App %s translation %s not found in language %s - fallback to default", self.app_id,
                         key, lang)
            lang = DEFAULT_LANGUAGE
            if lang not in D:
                return None
            langdict = D[lang]
        if key not in langdict:
            return None
        return langdict[key] % kwargs


AppAndTranslations = namedtuple('AppAndTranslations', 'app translations')


class AuthorizedUser(db.Model):
    user = db.UserProperty()

class ClientDistro(db.Model):
    user = db.UserProperty()
    timestamp = db.IntegerProperty()
    type = db.IntegerProperty()
    version = db.StringProperty()
    releaseNotes = db.TextProperty()
    package = blobstore.BlobReferenceProperty()

class UserLocation(db.Model):
    members = db.ListProperty(users.User)
    geoPoint = db.GeoPtProperty(indexed=False)
    accuracy = db.IntegerProperty(indexed=False)
    timestamp = db.IntegerProperty(indexed=False)

    @property
    def user(self):
        return users.User(self.key().name())

class _Settings(db.Model):
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 4
    THURSDAY = 8
    FRIDAY = 16
    SATERDAY = 32
    SUNDAY = 64

    WORK_DAYS = MONDAY | TUESDAY | WEDNESDAY | THURSDAY | FRIDAY
    ALL_DAYS = WORK_DAYS | SATERDAY | SUNDAY

    user = db.UserProperty()
    timestamp = db.IntegerProperty()
    recordPhoneCalls = db.BooleanProperty()
    recordPhoneCallsDays = db.IntegerProperty()
    recordPhoneCallsTimeslot = db.ListProperty(int)
    recordGeoLocationWithPhoneCalls = db.BooleanProperty()
    geoLocationTracking = db.BooleanProperty()
    geoLocationTrackingDays = db.IntegerProperty()
    geoLocationTrackingTimeslot = db.ListProperty(int)
    geoLocationSamplingIntervalBattery = db.IntegerProperty()
    geoLocationSamplingIntervalCharging = db.IntegerProperty()
    useGPSBattery = db.BooleanProperty()
    useGPSCharging = db.BooleanProperty()
    xmppReconnectInterval = db.IntegerProperty()

class Settings(_Settings):
    MINIMUM_INTERVAL = 15 * 60

    @staticmethod
    def get(user=None):
        if not user:
            user = users.get_current_user()
        db_settings = Settings.all().filter("user =", user).get()
        if not db_settings:
            db_settings = Settings()
            db_settings.user = user
            db_settings.timestamp = int(time.time())
            db_settings.recordPhoneCalls = True
            db_settings.recordPhoneCallsDays = Settings.WORK_DAYS
            db_settings.recordPhoneCallsTimeslot = [0, (24 * 3600) - 1]
            db_settings.recordGeoLocationWithPhoneCalls = True
            db_settings.geoLocationTracking = True
            db_settings.geoLocationTrackingDays = Settings.ALL_DAYS
            db_settings.geoLocationTrackingTimeslot = [0, (24 * 3600) - 1]
            db_settings.geoLocationSamplingIntervalBattery = Settings.MINIMUM_INTERVAL
            db_settings.geoLocationSamplingIntervalCharging = Settings.MINIMUM_INTERVAL
            db_settings.useGPSBattery = False
            db_settings.useGPSCharging = True
            db_settings.xmppReconnectInterval = Settings.MINIMUM_INTERVAL  # 15 minutes in order to able to join up with others on android
            db_settings.put()
        return db_settings

class MobileSettings(_Settings):
    mobile = db.ReferenceProperty(Mobile)
    color = db.StringProperty()
    majorVersion = db.IntegerProperty()
    minorVersion = db.IntegerProperty()
    lastHeartBeat = db.IntegerProperty()
    version = db.IntegerProperty(default=1)

    @staticmethod
    def get(mobile=None):
        if mobile is None:
            mobile = users.get_current_mobile()
        mob_settings = MobileSettings.all().filter("mobile =", mobile.key()).get()
        if not mob_settings:
            user_settings = Settings.get(mobile.user)
            mob_settings = MobileSettings()
            mob_settings.user = mobile.user
            mob_settings.mobile = mobile
            mob_settings.timestamp = int(time.time())
            mob_settings.recordPhoneCalls = True
            mob_settings.recordPhoneCallsDays = user_settings.recordPhoneCallsDays
            mob_settings.recordPhoneCallsTimeslot = user_settings.recordPhoneCallsTimeslot
            mob_settings.recordGeoLocationWithPhoneCalls = user_settings.recordGeoLocationWithPhoneCalls
            mob_settings.geoLocationTracking = user_settings.geoLocationTracking
            mob_settings.geoLocationTrackingDays = user_settings.geoLocationTrackingDays
            mob_settings.geoLocationTrackingTimeslot = user_settings.geoLocationTrackingTimeslot
            mob_settings.geoLocationSamplingIntervalBattery = user_settings.geoLocationSamplingIntervalBattery
            mob_settings.geoLocationSamplingIntervalCharging = user_settings.geoLocationSamplingIntervalCharging
            mob_settings.useGPSBattery = user_settings.useGPSBattery
            mob_settings.useGPSCharging = user_settings.useGPSCharging
            mob_settings.xmppReconnectInterval = user_settings.xmppReconnectInterval
            mob_settings.color = u"#000000"
            mob_settings.majorVersion = 0
            mob_settings.minorVersion = 0
            mob_settings.lastHeartBeat = 0
            mob_settings.put()
        return mob_settings

class CellTower(db.Model):
    cid = db.IntegerProperty()
    lac = db.IntegerProperty()
    net = db.IntegerProperty()
    geoPoint = db.GeoPtProperty()

class Avatar(db.Model, ArchivedModel):
    user = db.UserProperty()
    picture = db.BlobProperty()

class AvatarArchive(Avatar):
    pass

class FriendMap(db.Model, ArchivedModel):
    shareContacts = db.BooleanProperty(default=True)
    friends = db.ListProperty(users.User)
    friendDetails = FriendDetailsProperty()
    generation = db.IntegerProperty()
    version = db.IntegerProperty(indexed=False, default=0)  # bumped every time a friend is added/removed

    @property
    def user(self):
        return users.User(self.parent_key().name())

class FriendMapArchive(FriendMap):
    pass

class UserData(db.Model, ArchivedModel):
    data = db.TextProperty()  # deprecated, lazily migrated to userData when putting user_data
    userData = KeyValueProperty()

    @property
    def service_identity_user(self):
        return users.User(self.key().name())

    @property
    def app_user(self):
        return users.User(self.parent_key().name())

    @classmethod
    def createKey(cls, app_user, service_identity_user):
        from rogerthat.dal import parent_key
        azzert('/' in service_identity_user.email(), 'no slash in %s' % service_identity_user.email())
        return db.Key.from_path(cls.kind(), service_identity_user.email(), parent=parent_key(app_user))

class UserDataArchive(UserData):
    pass


class FriendServiceIdentityConnection(db.Model, ArchivedModel):
    friend_name = db.StringProperty()  # duplicate info - for performance + listing all users
    friend_avatarId = db.IntegerProperty(indexed=False)  # duplicate info - for performance
    friend_avatar_id = db.IntegerProperty(indexed=False)  # duplicate info - for performance
    service_identity_email = db.StringProperty()  # Needed to find all humans connected to a svc
    enabled_broadcast_types = db.StringListProperty()  # Needed for querying
    disabled_broadcast_types = db.StringListProperty(indexed=False)
    birthdate = db.IntegerProperty(indexed=True)  # Needed for querying (broadcast)
    gender = db.IntegerProperty(indexed=True)  # Needed for querying (broadcast)
    app_id = db.StringProperty(indexed=True, default=App.APP_ID_ROGERTHAT)  # Needed for querying

    # Should always construct using this factory method
    @staticmethod
    def createFriendServiceIdentityConnection(friend_user, friend_name, friend_avatarId, service_identity_user,
                                              broadcast_types, birthdate, gender, app_id):
        return FriendServiceIdentityConnection(key=FriendServiceIdentityConnection.createKey(friend_user,
                                                                                             service_identity_user),
                                               friend_name=friend_name,
                                               friend_avatarId=friend_avatarId,
                                               service_identity_email=service_identity_user.email(),
                                               disabled_broadcast_types=list(),
                                               enabled_broadcast_types=broadcast_types,
                                               birthdate=birthdate,
                                               gender=gender,
                                               app_id=app_id)

    @staticmethod
    def createKey(friend_user, service_identity_user):
        from rogerthat.dal import parent_key
        azzert('/' in service_identity_user.email(), 'no slash in %s' % service_identity_user.email())
        return db.Key.from_path(FriendServiceIdentityConnection.kind(),
                                service_identity_user.email(),
                                parent=parent_key(friend_user))

    @property
    def service_identity(self):  # this is historical, a better name was service_identity_user
        return users.User(self.key().name())

    @property
    def service_identity_user(self):
        return users.User(self.key().name())

    @property
    def friend(self):
        return users.User(self.parent_key().name())


FriendServiceIdentityConnectionArchive = ArchivedModel.constructArchivedModel("FriendServiceIdentityConnectionArchive",
                                                                              FriendServiceIdentityConnection)


class FriendInvitationHistory(db.Model):
    # parent_key of invitor user or invitor service_identity
    # key = invited user or service_identity
    inviteTimestamps = db.ListProperty(int, indexed=False)
    tag = db.StringProperty(indexed=False)
    lastAttemptKey = db.StringProperty()

    @staticmethod
    def create(invitor_user, invitee_user):
        return FriendInvitationHistory(key=FriendInvitationHistory.createKey(invitor_user, invitee_user))

    @staticmethod
    def createKey(invitor_user, invitee_user):
        from rogerthat.dal import parent_key_unsafe
        from rogerthat.utils.service import remove_slash_default
        # Do not azzert /
        return db.Key.from_path(FriendInvitationHistory.kind(),
                                remove_slash_default(invitee_user).email(),
                                parent=parent_key_unsafe(remove_slash_default(invitor_user)))

    @property
    def user(self):
        return users.User(self.parent_key().name())

    @property
    def invitee(self):
        return users.User(self.key().name())

class DoNotSendMeMoreInvites(db.Model):
    pass

class Code(db.Model):
    author = db.UserProperty()
    timestamp = db.IntegerProperty()
    name = db.StringProperty()
    source = db.TextProperty()
    functions = db.StringListProperty()
    version = db.IntegerProperty()

class TrialServiceAccount(db.Model):
    owner = db.UserProperty()
    service = db.UserProperty()
    password = db.StringProperty(indexed=False)
    creationDate = db.IntegerProperty()


class Profile(CachedModelMixIn, polymodel.PolyModel):
    avatarId = db.IntegerProperty(indexed=False, default=-1)
    avatarHash = db.StringProperty(indexed=False)
    passwordHash = db.StringProperty(indexed=False)
    termsAndConditionsVersion = db.IntegerProperty(indexed=False, default=0)
    lastUsedMgmtTimestamp = db.IntegerProperty(indexed=False, default=0)
    country = db.StringProperty(indexed=False)
    timezone = db.StringProperty(indexed=False)
    timezoneDeltaGMT = db.IntegerProperty(indexed=False)

    @classmethod
    def createKey(cls, user):
        from rogerthat.dal import parent_key
        return db.Key.from_path(cls.kind(), user.email(), parent=parent_key(user))

    @property
    def user(self):
        return users.User(self.parent_key().name())

    def invalidateCache(self):
        from rogerthat.dal.profile import _get_profile
        logging.info("Profile %s removed from cache.", self.user)
        _get_profile.invalidate_cache(self.user)  # @UndefinedVariable

    @property
    def avatarUrl(self):
        from rogerthat.settings import get_server_settings
        return u"%s/unauthenticated/mobi/cached/avatar/%s" % (get_server_settings().baseUrl, self.avatarId)

class ProfileInfo(object):

    @property
    def isServiceIdentity(self):
        raise Exception("Illegal method")

class UserProfile(Profile, ProfileInfo, ArchivedModel):
    GENDER_MALE_OR_FEMALE = 0
    GENDER_MALE = 1
    GENDER_FEMALE = 2
    GENDER_CUSTOM = 3
    _GENDER_STRINGS = {GENDER_MALE_OR_FEMALE: u"MALE_OR_FEMALE",
                       GENDER_MALE: u"MALE",
                       GENDER_FEMALE: u"FEMALE",
                       GENDER_CUSTOM: u"CUSTOM"}

    name = db.StringProperty(indexed=False)
    qualifiedIdentifier = db.StringProperty()
    language = db.StringProperty(indexed=False)
    mobiles = MobileDetailsProperty()
    ysaaa = db.BooleanProperty(indexed=False, default=False)
    birthdate = db.IntegerProperty(indexed=False)
    gender = db.IntegerProperty(indexed=False)
    roles = db.StringListProperty(indexed=False)  # list holding roles corresponding to the services in
    role_services = db.StringListProperty()  # the role_services property.
    version = db.IntegerProperty(indexed=False, default=0)  # bumped every time that FriendTO-related properties are updated
    app_id = db.StringProperty(indexed=True, default=App.APP_ID_ROGERTHAT)  # Needed for querying
    profileData = db.TextProperty()  # a JSON string containing extra profile fields
    unsubscribed_from_reminder_email = db.BooleanProperty(indexed=False, default=False)

    isCreatedForService = db.BooleanProperty(indexed=False, default=False)
    owningServiceEmails = db.StringListProperty(indexed=True)

    ArchivedModel.skip_on_archive(roles)
    ArchivedModel.skip_on_archive(role_services)

    @property
    def isServiceIdentity(self):
        return False

    @property
    def age(self):
        return calculate_age_from_date(datetime.date.fromtimestamp(self.birthdate)) if self.birthdate is not None else None

    @property
    def gender_str(self):
        if self.gender is None:
            return None
        azzert(self.gender in self._GENDER_STRINGS)
        return self._GENDER_STRINGS[self.gender]

    @classmethod
    def gender_from_string(cls, gender_str):
        for k, v in cls._GENDER_STRINGS.iteritems():
            if gender_str == v:
                return k
        return None

    @property
    def grants(self):
        if not hasattr(self, '_grants'):
            g = dict()
            for service_identity, role in zip(self.role_services or list(), self.roles or list()):
                roles = g.setdefault(service_identity, list())
                roles.append(role)
            self._grants = g
        return self._grants

    def _update_grants(self):
        if hasattr(self, '_grants'):
            rolez = list()
            rolez_services = list()
            for service_identity, roles in self._grants.iteritems():
                for role in set(roles):
                    rolez.append(role)
                    rolez_services.append(service_identity)
            self.roles = rolez
            self.role_services = rolez_services

    def has_role(self, service_identity_user, role):
        service_identity = service_identity_user.email()
        azzert("/" in service_identity)
        return service_identity in self.grants and role in self.grants[service_identity]

    def grant_role(self, service_identity_user, role):
        service_identity = service_identity_user.email()
        azzert("/" in service_identity)
        self.grants.setdefault(service_identity, list()).append(role)
        self._update_grants()

    def revoke_role(self, service_identity_user, role, skip_warning=False):
        service_identity = service_identity_user.email()
        azzert("/" in service_identity)
        if not self.has_role(service_identity_user, role):
            if not skip_warning:
                logging.warn("Cannot revoke role %s for service_identity %s from user %s",
                             role, service_identity, self.user)
            return
        self.grants[service_identity].remove(role)
        self._update_grants()

UserProfileArchive = ArchivedModel.constructArchivedModel("UserProfileArchive", UserProfile)

class FacebookUserProfile(UserProfile, ArchivedModel):
    profile_url = db.StringProperty(False)
    access_token = db.StringProperty(False)

FacebookUserProfileArchive = ArchivedModel.constructArchivedModel("FacebookUserProfileArchive", FacebookUserProfile)

class ServiceProfile(Profile):
    CALLBACK_FRIEND_INVITE_RESULT = 1
    CALLBACK_FRIEND_INVITED = 2
    CALLBACK_FRIEND_BROKE_UP = 4
    CALLBACK_FRIEND_IN_REACH = 512
    CALLBACK_FRIEND_OUT_OF_REACH = 1024
    CALLBACK_FRIEND_IS_IN_ROLES = 2048
    CALLBACK_FRIEND_UPDATE = 8192
    CALLBACK_FRIEND_LOCATION_FIX = 65536
    CALLBACK_FRIEND_REGISTER = 131072
    CALLBACK_FRIEND_REGISTER_RESULT = 262144
    CALLBACK_MESSAGING_RECEIVED = 8
    CALLBACK_MESSAGING_POKE = 16
    CALLBACK_MESSAGING_ACKNOWLEDGED = 128
    CALLBACK_MESSAGING_FLOW_MEMBER_RESULT = 64
    CALLBACK_MESSAGING_FORM_ACKNOWLEDGED = 32
    CALLBACK_MESSAGING_NEW_CHAT_MESSAGE = 4096
    CALLBACK_MESSAGING_CHAT_DELETED = 32768
    CALLBACK_MESSAGING_LIST_CHAT_MESSAGES = 1048576
    CALLBACK_SYSTEM_API_CALL = 256
    CALLBACK_SYSTEM_SERVICE_DELETED = 16384
    CALLBACK_SYSTEM_BRANDINGS_UPDATED = 524288


    CALLBACKS = (CALLBACK_FRIEND_INVITE_RESULT, CALLBACK_FRIEND_INVITED, CALLBACK_FRIEND_BROKE_UP,
                 CALLBACK_MESSAGING_RECEIVED, CALLBACK_MESSAGING_POKE, CALLBACK_MESSAGING_FLOW_MEMBER_RESULT,
                 CALLBACK_MESSAGING_ACKNOWLEDGED, CALLBACK_MESSAGING_FORM_ACKNOWLEDGED, CALLBACK_SYSTEM_API_CALL,
                 CALLBACK_SYSTEM_SERVICE_DELETED, CALLBACK_SYSTEM_BRANDINGS_UPDATED,
                 CALLBACK_FRIEND_IN_REACH, CALLBACK_FRIEND_OUT_OF_REACH, CALLBACK_FRIEND_IS_IN_ROLES,
                 CALLBACK_FRIEND_UPDATE, CALLBACK_MESSAGING_NEW_CHAT_MESSAGE, CALLBACK_MESSAGING_CHAT_DELETED,
                 CALLBACK_FRIEND_LOCATION_FIX, CALLBACK_FRIEND_REGISTER, CALLBACK_FRIEND_REGISTER_RESULT)

    ORGANIZATION_TYPE_UNSPECIFIED = -1
    ORGANIZATION_TYPE_NON_PROFIT = 1
    ORGANIZATION_TYPE_PROFIT = 2
    ORGANIZATION_TYPE_CITY = 3
    ORGANIZATION_TYPE_EMERGENCY = 4
    # don't forget to update ServiceProfile.localizedOrganizationType when adding an organization type

    FLAG_CLEAR_BROADCAST_SETTINGS_CACHE = 1
    FLAGS = (FLAG_CLEAR_BROADCAST_SETTINGS_CACHE,)

    callBackURI = db.StringProperty(indexed=False)
    sik = db.StringProperty(indexed=False)
    callBackJid = db.StringProperty(indexed=False)
    enabled = db.BooleanProperty(indexed=False)
    testCallNeeded = db.BooleanProperty(indexed=False, default=True)
    testValue = db.StringProperty(indexed=False)
    callbacks = db.IntegerProperty(indexed=False, default=CALLBACK_FRIEND_INVITE_RESULT | CALLBACK_FRIEND_INVITED \
                                   | CALLBACK_FRIEND_BROKE_UP | CALLBACK_FRIEND_UPDATE \
                                   | CALLBACK_MESSAGING_POKE | CALLBACK_MESSAGING_RECEIVED \
                                   | CALLBACK_MESSAGING_FLOW_MEMBER_RESULT | CALLBACK_MESSAGING_ACKNOWLEDGED \
                                   | CALLBACK_MESSAGING_FORM_ACKNOWLEDGED | CALLBACK_SYSTEM_API_CALL)
    lastWarningSent = db.IntegerProperty(indexed=False)
    aboutMenuItemLabel = db.StringProperty(indexed=False)
    messagesMenuItemLabel = db.StringProperty(indexed=False)
    shareMenuItemLabel = db.StringProperty(indexed=False)
    callMenuItemLabel = db.StringProperty(indexed=False)
    supportedLanguages = db.StringListProperty(indexed=False, default=[DEFAULT_LANGUAGE])
    activeTranslationSet = db.StringProperty(indexed=False)
    editableTranslationSet = db.StringProperty(indexed=False)
    broadcastTypes = db.StringListProperty(indexed=False)
    broadcastTestPersons = db.ListProperty(users.User, indexed=False)
    broadcastBranding = db.StringProperty(indexed=False)
    solution = db.StringProperty(indexed=False)
    monitor = db.BooleanProperty(indexed=True)
    autoUpdating = db.BooleanProperty(indexed=False, default=False)  # Auto-updates suspended by default
    updatesPending = db.BooleanProperty(indexed=False, default=False)
    category_id = db.StringProperty(indexed=False)
    organizationType = db.IntegerProperty(indexed=False, default=ORGANIZATION_TYPE_PROFIT)
    version = db.IntegerProperty(indexed=False, default=0)  # bumped every time that FriendTO-related properties are updated
    flags = db.IntegerProperty(indexed=False, default=0)
    canEditSupportedApps = db.BooleanProperty(indexed=False, default=False)
    expiredAt = db.IntegerProperty(default=0)

    @property
    def usesHttpCallback(self):
        return not self.callBackURI is None

    def callbackEnabled(self, callback):
        return self.callbacks & callback == callback

    @property
    def defaultLanguage(self):
        return self.supportedLanguages[0]

    @property
    def service_user(self):
        return self.user

    def addFlag(self, flag):
        azzert(flag in ServiceProfile.FLAGS)
        self.flags = set_flag(flag, self.flags)

    def clearFlag(self, flag):
        self.flags = unset_flag(flag, self.flags)

    def isFlagSet(self, flag):
        return is_flag_set(flag, self.flags)

    def localizedOrganizationType(self, language):
        if self.organizationType == ServiceProfile.ORGANIZATION_TYPE_NON_PROFIT:
            return localize(language, 'Associations')
        elif self.organizationType == ServiceProfile.ORGANIZATION_TYPE_PROFIT:
            return localize(language, 'Merchants')
        elif self.organizationType == ServiceProfile.ORGANIZATION_TYPE_CITY:
            return localize(language, 'Community Services')
        elif self.organizationType == ServiceProfile.ORGANIZATION_TYPE_EMERGENCY:
            return localize(language, 'Care')
        elif self.organizationType == ServiceProfile.ORGANIZATION_TYPE_UNSPECIFIED:
            return localize(language, 'Services')
        else:
            raise ValueError('Missing translation for organizationType %s' % self.organizationType)


class ProfileHashIndex(db.Model):
    user = db.UserProperty(indexed=False, required=True)

    @classmethod
    def create(cls, user):
        from rogerthat.utils import hash_user_identifier
        user_hash = hash_user_identifier(user)
        return cls(key=ProfileHashIndex.create_key(user_hash), user=user)

    @classmethod
    def create_key(cls, user_hash):
        return db.Key.from_path(cls.kind(), user_hash)


class ServiceRole(db.Model):
    TYPE_MANAGED = 'managed'
    TYPE_SYNCED = 'synced'
    TYPES = (TYPE_MANAGED, TYPE_SYNCED)

    name = db.StringProperty()
    creationTime = db.IntegerProperty(indexed=False)
    type = db.StringProperty()

    @property
    def service_user(self):
        return users.User(self.parent_key().name())

    @property
    def role_id(self):
        return self.key().id()

class FriendCategory(db.Model):
    name = db.StringProperty(indexed=False)
    avatar = db.BlobProperty()

    @staticmethod
    def create_new_key():
        return db.Key.from_path(FriendCategory.kind(), str(uuid.uuid4()))

    @property
    def id(self):
        return self.key().name()

class ServiceAPIFailures(db.Model):
    creationTime = db.IntegerProperty(indexed=False)
    failedCalls = db.IntegerProperty(indexed=False)
    failedCallBacks = db.IntegerProperty(indexed=False)

    @property
    def service_user(self):
        return users.User(self.parent_key().name())

    @staticmethod
    def key_from_service_user_email(service_user_email):
        from rogerthat.dal import parent_key
        return db.Key.from_path(ServiceAPIFailures.kind(), service_user_email, \
                                parent=parent_key(users.User(service_user_email)))

class RogerthatBackendErrors(db.Model):
    requestIds = db.StringListProperty(indexed=False)

    @staticmethod
    def get():
        key = RogerthatBackendErrors.get_key()
        obj = db.get(key)
        if not obj:
            obj = RogerthatBackendErrors(key=key)
            obj.requestIds = list()
        return obj

    @staticmethod
    def get_key():
        return db.Key.from_path(RogerthatBackendErrors.kind(), "errors")


class Broadcast(db.Model):
    TAG_MC_BROADCAST = "%s.broadcast" % MC_RESERVED_TAG_PREFIX

    TEST_PERSON_STATUS_ACCEPTED = 1
    TEST_PERSON_STATUS_DECLINED = 0
    TEST_PERSON_STATUS_UNDECIDED = -1

    name = db.StringProperty(indexed=False)
    type_ = db.StringProperty(indexed=False)
    creation_time = db.IntegerProperty(indexed=False)
    message_flow = db.StringProperty(indexed=False)
    test_persons = db.ListProperty(users.User, indexed=False)
    test_persons_statuses = db.ListProperty(int, indexed=False)
    sent_time = db.IntegerProperty(indexed=False, default=0)
    tag = db.TextProperty()
    scheduled_at = db.IntegerProperty(indexed=False, default=0)

    @staticmethod
    def create(service_user):
        from rogerthat.dal import parent_key
        return Broadcast(parent=parent_key(service_user))

    @property
    def service_user(self):
        return users.User(self.parent_key().name())

    @property
    def sent(self):
        return bool(self.sent_time)

    def set_status(self, test_user, status):
        self.test_persons_statuses[self.test_persons.index(test_user)] = status

    def get_status_count(self, status):
        return sum([status == s for s in self.test_persons_statuses])

    @property
    def declined(self):
        return any((Broadcast.TEST_PERSON_STATUS_DECLINED == s for s in self.test_persons_statuses))

    @property
    def approved(self):
        return all((Broadcast.TEST_PERSON_STATUS_ACCEPTED == s for s in self.test_persons_statuses))

class BroadcastSettingsFlowCache(db.Model):
    static_flow = db.TextProperty()
    timestamp = db.IntegerProperty(indexed=True)

    @property
    def service_identity_user(self):
        return users.User(self.key().name())

    @property
    def human_user(self):  # TODO app_user
        return users.User(self.parent_key().name())

    @staticmethod
    def create_key(app_user, service_identity_user):
        from rogerthat.dal import parent_key
        return db.Key.from_path(BroadcastSettingsFlowCache.kind(), service_identity_user.email(), parent=parent_key(app_user))

class ServiceIdentity(CachedModelMixIn, db.Model, ProfileInfo):
    # In service entity group
    # KeyName will be identity identifier
    DEFAULT = u'+default+'
    FLAG_INHERIT_DESCRIPTION = 1 << 0
    FLAG_INHERIT_DESCRIPTION_BRANDING = 1 << 1
    FLAG_INHERIT_MENU_BRANDING = 1 << 2
    FLAG_INHERIT_PHONE_NUMBER = 1 << 3
    FLAG_INHERIT_PHONE_POPUP_TEXT = 1 << 4
    FLAG_INHERIT_SEARCH_CONFIG = 1 << 5
    FLAG_INHERIT_EMAIL_STATISTICS = 1 << 6
    FLAG_INHERIT_APP_IDS = 1 << 7

    DEFAULT_FLAGS_INHERIT = FLAG_INHERIT_DESCRIPTION | FLAG_INHERIT_DESCRIPTION_BRANDING | FLAG_INHERIT_MENU_BRANDING | \
                            FLAG_INHERIT_PHONE_NUMBER | FLAG_INHERIT_PHONE_POPUP_TEXT | FLAG_INHERIT_SEARCH_CONFIG | \
                            FLAG_INHERIT_EMAIL_STATISTICS | FLAG_INHERIT_APP_IDS

    name = db.StringProperty(indexed=False)
    qualifiedIdentifier = db.StringProperty()
    description = db.TextProperty()
    descriptionBranding = db.StringProperty(indexed=False)
    menuGeneration = db.IntegerProperty(indexed=False, default=0)
    menuBranding = db.StringProperty(indexed=False)
    mainPhoneNumber = db.StringProperty(indexed=False)
    shareSIDKey = db.StringProperty(indexed=False)
    shareEnabled = db.BooleanProperty(indexed=False)
    callMenuItemConfirmation = db.StringProperty(indexed=False)
    inheritanceFlags = db.IntegerProperty(indexed=False, default=0)
    creationTimestamp = db.IntegerProperty(indexed=False, default=1353906000)
    metaData = db.StringProperty(indexed=False)
    appData = db.TextProperty()  # deprecated, lazily migrated to serviceData when putting service_data
    serviceData = KeyValueProperty()
    emailStatistics = db.BooleanProperty(indexed=True, default=False)
    version = db.IntegerProperty(indexed=False, default=0)  # bumped every time that FriendTO-related properties are updated
    appIds = db.StringListProperty(indexed=True, default=[App.APP_ID_ROGERTHAT])
    beacon_auto_invite = db.BooleanProperty(indexed=False, default=True)
    contentBrandingHash = db.StringProperty(indexed=False)

    def invalidateCache(self):
        from rogerthat.dal.service import get_service_identity
        logging.info("Svc Identity %s removed from cache." % self.user.email())
        get_service_identity.invalidate_cache(self.user)  # @UndefinedVariable
        if self.is_default:
            get_service_identity.invalidate_cache(self.service_user)  # @UndefinedVariable

    @property
    def avatarId(self):
        from rogerthat.dal.profile import get_service_profile
        return get_service_profile(self.service_user).avatarId

    @property
    def avatarUrl(self):
        from rogerthat.dal.profile import get_service_profile
        return get_service_profile(self.service_user).avatarUrl

    @property
    def avatarHash(self):
        from rogerthat.dal.profile import get_service_profile
        return get_service_profile(self.service_user).avatarHash

    @property
    def supportedLanguages(self):
        from rogerthat.dal.profile import get_service_profile
        return get_service_profile(self.service_user).supportedLanguages

    @property
    def isServiceIdentity(self):
        return True

    @property
    def identifier(self):
        return self.key().name()

    @property
    def is_default(self):
        return ServiceIdentity.DEFAULT == self.identifier

    @property
    def service_user(self):
        return users.User(self.parent_key().name())

    @property
    def user(self):
        from rogerthat.utils.service import create_service_identity_user
        return create_service_identity_user(self.service_user, self.identifier)

    @property
    def service_identity_user(self):
        return self.user

    @property
    def app_id(self):
        return self.appIds[0]

    @staticmethod
    def isDefaultServiceIdentityUser(service_identity_user):
        from rogerthat.utils.service import get_identity_from_service_identity_user
        return get_identity_from_service_identity_user(service_identity_user) == ServiceIdentity.DEFAULT

    @classmethod
    def keyFromUser(cls, service_identity_user):
        from rogerthat.utils.service import get_service_identity_tuple
        azzert("/" in service_identity_user.email())
        service_user, identifier = get_service_identity_tuple(service_identity_user)
        return cls.keyFromService(service_user, identifier)

    @staticmethod
    def keyFromService(service_user, identifier):
        from rogerthat.dal import parent_key
        azzert("/" not in service_user.email())
        return db.Key.from_path(ServiceIdentity.kind(), identifier, parent=parent_key(service_user))

class ServiceTranslationSet(db.Model):
    # key path:
    #    mc-i18n - service_user_email
    #       ServiceTranslationSet - str(timestamp)
    ACTIVE = 0
    EDITABLE = 1
    SYNCING = 2
    ARCHIVED = 3

    description = db.StringProperty(indexed=False)
    status = db.IntegerProperty(indexed=False,
                                choices=[ACTIVE, EDITABLE, SYNCING, ARCHIVED])
    latest_export_timestamp = db.IntegerProperty(indexed=False)

    @property
    def service_user(self):
        return users.User(self.parent_key().name())

    @staticmethod
    def create_editable_set(service_user):
        creation_timestamp = now()
        sts = ServiceTranslationSet(parent=db.Key.from_path(u'mc-i18n', service_user.email()), key_name=str(creation_timestamp))
        sts.description = "Service translation set created at %s" % time.ctime(creation_timestamp)
        sts.status = ServiceTranslationSet.EDITABLE
        return sts

class ServiceTranslation(db.Model):
    # parent object = ServiceTranslationSet
    # key name = str(translation_type)
    #
    # zipped_translations is zipped json string of all translations of a certain type (e.g. MFLOW_TEXT)
    #   Key is string in default language of that service, value is (possibly incomplete/None) dict with translations
    #
    #   { u"How are you" : { "fr": u"Comment ca va?", "nl": u"Hoe gaat het?" },
    #     u"Cancel"      : { "fr": u"Annuler",        "nl": u"Annuleren"     },
    #     u"Incomplete"  : None,
    #   }
    #
    MFLOW_TEXT = 1
    MFLOW_BUTTON = 2
    MFLOW_FORM = 3
    MFLOW_POPUP = 4
    MFLOW_BRANDING = 5
    HOME_TEXT = 101
    HOME_BRANDING = 102
    IDENTITY_TEXT = 201
    IDENTITY_BRANDING = 202
    SID_BUTTON = 301
    BROADCAST_TYPE = 401
    BROADCAST_BRANDING = 402
    BRANDING_CONTENT = 501

    MFLOW_TYPES = [MFLOW_TEXT, MFLOW_BUTTON, MFLOW_FORM, MFLOW_POPUP, MFLOW_BRANDING]
    MFLOW_TYPES_ALLOWING_LANGUAGE_FALLBACK = [MFLOW_BRANDING]
    HOME_TYPES = [HOME_TEXT, HOME_BRANDING]
    IDENTITY_TYPES = [IDENTITY_TEXT, IDENTITY_BRANDING]
    BROADCAST_TYPES = [BROADCAST_BRANDING, BROADCAST_TYPE]
    BRANDING_TYPES = [BRANDING_CONTENT]

    TYPE_MAP = {MFLOW_BRANDING: 'Message flow message branding',
                MFLOW_BUTTON: 'Message flow button caption',
                MFLOW_FORM: 'Message flow widget setting',
                MFLOW_POPUP: 'Message flow button action',
                MFLOW_TEXT: 'Message flow text',
                IDENTITY_BRANDING: 'Service identity branding',
                IDENTITY_TEXT: 'Service identity text',
                HOME_BRANDING: 'Service menu item branding',
                HOME_TEXT: 'Service menu item label',
                SID_BUTTON: 'QR code button caption',
                BROADCAST_TYPE: 'Broadcast type',
                BROADCAST_BRANDING: 'Broadcast branding',
                BRANDING_CONTENT: 'Branding content'}

    zipped_translations = db.BlobProperty()

    @property
    def service_translation_set(self):
        return self.parent()

    @property
    def translation_type(self):
        return int(self.key().name())

    @property
    def translation_dict(self):
        return json.loads(zlib.decompress(self.zipped_translations))

    @staticmethod
    def create(service_translation_set, translation_type, translation_dict):
        st = ServiceTranslation(parent=service_translation_set, key_name=str(translation_type))
        st.zipped_translations = zlib.compress(json.dumps(translation_dict))
        return st

    @staticmethod
    def create_key(service_translation_set, translation_type):
        return db.Key.from_path('ServiceTranslation', str(translation_type), parent=service_translation_set.key())


@deserializer
def ds_profile(stream):
    type_ = ds_long(stream)
    if type_ == 1:
        return ds_model(stream, FacebookUserProfile)
    elif type_ == 3:
        return ds_model(stream, UserProfile)
    elif type_ == 4:
        return ds_model(stream, ServiceProfile)
    else:
        raise ValueError("Unknown type code: %s" % type_)

@serializer
def s_profile(stream, profile):
    if isinstance(profile, FacebookUserProfile):
        s_long(stream, 1)
        s_model(stream, profile, FacebookUserProfile)
    elif isinstance(profile, UserProfile):
        s_long(stream, 3)
        s_model(stream, profile, UserProfile)
    elif isinstance(profile, ServiceProfile):
        s_long(stream, 4)
        s_model(stream, profile, ServiceProfile)
    else:
        raise ValueError("profile is not instance of expected type Facebook/User/Service Profile, but %s" % profile.__class__.__name__)

register(Profile, s_profile, ds_profile)

@deserializer
def ds_service_identity(stream):
    return ds_model(stream, ServiceIdentity)

@serializer
def s_service_identity(stream, svc_identity):
    s_model(stream, svc_identity, ServiceIdentity)

register(ServiceIdentity, s_service_identity, ds_service_identity)

@deserializer
def ds_app(stream):
    return ds_model(stream, App)

@serializer
def s_app(stream, app):
    s_model(stream, app, App)

register(App, s_app, ds_app)

@deserializer
def ds_app_settings(stream):
    return ds_model(stream, AppSettings)

@serializer
def s_app_settings(stream, app_settings):
    s_model(stream, app_settings, AppSettings)

register(AppSettings, s_app_settings, ds_app_settings)


@deserializer
def ds_app_and_translations(stream):
    return AppAndTranslations(ds_model(stream, App), ds_model(stream, AppTranslations))


@serializer
def s_app_and_translations(stream, app_and_translations):
    s_model(stream, app_and_translations.app, App)
    s_model(stream, app_and_translations.translations, AppTranslations)


register(AppAndTranslations, s_app_and_translations, ds_app_and_translations)


class SearchConfig(db.Model):
    DEFAULT_KEY = "SEARCH"
    enabled = db.BooleanProperty(indexed=False)
    keywords = db.TextProperty()

    @classmethod
    def create_key(cls, service_identity_user):
        return db.Key.from_path(cls.kind(), cls.DEFAULT_KEY, parent=ServiceIdentity.keyFromUser(service_identity_user))

    @property
    def service_identity_user(self):
        from rogerthat.utils.service import create_service_identity_user
        si_key = self.key().parent()
        return create_service_identity_user(users.User(si_key.parent().name()), si_key.name())


class SearchConfigLocation(db.Model):
    address = db.TextProperty()
    lat = db.IntegerProperty(indexed=False)
    lon = db.IntegerProperty(indexed=False)

class ServiceAdmin(db.Model):
    user = db.UserProperty()

    @property
    def service(self):
        return users.User(self.parent_key().name())

class UserAccount(db.Model):
    type = db.StringProperty()

    @property
    def user(self):
        return users.User(self.parent_key().name())

    @property
    def account(self):
        return self.key().name()


class MyDigiPassState(db.Model):
    state = db.StringProperty(indexed=False)
    creation_time = db.DateTimeProperty(indexed=False, auto_now_add=True)

    @property
    def user(self):
        return users.User(self.key().name())

    @classmethod
    def create_key(cls, app_user):
        from rogerthat.dal import parent_key
        return db.Key.from_path(cls.kind(), app_user.email(), parent=parent_key(app_user))


class MyDigiPassProfilePointer(db.Model, ArchivedModel):
    user = db.UserProperty()
    access_token = db.StringProperty(indexed=False)

    @property
    def mdpUUID(self):
        return self.key().name()

    @property
    def profile(self):
        from rogerthat.dal import parent_key
        return Profile.get_by_key_name(self.user.email(), parent_key(self.user))

    @classmethod
    def create(cls, app_user, mdp_uuid):
        from rogerthat.dal import parent_key
        return cls(key_name=mdp_uuid, parent=parent_key(app_user))

    @classmethod
    def get_by_user(cls, app_user):
        from rogerthat.dal import parent_key
        return cls.all().ancestor(parent_key(app_user)).get()


class FacebookProfilePointer(db.Model, ArchivedModel):
    user = db.UserProperty()

    @property
    def facebookId(self):
        return self.key().name()

    @property
    def profile(self):
        from rogerthat.dal import parent_key
        return Profile.get_by_key_name(self.user.email(), parent_key(self.user))

class FacebookProfilePointerArchive(FacebookProfilePointer):
    pass

class FacebookDiscoveryInvite(db.Model):

    @property
    def from_(self):
        return users.User(self.parent_key().name())

    @property
    def to(self):
        return users.User(self.key().name())

class ProfilePointer(db.Model):
    user = db.UserProperty(indexed=False)  # can be human user (invite), or service user (e.g. for ServiceInteractionDefs), or service identity user (invite)
    short_url_id = db.IntegerProperty(indexed=False)

    @staticmethod
    def get(user_code):
        return ProfilePointer.get_by_key_name(user_code)

    @staticmethod
    def create(user):
        from rogerthat.bizz.friends import userCode
        from rogerthat.bizz.profile import create_short_url
        from rogerthat.utils.service import remove_slash_default
        user = remove_slash_default(user)
        user_code = userCode(user)
        return ProfilePointer(key_name=user_code, user=user, short_url_id=create_short_url(user_code))

    @staticmethod
    def create_key(user):
        from rogerthat.bizz.friends import userCode
        from rogerthat.utils.service import remove_slash_default
        user = remove_slash_default(user)
        user_code = userCode(user)
        return db.Key.from_path(ProfilePointer.kind(), user_code)

class ProfileDiscoveryResult(db.Model):
    TYPE_GRAVATAR = 1
    TYPE_FACEBOOK = 2
    TYPE_TWITTER = 3
    TYPE_LINKEDIN = 4

    TYPES = (TYPE_GRAVATAR, TYPE_FACEBOOK, TYPE_TWITTER)

    type = db.IntegerProperty(indexed=False)
    account = db.StringProperty(indexed=False)
    name = db.StringProperty(indexed=False)
    data = db.TextProperty()
    avatar = db.BlobProperty()
    timestamp = db.IntegerProperty()

    @property
    def user(self):
        return users.User(self.parent_key().name())


class ShortURL(db.Model):
    full = db.StringProperty(indexed=False)

    @staticmethod
    def get(id_):
        return ShortURL.get_by_id(id_)

    def qr_code_content_with_base_url(self, base_url):
        return '%s/S/%s' % (base_url, base38.encode_int(self.key().id()))

    @property
    def user_code(self):
        return self.full[4:]


class APIKey(CachedModelMixIn, db.Model):
    user = db.UserProperty()
    timestamp = db.IntegerProperty(indexed=False)
    name = db.StringProperty(indexed=False)
    mfr = db.BooleanProperty(default=False)

    def invalidateCache(self):
        from rogerthat.dal.service import get_api_key, get_mfr_api_key
        get_api_key.invalidate_cache(self.api_key)  # @PydevCodeAnalysisIgnore @UndefinedVariable
        get_mfr_api_key.invalidate_cache(self.user)  # @PydevCodeAnalysisIgnore @UndefinedVariable

    @property
    def api_key(self):
        return self.key().name()

@deserializer
def ds_apikey(stream):
    return model_deserializer(stream, APIKey)

register(APIKey, s_model, ds_apikey)

class SIKKey(CachedModelMixIn, db.Model):
    user = db.UserProperty()

    def invalidateCache(self):
        from rogerthat.dal.service import get_sik
        get_sik.invalidate_cache(self.key().name())  # @PydevCodeAnalysisIgnore @UndefinedVariable

@deserializer
def ds_sikkey(stream):
    return model_deserializer(stream, SIKKey)

register(SIKKey, s_model, ds_sikkey)

class MFRSIKey(CachedModelMixIn, db.Model):
    sik = db.StringProperty(indexed=False)

    def invalidateCache(self):
        from rogerthat.dal.service import get_mfr_sik
        get_mfr_sik.invalidate_cache(users.User(self.key().name()))  # @PydevCodeAnalysisIgnore @UndefinedVariable

@deserializer
def ds_mfrsikkey(stream):
    return model_deserializer(stream, MFRSIKey)

register(MFRSIKey, s_model, ds_mfrsikkey)

class BrandingEditorConfiguration(db.Model):
    color_scheme = db.StringProperty(indexed=False)
    background_color = db.StringProperty(indexed=False)
    text_color = db.StringProperty(indexed=False)
    menu_item_color = db.StringProperty(indexed=False)
    static_content = db.TextProperty()
    static_content_mode = db.StringProperty(indexed=False)

    @staticmethod
    def create_key(branding_hash, service_user):
        from rogerthat.dal import parent_key
        return db.Key.from_path(BrandingEditorConfiguration.kind(), branding_hash, parent=parent_key(service_user))

    @property
    def service_user(self):
        return users.User(self.parent_key().name())

class Branding(CachedModelMixIn, db.Model):
    TYPE_NORMAL = 1  # This branding can be used for messages/menu/screenBranding/descriptionBranding
    TYPE_APP = 2  # This branding contains an app.html and can only be used as static branding

    COLOR_SCHEME_LIGHT = u"light"
    COLOR_SCHEME_DARK = u"dark"
    COLOR_SCHEMES = (COLOR_SCHEME_LIGHT, COLOR_SCHEME_DARK)

    DEFAULT_COLOR_SCHEME = COLOR_SCHEME_LIGHT
    DEFAULT_MENU_ITEM_COLORS = { COLOR_SCHEME_LIGHT : u"000000", COLOR_SCHEME_DARK : u"FFFFFF" }

    CONTENT_TYPE_HTML = u"text/html"
    CONTENT_TYPE_PDF = u"application/pdf"

    description = db.StringProperty(indexed=False)
    blob = db.BlobProperty(indexed=False)
    user = db.UserProperty()
    timestamp = db.IntegerProperty(indexed=False)
    pokes = db.ListProperty(db.Key)
    type = db.IntegerProperty(indexed=True)
    menu_item_color = db.StringProperty(indexed=False)
    editor_cfg_key = db.StringProperty(indexed=False)
    content_type = db.StringProperty(indexed=False)

    @property
    def hash(self):
        return self.key().name()

    def invalidateCache(self):
        from rogerthat.dal.messaging import get_branding
        logging.info("Branding '%s' removed from cache." % self.hash)
        invalidate_cache(get_branding, self.hash)

    @classmethod
    def list_by_type(cls, service_user, branding_type):
        return cls.all().filter('user', service_user).filter('type', branding_type)

    @classmethod
    def list_by_user(cls, service_user):
        return cls.all().filter('user', service_user)

class QRTemplate(db.Model):
    DEFAULT_BLUE_PACIFIC_KEY_NAME = "Blue Pacific"
    DEFAULT_BROWN_BAG_KEY_NAME = "Brown Bag"
    DEFAULT_PINK_PANTER_KEY_NAME = "Pink Panter"

    DEFAULT_COLORS = {DEFAULT_BLUE_PACIFIC_KEY_NAME: u"1C66E6",
                      DEFAULT_BROWN_BAG_KEY_NAME: u"F57505",
                      DEFAULT_PINK_PANTER_KEY_NAME: u"ED3DED"}

    description = db.StringProperty(indexed=False)
    blob = db.BlobProperty(indexed=False)
    body_color = db.ListProperty(int, indexed=False)
    timestamp = db.IntegerProperty(indexed=False)
    deleted = db.BooleanProperty(default=False)

    @property
    def user(self):
        return users.User(self.parent_key().name())


class ChatMembers(polymodel.PolyModel):
    members = db.StringListProperty(indexed=True)

    @property
    def parent_message_key(self):
        return self.parent_key().name()

    def is_read_only(self):
        raise NotImplementedError()

    def members_size(self):
        return sum(len(m) for m in self.members)

    @classmethod
    def create_parent_key(cls, thread_key):
        from rogerthat.dal.messaging import get_message_key
        return get_message_key(thread_key, None)

    @classmethod
    def list_by_thread_and_chat_member(cls, parent_message_key, member_app_email):
        return cls.all().ancestor(cls.create_parent_key(parent_message_key)).filter('members =', member_app_email)

    @classmethod
    def list_by_thread_and_chat_members(cls, parent_message_key, member_app_emails):
        return cls.all().ancestor(cls.create_parent_key(parent_message_key)).filter('members IN', member_app_emails)

    @classmethod
    def get_last_by_thread(cls, parent_message_key):
        return cls.all().ancestor(cls.create_parent_key(parent_message_key)).order('-__key__').get()

    @classmethod
    def list_by_chat_member(cls, member_app_email, keys_only=False):
        return cls.all(keys_only=keys_only).filter('members =', member_app_email)


class ChatWriterMembers(ChatMembers):

    def is_read_only(self):
        return False


class ChatReaderMembers(ChatMembers):

    def is_read_only(self):
        return True


class AbstractChatJob(db.Model):
    user = db.UserProperty(indexed=False, required=True)
    guid = db.StringProperty(indexed=True, required=True)

    @property
    def parent_message_key(self):
        return self.parent_key().name()

    @classmethod
    def create_parent_key(cls, parent_message_key):
        from rogerthat.dal.messaging import get_message_key
        return get_message_key(parent_message_key, None)

    @classmethod
    def list_by_guid(cls, parent_message_key, guid):
        return cls.all().ancestor(cls.create_parent_key(parent_message_key)).filter('guid', guid)


class DeleteMemberFromChatJob(AbstractChatJob):
    pass


class AddMemberToChatJob(AbstractChatJob):
    read_only = db.BooleanProperty(indexed=False, required=True)


class UpdateChatMemberJob(AbstractChatJob):
    read_only = db.BooleanProperty(indexed=False, required=True)


class ThreadAvatar(db.Model):
    avatar = db.BlobProperty()
    avatar_hash = db.StringProperty(indexed=False)

    @property
    def parent_message_key(self):
        return self.parent_key().name()

    @classmethod
    def create_key(cls, parent_message_key):
        return db.Key.from_path(cls.kind(), parent_message_key,
                                parent=db.Key.from_path(Message.kind(), parent_message_key))

    @classmethod
    def create(cls, parent_message_key, avatar):
        return cls(key=cls.create_key(parent_message_key),
                   avatar=db.Blob(avatar),
                   avatar_hash=sha256_hex(avatar))


class Message(db.Expando, polymodel.PolyModel):
    TYPE = 1
    TYPE_FORM_MESSAGE = 2

    FLAG_ALLOW_DISMISS = 1
    FLAG_ALLOW_CUSTOM_REPLY = 2
    FLAG_ALLOW_REPLY = 4
    FLAG_ALLOW_REPLY_ALL = 8
    FLAG_SHARED_MEMBERS = 16
    FLAG_LOCKED = 32
    FLAG_AUTO_LOCK = 64
    FLAG_SENT_BY_MFR = 128
    FLAG_SENT_BY_JS_MFR = 256
    FLAG_DYNAMIC_CHAT = 512
    FLAG_NOT_REMOVABLE = 1024
    FLAG_ALLOW_CHAT_BUTTONS = 2048
    FLAG_CHAT_STICKY = 4096
    FLAG_ALLOW_CHAT_PICTURE = 8192
    FLAG_ALLOW_CHAT_VIDEO = 16384
    FLAG_ALLOW_CHAT_PRIORITY = 32768
    FLAG_ALLOW_CHAT_STICKY = 65536
    FLAGS = (FLAG_ALLOW_DISMISS, FLAG_ALLOW_CUSTOM_REPLY, FLAG_ALLOW_REPLY, FLAG_ALLOW_REPLY_ALL, FLAG_SHARED_MEMBERS,
             FLAG_LOCKED, FLAG_AUTO_LOCK, FLAG_SENT_BY_MFR, FLAG_SENT_BY_JS_MFR, FLAG_DYNAMIC_CHAT, FLAG_NOT_REMOVABLE,
             FLAG_ALLOW_CHAT_BUTTONS, FLAG_CHAT_STICKY, FLAG_ALLOW_CHAT_PICTURE, FLAG_ALLOW_CHAT_VIDEO,
             FLAG_ALLOW_CHAT_PRIORITY, FLAG_ALLOW_CHAT_STICKY)

    ALERT_FLAG_SILENT = 1
    ALERT_FLAG_VIBRATE = 2
    ALERT_FLAG_RING_5 = 4
    ALERT_FLAG_RING_15 = 8
    ALERT_FLAG_RING_30 = 16
    ALERT_FLAG_RING_60 = 32
    ALERT_FLAG_INTERVAL_5 = 64
    ALERT_FLAG_INTERVAL_15 = 128
    ALERT_FLAG_INTERVAL_30 = 256
    ALERT_FLAG_INTERVAL_60 = 512
    ALERT_FLAG_INTERVAL_300 = 1024
    ALERT_FLAG_INTERVAL_900 = 2048
    ALERT_FLAG_INTERVAL_3600 = 4096

    UI_FLAG_EXPECT_NEXT_WAIT_5 = 1
    UI_FLAG_AUTHORIZE_LOCATION = 2
    UI_FLAGS = (UI_FLAG_EXPECT_NEXT_WAIT_5, UI_FLAG_AUTHORIZE_LOCATION)

    ALERT_FLAGS = (ALERT_FLAG_SILENT, ALERT_FLAG_VIBRATE, ALERT_FLAG_RING_5, ALERT_FLAG_RING_15, ALERT_FLAG_RING_30, \
                   ALERT_FLAG_RING_60, ALERT_FLAG_INTERVAL_5, ALERT_FLAG_INTERVAL_15, ALERT_FLAG_INTERVAL_30, \
                   ALERT_FLAG_INTERVAL_60, ALERT_FLAG_INTERVAL_300, ALERT_FLAG_INTERVAL_900, ALERT_FLAG_INTERVAL_3600)
    RING_ALERT_FLAGS = (ALERT_FLAG_RING_5, ALERT_FLAG_RING_15, ALERT_FLAG_RING_30, ALERT_FLAG_RING_60)
    INTERVAL_ALERT_FLAGS = (ALERT_FLAG_INTERVAL_5, ALERT_FLAG_INTERVAL_15, ALERT_FLAG_INTERVAL_30, \
                            ALERT_FLAG_INTERVAL_60, ALERT_FLAG_INTERVAL_300, ALERT_FLAG_INTERVAL_900, \
                            ALERT_FLAG_INTERVAL_3600)

    MEMBER_INDEX_STATUS_NOT_RECEIVED = '1'
    MEMBER_INDEX_STATUS_SHOW_IN_INBOX = '2'
    MEMBER_INDEX_STATUS_NOT_DELETED = '3'
    MEMBER_INDEX_STATUSSES = (MEMBER_INDEX_STATUS_NOT_RECEIVED, MEMBER_INDEX_STATUS_SHOW_IN_INBOX, \
                              MEMBER_INDEX_STATUS_NOT_DELETED)
    SERVICE_MESSAGE_DEFAULT_MEMBER_INDEX_STATUSSES = (MEMBER_INDEX_STATUS_NOT_RECEIVED, \
                                                      MEMBER_INDEX_STATUS_SHOW_IN_INBOX, \
                                                      MEMBER_INDEX_STATUS_NOT_DELETED)
    USER_MESSAGE_DEFAULT_MEMBER_INDEX_STATUSSES = (MEMBER_INDEX_STATUS_NOT_RECEIVED, \
                                                   MEMBER_INDEX_STATUS_NOT_DELETED)

    PRIORITY_NORMAL = 1
    PRIORITY_HIGH = 2
    PRIORITY_URGENT = 3
    PRIORITY_URGENT_WITH_ALARM = 4

    PRIORITIES = (PRIORITY_NORMAL, PRIORITY_HIGH, PRIORITY_URGENT, PRIORITY_URGENT_WITH_ALARM)

    sender = db.UserProperty(indexed=False)
    members = db.ListProperty(users.User, indexed=False)
    flags = db.IntegerProperty(indexed=False)
    originalFlags = db.IntegerProperty(indexed=False)
    alert_flags = db.IntegerProperty(indexed=False)
    timeout = db.IntegerProperty(indexed=False)
    branding = db.StringProperty(indexed=False)
    message = db.TextProperty()
    buttons = ButtonsProperty()
    memberStatusses = MemberStatusesProperty()
    creationTimestamp = db.IntegerProperty()
    generation = db.IntegerProperty(indexed=False)
    childMessages = db.ListProperty(db.Key, indexed=False)
    tag = db.TextProperty()
    timestamp = db.IntegerProperty()
    dismiss_button_ui_flags = db.IntegerProperty(indexed=False)
    member_status_index = db.StringListProperty()
    sender_type = db.IntegerProperty()
    broadcast_type = db.StringProperty(indexed=False)
    attachments = AttachmentsProperty()
    service_api_updates = db.UserProperty(indexed=False)
    thread_avatar_hash = db.StringProperty(indexed=False)  # -------|
    thread_background_color = db.StringProperty(indexed=False)  # --| Equal for all messages in the thread
    thread_text_color = db.StringProperty(indexed=False)  # --------|
    priority = db.IntegerProperty(indexed=False)
    broadcast_guid = db.StringProperty(indexed=False)
    default_priority = db.IntegerProperty(indexed=False)  # --------|
    default_sticky = db.BooleanProperty(indexed=False)  # ----------| Only on parent message
    step_id = db.StringProperty(indexed=False)  # used for FlowStatistics

    @property
    def sharedMembers(self):
        return self.flags & Message.FLAG_SHARED_MEMBERS == self.FLAG_SHARED_MEMBERS

    @property
    def mkey(self):
        return self.key().name()

    @property
    def pkey(self):
        return self.parent_key().name() if self.parent_key() else None

    @property
    def isRootMessage(self):
        return self.parent_key() == None

    @staticmethod
    def statusIndexValue(member, status):
        return "%s@%s" % (status, member.email())

    def hasStatusIndex(self, member, status):
        statusses = self.member_status_index or []
        for stat in statusses:
            if stat == Message.statusIndexValue(member, status):
                return True
        return False

    def addStatusIndex(self, member, status):
        statusses = set(self.member_status_index or [])
        for mem in llist(member):
            for stat in llist(status):
                azzert(stat in Message.MEMBER_INDEX_STATUSSES)
                statusses.add(Message.statusIndexValue(mem, stat))
                if stat == Message.MEMBER_INDEX_STATUS_NOT_RECEIVED:
                    statusses.add(Message.MEMBER_INDEX_STATUS_NOT_RECEIVED)
        self.member_status_index = list(statusses)

    def removeStatusIndex(self, member, status):
        statusses = self.member_status_index or []
        for mem in llist(member):
            for stat in llist(status):
                azzert(stat in Message.MEMBER_INDEX_STATUSSES)
                value = Message.statusIndexValue(mem, stat)
                if value in statusses:
                    statusses.remove(value)

                    # Check if this was the last member with MEMBER_INDEX_STATUS_NOT_RECEIVED
                    if stat == Message.MEMBER_INDEX_STATUS_NOT_RECEIVED:
                        if Message.MEMBER_INDEX_STATUS_NOT_RECEIVED in statusses:
                            for remaining_status in statusses:
                                if remaining_status.startswith("%s@" % Message.MEMBER_INDEX_STATUS_NOT_RECEIVED):
                                    break
                            else:
                                # We did not break ... this means this was the last member with MEMBER_INDEX_STATUS_NOT_RECEIVED
                                statusses.remove(Message.MEMBER_INDEX_STATUS_NOT_RECEIVED)

        self.member_status_index = statusses

class FormMessage(Message):
    TYPE = Message.TYPE_FORM_MESSAGE
    form = FormProperty()

class LastUnreadMessageMailingJob(db.Model):
    timestamp = db.IntegerProperty(default=0)

    @staticmethod
    def get():
        from rogerthat.dal import system_parent_key
        parent = system_parent_key()
        return LastUnreadMessageMailingJob.get_by_key_name("LastUnreadMessageMailingJob", parent) \
            or LastUnreadMessageMailingJob(parent=parent, key_name="LastUnreadMessageMailingJob", timestamp=0)

class SmartphoneChoice(db.Model):
    ANDROID = 1
    IPHONE = 2
    BLACKBERRY = 3
    WINDOWSPHONE = 4
    SYMBIAN = 5
    PALM = 6
    OTHER = 7

    choice = db.IntegerProperty(indexed=False)

class ServiceEmail(db.Model):
    TYPE_SERVICE_ENABLED = 1
    TYPE_SERVICE_DISABLED = 2

    timestamp = db.IntegerProperty()
    subject = db.StringProperty(indexed=False)
    messageText = db.TextProperty()
    messageHtml = db.TextProperty()

    @property
    def user(self):
        return users.User(self.parent_key().name())

class ServiceMenuDef(db.Model):
    TAG_MC_BROADCAST_SETTINGS = u"%s.broadcast_settings" % MC_RESERVED_TAG_PREFIX

    label = db.StringProperty(indexed=False)
    tag = db.TextProperty()
    timestamp = db.IntegerProperty(indexed=False)
    icon = db.BlobProperty()  # None if itemColor is None
    iconHash = db.StringProperty(indexed=False)  # None if itemColor is None
    iconName = db.StringProperty(indexed=False)
    iconColor = db.StringProperty(indexed=False)
    screenBranding = db.StringProperty(indexed=False)
    staticFlowKey = db.StringProperty(indexed=True)
    isBroadcastSettings = db.BooleanProperty(indexed=True)
    requiresWifi = db.BooleanProperty(indexed=False, default=False)
    runInBackground = db.BooleanProperty(indexed=False, default=True)
    roles = db.ListProperty(int, indexed=True)

    @staticmethod
    def createKey(coords, service_user):
        from rogerthat.dal import parent_key
        return db.Key.from_path(ServiceMenuDef.kind(), "x".join((str(x) for x in coords)), parent=parent_key(service_user))

    @property
    def service(self):
        return users.User(self.parent_key().name())

    @property
    def coords(self):
        return [int(c) for c in self.key().name().split('x')]

    @property
    def hashed_tag(self):
        return ServiceMenuDef.hash_tag(self.tag)

    @staticmethod
    def hash_tag(tag):
        return None if tag is None else unicode(hashlib.sha256(tag.encode('utf-8')).hexdigest())

class ServiceInteractionDef(db.Model):
    TAG_INVITE = "__invite__"

    description = db.TextProperty()
    tag = db.TextProperty()
    timestamp = db.IntegerProperty()
    qrTemplate = db.ReferenceProperty(QRTemplate, indexed=False)
    shortUrl = db.ReferenceProperty(ShortURL, indexed=False)
    deleted = db.BooleanProperty(default=False)
    totalScanCount = db.IntegerProperty(indexed=False, default=0)
    scannedFromRogerthatCount = db.IntegerProperty(indexed=False, default=0)
    scannedFromOutsideRogerthatOnSupportedPlatformCount = db.IntegerProperty(indexed=False, default=0)
    scannedFromOutsideRogerthatOnUnsupportedPlatformCount = db.IntegerProperty(indexed=False, default=0)
    service_identity = db.StringProperty()  # Needed to find all QR codes for a service identity
    multilanguage = db.BooleanProperty(default=False)
    staticFlowKey = db.StringProperty(indexed=True)
    branding = db.StringProperty(indexed=False)

    @property
    def user(self):
        return users.User(self.parent_key().name())

    @property
    def service_identity_user(self):
        from rogerthat.utils.service import create_service_identity_user
        return create_service_identity_user(self.user, self.service_identity or ServiceIdentity.DEFAULT)

    @property
    def SIDKey(self):
        return str(self.key())

class PokeTagMap(db.Model):
    tag = db.TextProperty()

    @property
    def service(self):
        return users.User(self.parent_key().name())

    @property
    def hash(self):
        return self.key().name()

class ServiceMenuDefTagMap(PokeTagMap):
    timestamp = db.IntegerProperty()


class UserInteraction(db.Model):
    INTERACTION_WELCOME = 1
    INTERACTION_DEMO = 2  # deprecated
    INTERACTION_YOUR_SERVICE_HERE = 4  # deprecated
    INTERACTIONS = (INTERACTION_WELCOME, INTERACTION_DEMO, INTERACTION_YOUR_SERVICE_HERE)

    interactions = db.IntegerProperty(indexed=False, default=0)
    services = db.StringListProperty(indexed=False, default=[])

    @property
    def user(self):
        return users.User(self.key().name())

class CustomMessageFlowDesign(object):
    # Used to start a message flow by XML
    xml = None

class MessageFlowDesign(db.Model):
    STATUS_VALID = 0
    STATUS_BROKEN = 1
    STATUS_SUBFLOW_BROKEN = 2
    STATUSSES = (STATUS_VALID, STATUS_BROKEN, STATUS_SUBFLOW_BROKEN)

    name = db.StringProperty()
    language = db.StringProperty(indexed=False)  # DO NOT USE!!! This is a property of the MFD javascript toolkit
    definition = db.TextProperty()
    status = db.IntegerProperty(default=STATUS_VALID)
    validation_error = db.TextProperty()
    design_timestamp = db.IntegerProperty(indexed=False)
    deleted = db.BooleanProperty(indexed=True)
    sub_flows = db.ListProperty(db.Key)
    broken_sub_flows = db.ListProperty(db.Key)
    xml = db.TextProperty()
    model_version = db.IntegerProperty(indexed=False)
    # version 2: added "results flush" action
    multilanguage = db.BooleanProperty(indexed=True, default=False)
    i18n_warning = db.TextProperty()
    js_flow_definitions = JsFlowDefinitionsProperty()

    @property
    def user(self):
        return users.User(self.parent_key().name())

class MessageFlowDesignBackup(db.Model):
    definition = db.TextProperty()
    design_timestamp = db.IntegerProperty(indexed=False)

class MessageFlowRunRecord(db.Model):
    _POST_RESULT_CALLBACK = 1

    flags = db.IntegerProperty(indexed=False, default=0)
    tag = db.TextProperty()
    service_identity = db.StringProperty()  # e.g. info@example.com/+default+ or info@example.com/otheridentity
    creationtime = db.IntegerProperty()

    @property
    def messageFlowRunId(self):
        return self.key().name().split('/')[-1]

    @staticmethod
    def createKeyName(service_user, guid):
        return "%s/%s" % (service_user.email(), guid)

    def _set_post_result_callback(self, value):
        if value:
            self.flags |= MessageFlowRunRecord._POST_RESULT_CALLBACK
        else:
            self.flags &= ~MessageFlowRunRecord._POST_RESULT_CALLBACK

    post_result_callback = property(fget=lambda self: self.flags & MessageFlowRunRecord._POST_RESULT_CALLBACK == MessageFlowRunRecord._POST_RESULT_CALLBACK, \
                                    fset=_set_post_result_callback)

class UserInvitationSecret(db.Model):
    STATUS_CREATED = 1
    STATUS_SENT = 2
    STATUS_REDIRECTED = 3
    STATUS_USED = 4
    STATUSSES = (STATUS_CREATED, STATUS_SENT, STATUS_REDIRECTED, STATUS_USED)

    status = db.IntegerProperty(indexed=False)
    creation_timestamp = db.IntegerProperty(indexed=False)
    sent_timestamp = db.IntegerProperty(indexed=False, default=0)
    redirected_timestamp = db.IntegerProperty(indexed=False, default=0)
    phone_number = db.StringProperty(indexed=False)
    email = db.UserProperty(indexed=False)
    used_timestamp = db.IntegerProperty(indexed=False, default=0)
    used_for_user = db.UserProperty(indexed=False)
    service_tag = db.TextProperty()
    origin = db.StringProperty(indexed=False)

    @property
    def secret(self):
        return unicode(base65.encode_int(self.key().id()))

    @property
    def user(self):
        return users.User(self.parent_key().name())

class LocationRequest(db.Model):
    timestamp = db.IntegerProperty(indexed=False)

    @property
    def friend(self):
        return users.User(self.parent_key().name())

    @property
    def user(self):
        return users.User(self.key().name())


class StartDebuggingRequest(db.Model):
    timestamp = db.IntegerProperty(indexed=False)

    @property
    def user(self):
        return users.User(self.parent_key().name())

    @property
    def target_id(self):
        return self.key().name()

    @staticmethod
    def create_key(app_user, target_id):  # target_id = mobile_id (branding debug) or xmpp_target_jid (admin debug)
        from rogerthat.dal import parent_key
        return db.Key.from_path(StartDebuggingRequest.kind(), target_id, parent=parent_key(app_user))


class Installation(db.Model):
    version = db.StringProperty(indexed=False)
    platform = db.IntegerProperty()
    timestamp = db.IntegerProperty()
    app_id = db.StringProperty()
    _logs = None

    service_identity_user = db.UserProperty(indexed=False)
    service_callback_result = db.StringProperty(indexed=False)
    qr_url = db.StringProperty(indexed=False)

    @property
    def install_id(self):
        return self.key().name()

    @property
    def logs(self):
        if self._logs is None:
            from rogerthat.dal.registration import get_installation_logs_by_installation
            self._logs = get_installation_logs_by_installation(self)
        return self._logs

    @property
    def platform_string(self):
        return Mobile.typeAsString(self.platform)

    @property
    def logged_registration_successful(self):
        if self.logs:
            t = 0
            for log in reversed(self.logs):
                if t != 0 and log.timestamp < t:
                    break
                t = log.timestamp
                if log.description.capitalize().startswith('Registration successful'):
                    return True

        return False


class Registration(db.Model):
    version = db.IntegerProperty(indexed=False)
    timestamp = db.IntegerProperty()
    device_id = db.StringProperty(indexed=False)
    pin = db.IntegerProperty(indexed=False)
    mobile = db.ReferenceProperty(Mobile)
    timesleft = db.IntegerProperty(indexed=False)
    installation = db.ReferenceProperty(Installation)
    request_id = db.StringProperty(indexed=False)
    language = db.StringProperty(indexed=False)

    @property
    def identifier(self):
        return self.key().name()

    @property
    def user(self):
        return users.User(self.parent_key().name())

class InstallationLog(db.Model):
    timestamp = db.IntegerProperty()
    description = db.StringProperty(indexed=False, multiline=True)
    pin = db.IntegerProperty()
    registration = db.ReferenceProperty(Registration)
    mobile = db.ReferenceProperty(Mobile)
    profile = db.ReferenceProperty(UserProfile)
    description_url = db.StringProperty(indexed=False, default=None)

    @property
    def time(self):
        return time.strftime("%a %d %b %Y\n%H:%M:%S GMT", time.localtime(self.timestamp))

    @property
    def safe_profile(self):
        try:
            return self.profile
        except ReferencePropertyResolveError:
            return None

    @property
    def gender(self):
        return self.profile.gender

class ActivationLog(db.Model):
    timestamp = db.IntegerProperty()
    email = db.StringProperty(indexed=True)
    mobile = db.ReferenceProperty(Mobile)
    description = db.TextProperty()

    @property
    def time(self):
        return time.strftime("%a %d %b %Y\n%H:%M:%S GMT", time.localtime(self.timestamp))

    @property
    def platform_string(self):
        try:
            return Mobile.typeAsString(self.mobile.type) if self.mobile else ""
        except ValueError:
            return "ValueError %s" % self.mobile.type

    @property
    def version_string(self):
        return self.mobile.osVersion if self.mobile else ""

    @property
    def mobile_string(self):
        return "%s - %s" % (self.platform_string, self.version_string)

class LogAnalysis(db.Model):
    analyzed_until = db.IntegerProperty(indexed=False)

class TransferResult(db.Model):
    STATUS_PENDING = 1
    STATUS_VERIFIED = 2
    STATUS_FAILED = 3
    service_identity_user = db.UserProperty()
    total_chunks = db.IntegerProperty(indexed=False)
    photo_hash = db.StringProperty(indexed=False)
    content_type = db.StringProperty()

    status = db.IntegerProperty(indexed=False)
    timestamp = db.IntegerProperty()

    @staticmethod
    def create_key(parent_message_key, message_key):
        azzert(message_key)
        key = urllib.urlencode((('pmk', parent_message_key), ('mk', message_key)) if parent_message_key else (('mk', message_key),))
        return db.Key.from_path(TransferResult.kind(), key)

    def _get_value_from_key(self, value):
        key = urlparse.parse_qs(self.key().name())
        val = key.get(value)
        if val:
            return val[0]
        return None

    @staticmethod
    def get_message_key_from_key(transfer_result_key):
        key = urlparse.parse_qs(transfer_result_key.name())
        val = key.get('mk')
        return val[0] if val else None

    @staticmethod
    def get_parent_message_key_from_key(transfer_result_key):
        key = urlparse.parse_qs(transfer_result_key.name())
        val = key.get('pmk')
        return val[0] if val else None

    @property
    def parent_message_key(self):
        return self._get_value_from_key('pmk')

    @property
    def message_key(self):
        return self._get_value_from_key('mk')


class TransferChunk(db.Model):
    content = db.BlobProperty(indexed=False)
    number = db.IntegerProperty(indexed=True)
    timestamp = db.IntegerProperty(indexed=False)

    @property
    def transfer_result_key(self):
        return self.parent_key()

class DSPickle(db.Model):
    version = db.IntegerProperty()

class DSPicklePart(db.Model):
    data = db.BlobProperty(indexed=False)
    version = db.IntegerProperty(indexed=True)
    number = db.IntegerProperty(indexed=True)
    timestamp = db.IntegerProperty(indexed=True)

class FlowResultMailFollowUp(db.Model):
    member = db.UserProperty(indexed=False)
    parent_message_key = db.StringProperty(indexed=False)
    service_user = db.UserProperty(indexed=False)
    service_identity = db.StringProperty(indexed=False)
    subject = db.StringProperty(indexed=False)
    addresses = db.StringListProperty(indexed=False)

class CurrentlyForwardingLogs(db.Model):
    TYPE_XMPP = 1
    TYPE_GAE_CHANNEL_API = 2

    xmpp_target = db.StringProperty(indexed=True)
    xmpp_target_password = db.StringProperty(indexed=True)
    type = db.IntegerProperty(indexed=False, default=TYPE_XMPP)

    @classmethod
    def create_parent_key(cls):
        return db.Key.from_path(cls.kind(), 'ancestor')

    @classmethod
    def create_key(cls, app_user):
        return db.Key.from_path(cls.kind(), app_user.email(), parent=cls.create_parent_key())

    @property
    def email(self):
        return self.key().name()

    @property
    def app_user(self):
        return users.User(self.email)

    @property
    def human_user(self):
        from rogerthat.utils.app import get_app_user_tuple_by_email
        return get_app_user_tuple_by_email(self.email)[0]

    @property
    def app_id(self):
        from rogerthat.utils.app import get_app_user_tuple_by_email
        return get_app_user_tuple_by_email(self.email)[1]

    @property
    def app_name(self):
        from rogerthat.dal.app import get_app_name_by_id
        return get_app_name_by_id(self.app_id)


class ServiceIdentityStatistic(db.Expando):
    number_of_users = db.IntegerProperty()
    gained_last_week = db.IntegerProperty(default=0)
    lost_last_week = db.IntegerProperty(default=0)
    users_gained = db.ListProperty(int, indexed=False)
    users_lost = db.ListProperty(int, indexed=False)
    last_entry_day = db.IntegerProperty(default=0)  # 20140128
    last_ten_users_gained = db.StringListProperty(indexed=False)
    last_ten_users_lost = db.StringListProperty(indexed=False)
    recommends_via_rogerthat = db.ListProperty(int, indexed=False)
    recommends_via_email = db.ListProperty(int, indexed=False)
    mip_labels = db.StringListProperty(indexed=False)

    @staticmethod
    def create_key(service_identity_user):
        from rogerthat.dal import parent_key
        from rogerthat.utils.service import add_slash_default
        from rogerthat.utils.service import get_service_user_from_service_identity_user
        service_identity_user = add_slash_default(service_identity_user)
        service_user = get_service_user_from_service_identity_user(service_identity_user)
        return db.Key.from_path(ServiceIdentityStatistic.kind(), service_identity_user.email(), parent=parent_key(service_user))

    @property
    def service_identity_user(self):
        return users.User(self.key().name())

    @property
    def service_user(self):
        return users.User(self.parent_key().name())


class FlowStatistics(db.Expando):
    '''
    Has dynamic properties in the following format:
    step(_<step_id>_<status sent/received/read/acked>_<btn_id if status==acked>)+
    - The value of these properties is a list with a counter per day.
    -- The first item of this list is the oldest counter.
    -- The last item of this list is the counter for <last_entry_day>.
    -- The counters list contains maximum 1000 entries.

    Example 1: self.labels = ['msgA']; self.step_0_read = [5, 0, 0, 10]
    - msgA is the start message of the flow
    - msgA is read 10 times at <last_entry_day> and 5 times 3 days before <last_entry_day>

    Example 2: self.labels = ['msgA', 'btn1', 'msgB']; self.step_0_1_2_sent = [0, 0, 0, 1]
    - msgB is reached 1 time via btn1 of msgA at <last_entry_day>
    '''
    labels = db.StringListProperty()  # list with step IDs and button IDs
    last_entry_day = db.IntegerProperty(default=0)  # 20140128

    STATUS_SENT = 'sent'
    STATUS_RECEIVED = 'received'
    STATUS_READ = 'read'
    STATUS_ACKED = 'acked'
    STATUSES = (STATUS_SENT, STATUS_RECEIVED, STATUS_READ, STATUS_ACKED)

    StepMetadata = namedtuple('Step', 'breadcrumbs step_id status btn_id')

    def _get_label_index_str(self, label):
        if not label:
            return ''
        try:
            return str(self.labels.index(label))
        except ValueError:
            self.labels.append(label)
            return str(len(self.labels) - 1)

    def _get_status_list_name(self, breadcrumbs, step_id, status, btn_id=None):
        def parts():
            yield 'step'
            for breadcrumb in breadcrumbs:
                yield self._get_label_index_str(breadcrumb)
            yield self._get_label_index_str(step_id)
            yield status
            if status == self.STATUS_ACKED:
                yield self._get_label_index_str(btn_id)

        return '_'.join(parts())

    def get_status_list_tuple(self, breadcrumbs, step_id, status, btn_id=None):
        prop_name = self._get_status_list_name(breadcrumbs, step_id, status, btn_id)
        status_list = getattr(self, prop_name, None)
        if status_list is None:
            status_list = [0]
            setattr(self, prop_name, status_list)
        return status_list, prop_name

    def get_status_list(self, breadcrumbs, step_id, status, btn_id=None):
        return self.get_status_list_tuple(breadcrumbs, step_id, status, btn_id)[0]

    def add(self, breadcrumbs, step_id, status, btn_id=None):
        status_list, status_list_name = self.get_status_list_tuple(breadcrumbs, step_id, status, btn_id)
        status_list[-1] += 1
        return status_list, status_list_name

    def _get_label(self, label_index_str):
        if label_index_str:
            return self.labels[int(label_index_str)]
        return None

    def parse_step_property(self, prop_name):
        splitted = prop_name.split('_')
        azzert(splitted.pop(0) == 'step')
        if splitted[-2] == self.STATUS_ACKED:
            btn_idx = splitted.pop(-1)
        else:
            btn_idx = None

        status = splitted.pop(-1)
        step_idx = splitted.pop(-1)

        return self.StepMetadata(breadcrumbs=map(self._get_label, splitted),
                                 step_id=self._get_label(step_idx),
                                 status=status,
                                 btn_id=self._get_label(btn_idx))

    def get_step_properties(self):
        return [p for p in self.dynamic_properties() if p.startswith('step_')]

    def _get_labels(self, matcher_func, days=1):
        lbls = dict()
        for prop_name in self.dynamic_properties():
            if matcher_func(prop_name):
                status_list = getattr(self, prop_name)
                for days_ago in xrange(days):
                    if status_list[days_ago] > 0:
                        splitted = prop_name.split('_')
                        idx_str = splitted[-2]
                        if idx_str == self.STATUS_ACKED:
                            idx_str = splitted[-1]
                        lbl = self.labels[int(idx_str)] if idx_str else None
                        lbls[lbl] = days_ago
                        break
        return sorted(lbls, key=lbls.get)  # sorted, most recent occurrence first

    def get_button_ids(self, breadcrumbs, step_id, days=1):
        prefix = self._get_status_list_name(breadcrumbs, step_id, self.STATUS_ACKED, None)
        def has_prefix(prop_name):
            return prop_name.startswith(prefix)
        return self._get_labels(has_prefix, days)

    def get_next_step_ids(self, breadcrumbs, days=1):
        prefix = 'step_%s' % '_'.join(map(self._get_label_index_str, breadcrumbs))
        def is_next_step(prop_name):
            return prop_name.endswith('_sent') \
                    and prop_name.startswith(prefix) \
                    and prop_name.count('_') == len(breadcrumbs) + 2
        return self._get_labels(is_next_step, days)

    def set_today(self, today=None):
        if today is None:
            today = datetime.datetime.utcnow().date()
        if self.last_entry_day == 0:  # new model
            delta = 0
        else:
            delta = (today - self.last_entry_datetime_date).days

        if delta > 0:
            for prop_name in self.get_step_properties():
                status_list = getattr(self, prop_name)
                for _ in xrange(delta):
                    status_list.append(0)
                    if len(status_list) > 1000:
                        status_list.pop(0)

        self.last_entry_day = int("%d%02d%02d" % (today.year, today.month, today.day))

    @property
    def last_entry_datetime_date(self):
        s = str(self.last_entry_day)
        return datetime.date(int(s[0:4]), int(s[4:6]), int(s[6:8]))

    @property
    def tag(self):
        return self.key().name()

    @property
    def service_identity(self):
        return self.parent_key().name()

    @property
    def service_user(self):
        return users.User(self.parent_key().parent().name())

    @property
    def service_identity_user(self):
        from rogerthat.utils.service import create_service_identity_user
        return create_service_identity_user(self.service_user, self.service_identity)

    @classmethod
    def create_parent_key(cls, service_identity_user):
        from rogerthat.dal import parent_key
        from rogerthat.utils.service import get_service_identity_tuple
        service_user, service_identity = get_service_identity_tuple(service_identity_user)
        service_parent_key = parent_key(service_user)
        return db.Key.from_path(service_parent_key.kind(), service_identity, parent=service_parent_key)

    @classmethod
    def create_key(cls, tag, service_identity_user):
        return db.Key.from_path(cls.kind(), tag, parent=cls.create_parent_key(service_identity_user))

    @classmethod
    def list_by_service_identity_user(cls, service_identity_user):
        return cls.all().ancestor(cls.create_parent_key(service_identity_user))

    @classmethod
    def list_by_service_user(cls, service_user):
        from rogerthat.dal import parent_key
        return cls.all().ancestor(parent_key(service_user))


class BroadcastStatistic(db.Model):
    timestamp = db.IntegerProperty()
    message = db.StringProperty(indexed=False, multiline=True)
    sent = db.IntegerProperty(indexed=False, default=0)
    received = db.IntegerProperty(indexed=False, default=0)
    read = db.IntegerProperty(indexed=False, default=0)
    acknowledged = db.IntegerProperty(indexed=False, default=0)  # TODO: Add logs

    @property
    def broadcast_guid(self):
        return self.key().name()

    @property
    def service_identity(self):
        return self.parent_key().name()

    @property
    def service_user(self):
        return users.User(self.parent_key().parent().name())

    @property
    def service_identity_user(self):
        from rogerthat.utils.service import create_service_identity_user
        return create_service_identity_user(self.service_user, self.service_identity)

    @staticmethod
    def create_key(broadcast_guid, service_identity_user):
        from rogerthat.utils.service import get_service_identity_tuple
        from rogerthat.dal import parent_key
        service_user, service_identity = get_service_identity_tuple(service_identity_user)
        service_parent_key = parent_key(service_user)
        return db.Key.from_path(BroadcastStatistic.kind(), broadcast_guid,
                                parent=db.Key.from_path(service_parent_key.kind(), service_identity,
                                                        parent=service_parent_key))

    @classmethod
    def get_all_by_service_identity_user(cls, service_identity_user):
        from rogerthat.utils.service import get_service_identity_tuple
        from rogerthat.dal import parent_key
        service_user, service_identity = get_service_identity_tuple(service_identity_user)
        service_parent_key = parent_key(service_user)
        ancestor = db.Key.from_path(service_parent_key.kind(), service_identity, parent=service_parent_key)
        return cls.all().ancestor(ancestor)


class Beacon(db.Model):
    uuid = db.StringProperty(indexed=True)
    name = db.StringProperty(indexed=True)
    tag = db.StringProperty(indexed=False, default=u"")
    service_identity = db.StringProperty(indexed=True)  # Needed to find all beacons for a service identity
    creation_time = db.IntegerProperty(indexed=False)

    @property
    def service_user(self):
        return users.User(self.parent_key().name())

    @property
    def service_identity_user(self):
        from rogerthat.utils.service import create_service_identity_user
        return create_service_identity_user(self.service_user, self.service_identity)

    @staticmethod
    def create_key(service_identity_user, beacon_name):
        from rogerthat.utils.service import get_service_user_from_service_identity_user
        from rogerthat.dal import parent_key

        service_user = get_service_user_from_service_identity_user(service_identity_user)
        return db.Key.from_path(Beacon.kind(), beacon_name, parent=parent_key(service_user))

class BeaconDiscovery(db.Model):
    creation_time = db.IntegerProperty(indexed=False)

    @property
    def service_user(self):
        from rogerthat.utils.service import get_service_user_from_service_identity_user
        return get_service_user_from_service_identity_user(users.User(self.key().name()))

    @property
    def service_identity(self):
        from rogerthat.utils.service import get_identity_from_service_identity_user
        return get_identity_from_service_identity_user(users.User(self.key().name()))

    @staticmethod
    def create_key(app_user, service_identity_user):
        from rogerthat.dal import parent_key
        azzert('/' in service_identity_user.email(), 'no slash in %s' % service_identity_user.email())
        return db.Key.from_path(BeaconDiscovery.kind(), service_identity_user.email(), parent=parent_key(app_user))


class BeaconMajor(db.Model):
    last_number = db.IntegerProperty(default=0)

    @classmethod
    def next(cls):
        azzert(db.is_in_transaction())
        beacon_major = cls.get_by_key_name('beacon_major')
        beacon_major.last_number += 1
        beacon_major.put()
        return beacon_major.last_number


class JSEmbedding(db.Model):
    creation_time = db.IntegerProperty(indexed=False)
    content = db.BlobProperty(indexed=False)
    hash = db.StringProperty(indexed=False)  # Zip Hash
    hash_files = db.StringProperty(indexed=False)

    @property
    def name(self):
        return self.key().name()

class Group(db.Model, ArchivedModel):
    name = db.StringProperty(indexed=False)
    avatar = db.BlobProperty(indexed=False)
    avatar_hash = db.StringProperty(indexed=True)
    members = db.ListProperty(unicode, indexed=True)

    @property
    def guid(self):
        return self.key().name()

    @property
    def user(self):
        return users.User(self.parent_key().name())

    @staticmethod
    def create_key(app_user, guid):
        from rogerthat.dal import parent_key
        return db.Key.from_path(Group.kind(), guid, parent=parent_key(app_user))


class BeaconRegion(db.Model):
    uuid = db.StringProperty(indexed=True)
    major = db.IntegerProperty(indexed=True)
    minor = db.IntegerProperty(indexed=True)
    creation_time = db.IntegerProperty(indexed=False)

    @property
    def app_id(self):
        return self.parent_key().name()

    @staticmethod
    def create_key(app_key, uuid, major, minor):
        return db.Key.from_path(BeaconRegion.kind(), "%s|%s|%s" % (uuid, major, minor), parent=app_key)

class ServiceLocationTracker(db.Model):
    creation_time = db.IntegerProperty(indexed=True)
    until = db.IntegerProperty(indexed=True)
    enabled = db.BooleanProperty(indexed=True)
    service_identity_user = db.UserProperty(indexed=True)
    notified = db.BooleanProperty(indexed=False, default=False)

    @property
    def user(self):
        return users.User(self.parent_key().name())

    @classmethod
    def create_key(cls, app_user, key):
        from rogerthat.dal import parent_key
        return db.Key.from_path(cls.kind(), key, parent=parent_key(app_user))

    def encrypted_key(self):
        from rogerthat.utils.service import get_service_user_from_service_identity_user
        service_user = get_service_user_from_service_identity_user(self.service_identity_user)
        return encrypt(service_user, str(self.key()))
