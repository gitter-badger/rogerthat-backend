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

import json
import logging

from rogerthat.bizz.service.mfd import save_message_flow, delete_message_flow_by_name, \
    MessageFlowDesignLevelTooDeepException, MessageFlowDesignLoopException
from rogerthat.bizz.service.mfr import MessageFlowDesignValidationException
from rogerthat.dal import parent_key
from rogerthat.dal.mfd import get_service_message_flow_design_by_name, get_service_message_flow_designs
from rogerthat.dal.profile import get_service_profile
from rogerthat.models import MessageFlowDesign
from rogerthat.models.properties.messaging import JsFlowDefinitions
from rogerthat.rpc import users
from rogerthat.rpc.service import BusinessException
from rogerthat.utils import now, azzert
from google.appengine.ext import webapp


SAMPLE_MF = '{"modules":[{"config":{"position":[7,6]},"name":"Start","value":{}},{"config":{"position":[504,474]},"name":"End","value":{"id":"bye","waitForFollowUpMessage":false}},{"config":{"messageDef":{"buttons_group":{"buttons_list":[{"action":"","caption":"Fine","id":"ok"},{"action":"","caption":"Felt better before","id":"not_ok"}]},"id":"sense","message":"How do you feel ?","settings_group":{"alert_interval":"NONE","alert_type":"BEEP","auto_lock":"true","branding":"","rogerthat_button":false,"vibrate":true}},"position":[277,75]},"name":"Message","value":{}},{"config":{"messageDef":{"buttons_group":{"buttons_list":[{"action":"tel://+32 9 324 25 64","caption":"Call doctor","id":"call_doctor"}]},"id":"doctor","message":"Please go see a doctor","settings_group":{"alert_interval":"NONE","alert_type":"BEEP","auto_lock":"true","branding":"","rogerthat_button":false,"vibrate":true}},"position":[467,245]},"name":"Message","value":{}},{"config":{"messageDef":{"buttons_group":{"buttons_list":[]},"id":"greet","message":"Super duper! Have a nice day.","settings_group":{"alert_interval":"NONE","alert_type":"BEEP","auto_lock":"true","branding":"","rogerthat_button":true,"vibrate":true}},"position":[24,243]},"name":"Message","value":{}},{"config":{"position":[202,412]},"name":"Results flush","value":{"id":"flush"}}],"properties":{"description":"","multilanguage":false,"name":"Sample message flow","test_account":"","test_language":null},"wires":[{"src":{"moduleId":0,"terminal":"out"},"tgt":{"moduleId":2,"terminal":"in"}},{"src":{"moduleId":2,"terminal":"Fine"},"tgt":{"moduleId":4,"terminal":"in"}},{"src":{"moduleId":2,"terminal":"Felt better before"},"tgt":{"moduleId":3,"terminal":"in"}},{"src":{"moduleId":4,"terminal":"roger that"},"tgt":{"moduleId":5,"terminal":"in"}},{"src":{"moduleId":3,"terminal":"Call doctor"},"tgt":{"moduleId":5,"terminal":"in"}},{"src":{"moduleId":5,"terminal":"out"},"tgt":{"moduleId":1,"terminal":"end"}}]}'

class SaveWiringHandler(webapp.RequestHandler):

    def post(self):
        service_user = users.get_current_user()
        azzert(get_service_profile(service_user))  # want an existing service profile
        logging.info(self.request.headers['Content-Type'])
        self.response.headers['Content-Type'] = 'application/json'
        wiring_id = self.request.get('name', None)
        design = self.request.get('working', None)
        language = self.request.get('language', None)
        force = self.request.get('force', None) == "true"
        multilanguage = self.request.get('multilanguage', None) == "true"

        logging.info("MULTI LANGUAGE = %s" % multilanguage)

        logging.info("save wiring request: %s" % self.request.body)

        error = None
        try:
            message_flow_design = save_message_flow(service_user, wiring_id, design, language, force, multilanguage)
        except MessageFlowDesignValidationException, e:
            message_flow_design = e.message_flow_design
        except MessageFlowDesignLevelTooDeepException, e:
            message_flow_design = e.message_flow_design
            error = message_flow_design.validation_error
        except MessageFlowDesignLoopException, e:
            message_flow_design = e.message_flow_design
            error = message_flow_design.validation_error

        result = dict(error=error, status=message_flow_design.status, force=force)
        if message_flow_design.status != MessageFlowDesign.STATUS_VALID:
            result['error_message'] = message_flow_design.validation_error
            result['broken_sub_flows'] = [k.name() for k in message_flow_design.broken_sub_flows]

        json.dump(result, self.response.out)

class LoadWiringHandler(webapp.RequestHandler):

    def get(self):
        service_user = users.get_current_user()
        azzert(get_service_profile(service_user))  # must exist
        message_flow_designs = get_service_message_flow_designs(service_user)

        result = []
        for wiring in message_flow_designs:
            if wiring.deleted or not wiring.definition:
                continue

            wiringDefinition = json.loads(wiring.definition)
            for k in wiringDefinition.iterkeys():
                if k == u"modules":
                    for m in wiringDefinition[k]:
                        if m["value"]:
                            m["config"]["formMessageDef"] = m["value"]

            result.append({"name": wiring.name, "language": wiring.language, "working": json.dumps(wiringDefinition)})

        if not result:
            wiring_id = "Sample message flow"
            language = "MessageFlow"
            result.append({"name": wiring_id, "language": language, "working": SAMPLE_MF})
            message_flow_design = MessageFlowDesign(parent=parent_key(service_user), key_name=wiring_id)
            message_flow_design.definition = SAMPLE_MF
            message_flow_design.name = wiring_id
            message_flow_design.language = language
            message_flow_design.design_timestamp = now()
            message_flow_design.status = MessageFlowDesign.STATUS_VALID
            message_flow_design.js_flow_definitions = JsFlowDefinitions()
            message_flow_design.put()
        self.response.out.write(json.dumps(result))

class DeleteWiringHandler(webapp.RequestHandler):

    def post(self):
        service_user = users.get_current_user()
        azzert(get_service_profile(service_user))  # must exist
        wiring_id = self.request.get('name', None)
        result = dict(error=None)
        try:
            delete_message_flow_by_name(service_user, wiring_id)
        except BusinessException, e:
            result['error'] = e.message
        json.dump(result, self.response.out)

class DownloadAsXMLHandler(webapp.RequestHandler):

    def get(self):
        service_user = users.get_current_user()
        azzert(get_service_profile(service_user))  # must exist
        wiring_id = self.request.get('name', None)
        type_ = self.request.get('type', None)
        message_flow_design = get_service_message_flow_design_by_name(service_user, wiring_id)
        if not message_flow_design:
            # TODO: error popup instead of killing the user flow; shouldnt this be 404?
            self.response.set_status(400)
            self.response.out.write("Message flow design '%s' not found" % wiring_id)

        if type_ == 'XML':
            if message_flow_design.status != MessageFlowDesign.STATUS_VALID:
                # TODO: error popup instead of killing the user flow; shouldnt this be 404?
                self.response.set_status(400)
                self.response.out.write("Message flow design should not be broken")
                return
            self.response.headers['Content-Type'] = 'text/xml; charset=utf8'
            self.response.headers['Content-Disposition'] = 'attachment; filename=%s.xml' % wiring_id.encode('utf-8')
            self.response.out.write(message_flow_design.xml)
            return
        self.response.headers['Content-Type'] = 'text/json; charset=utf8'
        self.response.headers['Content-Disposition'] = 'attachment; filename=%s.json' % wiring_id.encode('utf-8')
        self.response.out.write(message_flow_design.definition)
