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

import logging

from rogerthat.models import JSEmbedding
from rogerthat.pages import UserAwareRequestHandler


class JSEmbeddingDownloadHandler(UserAwareRequestHandler):

    def get(self, packetName):
        if not self.set_user():
            self.error(500)
            return
        self.response.headers['Content-Type'] = "application/zip"
        self.response.headers['Content-Disposition'] = 'attachment; filename=js_embedding_%s.zip' % packetName
        jse = JSEmbedding.get_by_key_name(packetName)
        if jse:
            self.response.out.write(jse.content)
        else:
            logging.error("JSEmbeddingDownloadHandler failed because %s does not exists." % packetName)
            self.error(404)

    post = get
