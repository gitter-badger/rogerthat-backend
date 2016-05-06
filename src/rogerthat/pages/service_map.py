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

import os

from rogerthat.settings import get_server_settings
from google.appengine.ext.webapp import template
import webapp2


class ServiceMapHandler(webapp2.RequestHandler):

    def get(self):
        path = os.path.join(os.path.dirname(__file__), "service_map.html")
        settings = get_server_settings()
        self.response.out.write(template.render(path, {'maps_key':settings.googleMapsKey}))
