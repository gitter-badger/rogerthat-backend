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

from rogerthat.bizz.profile import create_service_profile, create_user_profile, update_password_hash
from rogerthat.rpc import users
from rogerthat.utils import now
from google.appengine.ext import db
import mc_unittest

class Test(mc_unittest.TestCase):

    def testServiceProfile(self):
        self.set_datastore_hr_probability(1)

        service_profile, service_identity = create_service_profile(users.User(u's1@foo.com'), 's1', is_trial=True)
        service_profile = db.get(service_profile.key())
        assert service_profile.avatarId > 1
        assert service_profile.passwordHash is None

        service_identity = db.get(service_identity.key())
        assert service_identity.name == 's1'

        now_ = now()
        update_password_hash(service_profile, u"passwordHash", now_)
        service_profile = db.get(service_profile.key())
        assert service_profile.passwordHash == "passwordHash"
        assert service_profile.lastUsedMgmtTimestamp == now_
        assert service_profile.termsAndConditionsVersion > 0

    def testUserProfile(self):
        user_profile = create_user_profile(users.User(u'u1@foo.com'), 'u1', language='es')
        user_profile = db.get(user_profile.key())
        assert user_profile.avatarId > 1
        assert user_profile.passwordHash is None
        assert user_profile.language == 'es'
        assert user_profile.name == 'u1'

        now_ = now()
        update_password_hash(user_profile, u"passwordHash", now_)
        user_profile = db.get(user_profile.key())
        assert user_profile.passwordHash == "passwordHash"
        assert user_profile.lastUsedMgmtTimestamp == now_
        assert user_profile.termsAndConditionsVersion > 0
