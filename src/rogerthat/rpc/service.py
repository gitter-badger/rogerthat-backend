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

from copy import deepcopy
import inspect
import json
import logging
import os
import threading
import time
from types import NoneType
from urlparse import urlparse
import uuid

from rogerthat.consts import SERVICE_API_CALLBACK_RETRY_UNIT, DEBUG, APPSCALE
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.service import get_sik, get_api_key, log_service_activity
from rogerthat.models import SIKKey, ServiceProfile
from rogerthat.rpc import users, rpc
from rogerthat.rpc.models import ServiceAPIResult, ServiceAPICallback, ServiceLog
from rogerthat.rpc.rpc import check_decorations, DO_NOT_SAVE_RPCCALL_OBJECTS, mapping, APPENGINE_APP_ID, TARGET_MFR, \
    PERFORM_CALLBACK_SYNCHRONOUS
from rogerthat.utils import now, privatize, channel, azzert, try_or_defer, \
    offload, OFFLOAD_TYPE_API, OFFLOAD_TYPE_CALLBACK_API
from rogerthat.utils.transactions import run_after_transaction
from google.appengine.ext import webapp, db
from google.appengine.ext.deferred.deferred import PermanentTaskFailure
from mcfw.cache import set_cache_key
from mcfw.consts import MISSING
from mcfw.rpc import arguments, serialize_value, get_type_details, parse_parameter, run, parse_parameters, returns, \
    MissingArgumentException
from rogerthat.rpc.solutions import solution_supports_api_callback

ERROR_CODE_WARNING_THRESHOLD = 2000  # ServiceApiException errorcode >= 2000 is warning log on server

ERROR_CODE_UNKNOWN_ERROR = 1000
ERROR_CODE_MISSING_ARGUMENT = 1001
ERROR_CODE_NOT_ENABLED = 1002
ERROR_CODE_INCOMPLETE_REQUEST = 1003
ERROR_CODE_JSONRPCID_NOT_STRING = 1004
ERROR_CODE_INVALID_JSON_TYPE = 1005
ERROR_CODE_METHOD_NOT_FOUND = 1006
ERROR_CODE_INVALID_JSON = 1007
ERROR_CODE_INVALID_CALLBACK = 1008  # Error on request which is piggybacked on response
ERROR_CODE_PREVIOUS_CALL_ATTEMPT_STILL_RUNNING = 1009

if DEBUG:
    POST_BACK = "http://%s:%s/api/1/callback" % (os.environ['SERVER_NAME'], os.environ['SERVER_PORT'])
else:
    if APPSCALE:
        POST_BACK = "https://%s/api/1/callback" % os.environ['SERVER_NAME']
    else:
        POST_BACK = "https://%s.appspot.com/api/1/callback" % APPENGINE_APP_ID

_service_api_calls = dict()
SERVICE_API_CALLBACK_MAPPING = dict()

@mapping('com.mobicage.rpc.error')
@returns(NoneType)
@arguments(context=ServiceAPICallback, error=(str, unicode))
def logServiceError(context, error):
    logging.info("Service api call resulted in error.")
    if context.targetMFR:
        logging.error(error)

def register_service_api_calls(module):
    for f in (function for (name, function) in inspect.getmembers(module, lambda x: inspect.isfunction(x))):
        if hasattr(f, 'meta') and "service_api" in f.meta and f.meta["service_api"]:
            _service_api_calls[f.meta["function"]] = f

def get_service_api_calls(module):
    result = dict()
    for f in (function for (name, function) in inspect.getmembers(module, lambda x: inspect.isfunction(x))):
        if hasattr(f, 'meta') and "service_api" in f.meta and f.meta["service_api"]:
            result[f.meta['function']] = f
    return result

@arguments(function=unicode, code=int)
def service_api_callback(function, code):
    from rogerthat.dal import parent_key
    SERVICE_API_CALLBACK_MAPPING[function] = code

    def wrap(f):
        check_decorations(f)

        def capied(result_f, error_f, profile, *args, **kwargs):
            synchronous = kwargs.get(PERFORM_CALLBACK_SYNCHRONOUS, False)
            if not synchronous:
                _validate_api_callback(result_f, error_f, profile, function, f)
            cc = dict()
            cc["method"] = function

            default_arg_values = f.meta['fargs'].defaults
            if default_arg_values:
                args_with_defaults = f.meta['fargs'].args[-len(default_arg_values):]
                effective_kwargs = dict(zip(args_with_defaults, default_arg_values))
                effective_kwargs.update(kwargs)
            else:
                effective_kwargs = kwargs

            target_mfr = TARGET_MFR in kwargs
            is_solution = True if profile.solution else False

            if code:  # code 0 is test.test
                if target_mfr:
                    if code == ServiceProfile.CALLBACK_MESSAGING_RECEIVED:
                        return
                else:
                    if is_solution:
                        if not solution_supports_api_callback(profile.solution, code) and profile.callBackURI == "mobidick":
                            logging.debug('callback %s is not implemented for solution %s', code, profile.user)
                            return
                    else:
                        if not profile.callbackEnabled(code):
                            logging.debug('callback %s is not enabled for %s', code, profile.user)
                            return

            cc["params"] = dict(map(lambda (arg, type_): (arg, serialize_value(effective_kwargs[arg], *get_type_details(type_))), f.meta["kwarg_types"].iteritems()))

            now_ = now()
            callId = unicode(uuid.uuid1())
            cc["id"] = callId
            message = json.dumps(cc)
            timestamp = (now_ + SERVICE_API_CALLBACK_RETRY_UNIT) * 1 if profile.enabled else -1
            service_api_callback = ServiceAPICallback(parent_key(profile.user), callId, call=message, \
                timestamp=timestamp, resultFunction=result_f.meta[u"mapping"] if result_f else None, errorFunction=error_f.meta[u"mapping"] if error_f else None,
                targetMFR=target_mfr, monitor=bool(profile.monitor), code=code,
                is_solution=is_solution)
            if 'service_identity' in kwargs:
                azzert(kwargs['service_identity'], 'service_identity should not be None')
                service_api_callback.internal_service_identity = kwargs['service_identity']
            if synchronous:
                return submit_service_api_callback(profile, service_api_callback, effective_kwargs, function, synchronous, call_dict=cc, response_type=f.meta[u'return_type'])
            if not DO_NOT_SAVE_RPCCALL_OBJECTS in kwargs:
                service_api_callback.put()
            if profile.enabled or profile.solution or target_mfr or function == "test.test":
                submit_service_api_callback(profile, service_api_callback, effective_kwargs, function, call_dict=cc, response_type=f.meta[u'return_type'])
            return service_api_callback


        set_cache_key(capied, f)
        capied.meta.update(f.meta)
        capied.__name__ = f.__name__
        return capied

    return wrap

def _send_to_solution_context(service_api_callback, profile, effective_kwargs, function, synchronous, call_dict, response_type):
    if None in (effective_kwargs, function, response_type):
        logging.critical("Received retry of solution callback: %s (%s)", service_api_callback.code,
                         profile.user.email(), _suppress=False)
        service_api_callback.delete()
        return

    from rogerthat.rpc.calls import service_callback_result_mapping
    from rogerthat.rpc.context import start_in_new_context
    from solutions import handle_solution_api_callback

    if synchronous:
        done = threading.Event()

    result = dict()

    def process_result(response):
        offload(profile.user, OFFLOAD_TYPE_CALLBACK_API, call_dict,
                serialize_value(response, *get_type_details(response_type)),
                function, True)
        if synchronous:
            result['success'] = True
            result['result'] = response
            done.set()
            return
        service_callback_result_mapping[service_api_callback.resultFunction](context=service_api_callback, result=response)

    def process_error(error):
        offload(profile.user, OFFLOAD_TYPE_CALLBACK_API, call_dict,
                unicode(error), function, False)
        if synchronous:
            result['success'] = False
            result['error'] = error
            done.set()
            return
        service_callback_result_mapping[service_api_callback.errorFunction](context=service_api_callback, error=str(error))

    def process_not_implemented():
        if profile.callBackURI == "mobidick":
            process_result(None)
            return
        service_api_callback.is_solution = False
        service_api_callback.put()
        submit_service_api_callback(profile, service_api_callback, effective_kwargs, function, synchronous, call_dict,
                                    response_type)

    logging.info("Starting in new context: %s.%s\n%s" % (profile.solution, function, service_api_callback.call))
    start_in_new_context(handle_solution_api_callback,
                         [profile.service_user, profile.solution, service_api_callback.code, effective_kwargs],
                         dict(),
                         process_result,
                         list(),
                         dict(),
                         process_error,
                         synchronous,
                         not_implemented_func=process_not_implemented)
    if synchronous:
        rpc.context_threads.finalize(synchronous_only=True)
        done.wait()
        if result['success']:
            return result['result']
        else:
            raise result['error']

@run_after_transaction
@arguments(profile=ServiceProfile, service_api_callback=ServiceAPICallback, effective_kwargs=dict, function=unicode,
           synchronous=bool, call_dict=dict, response_type=type)
def submit_service_api_callback(profile, service_api_callback, effective_kwargs=None, function=None, synchronous=False,
                                call_dict=None, response_type=None):
    if service_api_callback.is_solution and not service_api_callback.targetMFR:
        result = _send_to_solution_context(service_api_callback, profile, effective_kwargs, function, synchronous,
                                           call_dict, response_type)
        if synchronous:
            return result
        return True, None

    from rogerthat.settings import get_server_settings
    from rogerthat.bizz.service import get_mfr_sik
    settings = get_server_settings()
    mfr_uri = "%s/callback_api" % settings.messageFlowRunnerAddress
    mobidick_uri = "%s/callback_api" % settings.mobidickAddress
    if service_api_callback.targetMFR:
        sik = get_mfr_sik(profile.user).sik
        return_sik = profile.sik
        method = "http"
        uri = mfr_uri
    else:
        method = "xmpp" if profile.callBackJid else "http"
        if method == "http" and profile.callBackURI == "mobidick":
            uri = mobidick_uri
        else:
            uri = profile.callBackJid if profile.callBackJid else profile.callBackURI
        sik = profile.sik
        return_sik = sik
    logging.info("Sending callback to %s, identifying through sik %s over %s @ %s:\n%s" \
                 % (profile.user, sik, method, uri, service_api_callback.call))
    if not (uri and sik):
        logging.error("Not enough information present to send the call!")
        return False, "Not enough information present to send the call!"

    if (APPSCALE and method == "http") \
            or uri in (mfr_uri, mobidick_uri) \
            or uri.startswith(settings.mobidickAddress) \
            or (method == "http" and urlparse(uri).hostname.endswith('.appspot.com')) \
            or synchronous:
        result = _send_directly(service_api_callback, profile, uri, synchronous)
        if synchronous:
            return result
    else:
        cbd = dict(p=method, r=uri, s=sik, rs=return_sik, c=unicode(service_api_callback.call), b=POST_BACK)
        rpc.api_callbacks.append(json.dumps(cbd))
    return True, None

def service_api(function, cache_result=True, available_when_disabled=False, silent_result=False):

    def wrap(f):
        if not inspect.isfunction(f):
            raise ValueError("f is not of type function!")

        arg_spec = f.meta[u'fargs']
        kwarg_types = f.meta[u"kwarg_types"]
        return_type = f.meta[u"return_type"]

        def wrapped(*args, **kwargs):
            request_data = dict()
            for i in xrange(len(args)):
                arg = arg_spec.args[i]
                request_data[arg] = serialize_value(args[i], *get_type_details(kwarg_types[arg]), skip_missing=True)
            for arg, value in kwargs.iteritems():
                if arg == 'accept_missing':
                    continue
                if value == MISSING:
                    continue
                request_data[arg] = serialize_value(value, *get_type_details(kwarg_types[arg]), skip_missing=True)
            try:
                result = f(*args, **kwargs)
                response_data = None if silent_result else serialize_value(result, *get_type_details(return_type))
                offload(users.get_current_user(), OFFLOAD_TYPE_API, request_data, response_data, function, True)
                return result
            except:
                offload(users.get_current_user(), OFFLOAD_TYPE_API, request_data, None, function, False)
                raise

        wrapped.__name__ = f.__name__
        wrapped.meta = {"service_api": True,
                        "function": function,
                        "cache_result": cache_result,
                        "available_when_disabled": available_when_disabled,
                        "silent_result": silent_result}
        if hasattr(f, "meta"):
            wrapped.meta.update(f.meta)
        return wrapped

    return wrap


class ApiWarning(PermanentTaskFailure):
    pass

class BusinessException(PermanentTaskFailure):
    pass

class ServiceApiException(BusinessException):
    BASE_CODE_TEST = 2000
    BASE_CODE_BRANDING = 10000
    BASE_CODE_FRIEND = 20000
    BASE_CODE_MESSAGE = 30000
    BASE_CODE_MESSAGE_FLOW = 40000
    BASE_CODE_QR = 50000
    BASE_CODE_SERVICE = 60000
    BASE_CODE_APP = 70000
    BASE_CODE_LOCATION = 80000
    BASE_CODE_SOLUTIONS = 200000

    def __init__(self, code, message, **kwargs):
        super(ServiceApiException, self).__init__(message)
        self.code = code
        self._message = message
        self.fields = kwargs

    def __unicode__(self):
        return unicode(self._message)

class ServiceApiHandlerBase(webapp.RequestHandler):

    def authenticate_request(self):
        ak = self.request.headers.get('X-Nuntiuz-API-Key', None) or self.request.get('X-Nuntiuz-API-Key', None)
        if not ak:
            self.response.set_status(401, "Missing X-Nuntiuz-API-Key, cannot authenticate!")
            return None
        aki = get_api_key(ak)
        if not aki:
            self.response.set_status(401, "Could not match %s to a service account!" % ak)
            return None
        logging.info("Authenticated %s as %s" % (ak, aki.user))
        if aki.mfr:
            logging.info("Executed by message flow engine.")
        users.set_user(aki.user, mfr=aki.mfr == True)
        return aki

class ServiceApiHandler(ServiceApiHandlerBase):

    def post(self):
        aki = self.authenticate_request()
        if not aki:
            return

        if self.request.headers.get('Content-Type', "").startswith('application/json-rpc'):
            request_json = self.request.body
        else:
            request_json = self.request.POST['data']

        if not isinstance(request_json, unicode):
            request_json = request_json.decode('utf-8')

        try:
            result_json, method, id_, log_service_call, error_code, error_message, _ = process_service_api_call(request_json, aki)
        except:
            from rogerthat.settings import get_server_settings
            server_settings = get_server_settings()
            erroruuid = str(uuid.uuid4())
            logging.exception("Unknown exception occurred: error id %s" % erroruuid)
            error_code = ERROR_CODE_UNKNOWN_ERROR
            error_message = 'An unknown error occurred. Please contact %sand mention error id %s' % (server_settings.supportEmail, erroruuid)
            log_service_activity(users.get_current_user(), str(uuid.uuid4()), ServiceLog.TYPE_CALL, \
                                 ServiceLog.STATUS_ERROR, None, request_json, None, error_code, error_message)
            return

        self.response.headers['Content-Type'] = 'application/json-rpc; charset=utf-8'
        if result_json:
            self.response.out.write(result_json)

        if log_service_call:
            log_service_activity(users.get_current_user(), id_, ServiceLog.TYPE_CALL,
                                 ServiceLog.STATUS_SUCCESS if error_code == 0 else ServiceLog.STATUS_ERROR,
                                 method, request_json, result_json, error_code, error_message)

        if error_code != 0:
            service_profile = get_service_profile(aki.user)
            from rogerthat.bizz import monitoring
            monitoring.log_service_api_failure(service_profile, monitoring.SERVICE_API_CALL)

def process_service_api_call(request_json, aki):
    result_json, method, id_, log_service_call, cache_result, error_code, error_message, from_cache = _execute_service_api_call(request_json, aki)

    if cache_result:
        ServiceAPIResult(key=ServiceAPIResult.create_key(aki.user, id_), result=result_json, timestamp=now(), running=False).put()

    return result_json, method, id_, log_service_call, error_code, error_message, from_cache

def _execute_service_api_call(request_json, aki):
    call = json.loads(request_json)
    logging.info("Incoming service api call: " + json.dumps(privatize(deepcopy(call))))
    log_service_call = not aki.mfr
    id_ = call.get("id", None)
    params = call.get("params", None)
    method = call.get("method", None)

    cache_result = False

    error_code = 0
    error_message = None

    if id_ == None or params == None or method == None:
        logging.error("Incomplete request %s" % json.dumps(call))
        error_code = ERROR_CODE_INCOMPLETE_REQUEST
        error_message = 'Incomplete call request. id, method, params are required fields!'
        result = {'id': id_, 'result': None, 'error': {'code': error_code, 'message': error_message}}
        return json.dumps(result), None, id_, log_service_call, cache_result, error_code, error_message, False

    if not isinstance(id_, (str, unicode)):
        logging.error("Incorrect request %s" % json.dumps(call))
        error_code = ERROR_CODE_JSONRPCID_NOT_STRING
        error_message = 'id should be a string (the JSON-RPC id)!'
        result = {'id': id_, 'result': None, 'error': {'code': error_code, 'message': error_message}}
        return json.dumps(result), None, id_, log_service_call, cache_result, error_code, error_message, False

    if not isinstance(params, dict):
        logging.error("Incorrect request %s" % json.dumps(call))
        error_code = ERROR_CODE_INVALID_JSON_TYPE
        error_message = 'Params should be a json object.'
        result = {'id': id_, 'result': None, 'error': {'code': error_code, 'message': error_message}}
        return json.dumps(result), None, id_, log_service_call, cache_result, error_code, error_message, False

    if not method in _service_api_calls:
        error_code = ERROR_CODE_METHOD_NOT_FOUND
        error_message = 'Method not found.'
        result = {'id': id_, 'result': None, 'error': {'code': error_code, 'message': error_message}}
        return json.dumps(result), None, id_, log_service_call, cache_result, error_code, error_message, False

    f = _service_api_calls[method]

    cache_result = f.meta['cache_result']
    service_api_result_running = None
    try:
        if cache_result:
            service_api_result = db.get(ServiceAPIResult.create_key(aki.user, id_))
            if service_api_result:
                if service_api_result.running:
                    error_code = ERROR_CODE_PREVIOUS_CALL_ATTEMPT_STILL_RUNNING
                    error_message = 'Previous request attempt still running'
                    result = {'id': id_, 'result': None, 'error': {'code': error_code, 'message': error_message}}
                    return json.dumps(result), None, id_, log_service_call, False, error_code, error_message, False
                else:
                    result = json.loads(service_api_result.result)
                    error = result.get("error")
                    if error:
                        error_code = error["code"]
                        error_message = error["message"]
                    return service_api_result.result, method, id_, log_service_call, cache_result, error_code, error_message, True
            else:
                service_api_result_running = ServiceAPIResult(key=ServiceAPIResult.create_key(aki.user, id_),
                                                              timestamp=now(), running=True)
                service_api_result_running.put()

        if method == u"messaging.mfr_flow_member_result":
            log_service_call = False

        available_when_disabled = f.meta['available_when_disabled']

        try:
            service_profile = get_service_profile(aki.user)
            if aki.mfr or service_profile.enabled or available_when_disabled:
                r = run(f, parse_parameters(f, params))
                result = {'id':id_, 'result': r, 'error': None}
            else:
                error_code = ERROR_CODE_NOT_ENABLED
                error_message = 'Service api not enabled!'
                error = {'code':error_code, 'message':error_message}
                result = {'id':id_, 'result': None, 'error': error}
        except MissingArgumentException, mae:
            logging.warning("Missing argument exception occurred", exc_info=1)
            error_code = ERROR_CODE_MISSING_ARGUMENT
            error_message = mae.message
            error = {'code':error_code, 'message':error_message, 'name': mae.name}
            result = {'id':id_, 'result': None, 'error': error}
        except ServiceApiException, sae:
            if (sae.code >= ERROR_CODE_WARNING_THRESHOLD):
                logging.warning("Service api exception occurred", exc_info=1)
            else:
                logging.exception("Severe Service API Exception")
            error_code = sae.code
            error_message = sae.message
            error = {'code':error_code, 'message':error_message}
            error.update(sae.fields)
            result = {'id':id_, 'result': None, 'error': error}
        except:
            from rogerthat.settings import get_server_settings
            server_settings = get_server_settings()
            erroruuid = str(uuid.uuid4())
            logging.exception("Unknown exception occurred: error id %s" % erroruuid)
            error_code = ERROR_CODE_UNKNOWN_ERROR
            error_message = 'An unknown error occurred. Please contact %s and mention error id %s' % (server_settings.supportEmail, erroruuid)
            error = {'code':error_code, 'message':error_message}
            result = {'id':id_, 'result': None, 'error': error}
    except:
        if service_api_result_running:
            try_or_defer(_delete_service_api_result_running, service_api_result_running)
        raise

    silent_result = f.meta.get('silent_result', False)
    if not silent_result:
        logging.info("Service api call result: " + json.dumps(privatize(deepcopy(result))))
    return json.dumps(result), method, id_, log_service_call, cache_result, error_code, error_message, False

def _delete_service_api_result_running(service_api_result_running):
    service_api_result_running.delete()


class CallbackResponseReceiver(webapp.RequestHandler):

    def post(self):
        from rogerthat.settings import get_server_settings
        settings = get_server_settings()
        secret = self.request.headers.get("X-Nuntiuz-Secret", None)
        if secret != settings.jabberSecret:
            logging.error(u"Received unauthenticated callback response, ignoring ...")
            return
        sik = self.request.headers.get("X-Nuntiuz-Service-Key", None)
        if not sik:
            logging.error(u"Received invalid Callback response without Service Identifier Key")
            return
        sik = get_sik(sik)
        if not sik:
            logging.error("Received invalid Callback response with unknown Service Identifier Key:\nsik: %s\nbody:\n%s" % (self.request.headers.get("X-Nuntiuz-Service-Key", None), self.request.body))
            return
        users.set_user(sik.user)

        raw_result = self.request.body
        try:
            from google.appengine.api.memcache import get  # @UnresolvedImport
            if get(sik.user.email() + "_interactive_logs"):
                content_type = self.request.headers.get('content-type', 'unknown')
                status = self.request.headers.get('X-Nuntiuz-Service-Status', 'unknown')
                if status == "600":
                    status = "unknown"
                result_url = self.request.headers.get('X-Nuntiuz-Service-Result-Url', 'unknown')
                channel.send_message(sik.user, "rogerthat.service.interactive_logs", content_type=content_type, status=status, result_url=result_url, body=raw_result.decode('utf-8', 'replace'))
        except:
            logging.exception("Error during interactive logging.")

        try:
            result = json.loads(raw_result)
        except Exception:
            raw_result_unicode = raw_result.decode('utf-8', 'replace')
            logging.warning(u"Could not parse request body as JSON!\n" + raw_result_unicode)
            error_code = ERROR_CODE_INVALID_JSON
            error_message = u"The JSON_RPC response could not be parsed as a valid JSON."

            log_service_activity(sik.user, str(time.time()), ServiceLog.TYPE_CALLBACK, ServiceLog.STATUS_ERROR,
                                 None, None, raw_result_unicode, error_code, error_message)
            return
        raw_result_unicode = json.dumps(privatize(deepcopy(result)), ensure_ascii=False)
        logging.info(u"Incoming call back response:\n" + raw_result_unicode)

        if not result:
            error_code = ERROR_CODE_INVALID_JSON
            error_message = u"The JSON_RPC response could not be parsed as a valid json."
            log_service_activity(sik.user, None, ServiceLog.TYPE_CALLBACK, ServiceLog.STATUS_ERROR, None, None,
                                 raw_result_unicode, error_code, error_message)
            return

        from rogerthat.dal import parent_key
        service_api_callback = ServiceAPICallback.get_by_key_name(result["id"], parent=parent_key(sik.user))
        if not service_api_callback:
            logging.warning(u"Service api call back response record not found !")
            return
        _process_callback_result(sik, result, raw_result_unicode, service_api_callback, True)

def _process_callback_result(sik, result, raw_result_unicode, service_api_callback, log, synchronous=False):
    from rogerthat.rpc.calls import service_callback_result_mapping
    from rogerthat.rpc.rpc import rpc_items
    from rogerthat.bizz import monitoring

    offload(service_api_callback.service_user, OFFLOAD_TYPE_CALLBACK_API, json.loads(service_api_callback.call), result)

    error = result["error"]
    if error:
        error_code = ERROR_CODE_INVALID_CALLBACK
        error_message = json.dumps(error)
        status = ServiceLog.STATUS_ERROR
        monitoring.log_service_api_failure(service_api_callback, monitoring.SERVICE_API_CALLBACK)
    else:
        error_code = 0
        error_message = None
        status = ServiceLog.STATUS_SUCCESS
    try:
        if not error:
            callback_result = parse_parameter(u"result", service_callback_result_mapping[service_api_callback.resultFunction].meta[u"kwarg_types"][u"result"], result["result"])
            if synchronous:
                return callback_result
            service_callback_result_mapping[service_api_callback.resultFunction](context=service_api_callback, result=callback_result)
        else:
            if not synchronous:
                service_callback_result_mapping[service_api_callback.errorFunction](context=service_api_callback, error=error)
    except ServiceApiException, sae:
        if (sae.code >= ERROR_CODE_WARNING_THRESHOLD):
            logging.warning(u"Service API exception occurred", exc_info=1)
        else:
            logging.exception(u"Severe Service API Exception")
        error_code = sae.code
        error_message = sae.message

    finally:
        request = json.loads(service_api_callback.call)
        if log and sik:
            log_service_activity(sik.user, request["id"], ServiceLog.TYPE_CALLBACK, status, request["method"],
                                 service_api_callback.call, raw_result_unicode, error_code, error_message)
        if service_api_callback.is_saved():
            service_api_callback_key = service_api_callback.key()
            rpc_items.append(db.delete_async(service_api_callback_key), _delete_service_api_callback_deferred, service_api_callback_key)

        if synchronous and error:
            raise ServiceApiException(error_code, error_message)

def _delete_service_api_callback_deferred(service_api_callback_key):
    db.delete(service_api_callback_key)

def _validate_api_callback(result_f, error_f, target, alias, f):
    def raise_invalid_target():
        raise ValueError("Target argument should be of type rogerthat.models.ServiceProfile or [rogerthat.models.ServiceProfile]")

    check_decorations(result_f)
    check_decorations(error_f)
    if not isinstance(target, ServiceProfile):
        raise_invalid_target()
    funcs = result_f, error_f
    from rogerthat.rpc.calls import service_callback_result_mapping
    if any(filter(lambda fn: "mapping" not in fn.meta or fn.meta["mapping"] not in service_callback_result_mapping, funcs)):
        raise ValueError("Result and error processing functions must have their mapping declared in rogerthat.rpc.calls.result_mapping!")
    if any(filter(lambda fn: fn.meta["return_type"] != NoneType, funcs)):
        raise ValueError("Result and error processing functions cannot have return types.")
    if any(filter(lambda fn: "context" not in fn.meta["kwarg_types"] or fn.meta["kwarg_types"]["context"] != ServiceAPICallback, funcs)):
        raise ValueError("Result and error processing functions must have a arg 'context' of type rogerthat.models.ClientCall.")
    if any(filter(lambda fn:len(fn.meta["kwarg_types"]) != 2, funcs)):
        raise ValueError("Result and error processing functions must have 2 arguments!")
    if f.meta["return_type"] != result_f.meta["kwarg_types"]["result"]:
        raise ValueError("Return value type and result function result argument types do not match!")
    from rogerthat.rpc.calls import service_callback_mapping
    if not alias in service_callback_mapping:
        raise ValueError("Function is not present in client_mapping")
    if not "error" in error_f.meta["kwarg_types"] or error_f.meta["kwarg_types"]["error"] in (str, unicode):
        raise ValueError("Error function must have an error parameter of type string.")

def _send_directly(service_api_callback, profile, url, synchronous):
    sik = profile.sik
    headers = {'Content-type':'application/json-rpc; charset=utf-8', 'X-Nuntiuz-Service-Key':sik}
    def processResult(response):
        if response.status_code != 200:
            raise Exception("%s failed with http status code %s.\nBody:\n%s" % (url, response.status_code, response.content))
        result = json.loads(response.content)
        raw_result_unicode = json.dumps(privatize(deepcopy(result)), ensure_ascii=False)
        result = _process_callback_result(SIKKey.get_by_key_name(sik), result, raw_result_unicode, service_api_callback, True)
        if synchronous:
            return result
    response = rpc.direct_calls.append(url, service_api_callback.call.encode('utf8'), headers, processResult, synchronous)
    if synchronous:
        return processResult(response)
