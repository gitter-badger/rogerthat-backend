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

from rogerthat.bizz.js_embedding import get_js_embedding_packets_disk, deploy_new_js_embedding
from rogerthat.models import JSEmbedding
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template


class JSEmbeddingTools(webapp.RequestHandler):

    def get(self):
        result = self.request.get("result", None)
        packetsDb = JSEmbedding.all()
        packetsDisk = get_js_embedding_packets_disk()
        args = {"packets_db": packetsDb,
                "packets_disk": packetsDisk,
                "result": result,
                }
        path = os.path.join(os.path.dirname(__file__), 'js_embedding.html')
        self.response.out.write(template.render(path, args))


class DeployJSEmbeddingHandler(webapp.RequestHandler):
    def post(self):
        deploy_new_js_embedding()
        self.redirect("/mobiadmin/js_embedding?%s" % urllib.urlencode((("result", "Deploying new js embedding!"),)))
