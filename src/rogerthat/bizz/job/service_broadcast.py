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
import uuid

from google.appengine.ext import db

from rogerthat.bizz.job import run_job
from rogerthat.dal.service import get_all_service_friend_keys_query, is_broadcast_type_enabled, \
    get_broadcast_audience_of_service_identity_keys_query
from rogerthat.rpc import users
from rogerthat.to.messaging import AnswerTO, UserMemberTO, AttachmentTO
from mcfw.rpc import arguments, returns


@arguments(service_user=users.User, flow=unicode, broadcast_type=unicode, tag=unicode)
def schedule_service_broadcast(service_user, flow, broadcast_type, tag):
    broadcast_guid = unicode(uuid.uuid4())
    run_job(get_all_service_friend_keys_query, [service_user], _service_broadcast, [flow, broadcast_type, tag, broadcast_guid])
    return broadcast_guid

@arguments(connection_key=db.Key, flow=unicode, broadcast_type=unicode, tag=unicode, broadcast_guid=unicode)
def _service_broadcast(connection_key, flow, broadcast_type, tag, broadcast_guid):
    connection = db.get(connection_key)
    if is_broadcast_type_enabled(connection.service_identity, connection.friend, broadcast_type):
        from rogerthat.bizz.service.mfr import start_flow
        start_flow(connection.service_identity, None, flow, [connection.friend], check_friends=False,
                   result_callback=True, tag=tag, broadcast_type=broadcast_type, broadcast_guid=broadcast_guid)

@returns(unicode)
@arguments(service_identity_user=users.User, broadcast_type=unicode, message=unicode, answers=[AnswerTO], flags=int,
           branding=unicode, tag=unicode, alert_flags=int, dismiss_button_ui_flags=int, min_age=(int, long, NoneType),
           max_age=(int, long, NoneType), gender=(NoneType, int), attachments=[AttachmentTO], app_id=(NoneType, unicode),
           timeout=int)
def schedule_identity_broadcast_message(service_identity_user, broadcast_type, message, answers, flags, branding, tag,
                                        alert_flags, dismiss_button_ui_flags, min_age=None, max_age=None, gender=None,
                                        attachments=None, app_id=None, timeout=0):
    broadcast_guid = unicode(uuid.uuid4())
    run_job(get_broadcast_audience_of_service_identity_keys_query,
            [service_identity_user, min_age, max_age, gender, app_id, broadcast_type],
            _identity_broadcast_message,
            [broadcast_type, message, answers, flags, branding, tag, alert_flags, dismiss_button_ui_flags, attachments,
             timeout, broadcast_guid])
    return broadcast_guid

@arguments(connection_key=db.Key, broadcast_type=unicode, message=unicode, answers=[AnswerTO],
           flags=int, branding=unicode, tag=unicode, alert_flags=int, dismiss_button_ui_flags=int,
           attachments=[AttachmentTO], timeout=int, broadcast_guid=unicode)
def _identity_broadcast_message(connection_key, broadcast_type, message, answers, flags, branding, tag, alert_flags,
                                dismiss_button_ui_flags, attachments, timeout, broadcast_guid):
    from rogerthat.bizz.messaging import sendMessage, CanOnlySendToFriendsException
    connection = db.get(connection_key)
    app_user = users.User(connection.friend)
    try:
        sendMessage(connection.service_identity, [UserMemberTO(app_user, alert_flags)], flags,
                    timeout, None, message, answers, None, branding, tag, dismiss_button_ui_flags,
                    broadcast_type=broadcast_type, attachments=attachments, broadcast_guid=broadcast_guid)
    except CanOnlySendToFriendsException:
        pass  # Possible race condition
