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

from rogerthat.utils.cookie import parse_cookie
from google.appengine.ext import webapp
from rogerthat.settings import get_server_settings


class QRInstallRequestHandler(webapp.RequestHandler):

    def redirect(self, url, permanent=False):
        return super(QRInstallRequestHandler, self).redirect(str(url), permanent)

    def get(self):
        server_settings = get_server_settings()
        cookie = self.request.cookies.get(server_settings.cookieQRScanName)
        if cookie:
            scan_url = parse_cookie(cookie)
            self.redirect(scan_url)
        else:
            self.redirect("rogerthat://i/qr?success=false")
