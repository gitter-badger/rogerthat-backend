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

from rogerthat.dal import parent_key
from rogerthat.dal.profile import get_user_profile
from rogerthat.dal.service import get_service_identities_by_service_identity_users
from rogerthat.models import ServiceIdentity, UserProfile, ServiceRole, ServiceProfile
from rogerthat.rpc import users
from rogerthat.to.roles import GrantTO
from rogerthat.utils.app import get_human_user_from_app_user
from rogerthat.utils.service import get_service_identity_tuple
from mcfw.rpc import arguments, returns
from types import NoneType


@returns([ServiceIdentity])
@arguments(user=users.User, app_id=unicode, organization_type=int, cached=bool)
def get_service_identities_via_user_roles(user, app_id=None, organization_type=ServiceProfile.ORGANIZATION_TYPE_UNSPECIFIED, cached=True):
    """
    Returns a list of service identities for which the user has an administration role
    """
    from rogerthat.bizz.roles import ROLES
    user_profile = get_user_profile(user, cached)
    service_identity_users = (users.User(si_email) for si_email, roles in user_profile.grants.iteritems()
                              if [role for role in roles if role in ROLES])
    return get_service_identities_by_service_identity_users(service_identity_users, app_id, organization_type)

@returns([GrantTO])
@arguments(service_user=users.User, filtered_service_identity=unicode, filtered_role_id=(NoneType, int, long),
           filtered_role_type=unicode)
def get_service_grants(service_user, filtered_service_identity=ServiceIdentity.DEFAULT, filtered_role_id=None,
                       filtered_role_type=None):
    from rogerthat.bizz.roles import ROLE_TYPE_ADMIN, ROLE_TYPE_SERVICE
    service_user_email = service_user.email()
    if not isinstance(service_user_email, unicode):
        service_user_email = service_user_email.decode('utf-8')

    profiles = UserProfile.all().filter('role_services >=', service_user_email + '/').filter('role_services <', service_user_email + u'/\ufffd')
    for p in profiles:
        for si, roles in p.grants.iteritems():
            if si.startswith(service_user_email + '/'):
                _, identity = get_service_identity_tuple(users.User(si))
                if filtered_service_identity != ServiceIdentity.DEFAULT and identity != filtered_service_identity:
                    continue
                for role in roles:
                    gto = GrantTO()
                    if role.startswith('sr:'):
                        gto.role_type = ROLE_TYPE_SERVICE
                        gto.role = None
                        gto.role_id = int(role[3:])
                    else:
                        gto.role_type = ROLE_TYPE_ADMIN
                        gto.role = role
                        gto.role_id = -1

                    if filtered_role_id is not None and filtered_role_id != gto.role_id:
                        continue
                    if filtered_role_type is not None and filtered_role_type != gto.role_type:
                        continue

                    gto.identity = identity
                    gto.service_email = service_user_email
                    gto.user_email = get_human_user_from_app_user(p.user).email()
                    gto.user_name = p.name
                    gto.user_avatar_id = p.avatarId
                    gto.app_id = p.app_id
                    yield gto

@returns([GrantTO])
@arguments(service_user=users.User)
def get_service_admins(service_user):
    from rogerthat.bizz import roles
    for gto in get_service_grants(service_user):
        if gto.role_type == roles.ROLE_TYPE_ADMIN and gto.role == roles.ROLE_ADMIN and gto.identity == ServiceIdentity.DEFAULT:
            yield gto

@returns(ServiceRole)
@arguments(service_user=users.User, name=unicode)
def get_service_role_by_name(service_user, name):
    return ServiceRole.all().ancestor(parent_key(service_user)).filter('name =', name).get()

@returns(ServiceRole)
@arguments(service_user=users.User, role_id=(int, long))
def get_service_role_by_id(service_user, role_id):
    return ServiceRole.get_by_id(role_id, parent_key(service_user))

@returns([ServiceRole])
@arguments(service_user=users.User, role_ids=[(int, long)])
def get_service_roles_by_ids(service_user, role_ids):
    return ServiceRole.get_by_id(role_ids, parent_key(service_user))

@returns([GrantTO])
@arguments(service_user=users.User, role_id=(int, long))
def get_service_role_grants(service_user, role_id):
    from rogerthat.bizz import roles
    for gto in get_service_grants(service_user):
        if gto.role_type == roles.ROLE_TYPE_SERVICE and gto.role_id == role_id:
            yield gto

@returns([ServiceRole])
@arguments(service_user=users.User)
def list_service_roles(service_user):
    return ServiceRole.all().ancestor(parent_key(service_user)).order('name')

@returns([ServiceRole])
@arguments(service_user=users.User, role_type=unicode)
def list_service_roles_by_type(service_user, role_type):
    return ServiceRole.all().ancestor(parent_key(service_user)).filter('type =', role_type)
