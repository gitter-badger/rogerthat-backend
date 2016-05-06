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
import threading

from rogerthat.utils import azzert, slog
from google.appengine.api import users
from mcfw.consts import MISSING
from mcfw.rpc import returns


class _TLocal(threading.local):
    def __init__(self):
        self.reset()

    def set_user(self, user=MISSING, xmpp_account=MISSING, mobile=MISSING, session=MISSING, backlog_item=MISSING,
                 deferred_user=MISSING, app_id=MISSING, mfr=MISSING):
        if user != MISSING:
            self.user = user
            if self.user:
                if mfr != MISSING:
                    self.user.is_mfr = mfr
                else:
                    self.user.is_mfr = False
        if xmpp_account != MISSING:
            self.xmpp_account = xmpp_account
        if mobile != MISSING:
            self.mobile = mobile
        if session != MISSING:
            self.session = session
        if backlog_item != MISSING:
            self.backlog_item = backlog_item
        if deferred_user != MISSING:
            self.deferred_user = deferred_user
        if app_id != MISSING:
            self.app_id = app_id
        from rogerthat.bizz import log_analysis
        if self.deferred_user not in (None, MISSING):
            slog(msg_="Request identification", function_=log_analysis.REQUEST_IDENTIFICATION,
                 email_=self.deferred_user.email(), type_=log_analysis.REQUEST_IDENTIFICATION_TYPE_DEFERRED)
        elif self.user:
            slog(msg_="Request identification", function_=log_analysis.REQUEST_IDENTIFICATION,
                 email_=self.user.email(), type_=log_analysis.REQUEST_IDENTIFICATION_TYPE_USER)

    def reset(self):
        self.user = None
        self.xmpp_account = None
        self.mobile = None
        self.session = None
        self.backlog_item = None
        self.deferred_user = MISSING
        self.app_id = None


_tlocal = _TLocal()
del _TLocal

User = users.User

@returns(users.User)
def get_current_user():
    return _tlocal.user

def get_current_mobile():
    return _tlocal.mobile

def get_current_session():
    return _tlocal.session

def get_current_app_id():
    app_id = _tlocal.app_id
    if not app_id:
        from rogerthat.utils.app import get_app_id_from_app_user
        _tlocal.app_id = app_id = get_app_id_from_app_user(_tlocal.user) if _tlocal.user else None
    return app_id

def get_current_backlog_item_timestamp():
    if _tlocal.backlog_item:
        from rogerthat.rpc.rpc import CALL_TIMESTAMP
        return _tlocal.backlog_item[CALL_TIMESTAMP]
    return None

def get_current_deferred_user():
    return _tlocal.deferred_user

def create_logout_url(*args, **kwargs):
    return users.create_logout_url(*args, **kwargs)

def create_login_url(*args, **kwargs):
    return users.create_login_url(*args, **kwargs)

def set_xmpp_user(sender):
    from rogerthat.dal.mobile import get_mobile_by_account
    try:
        xmpp_account = sender.split('/')[0]
        mobile = get_mobile_by_account(xmpp_account)
        if not mobile:
            logging.error("Unknown account accessing api: " + xmpp_account)
            raise ValueError("Unknown sender: '%s'" % sender)
        _tlocal.set_user(user=mobile.user, xmpp_account=xmpp_account, mobile=mobile, mfr=False, app_id=None)
    except:
        clear_user()
        raise

def set_backlog_item(backlog_item):
    _tlocal.backlog_item = backlog_item

def set_json_rpc_user(user, password, ignore_status=False):
    from rogerthat.dal.mobile import get_mobile_by_account
    from rogerthat.rpc.models import Mobile
    try:
        mobile = get_mobile_by_account(user)
        azzert(mobile and mobile.accountPassword == password)
        _tlocal.set_user(mobile=mobile, user=mobile.user, app_id=None, mfr=False)

        try:
            mobile_string = Mobile.typeAsString(_tlocal.mobile.type)
        except ValueError:
            mobile_string = str(_tlocal.mobile.type)

        logging.info("Request identity: %s (%s)", _tlocal.user, mobile_string)
        return True
    except:
        logging.warn("set_json_rpc_user failed", exc_info=True)
        clear_user()
        return False

def set_user(user, session=None, mfr=False):
    user = User(unicode(user.email())) if user else None  # Fix to make sure .email() always returns unicode
    _tlocal.set_user(user=user, session=session, mfr=mfr, xmpp_account=None, mobile=None, app_id=None)

    if user:
        if session and session.name:
            session_name = "%s - %s" % (user, session.name)
        else:
            session_name = str(user)
        if session and session.user != user:
            if session.shop:
                logging.info("Request identity: %s (%s via shop) (WEB)", session_name, session.user)
            else:
                logging.info("Request identity: %s (%s) (WEB)", session_name, session.user)
        else:
            logging.info("Request identity: %s (WEB)", session_name)

def set_deferred_user(user):
    _tlocal.set_user(deferred_user=user)

def update_session_object(new_session_object, new_user):
    _tlocal.session = new_session_object
    _tlocal.user = new_user
    _tlocal.app_id = None

def clear_user():
    _tlocal.reset()
