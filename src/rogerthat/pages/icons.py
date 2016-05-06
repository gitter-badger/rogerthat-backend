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

from rogerthat.bizz.service import get_icon_from_library, render_menu_icon, get_menu_icon
from rogerthat.dal.profile import get_profile_info
from rogerthat.dal.service import get_service_menu_item_by_coordinates
from rogerthat.rpc import users
from rogerthat.utils import parse_color
from mcfw.imaging import recolor_png
from rogerthat.utils.service import add_slash_default
from google.appengine.ext import webapp


class LibraryIconHandler(webapp.RequestHandler):

    def get(self, name):
        color = self.request.get("color", "000000")
        size = self.request.get("size", "50")
        if not color:
            color = "000000"
        color = parse_color(color)
        size = int(size)

        self.response.headers['Cache-Control'] = "public, max-age=31536000"  # Cache forever (1 year)
        self.response.headers['Content-Type'] = "image/png"
        self.response.out.write(recolor_png(get_icon_from_library(name, size), (0, 0, 0), color))

class IconHandler(webapp.RequestHandler):

    def get(self):
        if not "service" in self.request.GET:
            self.response.set_status(404)
            return
        service_identity_user = add_slash_default(users.User(self.request.GET["service"]))
        profile_info = get_profile_info(users.get_current_user(), skip_warning=True)
        app_user = None if profile_info.isServiceIdentity else users.get_current_user()

        coords = [int(x) for x in self.request.get("coords").split('x')]

        item = get_service_menu_item_by_coordinates(service_identity_user, coords)
        if item:
            self.response.headers['Content-Type'] = "image/png"
            icon = get_menu_icon(item, service_identity_user, app_user)[0]
            self.response.out.write(render_menu_icon(icon, 50))
        else:
            self.response.set_status(404)
