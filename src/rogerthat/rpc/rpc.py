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
from random import choice
import threading
import time
import traceback
from types import NoneType
import types
import uuid

from rogerthat.consts import FAST_QUEUE
from rogerthat.dal.rpc_call import get_rpc_capi_backlog_parent_by_account, get_rpc_capi_backlog_parent_by_mobile
from rogerthat.models import UserProfile
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile, RpcAPIResult, RpcCAPICall, \
    OutStandingGCMKick
from rogerthat.settings import get_server_settings
from rogerthat.to.system import LogErrorRequestTO
from rogerthat.utils import now, azzert
from rogerthat.utils.crypto import encrypt_for_jabber_cloud, decrypt_from_jabber_cloud
from rogerthat.utils.transactions import on_trans_committed
from concurrent import futures  # @UnresolvedImport
from google.appengine.api import urlfetch, memcache
from google.appengine.api.app_identity.app_identity import get_application_id
from google.appengine.ext import db, deferred
from mcfw.cache import set_cache_key
from mcfw.consts import MISSING
from mcfw.rpc import arguments, returns, check_function_metadata, get_parameter_types, run, get_parameters, \
    get_type_details, serialize_value, parse_parameter

_CALL_ACTION_RESEND = 1
_CALL_ACTION_MUST_PROCESS = 2
_CALL_ACTION_DO_NOT_PROCESS = 3

BACKLOG_CONCURRENCY_PROTECTION_INTERVAL = 120
MESSAGE_LINGER_INTERVAL = 3600 * 24 * 20  # 20 days
MESSAGE_ALLOWED_FUTURE_TIME_INTERVAL = 3600 * 24
BACKLOG_MESSAGE_RETENTION_INTERVAL = 3600 * 24 + MESSAGE_LINGER_INTERVAL  # 21 days
BACKLOG_DUPLICATE_AVOIDANCE_RETENTION_INTERVAL = 3600 * 24  # 1 day

APPENGINE_APP_ID = get_application_id()
DO_NOT_SAVE_RPCCALL_OBJECTS = "DO_NOT_SAVE_RPCCALL_OBJECTS"
PERFORM_CALLBACK_SYNCHRONOUS = "PERFORM_CALLBACK_SYNCHRONOUS"
SKIP_ACCOUNTS = "SKIP_ACCOUNTS"
MOBILE_ACCOUNT = "MOBILE_ACCOUNT"
DEFER_KICK = "DEFER_KICK"
TARGET_MFR = "TARGET_MFR"
API_VERSION = u"av"
API_DIRECT_PATH_KEY = u"ap"
CALL_ID = u"ci"
FUNCTION = u"f"
PARAMETERS = u"a"
STATUS = u"s"
STATUS_SUCCESS = u"success"
STATUS_FAIL = u"fail"
RESULT = u"r"
ERROR = u"e"
CALL_TIMESTAMP = u"t"
CALL_RESEND_TIMEOUT = 120
DEFAULT_RETENTION = 3600 * 24

MANDATORY_CALL_KEYS_SET = set([PARAMETERS, API_VERSION, CALL_ID, FUNCTION])

SEND_ACK = 1
IGNORE = 2

PRIORITY_NORMAL = 5
PRIORITY_HIGH = 10

DEFAULT_APPLE_PUSH_MESSAGE = base64.encodestring('{"aps":{"content-available":1}}')

CAPI_KEYWORD_ARG_PRIORITY = "_cka_priority_"
CAPI_KEYWORD_ARG_APPLE_PUSH_MESSAGE = "_cka_apple_push_message_"

def _call_rpc(endpoint, payload):
    settings = get_server_settings()
    jabberEndpoint = choice(settings.jabberEndPoints)
    challenge, data = encrypt_for_jabber_cloud(settings.jabberSecret.encode('utf8'), payload)
    response = urlfetch.fetch(url="http://%s/%s" % (jabberEndpoint, endpoint) , \
                             payload=data, method="POST",
                             allow_truncated=False, follow_redirects=False, validate_certificate=False)
    if response.status_code != 200:
        logging.error("Failed to call jabber cloud with the following info:\nendpoint: %s\npayload: %s" % (endpoint, payload))
        raise Exception(response.content)
    decrypt_from_jabber_cloud(settings.jabberSecret.encode('utf8'), challenge, response.content)

def _re_kick_gcm(registration_id):
    pass

class DirectRpcCaller(threading.local):

    def __init__(self):
        self.items = list()

    def append(self, endpoint, payload, headers, response_callback, synchronous=False):
        if synchronous:
            return urlfetch.fetch(url=endpoint,
                           payload=payload, method="POST", headers=headers,
                           allow_truncated=False, follow_redirects=False)
        rpc_item = urlfetch.create_rpc(10, None)
        urlfetch.make_fetch_call(rpc=rpc_item, url=endpoint,
                                 payload=payload, method="POST", headers=headers,
                                 allow_truncated=False, follow_redirects=False)
        self.items.append((rpc_item, endpoint, time.time(), response_callback))

    def finalize(self):
        for rpc_item, endpoint, start_time, response_callback in self.items:
            try:
                check_time = time.time()
                response = rpc_item.get_result()
                response_time = time.time()
                logging.info("DirectRpc - Called %s. Elapsed: %sms, checked after %sms" % (endpoint, int((response_time - start_time) * 1000), int((check_time - start_time) * 1000)))
                logging.debug("HTTP response status %d and content:\n%s" % (response.status_code, response.content.decode('utf8')))
                response_callback(response)
            except:
                logging.warning("Failed to reach %s!" % endpoint, exc_info=1)
        del self.items[:]


class JabberRpcCaller(threading.local):

    def __init__(self, endpoint):
        self.items = list()
        self.endpoint = endpoint

    def append(self, payload):
        settings = get_server_settings()
        jabberEndpoint = choice(settings.jabberEndPoints)
        rpc_item = urlfetch.create_rpc(5, None)
        challenge, data = encrypt_for_jabber_cloud(settings.jabberSecret.encode('utf8'), payload)
        url = "http://%s/%s" % (jabberEndpoint, self.endpoint)
        urlfetch.make_fetch_call(rpc=rpc_item, url=url,
                                 payload=data, method="POST",
                                 allow_truncated=False, follow_redirects=False, validate_certificate=False)
        self.items.append((rpc_item, payload, challenge, time.time(), url))

    def finalize(self):
        settings = get_server_settings()
        for rpc_item, payload, challenge, start_time, url in self.items:
            try:
                check_time = time.time()
                response = rpc_item.get_result()
                response_time = time.time()
                logging.info("JabberRpc - Called %s. Elapsed: %sms, checked after %sms\npayload: %s" % (url, int((response_time - start_time) * 1000), int((check_time - start_time) * 1000), payload))
                if response.status_code != 200:
                    logging.error("Failed to call jabber cloud with the following info:\nendpoint: %s\npayload: %s" % (self.endpoint, payload))
                    raise Exception(response.content)
                decrypt_from_jabber_cloud(settings.jabberSecret.encode('utf8'), challenge, response.content)
            except:
                logging.warn("Failed to reach jabber endpoint on %s, deferring ..." % url)
                deferred.defer(_call_rpc, self.endpoint, payload)
        del self.items[:]

class AndroidGCMKicker(threading.local):

    def __init__(self):
        self.items = list()
        self.outstandingKicks = list()

    def kick(self, registration_id, priority):
        settings = get_server_settings()
        rpc_item = urlfetch.create_rpc(5, None)
        collapse_key = "rogerthat" if priority == PRIORITY_NORMAL else "rogerthat_high_prio"
        registration_ids = [registration_id] if not isinstance(registration_id, list) else registration_id
        data = dict(registration_ids=registration_ids, collapse_key=collapse_key)
        if priority == PRIORITY_NORMAL:
            # There is no guarantee this message will ever reach the device
            # but in order to avoid throtteling of kicks while the user is actively using
            # Rogerthat we add time_to_live = 0
            data['time_to_live'] = 0
            self.outstandingKicks.append((db.get_async(OutStandingGCMKick.createKey(registration_id)), registration_id))
        data = json.dumps(data)
        url = "https://android.googleapis.com/gcm/send"
        urlfetch.make_fetch_call(rpc=rpc_item, url=url,
                                 payload=data, method="POST", headers={'Content-Type':'application/json', 'Authorization': 'key=%s' % settings.gcmKey},
                                 allow_truncated=False, follow_redirects=False, validate_certificate=False)
        self.items.append((rpc_item, time.time(), registration_id))

    def finalize(self):
        new_outstanding_kicks = dict()
        for rpc_item, registration_id in self.outstandingKicks:
            if not rpc_item.get_result():
                new_outstanding_kicks[registration_id] = OutStandingGCMKick(key_name=registration_id, timestamp=now())
        if new_outstanding_kicks:
            rpc_items.append(db.put_async(new_outstanding_kicks.values()), None)
        del self.outstandingKicks[:]
        for rpc_item, start_time, registration_id in self.items:
            try:
                check_time = time.time()
                response = rpc_item.get_result()
                response_time = time.time()
                logging.info("Call to GCM. Elapsed: %sms, checked after %sms" % (int((response_time - start_time) * 1000), int((check_time - start_time) * 1000)))
                if response.status_code != 200:
                    logging.error("Failed to call GCM.")
                    raise Exception(response.content)
            except:
                logging.warn("Failed to reach GCM , deferring ...")
                deferred.defer(_re_kick_gcm, registration_id)
        del self.items[:]

class RpcFinisher(threading.local):

    def __init__(self):
        self.items = list()

    def append(self, rpc_item, defered_func, *args):
        self.items.append((rpc_item, defered_func, args))

    def finalize(self):
        for rpc_item, defered_func, args in self.items:
            try:
                rpc_item.get_result()
            except:
                logging.warn("Rpc failed, defering ...")
                if defered_func:
                    deferred.defer(defered_func, *args)
        del self.items[:]


class ContextFinisher(threading.local):

    def __init__(self):
        self.items = list()
        self._pool = None

    @property
    def pool(self):
        if not self._pool:
            self._pool = futures.ThreadPoolExecutor(max_workers=10)
        return self._pool

    def append(self, future, callback_func, args, kwargs, err_func, synchronous, not_implemented_func,
               not_implemented_func_args):
        self.items.append((future, callback_func, args, kwargs, err_func, synchronous, not_implemented_func,
                           not_implemented_func_args))

    def finalize(self, synchronous_only=False):
        if not self.items:
            return  # skip logging

        logging.info("Finalizing %sfutures...", "synchronous " if synchronous_only else "")

        while True:
            futures_dict = { item[0]: item for item in self.items if not synchronous_only or item[5]}

            if not len(futures_dict):
                break

            for future in futures.as_completed(futures_dict):
                item = futures_dict[future]
                callback_func, args, kwargs, err_func, _, not_implemented_func, not_implemented_func_args = item[1:]
                logging.info("Future is completed: %s", future)
                self.items.remove(item)
                try:
                    exception = future.exception()
                    if exception is None:
                        callback_func(future.result(), *args, **kwargs)
                    elif not_implemented_func and isinstance(exception, NotImplementedError):
                        not_implemented_func(*(list() if not_implemented_func_args is None else not_implemented_func_args))
                    else:
                        err_func(exception)
                except:
                    logging.exception("Caught exception while executing start_in_new_context callback function")


        if self._pool:
            self._pool.shutdown(True)
            self._pool = None
        logging.info("Finalized futures")


kicks = JabberRpcCaller("kick")
gcm = AndroidGCMKicker()
api_callbacks = JabberRpcCaller("callback")
direct_calls = DirectRpcCaller()
start_flows = JabberRpcCaller("start_flow")
rpc_items = RpcFinisher()
context_threads = ContextFinisher()

def wait_for_rpcs():
    context_threads.finalize()
    kicks.finalize()
    api_callbacks.finalize()
    start_flows.finalize()
    direct_calls.finalize()
    gcm.finalize()
    rpc_items.finalize()

class AccessViolationError(Exception):
    pass

def expose(accessibility):

    def wrap(f):
        check_decorations(f)

        def wrapped(*args, **kwargs):
            from rogerthat.dal.profile import get_service_or_user_profile
            profile = get_service_or_user_profile(users.get_current_user())
            if (profile is None or not isinstance(profile, UserProfile)):
                raise AccessViolationError()
            return f(*args, **kwargs)

        set_cache_key(wrapped, f)
        f.meta[u"exposed"] = accessibility
        wrapped.meta.update(f.meta)
        wrapped.__name__ = f.__name__
        wrapped.__module__ = f.__module__
        return wrapped

    return wrap

def _deferred_kick(call_id, payload):
    if not memcache.get("capi_sent_to_phone:%s" % call_id):  # @UndefinedVariable
        kicks.append(payload)
    else:
        logging.info("Skipping kick %s" % call_id)

@arguments(alias=unicode, accept_sub_types=bool, priority=int)
def capi(alias, accept_sub_types=False, priority=PRIORITY_NORMAL):

    def wrap(f):
        check_decorations(f)

        def capied(result_f, error_f, target, *args, **kwargs):
            def _send_client_call(mobile_detail, cc, user, method):
                from rogerthat.rpc.calls import capi_priority_mapping
                now_ = now()
                call_id = unicode(uuid.uuid1())
                cc[CALL_ID] = call_id
                cc[CALL_TIMESTAMP] = now_
                message = json.dumps(cc)
                rpc_capi_call = RpcCAPICall(parent=get_rpc_capi_backlog_parent_by_account(user, mobile_detail.account),
                                            key_name=call_id, timestamp=now_, call=message, \
                                            priority=capi_priority_mapping[cc[FUNCTION]], \
                                            resultFunction=result_f.meta[u"mapping"], \
                                            errorFunction=error_f.meta[u"mapping"], deferredKick=DEFER_KICK in kwargs, method=method)
                if not DO_NOT_SAVE_RPCCALL_OBJECTS in kwargs:
                    rpc_capi_call.put()
                if mobile_detail.type_ in (Mobile.TYPE_IPHONE_HTTP_APNS_KICK, Mobile.TYPE_IPHONE_HTTP_XMPP_KICK,
                                           Mobile.TYPE_ANDROID_HTTP, Mobile.TYPE_WINDOWS_PHONE,
                                           Mobile.TYPE_LEGACY_IPHONE_XMPP, Mobile.TYPE_LEGACY_IPHONE):
                    prio = kwargs.get(CAPI_KEYWORD_ARG_PRIORITY, priority)
                    if mobile_detail.type_ in Mobile.ANDROID_TYPES and mobile_detail.pushId:
                        # Kick via GCM
                        if db.is_in_transaction():
                            on_trans_committed(gcm.kick, mobile_detail.pushId, prio)
                        else:
                            gcm.kick(mobile_detail.pushId, prio)
                    else:
                        # Kick via Jabbercloud
                        type_ = set()
                        if mobile_detail.type_ in {Mobile.TYPE_IPHONE_HTTP_XMPP_KICK, Mobile.TYPE_WINDOWS_PHONE, Mobile.TYPE_LEGACY_IPHONE_XMPP, Mobile.TYPE_LEGACY_IPHONE}.union(Mobile.ANDROID_TYPES):
                            type_.add("xmpp")
                        if mobile_detail.type_ in (Mobile.TYPE_IPHONE_HTTP_APNS_KICK, Mobile.TYPE_LEGACY_IPHONE_XMPP, Mobile.TYPE_LEGACY_IPHONE):
                            type_.add("apns")

                        cbd = dict(r=mobile_detail.account, p=prio, t=list(type_),
                                   kid=str(uuid.uuid4()), a=mobile_detail.app_id)
                        if mobile_detail.pushId:
                            cbd['d'] = mobile_detail.pushId
                            if "apns" in type_:
                                cbd['m'] = kwargs.get(CAPI_KEYWORD_ARG_APPLE_PUSH_MESSAGE, DEFAULT_APPLE_PUSH_MESSAGE)
                        if DEFER_KICK in kwargs:
                            deferred.defer(_deferred_kick, call_id, json.dumps(cbd),
                                           _countdown=2, _transactional=db.is_in_transaction(), _queue=FAST_QUEUE)
                        elif db.is_in_transaction():
                            on_trans_committed(kicks.append, json.dumps(cbd))
                        else:
                            kicks.append(json.dumps(cbd))
                return rpc_capi_call

            def run():
                targets = _validate_capi_call(result_f, error_f, target, alias, f, accept_sub_types=accept_sub_types)
                if not targets:
                    return
                cc = dict()
                cc[API_VERSION] = 1
                cc[FUNCTION] = alias
                cc[PARAMETERS] = dict(map(lambda (arg, type_): (arg, serialize_value(kwargs[arg], *get_type_details(type_))), f.meta["kwarg_types"].iteritems()))
                skippers = kwargs.get(SKIP_ACCOUNTS) or list()
                mobile = kwargs.get(MOBILE_ACCOUNT)
                if mobile:
                    from rogerthat.models.properties.profiles import MobileDetail
                    mobile_detail = MobileDetail()
                    mobile_detail.account = mobile.account
                    mobile_detail.type_ = mobile.type
                    mobile_detail.pushId = mobile.pushId
                    mobile_detail.app_id = mobile.app_id
                    logging.info(u"Sending capi: %s call to %s" % (alias, mobile.user.email()))
                    logging.info(u"Sending to account %s" % mobile_detail.account)
                    yield _send_client_call(mobile_detail, cc, mobile.user, alias)
                else:
                    from rogerthat.dal.profile import get_profile_infos
                    profile_infos = get_profile_infos(targets, allow_none_in_results=True)
                    for profile_info in profile_infos:
                        if not profile_info:
                            continue
                        if profile_info.isServiceIdentity:
                            logging.warn("Not sending capi call to ServiceIdentity (%s)" % profile_info.user.email())
                        else:
                            if profile_info.mobiles is None:
                                logging.info(u"%s does not have mobiles registered" % profile_info.user.email())
                                continue
                            for mobile_detail in profile_info.mobiles:
                                if mobile_detail.account in skippers:
                                    logging.info(u"Skipping account %s " % mobile_detail.account)
                                    continue
                                logging.info(u"Sending capi: %s call to %s, account: %s" % (alias, profile_info.user.email(), mobile_detail.account))
                                yield _send_client_call(mobile_detail, cc, profile_info.user, alias)
            return list(run())

        set_cache_key(capied, f)
        capied.meta.update(f.meta)
        capied.meta['alias'] = alias
        capied.__name__ = f.__name__
        capied.__module__ = f.__module__
        return capied

    return wrap

@arguments(alias=unicode)
def mapping(alias):

    def wrap(f):
        set_cache_key(f, f)
        f.meta[u"mapping"] = alias
        return f

    return wrap

@arguments(call=dict)
def call(call):
    from rogerthat.rpc.calls import low_reliability_calls

    is_low_reliability = call[FUNCTION] in low_reliability_calls
    call_id = call[u"ci"]

    # First check whether we know this call
    mobile_key = users.get_current_mobile().key()
    rpc_api_result = RpcAPIResult.get_by_key_name(call_id, parent=mobile_key) if not is_low_reliability else None

    # If we know the call, just return its result we calculated previously
    if rpc_api_result:
        return rpc_api_result.result, json.loads(rpc_api_result.result)

    # Okay, its a new call, we need to actually execute it!
    now_ = now()
    timestamp = call[CALL_TIMESTAMP] if CALL_TIMESTAMP in call else now_
    result_json, result_dict = _perform_call(call_id, call, timestamp)
    if not is_low_reliability:
        rpc_items.append(db.put_async(RpcAPIResult(parent=mobile_key, key_name=call_id, result=result_json, timestamp=now_)),
                         _store_rpc_api_result_deferred, mobile_key, call_id, result_json, now_)
    return result_json, result_dict

def _store_rpc_api_result_deferred(mobile_key, call_id, result_json, now_):
    RpcAPIResult(parent=mobile_key, key_name=call_id, result=result_json, timestamp=now_).put()

@returns(unicode)
@arguments(result=dict)
def cresult(result):
    from rogerthat.rpc.calls import result_mapping

    # Get the CAPI call from the datastore
    call_id = result[u"ci"]
    mobile = users.get_current_mobile()
    rpc_capi_call = RpcCAPICall.get_by_key_name(call_id, parent=get_rpc_capi_backlog_parent_by_mobile(mobile))

    # If we can't find it, we just return its call_id, so the remote party can cleanup its backlog
    if not rpc_capi_call:
        return call_id

    # Found it, now execute the callback result or error function
    try:
        if result[STATUS] == STATUS_SUCCESS:
            result_mapping[rpc_capi_call.resultFunction](context=rpc_capi_call, result=parse_parameter(u"result", result_mapping[rpc_capi_call.resultFunction].meta[u"kwarg_types"][u"result"], result[RESULT]))
        else:
            result_mapping[rpc_capi_call.errorFunction](context=rpc_capi_call, error=result[ERROR])
    except Exception, e:
        logging.error("Failed processing result handler!\nResult: %s\nException: %s\nBacktrace: %s" \
                      % (result, unicode(e), traceback.format_exc()))
    finally:
        rpc_capi_call.delete()

    return call_id

@returns(types.NoneType)
@arguments(call_id=unicode)
def ack(call_id):
    mobile = users.get_current_mobile()
    db.delete(db.Key.from_path(RpcAPIResult.kind(), call_id, parent=mobile.key()))

@arguments(call_ids=[unicode])
def ack_all(call_ids):
    if not call_ids:
        return

    mobile_key = users.get_current_mobile().key()
    rpc_items.append(db.delete_async([db.Key.from_path(RpcAPIResult.kind(), call_id, parent=mobile_key) for call_id in call_ids]),
                     _ack_all_deferred, mobile_key, call_ids)

def _ack_all_deferred(mobile_key, call_ids):
    db.delete_async([db.Key.from_path(RpcAPIResult.kind(), call_id, parent=mobile_key) for call_id in call_ids])

@mapping('com.mobicage.rpc.dismiss_error')
@returns(NoneType)
@arguments(context=RpcCAPICall, error=(str, unicode))
def dismissError(context, error):
    pass

@mapping('com.mobicage.rpc.error')
@returns(NoneType)
@arguments(context=RpcCAPICall, error=(str, unicode))
def logError(context, error):
    from rogerthat.models import MobileSettings
    mobile = context.mobile()
    settings = MobileSettings.get(mobile)

    ler = LogErrorRequestTO()
    ler.mobicageVersion = u"%s.%s" % (settings.majorVersion, settings.minorVersion)
    ler.platform = mobile.type
    ler.platformVersion = u""
    ler.errorMessage = error
    ler.description = u"Error returned as result of client call:\n" + context.call
    ler.timestamp = int(time.time())

    from rogerthat.bizz.system import logErrorBizz
    logErrorBizz(ler, users.get_current_user())

def _validate_capi_call(result_f, error_f, target, alias, f, accept_sub_types=False):
    def raise_invalid_target():
        raise ValueError("Target argument should be of type google.appengine.api.users.User or [google.appengine.api.users.User].\nGot %s instead" % (type(target)))

    check_decorations(result_f)
    check_decorations(error_f)
    funcs = result_f, error_f
    from rogerthat.rpc.calls import result_mapping
    if any(filter(lambda fn: "mapping" not in fn.meta or fn.meta["mapping"] not in result_mapping, funcs)):
        raise ValueError("Result and error processing functions must have their mapping declared in rogerthat.rpc.calls.result_mapping!")
    if any(filter(lambda fn: fn.meta["return_type"] != NoneType, funcs)):
        raise ValueError("Result and error processing functions cannot have return types.")
    if any(filter(lambda fn: "context" not in fn.meta["kwarg_types"] or fn.meta["kwarg_types"]["context"] != RpcCAPICall, funcs)):
        raise ValueError("Result and error processing functions must have a arg 'context' of type rogerthat.rpc.models.RpcCAPICall.")
    if any(filter(lambda fn:len(fn.meta["kwarg_types"]) != 2, funcs)):
        raise ValueError("Result and error processing functions must have 2 arguments!")
    if not accept_sub_types and f.meta["return_type"] != result_f.meta["kwarg_types"]["result"]:
        raise ValueError("Return value type and result function result argument types do not match!")
    if accept_sub_types and not issubclass(f.meta["return_type"], result_f.meta["kwarg_types"]["result"]):
        raise ValueError("Return value type and result function result argument types do not match!")
    islist = False
    if not isinstance(target, (users.User, NoneType)):
        islist = True
        if not isinstance(target, (list, set)):
            raise_invalid_target()
        if any((not isinstance(m, (users.User, NoneType)) for m in target)):
            raise_invalid_target()
    from rogerthat.rpc.calls import client_mapping
    if not alias in client_mapping:
        raise ValueError("Function is not present in client_mapping")
    if not "error" in error_f.meta["kwarg_types"] or error_f.meta["kwarg_types"]["error"] in (str, unicode):
        raise ValueError("Error function must have an error parameter of type string.")
    return filter(lambda x: x, target) if islist else ([target] if target else [])

def check_decorations(f):
    if not hasattr(f, "meta") or "return_type" not in f.meta or "kwarg_types" not in f.meta:
        raise ValueError("Function needs to be decorated with argument and return types")


def _get_function(name):
    from rogerthat.rpc.calls import mapping
    if not name in mapping:
        raise NameError("Unknown function")
    else:
        return mapping[name]

def parse_and_validate_request(call):
    api_version = call[API_VERSION]
    if api_version != 1:
        raise ValueError("Incompatible API-version!")
    if not MANDATORY_CALL_KEYS_SET.issubset(set(call.keys())):
        raise ValueError("Protocol error: Unrecognized request!")
    callid = call[CALL_ID]
    try:
        function = _get_function(call[FUNCTION])
    except NameError:
        return api_version, callid, None, None
    if not hasattr(function, "meta") \
            or not "exposed" in function.meta \
            or not "api" in function.meta["exposed"]:
        raise ValueError("Function does not exist!")
    parameters = call[PARAMETERS]
    return api_version, callid, function, parameters

def _perform_call(callId, request_json, timestamp):
    api_version, callid, function, parameters = parse_and_validate_request(request_json)
    if not function:
        result = {
            CALL_ID: callId,
            API_VERSION: api_version,
            ERROR: "Unknown function call!",
            STATUS: STATUS_FAIL,
            CALL_TIMESTAMP: timestamp}
        return json.dumps(result), result
    azzert(callid == callId)
    result = dict()
    result[CALL_ID] = callid
    result[API_VERSION] = api_version
    result[CALL_TIMESTAMP] = timestamp
    try:
        check_function_metadata(function)
        kwarg_types = get_parameter_types(function)
        kwargs = get_parameters(parameters, kwarg_types)
        for key in set(kwarg_types.keys()) - set(kwargs.keys()):
            kwargs[key] = MISSING
        result[RESULT] = run(function, kwargs)
        result[STATUS] = STATUS_SUCCESS
        return json.dumps(result), result
    except Exception, e:
        result[ERROR] = unicode(e)
        result[STATUS] = STATUS_FAIL
        from rogerthat.rpc.service import ServiceApiException, ApiWarning
        if isinstance(e, (ServiceApiException, ApiWarning)):
            loglevel = logging.WARNING
        else:
            loglevel = logging.ERROR
        logging.log(loglevel, "Error while executing %s: %s" % (function.__name__, traceback.format_exc()))
        return json.dumps(result), result
