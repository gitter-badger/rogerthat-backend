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
import time
from types import NoneType
import uuid

from rogerthat.bizz.friends import send_is_in_roles
from rogerthat.bizz.job import run_job
from rogerthat.consts import HIGH_LOAD_CONTROLLER_QUEUE
from rogerthat.dal.profile import get_user_profile, get_service_profile
from rogerthat.dal.roles import list_service_roles_by_type
from rogerthat.dal.service import get_all_service_friend_keys_query
from rogerthat.models import ServiceRole
from rogerthat.rpc import users
from rogerthat.to.roles import RoleTO
from rogerthat.to.service import UserDetailsTO
from rogerthat.utils import try_or_defer
from rogerthat.utils.service import create_service_identity_user, get_service_identity_tuple
from google.appengine.ext import db, deferred
from mcfw.rpc import returns, arguments


class RebuildRolesJob(db.Model):
    service_user = db.UserProperty(indexed=False)
    app_users = db.ListProperty(users.User, indexed=False)  # App users for which a RebuildRolesByMemberJob needs to be scheduled
    service_identity_users = db.ListProperty(users.User, indexed=False)

    @property
    def job_guid(self):
        return self.key().name()

    @classmethod
    def create_key(cls, job_guid):
        return db.Key.from_path(cls.kind(), job_guid)


class RebuildRolesJobMember(db.Model):

    @property
    def member(self):
        return self.key().name().split(" ")[0]

    @property
    def service_identity(self):
        return self.key().name().split(" ")[1]

    @classmethod
    def create_key(cls, job, member, service_identity_user):
        return db.Key.from_path(cls.kind(), "%s %s" % (member.email(), service_identity_user.email()), parent=job.key())


@returns(NoneType)
@arguments(service_user=users.User, app_users=[users.User], service_identity_users=[users.User])
def schedule_rebuild_synced_roles(service_user, app_users, service_identity_users):
    job_guid = uuid.uuid4().get_hex()
    logging.debug("Scheduling rebuild_synced_roles job with guid %s", job_guid)

    def trans():
        RebuildRolesJob(key=RebuildRolesJob.create_key(job_guid),
                        app_users=app_users,
                        service_user=service_user,
                        service_identity_users=service_identity_users).put()
        deferred.defer(_build_job, job_guid, None, _transactional=True, _queue=HIGH_LOAD_CONTROLLER_QUEUE)

    db.run_in_transaction(trans)


def _build_job(job_guid, cursor):
    job = db.get(RebuildRolesJob.create_key(job_guid))
    start = time.time()
    qry = get_all_service_friend_keys_query(create_service_identity_user(job.service_user))
    while True:
        qry.with_cursor(cursor)
        fsic_keys = qry.fetch(100)
        cursor = qry.cursor()
        logging.debug("Fetched %s FriendServiceIdentityConnection keys", len(fsic_keys))
        if not fsic_keys:  # Query reached its end
            deferred.defer(_start_job, job_guid, _queue=HIGH_LOAD_CONTROLLER_QUEUE)
            return
        work = list()
        for fsic_key in fsic_keys:
            app_user = users.User(fsic_key.parent().name())
            if job.app_users and not app_user in job.app_users:
                continue
            service_identity_user = users.User(fsic_key.name())
            if job.service_identity_users and not service_identity_user in job.service_identity_users:
                continue
            work.append(RebuildRolesJobMember(key=RebuildRolesJobMember.create_key(job, app_user, service_identity_user)))
        db.put(work)
        if time.time() - start > 500:
            deferred.defer(_build_job, job_guid, cursor, _queue=HIGH_LOAD_CONTROLLER_QUEUE)
            return


def _start_job(job_guid):
    job = db.get(RebuildRolesJob.create_key(job_guid))
    roles = map(RoleTO.fromServiceRole, list_service_roles_by_type(job.service_user, ServiceRole.TYPE_SYNCED))
    def trans():
        run_job(_worker_qry, [job_guid], _worker_task, [roles], qry_transactional=True)
        deferred.defer(_cleanup, job_guid, _queue=HIGH_LOAD_CONTROLLER_QUEUE, _countdown=5, _transactional=True)
    db.run_in_transaction(trans)


def _worker_qry(job_guid):
    qry = db.GqlQuery("SELECT __key__ FROM RebuildRolesJobMember WHERE ANCESTOR IS :job_key")
    qry.bind(job_key=RebuildRolesJob.create_key(job_guid))
    return qry


def _worker_task(key, roles):
    app_user, service_identity_user = map(users.User, key.name().split(" "))
    up = get_user_profile(app_user)
    if up:
        user_details = [UserDetailsTO.fromUserProfile(up)]
        service_user, identifier = get_service_identity_tuple(service_identity_user)
        service_profile = get_service_profile(service_user)
        logging.debug("Sending is_in_roles for app_user %s and service_identity_user %s", app_user, service_identity_user)
        send_is_in_roles(app_user, service_profile, identifier, user_details, roles)
    try_or_defer(db.delete, key)


def _cleanup(job_guid):
    def trans():
        qry = _worker_qry(job_guid)
        if qry.fetch(1):
            deferred.defer(_cleanup, job_guid, _queue=HIGH_LOAD_CONTROLLER_QUEUE, _countdown=5, _transactional=True)
        else:
            db.delete(RebuildRolesJob.create_key(job_guid))
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)
