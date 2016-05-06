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

from mcfw.properties import long_property, unicode_property, unicode_list_property, bool_property


class CodeTO(object):
    id = long_property('1')
    timestamp = long_property('2')
    author = unicode_property('3')
    name = unicode_property('4')
    source = unicode_property('5')
    functions = unicode_list_property('6')
    version = long_property('7')
    compile_error = unicode_property('8')
    
    @staticmethod
    def fromDBCode(code):
        ct = CodeTO()
        ct.id = code.key().id()
        ct.timestamp = code.timestamp
        ct.author = unicode(code.author.email())
        ct.name = code.name
        ct.source = code.source
        ct.functions = code.functions
        ct.version = code.version
        ct.compile_error = None
        return ct
    
class RunResultTO(object):
    result = unicode_property('1')
    succeeded = bool_property('2')
    time = long_property('3')
