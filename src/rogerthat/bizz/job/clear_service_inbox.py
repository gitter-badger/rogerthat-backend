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

from types import NoneType

from rogerthat.dal.messaging import get_service_user_inbox_keys_query
from rogerthat.models import Message
from rogerthat.rpc import users
from google.appengine.ext import deferred, db
from mcfw.rpc import arguments, returns


@returns(NoneType)
@arguments(service_identity_user=users.User, human_user=users.User)
def schedule(service_identity_user, human_user):
    deferred.defer(run, service_identity_user, human_user, _transactional=db.is_in_transaction())

def run(service_identity_user, human_user, cursor=None):
    qry = get_service_user_inbox_keys_query(service_identity_user, human_user, cursor)
    message_keys = qry.fetch(100)
    def update(message_key):
        message = db.get(message_key)
        message.removeStatusIndex(human_user, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX)
        message.put()
    for key in message_keys:
        db.run_in_transaction(update, key)
    if len(message_keys) > 0:
        return deferred.defer(run, service_identity_user, human_user, qry.cursor())
