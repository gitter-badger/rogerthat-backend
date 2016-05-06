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

from rogerthat.api.messaging.jsmfr import newFlowMessage, messageFlowMemberResult
from rogerthat.bizz.profile import create_service_profile, create_user_profile
from rogerthat.bizz.service.mfd import MFD_FORM_MODULES, message_flow_design_to_xml
from rogerthat.bizz.service.mfd.mfd_javascript import generate_js_flow
from rogerthat.models.properties.forms import FormResult, UnicodeWidgetResult, FloatListWidgetResult, Form
from rogerthat.rpc import users
from rogerthat.to.messaging import MessageTO
from rogerthat.to.messaging.flow import MessageFlowStepTO, FormFlowStepTO
from rogerthat.to.messaging.forms import FormMessageTO, TextLineTO, RangeSliderTO
from rogerthat.to.messaging.jsmfr import NewFlowMessageRequestTO, MessageFlowMemberResultRequestTO, \
    JsMessageFlowMemberRunTO
from mcfw.rpc import parse_complex_value
from rogerthat_tests import set_current_user
from rogerthat_tests.mobicage.bizz.test_mfd import MFDUtil
import mc_unittest
from rogerthat.bizz.friends import makeFriends
from rogerthat.dal.messaging import get_message

service_user = users.User(u's1@foo.com')
human_user = users.User(u'bart@example.com')

class Test(mc_unittest.TestCase):

    def setUp(self, datastore_hr_probability=None):
        super(Test, self).setUp()
        if datastore_hr_probability is None:
            self.set_datastore_hr_probability(1)
            service_profile = create_service_profile(service_user, 's1')[0]
            service_profile.supportedLanguages = ["en", "fr", "nl"]
            service_profile.put()

            create_user_profile(human_user, 'bart', 'en')

            makeFriends(service_user, human_user, None, None, None, False, False)

    def testJSFlowDef(self):
        set_current_user(service_user)

        mfdUtil = MFDUtil("A")
        forms = list()
        start_a = mfdUtil.add_start_module()
        msg_a_1 = mfdUtil.add_message_module("a_1")
        for m in MFD_FORM_MODULES:
            forms.append(mfdUtil.add_form_message_module(m, u"élève %s" % str(MFD_FORM_MODULES.index(m))))
        end_a_1 = mfdUtil.add_end_module("1")
        flush_a_1 = mfdUtil.add_flush_module("1")
        flush_a_2 = mfdUtil.add_flush_module("2")

        mfdUtil.add_wire(start_a, "start", msg_a_1, "in")
        mfdUtil.add_wire(msg_a_1, "roger that", forms[0], "in")
        mfdUtil.add_wire(forms[-1], "positive", flush_a_1, "in")
        mfdUtil.add_wire(forms[-1], "negative", flush_a_1, "in")
        mfdUtil.add_wire(flush_a_1, "out", flush_a_2, "in")
        mfdUtil.add_wire(flush_a_2, "out", end_a_1, "end")

        for x in xrange(len(forms) - 1):
            mfdUtil.add_wire(forms[x], "positive", forms[x + 1], "in")
            mfdUtil.add_wire(forms[x], "negative", forms[x + 1], "in")

        mfd = mfdUtil.save()

        xml = message_flow_design_to_xml(mfd.user, mfd, translator=None, context=None)[0]
        # print xml.encode('utf8')
        output = generate_js_flow(service_user, xml, must_validate=False)
        self.assertTrue(output['en'])
        print output['en'][0].encode('utf8')
        self.assertFalse("None" in output['en'][0], "'None' found in generated result")

    def testStaticFlowBrandings(self):
        xml = u'<?xml version="1.0" encoding="utf-8"?>\n<messageFlowDefinitionSet xmlns="https://rogerth.at/api/1/MessageFlow.xsd">\n    <definition name="demo_crisis" language="en" startReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV93ZWxrb20ifQ==">\n        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZW5kX2dlYmVsZCJ9" waitForFollowUpMessage="false"/>\n        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZW5kX2JlZWluZGlnZCJ9" waitForFollowUpMessage="false"/>\n        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZW5kX2h1bWFuX2NvbW11bmljYXRpb24ifQ==" waitForFollowUpMessage="false"/>\n        <message id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV93ZWxrb20ifQ==" alertIntervalType="NONE" alertType="BEEP" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" allowDismiss="false" vibrate="true" autoLock="true">\n            <content>Welkom bij het crisiscentrum.\n\nHoe kunnen we u helpen?</content>\n            <answer action="" caption="Ik heb een spraak of hoor probleem" id="button_doven" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9kb29mMSJ9"/>\n            <answer action="tel://112" caption="Bel ziekenwagen - 112" id="button_112" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92cmFhZyJ9"/>\n            <answer action="tel://+3270245245" caption="Bel antigif - 070/245.245" id="button_antigif" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92cmFhZyJ9"/>\n            <answer action="tel://+3292333444" caption="Bel brandweer - 09/233 34 44" id="button_brandweer" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92cmFhZyJ9"/>\n            <answer action="tel://100" caption="Bel politie - 100" id="button_politie" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92cmFhZyJ9"/>\n        </message>\n        <message id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92cmFhZyJ9" alertIntervalType="NONE" alertType="SILENT" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" allowDismiss="false" vibrate="true" autoLock="true">\n            <content>Bent u geholpen?</content>\n            <answer action="" caption="Ja" id="button_ja" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9zdXJ2ZXkifQ=="/>\n            <answer action="" caption="Neen" id="button_nee" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV93ZWxrb20ifQ=="/>\n        </message>\n        <message id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV90aGFua3MifQ==" alertIntervalType="NONE" alertType="SILENT" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" allowDismiss="false" vibrate="true" autoLock="true">\n            <content>Dank u wel.\n\nWij wensen u verder een prettige dag.</content>\n            <answer action="" caption="OK" id="button_ok" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOCJ9"/>\n        </message>\n        <message id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9kb29mMSJ9" alertIntervalType="NONE" alertType="SILENT" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" allowDismiss="false" vibrate="true" autoLock="true">\n            <content>Hoe kunnen we u helpen?</content>\n            <answer action="" caption="Ziekenwagen" id="button_mug" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlc2NoZWNrIn0="/>\n            <answer action="" caption="Brandweer" id="button_brandweer" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlc2NoZWNrIn0="/>\n            <answer action="" caption="Politie" id="button_Politie" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlc2NoZWNrIn0="/>\n            <answer action="" caption="Ander probleem" id="button_ander" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlc2NoZWNrIn0="/>\n        </message>\n        <message id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlc2NoZWNrIn0=" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" allowDismiss="false" vibrate="true" autoLock="true">\n            <content>Bent u momenteel op het volgende adres:\nKalandenberg 1 te 9000 Gent</content>\n            <answer action="" caption="Ja" id="button_ja" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV93aWUifQ=="/>\n            <answer action="" caption="Nee" id="button_nee" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlcyJ9"/>\n        </message>\n        <message id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV93aWUifQ==" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" allowDismiss="false" vibrate="true" autoLock="true">\n            <content>Hulp is onderweg naar u.\n\nWie is het slachtoffer?</content>\n            <answer action="" caption="Ikzelf" id="button_ikzelf" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9sZWVmdGlqZF91In0="/>\n            <answer action="" caption="Familie of vriend" id="button_familie" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9sZWVmdGlqZCJ9"/>\n            <answer action="" caption="Onbekende" id="button_onbekende" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9sZWVmdGlqZCJ9"/>\n        </message>\n        <message id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9iZWRhbmt0In0=" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" allowDismiss="false" vibrate="true" autoLock="true">\n            <content>Gelieve bij het slachtoffer te blijven en uw toestel bij de hand te houden.\n\nWij contacteren u verder.</content>\n            <answer action="" caption="OK" id="button_OK" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9"/>\n            <answer action="" caption="Ik wens met een verpleger te praten" id="button_praten" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9vcGVyYXRvcmh1bHAifQ=="/>\n        </message>\n        <message id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92ZXJwbGVnZXIifQ==" alertIntervalType="NONE" alertType="SILENT" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" allowDismiss="false" vibrate="true" autoLock="true">\n            <content>(Hier praat verpleger met slachtoffer, of stelt een vraag).</content>\n            <answer action="" caption="OK" id="button_ok" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18yMCJ9"/>\n        </message>\n        <message id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92ZXJwbGVnZXJfdSJ9" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" allowDismiss="false" vibrate="true" autoLock="true">\n            <content>Wenst u nog met een verpleger te praten?</content>\n            <answer action="" caption="Ja" id="button_ja" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9vcGVyYXRvcmh1bHAifQ=="/>\n            <answer action="" caption="Neen" id="button_nee" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9"/>\n        </message>\n        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9zdXJ2ZXkifQ==" alertIntervalType="NONE" alertType="BEEP" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV90aGFua3MifQ==" vibrate="true" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOCJ9">\n            <content>Gelieve onze dienstverlening te beoordelen .\n\n(1 = zeer slecht, 5 = zeer goed)</content>\n            <form positiveButtonConfirmation="" negativeButtonCaption="Stop" positiveButtonCaption="Verder" negativeButtonConfirmation="">\n                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="SliderWidget" max="5.000000" step="1.000000" precision="0" unit="&lt;value/&gt; op 5" min="1.000000" value="4.000000"/>\n            </form>\n        </formMessage>\n        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlcyJ9" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV93aWUifQ==" vibrate="true" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9">\n            <content>Waar bent u momenteel?</content>\n            <form positiveButtonConfirmation="" negativeButtonCaption="Stoppen" positiveButtonCaption="Verder" negativeButtonConfirmation="">\n                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextBlockWidget" maxChars="200"/>\n            </form>\n        </formMessage>\n        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9vcGVyYXRvcmh1bHAifQ==" alertIntervalType="NONE" alertType="SILENT" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92ZXJwbGVnZXIifQ==" vibrate="true" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9">\n            <content>Hallo dit is Jessie van Noodcentrum Oost-Vlaanderen.\n\nHoe kan ik u verder helpen?</content>\n            <form positiveButtonConfirmation="" negativeButtonCaption="Stoppen" positiveButtonCaption="Verder" negativeButtonConfirmation="">\n                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextBlockWidget" maxChars="200"/>\n            </form>\n        </formMessage>\n        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9sZWVmdGlqZCJ9" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9iZWRhbmt0In0=" vibrate="true" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9">\n            <content>Hoe oud schat u het slachtoffer</content>\n            <form positiveButtonConfirmation="" negativeButtonCaption="Stoppen" positiveButtonCaption="Verder" negativeButtonConfirmation="">\n                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="RangeSliderWidget" max="99.000000" step="1.000000" precision="0" unit="Tussen de &lt;low_value/&gt; en &lt;high_value/&gt; jaar" min="0.000000" lowValue="60.000000" highValue="70.000000"/>\n            </form>\n        </formMessage>\n        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9sZWVmdGlqZF91In0=" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92ZXJwbGVnZXJfdSJ9" vibrate="true" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9">\n            <content>Hoe oud bent u?</content>\n            <form positiveButtonConfirmation="" negativeButtonCaption="Stoppen" positiveButtonCaption="Volgende" negativeButtonConfirmation="">\n                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="SliderWidget" max="99.000000" step="1.000000" precision="0" unit="&lt;value/&gt; jaar" min="0.000000" value="50.000000"/>\n            </form>\n        </formMessage>\n        <resultsFlush id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOCJ9" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZW5kX2dlYmVsZCJ9"/>\n        <resultsFlush id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZW5kX2JlZWluZGlnZCJ9"/>\n        <resultsFlush id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18yMCJ9" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZW5kX2h1bWFuX2NvbW11bmljYXRpb24ifQ=="/>\n    </definition>\n<definition name="demo_crisis" language="nl" startReference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV93ZWxrb20ifQ==">\n    <end id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZW5kX2dlYmVsZCJ9" waitForFollowUpMessage="false"/>\n    <end id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZW5kX2JlZWluZGlnZCJ9" waitForFollowUpMessage="false"/>\n    <end id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZW5kX2h1bWFuX2NvbW11bmljYXRpb24ifQ==" waitForFollowUpMessage="false"/>\n    <message id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV93ZWxrb20ifQ==" alertIntervalType="NONE" alertType="BEEP" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" allowDismiss="false" vibrate="true" autoLock="true">\n        <content>Welkom bij het crisiscentrum.\n\nHoe kunnen we u helpen?</content>\n        <answer action="" caption="Ik heb een spraak of hoor probleem" id="button_doven" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9kb29mMSJ9"/>\n        <answer action="tel://112" caption="Bel ziekenwagen - 112" id="button_112" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92cmFhZyJ9"/>\n        <answer action="tel://+3270245245" caption="Bel antigif - 070/245.245" id="button_antigif" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92cmFhZyJ9"/>\n        <answer action="tel://+3292333444" caption="Bel brandweer - 09/233 34 44" id="button_brandweer" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92cmFhZyJ9"/>\n        <answer action="tel://100" caption="Bel politie - 100" id="button_politie" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92cmFhZyJ9"/>\n    </message>\n    <message id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92cmFhZyJ9" alertIntervalType="NONE" alertType="SILENT" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" allowDismiss="false" vibrate="true" autoLock="true">\n        <content>Bent u geholpen?</content>\n        <answer action="" caption="Ja" id="button_ja" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9zdXJ2ZXkifQ=="/>\n        <answer action="" caption="Neen" id="button_nee" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV93ZWxrb20ifQ=="/>\n    </message>\n    <message id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV90aGFua3MifQ==" alertIntervalType="NONE" alertType="SILENT" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" allowDismiss="false" vibrate="true" autoLock="true">\n        <content>Dank u wel.\n\nWij wensen u verder een prettige dag.</content>\n        <answer action="" caption="OK" id="button_ok" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOCJ9"/>\n    </message>\n    <message id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9kb29mMSJ9" alertIntervalType="NONE" alertType="SILENT" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" allowDismiss="false" vibrate="true" autoLock="true">\n        <content>Hoe kunnen we u helpen?</content>\n        <answer action="" caption="Ziekenwagen" id="button_mug" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlc2NoZWNrIn0="/>\n        <answer action="" caption="Brandweer" id="button_brandweer" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlc2NoZWNrIn0="/>\n        <answer action="" caption="Politie" id="button_Politie" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlc2NoZWNrIn0="/>\n        <answer action="" caption="Ander probleem" id="button_ander" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlc2NoZWNrIn0="/>\n    </message>\n    <message id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlc2NoZWNrIn0=" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" allowDismiss="false" vibrate="true" autoLock="true">\n        <content>Bent u momenteel op het volgende adres:\nKalandenberg 1 te 9000 Gent</content>\n        <answer action="" caption="Ja" id="button_ja" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV93aWUifQ=="/>\n        <answer action="" caption="Nee" id="button_nee" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlcyJ9"/>\n    </message>\n    <message id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV93aWUifQ==" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" allowDismiss="false" vibrate="true" autoLock="true">\n        <content>Hulp is onderweg naar u.\n\nWie is het slachtoffer?</content>\n        <answer action="" caption="Ikzelf" id="button_ikzelf" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9sZWVmdGlqZF91In0="/>\n        <answer action="" caption="Familie of vriend" id="button_familie" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9sZWVmdGlqZCJ9"/>\n        <answer action="" caption="Onbekende" id="button_onbekende" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9sZWVmdGlqZCJ9"/>\n    </message>\n    <message id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9iZWRhbmt0In0=" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" allowDismiss="false" vibrate="true" autoLock="true">\n        <content>Gelieve bij het slachtoffer te blijven en uw toestel bij de hand te houden.\n\nWij contacteren u verder.</content>\n        <answer action="" caption="OK" id="button_OK" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9"/>\n        <answer action="" caption="Ik wens met een verpleger te praten" id="button_praten" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9vcGVyYXRvcmh1bHAifQ=="/>\n    </message>\n    <message id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92ZXJwbGVnZXIifQ==" alertIntervalType="NONE" alertType="SILENT" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" allowDismiss="false" vibrate="true" autoLock="true">\n        <content>(Hier praat verpleger met slachtoffer, of stelt een vraag).</content>\n        <answer action="" caption="OK" id="button_ok" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18yMCJ9"/>\n    </message>\n    <message id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92ZXJwbGVnZXJfdSJ9" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" allowDismiss="false" vibrate="true" autoLock="true">\n        <content>Wenst u nog met een verpleger te praten?</content>\n        <answer action="" caption="Ja" id="button_ja" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9vcGVyYXRvcmh1bHAifQ=="/>\n        <answer action="" caption="Neen" id="button_nee" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9"/>\n    </message>\n    <formMessage id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9zdXJ2ZXkifQ==" alertIntervalType="NONE" alertType="BEEP" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" positiveReference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV90aGFua3MifQ==" vibrate="true" autoLock="true" negativeReference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOCJ9">\n        <content>Gelieve onze dienstverlening te beoordelen .\n\n(1 = zeer slecht, 5 = zeer goed)</content>\n        <form positiveButtonConfirmation="" negativeButtonCaption="Stoppen" positiveButtonCaption="Verder" negativeButtonConfirmation="">\n            <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="SliderWidget" max="5.000000" step="1.000000" precision="0" unit="&lt;value/&gt; op 5" min="1.000000" value="4.000000"/>\n        </form>\n    </formMessage>\n    <formMessage id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9hZHJlcyJ9" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" positiveReference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV93aWUifQ==" vibrate="true" autoLock="true" negativeReference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9">\n        <content>Waar bent u momenteel?</content>\n        <form positiveButtonConfirmation="" negativeButtonCaption="Stoppen" positiveButtonCaption="Verder" negativeButtonConfirmation="">\n            <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextBlockWidget" maxChars="200"/>\n        </form>\n    </formMessage>\n    <formMessage id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9vcGVyYXRvcmh1bHAifQ==" alertIntervalType="NONE" alertType="SILENT" brandingKey="625994D81ACF8B8D9553B047FA71B2544C99B6CEEBF6ED326F66DAD9AC32635D" positiveReference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92ZXJwbGVnZXIifQ==" vibrate="true" autoLock="true" negativeReference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9">\n        <content>Hallo dit is Jessie van Noodcentrum Oost-Vlaanderen.\n\nHoe kan ik u verder helpen?</content>\n        <form positiveButtonConfirmation="" negativeButtonCaption="Stoppen" positiveButtonCaption="Verder" negativeButtonConfirmation="">\n            <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextBlockWidget" maxChars="200"/>\n        </form>\n    </formMessage>\n    <formMessage id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9sZWVmdGlqZCJ9" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" positiveReference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9iZWRhbmt0In0=" vibrate="true" autoLock="true" negativeReference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9">\n        <content>Hoe oud schat u het slachtoffer</content>\n        <form positiveButtonConfirmation="" negativeButtonCaption="Stoppen" positiveButtonCaption="Verder" negativeButtonConfirmation="">\n            <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="RangeSliderWidget" max="99.000000" step="1.000000" precision="0" unit="Tussen de &lt;low_value/&gt; en &lt;high_value/&gt; jaar" min="0.000000" lowValue="60.000000" highValue="70.000000"/>\n        </form>\n    </formMessage>\n    <formMessage id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV9sZWVmdGlqZF91In0=" alertIntervalType="NONE" alertType="SILENT" brandingKey="613B62A5535E01C6DB650006A7006B58DEB10D87A3164C65DD673CC8300A42D3" positiveReference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAibWVzc2FnZV92ZXJwbGVnZXJfdSJ9" vibrate="true" autoLock="true" negativeReference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9">\n        <content>Hoe oud bent u?</content>\n        <form positiveButtonConfirmation="" negativeButtonCaption="Stoppen" positiveButtonCaption="Volgende" negativeButtonConfirmation="">\n            <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="SliderWidget" max="99.000000" step="1.000000" precision="0" unit="&lt;value/&gt; jaar" min="0.000000" value="50.000000"/>\n        </form>\n    </formMessage>\n    <resultsFlush id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOCJ9" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZW5kX2dlYmVsZCJ9"/>\n    <resultsFlush id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18xOSJ9" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZW5kX2JlZWluZGlnZCJ9"/>\n    <resultsFlush id="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZmx1c2hfcmVzdWx0c18yMCJ9" reference="base64:eyJsYW5nIjogIm5sIiwgIm1mZCI6ICJhaEZ6Zm0xdlltbGpZV2RsWTJ4dmRXUm9jbkpKQ3hJS2JXTXRkSEpoWTJ0bGNpSVhaR1Z0Ynk1elpYSjJhV05sUUhKdloyVnlkR2d1WVhRTUN4SVJUV1Z6YzJGblpVWnNiM2RFWlhOcFoyNGlDMlJsYlc5ZlkzSnBjMmx6REEiLCAiaWQiOiAiZW5kX2h1bWFuX2NvbW11bmljYXRpb24ifQ=="/>\n</definition>\n</messageFlowDefinitionSet>\n'
        output = generate_js_flow(service_user, xml, must_validate=True)
        brandings = output['en'][1]
        self.assertEqual(2, len(brandings))

    def testNewFlowMessage(self):
        set_current_user(human_user)

        value = {
           'message': {
               'alert_flags': 0,
               'branding': None,
               'buttons': [{
                    'id': u'id1',
                    'caption': u'caption1',
                    'action': None,
                    'ui_flags': 0
                }, {
                    'id': u'id2',
                    'caption': u'caption2',
                    'action': None,
                    'ui_flags': 0
                }],
               'context': u'context',
               'dismiss_button_ui_flags': 0,
               'flags': 321,
               'key': u'key',
               'members': [{
                    'acked_timestamp': 12345,
                    'button_id': None,
                    'custom_reply': None,
                    'member': human_user.email(),
                    'received_timestamp': 12345,
                    'status': 7
               }],
               'message': u'a_1',
               'message_type': 1,
               'parent_key': None,
               'sender': service_user.email(),
               'threadTimestamp': 0,
               'thread_size': 0,
               'timeout': 0,
               'timestamp': 12345
            }
        }
        r = parse_complex_value(NewFlowMessageRequestTO, value, False)
        self.assertIsInstance(r.message, MessageTO)
        newFlowMessage(r)

    def testNewFlowTextLine(self):
        set_current_user(human_user)

        value = {
            'message': {
                'alert_flags': 0,
                'branding': None,
                'context': u'context',
                'flags': 320,
                'form': {
                    'positive_button': u'Submit',
                    'positive_confirmation': None,
                    'positive_button_ui_flags': 1,
                    'negative_button': u'Cancel',
                    'negative_confirmation': None,
                    'negative_button_ui_flags': 1,
                    'javascript_validation': None,
                    'type': u'text_line',
                    'widget': {"max_chars": 50, "place_holder": None, "value": None}
                },
                'key': u'key',
                'member': {
                    'acked_timestamp': 12345,
                    'button_id': Form.POSITIVE,
                    'custom_reply': None,
                    'member': human_user.email(),
                    'received_timestamp': 12345,
                    'status': 7
                },
                'message': u'0',
                'message_type': 2,
                'parent_key': None,
                'sender': service_user.email(),
                'threadTimestamp': 0,
                'thread_size': 0,
                'timestamp': 12345
            },
            "form_result": {
                "type": u"unicode_result",
                "result": {
                    "value": u"Yyy"
                }
            }
        }
        r = parse_complex_value(NewFlowMessageRequestTO, value, False)
        self.assertIsInstance(r.message, FormMessageTO)
        self.assertIsInstance(r.message.form.widget, TextLineTO)
        self.assertIsInstance(r.form_result, FormResult)
        self.assertIsInstance(r.form_result.result, UnicodeWidgetResult)
        newFlowMessage(r)

    def testNewFlowRangeSlider(self):
        set_current_user(human_user)

        value = {
            'message': {
                'alert_flags': 0,
                'branding': None,
                'context': u'context',
                'flags': 320,
                'form': {
                    'positive_button': u'Submit',
                    'positive_confirmation': None,
                    'positive_button_ui_flags': 1,
                    'negative_button': u'Cancel',
                    'negative_confirmation': None,
                    'negative_button_ui_flags': 1,
                    'javascript_validation': None,
                    'type': u'range_slider',
                    'widget': {
                        "max": 100,
                        "min": 0,
                        "step": 2,
                        "unit": u"$<low_value/> - $<high_value/>",
                        "low_value": 10,
                        "high_value": 90,
                        "precision": 2
                    }
                },
                'key': u'key',
                'member': {
                    'acked_timestamp': 12345,
                    'button_id': Form.POSITIVE,
                    'custom_reply': None,
                    'member': human_user.email(),
                    'received_timestamp': 12345,
                    'status': 7
                },
                'message': u'0',
                'message_type': 2,
                'parent_key': None,
                'sender': service_user.email(),
                'threadTimestamp': 0,
                'thread_size': 0,
                'timestamp': 12345
            },
            "form_result": {
                "type": u"float_list_result",
                "result": {
                    "values": [0, 7]
                }
            }
        }
        r = parse_complex_value(NewFlowMessageRequestTO, value, False)
        self.assertIsInstance(r.message, FormMessageTO)
        self.assertIsInstance(r.message.form.widget, RangeSliderTO)
        self.assertIsInstance(r.form_result.result, FloatListWidgetResult)
        newFlowMessage(r)
        m = get_message(r.message.key, r.message.parent_key)
        ms = m.memberStatusses[m.members.index(human_user)]
        self.assertEqual(ms.status, 7)
        self.assertEqual(ms.form_result.result.values, [0, 7])

    def testMessageFlowMemberResult(self):
        set_current_user(human_user)

        value = {
            "flush_id": u"flush_1",
            "run": {
                "parent_message_key": u"_js_key/1e51148-156e-7f86-9d21-dc5fb07a720e",
                "steps": [{
                    "received_timestamp": 1358241794,
                    "message_key": u"_js_key/1e51148-156e-7f86-9d21-dc5fb07a720e",
                    "button": u"Roger that!",
                    "step_type": u"message_step",
                    "step_id": u"message_1",
                    "message": u"*****",
                    "acknowledged_timestamp": 1358241801,
                    "answer_id": None
                }, {
                    "received_timestamp": 1358241802,
                    "message_key": u"_js_key/5ace34fd-eea7-4b41-51e3-bd79585fd08b",
                    "button": u"Submit",
                    "step_type": u"form_step",
                    "form_result": { "type": u"unicode_result", "result" : {"value": u"test123"}},
                    "step_id": u"message_2",
                    "message": u"*****",
                    "answer_id": u"positive",
                    "display_value": u"test123",
                    "acknowledged_timestamp": 1358241814
                }, {
                    "received_timestamp": 1358241814,
                    "message_key": u"_js_key/871ef182-710c-1132-95bc-32c55886af83",
                    "button": u"Submit",
                    "step_type": u"form_step",
                    "form_result": { "type": u"unicode_result", "result" : {"value": u"test456"}},
                    "step_id": u"message_3",
                    "message": u"*****",
                    "answer_id": u"positive",
                    "display_value": u"test456",
                    "acknowledged_timestamp": 1358241858
                }, {
                    "received_timestamp": 1358241858,
                    "message_key": u"_js_key/25b1a512-3c35-5e31-9fb2-90dee433fd00",
                    "button": u"Submit",
                    "step_type": u"form_step",
                    "form_result": { "type": u"unicode_result", "result" : {"value": u"def"}},
                    "step_id": u"message_4",
                    "message": u"*****",
                    "answer_id": u"positive",
                    "display_value": u"def",
                    "acknowledged_timestamp": 1358241869
                }, {
                    "received_timestamp": 1358241870,
                    "message_key": u"_js_key/f524e048-a2a2-91a6-9344-332292121a00",
                    "button": u"Submit",
                    "step_type": u"form_step",
                    "form_result": { "type": u"unicode_result", "result" : {"value": u"c"}},
                    "step_id": u"message_5",
                    "message": u"*****",
                    "answer_id": u"positive",
                    "display_value": u"C",
                    "acknowledged_timestamp": 1358241872
                }, {
                    "received_timestamp": 1358241872,
                    "message_key": u"_js_key/f929387b-5929-d1a3-c340-1e41e52584f4",
                    "button": u"Submit",
                    "step_type": u"form_step",
                    "form_result": { "type": u"unicode_list_result", "result" : {"values": [u"b", u"c", u"d"]}},
                    "step_id": u"message_6",
                    "message": u"*****",
                    "answer_id": u"positive",
                    "display_value": u"B\nC\nD",
                    "acknowledged_timestamp": 1358241912
                }, {
                    "received_timestamp": 1358241913,
                    "message_key": u"_js_key/56ad47fe-474d-3ad1-dc0f-792c222d9fe0",
                    "button": u"Submit",
                    "step_type": u"form_step",
                    "form_result": { "type": u"long_result", "result" : {"value": 1358244900}},
                    "step_id": u"message_7",
                    "message": u"*****",
                    "answer_id": u"positive",
                    "display_value": u"January 15, 2013 10:15",
                    "acknowledged_timestamp": 1358241916
                }, {
                    "received_timestamp": 1358241917,
                    "message_key": u"_js_key/1786c22-e076-fefe-59d7-b597ab4fd7c8",
                    "button": u"Submit",
                    "step_type": u"form_step",
                    "form_result": { "type": u"float_result", "result" : {"value": 6}},
                    "step_id": u"message_8",
                    "message": u"*****",
                    "answer_id": u"positive",
                    "display_value": u"6",
                    "acknowledged_timestamp": 1358241920
                }, {
                    "received_timestamp": 1358241920,
                    "message_key": u"_js_key/f4d28fa8-6e54-f978-7064-88284adaab9b",
                    "button": u"Submit",
                    "step_type": u"form_step",
                    "form_result": { "type": u"float_list_result", "result" : {"values": [7, 9]}},
                    "step_id": u"message_9",
                    "message": u"*****",
                    "answer_id": u"positive",
                    "display_value": u"7 - 9",
                    "acknowledged_timestamp": 1358241925
                }],
                "sender": service_user.email(),
                "context": u"MENU_4fccdc92-6a4f-4244-87e8-6afe7bee9fc7",
                "message_flow_run_id": u"9b2b91ef-4295-903e-f08a-1e2fc937797a"
            },
            "end_id": None
        }
        r = parse_complex_value(MessageFlowMemberResultRequestTO, value, False)
        self.assertIsInstance(r.run, JsMessageFlowMemberRunTO)
        self.assertIsInstance(r.run.steps[0], MessageFlowStepTO)
        self.assertIsInstance(r.run.steps[8], FormFlowStepTO)
        self.assertIsInstance(r.run.steps[8].form_result.result, FloatListWidgetResult)
        messageFlowMemberResult(r)
