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

import base64
import json
import logging
import time

from google.appengine.api import memcache
from google.appengine.ext import webapp, db

from rogerthat.consts import MAX_RPC_SIZE, DEBUG, APPSCALE
from rogerthat.dal.rpc_call import get_limited_backlog, get_filtered_backlog
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile, OutStandingGCMKick
from rogerthat.rpc.rpc import API_VERSION, call, cresult, API_DIRECT_PATH_KEY, ack_all, wait_for_rpcs, \
    parse_and_validate_request, CALL_ID, ERROR, STATUS, CALL_TIMESTAMP, STATUS_FAIL, APPENGINE_APP_ID, \
    rpc_items
from rogerthat.settings import get_server_settings
from rogerthat.utils import foreach, now, azzert, offload, \
    OFFLOAD_TYPE_APP


class JSONRPCRequestHandler(webapp.RequestHandler):
    def post(self):
        if not self.set_user():
            self.response.set_status(500)
            return
        try:
            body = self.request.body
            json_result = process(body)

            self.response.headers['Content-Type'] = 'application/json-rpc'
            self.response.out.write(json_result)
        finally:
            users.clear_user()

    def set_user(self):
        user = self.request.headers.get("X-MCTracker-User", None)
        password = self.request.headers.get("X-MCTracker-Pass", None)
        if not user or not password:
            return False
        return users.set_json_rpc_user(base64.decodestring(user), base64.decodestring(password))


def process(body):
    try:
        request = json.loads(body)
    except:
        logging.warn(body)
        raise
    mobile = users.get_current_mobile()
    jid = mobile.account

    memcache_rpc = memcache.Client().set_multi_async(
        {"last_user_heart_beat_%s" % users.get_current_user().email(): now()})

    logging.info("Incoming HTTP call from %s", jid)

    azzert(request[API_VERSION] == 1)
    responses = list()
    acks = list()
    calls = list()

    starttime = now()

    timeToStartFlushing = lambda: now() - starttime > 15

    sizes = list()

    def processResult(r):
        users.set_backlog_item(r)
        try:
            ack = cresult(r)
            acks.append(ack)
            sizes.append(len(ack))
        finally:
            users.set_backlog_item(None)

    def processCall(c):
        users.set_backlog_item(c)
        try:
            if mobile.is_phone_unregistered:
                # Do not process calls coming from an unregistered app.
                api_version, callid, _, _ = parse_and_validate_request(c)
                timestamp = c[CALL_TIMESTAMP] if CALL_TIMESTAMP in c else now()
                result = {
                    CALL_ID: callid,
                    API_VERSION: api_version,
                    ERROR: "Unknown function call!",
                    STATUS: STATUS_FAIL,
                    CALL_TIMESTAMP: timestamp}
            else:
                result = call(c)
                if not result:
                    return
                _, result = result
            responses.append(result)
            sizes.append(len(json.dumps(result)))
        finally:
            users.set_backlog_item(None)

    def stream():
        ack_all(request.get(u"a", []))
        for r in request.get(u"r", []):
            yield processResult, r
            if timeToStartFlushing() or sum(sizes) > MAX_RPC_SIZE:
                return
        for c in request.get(u"c", []):
            yield processCall, c
            if timeToStartFlushing() or sum(sizes) > MAX_RPC_SIZE:
                return

    foreach(lambda (f, a): f(a), stream())

    if not DEBUG:
        wait_for_rpcs()

    if mobile.type in Mobile.ANDROID_TYPES and mobile.pushId:
        rpc_items.append(db.delete_async(OutStandingGCMKick.createKey(mobile.pushId)), None)

    more = False
    if sum(sizes) > MAX_RPC_SIZE:
        more = True
    else:
        count = 0
        deferred_kicks = list()

        while True:
            if mobile.is_phone_unregistered:
                memcache_key = "unregistered" + str(mobile.key())
                if memcache.get(memcache_key):  # @UndefinedVariable
                    logging.debug("send empty result to give the phone the chance to finish unregistering")
                    break
                logging.debug("%s (user: %s. status: %s) should unregister itself. "
                              "Close the communication channel via only allowing the Unregister Call",
                              mobile.account, mobile.user, mobile.status)
                qry = get_filtered_backlog(mobile, "com.mobicage.capi.system.unregisterMobile")
            else:
                # Stream the backlog as normal
                qry = get_limited_backlog(mobile, 21)
            for b in qry:
                count += 1
                calls.append(json.loads(b.call))
                sizes.append(len(b.call))
                if b.deferredKick:
                    deferred_kicks.append(b.key().name())
                if sum(sizes) > MAX_RPC_SIZE:
                    more = True
                    break
            if mobile.is_phone_unregistered:
                if not calls:
                    logging.debug("No unregister calls found in the backlog, re-add it.")
                    from rogerthat.bizz.system import unregister_mobile
                    unregister_mobile(users.get_current_user(), mobile)
                    time.sleep(2)  # Make sure when the query runs again, we will get results
                else:
                    memcache.set(memcache_key, "call sent", 60)  # @UndefinedVariable
                    break
            else:
                break

        if count == 21:
            calls.pop()
            more = True
        memcache_stuff = dict()
        for c in calls:
            call_id = c["ci"]
            if call_id in deferred_kicks:
                memcache_stuff["capi_sent_to_phone:%s" % call_id] = True
        if memcache_stuff:
            memcache.set_multi(memcache_stuff, 10)  # @UndefinedVariable

    result = dict()
    result[API_VERSION] = 1
    no_api_direct_path = DEBUG or APPSCALE or users.get_current_app_id() == 'em-be-roi-booster'  # hard-coded for now
    result[
        API_DIRECT_PATH_KEY] = "%s/json-rpc" % get_server_settings().baseUrl if no_api_direct_path else u"https://%s.appspot.com/json-rpc" % APPENGINE_APP_ID
    if responses:
        result[u"r"] = responses
    if acks:
        result[u"a"] = acks
    if calls:
        result[u"c"] = calls
    result[u"more"] = more
    result[u"t"] = now()

    memcache_rpc.get_result()

    offload(users.get_current_user(), OFFLOAD_TYPE_APP, request, result)
    return json.dumps(result)
