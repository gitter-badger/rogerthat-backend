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

from rogerthat.bizz.profile import create_service_profile, create_user_profile
from rogerthat.dal import parent_key
from rogerthat.dal.profile import get_service_profile, get_profile_info
from rogerthat.dal.service import get_default_service_identity, get_service_identity
from rogerthat.models import ServiceProfile, UserProfile, FacebookUserProfile, ServiceIdentity, ds_service_identity, \
    s_service_identity
from rogerthat.rpc import users, rpc
from rogerthat.utils.service import add_slash_default
from mcfw.cache import flush_request_cache
import StringIO
import mc_unittest
import uuid

class Test(mc_unittest.TestCase):

    def testServiceProfileCacheSerialization(self):
        svc_user = users.User(u'service@foo.com')
        _, svc_identity = create_service_profile(svc_user, 'Service')

        self.assert_(isinstance(svc_identity, ServiceIdentity))

        profile2 = get_service_profile(svc_user)
        self.assert_(isinstance(profile2, ServiceProfile))
        service_identity2 = get_profile_info(svc_user)
        self.assert_(isinstance(service_identity2, ServiceIdentity))

        rpc.wait_for_rpcs()
        flush_request_cache()

        profile3 = get_profile_info(svc_user)
        self.assert_(isinstance(profile3, ServiceIdentity))

        rpc.wait_for_rpcs()
        flush_request_cache()

        service_identity4 = get_default_service_identity(svc_user)
        self.assert_(service_identity2.user, service_identity4.user)
        self.assert_(service_identity2.name, service_identity4.name)

    def testServiceIdentityCacheSerialization(self):
        svc_user = users.User(u'servicexx@foo.com')
        _, svc_identity = create_service_profile(svc_user, 'Serviceke')
        self.assert_(isinstance(svc_identity, ServiceIdentity))

        svc_id2 = get_default_service_identity(svc_user)
        self.assert_(isinstance(svc_id2, ServiceIdentity))
        self.assert_(svc_id2.name == svc_identity.name)
        self.assert_(svc_id2.name == 'Serviceke')

        svc_id3 = get_profile_info(svc_user)
        self.assert_(isinstance(svc_id3, ServiceIdentity))

        rpc.wait_for_rpcs()
        flush_request_cache()

        svc_id4 = get_profile_info(svc_user)
        self.assert_(isinstance(svc_id4, ServiceIdentity))

        rpc.wait_for_rpcs()
        flush_request_cache()

        svc_id5 = get_default_service_identity(svc_user)
        self.assert_(svc_user == svc_id5.service_user)
        self.assert_('Serviceke' == svc_id5.name)

    def testUserProfileCacheSerialization(self):
        user = users.User(u'user1@foo.com')
        user_profile = create_user_profile(user, user.email())

        self.assert_(isinstance(user_profile, UserProfile))

        profile2 = get_profile_info(user)
        self.assert_(isinstance(profile2, UserProfile))

        rpc.wait_for_rpcs()
        flush_request_cache()

        profile3 = get_profile_info(user)
        self.assert_(isinstance(profile3, UserProfile))

    def testFacebookProfileCacheSerialization(self):
        user = users.User(u'user2@foo.com')
        profile1 = FacebookUserProfile(parent=parent_key(user), key_name=user.email())
        profile1.name = user.email().replace('@', ' at ')
        profile1.put()

        profile2 = get_profile_info(user)
        self.assert_(isinstance(profile2, FacebookUserProfile))

        rpc.wait_for_rpcs()
        flush_request_cache()

        profile3 = get_profile_info(user)
        self.assert_(isinstance(profile3, FacebookUserProfile))

    def testServiceIdentityCacheSerialization2(self):
        name = u'xxxx'
        svc_email = u'service@foo.com'
        svc_user = users.User(svc_email)
        _, svc_identity = create_service_profile(svc_user, name)
        self.assert_(svc_identity.name == name)
        self.assert_(svc_identity.is_default)
        self.assert_(svc_identity.service_user.email() == svc_email)
        self.assert_(svc_identity.isServiceIdentity)

        svc_id1 = get_profile_info(svc_user)
        self.assert_(svc_id1.name == name)
        self.assert_(svc_id1.is_default)
        self.assert_(svc_id1.service_user.email() == svc_email)
        self.assert_(svc_id1.isServiceIdentity)

        svc_id2 = get_profile_info(svc_user)
        self.assert_(svc_id2.name == name)
        self.assert_(svc_id2.is_default)
        self.assert_(svc_id2.service_user.email() == svc_email)
        self.assert_(svc_id2.isServiceIdentity)

        rpc.wait_for_rpcs()
        flush_request_cache()

        svc_id3 = get_service_identity(add_slash_default(svc_user))
        self.assert_(svc_id3.name == name)
        self.assert_(svc_id3.is_default)
        self.assert_(svc_id3.service_user.email() == svc_email)
        self.assert_(svc_id3.isServiceIdentity)

        rpc.wait_for_rpcs()
        flush_request_cache()

        svc_id4 = get_service_identity(add_slash_default(svc_user))
        self.assert_(svc_id4.name == name)
        self.assert_(svc_id4.is_default)
        self.assert_(svc_id4.service_user.email() == svc_email)
        self.assert_(svc_id4.isServiceIdentity)

        self.assertRaises(AssertionError, get_service_identity, svc_user)

    def testServiceIdentitySerializer(self):
        name = u'name %s' % uuid.uuid4()
        svc_email = u'%s@foo.com' % uuid.uuid4()
        svc_user = users.User(svc_email)
        create_service_profile(svc_user, name)

        svc_identity_original = get_default_service_identity(users.User(svc_email))
        stream = StringIO.StringIO()
        s_service_identity(stream, svc_identity_original)
        stream_str = stream.getvalue()

        svc_identity_deserialized = ds_service_identity(StringIO.StringIO(stream_str))

        self.assert_(svc_identity_original.user == svc_identity_deserialized.user)
        self.assert_(svc_identity_original.name == svc_identity_deserialized.name)
