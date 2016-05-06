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

import datetime
import hashlib
import json
import logging
import os
import types
import urllib
from httplib import HTTPException
from types import NoneType

from google.appengine.api import images, urlfetch, search
from google.appengine.api.images import composite, TOP_LEFT, BOTTOM_LEFT
from google.appengine.api.urlfetch_errors import DeadlineExceededError
from google.appengine.ext import db, deferred

import facebook
from mcfw.cache import invalidate_cache
from mcfw.rpc import returns, arguments
from mcfw.utils import chunks
from rogerthat.bizz.friends import INVITE_ID, INVITE_FACEBOOK_FRIEND, invite, breakFriendShip, makeFriends, userCode
from rogerthat.bizz.job import run_job
from rogerthat.bizz.messaging import sendMessage
from rogerthat.bizz.session import drop_sessions_of_user
from rogerthat.bizz.system import get_identity, identity_update_response_handler
from rogerthat.bizz.user import reactivate_user_profile
from rogerthat.capi.system import identityUpdate
from rogerthat.consts import MC_DASHBOARD
from rogerthat.dal import parent_key, put_and_invalidate_cache
from rogerthat.dal.app import get_app_name_by_id, get_app_by_user, get_default_app
from rogerthat.dal.broadcast import get_broadcast_settings_flow_cache_keys_of_user
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.profile import get_avatar_by_id, get_existing_profiles_via_facebook_ids, \
    get_existing_user_profiles, get_user_profile, get_profile_infos, get_profile_info, get_service_profile, is_trial_service, \
    get_user_profiles, get_service_or_user_profile, get_deactivated_user_profile
from rogerthat.dal.service import get_default_service_identity_not_cached, get_all_service_friend_keys_query, \
    get_service_identities_query, get_all_archived_service_friend_keys_query, get_friend_serviceidentity_connection
from rogerthat.models import FacebookUserProfile, Avatar, ProfilePointer, ShortURL, ProfileDiscoveryResult, \
    FacebookProfilePointer, FacebookDiscoveryInvite, Message, ServiceProfile, UserProfile, ServiceIdentity, ProfileInfo, App, \
    Profile, SearchConfig, FriendServiceIdentityConnectionArchive, \
    UserData, UserDataArchive, ActivationLog, ProfileHashIndex
from rogerthat.rpc import users
from rogerthat.rpc.models import TempBlob, Mobile
from rogerthat.rpc.rpc import logError, SKIP_ACCOUNTS
from rogerthat.rpc.service import BusinessException
from rogerthat.to.friends import FacebookRogerthatProfileMatchTO
from rogerthat.to.messaging import ButtonTO, UserMemberTO
from rogerthat.to.service import UserDetailsTO
from rogerthat.to.system import IdentityUpdateRequestTO
from rogerthat.translations import localize, DEFAULT_LANGUAGE
from rogerthat.utils import now, azzert, urlencode, is_clean_app_user_email, get_epoch_from_datetime
from rogerthat.utils.app import get_app_id_from_app_user, create_app_user, get_human_user_from_app_user, \
    get_app_user_tuple
from rogerthat.utils.channel import send_message
from rogerthat.utils.oauth import LinkedInClient
from rogerthat.utils.service import create_service_identity_user, remove_slash_default
from rogerthat.utils.transactions import on_trans_committed, run_in_transaction

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

CURRENT_DIR = os.path.dirname(__file__)

UNKNOWN_AVATAR_PATH = os.path.join(CURRENT_DIR, 'unknown_avatar.png')
NUNTIUZ_AVATAR_PATH = os.path.join(CURRENT_DIR, 'nuntiuz.png')

USER_INDEX = "USER_INDEX"

class FailedToBuildFacebookProfileException(BusinessException):
    pass

def get_unknown_avatar():
    f = open(UNKNOWN_AVATAR_PATH, "rb")
    try:
        return f.read()
    finally:
        f.close()

def get_nuntiuz_avatar():
    f = open(NUNTIUZ_AVATAR_PATH, "rb")
    try:
        return f.read()
    finally:
        f.close()

UNKNOWN_AVATAR = get_unknown_avatar()
NUNTIUZ_AVATAR = get_nuntiuz_avatar()

@returns(NoneType)
@arguments(app_user=users.User)
def schedule_re_index(app_user):
    # Does NOT have to be transactional, running it over and over does not harm
    deferred.defer(_re_index, app_user)

def _re_index(app_user):
    def trans():
        user_profile = get_profile_info(app_user, False)
        fm = get_friends_map(app_user)
        return user_profile, fm
    user_profile, fm = db.run_in_transaction(trans)

    if not user_profile:
        logging.info("Tried to index a user who is deactivated")
        search.Index(name=USER_INDEX).delete(app_user.email())
        return

    if user_profile.isServiceIdentity:
        logging.error("Tried to index a service into the USER_INDEX")
        return

    connections = StringIO()
    for f in fm.friends:
        email = f.email().encode('utf8').replace('"', '')
        connections.write('@@%s@@' % email)
        if '/' in email:
            connections.write('@@%s@@' % email.split('/')[0])

    human_user, app_id = get_app_user_tuple(app_user)

    fields = [
        search.TextField(name='email', value=human_user.email()),
        search.TextField(name='name', value=user_profile.name),
        search.TextField(name='language', value=user_profile.language),
        search.TextField(name='connections', value=connections.getvalue()),
        search.TextField(name='app_id', value=app_id)
    ]

    if user_profile.profileData:
        data = json.loads(user_profile.profileData)
        for key, value in data.iteritems():
            fields.append(search.TextField(name='pd_%s' % key.replace(' ', '_'), value=value))

    doc = search.Document(doc_id=app_user.email(), fields=fields)
    search.Index(name=USER_INDEX).put(doc)

@returns([UserDetailsTO])
@arguments(name_or_email_term=unicode, app_id=unicode)
def search_users_via_name_or_email(name_or_email_term, app_id=None):
    logging.info("Looking for users with term '%s'." % name_or_email_term)
    if len(name_or_email_term) < 3:
        logging.info("Search term is to short. Bye bye.")
        return []
    name_or_email_term = name_or_email_term.replace('"', '')
    if app_id:
        query = search.Query(query_string='email:"%s" OR name:"%s" app_id:%s' % (name_or_email_term, name_or_email_term, app_id),
                             options=search.QueryOptions(returned_fields=['email', 'name', 'language', 'app_id'], limit=10))
    else:
        query = search.Query(query_string='email:"%s" OR name:"%s"' % (name_or_email_term, name_or_email_term),
                             options=search.QueryOptions(returned_fields=['email', 'name', 'language', 'app_id'], limit=10))
    search_result = search.Index(name=USER_INDEX).search(query)
    def create_user_detail(doc):
        ud = UserDetailsTO()
        ud.email = doc.fields[0].value
        ud.name = doc.fields[1].value
        ud.language = doc.fields[2].value
        ud.app_id = doc.fields[3].value
        ud.avatar_url = None
        return ud
    return [create_user_detail(d) for d in search_result.results]

@returns([UserDetailsTO])
@arguments(connection=unicode, name_or_email_term=unicode, app_id=unicode, include_avatar=bool)
def search_users_via_friend_connection_and_name_or_email(connection, name_or_email_term, app_id=None, include_avatar=False):
    """Search for users in the USER_INDEX.
    connection: The account of the connection (human or service).
        In case of a service searching across identities is possible via ommiting the slash and everything after it.
    name_or_email_term: A fragment of the name or email of the user you are looking for."""
    if len(name_or_email_term) < 3:
        return []
    connection = connection.encode('utf8').replace('"', '')
    name_or_email_term = name_or_email_term.replace('"', '')
    if app_id:
        query = search.Query(query_string='connections:"@@%s@@" AND (email:"%s" OR name:"%s") app_id:%s' % (connection, name_or_email_term, name_or_email_term, app_id),
                             options=search.QueryOptions(returned_fields=['email', 'name', 'language', 'app_id'], limit=10))
    else:
        query = search.Query(query_string='connections:"@@%s@@" AND (email:"%s" OR name:"%s")' % (connection, name_or_email_term, name_or_email_term),
                             options=search.QueryOptions(returned_fields=['email', 'name', 'language', 'app_id'], limit=10))
    search_result = search.Index(name=USER_INDEX).search(query)

    userProfiles = {}
    if include_avatar:
        usrs = []
        for d in search_result.results:
            usrs.append(create_app_user(users.User(d.fields[0].value), d.fields[3].value))
        profiles = get_user_profiles(usrs)
        for p in profiles:
            userProfiles[p.user.email()] = p

    def create_user_detail(doc):
        ud = UserDetailsTO()
        app_user = create_app_user(users.User(d.fields[0].value), d.fields[3].value)

        ud.email = d.fields[0].value
        ud.name = doc.fields[1].value
        ud.language = doc.fields[2].value
        ud.app_id = doc.fields[3].value
        if include_avatar:
            up = userProfiles.get(app_user.email())
            if up:
                ud.avatar_url = up.avatarUrl
            else:
                ud.avatar_url = None
        else:
            ud.avatar_url = None
        return ud
    return [create_user_detail(d) for d in search_result.results]

@returns(UserProfile)
@arguments(email=unicode, language=unicode, name=unicode)
def get_profile_for_google_user(email, language, name):
    user = users.User(email)
    user_profile = get_user_profile(user)
    if not user_profile:
        user_profile = UserProfile(parent=parent_key(user), key_name=user.email())
        user_profile.name = name if name else user.email()
        user_profile.language = language
        user_profile.version = 1
        put_and_invalidate_cache(user_profile, ProfilePointer.create(user))
        update_friends(user_profile)
    return user_profile


@returns(Avatar)
@arguments(app_user=users.User, fb_id=unicode, profile_or_key=(Profile, db.Key), avatar_or_key=(Avatar, db.Key),
           retry_count=int)
def _get_facebook_avatar(app_user, fb_id, profile_or_key, avatar_or_key, retry_count=0):
    if retry_count == 5:
        logging.debug("Reached max retry count. Giving up trying to get the facebook avatar for %s.", app_user)
        return None

    avatar = db.get(avatar_or_key) if isinstance(avatar_or_key, db.Key) else avatar_or_key
    if avatar.picture:
        logging.debug("In the mean time, there already is an avatar set for %s. Stop retrying...", app_user)
        return avatar

    profile_or_key_is_key = isinstance(profile_or_key, db.Key)
    try:
        file_handle = urllib.urlopen("http://graph.facebook.com/%s/picture" % fb_id)
        try:
            image = file_handle.read()
        finally:
            file_handle.close()

        def update_avatar_and_profile(profile_or_key_is_key):
            avatar = db.get(avatar_or_key) if isinstance(avatar_or_key, db.Key) else avatar_or_key
            if avatar.picture:
                logging.debug("In the mean time, there already is an avatar set for %s. Stopping...", app_user)
                return None, None
            avatar.picture = image
            avatar.put()

            profile = db.get(profile_or_key) if profile_or_key_is_key else profile_or_key
            _calculateAndSetAvatarHash(profile, image)
            if profile_or_key_is_key:
                profile.put()
            return avatar

        if profile_or_key_is_key:
            xg_on = db.create_transaction_options(xg=True)
            avatar = db.run_in_transaction_options(xg_on, update_avatar_and_profile, profile_or_key_is_key)
        else:
            avatar = update_avatar_and_profile(profile_or_key_is_key)

    except Exception, e:
        avatar.put()  # put empty to get avatar id.

        if isinstance(e, DeadlineExceededError) or isinstance(e, HTTPException) and e.message and 'deadline' in e.message.lower():
            logging.debug("Timeout while retrieving facebook avatar for %s. Retrying...", app_user)
            profile_key = profile_or_key if profile_or_key_is_key else profile_or_key.key()
            deferred.defer(_get_facebook_avatar, app_user, fb_id, profile_key, avatar.key(), retry_count + 1,
                           _countdown=5)
        else:
            logging.exception("Failed to retrieve facebook avatar for %s.", app_user)

    return avatar


@returns(UserProfile)
@arguments(access_token=unicode, app_user=users.User, update=bool, language=unicode, app_id=unicode)
def get_profile_for_facebook_user(access_token, app_user, update=False, language=DEFAULT_LANGUAGE, app_id=App.APP_ID_ROGERTHAT):
    gapi = facebook.GraphAPI(access_token)
    fb_profile = gapi.get_object("me", fields=["id", "first_name", "last_name", "name", "verified", "locale", "gender", "email", "birthday", "link"])
    logging.debug("/me graph response: %s", fb_profile)

    if not app_user:
        if "email" in fb_profile:
            app_user = create_app_user(users.User(fb_profile["email"]), app_id)
        else:
            raise FailedToBuildFacebookProfileException(localize(language, 'There is no e-mail address configured in your facebook account. Please use the e-mail based login.'))

        # TODO we should validate app.user_regex
        # TODO we should check if email is not used for a service account

    couple_facebook_id_with_profile(app_user, access_token)
    profile = get_user_profile(app_user)
    if not profile or update:
        if not profile:
            profile = FacebookUserProfile(parent=parent_key(app_user), key_name=app_user.email())
            profile.app_id = app_id
            avatar = Avatar(user=app_user)
        else:
            avatar = get_avatar_by_id(profile.avatarId)
            if not avatar:
                avatar = Avatar(user=app_user)

        if fb_profile.get("name"):
            profile.name = fb_profile["name"]
        else:
            profile.name = get_human_user_from_app_user(app_user).email().replace("@", " at ")

        if profile.birthdate is None and fb_profile.get("birthday"):
            birthday = fb_profile["birthday"].split("/")
            profile.birthdate = get_epoch_from_datetime(datetime.date(int(birthday[2]), int(birthday[0]), int(birthday[1])))

        if profile.gender is None and fb_profile.get("gender"):
            gender = fb_profile["gender"]
            if gender == "male":
                profile.gender = UserProfile.GENDER_MALE
            elif gender == "female":
                profile.gender = UserProfile.GENDER_FEMALE
            else:
                profile.gender = UserProfile.GENDER_CUSTOM


        avatar = _get_facebook_avatar(app_user, fb_profile["id"], profile, avatar)

        profile.avatarId = avatar.key().id()
        profile.profile_url = fb_profile["link"]
        profile.access_token = access_token
        profile.version = 1
        put_and_invalidate_cache(profile, ProfilePointer.create(app_user))
        update_friends(profile)
        update_mobiles(app_user, profile)
    return profile

@returns(NoneType)
@arguments(app_user=users.User, access_token=unicode)
def couple_facebook_id_with_profile(app_user, access_token):
    deferred.defer(_couple_facebook_id_with_profile, app_user, access_token)

def _couple_facebook_id_with_profile(app_user, access_token):
    try:
        gapi = facebook.GraphAPI(access_token)
        fb_profile = gapi.get_object("me")
    except facebook.GraphAPIError, e:
        if e.type == "OAuthException":
            # throwing a BusinessException(PermanentTaskFailure) will make sure the task won't retry and keep failing
            raise BusinessException("Giving up because we caught an OAuthException: %s" % e)
        else:
            raise e
    FacebookProfilePointer(key_name=fb_profile["id"], user=app_user).put()
    _discover_registered_friends_via_facebook_profile(app_user, access_token)

def _discover_registered_friends_via_facebook_profile(app_user, access_token):
    facebook_friends = get_friend_list_from_facebook(access_token)
    friend_ids = list(set((f['id'] for f in facebook_friends)))
    matches = get_existing_profiles_via_facebook_ids(friend_ids, get_app_id_from_app_user(app_user))
    invites_sent = db.get([db.Key.from_path(FacebookDiscoveryInvite.kind(), rtId.email(), parent=parent_key(app_user)) for _, rtId in matches])
    i = 0
    for invite in invites_sent:
        if not invite:
            deferred.defer(_send_message_to_inform_user_about_a_new_join, app_user, matches[i][1], _countdown=30)
        i += 1

def _send_message_to_inform_user_about_a_new_join(new_user, fb_friend_user):
    def trans():
        key_name = fb_friend_user.email()
        parent = parent_key(new_user)
        invite = FacebookDiscoveryInvite.get_by_key_name(key_name, parent)
        if invite:
            return
        db.put_async(FacebookDiscoveryInvite(key_name=key_name, parent=parent))
        friend_map = get_friends_map(new_user)
        if fb_friend_user in friend_map.friends:
            return
        deferred.defer(_send_message_to_inform_user_about_a_new_join_step_2, fb_friend_user, new_user, _transactional=True)
    db.run_in_transaction(trans)

def _send_message_to_inform_user_about_a_new_join_step_2(fb_friend_user, new_user):
    new_user_profile, fb_friend_profile = get_profile_infos([new_user, fb_friend_user], expected_types=[UserProfile, UserProfile])
    azzert(new_user_profile.app_id == fb_friend_profile.app_id)
    app_name = get_app_name_by_id(new_user_profile.app_id)
    to_language = fb_friend_profile.language if fb_friend_profile else DEFAULT_LANGUAGE
    message_text = localize(to_language, "%(name)s just joined %(app_name)s, and we found you in his facebook friends list!", name=new_user_profile.name, app_name=app_name)
    button = ButtonTO()
    button.id = INVITE_ID
    button.caption = localize(to_language, "Invite %(name)s to connect on %(app_name)s", name=new_user_profile.name, app_name=app_name)
    button.action = None
    button.ui_flags = 0
    def trans():
        message = sendMessage(MC_DASHBOARD, [UserMemberTO(fb_friend_user)], Message.FLAG_ALLOW_DISMISS, 0, None,
                              message_text, [button], None, get_app_by_user(fb_friend_user).core_branding_hash,
                              INVITE_FACEBOOK_FRIEND, is_mfr=False)
        message.invitor = fb_friend_user
        message.invitee = new_user
        message.put()
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)

@returns(NoneType)
@arguments(message=Message)
def ack_facebook_invite(message):
    azzert(message.tag == INVITE_FACEBOOK_FRIEND)
    memberStatus = message.memberStatusses[message.members.index(message.invitor)]
    if not memberStatus.dismissed and message.buttons[memberStatus.button_index].id == INVITE_ID:
        profile = get_user_profile(message.invitee)
        invite(message.invitor, message.invitee.email(), profile.name, None, profile.language, None, None,
               get_app_id_from_app_user(message.invitor))

@returns(NoneType)
@arguments(linkedin_client=LinkedInClient, token=unicode, secret=unicode, user=users.User)
def get_profile_for_linkedin_user(linkedin_client, token, secret, user):
    profile_url = "http://api.linkedin.com/v1/people/~:(id,first-name,last-name,picture-url)"
    response = linkedin_client.make_request(profile_url, token=token, secret=secret, headers={"x-li-format":"json"})
    if response.status_code != 200:
        raise Exception("Could not get connections from linkedin")
    logging.info(response.content)
    profile = json.loads(response.content)
    url = profile.get('pictureUrl', None)
    name = "%s %s" % (profile['firstName'], profile['lastName'])
    if url:
        avatar = urlfetch.fetch(url, deadline=10)
        if avatar.status_code == 200:
            avatar = avatar.content
        else:
            avatar = None
    else:
        avatar = None
    pd = ProfileDiscoveryResult(parent=parent_key(user), type=ProfileDiscoveryResult.TYPE_LINKEDIN,
                                account=str(profile['id']), name=name, data=json.dumps(profile), avatar=avatar,
                                timestamp=now())
    pd.put()
    deferred.defer(update_profile_from_profile_discovery, user, pd, _transactional=db.is_in_transaction())

@returns(int)
@arguments(user_code=unicode)
def create_short_url(user_code):
    su = ShortURL()
    su.full = "/q/i" + user_code
    su.put()
    return su.key().id()


@returns([ShortURL])
@arguments(app_id=unicode, amount=(int, long))
def generate_unassigned_short_urls(app_id, amount):
    @db.non_transactional
    def allocate_ids():
        return db.allocate_ids(db.Key.from_path(ShortURL.kind(), 1), amount)  # (start, end)

    result = list()
    id_range = allocate_ids()
    for short_url_id in xrange(id_range[0], id_range[1] + 1):
        user_code = userCode(users.User("%s@%s" % (short_url_id, app_id)))
        result.append(ShortURL(key=db.Key.from_path(ShortURL.kind(), short_url_id), full="/q/i" + user_code))

    for c in chunks(result, 200):
        db.put(c)
    return result


def _validate_name(name):
    if name is None:
        raise ValueError("Name can not be NULL")
    if not name:
        raise ValueError("Name can not be empty")
    name = name.strip().replace('@', ' at ')
    if len(name) > 50:
        raise ValueError("Name can not be bigger than 50 characters. name: '%s' len: %s " % (name , len(name)))
    return name

def _create_new_avatar(user, add_trial_overlay):
    avatar = Avatar(user=user)
    image = UNKNOWN_AVATAR
    if add_trial_overlay:
        image = add_trial_service_overlay(image)
    avatar.picture = db.Blob(image)
    avatar.put()
    return avatar, image


@returns(UserProfile)
@arguments(app_user=users.User, name=unicode, language=unicode, ysaaa=bool)
def create_user_profile(app_user, name, language=None, ysaaa=False):
    name = _validate_name(name)

    def trans_create():
        azzert(not get_user_profile(app_user, cached=False))

        avatar, image = _create_new_avatar(app_user, add_trial_overlay=False)

        user_profile = UserProfile(parent=parent_key(app_user), key_name=app_user.email())
        user_profile.name = name
        user_profile.language = language
        user_profile.avatarId = avatar.key().id()
        user_profile.app_id = get_app_id_from_app_user(app_user)
        _calculateAndSetAvatarHash(user_profile, image)

        put_and_invalidate_cache(user_profile, ProfilePointer.create(app_user), ProfileHashIndex.create(app_user))

        return user_profile

    user_profile = run_in_transaction(trans_create, True)
    if not ysaaa:
        schedule_re_index(app_user)
    return user_profile

@returns()
@arguments(email=unicode, app_id=unicode, user_code=unicode, short_url_id=(int, long), language=unicode)
def put_loyalty_user_profile(email, app_id, user_code, short_url_id, language):
    app_user = create_app_user(users.User(email), app_id)
    name = _validate_name(email)

    def trans_create():
        rogerthat_profile = get_service_or_user_profile(users.User(email))
        if rogerthat_profile and isinstance(rogerthat_profile, ServiceProfile):
            from rogerthat.bizz.service import AppFailedToCreateUserProfileWithExistingServiceException
            raise AppFailedToCreateUserProfileWithExistingServiceException(email)

        user_profile = get_user_profile(app_user, cached=False)
        is_new_profile = False
        if not user_profile:
            deactivated_user_profile = get_deactivated_user_profile(app_user)
            if deactivated_user_profile:
                deferred.defer(reactivate_user_profile, deactivated_user_profile, app_user, _transactional=True)
                ActivationLog(timestamp=now(), email=app_user.email(), mobile=None, description="Reactivate user account by registering a paper loyalty card").put()
            else:
                is_new_profile = True
                avatar, image = _create_new_avatar(app_user, add_trial_overlay=False)

                user_profile = UserProfile(parent=parent_key(app_user), key_name=app_user.email())
                user_profile.name = name
                user_profile.language = language
                user_profile.avatarId = avatar.key().id()
                user_profile.app_id = app_id
                _calculateAndSetAvatarHash(user_profile, image)

        pp = ProfilePointer(key=db.Key.from_path(ProfilePointer.kind(), user_code))
        pp.user = app_user
        pp.short_url_id = short_url_id

        if is_new_profile:
            put_and_invalidate_cache(user_profile, pp, ProfilePointer.create(app_user))
        else:
            pp.put()

    run_in_transaction(trans_create, True)
    schedule_re_index(app_user)

@returns(tuple)
@arguments(service_user=users.User, name=unicode, is_trial=bool, update_func=types.FunctionType,
           supported_app_ids=[unicode])
def create_service_profile(service_user, name, is_trial=False, update_func=None, supported_app_ids=None):
    from rogerthat.bizz.service import create_default_qr_templates

    name = _validate_name(name)

    if supported_app_ids is None:
        default_app = get_default_app()
        default_app_id = default_app.app_id if default_app else App.APP_ID_ROGERTHAT
        supported_app_ids = [default_app_id]
    else:
        default_app_id = supported_app_ids[0]

    def trans_prepare_create():
        avatar, image = _create_new_avatar(service_user, is_trial)

        from rogerthat.bizz.service import _create_recommendation_qr_code
        share_sid_key = _create_recommendation_qr_code(service_user, ServiceIdentity.DEFAULT, default_app_id)

        return avatar, image, share_sid_key

    def trans_create(avatar, image, share_sid_key):
        azzert(not get_service_profile(service_user, cached=False))
        azzert(not get_default_service_identity_not_cached(service_user))

        profile = ServiceProfile(parent=parent_key(service_user), key_name=service_user.email())
        profile.avatarId = avatar.key().id()
        _calculateAndSetAvatarHash(profile, image)

        service_identity_user = create_service_identity_user(service_user, ServiceIdentity.DEFAULT)
        service_identity = ServiceIdentity(key=ServiceIdentity.keyFromUser(service_identity_user))
        service_identity.inheritanceFlags = 0
        service_identity.name = name
        service_identity.description = "%s (%s)" % (name, service_user.email())
        service_identity.shareSIDKey = share_sid_key
        service_identity.shareEnabled = False
        service_identity.creationTimestamp = now()
        service_identity.appIds = supported_app_ids

        update_result = update_func(profile, service_identity) if update_func else None

        put_and_invalidate_cache(profile, service_identity,
                                 ProfilePointer.create(service_user),
                                 ProfileHashIndex.create(service_user))

        deferred.defer(create_default_qr_templates, service_user, _transactional=True)

        return profile, service_identity, update_result

    avatar, image, share_sid_key = run_in_transaction(trans_prepare_create, True)
    try:
        profile, service_identity, update_result = run_in_transaction(trans_create, True, avatar, image, share_sid_key)
        return (profile, service_identity, update_result) if update_func else (profile, service_identity)
    except:
        db.delete([avatar, share_sid_key])
        raise


def update_password_hash(profile, passwordHash, lastUsedMgmtTimestamp):
    profile.passwordHash = passwordHash
    profile.lastUsedMgmtTimestamp = lastUsedMgmtTimestamp
    profile.termsAndConditionsVersion = 1
    profile.put()


def update_user_profile(app_user, name, tmp_avatar_key, x1, y1, x2, y2, language):
    def trans():
        user_profile = get_user_profile(app_user)
        if user_profile.language != language:
            user_profile.language = language
            db.delete_async(get_broadcast_settings_flow_cache_keys_of_user(app_user))
        user_profile.name = name
        if tmp_avatar_key:
            _update_avatar(user_profile, tmp_avatar_key, x1, y1, x2, y2, add_trial_overlay=False)
        user_profile.version += 1
        user_profile.put()

        update_mobiles(app_user, user_profile)  # update myIdentity
        update_friends(user_profile)  # notify my friends

        return user_profile

    user_profile = run_in_transaction(trans, xg=True)
    schedule_re_index(app_user)
    return user_profile


def update_service_profile(service_user, tmp_avatar_key, x1, y1, x2, y2, add_trial_overlay, organization_type=None):
    if not tmp_avatar_key and organization_type is None:
        logging.info("No tmp_avatar_key. Service user pressed save without changing his avatar.")
        return get_service_profile(service_user)

    def trans():
        service_profile = get_service_profile(service_user)
        if tmp_avatar_key:
            _update_avatar(service_profile, tmp_avatar_key, x1, y1, x2, y2, add_trial_overlay)
        if organization_type is not None:
            service_profile.organizationType = organization_type
        service_profile.version += 1
        service_profile.put()

        from rogerthat.bizz.job.update_friends import schedule_update_all_friends_of_service_user
        schedule_update_all_friends_of_service_user(service_profile)

        return service_profile

    return run_in_transaction(trans, True)

def _update_avatar(profile, tmp_avatar_key, x1, y1, x2, y2, add_trial_overlay):
    tb = TempBlob.get(tmp_avatar_key)

    img = images.Image(str(tb.blob))
    img.crop(x1, y1, x2, y2)
    img.resize(150, 150)

    avatar = get_avatar_by_id(profile.avatarId)
    if not avatar:
        avatar = Avatar(user=profile.user)
    image = img.execute_transforms(images.PNG, 100)
    if add_trial_overlay:
        image = add_trial_service_overlay(image)
    update_avatar_profile(profile, avatar, image)

@returns(NoneType)
@arguments(service_user=users.User, image=str)
def update_service_avatar(service_user, image):
    img = images.Image(image)
    img.im_feeling_lucky()
    img.execute_transforms()
    if img.height != img.width:
        devation = float(img.width) / float(img.height)
        if devation < 0.95 or devation > 1.05:
            from rogerthat.bizz.service import AvatarImageNotSquareException
            logging.debug("Avatar Size: %sx%s" % (img.width, img.height))
            raise AvatarImageNotSquareException()
    img = images.Image(image)
    img.resize(150, 150)
    image = img.execute_transforms(images.PNG, 100)
    if is_trial_service(service_user):
        image = add_trial_service_overlay(image)
    def trans():
        service_profile = get_service_profile(service_user)
        avatar = get_avatar_by_id(service_profile.avatarId)
        if not avatar:
            avatar = Avatar(user=service_profile.user)
        update_avatar_profile(service_profile, avatar, image)
        service_profile.version += 1
        service_profile.put()

        from rogerthat.bizz.job.update_friends import schedule_update_all_friends_of_service_user
        schedule_update_all_friends_of_service_user(service_profile)
    xg_on = db.create_transaction_options(xg=True)
    return db.run_in_transaction_options(xg_on, trans)

def update_avatar_profile(profile, avatar, image):
    avatar.picture = db.Blob(image)
    avatar.put()
    profile.avatarId = avatar.key().id()
    _calculateAndSetAvatarHash(profile, image)

def add_trial_service_overlay(image):
    image_width = images.Image(image).width
    scale = image_width / 50.0
    overlay = _get_trial_service_overlay()
    if scale != 1:
        overlay_img = images.Image(overlay)
        new_size = int(scale * overlay_img.width)
        overlay_img.resize(new_size, new_size)
        overlay = overlay_img.execute_transforms(overlay_img.format, 100)

    return composite([(image, 0, 0, 1.0, TOP_LEFT),
                      (overlay, int(5 * scale), int(-5 * scale), 1.0, BOTTOM_LEFT)], image_width, image_width)

@returns(unicode)
@arguments(user=users.User, app_id=unicode)
def get_profile_info_name(user, app_id):
    if user == MC_DASHBOARD:
        app_name = get_app_name_by_id(app_id)
        if app_id == App.APP_ID_ROGERTHAT:
            return u"%s Dashboard" % app_name
        else:
            return app_name
    else:
        profile_info = get_profile_info(user)
        if profile_info:
            return profile_info.name or profile_info.qualifiedIdentifier or remove_slash_default(user).email()
        else:
            return user.email()

def update_profile_from_profile_discovery(app_user, discovery):
    azzert(discovery.user == app_user)
    user_profile = get_user_profile(app_user)
    user_profile.name = discovery.name.strip()

    if discovery.avatar:
        img = images.Image(str(discovery.avatar))
        img.resize(150, 150)
        avatar = get_avatar_by_id(user_profile.avatarId)
        if not avatar:
            avatar = Avatar(user=app_user)
        image = img.execute_transforms(images.PNG, 100)
        avatar.picture = db.Blob(image)
        avatar.put()
        user_profile.avatarId = avatar.key().id()
        _calculateAndSetAvatarHash(user_profile, image)
    user_profile.version += 1
    user_profile.put()
    update_mobiles(app_user, user_profile)
    update_friends(user_profile)

@returns(NoneType)
@arguments(profile_info=ProfileInfo)
def update_friends(profile_info):
    """If profile_info is human user ==> update friends and services of human_user
    If profile_info is service_identity ==> update human friendMaps of service_identity"""
    from rogerthat.bizz.job.update_friends import schedule_update_friends_of_profile_info
    schedule_update_friends_of_profile_info(profile_info)


@returns([users.User])
@arguments(app_user=users.User, users_=[users.User])
def find_rogerthat_users_via_email(app_user, users_):
    users_ = filter(is_clean_app_user_email, users_)
    users_ = [p.user for p in get_existing_user_profiles(users_)]
    result = list()
    friend_map = get_friends_map(app_user)
    for u in users_:
        if u in friend_map.friends:
            continue
        result.append(u)
    return result


@returns([FacebookRogerthatProfileMatchTO])
@arguments(app_user=users.User, access_token=unicode)
def find_rogerthat_users_via_facebook(app_user, access_token):
    couple_facebook_id_with_profile(app_user, access_token)
    friends = get_friend_list_from_facebook(access_token)
    friends_dict = dict([(f['id'], (f['name'], f['picture']['data']['url'])) for f in friends])
    matches = get_existing_profiles_via_facebook_ids(friends_dict.keys(), get_app_id_from_app_user(app_user))
    result = list()
    friend_map = get_friends_map(app_user)
    for fbId, rtId in matches:
        if rtId in friend_map.friends:
            continue
        result.append(FacebookRogerthatProfileMatchTO(fbId, get_human_user_from_app_user(rtId).email(), friends_dict[fbId][0], friends_dict[fbId][1]))
    return result

def get_friend_list_from_facebook(access_token):
    args = dict()
    args["access_token"] = access_token
    args["fields"] = 'name,picture'
    result = urlfetch.fetch(url="https://graph.facebook.com/me/friends?" + urlencode(args), deadline=55)
    logging.info(result.content)
    if result.status_code == 200:
        return json.loads(result.content)["data"]
    raise Exception("Could not get friend list from facebook!\nstatus: %s\nerror:%s" % (result.status_code, result.content))

def _calculateAndSetAvatarHash(profile, image):
    digester = hashlib.sha256()
    digester.update(image)
    profile.avatarHash = digester.hexdigest().upper()
    logging.info("New avatar hash: %s", profile.avatarHash)
    from rogerthat.pages.profile import get_avatar_cached
    invalidate_cache(get_avatar_cached, profile.avatarId, 50)
    invalidate_cache(get_avatar_cached, profile.avatarId, 67)
    invalidate_cache(get_avatar_cached, profile.avatarId, 100)
    invalidate_cache(get_avatar_cached, profile.avatarId, 150)

@returns(NoneType)
@arguments(user=users.User, user_profile=UserProfile, skipped_mobile=Mobile, countdown=(int, long))
def update_mobiles(user, user_profile, skipped_mobile=None, countdown=5):
    request = IdentityUpdateRequestTO()
    request.identity = get_identity(user, user_profile)
    deferred.defer(_update_mobiles_deferred, user, request, skipped_mobile, _countdown=countdown)

def _update_mobiles_deferred(user, request, skipped_mobile):
    logging.info("Updating mobile of user %s" % user)
    extra_kwargs = dict()
    if skipped_mobile is not None:
        extra_kwargs[SKIP_ACCOUNTS] = [skipped_mobile.account]
    identityUpdate(identity_update_response_handler, logError, user, request=request, **extra_kwargs)

_TRIAL_SERVICE_OVERLAY_PATH = os.path.join(CURRENT_DIR, 'trial_service_overlay.png')
def _get_trial_service_overlay():
    f = open(_TRIAL_SERVICE_OVERLAY_PATH, "rb")
    try:
        return f.read()
    finally:
        f.close()

@returns(NoneType)
@arguments(service_user=users.User, app_user=users.User, data_string=unicode)
def set_profile_data(service_user, app_user, data_string):
    from rogerthat.bizz.service import InvalidJsonStringException, InvalidValueException, FriendNotFoundException

    data_object = None
    try:
        data_object = json.loads(data_string)
    except:
        raise InvalidJsonStringException()
    if data_object is None:
        raise InvalidJsonStringException()
    if not isinstance(data_object, dict):
        raise InvalidJsonStringException()

    for k, v in data_object.iteritems():
        if not isinstance(v, basestring):
            raise InvalidValueException(k, u"The values of profile_data must be strings")

    if not data_object:
        return

    def trans(data_update):
        user_profile = get_user_profile(app_user, cached=False)
        if not user_profile:
            logging.info('User %s not found', app_user.email())
            raise FriendNotFoundException()

        # Deserialize key-value store
        data = json.loads(user_profile.profileData) if user_profile.profileData else dict()

        # Update existing user data with new values
        data.update(data_update)

        # Remove keys with empty values
        for key in [key for key, value in data.iteritems() if value is None]:
            data.pop(key)

        user_profile.profileData = json.dumps(data) if data else None
        user_profile.put()

        on_trans_committed(update_mobiles, app_user, user_profile, countdown=0)
        on_trans_committed(schedule_re_index, app_user)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans, data_object)


def _archive_friend_connection(fsic_key):
    app_user = users.User(fsic_key.parent().name())
    service_identity_user = users.User(fsic_key.name())

    def trans():
        to_put = list()
        user_data_key = UserData.createKey(app_user, service_identity_user)
        fsic, user_data = db.get([fsic_key, user_data_key])
        archived_fsic = fsic.archive(FriendServiceIdentityConnectionArchive)
        if user_data:
            archived_user_data = user_data.archive(UserDataArchive)
            to_put.append(archived_user_data)
        to_put.append(archived_fsic)
        db.put(to_put)

    db.run_in_transaction(trans)
    breakFriendShip(service_identity_user, app_user)


def _unarchive_friend_connection(fsic_archive_key):
    app_user = users.User(fsic_archive_key.parent().name())
    service_identity_user = users.User(fsic_archive_key.name())

    user_data_key = UserDataArchive.createKey(app_user, service_identity_user)
    fsic_archive, user_data_archive = db.get([fsic_archive_key, user_data_key])

    to_delete = [fsic_archive]
    if user_data_archive:
        user_data_data = user_data_archive.data
        to_delete.append(user_data_archive)
    else:
        user_data_data = None

    makeFriends(service_identity_user, app_user, app_user, None, None, notify_invitee=False, notify_invitor=False,
                user_data=user_data_data)

    # set disabled and enabled broadcast types
    def trans():
        fsic = get_friend_serviceidentity_connection(app_user, service_identity_user)
        fsic.disabled_broadcast_types = fsic_archive.disabled_broadcast_types
        fsic.enabled_broadcast_types = fsic_archive.enabled_broadcast_types
        fsic.put()
        db.delete(to_delete)

    db.run_in_transaction(trans)


@returns()
@arguments(service_user=users.User)
def set_service_disabled(service_user):
    """
    Disconnects all connected users, stores them in an archive and deletes the service from search index.
    """
    from rogerthat.bizz.service import _cleanup_search_index, SERVICE_INDEX, SERVICE_LOCATION_INDEX

    def trans():
        to_put = list()
        service_profile = get_service_profile(service_user)
        service_profile.expiredAt = now()
        service_profile.enabled = False
        to_put.append(service_profile)
        service_identity_keys = get_service_identities_query(service_user, True)
        search_configs = db.get(
                [SearchConfig.create_key(create_service_identity_user(users.User(key.parent().name()), key.name())) for
                 key in service_identity_keys])

        svc_index = search.Index(name=SERVICE_INDEX)
        loc_index = search.Index(name=SERVICE_LOCATION_INDEX)

        for search_config in search_configs:
            if search_config:
                search_config.enabled = False
                to_put.append(search_config)
                on_trans_committed(_cleanup_search_index, search_config.service_identity_user.email(), svc_index,
                                   loc_index)

        for objects_to_put in chunks(to_put, 200):
            put_and_invalidate_cache(*objects_to_put)

        deferred.defer(cleanup_sessions, service_user, _transactional=True)
        deferred.defer(cleanup_friend_connections, service_user, _transactional=True)

    run_in_transaction(trans, True)


@returns()
@arguments(service_user=users.User)
def cleanup_friend_connections(service_user):
    run_job(get_all_service_friend_keys_query, [service_user], _archive_friend_connection, [])


@returns()
@arguments(service_user=users.User)
def cleanup_sessions(service_user):
    for user_profile_key in UserProfile.all(keys_only=True).filter('owningServiceEmails', service_user.email()):
        drop_sessions_of_user(users.User(user_profile_key.name()))
    drop_sessions_of_user(service_user)
    send_message(service_user, 'rogerthat.system.logout')


@returns()
@arguments(service_user=users.User)
def set_service_enabled(service_user):
    """
    Re-enables the service profile and restores all connected users.
    """
    service_profile = get_service_profile(service_user)
    service_profile.expiredAt = 0
    service_profile.enabled = True
    service_profile.put()

    run_job(get_all_archived_service_friend_keys_query, [service_user], _unarchive_friend_connection, [])
