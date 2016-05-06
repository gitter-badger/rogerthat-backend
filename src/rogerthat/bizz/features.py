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

from functools import total_ordering

from mcfw.consts import MISSING
from mcfw.properties import long_property, typed_property
from mcfw.utils import Enum


@total_ordering  # @total_ordering uses __lt__ and __eq__ to create __gt__, __ge__, __le__ and __ne__
class Version(object):
    major = long_property('1')
    minor = long_property('2')

    def __init__(self, major=MISSING, minor=MISSING):
        if major is not MISSING:
            self.major = major
        if minor is not MISSING:
            self.minor = minor

    def __eq__(self, other):
        return (self.major, self.minor) == (other.major, other.minor)

    def __lt__(self, other):
        return (self.major, self.minor) < (other.major, other.minor)

    def __str__(self):
        return '%s.%s' % (self.major, self.minor)

    __repr__ = __str__


class Feature(object):
    ios = typed_property('1', Version)
    android = typed_property('2', Version)

    def __init__(self, ios=MISSING, android=MISSING):
        if ios is not MISSING:
            self.ios = ios
        if android is not MISSING:
            self.android = android


class Features(Enum):
    FRIEND_SET = Feature(ios=Version(0, 162), android=Version(0, 1003))
    BROADCAST_VIA_FLOW_CODE = Feature(ios=Version(0, 765), android=Version(0, 1626))
    ADVANCED_ORDER = Feature(ios=Version(0, 765), android=Version(0, 1626))
