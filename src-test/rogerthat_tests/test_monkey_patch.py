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

import unittest
# noinspection PyUnresolvedReferences
import test  # @UnusedImport
from rogerthat.rpc import users
import google.appengine.api.users

class Test(unittest.TestCase):


    def testUserAccountCaseInsensitiveness(self):
        self.assertEqual(users.User(u'Geert@example.com'), users.User(u'geert@example.com'))

    def testNone(self):
        self.assertRaises(google.appengine.api.users.UserNotFoundError, lambda: users.User(None))

    def testUserByUser(self):
        user1 = users.User('geert@example.com')
        user2 = users.User(user1)
        self.assertEqual(user1, user2)
        self.assertEqual(user2.email(), u'geert@example.com')
