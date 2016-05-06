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

import webapp2

from rogerthat.bizz.channel import client_connected, client_disconnected, parse_channel_id


class ChannelConnectedHandler(webapp2.RequestHandler):

    def post(self):
        client_id = self.request.get('from')
        service_user, service_identity = parse_channel_id(client_id)
        if service_user:
            client_connected(service_user, service_identity, client_id)


class ChannelDisconnectedHandler(webapp2.RequestHandler):

    def post(self):
        client_id = self.request.get('from')
        service_user, _ = parse_channel_id(client_id)
        if service_user:
            client_disconnected(service_user, client_id)
