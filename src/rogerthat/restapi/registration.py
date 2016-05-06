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

from rogerthat.rpc import users
from rogerthat.to.registration import AccountTO
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments


@rest("/mobi/rest/devices/mobiles/register", "post")
@returns(AccountTO)
@arguments()
def register_mobile():
    from rogerthat.bizz.registration import register_mobile as register_mobile_bizz
    return register_mobile_bizz(users.get_current_user())
