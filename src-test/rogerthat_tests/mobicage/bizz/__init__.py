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

from rogerthat.bizz.features import Version, Features
import mc_unittest


class TestFeatures(mc_unittest.TestCase):

    def testVersion(self):
        self.assertLess(Version(0, 1), Version(0, 2))
        self.assertLess(Version(0, 10), Version(0, 20))
        self.assertLessEqual(Version(0, 10), Version(0, 20))
        self.assertLessEqual(Version(0, 20), Version(1, 0))

        self.assertLessEqual(Version(10, 0), Version(10, 0))
        self.assertEqual(Version(10, 0), Version(10, 0))
        self.assertGreaterEqual(Version(10, 0), Version(10, 0))

        self.assertGreaterEqual(Version(1, 0), Version(0, 20))
        self.assertGreaterEqual(Version(10, 0), Version(0, 20))
        self.assertGreater(Version(10, 0), Version(0, 20))
        self.assertGreater(Version(0, 2), Version(0, 1))

        self.assertNotEqual(Version(0, 1), Version(0, 2))

    def testFeature(self):
        self.assertLess(Features.BROADCAST_VIA_FLOW_CODE.ios, Features.BROADCAST_VIA_FLOW_CODE.android)
        self.assertLess(Features.FRIEND_SET.ios.minor, Features.FRIEND_SET.android.minor)  # @UndefinedVariable
        self.assertEqual(Features.FRIEND_SET.ios.major, Features.FRIEND_SET.android.major)  # @UndefinedVariable
