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

from rogerthat.capi.messaging import newMessage
from rogerthat.rpc import users
from rogerthat.to.messaging import NewMessageRequestTO
from mcfw.consts import MISSING
import mc_unittest
from rogerthat.bizz.messaging import new_message_response_handler
from rogerthat.rpc.rpc import logError

class Test(mc_unittest.TestCase):

    def testIncompleteMessageTOInCapi(self):
        request = NewMessageRequestTO()
        request.message = MISSING

        self.assertRaises(AttributeError, newMessage, new_message_response_handler, logError,
                          users.User('geert@example.com'), request=request)
