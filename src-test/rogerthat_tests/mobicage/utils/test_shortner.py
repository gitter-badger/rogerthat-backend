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

from rogerthat.models import ShortURL
from rogerthat.pages.shortner import get_short_url_by_code
from google.appengine.ext import db
import mc_unittest


class Test(mc_unittest.TestCase):


    def testGetShortUrlByCode(self):
        self.set_datastore_hr_probability(1)
        user_code = u"l6FTdKUMafjzHQ.gxGY.BiCbbUJ2z2b6zbFIe8plGvk-"
        sid_id = u"5629499534213120"
        su_id = 4530377460809728
        su = ShortURL(key=db.Key.from_path(ShortURL.kind(), su_id))
        su.full = u"/q/s/%s/%s" % (user_code, sid_id)
        su.put()

        self.assertEqual(su_id, get_short_url_by_code("W4OB0RU.FR").key().id())
        self.assertEqual(su_id, get_short_url_by_code("W4OB0RU.FR…").key().id())
        self.assertEqual(su_id, get_short_url_by_code("W4OB0RU.FR%E2%80%A6").key().id())
