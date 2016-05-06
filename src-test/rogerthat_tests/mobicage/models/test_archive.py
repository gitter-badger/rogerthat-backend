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

from rogerthat.bizz import roles
from rogerthat.bizz.profile import create_service_profile, create_user_profile
from rogerthat.rpc import users
import mc_unittest
from rogerthat.dal.profile import get_user_profile
from rogerthat.models import UserProfileArchive


class SkipTests(mc_unittest.TestCase):

    def setUp(self):
        super(SkipTests, self).setUp(1)
        self.service = users.User(u'monitoring@rogerth.at')
        _, service_identity = create_service_profile(self.service, u"Monitoring service")

        self.john = users.User(u'john_doe@foo.com')
        up = create_user_profile(self.john, u"John Doe")
        up.grant_role(service_identity.user, roles.ROLE_ADMIN)
        up.put()

    def test_skip_on_archive(self):

        john_profile = get_user_profile(self.john)
        self.assertTrue(john_profile.roles)
        self.assertTrue(john_profile.role_services)

        archived_john_profile = john_profile.archive(UserProfileArchive)
        self.assertEqual([], archived_john_profile.roles)
        self.assertEqual([], archived_john_profile.role_services)
