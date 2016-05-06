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

from rogerthat.models import ServiceIdentityStatistic
from google.appengine.ext import db
import mc_unittest


class TestCase(mc_unittest.TestCase):

    def _test_expando(self, cls):
        expando = cls()
        for x in xrange(50):
            setattr(expando, 'range%s' % x, range(500))
        expando.put()
        return expando

    def test_random_expando(self):
        class RandomExpando(db.Expando):
            pass
        self._test_expando(RandomExpando)

    def test_si_stats(self):
        expando = self._test_expando(ServiceIdentityStatistic)
        self.assertIn('users_gained', ServiceIdentityStatistic._unindexed_properties)
        self.assertIn('range1', expando._unindexed_properties)
        self.assertIn('users_gained', expando._unindexed_properties)
