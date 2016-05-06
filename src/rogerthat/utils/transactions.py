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

from functools import wraps
import logging
import threading

from rogerthat.utils import azzert
from google.appengine.ext import db


class PostTransactionActions(threading.local):

    def __init__(self):
        self.transaction_guids = list()
        self.items = dict()

    def set_current_transaction_guid(self, transaction_guid):
        azzert(transaction_guid not in self.transaction_guids)
        self.transaction_guids.append(transaction_guid)
        self.items[transaction_guid] = list()

    def get_current_transaction_guid(self):
        return self.transaction_guids[-1]

    def reset(self, transaction_guid):
        while self.items[transaction_guid]:
            self.items[transaction_guid].pop(0)

    def append(self, success, callback_func, *callback_args, **callback_kwargs):
        transaction_guid = self.get_current_transaction_guid()
        self.items[transaction_guid].append((success, callback_func, callback_args, callback_kwargs))

    def finalize(self, success, transaction_guid):
        try:
            items = self.items[transaction_guid]
            if items:
                logging.debug("Finalizing transaction items (total: %s) ...", len(items))
                while items:
                    is_success_callback, callback_func, callback_args, callback_kwargs = items.pop(0)
                    logging.debug("Finalizing transaction items (%s left) ...", len(items))
                    try:
                        if (success and is_success_callback) or (not success and not is_success_callback):
                            logging.debug("Executing post-transaction action: %s" % callback_func.func_name)
                            callback_func(*callback_args, **callback_kwargs)
                    except:
                        logging.exception("Caught exception in transaction_done_callback")
                logging.debug("Transaction finalized")
        finally:
            del self.items[transaction_guid]
            self.transaction_guids.remove(transaction_guid)

post_transaction_actions = PostTransactionActions()


def on_trans_committed(func, *args, **kwargs):
    """
    Executes func when the transaction the function is run in has completed.

    Args:
        func: Function to execute
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Notes:
        Does not return the function's return value.
    """
    azzert(db.is_in_transaction())
    post_transaction_actions.append(True, func, *args, **kwargs)


def on_trans_rollbacked(func, *args, **kwargs):
    azzert(db.is_in_transaction())
    post_transaction_actions.append(False, func, *args, **kwargs)

def run_after_transaction(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if db.is_in_transaction():
            on_trans_committed(f, *args, **kwargs)
        else:
            return f(*args, **kwargs)

    return wrapped


def run_in_xg_transaction(function, *args, **kwargs):
    xg_on = db.create_transaction_options(xg=True)
    return db.run_in_transaction_options(xg_on, function, *args, **kwargs)


def run_in_transaction(function, xg=False, *args, **kwargs):
    """Runs specified function in a transaction.
    If called inside a transaction, the function is executed without creating a new transaction.

    Args:
        function: a function to be run inside the transaction on all remaining arguments
        xg: set to true to allow cross-group transactions (high replication datastore only)
        *args: Positional arguments for function.
        **kwargs: Keyword arguments for function.

    Returns:
        The function's return value, if any
    """
    if db.is_in_transaction():
        return function(*args, **kwargs)
    elif xg:
        transaction_options = db.create_transaction_options(xg=True)
        return db.run_in_transaction_options(transaction_options, function, *args, **kwargs)
    else:
        return db.run_in_transaction(function, *args, **kwargs)


allow_transaction_propagation = db.allow_transaction_propagation  # @UndefinedVariable
