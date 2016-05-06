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

from rogerthat.bizz import log_analysis
from rogerthat.models import ServiceProfile
from rogerthat.rpc.models import ServiceAPICallback
from rogerthat.utils import slog, azzert
from mcfw.rpc import arguments, returns


SERVICE_API_CALL = u"Call"
SERVICE_API_CALLBACK = u"CallBack"

@returns(NoneType)
@arguments(monitor=(ServiceProfile, ServiceAPICallback), call_type=unicode)
def log_service_api_failure(monitor, call_type):
    azzert(call_type in (SERVICE_API_CALL, SERVICE_API_CALLBACK))
    if monitor.monitor:
        slog(msg_=u"Service Api%s failure" % call_type, function_=log_analysis.SERVICE_MONITOR, service=monitor.service_user.email(), call_type=call_type)
