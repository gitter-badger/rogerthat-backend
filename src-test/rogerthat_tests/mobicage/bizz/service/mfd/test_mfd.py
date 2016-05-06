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

import mc_unittest
from rogerthat.bizz.service.mfd.sub import parsexml_, MessageFlowRunSub
import StringIO

class Test(mc_unittest.TestCase):

    def testLoadMFR(self):
        xml_string = """<messageFlowRun launchTimestamp="1" xmlns="https://rogerth.at/api/1/MessageFlow.xsd"><definition startReference="model" name="Baudi Car configurator"><end id="cool"/><end id="looser"/><message alertIntervalType="NONE" alertType="BEEP" vibrate="true" autoLock="false" allowDismiss="false" id="model"><content>Which Baudi model are you interested in ?</content><answer reference="congrats" id="B1" action="" caption="B1"/><answer reference="retry" id="B3" action="" caption="B3"/><answer reference="retry" id="B4" action="" caption="B4"/><answer reference="retry" id="B5" action="" caption="B5"/></message><message alertIntervalType="NONE" alertType="BEEP" vibrate="true" autoLock="false" dismissReference="cool" allowDismiss="true" id="congrats"><content>Congratulations, excellent choice. Small cars are handy, economical, environment friendly and easy to park!</content></message><message alertIntervalType="NONE" alertType="BEEP" vibrate="true" autoLock="false" dismissReference="model" allowDismiss="true" id="retry"><content>Not a valid option, try again!</content><answer reference="looser" id="moehahaha" action="" caption="I give up"/></message></definition><memberRun status="FINISHED" name="Geert example" email="geert@example.com"><step xsi:type="MessageStep" acknowledgedTimestamp="1324546083" receivedTimestamp="1324545998" nextStep="cff3ee44-67de-4f46-abf7-1cb43567d80a" definition="model" creationTimestamp="1324545998" id="ebbdb9e3-11cb-4e0f-b46b-538af7d544f1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/><step xsi:type="MessageStep" acknowledgedTimestamp="1324546107" receivedTimestamp="1324546090" nextStep="d3f6d81d-ec1e-4265-9b85-5d129437b857" previousStep="ebbdb9e3-11cb-4e0f-b46b-538af7d544f1" definition="retry" creationTimestamp="1324546089" id="cff3ee44-67de-4f46-abf7-1cb43567d80a" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/><step xsi:type="MessageStep" acknowledgedTimestamp="1324546112" receivedTimestamp="1324546108" nextStep="98cf08ce-563c-45b2-8b29-a71c22ef31fa" previousStep="cff3ee44-67de-4f46-abf7-1cb43567d80a" definition="model" creationTimestamp="1324546108" id="d3f6d81d-ec1e-4265-9b85-5d129437b857" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/><step xsi:type="MessageStep" acknowledgedTimestamp="1324546119" receivedTimestamp="1324546114" previousStep="d3f6d81d-ec1e-4265-9b85-5d129437b857" definition="congrats" creationTimestamp="1324546113" id="98cf08ce-563c-45b2-8b29-a71c22ef31fa" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/></memberRun></messageFlowRun>"""
        doc = parsexml_(StringIO.StringIO(xml_string))
        rootNode = doc.getroot()
        mfr = MessageFlowRunSub.factory()
        mfr.build(rootNode)
        self.assertTrue(isinstance(mfr, MessageFlowRunSub))
        self.assertEqual(len(mfr.definition), 1)
        self.assertEqual("Baudi Car configurator", mfr.definition[0].name)
