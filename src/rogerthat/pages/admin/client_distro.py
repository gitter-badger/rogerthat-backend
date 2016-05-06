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
import time

from rogerthat.bizz.system import publish_client_app
from rogerthat.consts import DEBUG
from rogerthat.dal.mobile import get_active_mobiles
from rogerthat.models import ClientDistro
from rogerthat.rpc.models import Mobile
from rogerthat.utils import azzert
from rogerthat.utils.models import addId
from google.appengine.api import users
from google.appengine.api.users import create_logout_url
from google.appengine.ext import webapp, blobstore
from google.appengine.ext.webapp import template, blobstore_handlers


class ClientDistroPage(webapp.RequestHandler):

    def get(self):
        user = users.get_current_user()
        path = os.path.join(os.path.dirname(__file__), 'distros.html')
        self.response.out.write(template.render(path, {
            'debug':DEBUG,
            'user':user,
            'upload_url':blobstore.create_upload_url('/mobiadmin/distros/post'),
            'session':create_logout_url("/"),
            'distros':(addId(d) for d in ClientDistro.all().order("-timestamp"))}))

class ClientDistroPostHandler(blobstore_handlers.BlobstoreUploadHandler):

    def post(self):
        version = self.request.get("version")
        version_parts = version.split('.')
        azzert(len(version_parts) == 2)
        azzert(version == '.'.join((unicode(p) for p in (int(p) for p in version_parts))))
        cd = ClientDistro()
        cd.user = users.get_current_user()
        cd.timestamp = int(time.time())
        cd.type = int(self.request.get("type"))
        cd.version = version
        cd.releaseNotes = self.request.get("notes")
        cd.package = self.get_uploads("package")[0]
        cd.put()
        self.redirect('/mobiadmin/distros')

class GetClientDistroPackageHandler(blobstore_handlers.BlobstoreDownloadHandler):

    def get(self, id_):
        distro = ClientDistro.get_by_id(int(id_))
        resource = distro.package.key()
        blob_info = blobstore.BlobInfo.get(resource)
        self.send_blob(blob_info, content_type="application/vnd.android.package-archive", save_as="rogerthat." + distro.version + ".apk")

class Publish(webapp.RequestHandler):

    def post(self):
        id_ = int(self.request.POST['id'])
        recipients = self.request.POST['to'].split(',')

        if 'all' in recipients:
            userz = list(set([m.user for m in get_active_mobiles() if m.type == Mobile.TYPE_ANDROID_HTTP]))
        else:
            userz = list()
            if "geert" in recipients:
                userz.append(users.User('geert@example.com'))

        distro = ClientDistro.get_by_id(id_)
        publish_client_app(distro, userz)
