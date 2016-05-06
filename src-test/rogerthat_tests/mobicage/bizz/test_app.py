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

from rogerthat_tests import set_current_user, register_tst_mobile, set_current_mobile

from rogerthat.bizz.friends import canBeFriends, makeFriends, breakFriendShip, areFriends, invite, ORIGIN_USER_INVITE
from rogerthat.bizz.profile import create_user_profile, create_service_profile
from rogerthat.bizz.service import convert_user_to_service, create_service_identity
from rogerthat.dal.profile import is_service_identity_user
from rogerthat.dal.service import get_default_service_identity, get_service_identity
from rogerthat.models import App
from rogerthat.rpc import users
from rogerthat.to.service import ServiceIdentityDetailsTO
from rogerthat.utils import azzert
from rogerthat.utils.app import create_app_user, get_app_user_tuple, get_app_user_tuple_by_email, \
    get_human_user_from_app_user, get_app_id_from_app_user
from rogerthat.utils.service import create_service_identity_user
import mc_unittest


class TestApp(mc_unittest.TestCase):

    def _test_rogerthat_app_user(self, human_user, app_id, si):
        app_user = create_app_user(human_user, app_id)

        email = human_user.email()

        if app_id == App.APP_ID_ROGERTHAT:
            self.assertEqual(email, app_user.email())
        else:
            self.assertEqual("%s:%s" % (email, app_id), app_user.email())

        self.assertEqual((human_user, app_id), get_app_user_tuple(app_user))
        self.assertEqual((human_user, app_id), get_app_user_tuple_by_email(app_user.email()))
        self.assertEqual(human_user, get_human_user_from_app_user(app_user))
        self.assertEqual(app_id, get_app_id_from_app_user(app_user))

        user_profile = create_user_profile(app_user, email)
        self.assertEqual(app_user, user_profile.user)

        self.assertEqual(app_id == App.APP_ID_ROGERTHAT, canBeFriends(si, user_profile))
        self.assertEqual(app_id == App.APP_ID_ROGERTHAT, canBeFriends(user_profile, si))

        if app_id == App.APP_ID_ROGERTHAT:
            makeFriends(app_user, si.user, None, None, None, False, False)
        else:
            self.assertRaises(Exception, makeFriends, app_user, si.user, None, None, None, False, False)

        self.assertEqual(app_id == App.APP_ID_ROGERTHAT, areFriends(user_profile, si))

        breakFriendShip(app_user, si.user)
        self.assertFalse(areFriends(user_profile, si))

        return app_user, user_profile

    def _create_service_identity(self):
        service_user = users.get_current_user()
        convert_user_to_service(service_user)
        si = get_default_service_identity(service_user)
        return si

    def test_rogerthat_app(self):
        self.set_datastore_hr_probability(1)

        # creating a service
        si = self._create_service_identity()

        human_user = users.User(u"bart@example.com")
        rogerthat_app_user, rogerthat_user_profile = self._test_rogerthat_app_user(human_user, "rogerthat", si)
        lochristi_app_user, lochristi_user_profile = self._test_rogerthat_app_user(human_user, "be-loc", si)

        self.assertFalse(canBeFriends(rogerthat_user_profile, lochristi_user_profile))

        self.assertRaises(Exception, makeFriends, rogerthat_app_user, lochristi_app_user, None, None, None, False, False)
        self.assertRaises(Exception, makeFriends, lochristi_app_user, rogerthat_app_user, None, None, None, False, False)

    def test_current_app(self):
        app_id = "be-loc"
        app_user = create_app_user(users.User(u"bart@example.com"), app_id)
        set_current_user(app_user, skip_create_session=True)
        self.assertEqual(app_id, users.get_current_app_id())

        app_id = "rogerthat"
        app_user = create_app_user(users.User(u"bart@example.com"), app_id)
        set_current_user(app_user, skip_create_session=True)
        self.assertEqual(app_id, users.get_current_app_id())

    def test_multiple_app_users_for_service(self):
        app_id_rogerthat = "rogerthat"
        app_user_rogerthat = create_app_user(users.User(u"bart@example.com"), app_id_rogerthat)
        app_user_rogerthat_profile = create_user_profile(app_user_rogerthat, "app_user_rogerthat")
        self.assertEqual(app_user_rogerthat, app_user_rogerthat_profile.user)
        set_current_user(app_user_rogerthat)
        self.assertEqual(app_id_rogerthat, users.get_current_app_id())

        app_id_lochristi = "be-loc"
        app_user_lochristi = create_app_user(users.User(u"bart@example.com"), app_id_lochristi)
        app_user_lochristi_profile = create_user_profile(app_user_lochristi, "app_user_lochristi")
        self.assertEqual(app_user_lochristi, app_user_lochristi_profile.user)
        set_current_user(app_user_lochristi)
        self.assertEqual(app_id_lochristi, users.get_current_app_id())

        legacy_svc_identity_user = users.User(u"info@example.com")

        create_service_profile(legacy_svc_identity_user, legacy_svc_identity_user.email())
        self.assertTrue(is_service_identity_user(legacy_svc_identity_user))
        set_current_user(legacy_svc_identity_user)

        svc_identity_user = create_service_identity_user(legacy_svc_identity_user, 'subservice')

        to = ServiceIdentityDetailsTO()
        to.app_data = None
        to.identifier = u'subservice'
        to.name = u'Sub service'
        to.created = 100000
        to.qualified_identifier = to.description = to.description_branding = to.menu_branding = to.phone_number = \
            to.phone_call_popup = to.search_config = None
        to.admin_emails = list()
        to.recommend_enabled = False
        to.description_use_default = to.description_branding_use_default = to.menu_branding_use_default = \
            to.phone_number_use_default = to.phone_call_popup_use_default = to.search_use_default = \
            to.email_statistics_use_default = to.app_ids_use_default = False
        to.email_statistics = False
        to.beacons = list()
        to.app_ids = list()
        to.beacon_auto_invite = True
        to.content_branding_hash = None
        si = create_service_identity(legacy_svc_identity_user, to)
        self.assertTrue(is_service_identity_user(svc_identity_user))

        self.assertFalse(canBeFriends(app_user_rogerthat_profile, app_user_lochristi_profile))
        self.assertFalse(canBeFriends(app_user_lochristi_profile, app_user_rogerthat_profile))

        self.assertTrue(canBeFriends(app_user_rogerthat_profile, si))
        self.assertFalse(canBeFriends(app_user_lochristi_profile, si))

        ###########################################################################
        si = get_service_identity(svc_identity_user)
        si.appIds = [app_id_rogerthat]
        si.put()

        self.assertTrue(canBeFriends(app_user_rogerthat_profile, si))
        self.assertFalse(canBeFriends(app_user_lochristi_profile, si))

        makeFriends(app_user_rogerthat_profile.user, si.user, None, None, None, False, False)
        self.assertTrue(areFriends(app_user_rogerthat_profile, si))
        breakFriendShip(app_user_rogerthat_profile.user, si.user)
        self.assertFalse(areFriends(app_user_rogerthat_profile, si))

        self.assertRaises(Exception, makeFriends, app_user_lochristi_profile.user, si.user, None, None, None, False, False)
        self.assertFalse(areFriends(app_user_lochristi_profile, si))
        breakFriendShip(app_user_lochristi_profile.user, si.user)
        self.assertFalse(areFriends(app_user_lochristi_profile, si))

        ###########################################################################
        si = get_service_identity(svc_identity_user)
        si.appIds = [app_id_lochristi]
        si.put()

        self.assertFalse(canBeFriends(app_user_rogerthat_profile, si))
        self.assertTrue(canBeFriends(app_user_lochristi_profile, si))

        self.assertRaises(Exception, makeFriends, app_user_rogerthat_profile.user, si.user, None, None, None, False, False)
        self.assertFalse(areFriends(app_user_rogerthat_profile, si))
        breakFriendShip(app_user_rogerthat_profile.user, si.user)
        self.assertFalse(areFriends(app_user_rogerthat_profile, si))

        makeFriends(app_user_lochristi_profile.user, si.user, None, None, None, False, False)
        self.assertTrue(areFriends(app_user_lochristi_profile, si))
        breakFriendShip(app_user_lochristi_profile.user, si.user)
        self.assertFalse(areFriends(app_user_lochristi_profile, si))

        ###########################################################################
        si = get_service_identity(svc_identity_user)
        si.appIds = [app_id_rogerthat, app_id_lochristi]
        si.put()

        self.assertTrue(canBeFriends(app_user_rogerthat_profile, si))
        self.assertTrue(canBeFriends(app_user_lochristi_profile, si))

        makeFriends(app_user_rogerthat_profile.user, si.user, None, None, None, False, False)
        self.assertTrue(areFriends(app_user_rogerthat_profile, si))
        breakFriendShip(app_user_rogerthat_profile.user, si.user)
        self.assertFalse(areFriends(app_user_rogerthat_profile, si))

        makeFriends(app_user_lochristi_profile.user, si.user, None, None, None, False, False)
        self.assertTrue(areFriends(app_user_lochristi_profile, si))
        breakFriendShip(app_user_lochristi_profile.user, si.user)
        self.assertFalse(areFriends(app_user_lochristi_profile, si))

        ###########################################################################
        si = get_service_identity(svc_identity_user)
        si.appIds = [u"rogerthat"]
        si.put()

        human_user = users.User(u"bart2@example.com")
        rogerthat_app_user, rogerthat_user_profile = self._test_rogerthat_app_user(human_user, "rogerthat", si)
        lochristi_app_user, lochristi_user_profile = self._test_rogerthat_app_user(human_user, "be-loc", si)

        self.assertRaises(Exception, invite, rogerthat_app_user, get_human_user_from_app_user(rogerthat_user_profile.user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"be-loc")
        self.assertRaises(Exception, invite, rogerthat_app_user, get_human_user_from_app_user(lochristi_user_profile.user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"be-loc")
        self.assertRaises(Exception, invite, lochristi_app_user, get_human_user_from_app_user(lochristi_user_profile.user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"be-loc")
        self.assertRaises(Exception, invite, lochristi_app_user, get_human_user_from_app_user(rogerthat_user_profile.user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"be-loc")

        self.assertRaises(Exception, invite, rogerthat_app_user, get_human_user_from_app_user(rogerthat_user_profile.user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"rogerthat")
        self.assertRaises(Exception, invite, rogerthat_app_user, get_human_user_from_app_user(lochristi_user_profile.user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"rogerthat")
        self.assertRaises(Exception, invite, lochristi_app_user, get_human_user_from_app_user(lochristi_user_profile.user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"rogerthat")
        self.assertRaises(Exception, invite, lochristi_app_user, get_human_user_from_app_user(rogerthat_user_profile.user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"rogerthat")

        invite(svc_identity_user, get_human_user_from_app_user(rogerthat_app_user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"rogerthat")
        self.assertRaises(Exception, invite, svc_identity_user, get_human_user_from_app_user(rogerthat_app_user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"rogerthat")
        self.assertRaises(Exception, invite, svc_identity_user, get_human_user_from_app_user(lochristi_app_user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"be-loc")

        si = get_service_identity(svc_identity_user)
        si.appIds = [u"be-loc"]
        si.put()

        invite(svc_identity_user, u'bart@example.com', None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"be-loc")
        self.assertRaises(Exception, invite, svc_identity_user, u'bart@example.com', None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=u"rogerthat")

    def test_mobiles(self):
        self.set_datastore_hr_probability(1)
        john = create_app_user(users.User(u'john_doe@foo.com'), "be-loc")
        create_user_profile(john, u"John Doe")
        john_mobile = register_tst_mobile(john.email())
        set_current_mobile(john_mobile)

        self.assertEqual("be-loc", users.get_current_app_id())
        azzert(john_mobile == users.get_current_mobile())

        jane = create_app_user(users.User(u'jane_doe@foo.com'), "be-loc2#ffaf14579")
        create_user_profile(jane, u"Jane Doe")
        jane_mobile = register_tst_mobile(jane.email())
        set_current_mobile(jane_mobile)

        self.assertEqual("be-loc2#ffaf14579", users.get_current_app_id())
        azzert(jane_mobile == users.get_current_mobile())
