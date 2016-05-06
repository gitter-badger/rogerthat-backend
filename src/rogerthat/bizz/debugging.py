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
import uuid

from rogerthat.bizz.registration import create_jabber_account, generate_account
from rogerthat.bizz.system import start_log_forwarding, delete_xmpp_account
from rogerthat.consts import APPSCALE, SCHEDULED_QUEUE
from rogerthat.dal.mobile import get_mobile_by_id, get_user_active_mobiles
from rogerthat.models import StartDebuggingRequest, CurrentlyForwardingLogs
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile
from rogerthat.settings import get_server_settings
from rogerthat.utils import channel, now, try_or_defer, azzert
from rogerthat.utils.crypto import encrypt_value, md5
from rogerthat.utils.transactions import on_trans_committed
from google.appengine.ext import deferred, db
from mcfw.rpc import returns, arguments


@returns(CurrentlyForwardingLogs)
@arguments(app_user=users.User, timeout=(int, long))
def start_admin_debugging(app_user, timeout):
    mobiles = list(get_user_active_mobiles(app_user))
    azzert(len(mobiles) == 1)

    m = mobiles[0]
    if m.type in (Mobile.TYPE_IPHONE_HTTP_APNS_KICK,
                  Mobile.TYPE_IPHONE_HTTP_XMPP_KICK,
                  Mobile.TYPE_WINDOWS_PHONE) \
              or (m.is_android and m.pushId):
        # No XMPP account needs to be created
        settings = get_server_settings()
        jid = base64.b64encode(encrypt_value(md5(settings.secret), users.get_current_user().email().encode('utf8')))
        password = None
        type_ = CurrentlyForwardingLogs.TYPE_GAE_CHANNEL_API
    else:
        account = generate_account(u'dbg_%s' % uuid.uuid4().get_hex())
        if not APPSCALE:
            create_jabber_account(account, None)
        jid = account.account
        password = account.password
        type_ = CurrentlyForwardingLogs.TYPE_XMPP

    def trans():
        debug_request = StartDebuggingRequest(key=StartDebuggingRequest.create_key(app_user, jid),
                                              timestamp=now())
        db.put_async(debug_request)
        deferred.defer(stop_debugging, app_user, jid, debug_request=debug_request, notify_user=False,
                       _countdown=timeout * 60, _transactional=True, _queue=SCHEDULED_QUEUE)
        return start_log_forwarding(app_user, jid, xmpp_target_password=password, type_=type_)

    xg_on = db.create_transaction_options(xg=True)
    return db.run_in_transaction_options(xg_on, trans)


@returns()
@arguments(app_user=users.User, mobile_id=unicode)
def start_debugging(app_user, mobile_id):
    settings = get_server_settings()
    domain = settings.jabberDomain

    target_jid = "kick.%s/debug:%s" % (domain, base64.b64encode(app_user.email().encode('utf-8')))

    def trans(mobile):
        debug_request = StartDebuggingRequest(key=StartDebuggingRequest.create_key(app_user, mobile_id),
                                              timestamp=now())
        db.put_async(debug_request)
        start_log_forwarding(app_user, target_jid, mobile=mobile)
        deferred.defer(stop_debugging, app_user, mobile_id, debug_request=debug_request,
                       _countdown=30 * 60, _transactional=True, _queue=SCHEDULED_QUEUE)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans, get_mobile_by_id(mobile_id))


@returns()
@arguments(app_user=users.User, mobile_id=unicode, debug_request=StartDebuggingRequest, notify_user=bool)
def stop_debugging(app_user, mobile_id, debug_request=None, notify_user=True):
    # debug_request is not None when debug session timed out

    def trans(mobile):
        stopped = False
        debug_request_from_ds = db.get(StartDebuggingRequest.create_key(app_user, mobile_id))
        if debug_request_from_ds:
            if not debug_request or debug_request.timestamp == debug_request_from_ds.timestamp:
                db.delete_async(debug_request_from_ds)
                start_log_forwarding(app_user, None, mobile)  # target_jid=None ==> will stop log forwarding
                stopped = True
            if not APPSCALE and debug_request_from_ds.target_id.startswith('dbg_'):
                on_trans_committed(try_or_defer, delete_xmpp_account, debug_request_from_ds.target_id, None)

        return stopped

    # stop debugging session after timeout, or when user closed the debugging dialog in the web UI
    xg_on = db.create_transaction_options(xg=True)
    stopped = db.run_in_transaction_options(xg_on, trans, get_mobile_by_id(mobile_id))
    if stopped and notify_user:
        channel.send_message(app_user, 'rogerthat.settings.stopped_debugging')


@returns()
@arguments(app_user=users.User, message=unicode)
def forward_log(app_user, message):
    channel.send_message(app_user, 'rogerthat.settings.log', message=message)
