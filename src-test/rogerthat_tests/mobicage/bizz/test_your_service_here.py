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

from rogerthat.bizz.service.yourservicehere import signup
from rogerthat.dal.profile import is_trial_service, get_trial_service_by_owner, get_service_profile
from rogerthat.dal.service import get_default_service_identity, get_service_interaction_defs
from rogerthat.rpc import users
import mc_unittest
from rogerthat.models import ServiceInteractionDef

class Test(mc_unittest.TestCase):

    def testSignup(self):
        self.set_datastore_hr_probability(1)

        owner_user = users.get_current_user()
        name = u"service_name"
        description = u"service_description"
        trial_service_to = signup(owner_user, name, description, True)
        assert is_trial_service(users.User(trial_service_to.account))

        ts = get_trial_service_by_owner(owner_user)
        assert ts
        si = get_default_service_identity(ts.service)
        assert si.name == name
        assert si.description == description

        svc_profile = get_service_profile(si.service_user)
        assert svc_profile.avatarId > 0
        assert svc_profile.passwordHash

        qr_codes = get_service_interaction_defs(si.service_user, si.identifier, None, True)['defs']
        assert len(qr_codes) > 0
        assert ServiceInteractionDef.TAG_INVITE in [qr.tag for qr in qr_codes]
