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
import json
import logging
import os
from uuid import uuid4

import webapp2
from google.appengine.api import channel
from google.appengine.api import memcache
from google.appengine.ext import db

from rogerthat.bizz.channel import parse_channel_id
from rogerthat.consts import MC_DASHBOARD
from rogerthat.models.channel import ConnectedChannelClients
from rogerthat.rpc import users
from rogerthat.utils import try_or_defer, offload, \
    OFFLOAD_TYPE_WEB_CHANNEL, azzert
from rogerthat.utils.transactions import on_trans_committed

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

MAX_CHANNEL_MESSAGE_SIZE = 31 * 1024

def send_message_to_session(service_user, session, type_, **kwargs):
    ccc = db.get(ConnectedChannelClients.create_key(service_user))
    if ccc:
        if isinstance(type_, list):
            data = json.dumps(type_)
        else:
            data = get_data(type_, **kwargs)

        offload(service_user, OFFLOAD_TYPE_WEB_CHANNEL, data, None, type_)

        s = StringIO()
        s.write('b-')
        s.write(base64.b32encode(session.key().name().decode('hex')).replace("=", ""))
        s.write('|')
        channel_id = s.getvalue()

        targets = []
        for client_id in ccc.ids:
            if client_id.startswith(channel_id):
                targets.append(client_id)

        for client_id in targets:
            if db.is_in_transaction():
                on_trans_committed(try_or_defer, _send_message, client_id, data)
            else:
                try_or_defer(_send_message, client_id, data)

def send_message(user, type_, skip_dashboard_user=True, service_identity=None, **kwargs):
    if u"SERVER_SOFTWARE" in os.environ:
        targets = []
        connected_client_keys = []
        if isinstance(type_, list):
            data = json.dumps(type_)
        else:
            data = get_data(type_, **kwargs)

        for u in (user if isinstance(user, (set, list, tuple)) else [user]):
            if skip_dashboard_user and u == MC_DASHBOARD:
                continue
            offload(u, OFFLOAD_TYPE_WEB_CHANNEL, data, None, type_)
            connected_client_keys.append(ConnectedChannelClients.create_key(u))
            targets.append(u.email())

        for ccc in db.get(connected_client_keys):
            if ccc:
                if service_identity and ccc.identities:
                    for i in xrange(len(ccc.ids)):
                        if service_identity == ccc.identities[i] or (service_identity == "+default+" and ccc.identities[i] == ""):
                            targets.append(ccc.ids[i])
                else:
                    targets.extend(ccc.ids)

        for email_or_client_id in targets:
            if db.is_in_transaction():
                on_trans_committed(try_or_defer, _send_message, email_or_client_id, data)
            else:
                try_or_defer(_send_message, email_or_client_id, data)
        return True

def _send_message(client_id, data):
    if len(data) > MAX_CHANNEL_MESSAGE_SIZE:
        key = str(uuid4())
        memcache.set(key, (client_id, data), 60 * 5)  # @UndefinedVariable
        channel.send_message(client_id, "large_object=" + key)
    else:
        channel.send_message(client_id, data)


class ChannelMessageRequestHandler(webapp2.RequestHandler):

    def get(self):
        key = self.request.get('key')
        result = memcache.get(key)  # @UndefinedVariable
        if result:
            client_id, data = result
            service_user, _ = parse_channel_id(client_id)
            azzert(service_user == users.get_current_user())
            memcache.delete(key)  # @UndefinedVariable
        else:
            logging.error("Failed to get channel message from memcache!")
            data = '{ "type": "" }'

        self.response.headers['Content-Type'] = 'text/json'
        self.response.write(data)


def get_data(type_, **kwargs):
    kwargs[u'type'] = type_
    return json.dumps(kwargs)

def broadcast_via_iframe_result(type_, **kwargs):
    return """<html><body><script language="javascript" type="text/javascript">
    var obj = window.top.window.mctracker ? window.top.window.mctracker : window.top.window.sln; obj.broadcast(%s);
</script></body></html>""" % get_data(type_, **kwargs)
