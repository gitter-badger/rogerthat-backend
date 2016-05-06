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

from rogerthat.bizz.system import unregister_mobile
from rogerthat.bizz.user import archiveUserDataAfterDisconnect
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.profile import get_user_profile
from rogerthat.rpc import users
import mc_unittest


class Test(mc_unittest.TestCase):

    def setUp(self):
        mc_unittest.TestCase.setUp(self, datastore_hr_probability=1)

    def test_unregister_deactivated_account(self):
        user = users.get_current_user()
        mobile = users.get_current_mobile()
        # deactivate account
        archiveUserDataAfterDisconnect(user, get_friends_map(user), get_user_profile(user), False)
        unregister_mobile(user, mobile)
