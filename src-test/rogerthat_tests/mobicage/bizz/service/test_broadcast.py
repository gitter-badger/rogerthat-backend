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

from uuid import uuid4

from rogerthat.api.services import getStaticFlow
from rogerthat.bizz.friends import makeFriends, ORIGIN_USER_INVITE
from rogerthat.bizz.i18n import get_translator
from rogerthat.bizz.profile import create_service_profile, create_user_profile
from rogerthat.bizz.service import create_menu_item, move_menu_item
from rogerthat.bizz.service.broadcast import generate_broadcast_settings_static_flow, \
    generate_broadcast_settings_flow_def, _check_flow_end_modules
from rogerthat.dal.profile import get_user_profile
from rogerthat.dal.service import get_default_service_identity, get_friend_serviceidentity_connection
from rogerthat.models import CustomMessageFlowDesign
from rogerthat.rpc import users
from rogerthat.rpc.service import BusinessException
from rogerthat.to.friends import ServiceMenuTO, WebServiceMenuTO
from rogerthat.to.service import GetStaticFlowRequestTO
from rogerthat.utils.service import add_slash_default
import mc_unittest
from rogerthat_tests import set_current_user


class Test(mc_unittest.TestCase):

    def _prepare_users(self):
        service_user = users.User('svc-%s@foo.com' % uuid4())
        service_profile = create_service_profile(service_user, u"s1")[0]

        human_user = users.User('user-%s@foo.com' % uuid4())
        user_profile = get_user_profile(human_user) or create_user_profile(human_user, u"i")

        set_current_user(user_profile.user)

        return user_profile, service_profile

    def test_generated_broadcast_settings_flow(self):
        user_profile, service_profile = self._prepare_users()
        friend_user = user_profile.user
        service_identity_user = add_slash_default(service_profile.user)

        makeFriends(friend_user, service_identity_user, service_identity_user, None, origin=ORIGIN_USER_INVITE)

        # No broadcast types ==> no flow
        self.assertFalse(generate_broadcast_settings_static_flow(service_identity_user, user_profile.user))

        service_profile.broadcastTypes = ['Apes', 'Birds', 'Cats', 'Dogs']
        service_profile.put()

        friend_service_identity_connection = get_friend_serviceidentity_connection(friend_user, service_identity_user)
        friend_service_identity_connection.enabled_broadcast_types = service_profile.broadcastTypes
        friend_service_identity_connection.put()

        self.assertTrue(generate_broadcast_settings_static_flow(service_identity_user, user_profile.user))

        mfds = generate_broadcast_settings_flow_def(service_identity_user, user_profile)
        self.assertEqual(1, len(mfds.definition))
        mf_def = mfds.definition[0]
        self.assertEqual(1, len(mf_def.formMessage))
        fm = mf_def.formMessage[0]
        self.assertEqual(len(service_profile.broadcastTypes), len(fm.form.widget.choice))
        self.assertEqual(0, len(service_profile.broadcastTypes) - len(fm.form.widget.value))  # 0 disabled values

        friend_service_identity_connection1 = get_friend_serviceidentity_connection(friend_user, service_identity_user)
        friend_service_identity_connection1.enabled_broadcast_types = ['Birds', 'Cats', 'Dogs']
        friend_service_identity_connection1.disabled_broadcast_types = ['Apes']
        friend_service_identity_connection1.put()

        mfds = generate_broadcast_settings_flow_def(service_identity_user, user_profile)
        self.assertEqual(1, len(mfds.definition))
        mf_def = mfds.definition[0]
        self.assertEqual(1, len(mf_def.formMessage))
        fm = mf_def.formMessage[0]
        self.assertEqual(len(service_profile.broadcastTypes), len(fm.form.widget.choice))
        self.assertEqual(1, len(service_profile.broadcastTypes) - len(fm.form.widget.value))  # 1 disabled values

        friend_service_identity_connection2 = get_friend_serviceidentity_connection(friend_user, service_identity_user)
        friend_service_identity_connection2.enabled_broadcast_types = ['Cats', 'Dogs']
        friend_service_identity_connection2.disabled_broadcast_types = ['Apes', 'Birds']
        friend_service_identity_connection2.put()

        mfds = generate_broadcast_settings_flow_def(service_identity_user, user_profile)
        self.assertEqual(1, len(mfds.definition))
        mf_def = mfds.definition[0]
        self.assertEqual(1, len(mf_def.formMessage))
        fm = mf_def.formMessage[0]
        self.assertEqual(len(service_profile.broadcastTypes), len(fm.form.widget.choice))
        self.assertEqual(2, len(service_profile.broadcastTypes) - len(fm.form.widget.value))  # 2 disabled values

    def test_menu_items(self):
        user_profile, service_profile = self._prepare_users()

        friend_user = user_profile.user
        service_user = service_profile.user
        service_identity = get_default_service_identity(service_profile.user)
        makeFriends(friend_user, service_identity.user, service_identity.user, None, origin=ORIGIN_USER_INVITE)

        translator = get_translator(service_profile.user)

        menu = ServiceMenuTO.fromServiceIdentity(service_identity, user_profile.language, translator, user_profile)
        self.assertEqual(0, len(menu.items))

        # No broadcast types --> error
        self.assertRaises(BusinessException, create_menu_item, service_user, "3d", "000000", "label", "tag", [1, 1, 1],
                          None, None, False, False, [], is_broadcast_settings=True, broadcast_branding=None)

        service_profile.broadcastTypes = ['Apes', 'Birds', 'Cats', 'Dogs']
        service_profile.put()

        friend_service_identity_connection = get_friend_serviceidentity_connection(friend_user, service_identity.user)
        friend_service_identity_connection.enabled_broadcast_types = service_profile.broadcastTypes
        friend_service_identity_connection.put()

        create_menu_item(service_user, "3d", "000000", "label", "tag", [1, 1, 1], None, None, False, False, [],
                         is_broadcast_settings=True, broadcast_branding=None)

        def _test_1_bc_settings_item():
            menu = ServiceMenuTO.fromServiceIdentity(service_identity, user_profile.language, translator, user_profile)
            self.assertEqual(1, len(menu.items))
            smi = menu.items[0]
            self.assertTrue(smi.staticFlowHash)

            request = GetStaticFlowRequestTO()
            request.service = service_user.email()
            request.staticFlowHash = smi.staticFlowHash
            request.coords = smi.coords

            response = getStaticFlow(request)
            self.assertTrue(response)
            self.assertTrue(response.staticFlow)

        _test_1_bc_settings_item()

        move_menu_item(service_user, [1, 1, 1], [2, 2, 2])

        _test_1_bc_settings_item()

        # test Web-version of menu TO
        WebServiceMenuTO.fromServiceIdentity(service_identity, user_profile.language, translator, user_profile)


    def test_patched_test_broadcast_flow(self):
        _, service_profile = self._prepare_users()

        mfd = CustomMessageFlowDesign()
        mfd.user = service_profile.user
        mfd.key = lambda: None
        mfd.xml = """<?xml version="1.0" encoding="utf-8"?>
<messageFlowDefinitionSet xmlns="https://rogerth.at/api/1/MessageFlow.xsd">
    <definition name="test2" language="en" startReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogIm1lc3NhZ2VfMTIzIn0=">
        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogImVuZF8xIn0=" waitForFollowUpMessage="false"/>
        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogImVuZF8yIn0=" waitForFollowUpMessage="false"/>
        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogImVuZF8zIn0=" waitForFollowUpMessage="false"/>
        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogImVuZF81In0=" waitForFollowUpMessage="false"/>
        <message id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogIm1lc3NhZ2VfMTIzIn0=" alertIntervalType="NONE" alertType="SILENT" allowDismiss="true" vibrate="false" dismissReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogImVuZF81In0=" autoLock="true">
            <content>123</content>
            <answer action="" caption="1" id="button_1" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogImVuZF8zIn0="/>
            <answer action="" caption="2" id="button_2" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogIm1lc3NhZ2VfMSJ9"/>
            <answer action="" caption="4" id="button_4" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogImVuZF8xIn0="/>
        </message>
        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogIm1lc3NhZ2VfMSJ9" alertIntervalType="NONE" alertType="SILENT" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogImVuZF8yIn0=" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2pZTEVncHRZeTEwY21GamEyVnlJZ3B6TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnVjBaWE4wTWd3IiwgImlkIjogImVuZF8zIn0=">
            <content>Which type of broadcasts do you wish to receive:</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Save" negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="SelectMultiWidget">
                    <choice value="1" label="1"/>
                    <choice value="2" label="2"/>
                    <value value="1"/>
                    <value value="2"/>
                </widget>
            </form>
        </formMessage>
    </definition>
</messageFlowDefinitionSet>
"""

        new_xml = _check_flow_end_modules(mfd)
        assert new_xml

    def test_patched_test_broadcast_flow2(self):
        _, service_profile = self._prepare_users()

        mfd = CustomMessageFlowDesign()
        mfd.user = service_profile.user
        mfd.key = lambda: None
        mfd.xml = """<?xml version="1.0" encoding="utf-8"?>
<messageFlowDefinitionSet xmlns="https://rogerth.at/api/1/MessageFlow.xsd">
    <definition
        name="Feedback"
        language="en"
        startReference="base64:eyJtZmQiOiAiYWhOa1pYWi1iVzlpYVdOaFoyVmpiRzkxWkdoeWNrSUxFZ3B0WXkxMGNtRmphMlZ5SWhOeVpYTjBielpBYlc5aWFXTmhaMlV1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ2htWldWa1ltRmphd3ciLCAiaWQiOiAibWVzc2FnZV9RMSIsICJsYW5nIjogIm5sIn0=">
        <end
            id="base64:eyJtZmQiOiAiYWhOa1pYWi1iVzlpYVdOaFoyVmpiRzkxWkdoeWNrSUxFZ3B0WXkxMGNtRmphMlZ5SWhOeVpYTjBielpBYlc5aWFXTmhaMlV1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ2htWldWa1ltRmphd3ciLCAiaWQiOiAiZW5kX0VORCIsICJsYW5nIjogIm5sIn0="
            waitForFollowUpMessage="false" />
        <message
            id="base64:eyJtZmQiOiAiYWhOa1pYWi1iVzlpYVdOaFoyVmpiRzkxWkdoeWNrSUxFZ3B0WXkxMGNtRmphMlZ5SWhOeVpYTjBielpBYlc5aWFXTmhaMlV1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ2htWldWa1ltRmphd3ciLCAiaWQiOiAibWVzc2FnZV9RMSIsICJsYW5nIjogIm5sIn0="
            alertIntervalType="NONE"
            alertType="SILENT"
            brandingKey=""
            allowDismiss="false"
            vibrate="false"
            autoLock="true">
            <content>feedback-message-1</content>
            <answer
                action=""
                caption="Yes"
                id="button_Q1_YES"
                reference="base64:eyJtZmQiOiAiYWhOa1pYWi1iVzlpYVdOaFoyVmpiRzkxWkdoeWNrSUxFZ3B0WXkxMGNtRmphMlZ5SWhOeVpYTjBielpBYlc5aWFXTmhaMlV1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ2htWldWa1ltRmphd3ciLCAiaWQiOiAibWVzc2FnZV9RMiIsICJsYW5nIjogIm5sIn0=" />
            <answer
                action=""
                caption="No"
                id="button_Q1_NO"
                reference="base64:eyJtZmQiOiAiYWhOa1pYWi1iVzlpYVdOaFoyVmpiRzkxWkdoeWNrSUxFZ3B0WXkxMGNtRmphMlZ5SWhOeVpYTjBielpBYlc5aWFXTmhaMlV1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ2htWldWa1ltRmphd3ciLCAiaWQiOiAibWVzc2FnZV9RMiIsICJsYW5nIjogIm5sIn0=" />
        </message>
        <message
            id="base64:eyJtZmQiOiAiYWhOa1pYWi1iVzlpYVdOaFoyVmpiRzkxWkdoeWNrSUxFZ3B0WXkxMGNtRmphMlZ5SWhOeVpYTjBielpBYlc5aWFXTmhaMlV1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ2htWldWa1ltRmphd3ciLCAiaWQiOiAibWVzc2FnZV9RMiIsICJsYW5nIjogIm5sIn0="
            alertIntervalType="NONE"
            alertType="SILENT"
            brandingKey=""
            allowDismiss="false"
            vibrate="false"
            autoLock="true">
            <content>feedback-message-2</content>
            <answer
                action=""
                caption="Yes"
                id="button_Q2_YES"
                reference="base64:eyJtZmQiOiAiYWhOa1pYWi1iVzlpYVdOaFoyVmpiRzkxWkdoeWNrSUxFZ3B0WXkxMGNtRmphMlZ5SWhOeVpYTjBielpBYlc5aWFXTmhaMlV1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ2htWldWa1ltRmphd3ciLCAiaWQiOiAiZmx1c2hfUjEiLCAibGFuZyI6ICJubCJ9" />
            <answer
                action=""
                caption="No"
                id="button_Q2_NO"
                reference="base64:eyJtZmQiOiAiYWhOa1pYWi1iVzlpYVdOaFoyVmpiRzkxWkdoeWNrSUxFZ3B0WXkxMGNtRmphMlZ5SWhOeVpYTjBielpBYlc5aWFXTmhaMlV1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ2htWldWa1ltRmphd3ciLCAiaWQiOiAiZmx1c2hfUjEiLCAibGFuZyI6ICJubCJ9" />
        </message>
        <message
            id="base64:eyJtZmQiOiAiYWhOa1pYWi1iVzlpYVdOaFoyVmpiRzkxWkdoeWNrSUxFZ3B0WXkxMGNtRmphMlZ5SWhOeVpYTjBielpBYlc5aWFXTmhaMlV1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ2htWldWa1ltRmphd3ciLCAiaWQiOiAibWVzc2FnZV9RMyIsICJsYW5nIjogIm5sIn0="
            alertIntervalType="NONE"
            alertType="SILENT"
            brandingKey=""
            allowDismiss="true"
            vibrate="false"
            dismissReference="base64:eyJtZmQiOiAiYWhOa1pYWi1iVzlpYVdOaFoyVmpiRzkxWkdoeWNrSUxFZ3B0WXkxMGNtRmphMlZ5SWhOeVpYTjBielpBYlc5aWFXTmhaMlV1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ2htWldWa1ltRmphd3ciLCAiaWQiOiAiZW5kX0VORCIsICJsYW5nIjogIm5sIn0="
            autoLock="true">
            <content>feedback-message-3</content>
        </message>
        <resultsFlush
            id="base64:eyJtZmQiOiAiYWhOa1pYWi1iVzlpYVdOaFoyVmpiRzkxWkdoeWNrSUxFZ3B0WXkxMGNtRmphMlZ5SWhOeVpYTjBielpBYlc5aWFXTmhaMlV1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ2htWldWa1ltRmphd3ciLCAiaWQiOiAiZmx1c2hfUjEiLCAibGFuZyI6ICJubCJ9"
            reference="base64:eyJtZmQiOiAiYWhOa1pYWi1iVzlpYVdOaFoyVmpiRzkxWkdoeWNrSUxFZ3B0WXkxMGNtRmphMlZ5SWhOeVpYTjBielpBYlc5aWFXTmhaMlV1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ2htWldWa1ltRmphd3ciLCAiaWQiOiAibWVzc2FnZV9RMyIsICJsYW5nIjogIm5sIn0=" />
    </definition>
</messageFlowDefinitionSet>
"""

        new_xml = _check_flow_end_modules(mfd)
        assert new_xml


    def test_patched_test_broadcast_flow3(self):
        _, service_profile = self._prepare_users()

        mfd = CustomMessageFlowDesign()
        mfd.user = service_profile.user
        mfd.key = lambda: None
        mfd.xml = """<?xml version="1.0" encoding="utf-8"?>
<messageFlowDefinitionSet xmlns="https://rogerth.at/api/1/MessageFlow.xsd">
    <definition name="meldingskaart" language="nl" startReference="message_1">
        <end id="end_1" waitForFollowUpMessage="false"/>
        <message id="message_1" alertIntervalType="NONE" alertType="SILENT" brandingKey="B26DFDEF91BB94325DF1537AE6A9048F10B1C9FB84836CAE085B4355EA3408A5" allowDismiss="false" vibrate="false" autoLock="true">
            <content>maak hier uw keuze</content>
            <answer action="" caption="slecht wegdek" id="button_slecht wegdek" reference="message_2"/>
            <answer action="tel://32475982340" caption="bel lieven" id="button_bel lieven" reference="end_1"/>
            <answer action="" caption="zwerfvuil" id="button_zwerfvuil" reference="message_2"/>
        </message>
        <formMessage id="message_2" alertIntervalType="NONE" alertType="SILENT" brandingKey="B26DFDEF91BB94325DF1537AE6A9048F10B1C9FB84836CAE085B4355EA3408A5" positiveReference="message_3" vibrate="false" autoLock="true" negativeReference="message_1">
            <content>???</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="annuleren" positiveButtonCaption="verder" negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextBlockWidget" maxChars="50"/>
            </form>
        </formMessage>
        <formMessage id="message_3" alertIntervalType="NONE" alertType="SILENT" brandingKey="B26DFDEF91BB94325DF1537AE6A9048F10B1C9FB84836CAE085B4355EA3408A5" positiveReference="message_4=" vibrate="false" autoLock="true" negativeReference="end_1">
            <content>cdsc</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="PhotoUploadWidget" camera="true" quality="400000" gallery="false"/>
            </form>
        </formMessage>
        <formMessage id="message_4=" alertIntervalType="NONE" alertType="SILENT" brandingKey="B26DFDEF91BB94325DF1537AE6A9048F10B1C9FB84836CAE085B4355EA3408A5" positiveReference="email_1" vibrate="false" autoLock="true" negativeReference="message_3">
            <content>????</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="SliderWidget" max="10.000000" step="1.000000" precision="1" unit="&lt;value/&gt;" min="1.000000" value="1.000000"/>
            </form>
        </formMessage>
        <resultsEmail id="email_1" reference="end_1" emailAdmins="false">
            <email value="communicatie@lochristi.be"/>
        </resultsEmail>
    </definition>
</messageFlowDefinitionSet>

"""

        new_xml = _check_flow_end_modules(mfd)
        assert new_xml
