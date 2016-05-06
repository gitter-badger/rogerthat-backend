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

from add_1_monkey_patches import dummy2
from add_2_zip_imports import dummy
from rogerthat.bizz import channel
from rogerthat.pages.register_mobile import RegisterMobileViaAndroidGoogleAccountHandler
from rogerthat.utils.channel import ChannelMessageRequestHandler
from rogerthat.wsgi import RogerthatWSGIApplication
from mcfw.restapi import rest_functions


dummy()
dummy2()

handlers = [
    ('/register_android_google_account', RegisterMobileViaAndroidGoogleAccountHandler),
    ('/channel/large_object', ChannelMessageRequestHandler),
]

handlers.extend(rest_functions(channel))

app = RogerthatWSGIApplication(handlers, uses_session=False, name="main_google_authenticated", google_authenticated=True)
