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

from rogerthat.dal import parent_key
from rogerthat.models import QRTemplate
from rogerthat.rpc import users
from rogerthat.rpc.service import ServiceApiException
from rogerthat.utils import png, now, parse_color
from google.appengine.ext import db
from mcfw.rpc import returns, arguments


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

class InvalidQRCodeBodyColorException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_QR + 1, "Invalid QR code color specification.")

class InvalidQRDescriptionException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_QR + 2, "Invalid QR code description.")

class InvalidQRTemplateSizeException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_QR + 3, "Invalid QR code template size.")


@returns(QRTemplate)
@arguments(user=users.User, png_stream=str, description=unicode, color=unicode, key_name=unicode)
def store_template(user, png_stream, description, color, key_name=None):
    # Validate color
    try:
        color = parse_color(color)
    except ValueError:
        raise InvalidQRCodeBodyColorException()
    # Validate description
    if not description or not description.strip():
        raise InvalidQRDescriptionException()
    # Validate png
    png_value = png_stream
    if png_stream:
        png_stream = StringIO(png_stream)
        reader = png.Reader(file=png_stream)
        img = reader.read()
        width, height, _, _ = img
        if width < 343 or height < 343:
            raise InvalidQRTemplateSizeException()
    # Store template
    if user:
        parent = parent_key(user)
    else:
        parent = None

    if key_name:
        template = QRTemplate(key=db.Key.from_path(QRTemplate.kind(), key_name, parent=parent),
                              description=description, body_color=list(color), timestamp=now())
    else:
        template = QRTemplate(parent=parent, description=description, body_color=list(color), timestamp=now())

    if png_value:
        template.blob = db.Blob(png_value)
    template.put()
    return template
