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
from mcfw.properties import unicode_property, long_property, typed_property


class OauthUserInfoTO(object):
    username = unicode_property('1')


class OauthAccessTokenTO(object):
    access_token = unicode_property('1')
    expires_in = long_property('2')
    refresh_token = unicode_property('3')
    token_type = unicode_property('4')
    scopes = unicode_property('5')
    info = typed_property('6', OauthUserInfoTO)
