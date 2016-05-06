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

from rogerthat.bizz import roles
from rogerthat.bizz.profile import create_user_profile, create_service_profile
from rogerthat.bizz.roles import has_role, create_service_role, grant_role
from rogerthat.dal.profile import get_user_profile
from rogerthat.rpc import users
import mc_unittest
from rogerthat.bizz.service import create_menu_item
from rogerthat.models import ServiceRole
from rogerthat.to.friends import FriendTO
from rogerthat.bizz.friends import makeFriends, ORIGIN_USER_INVITE
from rogerthat.dal.friend import get_friends_map


class Test(mc_unittest.TestCase):

    def setUp(self):
        super(Test, self).setUp(1)
        self.service_user = users.User(u'monitoring@rogerth.at')
        _, service_identity = create_service_profile(self.service_user, u"Monitoring service")
        self.service_identity_user = service_identity.user

        self.john = users.User(u'john_doe@foo.com')
        up = create_user_profile(self.john, u"John Doe")
        up.grant_role(service_identity.user, roles.ROLE_ADMIN)
        up.put()

        self.jane = users.User(u'jane_doe@foo.com')
        create_user_profile(self.jane, u"Jane Doe")

    def test_grant_role(self):
        john_profile = get_user_profile(self.john, True)
        jane_profile = get_user_profile(self.jane, True)
        self.assertTrue(john_profile.has_role(self.service_identity_user, roles.ROLE_ADMIN))
        self.assertTrue(has_role(self.service_identity_user, john_profile, roles.ROLE_ADMIN))
        self.assertTrue(has_role(self.service_identity_user, self.john, roles.ROLE_ADMIN))

        self.assertFalse(jane_profile.has_role(self.service_identity_user, roles.ROLE_ADMIN))
        self.assertFalse(has_role(self.service_identity_user, jane_profile, roles.ROLE_ADMIN))
        self.assertFalse(has_role(self.service_identity_user, self.jane, roles.ROLE_ADMIN))

    def test_remove_role(self):
        john_profile = get_user_profile(self.john, True)
        john_profile.revoke_role(self.service_identity_user, roles.ROLE_ADMIN)
        john_profile.put()
        jane_profile = get_user_profile(self.jane, True)
        self.assertFalse(john_profile.has_role(self.service_identity_user, roles.ROLE_ADMIN))
        self.assertFalse(jane_profile.has_role(self.service_identity_user, roles.ROLE_ADMIN))

    def create_roles_and_menu_items(self):
        role1 = create_service_role(self.service_user, u'role1', ServiceRole.TYPE_MANAGED)
        role2 = create_service_role(self.service_user, u'role2', ServiceRole.TYPE_MANAGED)
        create_menu_item(self.service_user, u'gear', u'#e6e6e6', u'label1', u'tag1', [1, 1, 1], screen_branding=None,
                         static_flow_name=None, requires_wifi=False, run_in_background=False, roles=[role1.role_id],
                         is_broadcast_settings=False, broadcast_branding=None)
        create_menu_item(self.service_user, u'gear', u'#e6e6e6', u'label2', u'tag2', [1, 2, 1], screen_branding=None,
                         static_flow_name=None, requires_wifi=False, run_in_background=False, roles=[role2.role_id],
                         is_broadcast_settings=False, broadcast_branding=None)
        return role1, role2

    def test_service_menu_item_roles(self):
        role1, _ = self.create_roles_and_menu_items()

        grant_role(self.service_identity_user, self.john, role1)

        makeFriends(self.john, self.service_identity_user, None, None, ORIGIN_USER_INVITE)
        makeFriends(self.jane, self.service_identity_user, None, None, ORIGIN_USER_INVITE)

        john_friendTO = FriendTO.fromDBFriendMap(get_friends_map(self.john), self.service_identity_user,
                                                 includeAvatarHash=False, includeServiceDetails=True,
                                                 targetUser=self.john)
        self.assertEqual(1, len(john_friendTO.actionMenu.items))
        self.assertListEqual([1, 1, 1], john_friendTO.actionMenu.items[0].coords)

        jane_friendTO = FriendTO.fromDBFriendMap(get_friends_map(self.jane), self.service_identity_user,
                                                 includeAvatarHash=False, includeServiceDetails=True,
                                                 targetUser=self.jane)
        self.assertEqual(0, len(jane_friendTO.actionMenu.items))
