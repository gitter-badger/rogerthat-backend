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

from rogerthat.dal.service import get_service_identity
from rogerthat.rpc import users
from rogerthat.templates import render
from rogerthat.translations import DEFAULT_LANGUAGE
from rogerthat.utils import azzert
from rogerthat.utils.crypto import md5_hex
from rogerthat.utils.service import create_service_identity_user


class ServiceUsersHandler(webapp2.RequestHandler):

    def get(self):
        identifier = self.request.GET.get('identifier')
        azzert(identifier)
        cursor = self.request.GET.get('cursor')

        si = get_service_identity(create_service_identity_user(users.get_current_user(), identifier))

        params = {'service_identity': identifier,
                  'service_identity_name': si.name,
                  'container_id': 'serviceUsersContainer_%s' % md5_hex(identifier),
                  'cursor': cursor}
        self.response.out.write(render('service_users', [DEFAULT_LANGUAGE], params, 'web'))
