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

import os
os.environ['AUTH_DOMAIN'] = 'gmail.com'    # Do not remove this line
from rogerthat.rpc.calls import service_callback_mapping
from rogerthat.rpc.service import get_service_api_calls
from rogerthat.service.api import friends, messaging
from generator.generator import generate


service_mapping = get_service_api_calls(friends)
service_mapping.update(get_service_api_calls(messaging))
generate(os.path.splitext(os.path.basename(__file__))[0], service_mapping, service_callback_mapping, max_argument_count=1000)
