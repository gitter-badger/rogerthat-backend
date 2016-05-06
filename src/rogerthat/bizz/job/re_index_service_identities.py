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
from rogerthat.bizz.service import SERVICE_INDEX, SERVICE_LOCATION_INDEX, re_index
from rogerthat.dal.profile import is_trial_service
from rogerthat.models import ServiceIdentity
from rogerthat.utils.service import get_service_user_from_service_identity_user
from google.appengine.api import search
from google.appengine.ext import db


def drop_index(index):
    while True:
        search_result = index.get_range(ids_only=True)
        ids = [r.doc_id for r in search_result.results]
        if not ids:
            break
        index.delete(ids)

def job():
    svc_index = search.Index(name=SERVICE_INDEX)
    loc_index = search.Index(name=SERVICE_LOCATION_INDEX)

    drop_index(svc_index)
    drop_index(loc_index)

    run_job(query, [], worker, [])

def worker(si_key):
    si = db.get(si_key)
    service_user = get_service_user_from_service_identity_user(si.service_identity_user)
    if is_trial_service(service_user):
        return
    re_index(si.service_identity_user)

def query():
    return ServiceIdentity.all(keys_only=True)
