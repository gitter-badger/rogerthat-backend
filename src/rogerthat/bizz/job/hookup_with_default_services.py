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

from rogerthat.bizz.friends import makeFriends, ORIGIN_USER_INVITE, send_is_in_roles
from rogerthat.dal import parent_key
from rogerthat.dal.app import get_app_by_id
from rogerthat.dal.profile import get_user_profile, get_service_profile
from rogerthat.dal.roles import get_service_roles_by_ids
from rogerthat.models import UserInteraction, ServiceRole
from rogerthat.models.properties.app import AutoConnectedService
from rogerthat.rpc import users
from rogerthat.to.roles import RoleTO
from rogerthat.to.service import UserDetailsTO
from rogerthat.utils import azzert, get_country_code_by_ipaddress
from rogerthat.utils.app import get_app_id_from_app_user
from rogerthat.utils.service import get_service_identity_tuple
from google.appengine.ext import deferred, db
from mcfw.rpc import arguments, returns


@returns(NoneType)
@arguments(app_user=users.User, ipaddress=unicode)
def schedule(app_user, ipaddress):
    deferred.defer(run, app_user, ipaddress, _transactional=db.is_in_transaction(), _countdown=2)


@returns(UserInteraction)
@arguments(app_user=users.User)
def get_user_interaction(app_user):
    return UserInteraction.get_by_key_name(app_user.email(), parent=parent_key(app_user)) \
        or UserInteraction(key_name=app_user.email(), parent=parent_key(app_user))


@returns(NoneType)
@arguments(app_user_or_key=(users.User, db.Key), ipaddress=unicode)
def run(app_user_or_key, ipaddress):
    app_user = app_user_or_key if isinstance(app_user_or_key, users.User) else users.User(app_user_or_key.name())
    app = get_app_by_id(get_app_id_from_app_user(app_user))
    logging.debug("Default services for the '%s' app are: %s", app.name,
                 [a.service_identity_email for a in app.auto_connected_services])
    for i, acs in enumerate(app.auto_connected_services):
        run_for_auto_connected_service(app_user, acs, ipaddress, i * 2)


@returns(NoneType)
@arguments(app_user_or_key=(users.User, db.Key), acs=AutoConnectedService, ipaddress=unicode, countdown=int)
def run_for_auto_connected_service(app_user_or_key, acs, ipaddress=None, countdown=0):
    app_user = app_user_or_key if isinstance(app_user_or_key, users.User) else users.User(app_user_or_key.name())

    def trans():
        if acs.local:
            deferred.defer(run_local_services, app_user, ipaddress, acs, _transactional=True, _countdown=countdown)
        else:
            hookup(app_user, acs)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


def run_local_services(app_user, ipaddress, auto_connected_service):
    logging.debug("Checking if %s (ip: %s) is in %s for %s",
                  app_user, ipaddress, auto_connected_service.local, auto_connected_service.service_identity_email)

    profile = get_user_profile(app_user)
    if not profile.language:
        logging.info("Can't connect %s to %s. User has no language set.",
                     app_user, auto_connected_service.service_identity_email)
        return

    if profile.country:
        country_code = profile.country
    elif ipaddress:
        country_code = get_country_code_by_ipaddress(ipaddress)
        azzert(country_code)
    else:
        logging.info("Can't connect %s to %s if there is no ip address, and no country in UserProfile.",
                     app_user, auto_connected_service.service_identity_email)
        return

    local_service_map_key = "%s-%s" % (profile.language, country_code.lower())

    if local_service_map_key in auto_connected_service.local:
        deferred.defer(hookup, app_user, auto_connected_service)
    else:
        logging.info("Not connecting to %s. There is no entry for local key %s",
                     auto_connected_service.service_identity_email, local_service_map_key)


def hookup(app_user, acs):
    def trans():
        user_profile = get_user_profile(app_user)
        if user_profile.isCreatedForService:
            return

        ui = get_user_interaction(app_user)
        if acs.service_identity_email not in ui.services:
            service_identity_user = users.User(acs.service_identity_email)
            do_make_friends = True
            if acs.service_roles:
                do_make_friends = False
                # is app_user in one of the roles?
                service_user, si_id = get_service_identity_tuple(service_identity_user)
                synced_roles = list()
                for service_role in get_service_roles_by_ids(service_user, acs.service_roles):
                    if user_profile.has_role(service_identity_user, u'sr:%s' % service_role.role_id):
                        do_make_friends = True
                        break
                    elif service_role.type == ServiceRole.TYPE_SYNCED:
                        synced_roles.append(service_role)
                else:
                    # for loop did not reach BREAK: user_profile does not have any role --> send friend.is_in_roles
                    user_details = [UserDetailsTO.fromUserProfile(user_profile)]
                    send_is_in_roles(app_user, get_service_profile(service_user), si_id, user_details,
                                     map(RoleTO.fromServiceRole, synced_roles), make_friends_if_in_role=True)

            if do_make_friends:
                ui.services.append(acs.service_identity_email)
                ui.put()
                logging.info("Connecting %s with auto-connected service %s", app_user, acs.service_identity_email)
                deferred.defer(makeFriends, service_identity_user, app_user, app_user, None,
                               notify_invitee=False, origin=ORIGIN_USER_INVITE, _transactional=True)

    if db.is_in_transaction():
        trans()
    else:
        xg_on = db.create_transaction_options(xg=True)
        db.run_in_transaction_options(xg_on, trans)
