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

import inspect
import logging

from rogerthat.rpc import users
from rogerthat.utils import azzert
from mcfw.rpc import arguments, returns

HANDLERS = dict()

@arguments(solution=unicode, code=int)
def service_api_callback_handler(solution, code):

    def wrap(f):

        def wrapped(service_user, **kwargs):
            users.set_user(service_user)
            return f(**kwargs)

        wrapped.__name__ = f.__name__
        wrapped.meta = dict(service_api_callback_handler=True, solution=solution, code=code)
        if hasattr(f, u"meta"):
            wrapped.meta.update(f.meta)
        return wrapped

    return wrap

def _get_key(solution, function):
    return "%s.%s" % (solution, function)

def service_api_callback_handler_functions(module):
    handlers_in_module = dict()
    for f in (function for (name, function) in inspect.getmembers(module, lambda x: inspect.isfunction(x))):
        if hasattr(f, 'meta') and f.meta.get("service_api_callback_handler", False):
            k = _get_key(f.meta['solution'], f.meta['code'])
            possible_duplicate = handlers_in_module.get(k)
            azzert(possible_duplicate is None,
                   u"Duplicate service_api_callback_handler specified:\n%s\n%s" % (f, possible_duplicate))
            HANDLERS[k] = handlers_in_module[k] = f

@returns(bool)
@arguments(solution=unicode, code=int)
def solution_supports_api_callback(solution, code):
    return _get_key(solution, code) in HANDLERS

@arguments(service_user=users.User, solution=unicode, code=int, kwargs=dict)
def handle_solution_api_callback(service_user, solution, code, kwargs):
    k = _get_key(solution, code)
    f = HANDLERS.get(k)
    if not f:
        raise NotImplementedError()
    try:
        # Forwards compatible: only supply kwargs implemented by f
        effective_kwargs = dict([ (arg, kwargs[arg]) for arg in f.meta['fargs'][0] ])
        return f(service_user, **effective_kwargs)
    except NotImplementedError:
        raise
    except:
        logging.exception("Caught exception in handle_solution_api_callback: %s" % k, _suppress=False)
        raise
