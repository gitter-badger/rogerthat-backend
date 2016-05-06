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

import datetime
from functools import wraps
import json
import logging
import os
import pickle
import threading
import time
import uuid
import webapp2

from google.appengine.api.datastore_errors import TransactionFailedError
import google.appengine.api.users
from google.appengine.datastore.datastore_rpc import TransactionOptions, ConfigOption
from google.appengine.ext import db
from google.appengine.ext import deferred


SERVER_SOFTWARE = os.environ.get("SERVER_SOFTWARE", "Development")
APPSCALE = SERVER_SOFTWARE.startswith('AppScaleServer')
DEBUG = SERVER_SOFTWARE.startswith('Development')

# THIS PIECE OF CODE MUST BE ON TOP BECAUSE IT MONKEY PATCHES THE BUILTIN USER CLASS
# START MONKEY PATCH

def email_lower(email):
    if email is None:
        return None
    email = email.email() if isinstance(email, google.appengine.api.users.User) else email
    email = unicode(email) if not isinstance(email, unicode) else email
    return email.lower()


original_constructor = google.appengine.api.users.User.__init__
def __init__(self, *args, **kwargs):
    if args:
        email = args[0]
        if email:
            lower_email = email_lower(email)
            if lower_email != email:
                args = list(args)
                args[0] = lower_email
    else:
        email = kwargs.get('email', None)
        if email != None:
            lower_email = email_lower(email)
            if lower_email != email:
                kwargs['email'] = lower_email
    original_constructor(self, *args, **kwargs)
google.appengine.api.users.User.__init__ = __init__
# END MONKEY PATCH

# MONKEY PATCH logging
# Add possibility to bring down error levels for deferreds

class _TLocal(threading.local):
    def __init__(self):
        self.suppress = 0
_tlocal = _TLocal()
del _TLocal

def start_suppressing():
    _tlocal.suppress += 1

def stop_suppressing():
    if _tlocal.suppress > 0:
        _tlocal.suppress -= 1

def reset_suppressing():
    _tlocal.suppress = 0

_orig_error = logging.error
_orig_critical = logging.critical

def _new_error(msg, *args, **kwargs):
    suppress = kwargs.pop('_suppress', True)
    if _tlocal.suppress > 0 and suppress:
        logging.warning(msg, *args, **kwargs)
    else:
        _orig_error(msg, *args, **kwargs)

def _new_critical(msg, *args, **kwargs):
    suppress = kwargs.pop('_suppress', True)
    if _tlocal.suppress > 0 and suppress:
        logging.warning(msg, *args, **kwargs)
    else:
        _orig_critical(msg, *args, **kwargs)

def _new_exception(msg, *args, **kwargs):
    suppress = kwargs.pop('_suppress', True)
    if _tlocal.suppress > 0 and suppress:
        logging.warning(msg, *args, exc_info=1, **kwargs)
    else:
        _orig_error(msg, *args, exc_info=1, **kwargs)

logging.error = _new_error
logging.critical = _new_critical
logging.exception = _new_exception

# MONKEY PATCH db

# Add possibility to run post-transaction actions

class __TLocal(threading.local):
    def __init__(self):
        self.propagation = False

_temp_transaction_options = __TLocal()
del __TLocal

_orig_run_in_transaction_options = db.run_in_transaction_options
_options = [attr for attr in dir(TransactionOptions) if isinstance(getattr(TransactionOptions, attr), ConfigOption)]
_clone_options = lambda o: {attr: getattr(o, attr) for attr in _options}
_default_options = _clone_options(db.create_transaction_options())
def _wrap_run_in_transaction_func(is_retries, is_options):

    @wraps(_orig_run_in_transaction_options)
    def wrapped(*args, **kwargs):
        if is_options:
            options = _clone_options(args[0])
            args = args[1:]
        else:
            options = dict(_default_options)
        if is_retries:
            retries = args[0]
            args = args[1:]
        else:
            retries = options['retries']
        options['retries'] = 0
        if options.get('propagation') is None and _temp_transaction_options.propagation:
            options['propagation'] = db.ALLOWED
        options = db.create_transaction_options(**options)

        if db.is_in_transaction():
            return _orig_run_in_transaction_options(options, *args, **kwargs)

        if not retries:
            retries = 3
        if APPSCALE:
            retries += 3

        def run(transaction_guid):
            max_tries = retries + 1
            count = 0
            while count < max_tries:
                count += 1
                start = time.time()
                try:
                    return _orig_run_in_transaction_options(options, *args, **kwargs)
                except TransactionFailedError:
                    if count == max_tries:
                        raise
                    transactions.post_transaction_actions.reset(transaction_guid)
                    logging.info("Transaction collision, retrying %s ....", count)
                    sleep_time = 1.1 - (time.time() - start)
                    if sleep_time > 0:
                        logging.info("Sleeping %s seconds ....", sleep_time)
                        time.sleep(sleep_time)

        from rogerthat.utils import transactions
        if db.is_in_transaction():
            transaction_guid = transactions.post_transaction_actions.get_current_transaction_guid()
        else:
            transaction_guid = str(uuid.uuid4())
            transactions.post_transaction_actions.set_current_transaction_guid(transaction_guid)
        try:
            r = run(transaction_guid)
        except:
            transactions.post_transaction_actions.finalize(success=False, transaction_guid=transaction_guid)
            raise
        try:
            transactions.post_transaction_actions.finalize(success=True, transaction_guid=transaction_guid)
        except:
            logging.error("Caught exception in rpc.transaction_done", exc_info=1, _suppress=False)
        return r
    return wrapped

db.run_in_transaction = _wrap_run_in_transaction_func(is_retries=False, is_options=False)
db.run_in_transaction_custom_retries = _wrap_run_in_transaction_func(is_retries=True, is_options=False)
db.run_in_transaction_options = _wrap_run_in_transaction_func(is_retries=False, is_options=True)


_orig_db_transactional = db.transactional

def _new_transactional(**kwargs):

    def wrap(func):

        def wrapped(*args, **kwds):
            @_orig_db_transactional(**kwargs)
            def run():
                func(*args, **kwds)
            return _wrap_run_in_transaction_func(run)()

        return wrapped

    return wrap

db.transactional = _new_transactional

# END MONKEY PATCH

def _allow_transaction_propagation(func, *args, **kwargs):
    original_propagation_value = _temp_transaction_options.propagation
    _temp_transaction_options.propagation = True
    try:
        return func(*args, **kwargs)
    finally:
        _temp_transaction_options.propagation = original_propagation_value

db.allow_transaction_propagation = _allow_transaction_propagation
del _allow_transaction_propagation

# MONKEY PATCH json.dump & json.dumps to eliminate useless white space

_orig_json_dumps = json.dumps
def _new_json_dumps(*args, **kwargs):
    if len(args) < 8:
        kwargs.setdefault("separators", (',', ':'))
    return _orig_json_dumps(*args, **kwargs)
json.dumps = _new_json_dumps

_orig_json_dump = json.dump
def _new_json_dump(*args, **kwargs):
    if len(args) < 8:
        kwargs.setdefault("separators", (',', ':'))
    return _orig_json_dump(*args, **kwargs)
json.dump = _new_json_dump

# END MONKEY PATCH

# MONKEY PATCH deferred.defer

_old_deferred_defer = deferred.defer

def _new_deferred_defer(f, *args, **kwargs):
    from rogerthat.rpc import users
    from mcfw.consts import MISSING
    if users.get_current_deferred_user() == MISSING:
        kwargs['__user'] = users.get_current_user()
    else:
        kwargs['__user'] = users.get_current_deferred_user()
    return _old_deferred_defer(f, *args, **kwargs)


def _new_deferred_run(data):
    try:
        func, args, kwds = pickle.loads(data)
    except Exception, e:
        raise deferred.PermanentTaskFailure(e)
    else:
        from rogerthat.rpc import users
        current_user = kwds.pop('__user', None)
        if current_user:
            users.set_deferred_user(current_user)

        try:
            dt = datetime.datetime.utcnow()
            # do not log between 00:00 and 00:15
            # too many defers are run at this time
            if dt.hour != 0 or dt.minute > 15:
                from rogerthat.utils import get_current_queue
                logging.debug('Queue: %s\ndeferred.run(%s.%s%s%s)',
                              get_current_queue(),
                              func.__module__, func.__name__,
                              "".join((",\n             %s" % repr(a) for a in args)),
                              "".join((",\n             %s=%s" % (k, repr(v)) for k, v in kwds.iteritems())))
        except:
            logging.exception('Failed to log the info of this defer (%s)', func)

        try:
            return func(*args, **kwds)
        except:
            request = webapp2.get_request()
            if request:
                execution_count_triggering_error_log = 9
                execution_count = request.headers.get('X-Appengine-Taskexecutioncount', None)
                if execution_count and int(execution_count) == execution_count_triggering_error_log:
                    logging.error('This deferred.run already failed %s times!', execution_count, _suppress=False)
            raise
        finally:
            if current_user:
                users.clear_user()

deferred.defer = deferred.deferred.defer = _new_deferred_defer
deferred.run = deferred.deferred.run = _new_deferred_run

# END MONKEY PATCH

# MONKEY PATCH expando unindexed properties

_orginal_expando_getattr = db.Expando.__getattribute__
def _new_expando_getattr(self, key):
    if key == '_unindexed_properties':
        return self.__class__._unindexed_properties.union(self.dynamic_properties())
    return _orginal_expando_getattr(self, key)
db.Expando.__getattribute__ = _new_expando_getattr

# END MONKEY PATCH

dummy2 = lambda: None
