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
import urllib

from rogerthat.templates import render
from rogerthat.translations import DEFAULT_LANGUAGE
from rogerthat.utils import azzert
from rogerthat.utils.channel import broadcast_via_iframe_result
from rogerthat.utils.crypto import md5_hex
from google.appengine.ext import blobstore, webapp
from google.appengine.ext.webapp import blobstore_handlers, template


_BASE_DIR = os.path.dirname(__file__)

class MessageHandler(webapp.RequestHandler):

    def get(self):
        user_agent = self.request.environ['HTTP_USER_AGENT']
        mobile = "Android" in user_agent or "iPhone" in user_agent or 'iPad' in user_agent or 'iPod' in user_agent
        message = self.request.get("message", "Thank you for using Rogerthat!")
        path = os.path.join(_BASE_DIR, 'message.html')
        self.response.out.write(template.render(path, {'message': message, "mobile": mobile}))


class MessageHistoryHandler(webapp.RequestHandler):

    def get(self):
        member_email = self.request.GET.get('member')
        azzert(member_email)

#        user = users.get_current_user()
#        member = users.User(member_email)
#        TODO: check friend relation between user & member

        params = dict(container_id='messageHistory_%s' % md5_hex(member_email), query_param=member_email, query_type='message_history')
        self.response.out.write(render('message_query', [DEFAULT_LANGUAGE], params, 'web'))

class PhotoUploadUploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        upload_files = self.get_uploads('file')
        blob_info = upload_files[0]
        self.response.out.write(broadcast_via_iframe_result(u"rogerthat.messaging.photo_upload_done", downloadUrl=u"/mobi/message/photo_upload/get/%s" % blob_info.key()))

class PhotoUploadDownloadHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, resource):
        resource = str(urllib.unquote(resource))
        blob_info = blobstore.BlobInfo.get(resource)
        self.send_blob(blob_info)
