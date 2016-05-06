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

from rogerthat.to.friends import FriendTO
from rogerthat.to.messaging import MessageListTO, RootMessageListTO
from rogerthat.to.system import UserStatusTO
from mcfw.properties import typed_property


class WebTO(object):
    messages = typed_property('1', RootMessageListTO, False)
    service_inbox = typed_property('2', MessageListTO, False)
    friends = typed_property('3', FriendTO, True)
    user_status = typed_property('4', UserStatusTO, False)
