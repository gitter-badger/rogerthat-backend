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

import imghdr
import logging
import os.path

from rogerthat.bizz.service.branding_editor import render_branding_html, generate_branding, COLOR_BLACK, \
    get_branding_editor_logo_key, LOGO_MAX_SIZE, set_logo, webcolor_to_color_tuple, get_configuration
from rogerthat.dal import parent_key
from rogerthat.dal.service import get_default_service_identity
from rogerthat.models import Branding
from rogerthat.rpc import users
from rogerthat.rpc.models import TempBlob
from rogerthat.rpc.service import BusinessException
from rogerthat.to import ReturnStatusTO, RETURNSTATUS_TO_SUCCESS
from rogerthat.to.branding import BrandingEditorConfigurationTO
from rogerthat.utils import azzert, now
from mcfw.imaging import recolor_png
from rogerthat.utils.channel import broadcast_via_iframe_result
from google.appengine.api import images
from google.appengine.ext import db
from google.appengine.runtime.apiproxy_errors import RequestTooLargeError
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments
import webapp2


class BrandingEditorPreviewHandler(webapp2.RequestHandler):

    def get(self, version, page):
        if int(version) > 0:
            self.response.headers['Cache-Control'] = "public, max-age=31536000"  # Cache forever (1 year)
        if page not in ('branding.html', 'logo.jpg', 'frame.png'):
            logging.warning("%s not found in branding editor" % page)
            self.error(404)
            return
        _, extension = os.path.splitext(page.lower())
        if extension in (".jpg", ".jpeg"):
            self.response.headers['Content-Type'] = "image/jpeg"
        elif extension == ".png":
            self.response.headers['Content-Type'] = "image/png"
        elif extension == ".css":
            self.response.headers['Content-Type'] = "text/css"

        if page == "branding.html":
            content, _ = render_branding_html(self.request.get("color_scheme", Branding.COLOR_SCHEME_DARK),
                                              self.request.get("background_color", "000000"),
                                              self.request.get("text_color", "FFFFFF"),
                                              self.request.get("menu_item_color", "FFFFFF"),
                                              self.request.get("show_header", "false") == "true")
            logging.debug("branding.html: %s" % content)
        else:
            with open(os.path.join(os.path.dirname(__file__), page)) as f:
                content = f.read()
            target_color = self.request.get("color")
            if target_color and target_color != COLOR_BLACK:
                logging.debug("Re-coloring PNG to %s" % str(webcolor_to_color_tuple(target_color)))
                content = recolor_png(content, webcolor_to_color_tuple(COLOR_BLACK), webcolor_to_color_tuple(target_color))

        if self.request.get('xrender', 'false') == 'true':
            from lxml import html, etree
            doc = html.fromstring(content)
            service_identity = None
            for elem in doc.xpath("//nuntiuz_identity_name"):
                service_identity = service_identity or get_default_service_identity(users.get_current_user())
                parent = elem.getparent()
                elem.drop_tree()
                parent.text = service_identity.name
            self.response.out.write(etree.tostring(doc))  # @UndefinedVariable
        else:
            self.response.out.write(content)

class GetTmpBrandingEditorLogoHandler(webapp2.RequestHandler):
    def get(self):
        logging.debug("GetTmpBrandingEditorLogoHandler.get")
        user = users.get_current_user()
        tb = TempBlob.get(get_branding_editor_logo_key(user))
        azzert(tb.parent_key() == parent_key(user))
        self.response.headers['Content-Type'] = "image/png"
        self.response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        self.response.headers["Pragma"] = "no-cache"
        self.response.headers["Expires"] = "0"
        self.response.out.write(tb.blob)

class UploadBrandingEditorLogoHandler(webapp2.RequestHandler):
    def post(self):
        try:
            logging.debug("UploadBrandingEditorLogoHandler.post")
            user = users.get_current_user()
            tb = TempBlob(key=get_branding_editor_logo_key(user))
            tb.timeout = now() + 86400
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
                while len(image) > LOGO_MAX_SIZE:
                    size -= size / 10
                    img = images.Image(orig_image)
                    img.resize(orig_width * size / 100, orig_height * size / 100)
                    image = img.execute_transforms(images.JPEG if image_type == 'jpeg' else images.PNG)
                tb.blob = db.Blob(image)
            except images.NotImageError:
                logging.info("Sending failure to the logged on users (%s) channel" % user.email())
                self.response.out.write(broadcast_via_iframe_result(u"rogerthat.bizz.service.branding_editor.logo_upload_failed",
                                                                    error=u"The uploaded file is not an image!"))
                return
            except IOError, e:
                logging.info("Sending failure to the logged on users (%s) channel" % user.email())
                self.response.out.write(broadcast_via_iframe_result(u"rogerthat.bizz.service.branding_editor.logo_upload_failed",
                                                                    error=e.message))
                return
            try:
                tb.put()
            except RequestTooLargeError:
                logging.info("Sending failure to the logged on users (%s) channel" % user.email())
                self.response.out.write(broadcast_via_iframe_result(u"rogerthat.bizz.service.branding_editor.logo_upload_failed",
                                                                    error=u"The picture size is too large. Picture should be smaller than 750 KB."))
                return
            logging.info("Sending result to the logged on users (%s) channel" % user.email())
            self.response.out.write(broadcast_via_iframe_result(u"rogerthat.bizz.service.branding_editor.logo_uploaded",
                                                                key=str(tb.key())))
        except:
            logging.exception("Sending failure to the logged on users (%s) channel" % user.email())
            self.response.out.write(broadcast_via_iframe_result(u"rogerthat.bizz.service.branding_editor.logo_upload_failed",
                                                                error=u"Imaging system failed for indeterminable reasons."))
            return

@rest('/mobi/service/branding/editor/save', 'post')
@returns(ReturnStatusTO)
@arguments(description=unicode, color_scheme=unicode, background_color=unicode, text_color=unicode,
           menu_item_color=unicode, show_header=bool, static_content_mode=unicode, static_content=unicode,
           use_uploaded_logo=bool)
def branding_editor_save(description, color_scheme, background_color, text_color, menu_item_color, show_header,
                         static_content_mode, static_content, use_uploaded_logo):
    try:
        branding = generate_branding(users.get_current_user(), description, color_scheme, background_color or None,
                                     text_color or None, menu_item_color or None, show_header, static_content_mode,
                                     static_content, use_uploaded_logo)
        logging.debug("Generated branding: %s" % branding.key().name())
        return RETURNSTATUS_TO_SUCCESS
    except BusinessException, be:
        logging.exception("Failed to generate branding with branding designer")
        return ReturnStatusTO.create(False, "Failed to create branding (%s)" % be.message)


@rest("/mobi/service/branding/editor/update_logo", "post")
@returns(unicode)
@arguments(tmp_avatar_key=unicode, x1=(float, int), y1=(float, int), x2=(float, int), y2=(float, int))
def update_logo(tmp_avatar_key, x1, y1, x2, y2):
    if not tmp_avatar_key:
        logging.info("No tmp_avatar_key. Service user pressed save without changing his logo.")
        return "Please select a picture"
    service_user = users.get_current_user()
    x1 = float(x1)
    x2 = float(x2)
    y1 = float(y1)
    y2 = float(y2)
    try:
        set_logo(service_user, tmp_avatar_key, x1, y1, x2, y2)
    except Exception, e:
        logging.exception(e)
        return e.message

@rest("/mobi/service/branding/editor/cfg", "get")
@returns(BrandingEditorConfigurationTO)
@arguments(branding_hash=unicode)
def branding_editor_configuration(branding_hash):
    model = get_configuration(users.get_current_user(), branding_hash)
    return BrandingEditorConfigurationTO.fromModel(model)
