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

from mcfw.properties import unicode_property, long_property, typed_property


class QRTemplateTO(object):
    id = unicode_property('1')
    description = unicode_property('2')
    color = unicode_property('3')
    timestamp = long_property('4')

    @staticmethod
    def fromDBQRTemplate(template):
        b = QRTemplateTO()
        b.id = u"qr%X" % template.key().id()
        b.description = template.description
        b.timestamp = template.timestamp
        b.color = u"".join(("%X" % c).rjust(2, '0') for c in template.body_color)
        return b

class QRTemplateListResultTO(object):
    cursor = unicode_property('1')
    templates = typed_property('2', QRTemplateTO, True)


class QRTemplateWithFileTO(object):
    description = unicode_property('1')
    color = unicode_property('2')
    template = unicode_property('3')  # Base64 encoded image

    @classmethod
    def create(cls, description, color, template):
        to = cls()
        to.description = description
        to.color = color
        to.template = unicode(template)
        return to
