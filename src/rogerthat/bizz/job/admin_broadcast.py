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
from types import NoneType

from google.appengine.ext import db

from mcfw.rpc import returns, arguments
from rogerthat.bizz.messaging import sendMessage
from rogerthat.consts import MC_DASHBOARD
from rogerthat.dal.app import get_app_by_user
from rogerthat.dal.profile import get_profile_info
from rogerthat.models import Message
from rogerthat.rpc.models import Mobile
from rogerthat.to.messaging import ButtonTO, UserMemberTO


@returns(NoneType)
@arguments(message=unicode, filter_src=unicode, buttons=[ButtonTO])
def send(message, filter_src, buttons):
    from google.appengine.ext import deferred
    deferred.defer(job, message, filter_src, buttons, _transactional=db.is_in_transaction())

def job(message, filter_src, buttons, cursor=None):
    from google.appengine.ext import deferred
    filter_function = eval(filter_src)
    query = Mobile.gql("WHERE status = %s" % (Mobile.STATUS_NEW | Mobile.STATUS_ACCOUNT_CREATED | Mobile.STATUS_REGISTERED))
    query.with_cursor(cursor)
    mobiles = query.fetch(100)
    for m in mobiles:
        logging.info("Applying filter on %s" % m.user.email())

        # Patch because bad test data appears to be in the datastore
        profile_info = get_profile_info(m.user)
        if profile_info.isServiceIdentity:
            continue
        # End Patch

        if filter_function(m):
            deferred.defer(send_to_user, message, m.user, buttons, _transactional=db.is_in_transaction())
    if len(mobiles) > 0:
        return deferred.defer(job, message, filter_src, buttons, query.cursor(), _transactional=db.is_in_transaction())

def send_to_user(message, user, buttons):
    logging.info("Sending message to user %s:\n%s" % (user.email(), message))
    sendMessage(MC_DASHBOARD, [UserMemberTO(user, Message.ALERT_FLAG_VIBRATE)], Message.FLAG_ALLOW_DISMISS, 0, None,
                message, buttons, None, get_app_by_user(user).core_branding_hash, None, is_mfr=False)
