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

from types import NoneType

from rogerthat.rpc import users
from rogerthat.to.system import LogErrorRequestTO
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments

@rest("/mobi/rest/system/feedback", "post")
@returns(NoneType)
@arguments(type_=unicode, subject=unicode, message=unicode)
def feedback(type_, subject, message):
    from rogerthat.bizz.system import feedback as feedbackBizz
    feedbackBizz(users.get_current_user(), type_, subject, message)

@rest("/mobi/rest/system/log_error", "post")
@returns(NoneType)
@arguments(description=unicode, errorMessage=unicode, timestamp=int, user_agent=unicode)
def log_error(description, errorMessage, timestamp, user_agent):
    request = LogErrorRequestTO()
    request.description = description
    request.errorMessage = errorMessage
    request.mobicageVersion = u"web"
    request.platform = 0
    request.platformVersion = user_agent
    request.timestamp = timestamp
    from rogerthat.bizz.system import logErrorBizz
    return logErrorBizz(request, users.get_current_user(), session=users.get_current_session())
