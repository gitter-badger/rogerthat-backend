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

import base64
import json
import logging

import webapp2

from rogerthat.bizz.messaging import assemble_transfer_from_chunks
from rogerthat.dal.messaging import get_transfer_result
from rogerthat.utils import azzert


class ServiceDownloadPhotoHandler(webapp2.RequestHandler):

    def get(self, info):
        try:
            padding = ""
            while True:
                try:
                    data = base64.b64decode(info + padding)
                    break
                except TypeError:
                    if len(padding) < 2:
                        padding += "="
                    else:
                        raise
            json_params = json.loads(data)

            parent_message_key = json_params['parent_message_key']
            message_key = json_params['message_key']

            azzert(message_key, "message_key is required")

            if parent_message_key == "":
                parent_message_key = None
        except:
            logging.exception("Error in ServiceDownloadPhotoHandler")
            self.error(404)
            return

        logging.debug("Download photo %s %s" % (parent_message_key, message_key))
        photo_upload_result = get_transfer_result(parent_message_key, message_key)
        if not photo_upload_result:
            self.error(404)
            return

        azzert(photo_upload_result.status == photo_upload_result.STATUS_VERIFIED)
        self.response.headers['Content-Type'] = "image/jpeg" if photo_upload_result.content_type == None else str(photo_upload_result.content_type)
        self.response.out.write(assemble_transfer_from_chunks(photo_upload_result.key()))
