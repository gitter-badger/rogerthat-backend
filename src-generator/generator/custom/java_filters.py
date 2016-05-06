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

from django import template
from mcfw.consts import MISSING
register = template.Library()

JAVA_TYPE_MAPPING = {'unicode': 'String',
                     'bool':    'boolean',
                     'float':   'float',
                     'int':     'long',
                     'long':    'long'}

@register.filter
def java_map_type(value):
    return JAVA_TYPE_MAPPING.get(value, value)

@register.filter
def java_cast(value, var):
    if value == 'float':
        return "((Float) %s).floatValue()" % var
    if value in ('int', 'long'):
        return "((Long) %s).longValue()" % var
    if value == 'bool':
        return "((Boolean) %s).booleanValue()" % var
    return "(%s) %s" % (java_map_type(value), var)

@register.filter
def java_has_complex_field(class_def):
    for field in class_def.fields:
        if field.type not in JAVA_TYPE_MAPPING.keys():
            return True
    return False

@register.filter
def java_has_list_field(class_def):
    for field in class_def.fields:
        if field.collection_type:
            return True
    return False

@register.filter
def java_default_value(field):
    if field.default == MISSING:
        raise Exception("There is no default value (field: %s)" % field.name)

    if field.default is None:
        return 'null'
    if field.collection_type:
        return "new %s[0]" % JAVA_TYPE_MAPPING.get(field.type, field.type)

    if field.type not in JAVA_TYPE_MAPPING:
        raise Exception("field.type (%s) not in JAVA_TYPE_MAPPING" % field.type)

    if field.type == 'unicode':
        return '"%s"' % field.default
    if field.type == 'bool':
        return 'true' if field.default else 'false'
    return field.default
