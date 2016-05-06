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

from rogerthat.bizz.job import run_job
from rogerthat.bizz.job.update_friends import _update_friend_via_friend_connection
from rogerthat.bizz.service.mfd import render_js_for_message_flow_designs
from rogerthat.dal import put_and_invalidate_cache
from rogerthat.dal.mfd import get_message_flow_designs_by_status
from rogerthat.dal.profile import get_service_profile
from rogerthat.models import MessageFlowDesign, ServiceProfile
from rogerthat.rpc import users
from google.appengine.ext import db


def job_regenerate_js():
    run_job(_get_service_profile_keys, [], _task_regenerate_js, [])


def _get_service_profile_keys():
    return ServiceProfile.all(keys_only=True)


def _task_regenerate_js(service_profile_key):
    service_user = users.User(service_profile_key.parent().name())

    def trans_get_mfds():
        return get_message_flow_designs_by_status(service_user, MessageFlowDesign.STATUS_VALID)

    def trans_update(mfds):
        service_profile = get_service_profile(service_user)
        service_profile.version += 1

        put_and_invalidate_cache(service_profile, *mfds)

    mfds = db.run_in_transaction(trans_get_mfds)
    render_js_for_message_flow_designs(mfds, notify_friends=False)
    db.run_in_transaction(trans_update, mfds)


def job_update_friends():
    run_job(_get_fsic_keys, [], _task_update_friends, [])

def _get_fsic_keys():
    return db.GqlQuery("SELECT __key__ FROM FriendServiceIdentityConnection")

def _task_update_friends(fsic_key):
    _update_friend_via_friend_connection(fsic_key, None)
