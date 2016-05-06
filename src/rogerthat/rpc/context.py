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
import time


def _safe(f, *args, **kwargs):
    try:
        return f(*args, **kwargs)
    except:
        try:
            logging.exception("Caught exception while cleaning context")
        except:
            try:
                logging.critical("Could not log exception while cleaning context", _suppress=False)
            except:
                pass  # we give up


def _log_time_elapsed(start, path):
    if path and path not in ('/_ah/queue/deferred', '/_ah/warmup', '/cron/rpc/cleanup'):
        elapsed = time.time() - start
        if elapsed > 5:
            logging.warning("Request took %s seconds!" % elapsed)


def run_in_context(f, *args, **kwargs):
    from add_1_monkey_patches import reset_suppressing
    from rogerthat.rpc import users
    from rogerthat.rpc.rpc import wait_for_rpcs
    from mcfw.cache import flush_request_cache
    from mcfw.restapi import GenericRESTRequestHandler

    path = kwargs.pop('_path', None)
    start = time.time()

    reset_suppressing()
    try:
        return f(*args, **kwargs)
    finally:
        _safe(wait_for_rpcs)
        _safe(GenericRESTRequestHandler.clearCurrent)
        _safe(flush_request_cache)
        _safe(_log_time_elapsed, start, path)
        _safe(users.clear_user)
        _safe(reset_suppressing)


def start_in_new_context(func, func_args, func_kwargs, callback_func, callback_args, callback_kwargs, err_func,
                         synchronous, not_implemented_func=None, not_implemented_func_args=None):
    def wrapped(f, args, kwargs):
        return run_in_context(f, *args, **kwargs)

    from rogerthat.rpc import rpc
    future = rpc.context_threads.pool.submit(wrapped, func, func_args, func_kwargs)  # @UndefinedVariable
    rpc.context_threads.append(future, callback_func, callback_args, callback_kwargs, err_func, synchronous,
                               not_implemented_func, not_implemented_func_args)
