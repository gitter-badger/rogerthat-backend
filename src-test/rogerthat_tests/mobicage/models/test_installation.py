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

from rogerthat.models import Installation, InstallationLog
from rogerthat.utils import now
import mc_unittest


class TestInstallationLogs(mc_unittest.TestCase):

    def test_registration_successful(self):
        t = now()
        installation = Installation()
        installation._logs = list()
        self.assertFalse(installation.logged_registration_successful)

        installation._logs.append(InstallationLog(timestamp=t, description='Registration Successfull'))
        self.assertTrue(installation.logged_registration_successful)

        installation._logs.append(InstallationLog(timestamp=t, description='Blablabla'))
        self.assertTrue(installation.logged_registration_successful)

        installation._logs.append(InstallationLog(timestamp=t + 1, description='Blablabla2'))
        self.assertFalse(installation.logged_registration_successful)
