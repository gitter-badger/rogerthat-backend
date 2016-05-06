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

from rogerthat.bizz import roles
from rogerthat.bizz.friends import breakFriendShip
from rogerthat.bizz.job import run_job
from rogerthat.bizz.roles import revoke_role
from rogerthat.bizz.service import remove_service_identity_from_index
from rogerthat.bizz.system import delete_service_finished
from rogerthat.bizz.user import delete_account
from rogerthat.dal import put_and_invalidate_cache, parent_key
from rogerthat.dal.mobile import get_user_active_mobiles
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.roles import get_service_grants
from rogerthat.dal.service import get_all_service_friend_keys_query, \
    get_service_identities
from rogerthat.models import ServiceIdentity, Avatar, App, \
    TrialServiceAccount, ProfilePointer, MessageFlowRunRecord, \
    ServiceInteractionDef, Branding, SIKKey, APIKey, ShortURL, UserProfile
from rogerthat.rpc import users
from rogerthat.rpc.models import Session, ServiceLog
from rogerthat.utils import azzert
from rogerthat.utils.app import create_app_user
from rogerthat.utils.service import create_service_identity_user, \
    get_service_user_from_service_identity_user
from google.appengine.ext import deferred, db
from mcfw.rpc import arguments, returns


class DeleteServiceTasks(db.Model):
    tasks = db.IntegerProperty()

@returns(NoneType)
@arguments(parent_service_user=users.User, service_user=users.User)
def job(parent_service_user, service_user):
    def trans():
        deferred.defer(_break_all_friends, parent_service_user, service_user, _transactional=True)
        deferred.defer(_continue_after_break_all_friends, parent_service_user, service_user, _transactional=True, _countdown=5)
    db.run_in_transaction(trans)

def _continue_after_break_all_friends(parent_service_user, service_user):
    key = get_all_service_friend_keys_query(create_service_identity_user(service_user, ServiceIdentity.DEFAULT)).get()
    if key is None:
        deferred.defer(_delete_roles, parent_service_user, service_user)
    else:
        deferred.defer(_continue_after_break_all_friends, parent_service_user, service_user, _countdown=5)

def _get_all_apps_keys_query():
    return App.all(keys_only=True)

def _break_all_friends(parent_service_user, service_user):
    run_job(get_all_service_friend_keys_query, [create_service_identity_user(service_user, ServiceIdentity.DEFAULT)], _break_friends, [])
    run_job(_get_all_apps_keys_query, [], _remove_autoconnected_service, [service_user])

def _break_friends(fsic_key):
    breakFriendShip(users.User(fsic_key.parent().name()), users.User(fsic_key.name()))

def _remove_autoconnected_service(app_key, service_user):
    def trans():
        app = db.get(app_key)
        identities = list()
        for acs in app.auto_connected_services:
            if get_service_user_from_service_identity_user(users.User(acs.service_identity_email)).email() == service_user.email():
                identities.append(acs.service_identity_email)

        updated = False
        if identities:
            updated = True
            for service_identity_email in identities:
                app.auto_connected_services.remove(service_identity_email)

        if service_user.email() in app.admin_services:
            updated = True
            app.admin_services.remove(service_user.email())

        if updated:
            app.put()

    db.run_in_transaction(trans)

def _delete_roles(parent_service_user, service_user):
    for gto in get_service_grants(service_user):
        if gto.role_type == roles.ROLE_TYPE_ADMIN and gto.role == roles.ROLE_ADMIN and gto.identity == ServiceIdentity.DEFAULT:
            revoke_role(create_service_identity_user(service_user, gto.identity),
                        create_app_user(users.User(gto.user_email), gto.app_id),
                        gto.role)
        else:
            azzert(False, "This should not happen.")

    deferred.defer(_delete_non_ancestor_models, parent_service_user, service_user)
    deferred.defer(_delete_ownership_users, service_user.email())

def _delete_non_ancestor_models(parent_service_user, service_user):
    sp = get_service_profile(service_user)
    if sp:
        def get_service_identity_based_keys():
            keys = list()
            si_users = list()
            for si in get_service_identities(service_user):
                keys.append(ProfilePointer.create_key(si.service_identity_user))
                si_users.append(si.service_identity_user)
            for qr in ServiceInteractionDef.all().ancestor(parent_key(service_user)):
                keys.append(db.Key.from_path(ShortURL.kind(), ServiceInteractionDef.shortUrl.get_value_for_datastore(qr).id()))
            return keys, si_users

        keys = [db.Key.from_path(Avatar.kind(), sp.avatarId)]
        keys.extend(TrialServiceAccount.all(keys_only=True).filter("service", service_user))
        more_keys, service_identity_users = db.run_in_transaction(get_service_identity_based_keys)
        keys.extend(more_keys)
        keys.extend(MessageFlowRunRecord.all(keys_only=True).filter("service_identity >=", service_user.email() + '/').filter("service_identity <", service_user.email() + u"/\ufffd"))
        keys.extend(Branding.all(keys_only=True).filter("user", service_user))
        keys.extend(SIKKey.all(keys_only=True).filter("user", service_user))
        keys.extend(APIKey.all(keys_only=True).filter("user", service_user))
        logging.info(keys)
        db.delete(keys)

        delete_service_tasks = DeleteServiceTasks(key_name=service_user.email())
        delete_service_tasks.tasks = 3
        delete_service_tasks.put()

        deferred.defer(_delete_sessions, parent_service_user, service_user)
        deferred.defer(_delete_service_log, parent_service_user, service_user)
        deferred.defer(_delete_service_models, parent_service_user, service_user)
        deferred.defer(_cleanup_service_identities, service_identity_users)
    else:
        if parent_service_user and parent_service_user != service_user:
            deferred.defer(delete_service_finished, parent_service_user, service_user.email(), True)

def _cleanup_service_identities(service_identity_users):
    for service_identity_user in service_identity_users:
        deferred.defer(remove_service_identity_from_index, service_identity_user)

def _delete_sessions(parent_service_user, service_user):
    keys = Session.all(keys_only=True).filter("user", service_user).fetch(1000)
    if keys:
        db.delete(keys)
        deferred.defer(_delete_sessions, parent_service_user, service_user, _countdown=5)
    else:
        _decrease_and_verify(parent_service_user, service_user)

def _delete_service_log(parent_service_user, service_user):
    keys = ServiceLog.all(keys_only=True).filter("user", service_user).fetch(1000)
    if keys:
        db.delete(keys)
        deferred.defer(_delete_service_log, parent_service_user, service_user, _countdown=5)
    else:
        _decrease_and_verify(parent_service_user, service_user)

def _delete_service_models(parent_service_user, service_user):
    key = parent_key(service_user)
    def trans():
        keys = db.GqlQuery("SELECT __key__ WHERE ANCESTOR IS KEY('%s')" % str(key)).fetch(1000)
        if keys:
            db.delete(keys)
            return True
        return False
    while db.run_in_transaction(trans):
        pass
    _decrease_and_verify(parent_service_user, service_user)

def _delete_ownership_users(service_email):
    to_put = []
    for up in UserProfile.all().filter("owningServiceEmails =", service_email):
        if service_email in up.owningServiceEmails:
            up.owningServiceEmails.remove(service_email)
        if list(get_user_active_mobiles(up.user)):
            if not up.owningServiceEmails:
                up.isCreatedForService = False
            to_put.append(up)
        else:
            if not up.owningServiceEmails:
                deferred.defer(delete_account, up.user, _countdown=5)
            else:
                to_put.append(up)

    if to_put:
        put_and_invalidate_cache(*to_put)

def _decrease_and_verify(parent_service_user, service_user):
    def trans():
        delete_service_tasks = DeleteServiceTasks.get_by_key_name(service_user.email())
        if delete_service_tasks:
            delete_service_tasks.tasks -= 1
            if delete_service_tasks.tasks <= 0:
                if parent_service_user and parent_service_user != service_user:
                    deferred.defer(delete_service_finished, parent_service_user, service_user.email(), True, _transactional=True)
                delete_service_tasks.delete()
            else:
                delete_service_tasks.put()

    db.run_in_transaction(trans)
