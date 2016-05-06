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

from rogerthat.bizz.friends import makeFriends, breakFriendShip
from rogerthat.bizz.messaging import CanOnlySendToFriendsException
from rogerthat.bizz.profile import create_service_profile, create_user_profile
from rogerthat.bizz.service import create_service_identity
from rogerthat.dal.profile import is_service_identity_user
from rogerthat.models import ServiceIdentity
from rogerthat.rpc import users
from rogerthat.to.service import ServiceIdentityDetailsTO
from rogerthat.utils.service import create_service_identity_user
from mcfw.rpc import MissingArgumentException
from rogerthat_tests import set_current_user
import mc_unittest

class Test(mc_unittest.TestCase):

    def testServiceIdentities(self):
        from rogerthat.service.api.messaging import send

        legacy_svc_identity_user = users.User(u"info@example.com")

        create_service_profile(legacy_svc_identity_user, legacy_svc_identity_user.email())
        assert is_service_identity_user(legacy_svc_identity_user)
        set_current_user(legacy_svc_identity_user)

        geert = users.User(u"geert@example.com")

        create_user_profile(geert, geert.email())

        # Send message
        message = u"De kat krabt de krollen van de trap!"
        self.assertRaises(CanOnlySendToFriendsException, send, parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None)

        self.assertRaises(CanOnlySendToFriendsException, send, parent_message_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None)

        self.assertRaises(MissingArgumentException, send, message=message, answers=[], flags=1, members=[u'geert@example.com'],
                          branding=None, tag=None, accept_missing=None)

        makeFriends(legacy_svc_identity_user, geert, None, None, None, False, False)

        send(parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None)

        send(parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None, service_identity=None)

        send(parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None, service_identity='')

        send(parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None, service_identity=ServiceIdentity.DEFAULT)

        breakFriendShip(geert, legacy_svc_identity_user)


        makeFriends(geert, legacy_svc_identity_user, None, None, None, False, False)

        send(parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None)

        send(parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None, service_identity=None)

        send(parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None, service_identity='')

        send(parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None, service_identity=ServiceIdentity.DEFAULT)

        breakFriendShip(legacy_svc_identity_user, geert)


        self.assertRaises(CanOnlySendToFriendsException, send, parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None)


        svc_identity_user = users.User(u"info@example.com/+default+")


        makeFriends(svc_identity_user, geert, None, None, None, False, False)

        send(parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None)

        breakFriendShip(svc_identity_user, geert)


        makeFriends(geert, svc_identity_user, None, None, None, False, False)

        send(parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None)

        breakFriendShip(geert, svc_identity_user)

        svc_user = users.User(u'info@example.com')
        svc_identity_user2 = create_service_identity_user(svc_user, 'subservice')

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
        create_service_identity(svc_user, to)
        assert is_service_identity_user(svc_identity_user2)

        makeFriends(geert, svc_identity_user2, None, None, None, False, False)
        breakFriendShip(geert, svc_identity_user2)
        makeFriends(svc_identity_user2, geert, None, None, None, False, False)
        breakFriendShip(svc_identity_user2, geert)

        self.assertRaises(CanOnlySendToFriendsException, send, parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None, service_identity='subservice')

        makeFriends(geert, svc_identity_user, None, None, None, False, False)

        self.assertRaises(CanOnlySendToFriendsException, send, parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None, service_identity='subservice')

        makeFriends(geert, svc_identity_user2, None, None, None, False, False)

        send(parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None, service_identity='subservice')

        breakFriendShip(geert, svc_identity_user)

        send(parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None, service_identity='subservice')

        self.assertRaises(CanOnlySendToFriendsException, send, parent_key=None, message=message, answers=[], flags=1,
                          members=[u'geert@example.com'], branding=None, tag=None, accept_missing=None, service_identity=None)

        breakFriendShip(geert, svc_identity_user2)

        breakFriendShip(geert, svc_identity_user)  # No error when breaking again

        breakFriendShip(geert, svc_identity_user2)  # No error when breaking again
