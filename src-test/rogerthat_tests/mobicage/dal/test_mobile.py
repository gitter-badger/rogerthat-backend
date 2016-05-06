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
from rogerthat.rpc import users
from rogerthat.dal.mobile import get_user_mobile_by_id_cached

class Test(mc_unittest.TestCase):

    def test_get_mobile_id_cached(self):
        self.set_datastore_hr_probability(1)
        mobile = users.get_current_mobile()
        assert get_user_mobile_by_id_cached(users.get_current_user(), mobile.id) == mobile
