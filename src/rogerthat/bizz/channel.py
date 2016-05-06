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
import logging
import uuid

from rogerthat.models.channel import ConnectedChannelClients
from rogerthat.rpc import users
from rogerthat.rpc.models import Session
from rogerthat.utils import azzert
from rogerthat.utils.service import get_service_user_from_service_identity_user
from google.appengine.api.channel import channel
from google.appengine.ext import db
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


@returns(unicode)
@arguments()
def create_channel_for_current_session():
    return channel.create_channel(create_channel_id(users.get_current_session()))


@returns(str)
@arguments(session=Session)
def create_channel_id(session):
    s = StringIO()
    s.write('b-')
    s.write(base64.b32encode(session.key().name().decode('hex')).replace("=", ""))
    s.write('|')
    s.write(base64.b32encode(uuid.uuid4().bytes).replace("=", ""))
    channel_id = s.getvalue()
    azzert(len(channel_id) <= 64, "Channel ids should not be longer than 64 bytes")
    return channel_id


@returns(tuple)
@arguments(client_id=str)
def parse_channel_id(client_id):
    if "|" not in client_id:
        return None, None

    def get_session(session_secret):
        session = Session.get_by_key_name(session_secret.encode('hex'))
        if session.service_identity_user:
            return get_service_user_from_service_identity_user(session.service_identity_user), session.service_identity
        return session.user, session.service_identity

    if client_id[:2] == "b:":
        session_secret = base64.b64decode(client_id[2:].split('|', 1)[0])
        return get_session(session_secret)
    elif client_id[:2] == "b-":
        b32str = client_id[2:].split('|', 1)[0]
        while len(b32str) < 32:
            b32str += '='
        session_secret = base64.b32decode(b32str)
        return get_session(session_secret)
    else:
        return users.User(client_id.split("|")[0]), None


@returns(bool)
@arguments(service_user=users.User, service_identity=unicode, client_id=unicode)
def client_connected(service_user, service_identity, client_id):
    def trans():
        connected_clients = ConnectedChannelClients.get(service_user)
        if client_id not in connected_clients.ids:
            if not connected_clients.identities:
                connected_clients.identities = ["" for _ in xrange(len(connected_clients.ids))]
            connected_clients.ids.append(client_id)
            connected_clients.identities.append(service_identity if service_identity else "")
            connected_clients.put()
            return connected_clients, True
        return connected_clients, False

    connected_clients, updated = db.run_in_transaction(trans)
    logging.debug('User %s (%s) connected to the channel.\nConnected channel clients: %s',
                  client_id, service_user.email(), connected_clients.ids)
    return updated


@returns(bool)
@arguments(service_user=users.User, client_id=unicode)
def client_disconnected(service_user, client_id):
    def trans():
        connected_clients = ConnectedChannelClients.get(service_user)
        if client_id in connected_clients.ids:
            if connected_clients.identities:
                i = connected_clients.ids.index(client_id)
                del connected_clients.identities[i]
                del connected_clients.ids[i]
            else:
                connected_clients.ids.remove(client_id)
            connected_clients.put()
            return connected_clients, True
        return connected_clients, False

    connected_clients, updated = db.run_in_transaction(trans)
    logging.debug('User %s (%s) disconnected from the channel.\nConnected channel clients: %s',
                  client_id, service_user.email(), connected_clients.ids)
    return updated


@returns([unicode])
@arguments(service_user=users.User)
def get_connected_clients(service_user):
    def trans():
        connected_clients = ConnectedChannelClients.get(service_user)
        return connected_clients.ids

    return db.run_in_transaction(trans)


@rest("/channel/token", "get", read_only_access=True)
@returns(unicode)
@arguments()
def token():
    return create_channel_for_current_session()
