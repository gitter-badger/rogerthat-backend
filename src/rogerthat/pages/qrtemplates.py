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

from cgi import FieldStorage
import logging
import os

from google.appengine.ext import webapp

from rogerthat.bizz.qrtemplate import store_template
from rogerthat.bizz.system import qrcode
from rogerthat.dal import parent_key
from rogerthat.models import QRTemplate
from rogerthat.rpc import users
from rogerthat.rpc.service import ServiceApiException
from rogerthat.settings import get_server_settings
from rogerthat.utils.channel import broadcast_via_iframe_result


CURRENT_DIR = os.path.dirname(__file__)

class PostQRTemplateHandler(webapp.RequestHandler):

    def post(self):
        user = users.get_current_user()
        try:
            file_ = self.request.POST.get('file')
            description = self.request.POST.get("description")
            color = self.request.POST.get("color")
            file_ = file_.file.getvalue() if isinstance(file_, FieldStorage) else None
            store_template(user, file_, description, color)
            self.response.out.write(broadcast_via_iframe_result(u'rogerthat.store_qr_template.post_result'))
        except ServiceApiException, e:
            self.response.out.write(broadcast_via_iframe_result(u'rogerthat.store_qr_template.post_result',
                                                                error=e.message, error_code=e.code))
        except:
            self.response.out.write(broadcast_via_iframe_result(u'rogerthat.store_qr_template.post_result',
                                                                error=u"Unknown error has occurred."))
            logging.exception("Failure while receiving qr template.")

class TemplateExampleHandler(webapp.RequestHandler):

    def get(self):
        user = users.get_current_user()
        template_id = self.request.get("template_id")
        logging.info(template_id)
        template = QRTemplate.get_by_id(int(template_id[2:], 16), parent_key(user))
        self.response.headers['Content-Type'] = "image/png"
        logging.info(map(int, template.body_color))
        url = "%s/" % get_server_settings().baseUrl
        self.response.out.write(qrcode(url, template.blob, map(int, template.body_color), True))
