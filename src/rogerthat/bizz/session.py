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
import uuid
from types import NoneType

from google.appengine.api import users as gusers
from google.appengine.ext import db, deferred

from rogerthat.consts import SESSION_TIMEOUT
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.service import get_service_identities_by_service_identity_users
from rogerthat.exceptions import ServiceExpiredException
from rogerthat.rpc import users
from rogerthat.rpc.models import Session
from rogerthat.utils import now
from rogerthat.utils.crypto import md5_hex
from rogerthat.utils.service import create_service_identity_user
from mcfw.cache import cached
from mcfw.rpc import returns, arguments
from mcfw.utils import chunks


@cached(1, lifetime=3600, request=False, memcache=True)
@returns(Session)
@arguments(user=gusers.User)
def create_session_for_google_authenticated_user(user):
    secret = md5_hex(user.email().encode('utf-8'))
    timeout = now() + SESSION_TIMEOUT
    session = Session.get_or_insert(key_name=secret,
                                    user=user,
                                    timeout=timeout,
                                    name=user.email(),
                                    deleted=False,
                                    type=Session.TYPE_GOOGLE)
    return session


@returns(tuple)
@arguments(user=users.User, ignore_expiration=bool, service_identity=unicode)
def create_session(user, ignore_expiration=False, service_identity=None):
    from rogerthat.dal.profile import get_profile_info
    from rogerthat.dal.roles import get_service_identities_via_user_roles
    secret = unicode(uuid.uuid4()).replace("-", "")
    timeout = now() + SESSION_TIMEOUT
    session_profile_info = get_profile_info(user, skip_warning=True)
    session = Session(key_name=secret,
                      user=user,
                      timeout=timeout,
                      name=session_profile_info.name,
                      deleted=False,
                      type=Session.TYPE_ROGERTHAT,
                      service_identity=service_identity)
    if not session_profile_info.isServiceIdentity:
        user_services = []
        if session_profile_info.owningServiceEmails:
            my_owning_service_identity_users = [create_service_identity_user(users.User(owning_service_email))
                                                for owning_service_email in session_profile_info.owningServiceEmails]
            my_owning_service_identities = get_service_identities_by_service_identity_users(my_owning_service_identity_users)
            user_services.extend(my_owning_service_identities)
        user_services.extend(get_service_identities_via_user_roles(user))

        if session_profile_info.isCreatedForService and len(user_services) == 1:
            # when there are multiple profiles, the expired checking is done in login_as logic
            if not ignore_expiration:
                service_profile = get_service_profile(users.User(session_profile_info.owningServiceEmails[0]))
                if service_profile.expiredAt > 0:
                    raise ServiceExpiredException()
            session = Session(key_name=secret,
                              user=users.User(session_profile_info.owningServiceEmails[0]),
                              timeout=timeout,
                              deleted=False,
                              type=Session.TYPE_ROGERTHAT,
                              service_identity=service_identity)
        else:
            session.service_users = sorted(user_services, key=lambda us: "%s <%s>" % (us.name, us.service_identity_user))

    session.put()
    return secret, session


@returns(NoneType)
@arguments(session=Session)
def drop_session(session):
    session.deleted = True
    session.put()


@returns(NoneType)
@arguments(user=users.User)
def drop_sessions_of_user(user):
    sessions = list(Session.all().filter("user =", user).filter('deleted', False))
    for session in sessions:
        session.deleted = True
    for chunk in chunks(sessions, 200):
        db.put(chunk)


@returns(tuple)
@arguments(secret=unicode, logged_in_as=unicode)
def validate_session(secret, logged_in_as):
    from rogerthat.utils.service import get_service_identity_tuple
    session = db.run_in_transaction(Session.get_by_key_name, secret)
    if not session or session.deleted:
        return None, None
    if session.timeout < now():
        session.deleted = True
        session.put()
        return None, None
    if session.timeout < now() + (SESSION_TIMEOUT / 2):
        deferred.defer(_update_session_timeout, secret)
    if logged_in_as:
        if logged_in_as == session.user.email():
            return session, session.user
        if not (session.shop or session.has_access(logged_in_as)):
            logging.info("Dropping session because '%s' was not found in %s", logged_in_as, session.service_users_blob)
            session.delete()
            return None, None
        else:
            service_identity_user = users.User(logged_in_as)
            service_user, _ = get_service_identity_tuple(service_identity_user)
            return session, service_user
    if session.service_identity_user:
        service_user, _ = get_service_identity_tuple(session.service_identity_user)
        return session, service_user
    return session, session.user


def _update_session_timeout(secret):
    def trans():
        session = Session.get_by_key_name(secret)
        if session and session.timeout < now() + (SESSION_TIMEOUT / 2):
            session.timeout = now() + SESSION_TIMEOUT
            session.put()
    db.run_in_transaction(trans)


@returns(Session)
@arguments(session=Session, service_identity_user=users.User, read_only=bool, shop=bool)
def switch_to_service_identity(session, service_identity_user, read_only, shop):
    from rogerthat.dal.profile import get_profile_info
    secret = session.key().name()
    if service_identity_user:
        session_profile_info = get_profile_info(service_identity_user, skip_warning=True)
    def trans():
        session = Session.get_by_key_name(secret)
        session.service_identity_user = service_identity_user
        session.read_only = read_only
        session.shop = shop
        session.name = session_profile_info.name if service_identity_user else None
        session.service_identity = None
        session.put()
        return session
    return db.run_in_transaction(trans)

@returns(Session)
@arguments(session=Session, service_identity=unicode)
def set_service_identity(session, service_identity):
    secret = session.key().name()
    def trans():
        session = Session.get_by_key_name(secret)
        session.service_identity = service_identity
        session.put()
        return session
    return db.run_in_transaction(trans)
