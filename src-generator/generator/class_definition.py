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

from mcfw.consts import MISSING


class ClassDefinition(object):

    def __init__(self, name=None, package=None, super_class=None, fields=None, doc=None):
        self.name = name
        if package.startswith('rogerthat.'):
            package = package.replace('rogerthat.', 'com.mobicage.', 1)
        self.package = package
        self.super_class = super_class
        self.fields = fields or list()
        self.doc = doc

    @property
    def full_name(self):
        return "%s.%s" % (self.package, self.name)

    def __str__(self):
        return self.full_name

    __repr__ = __str__


class AttrDefinition(object):

    def __init__(self, name=None, type_=None, collection_type=None, doc=None, default=MISSING):
        self.name = name
        if type_.startswith('rogerthat.'):
            type_ = type_.replace('rogerthat.', 'com.mobicage.', 1)
        self.type = type_
        self.collection_type = collection_type  # eg. map/set/list/tuple/...
        self.doc = doc
        self.default = default

    def __str__(self):
        return "%s %s" % (self.type, self.name)

    __repr__ = __str__

class FunctionDefinition(object):

    def __init__(self, name=None, rtype=None, args=None):
        self.name = name
        self.rtype = rtype
        self.args = args or list()

class PackageDefinition(object):

    def __init__(self, name=None, functions=None):
        self.name = name
        self.functions = functions or list()
