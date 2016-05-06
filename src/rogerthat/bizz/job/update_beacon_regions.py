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

from rogerthat.bizz.beacon import update_beacon_regions_response
from rogerthat.bizz.job import run_job
from rogerthat.capi.location import updateBeaconRegions
from rogerthat.dal.profile import get_user_profile_keys_by_app_id
from rogerthat.rpc.rpc import logError
from rogerthat.to.beacon import UpdateBeaconRegionsRequestTO
from google.appengine.ext import deferred, db
from mcfw.rpc import returns, arguments


@returns(NoneType)
@arguments(app_id=unicode)
def schedule_update_beacon_regions_for_all_users(app_id):
    deferred.defer(_run_update_beacon_regions_for_all_users, app_id, _transactional=db.is_in_transaction())

def _run_update_beacon_regions_for_all_users(app_id):
    request = UpdateBeaconRegionsRequestTO()
    run_job(get_user_profile_keys_by_app_id, [app_id], _update_beacon_regions_for_user, [request])

def _update_beacon_regions_for_user(up_key, request):
    user_profile = db.get(up_key)
    if user_profile.mobiles and len(user_profile.mobiles) > 0:
        updateBeaconRegions(update_beacon_regions_response, logError, user_profile.user, request=request)
