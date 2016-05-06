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

from rogerthat.bizz.job import run_job
from rogerthat.bizz.messaging import delete_conversation
from rogerthat.dal.messaging import get_messages_query
from rogerthat.models import ChatMembers
from rogerthat.models.properties.messaging import MemberStatus
from rogerthat.rpc import users
from google.appengine.ext import db
from mcfw.rpc import arguments


@arguments(app_user=users.User)
def job(app_user):
    run_job(_qry_messages, [app_user], _worker_messages, [app_user])
    run_job(_qry_chats, [app_user], _worker_chats, [app_user])

def _qry_messages(app_user):
    return get_messages_query(app_user, None, False)

def _worker_messages(message, app_user):
    delete_conversation(app_user, message.mkey, False, MemberStatus.STATUS_ACCOUNT_DELETED)

def _qry_chats(app_user):
    return ChatMembers.list_by_chat_member(app_user.email(), True)

def _worker_chats(chat_members_key, app_user):
    def trans():
        chatMembers = db.get(chat_members_key)
        try:
            chatMembers.members.remove(app_user.email())
        except ValueError:
            logging.warning("Expected member %s not found in members." % app_user.email())
            return
        chatMembers.put()
    db.run_in_transaction(trans)
