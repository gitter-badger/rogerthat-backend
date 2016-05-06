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

# Outcome of this encoding is url-friendly and does not have to be url-encoded
# resulting in shorter urls in sms messages

from mcfw.rpc import arguments, returns


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

_BASE65_MAPPING = "-.1032547698ACBEDGFIHKJMLONQPSRUTWVYXZ_acbedgfihkjmlonqpsrutwvyxz"
def _init_reverse_mapping():
    rm = [None for _ in xrange(256)]
    i = 0
    for c in _BASE65_MAPPING:
        rm[ord(c)] = i
        i += 1
    return rm
_BASE65_REVERSE_MAPPING = _init_reverse_mapping()
del _init_reverse_mapping

@returns(str)
@arguments(val=int)
def encode_int(val):
    res = StringIO()
    while val > 0:
        res.write(_BASE65_MAPPING[val % 65])
        val /= 65
    return res.getvalue()

@returns(int)
@arguments(val=str)
def decode_int(val):
    res = 0
    val = list(val)
    val.reverse()
    for c in val:
        res = _BASE65_REVERSE_MAPPING[ord(c)] + res * 65
    return res
