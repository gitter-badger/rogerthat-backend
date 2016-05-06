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
import sys

from rogerthat.bizz.branding import store_branding, BrandingValidationException, is_branding, TYPE_BRANDING, \
    BadBrandingZipException
from rogerthat.bizz.profile import create_service_profile
from rogerthat.rpc import users
import mc_unittest


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


class Test(mc_unittest.TestCase):

    def _prepare_user(self):
        user = users.User('testService@foo.com')
        create_service_profile(user, u"Testen he pol2")
        return user

    def testUser(self):
        # User has no profile, should throw AssertionError
        stream = StringIO()
        self.assertRaises(AssertionError, store_branding, users.User('not_existing_user@example.com'), stream, "test")

        # User is not a service, should throw AssertionError
        user1 = users.get_current_user()
        self.assertRaises(AssertionError, store_branding, user1, stream, "test")

    def testValidZip(self):
        if sys.platform == "win32":
            return

        user = self._prepare_user()
        stream = StringIO()
        # stream is not a zip, should throw BrandingValidationException
        self.assertRaises(BadBrandingZipException, store_branding, user, stream, "test")

        # stream is a valid zip
        filename = os.path.join(os.path.dirname(__file__), "nuntiuz.zip")
        stream.write(open(filename).read())
        stream.seek(0)
        store_branding(user, stream, "test")
        stream.seek(0)
        self.assertTrue(is_branding(stream.read(), TYPE_BRANDING))

    def testExternalLinks(self):
        if sys.platform == "win32":
            return

        user = self._prepare_user()
        # stream is a valid zip with a external link in the branding
        filename = os.path.join(os.path.dirname(__file__), "nuntiuz_with_external_link.zip")
        stream = StringIO()
        stream.write(open(filename).read())
        self.assertRaises(BrandingValidationException, store_branding, user, stream, "test")
        stream.seek(0)
        self.assertFalse(is_branding(stream.read(), TYPE_BRANDING))

    def testScriptTags(self):
        if sys.platform == "win32":
            return

        user = self._prepare_user()
        # stream is a valid zip with a script tag in the branding
        filename = os.path.join(os.path.dirname(__file__), "nuntiuz_with_script_tag.zip")
        stream = StringIO()
        stream.write(open(filename).read())
        self.assertRaises(BrandingValidationException, store_branding, user, stream, "test")
        stream.seek(0)
        self.assertFalse(is_branding(stream.read(), TYPE_BRANDING))

    def testInvalidFilename(self):
        if sys.platform == "win32":
            return

        user = self._prepare_user()
        # stream is a valid zip with a script tag in the branding
        filename = os.path.join(os.path.dirname(__file__), "nuntiuz_with_invalid_branding_filename.zip")
        stream = StringIO()
        stream.write(open(filename).read())
        self.assertRaises(BrandingValidationException, store_branding, user, stream, "test")
        stream.seek(0)
        self.assertFalse(is_branding(stream.read(), TYPE_BRANDING))

    def testTooLarge(self):
        if sys.platform == "win32":
            return

        user = self._prepare_user()
        # stream is a valid zip which is too large
        filename = os.path.join(os.path.dirname(__file__), "nuntiuz_bigger.zip")
        stream = StringIO()
        stream.write(open(filename).read())
        self.assertRaises(BrandingValidationException, store_branding, user, stream, "test")
        stream.seek(0)
        self.assertFalse(is_branding(stream.read(), TYPE_BRANDING))

    def testPokes(self):
        if sys.platform == "win32":
            return

        user = self._prepare_user()
        # stream is a valid zip with pokes
        filename = os.path.join(os.path.dirname(__file__), "nuntiuz_poke_tags.zip")
        stream = StringIO()
        stream.write(open(filename).read())
        b = store_branding(user, stream, "test")
        self.assertIsNotNone(b.menu_item_color)
        stream.seek(0)
        self.assertTrue(is_branding(stream.read(), TYPE_BRANDING))

    def testValidMenuItemColor(self):
        if sys.platform == "win32":
            return

        user = self._prepare_user()
        # stream is a valid zip with pokes
        filename = os.path.join(os.path.dirname(__file__), "nuntiuz_with_rt_styles.zip")
        stream = StringIO()
        stream.write(open(filename).read())
        b = store_branding(user, stream, "test")
        self.assertEqual("999999", b.menu_item_color)
        stream.seek(0)
        self.assertTrue(is_branding(stream.read(), TYPE_BRANDING))

    def testInvalidMenuItemColor(self):
        if sys.platform == "win32":
            return

        user = self._prepare_user()
        # stream is a valid zip with pokes
        filename = os.path.join(os.path.dirname(__file__), "nuntiuz_with_invalid_menu_item_color.zip")
        stream = StringIO()
        stream.write(open(filename).read())
        self.assertRaises(BrandingValidationException, store_branding, user, stream, "test")
        stream.seek(0)
        self.assertFalse(is_branding(stream.read(), TYPE_BRANDING))

    def testDotHacked(self):
        if sys.platform == "win32":
            return

        user = self._prepare_user()
        # stream is a valid zip with pokes
        filename = os.path.join(os.path.dirname(__file__), "nuntiuz_with_dot_hacked.zip")
        stream = StringIO()
        stream.write(open(filename).read())
        self.assertRaises(BrandingValidationException, store_branding, user, stream, "test")
        stream.seek(0)
        self.assertFalse(is_branding(stream.read(), TYPE_BRANDING))
