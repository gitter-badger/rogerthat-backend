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

from rogerthat.utils import email_to_id, id_to_email
import mc_unittest


class Test(mc_unittest.TestCase):

    def testEmailToId(self):

        orig_email = u"g€€rt@mobicag€.com"
        id_ = email_to_id(orig_email)
        result_email = id_to_email(id_)

        self.assertEquals(orig_email, result_email)
