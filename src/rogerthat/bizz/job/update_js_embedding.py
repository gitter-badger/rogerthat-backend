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

from rogerthat.bizz.job import run_job
from rogerthat.bizz.js_embedding.mapping import update_jsembedding_response
from rogerthat.capi.system import updateJsEmbedding
from rogerthat.dal.mobile import get_active_mobiles_keys
from rogerthat.rpc.rpc import logError
from rogerthat.to.js_embedding import UpdateJSEmbeddingRequestTO
from google.appengine.ext import deferred, db
from mcfw.rpc import returns, arguments


@returns(NoneType)
@arguments(db_keys=list)
def schedule_update_embedded_js_for_all_users(db_keys):
    deferred.defer(_run_update_embedded_js_for_all_users, db_keys, _transactional=db.is_in_transaction())

def _run_update_embedded_js_for_all_users(db_keys):

    def run():
        return db.get(db_keys)

    xg_on = db.create_transaction_options(xg=True)
    js_embedding_models = db.run_in_transaction_options(xg_on, run)

    request = UpdateJSEmbeddingRequestTO.fromDBJSEmbedding(js_embedding_models)
    run_job(get_active_mobiles_keys, [], _update_embedded_js_for_user, [request])


def _update_embedded_js_for_user(mobile_key, request):
    mobile = db.get(mobile_key)
    updateJsEmbedding(update_jsembedding_response, logError, mobile.user, request=request)
