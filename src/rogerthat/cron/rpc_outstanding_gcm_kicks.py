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

from rogerthat.rpc.models import OutStandingGCMKick
from rogerthat.rpc.rpc import gcm, PRIORITY_HIGH
from rogerthat.utils import now
from google.appengine.ext import webapp, deferred, db


class Reschedule(webapp.RequestHandler):
    
    def get(self):
        purge_timestamp = now()
        deferred.defer(kick, purge_timestamp)
            
def kick(from_):     
    logging.info("Getting outstanding kicks from datastore")       
    outstanding_kicks = OutStandingGCMKick.all(keys_only=True).filter("timestamp <=", from_ - 300).order("timestamp")
    results = outstanding_kicks.fetch(1000)
    if not results:
        return
    logging.info("Bulk kicking registration_ids")       
    registration_ids = list()
    for key in results:
        registration_ids.append(key.name())
    gcm.kick(registration_ids, PRIORITY_HIGH)
    db.delete(results)
    logging.info("Continue in 5 seconds ...")       
    deferred.defer(kick, from_, _countdown=5)
