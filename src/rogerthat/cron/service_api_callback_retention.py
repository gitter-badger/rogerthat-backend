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

import json
import logging

from rogerthat.bizz import monitoring
from rogerthat.bizz.service import send_callback_delivery_warning
from rogerthat.consts import SERVICE_API_CALLBACK_RETRY_UNIT
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.service import log_service_activity
from rogerthat.rpc.models import ServiceLog
from rogerthat.rpc.service import submit_service_api_callback
from rogerthat.utils import now
from rogerthat.utils.models import run_all
from google.appengine.ext import webapp, db


class ProcessServiceAPICallbackHandler(webapp.RequestHandler):

    def get(self):
        def process(service_api_callback):
            try:
                svc_profile = get_service_profile(service_api_callback.service_user)
                if not svc_profile.enabled:
                    service_api_callback.timestamp = 0 - service_api_callback.timestamp
                    service_api_callback.put()
                    return
                retry_call_back = True
                service_api_callback.retryCount += 1
                service_api_callback.timestamp = now() + (SERVICE_API_CALLBACK_RETRY_UNIT * 2 ** service_api_callback.retryCount)
                if service_api_callback.retryCount > 2:
                    monitoring.log_service_api_failure(service_api_callback, monitoring.SERVICE_API_CALLBACK)
                if service_api_callback.retryCount > 7:
                    send_callback_delivery_warning(svc_profile, "callback timeout delivery")
                service_api_callback.put()
                if not retry_call_back:
                    return
                success, message = submit_service_api_callback(svc_profile, service_api_callback)
                request = json.loads(service_api_callback.call)
                log_service_activity(svc_profile.user, request["id"], ServiceLog.TYPE_CALLBACK,
                                     ServiceLog.STATUS_WAITING_FOR_RESPONSE if success else ServiceLog.STATUS_ERROR,
                                      request["method"], service_api_callback.call, message)
            except Exception, e:
                logging.error("Could not process service api callback retention:\n%s" % e)

        qry = db.GqlQuery("SELECT * FROM ServiceAPICallback WHERE timestamp < :retention_timeout AND timestamp > 0")
        qry.bind(retention_timeout=now() - 30)
        processed_size = run_all(qry, process)
        logging.info("Processed %s timedout ServiceAPICallback" % processed_size)
