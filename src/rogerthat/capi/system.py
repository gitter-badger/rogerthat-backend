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

from rogerthat.rpc.rpc import capi
from rogerthat.to.js_embedding import UpdateJSEmbeddingResponseTO, UpdateJSEmbeddingRequestTO
from rogerthat.to.system import UpdateSettingsResponseTO, UpdateSettingsRequestTO, UnregisterMobileResponseTO, \
    UnregisterMobileRequestTO, UpdateAvailableResponseTO, UpdateAvailableRequestTO, IdentityUpdateResponseTO, \
    IdentityUpdateRequestTO, ForwardLogsResponseTO, ForwardLogsRequestTO
from mcfw.rpc import returns, arguments


@capi('com.mobicage.capi.system.updateSettings')
@returns(UpdateSettingsResponseTO)
@arguments(request=UpdateSettingsRequestTO)
def updateSettings(request):
    pass

@capi('com.mobicage.capi.system.unregisterMobile')
@returns(UnregisterMobileResponseTO)
@arguments(request=UnregisterMobileRequestTO)
def unregisterMobile(request):
    pass

@capi('com.mobicage.capi.system.updateAvailable')
@returns(UpdateAvailableResponseTO)
@arguments(request=UpdateAvailableRequestTO)
def updateAvailable(request):
    pass

@capi('com.mobicage.capi.system.identityUpdate')
@returns(IdentityUpdateResponseTO)
@arguments(request=IdentityUpdateRequestTO)
def identityUpdate(request):
    pass

@capi('com.mobicage.capi.system.forwardLogs')
@returns(ForwardLogsResponseTO)
@arguments(request=ForwardLogsRequestTO)
def forwardLogs(request):
    pass

@capi('com.mobicage.capi.system.updateJsEmbedding')
@returns(UpdateJSEmbeddingResponseTO)
@arguments(request=UpdateJSEmbeddingRequestTO)
def updateJsEmbedding(request):
    pass
