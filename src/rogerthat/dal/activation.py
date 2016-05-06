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

from rogerthat.dal import generator
from rogerthat.models import ActivationLog
from mcfw.rpc import returns, arguments


@returns([ActivationLog])
@arguments(min_timestamp=int, max_timestamp=int)
def get_activation_log(min_timestamp, max_timestamp):
    qry = ActivationLog.gql("WHERE timestamp > :min_timestamp AND timestamp < :max_timestamp ORDER BY timestamp DESC")
    qry.bind(min_timestamp=min_timestamp, max_timestamp=max_timestamp)
    return generator(qry.run())
