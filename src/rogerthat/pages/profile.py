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
import imghdr
import logging

import webapp2
from google.appengine.api import images
from google.appengine.api.images import BadRequestError
from google.appengine.ext import db
from google.appengine.runtime.apiproxy_errors import RequestTooLargeError

from rogerthat.bizz.profile import UNKNOWN_AVATAR
from rogerthat.dal import parent_key
from rogerthat.dal.profile import get_avatar_by_id, get_service_or_user_profile
from rogerthat.rpc import users
from rogerthat.rpc.models import TempBlob
from rogerthat.utils import now, azzert
from rogerthat.utils.channel import broadcast_via_iframe_result
from mcfw.cache import cached
from mcfw.rpc import returns, arguments


@returns(str)
@arguments(avatar_id=int, size=int)
def get_avatar(avatar_id, size=150):
    if avatar_id == -1:
        return UNKNOWN_AVATAR
    avatar = get_avatar_by_id(avatar_id)
    if avatar and avatar.picture:
        picture = str(avatar.picture)
        img = images.Image(picture)
        if img.width > size or img.height > size:
            img.resize(size, size)
            return img.execute_transforms(output_encoding=img.format)
        else:
            return picture
    else:
        return UNKNOWN_AVATAR

@cached(1, 24 * 60 * 60, False, True)
@returns(str)
@arguments(avatar_id=int, size=int)
def get_avatar_cached(avatar_id, size=150):
    return get_avatar(avatar_id, size)


class AvatarUploadRequestHandler(webapp2.RequestHandler):

    def post(self):
        try:
            user = users.get_current_user()
            tb = TempBlob(parent=parent_key(user))
            tb.timeout = now() + 24 * 60 * 60
            image = self.request.get("newAvatar")
            image_type = imghdr.what(None, image)
            try:
                img = images.Image(image)
                img.horizontal_flip()
                img.horizontal_flip()
                orig_width = img.width
                orig_height = img.height
                orig_image = image
                size = min(100, 100 * 4000 / max(orig_width, orig_height))  # max 4000 wide/high
                while len(image) > (1024 * 1024 - 100 * 1024):
                    size -= size / 10
                    img = images.Image(orig_image)
                    img.resize(orig_width * size / 100, orig_height * size / 100)
                    image = img.execute_transforms(images.JPEG if image_type == 'jpeg' else images.PNG)

                tb.blob = db.Blob(image)
            except images.NotImageError:
                logging.info("Sending failure to the logged on users (%s) channel" % user.email())
                self.response.out.write(broadcast_via_iframe_result(u"rogerthat.profile.avatar_upload_failed", error=u"The uploaded file is not an image!"))
                return
            except IOError, e:
                logging.info("Sending failure to the logged on users (%s) channel" % user.email())
                self.response.out.write(broadcast_via_iframe_result(u"rogerthat.profile.avatar_upload_failed", error=e.message))
                return
            except BadRequestError, e:
                logging.info("Sending failure to the logged on users (%s) channel" % user.email())
                self.response.out.write(broadcast_via_iframe_result(u"rogerthat.profile.avatar_upload_failed",
                                                                    error=e.message))
                return
            try:
                tb.put()
            except RequestTooLargeError:
                logging.info("Sending failure to the logged on users (%s) channel" % user.email())
                self.response.out.write(broadcast_via_iframe_result(u"rogerthat.profile.avatar_upload_failed", error=u"The picture size is too large. Picture should be smaller than 750 KB."))
                return
            logging.info("Sending result to the logged on users (%s) channel" % user.email())
            self.response.out.write(broadcast_via_iframe_result(u"rogerthat.profile.avatar_uploaded", key=str(tb.key())))
        except:
            logging.exception("Sending failure to the logged on users (%s) channel" % user.email())
            self.response.out.write(broadcast_via_iframe_result(u"rogerthat.profile.avatar_upload_failed", error=u"Imaging system failed for indeterminable reasons."))
            return


class TempAvatarRequestHandler(webapp2.RequestHandler):

    def get(self):
        user = users.get_current_user()
        key = self.request.GET['key']
        tb = TempBlob.get(key)
        azzert(tb.parent_key() == parent_key(user))
        self.response.headers['Content-Type'] = "image/png"
        self.response.out.write(tb.blob)


class GetMyAvatarHandler(webapp2.RequestHandler):

    def get(self):
        user_email = self.request.get('user')
        if not user_email:
            self.error(500)
            logging.error("user not provided")
            return
        user = users.User(user_email)
        if user != users.get_current_user():
            session = users.get_current_session()
            if not session.has_access(user_email):
                self.error(500)
                logging.error("Logged in user %s does not have access to %s", session.user, user_email)
                return
        profile = get_service_or_user_profile(user)
        self.response.headers['Content-Type'] = "image/png"
        avatarId = -1 if not profile or not profile.avatarId else profile.avatarId
        self.response.out.write(get_avatar_cached(avatarId))


class GetCachedAvatarHandler(webapp2.RequestHandler):

    def get(self, avatar_id):
        self.response.headers['Cache-Control'] = "public, max-age=86400"
        self.response.headers['Access-Control-Allow-Origin'] = "*"
        avatar = get_avatar_cached(int(avatar_id))
        if self.request.get('base64'):
            self.response.headers['Content-Type'] = "text/plain"
            self.response.out.write(base64.b64encode(avatar))
        else:
            self.response.headers['Content-Type'] = "image/png"
            self.response.out.write(avatar)


class GetAvatarHandler(webapp2.RequestHandler):

    def get(self, avatar_id):
        self.response.headers['Content-Type'] = "image/png"
        self.response.out.write(get_avatar(int(avatar_id)))
