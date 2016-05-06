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

import mc_unittest
import uuid
from rogerthat.utils import DSPickler

class Test(mc_unittest.TestCase):

    def testDSPickler(self):

        d1 = dict()

        for _ in xrange(10000):
            d1['key%s' % _] = uuid.uuid4()

        dspp = DSPickler('moehahaha')
        dspp.update(d1)

        dspp = DSPickler.read('moehahaha')
        d2 = dspp.data

        self.assertEqual(d1, d2)

        dspp.delete()

        dspp = DSPickler.read('moehahaha')
        self.assertIsNone(dspp.data)
