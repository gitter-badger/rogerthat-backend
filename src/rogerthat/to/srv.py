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

from rogerthat.utils import azzert
from mcfw.properties import unicode_property, long_property


class SRVDetailsTO(object):
    ip = unicode_property('0')
    port = long_property('1')
    priority = long_property('2')

    @staticmethod
    def fromString(srvDetail):
        srv = SRVDetailsTO()
        parts = srvDetail.split(":")
        part_ip = [int(p) for p in parts[0].split('.')]
        azzert(len(part_ip) == 4)
        ip = parts[0]
        port = int(parts[1])
        priority = int(parts[2])
        srv.ip = ip.decode('unicode-escape')
        srv.port = port
        srv.priority = priority
        return srv

    def __str__(self):
        return "%s:%s:%s" % (self.ip, self.port, self.priority)
