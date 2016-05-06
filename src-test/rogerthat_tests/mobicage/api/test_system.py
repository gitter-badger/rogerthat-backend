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

from rogerthat_tests import create_call, assert_result
from rogerthat.rpc.rpc import call
import math
import time
import mc_unittest
from rogerthat.models import MobileSettings
from rogerthat.rpc import users

class Test(mc_unittest.TestCase):

    def testHeartBeat(self):
        self.set_datastore_hr_probability(1)

        arguments = {'request': {'majorVersion': 1,
                                 'minorVersion': 2,
                                 'product': u'unit tester',
                                 'flushBackLog': True,
                                 'timestamp': 0,
                                 'timezone': u'GMT+1',
                                 'buildFingerPrint': u'test',
                                 'SDKVersion': u'1.0',
                                 'networkState': u'moehahaha'}}
        callId, c = create_call(1, "com.mobicage.api.system.heartBeat", arguments)
        _, result = call(c)
        print _, result
        result = assert_result(result, callId, True, lambda x: math.fabs(x['systemTime'] - time.time()) < 5)

        ms = MobileSettings.get(users.get_current_mobile())
        assert ms.majorVersion == 1
        assert ms.minorVersion == 2
        assert ms.lastHeartBeat == result['systemTime']
