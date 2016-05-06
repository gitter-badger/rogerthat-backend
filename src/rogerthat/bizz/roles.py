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

from types import NoneType

from rogerthat.bizz.service import RoleAlreadyExistsException, InvalidRoleTypeException, \
    DeleteRoleFailedHasMembersException, RoleNotFoundException, ServiceIdentityDoesNotExistException, \
    DeleteRoleFailedHasSMDException
from rogerthat.bizz.session import drop_sessions_of_user
from rogerthat.dal import parent_key
from rogerthat.dal.profile import get_user_profile, get_service_profile
from rogerthat.dal.roles import get_service_role_by_name, get_service_role_grants, get_service_role_by_id
from rogerthat.dal.service import get_service_identity
from rogerthat.models import ServiceRole, ServiceIdentity, UserProfile, ServiceMenuDef
from rogerthat.rpc import users
from rogerthat.utils import azzert, now, channel, bizz_check
from rogerthat.utils.app import create_app_user_by_email
from rogerthat.utils.service import create_service_identity_user, get_service_user_from_service_identity_user, \
    get_identity_from_service_identity_user
from google.appengine.ext import db, deferred
from mcfw.rpc import returns, arguments


ROLE_TYPE_ADMIN = u'admin'
ROLE_TYPE_SERVICE = u'service'
ROLE_TYPES = (ROLE_TYPE_ADMIN, ROLE_TYPE_SERVICE)

ROLE_ADMIN = u'admin'
ROLES = (ROLE_ADMIN,)


@returns(NoneType)
@arguments(service_identity_user=users.User, user=users.User, role=(unicode, ServiceRole))
def grant_role(service_identity_user, user, role):
    admin = False
    service_identity = get_service_identity(service_identity_user)
    if not service_identity:
        raise ServiceIdentityDoesNotExistException(get_identity_from_service_identity_user(service_identity_user))
    if isinstance(role, unicode):
        admin = True
        azzert(role in ROLES)  # builtin
    else:
        azzert(role.service_user == service_identity.service_user)
        role = u'sr:%s' % role.role_id

    def trans():
        user_profile = get_user_profile(user, False)
        bizz_check(user_profile, "User %s does not exist" % user.email())
        user_profile.grant_role(service_identity_user, role)
        user_profile.put()

    if db.is_in_transaction():
        trans()
    else:
        db.run_in_transaction(trans)

    if admin:
        _send_admin_role_updates(service_identity_user)


@returns(NoneType)
@arguments(service_identity_user=users.User, user=users.User, role=(unicode, ServiceRole))
def revoke_role(service_identity_user, user, role):
    admin = False
    service_identity = get_service_identity(service_identity_user)
    if not service_identity:
        raise ServiceIdentityDoesNotExistException(get_identity_from_service_identity_user(service_identity_user))
    if isinstance(role, unicode):
        admin = True
        azzert(role in ROLES)  # builtin
    else:
        azzert(role.service_user == service_identity.service_user)
        role = u'sr:%s' % role.role_id

    def trans():
        user_profile = get_user_profile(user, False)
        user_profile.revoke_role(service_identity_user, role)
        user_profile.put()
        if admin:
            deferred.defer(drop_sessions_of_user, user, _transactional=True)

    if db.is_in_transaction():
        trans()
    else:
        db.run_in_transaction(trans)

    if admin:
        _send_admin_role_updates(service_identity_user)


@returns(bool)
@arguments(service_identity=(users.User, ServiceIdentity), user=(users.User, UserProfile), role=(unicode, ServiceRole))
def has_role(service_identity, user, role):
    if isinstance(service_identity, users.User):
        service_identity_user = service_identity
        service_identity = get_service_identity(service_identity_user)
        azzert(service_identity, "Service identity %s not found" % service_identity_user)
    else:
        service_identity_user = service_identity.service_identity_user

    if isinstance(user, users.User):
        user_profile = get_user_profile(user, True)
    else:
        user_profile = user
        user = user_profile.user

    if isinstance(role, unicode):
        # Admin role, just fallback on UserProfile.has_role
        return user_profile.has_role(service_identity_user, role)

    azzert(role.service_user == service_identity.service_user)
    role = u'sr:%s' % role.role_id
    # check on the service identity itself
    if user_profile.has_role(service_identity_user, role):
        return True
    if service_identity.is_default:
        return False
    # check on the default service identity
    return user_profile.has_role(create_service_identity_user(service_identity.service_user, ServiceIdentity.DEFAULT),
                                 role)


@returns(ServiceRole)
@arguments(service_user=users.User, name=unicode, type_=unicode)
def create_service_role(service_user, name, type_=unicode):
    if type_ not in ServiceRole.TYPES:
        raise InvalidRoleTypeException(type_)
    service_profile = get_service_profile(service_user)
    azzert(service_profile, "Service %s does not exist" % service_user)
    def trans():
        service_role = get_service_role_by_name(service_user, name)
        if service_role:
            raise RoleAlreadyExistsException(name)
        service_role = ServiceRole(parent=parent_key(service_user))
        service_role.name = name
        service_role.creationTime = now()
        service_role.type = type_
        service_role.put()
        return service_role
    try:
        return db.run_in_transaction(trans)
    finally:
        _send_service_role_updates(service_user)


@returns(NoneType)
@arguments(service_user=users.User, role_id=(int, long), cleanup_members=bool)
def delete_service_role(service_user, role_id, cleanup_members=False):
    service_role = get_service_role_by_id(service_user, role_id)
    if not service_role:
        raise RoleNotFoundException(role_id)

    if bool(ServiceMenuDef.all().ancestor(parent_key(service_user)).filter('roles =', role_id).count(1)):
        raise DeleteRoleFailedHasSMDException(role_id)

    if cleanup_members:
        service_identity_user = create_service_identity_user(service_user)
        role = u'sr:%s' % role_id
        for srg in get_service_role_grants(service_user, role_id):
            app_user = create_app_user_by_email(srg.user_email, srg.app_id)
            def trans():
                user_profile = get_user_profile(app_user, False)
                user_profile.revoke_role(service_identity_user, role)
                user_profile.put()

            if db.is_in_transaction():
                trans()
            else:
                db.run_in_transaction(trans)
    else:
        has_grants = any(get_service_role_grants(service_user, role_id))
        if has_grants:
            raise DeleteRoleFailedHasMembersException(role_id)

    db.delete(service_role)
    _send_service_role_updates(service_user)


@returns(NoneType)
@arguments(service_user=users.User, identity=unicode, user=users.User, role_id=(int, long))
def grant_service_role(service_user, identity, user, role_id):
    service_role = get_service_role_by_id(service_user, role_id)
    if not service_role:
        raise RoleNotFoundException(role_id)
    service_identity_user = create_service_identity_user(service_user, identity)
    grant_role(service_identity_user, user, service_role)
    _send_service_role_grants_updates(service_user)
    _send_update_friend(service_user, identity, user, force=True)


@returns(NoneType)
@arguments(service_user=users.User, identity=unicode, user=users.User, role_id=(int, long))
def revoke_service_role(service_user, identity, user, role_id):
    service_role = get_service_role_by_id(service_user, role_id)
    if not service_role:
        raise RoleNotFoundException(role_id)
    service_identity_user = create_service_identity_user(service_user, identity)
    revoke_role(service_identity_user, user, service_role)
    _send_service_role_grants_updates(service_user)
    _send_update_friend(service_user, identity, user, force=True)


def _send_update_friend(service_user, identity, user, force=False):
    if identity == ServiceIdentity.DEFAULT:
        # schedule update for all identities
        from rogerthat.bizz.job.update_friends import schedule_update_a_friend_of_service_user
        schedule_update_a_friend_of_service_user(service_user, user, force=force)
    else:
        from rogerthat.bizz.job.update_friends import schedule_update_a_friend_of_a_service_identity_user
        schedule_update_a_friend_of_a_service_identity_user(create_service_identity_user(service_user, identity), user,
                                                            force=force)


def _send_admin_role_updates(service_identity_user):
    channel.send_message(get_service_user_from_service_identity_user(service_identity_user),
                         u'rogerthat.service.adminsChanged')


def _send_service_role_updates(service_user):
    channel.send_message(service_user, u'rogerthat.service.roles.updated')


def _send_service_role_grants_updates(service_user):
    channel.send_message(service_user, u'rogerthat.service.role.grants.updated')
