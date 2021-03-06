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

from mcfw.rpc import arguments, returns


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

_BASE38_MAPPING = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-."
def _init_reverse_mapping():
    rm = [None for _ in xrange(256)]
    i = 0
    for c in _BASE38_MAPPING:
        rm[ord(c)] = i
        i += 1
    return rm
_BASE38_REVERSE_MAPPING = _init_reverse_mapping()
del _init_reverse_mapping

@returns(str)
@arguments(val=int)
def encode_int(val):
    res = StringIO()
    while val > 0:
        res.write(_BASE38_MAPPING[val % 38])
        val /= 38
    return res.getvalue()

@returns(int)
@arguments(val=str)
def decode_int(val):
    res = 0
    val = list(val)
    val.reverse()
    for c in val:
        res = _BASE38_REVERSE_MAPPING[ord(c)] + res * 38
    return res

@returns(bool)
@arguments(val=str)
def is_base38(val):
    chars = set(list(val))
    return chars.issubset(set(list(_BASE38_MAPPING)))

@returns(str)
@arguments(val=str)
def filter_unknown_base38_chars(val):
    filterd_chars = [char for char in list(val) if char in _BASE38_MAPPING]
    return ''.join(filterd_chars)
