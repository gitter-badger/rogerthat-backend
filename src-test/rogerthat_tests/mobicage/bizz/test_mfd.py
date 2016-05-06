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
from xml.dom.minidom import parseString

from rogerthat.bizz.i18n import _translate_all_message_flows
from rogerthat.bizz.profile import create_user_profile
from rogerthat.bizz.service import convert_user_to_service
from rogerthat.bizz.service.mfd import create_json_id, save_message_flow, delete_message_flow_by_name, \
    MFD_MODULE_START, MFD_MODULE_END, MFD_MODULE_MESSAGE_FLOW, MFD_MODULE_MESSAGE, MFD_MODULE_AUTO_COMPLETE, \
    MFD_MODULE_DATE_SELECT, MFD_MODULE_MULTI_SELECT, MFD_MODULE_RANGE_SLIDER, MFD_MODULE_SINGLE_SELECT, \
    MFD_MODULE_SINGLE_SLIDER, MFD_MODULE_TEXT_BLOCK, MFD_MODULE_TEXT_LINE, \
    MessageFlowDesignLevelTooDeepException, MessageFlowDesignLoopException, MFD_FORM_MODULES, message_flow_design_to_xml, \
    MFD_MODULE_RESULTS_FLUSH, MFD_MODULE_PHOTO_UPLOAD, MFD_MODULE_GPS_LOCATION, MFD_MODULE_RESULTS_EMAIL, MFD_MODULE_MYDIGIPASS, \
    MFD_MODULE_ADVANCED_ORDER
from rogerthat.bizz.service.mfr import _create_message_flow_run_xml_doc
from rogerthat.dal.mfd import get_super_message_flows
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.service import get_default_service_identity
from rogerthat.models import MessageFlowDesign, ServiceIdentity, MessageFlowRunRecord, App
from rogerthat.models.properties.forms import MdpScope
from rogerthat.rpc import users
from rogerthat.rpc.service import BusinessException
from rogerthat.utils import now
from rogerthat.utils.service import create_service_identity_user
from google.appengine.ext import db
import mc_unittest
from rogerthat_tests.i18n.test_services import translate_service_strings


STATUS_MAP = {
    MessageFlowDesign.STATUS_VALID: "VALID",
    MessageFlowDesign.STATUS_BROKEN: "BROKEN",
    MessageFlowDesign.STATUS_SUBFLOW_BROKEN: "SUBFLOW_BROKEN"
}

class MFDUtil(object):

    def __init__(self, mfd_name):
        self.name = mfd_name
        self.design = dict(modules=list(), wires=list())
        self.start = None
        self.messages = list()
        self.form_messages = list()
        self.flushes = list()
        self.ends = list()
        self.message_flows = list()
        self.service = users.get_current_user()

    def _create_default_form_settings(self, module_name):
        if module_name in [MFD_MODULE_TEXT_LINE, MFD_MODULE_TEXT_BLOCK, MFD_MODULE_AUTO_COMPLETE]:
            return dict(max_chars='50', place_holder='', value='')
        if module_name == MFD_MODULE_SINGLE_SELECT:
            return dict(value='')
        if module_name == MFD_MODULE_MULTI_SELECT:
            return dict()
        if module_name == MFD_MODULE_DATE_SELECT:
            return dict(mode='date_time', minute_interval='', unit='')
        if module_name in [MFD_MODULE_SINGLE_SLIDER, MFD_MODULE_RANGE_SLIDER]:
            return dict(min='0', max='10', step='', precision='', unit='', value='', low_value='', high_value='')
        if module_name == MFD_MODULE_PHOTO_UPLOAD:
            return dict(crop=True, ratio='200x200', quality='best', source='gallery_camera')
        if module_name == MFD_MODULE_GPS_LOCATION:
            return dict(gps=True)
        if module_name == MFD_MODULE_MYDIGIPASS:
            return dict()
        if module_name == MFD_MODULE_ADVANCED_ORDER:
            return dict(currency="€", leap_time=3600)
        assert False, "No form_settings_group configured in mfd.py form module '%s'" % module_name

    def _create_other_form_settings(self, module_name):
        if module_name == MFD_MODULE_AUTO_COMPLETE:
            return [{"suggestions_group":{"suggestions_list":[{"value":"abc"}, {"value":"def"}]}}]
        if module_name in [MFD_MODULE_SINGLE_SELECT, MFD_MODULE_MULTI_SELECT]:
            o = [{"choices_group":{"choices_list":[{"value":"a", "label":"A"},
                                                   {"value":"b", "label":"B"},
                                                   {"value":"c", "label":"C"},
                                                   {"value":"d", "label":"D"}]}}]
            if module_name == MFD_MODULE_MULTI_SELECT:
                o.append({"initial_choices_group":{"initial_choices_list":[{"value":"a"},
                                                                           {"value":"b"},
                                                                           {"value":"c"}]}})
            return o
        if module_name == MFD_MODULE_MYDIGIPASS:
            return [{'mdp_scopes_group': { scope: True for scope in MdpScope.all() }}]
        if module_name == MFD_MODULE_ADVANCED_ORDER:
            return [{"advanced_order_group" : {"category_list": [{"id": "category-drinks",
                                                               "name": "Drinks",
                                                               "category_item_list" :[{"id": "item-drinks-cola",
                                                                                       "name": "Cola",
                                                                                       "description": None,
                                                                                       "value": 0,
                                                                                       "unit": "l",
                                                                                       "unitPrice": 160,
                                                                                       "hasPrice": True,
                                                                                       "step": 50,
                                                                                       "stepUnit": "cl",
                                                                                       "stepUnitConversion": 100,
                                                                                       "imageUrl": "http://www.rogerthat.net/wp-content/uploads/2012/09/rogerthat-logo.png"
                                                                                       }]
                                                               }]
                                               }
                     }]

        return None

    def save(self):
        return save_message_flow(self.service, self.name, json.dumps(self.design), language="en", force=True,
                                 multilanguage=True)

    def add_start_module(self):
        assert self.start is None
        start = self.create_start_module()
        self.design["modules"].append(start)
        self.start = start
        return start

    def add_message_module(self, id_=None, allowDismiss=True, button_ids=None):
        if id_ is None:
            id_ = self.name
        assert isinstance(id_, (str, unicode))
        msg = self.create_message_module(id_, allowDismiss, button_ids or list())
        self.design["modules"].append(msg)
        self.messages.append(msg)
        return msg

    def add_form_message_module(self, module_name, id_=None, widget_settings=None, other_settings=None):
        id_ = self.name if id is None else id_
        assert isinstance(id_, (str, unicode))
        widget_settings = self._create_default_form_settings(module_name) if widget_settings is None else widget_settings
        other_settings = self._create_other_form_settings(module_name) if other_settings is None else other_settings

        fm = self.create_form_message_module(module_name, id_, widget_settings, other_settings)
        self.design["modules"].append(fm)
        self.form_messages.append(fm)
        return fm

    def add_flush_module(self, id_=None):
        if id_ is None:
            id_ = self.name
        assert isinstance(id_, (str, unicode))
        flush = self.create_flush_module(id_)
        self.design["modules"].append(flush)
        self.flushes.append(flush)
        return flush

    def add_email_module(self, id_=None):
        if id_ is None:
            id_ = self.name
        assert isinstance(id_, (str, unicode))
        email_ = self.create_email_module(id_)
        self.design["modules"].append(email_)
        self.flushes.append(email_)
        return email_

    def add_end_module(self, id_=None):
        if id_ is None:
            id_ = self.name
        assert isinstance(id_, (str, unicode))
        end = self.create_end_module(id_)
        self.design["modules"].append(end)
        self.ends.append(end)
        return end

    def add_message_flow_module(self, mfd):
        assert isinstance(mfd, MessageFlowDesign)
        sf = self.create_message_flow_module(mfd)
        self.design["modules"].append(sf)
        self.message_flows.append(sf)
        return sf

    def remove_module(self, module):
        self.design["modules"].remove(module)
        module_name = module['name']
        if module_name == MFD_MODULE_START:
            self.start = None
        elif module_name == MFD_MODULE_MESSAGE:
            self.messages.remove(module)
        elif module_name in MFD_FORM_MODULES:
            self.form_messages.remove(module)
        elif module_name == MFD_MODULE_MESSAGE_FLOW:
            self.message_flows.remove(module)
        elif module_name == MFD_MODULE_END:
            self.ends.remove(module)

    def add_wire(self, src, src_terminal, tgt, tgt_terminal):
        wire = self.create_wire(src, src_terminal, tgt, tgt_terminal)
        self.design["wires"].append(wire)
        return wire

    def auto_break(self):
        self.design["wires"].pop(0)
        return self.save()

    def auto_fix(self):
        wire = self.create_wire(self.start, "start", self.messages[0], "in")
        self.design["wires"].insert(0, wire)
        return self.save()

    def create_start_module(self):
        return {"name": MFD_MODULE_START}

    def create_end_module(self, id_, wff=False):
        return {"name": MFD_MODULE_END, "value": {"id": id_, "waitForFollowUpMessage": wff}}

    def create_flush_module(self, id_):
        return {"name": MFD_MODULE_RESULTS_FLUSH, "value": {"id": id_}}

    def create_email_module(self, id_):
        return {"name": MFD_MODULE_RESULTS_EMAIL, "value": {"id": id_, "emailadmins": True, "emails_group": {"emails_list": []}}}

    def create_message_flow_module(self, mfd):
        return { "name": MFD_MODULE_MESSAGE_FLOW, "value": {"nmessage_flow": str(mfd.key())}}

    def create_message_module(self, id_, allowDismiss, button_ids):
        return {
            "name": MFD_MODULE_MESSAGE,
            "config": {
                "messageDef": {
                    "id": id_,
                    "message": id_,
                    "settings_group": {
                        "alert_interval": "NONE",
                        "alert_type": "BEEP",
                        "auto_lock": True,
                        "branding": "",
                        "rogerthat_button": allowDismiss,
                        "vibrate": False,
                    },
                    "buttons_group": {
                        "buttons_list": [ {"action":"confirm://This is a test", "id":id_, "caption":id_} for id_ in button_ids ]
                    }
                }
            }
        }

    def create_form_message_module(self, module_name, id_, widget_settings, other_settings):
        module = {
            "name": module_name,
            "value": {
                "id": id_,
                "message": id_,
                "form_settings_group": {
                    "negative_caption": "Cancel",
                    "negative_confirmation": "",
                    "positive_caption": "Submit",
                    "positive_confirmation": "",
                    "javascript_validation": ""
                },
                "message_settings_group": {
                    "alert_interval": "NONE",
                    "alert_type": "BEEP",
                    "auto_lock": True,
                    "branding": "",
                    "vibrate": False,
                }
            }
        }
        module['value']['form_settings_group'].update(widget_settings)
        if other_settings:
            for other_group in other_settings:
                module["value"].update(other_group)
        return module

    def create_wire(self, src, src_terminal, tgt, tgt_terminal):
        return {
            "src": {
                "moduleId": self.design["modules"].index(src),
                "terminal": src_terminal
            },
            "tgt": {
                 "moduleId": self.design["modules"].index(tgt),
                 "terminal": tgt_terminal
            }
        }

    def link_message_flow(self, mfd):
        # Add button to last message and connect it to end module
        # Connect roger that button to sub flow module
        self.add_message_flow_module(mfd)
        wire = self.design["wires"].pop()
        assert wire['tgt']['terminal'] == 'end', "For simplicity reasons the last wire should point to an END module"
        self.messages[-1]['config']['messageDef']['buttons_group']['buttons_list'].append({'id':mfd.name, 'caption':mfd.name, 'action':''})
        self.add_wire(self.messages[-1], "roger that", self.message_flows[-1], "in")
        self.add_wire(self.messages[-1], mfd.name, self.ends[0], 'end')
        return self.save()



# TODO: testEmptyFormWidgetId
# TODO: testEmptyCodeBlockId
# TODO: testEmptySubMessageFlow
# TODO: testDuplicateButtonIds
# TODO: testDuplicateButtonCaptions
# TODO: testIllegalButtonCaptions (end/in/roger that)
class Test(mc_unittest.TestCase):

    def setUp(self, datastore_hr_probability=None):
        super(Test, self).setUp()
        if datastore_hr_probability is None:
            self.set_datastore_hr_probability(1)
            user = users.get_current_user()
            convert_user_to_service(user)
            service_profile = get_service_profile(user)
            service_profile.supportedLanguages = ["en", "fr", "nl"]
            service_profile.put()
            si = get_default_service_identity(service_profile.service_user)
            si.appIds = [App.APP_ID_ROGERTHAT, App.APP_ID_OSA_LOYALTY]
            si.put()

    def delete(self, mfd_name):
        delete_message_flow_by_name(users.get_current_user(), mfd_name)

    def createLinearHierarchy(self, mfd_names):
        hierarchy = list()

        for mfd_name in reversed(mfd_names):
            mfdUtil = MFDUtil(mfd_name)
            start = mfdUtil.add_start_module()
            msg = mfdUtil.add_message_module(mfd_name)
            mfdUtil.add_wire(start, "start", msg, "in")

            if hierarchy:
                sub = mfdUtil.add_message_flow_module(hierarchy[0][1])
                mfdUtil.add_wire(msg, "roger that", sub, "in")
            else:
                end = mfdUtil.add_end_module()
                mfdUtil.add_wire(msg, "roger that", end, "end")

            mfd = mfdUtil.save()
            self.assertStatusValid(mfd)
            if hierarchy:
                self.assertEqual(len(mfd.sub_flows), 1)
                self.assertEqual(mfd.sub_flows[0], hierarchy[0][1].key())

            hierarchy.insert(0, (mfdUtil, mfd))

        return hierarchy

    def mfd_str(self, mfd):
        s = STATUS_MAP.get(mfd.status, "+".join([v for (k, v) in STATUS_MAP.iteritems() if mfd.status & k == k]))
        broken_subs = [str(k.name()) for k in mfd.broken_sub_flows]
        return "MFD: %s\n    status: %s\n    error: %s\n    broken subflows: %s" % (mfd.name, s, mfd.validation_error, broken_subs)

    def assertStatusValid(self, mfd):
        msg = self.mfd_str(mfd)
        self.assertEqual(mfd.status, MessageFlowDesign.STATUS_VALID, msg)
        self.assertFalse(mfd.validation_error, msg)
        self.assertFalse(mfd.broken_sub_flows, msg)
        self.assertTrue(mfd.xml, msg)
        self.assertTrue(mfd.js_flow_definitions.values(), msg)

    def assertStatusBroken(self, mfd):
        msg = self.mfd_str(mfd)
        self.assertEqual(mfd.status & MessageFlowDesign.STATUS_BROKEN, MessageFlowDesign.STATUS_BROKEN, msg)
        self.assertTrue(mfd.validation_error, msg)
        self.assertFalse(mfd.sub_flows, msg)
        self.assertFalse(mfd.broken_sub_flows, msg)
        self.assertFalse(mfd.xml, msg)
        self.assertFalse(mfd.js_flow_definitions.values(), msg)

    def assertStatusSubFlowBroken(self, mfd, broken_sub_flows):
        msg = self.mfd_str(mfd)
        self.assertEqual(mfd.status & MessageFlowDesign.STATUS_SUBFLOW_BROKEN, MessageFlowDesign.STATUS_SUBFLOW_BROKEN, msg)
        self.assertTrue(mfd.sub_flows, msg)
        self.assertTrue(mfd.broken_sub_flows, msg)
        self.assertTrue(set(mfd.broken_sub_flows).issubset(set(mfd.sub_flows)), msg)
        self.assertFalse(mfd.xml, msg)
        self.assertFalse(mfd.js_flow_definitions.values(), msg)
        if broken_sub_flows:
            broken_keys = set([f.key() for f in broken_sub_flows])
            self.assertFalse(broken_keys.difference(set(mfd.broken_sub_flows)), msg)

    def validateLinearCircularFlows(self, linear_hierarchy):
        hierarchy = list()

        # Create reversed copy of hierarchy with up to date MFDs from DB
        for mfdUtil, mfd in reversed(linear_hierarchy):
            hierarchy.append((mfdUtil, db.get(mfd.key())))

        for _, mfd in hierarchy:
            self.assertStatusValid(mfd)

        # Build list of IDs that should be present in the XML
        ids = list()
        for mfdUtil, mfd in hierarchy:
            for module in mfdUtil.ends:
                ids.append(create_json_id(mfd, "end_", module['value']['id']))
            for module in mfdUtil.messages:
                ids.append(create_json_id(mfd, "message_", module['config']['messageDef']['id']))
            for module in mfdUtil.form_messages:
                ids.append(create_json_id(mfd, "message_", module['value']['id']))

        # Check that all IDs are present + check if there are no double messages in XML
        for _, mfd in hierarchy:
            element_ids_found = list()
            xml_doc = parseString(mfd.xml)
            for child in xml_doc.documentElement.childNodes:
                if child.nodeType == xml_doc.ELEMENT_NODE:
                    element_ids_found.append(child.getAttribute('id'))
            self.assertEqual(len(element_ids_found), len(set(element_ids_found)), "MFD '%s' has duplicate elements in its XML" % mfd.name)
            self.assertEqual(len(element_ids_found), len(ids), "MFD '%s' has an incorrect amount of elements in its XML" % mfd.name)

        message_ids = list()
        for mfdUtil, mfd in hierarchy:
            id_ = create_json_id(mfd, "message_", mfdUtil.messages[0]['config']['messageDef']['id'])
            message_ids.append(id_)

        # Check references
        references = dict()
        last_i = len(message_ids) - 1
        for i in xrange(len(message_ids)):
            j = 0 if i == last_i else i + 1
            references[message_ids[j]] = message_ids[i]

        for _, mfd in hierarchy:
            element_ids_found = list()
            xml_doc = parseString(mfd.xml)
            for child in xml_doc.documentElement.childNodes:
                if child.nodeName == 'message':
                    self.assertEqual(child.getAttribute('dismissReference'), references[child.getAttribute('id')], "Incorrect references in MFD '%s'" % mfd.name)

    def _getTextLineFormGroupSettings(self):
        settings = dict()
        settings['max_chars'] = "50"
        settings['place_holder'] = "place_holder"
        settings['value'] = "value"
        return settings

    def testIllegalButtonCaptions(self):
        for illegal_caption in ['in', 'end', 'roger that']:
            mfdUtil = MFDUtil("A")
            start_a = mfdUtil.add_start_module()
            msg_a_1 = mfdUtil.add_message_module("a_1", button_ids=[illegal_caption])
            end_a_1 = mfdUtil.add_end_module("a_1")

            mfdUtil.add_wire(start_a, "start", msg_a_1, illegal_caption)
            mfdUtil.add_wire(msg_a_1, illegal_caption, end_a_1, "end")

            self.assertStatusBroken(mfdUtil.save())

    def testFormMessages(self):
        mfdUtil = MFDUtil("A")
        forms = list()
        start_a = mfdUtil.add_start_module()
        for m in MFD_FORM_MODULES:
            print 'Adding MFD module: %s' % m
            forms.append(mfdUtil.add_form_message_module(m, str(MFD_FORM_MODULES.index(m))))
        end_a_1 = mfdUtil.add_end_module("1")

        mfdUtil.add_wire(start_a, "start", forms[0], "in")
        mfdUtil.add_wire(forms[-1], "positive", end_a_1, "end")
        mfdUtil.add_wire(forms[-1], "negative", end_a_1, "end")

        for x in xrange(len(forms) - 1):
            mfdUtil.add_wire(forms[x], "positive", forms[x + 1], "in")
            mfdUtil.add_wire(forms[x], "negative", forms[x + 1], "in")

        mfd = mfdUtil.save()
        self.assertStatusValid(mfd)
        self.assertEqual(len(mfd.sub_flows), 0)
        self.assertEqual(len(mfd.broken_sub_flows), 0)

    def testSaveStandAloneFlow(self):
        mfdUtil = MFDUtil("A")
        start_a = mfdUtil.add_start_module()
        msg_a_1 = mfdUtil.add_message_module("a_1")
        msg_a_2 = mfdUtil.add_message_module("a_2")
        end_a_1 = mfdUtil.add_end_module("a_1")

        mfd = mfdUtil.save()
        self.assertEqual(mfd.status & MessageFlowDesign.STATUS_BROKEN, MessageFlowDesign.STATUS_BROKEN)
        self.assertTrue(mfd.validation_error)

        mfdUtil.add_wire(start_a, "start", msg_a_1, "in")
        mfdUtil.add_wire(msg_a_1, "roger that", msg_a_2, "in")
        mfdUtil.add_wire(msg_a_2, "roger that", end_a_1, "end")

        mfd = mfdUtil.save()
        self.assert_(mfd.xml)
        self.assertStatusValid(mfd)
        self.assertEqual(len(mfd.sub_flows), 0)
        self.assertEqual(len(mfd.broken_sub_flows), 0)

    def testSaveAllModulesinFlow(self):
        mfdUtil = MFDUtil("A")
        print 'Adding MFD module: start'
        start_a = mfdUtil.add_start_module()
        print 'Adding MFD module: message'
        msg_a = mfdUtil.add_message_module("a", button_ids=["ab"])

        forms = list()
        for m in MFD_FORM_MODULES:
            print 'Adding MFD module: %s' % m
            forms.append(mfdUtil.add_form_message_module(m, str(MFD_FORM_MODULES.index(m))))

        print 'Adding MFD module: flush'
        flush_a = mfdUtil.add_flush_module("a")
        print 'Adding MFD module: email'
        email_a = mfdUtil.add_email_module("a")
        print 'Adding MFD module: end'
        end_a = mfdUtil.add_end_module("a")

        mfd = mfdUtil.save()
        self.assertEqual(mfd.status & MessageFlowDesign.STATUS_BROKEN, MessageFlowDesign.STATUS_BROKEN)
        self.assertTrue(mfd.validation_error)

        mfdUtil.add_wire(start_a, "start", msg_a, "in")
        mfdUtil.add_wire(msg_a, "roger that", forms[0], "in")
        mfdUtil.add_wire(msg_a, "ab", forms[0], "in")
        mfdUtil.add_wire(forms[-1], "positive", flush_a, "in")
        mfdUtil.add_wire(forms[-1], "negative", flush_a, "in")

        for x in xrange(len(forms) - 1):
            mfdUtil.add_wire(forms[x], "positive", forms[x + 1], "in")
            mfdUtil.add_wire(forms[x], "negative", forms[x + 1], "in")

        mfdUtil.add_wire(flush_a, "out", email_a, "in")
        mfdUtil.add_wire(email_a, "out", end_a, "end")

        mfd = mfdUtil.save()
        self.assert_(mfd.xml)
        self.assertStatusValid(mfd)
        self.assertEqual(len(mfd.sub_flows), 0)
        self.assertEqual(len(mfd.broken_sub_flows), 0)

    def testEmptyMessage(self):
        mfdUtil = self.createLinearHierarchy(["A"])[0][0]
        mfdUtil.messages[0]['config']['messageDef']['message'] = ''
        mfd = mfdUtil.save()
        self.assertStatusValid(mfd)

    def testWires(self):
        mfdUtil = MFDUtil("A")
        start_a = mfdUtil.add_start_module()
        msg_a_1 = mfdUtil.add_message_module("a_1")
        msg_a_2 = mfdUtil.add_message_module("a_2")
        end_a_1 = mfdUtil.add_end_module("a_1")
        self.assertStatusBroken(mfdUtil.save())  # Broken: no wires

        mfdUtil.add_wire(start_a, "start", msg_a_1, "in")
        self.assertStatusBroken(mfdUtil.save())

        mfdUtil.add_wire(msg_a_1, "roger that", msg_a_2, "in")
        self.assertStatusBroken(mfdUtil.save())

        mfdUtil.add_wire(end_a_1, "end", msg_a_2, "roger that")  # Reverse wiring
        self.assertStatusValid(mfdUtil.save())  # Everything wired

        # Remove wires & re-add them reversed
        for _ in xrange(len(mfdUtil.design["wires"])):
            wire = mfdUtil.design["wires"].pop()
            self.assertStatusBroken(mfdUtil.save())

            tgt = mfdUtil.design["modules"][wire["tgt"]["moduleId"]]
            src = mfdUtil.design["modules"][wire["src"]["moduleId"]]
            mfdUtil.add_wire(tgt, wire["tgt"]["terminal"], src, wire["src"]["terminal"])
            self.assertStatusValid(mfdUtil.save())

    def testEmptyEndId(self):
        mfdUtil, _ = self.createLinearHierarchy(["A"])[0]
        mfdUtil.ends[0]['value']['id'] = ''
        self.assertStatusBroken(mfdUtil.save())
        del mfdUtil.ends[0]['value']['id']
        self.assertStatusBroken(mfdUtil.save())

    def testEmptyMessageId(self):
        mfdUtil, _ = self.createLinearHierarchy(["A"])[0]
        mfdUtil.messages[0]['config']['messageDef']['id'] = ''
        self.assertStatusBroken(mfdUtil.save())
        del mfdUtil.messages[0]['config']['messageDef']['id']
        self.assertStatusBroken(mfdUtil.save())

    def testDuplicateIds(self):
        mfdUtil, _ = self.createLinearHierarchy(["A"])[0]
        msg2 = mfdUtil.add_message_module("A_2")
        msg2['config']['messageDef']['id'] = mfdUtil.messages[0]['config']['messageDef']['id']
        mfdUtil.design["wires"].pop(0)
        mfdUtil.add_wire(mfdUtil.start, "start", msg2, "in")
        mfdUtil.add_wire(msg2, "roger that", mfdUtil.messages[0], "in")
        mfd = mfdUtil.save()
        self.assertStatusBroken(mfd)

    def testSupers(self):
        # hierarchy: C > B > A
        hierarchy = self.createLinearHierarchy(["C", "B", "A"])
        mfd_c = hierarchy[0][1]
        mfd_b = hierarchy[1][1]
        mfd_a = hierarchy[2][1]

        supers_c = get_super_message_flows(mfd_c)
        self.assertEqual(len(supers_c), 0)

        supers_b = get_super_message_flows(mfd_b)
        self.assertEqual(len(supers_b), 1)
        self.assertEqual(supers_b[0].key(), mfd_c.key())

        supers_a = get_super_message_flows(mfd_a)
        self.assertEqual(len(supers_a), 2)
        self.assertTrue(mfd_b.key() in [f.key() for f in supers_a])
        self.assertTrue(mfd_c.key() in [f.key() for f in supers_a])

    def testAmpInSubFlow(self):
        self.createLinearHierarchy(["&1", "&2"])

    def testIncludeBrokenSubFlow(self):
        # Save broken A and use it in B
        #     A -> BROKEN
        #     B -> SUBFLOW_BROKEN
        mfdUtil_a = MFDUtil('A')
        start_a = mfdUtil_a.add_start_module()
        end_a = mfdUtil_a.add_end_module()
        msg_a = mfdUtil_a.add_message_module(mfdUtil_a.name, False, ['1', '2'])
        mfdUtil_a.add_wire(start_a, 'start', msg_a, 'in')
        mfdUtil_a.add_wire(msg_a, '1', end_a, 'end')
        mfd_a = mfdUtil_a.save()
        self.assertStatusBroken(mfd_a)  # btn_2 not wired

        mfdUtil_b = MFDUtil('B')
        start_b = mfdUtil_b.add_start_module()
        sub_b = mfdUtil_b.add_message_flow_module(mfd_a)
        mfdUtil_b.add_wire(start_b, 'start', sub_b, 'in')
        mfd_b = mfdUtil_b.save()
        self.assertEqual(mfd_b.status & MessageFlowDesign.STATUS_BROKEN, 0)
        self.assertStatusSubFlowBroken(mfd_b, [mfd_a])

        # In B: remove message_flow A module
        #     A, B -> BROKEN
        mfdUtil_b.design["wires"] = list()
        mfdUtil_b.remove_module(sub_b)
        mfd_b = mfdUtil_b.save()
        self.assertStatusBroken(mfd_b)
        self.assertStatusBroken(db.get(mfd_a.key()))

    def testBreakLinearFlow(self):
        # Create C > B > A
        hierarchy = self.createLinearHierarchy(["C", "B", "A"])
        _, mfd_c = hierarchy[0]
        mfdUtil_b, mfd_b = hierarchy[1]
        mfdUtil_a, _ = hierarchy[2]

        # Break A
        #     A -> BROKEN
        #     B, C -> SUBFLOW_BROKEN
        mfd_a = mfdUtil_a.auto_break()
        mfd_b = db.get(mfd_b.key())
        mfd_c = db.get(mfd_c.key())
        self.assertStatusBroken(mfd_a)
        self.assertStatusSubFlowBroken(mfd_b, [mfd_a])
        self.assertStatusSubFlowBroken(mfd_c, [mfd_b])

        # Correct A
        #     A, B, C -> VALID
        mfd_a = mfdUtil_a.auto_fix()
        mfd_b = db.get(mfd_b.key())
        mfd_c = db.get(mfd_c.key())
        self.assertStatusValid(mfd_a)
        self.assertStatusValid(mfd_b)
        self.assertStatusValid(mfd_c)

        # Break B
        #     A -> VALID
        #     B -> BROKEN
        #     C -> SUBFLOW_BROKEN
        mfd_b = mfdUtil_b.auto_break()
        mfd_a = db.get(mfd_a.key())
        mfd_c = db.get(mfd_c.key())
        self.assertStatusValid(mfd_a)
        self.assertStatusBroken(mfd_b)
        self.assertStatusSubFlowBroken(mfd_c, [mfd_b])

        # Break A
        #     A, B -> BROKEN
        #     C -> SUBFLOW_BROKEN
        mfd_a = mfdUtil_a.auto_break()
        mfd_b = db.get(mfd_b.key())
        mfd_c = db.get(mfd_c.key())
        self.assertStatusBroken(mfd_a)
        self.assertStatusBroken(mfd_b)
        self.assertStatusSubFlowBroken(mfd_c, [mfd_b])

        # Correct B
        #     A -> BROKEN
        #     B, C -> SUBFLOW_BROKEN
        mfd_b = mfdUtil_b.auto_fix()
        mfd_a = db.get(mfd_a.key())
        mfd_c = db.get(mfd_c.key())
        self.assertStatusBroken(mfd_a)
        self.assertStatusSubFlowBroken(mfd_b, [mfd_a])
        self.assertStatusSubFlowBroken(mfd_c, [mfd_b])

        # Correct A
        #     A, B, C -> VALID
        mfd_a = mfdUtil_a.auto_fix()
        mfd_b = db.get(mfd_b.key())
        mfd_c = db.get(mfd_c.key())
        self.assertStatusValid(mfd_a)
        self.assertStatusValid(mfd_b)
        self.assertStatusValid(mfd_c)

    def testFixBrokenFlowByCuttingOffBrokenSubFlow(self):
        # Create C > B > A
        hierarchy = self.createLinearHierarchy(["C", "B", "A"])
        _, mfd_c = hierarchy[0]
        mfdUtil_b, mfd_b = hierarchy[1]
        mfdUtil_a, _ = hierarchy[2]

        # Break A
        #     A -> BROKEN
        #     B, C -> SUBFLOW_BROKEN
        mfd_a = mfdUtil_a.auto_break()
        mfd_b = db.get(mfd_b.key())
        mfd_c = db.get(mfd_c.key())
        self.assertStatusBroken(mfd_a)
        self.assertStatusSubFlowBroken(mfd_b, [mfd_a])
        self.assertStatusSubFlowBroken(mfd_c, [mfd_b])

        # Cut B -/-> A
        # Now we have [ C > B ] and [ A ]
        #     A -> BROKEN
        #     B, C -> VALID
        mfdUtil_b.design['wires'].pop()
        mfdUtil_b.remove_module(mfdUtil_b.message_flows[0])
        mfdUtil_b.add_end_module()
        mfdUtil_b.add_wire(mfdUtil_b.messages[0], 'roger that', mfdUtil_b.ends[0], 'end')
        mfd_b = mfdUtil_b.save()
        mfd_a = db.get(mfd_a.key())
        mfd_c = db.get(mfd_c.key())
        self.assertStatusBroken(mfd_a)
        self.assertStatusValid(mfd_b)
        self.assertStatusValid(mfd_c)


    def testBreakComplexFlow(self):
        # Create X > Y > A < B < C
        #              > Z

        c_b_a = self.createLinearHierarchy(["C", "B", "A"])
        x_y_z = self.createLinearHierarchy(["X", "Y", "Z"])

        _, mfd_x = x_y_z[0]
        mfdUtil_y, _ = x_y_z[1]
        mfdUtil_z, mfd_z = x_y_z[2]
        _, mfd_c = c_b_a[0]
        _, mfd_b = c_b_a[1]
        mfdUtil_a, mfd_a = c_b_a[2]

        # Use A in Y
        mfdUtil_y.remove_module(mfdUtil_y.messages[0])
        sub_y_1 = mfdUtil_y.message_flows[0]
        sub_y_2 = mfdUtil_y.add_message_flow_module(mfd_a)
        msg_y_1 = mfdUtil_y.add_message_module("y_1", False, ["y_1", "y_2"])
        mfdUtil_y.design["wires"] = list()  # need to re-wire everything because module sequence has changed
        mfdUtil_y.add_wire(mfdUtil_y.start, "start", msg_y_1, "in")
        mfdUtil_y.add_wire(msg_y_1, "y_1", sub_y_1, "in")
        mfdUtil_y.add_wire(msg_y_1, "y_2", sub_y_2, "in")

        mfd_y = mfdUtil_y.save()
        self.assertStatusValid(mfd_y)

        # Break A
        #     A -> BROKEN
        #     B, C, X, Y -> SUBFLOW_BROKEN
        #     Z -> VALID
        mfd_a = mfdUtil_a.auto_break()
        mfd_b = db.get(mfd_b.key())
        mfd_c = db.get(mfd_c.key())
        mfd_x = db.get(mfd_x.key())
        mfd_y = db.get(mfd_y.key())
        mfd_z = db.get(mfd_z.key())
        self.assertStatusBroken(mfd_a)
        self.assertStatusSubFlowBroken(mfd_b, [mfd_a])
        self.assertStatusSubFlowBroken(mfd_c, [mfd_b])
        self.assertStatusSubFlowBroken(mfd_x, [mfd_y])
        self.assertStatusSubFlowBroken(mfd_y, [mfd_a])
        self.assertStatusValid(mfd_z)

        # Break Z
        #     A, Z -> BROKEN
        #     B, C, X, Y -> SUBFLOW_BROKEN
        mfd_z = mfdUtil_z.auto_break()
        mfd_a = db.get(mfd_a.key())
        mfd_b = db.get(mfd_b.key())
        mfd_c = db.get(mfd_c.key())
        mfd_x = db.get(mfd_x.key())
        mfd_y = db.get(mfd_y.key())
        self.assertStatusBroken(mfd_a)
        self.assertStatusSubFlowBroken(mfd_b, [mfd_a])
        self.assertStatusSubFlowBroken(mfd_c, [mfd_b])
        self.assertStatusSubFlowBroken(mfd_x, [mfd_y])
        self.assertStatusSubFlowBroken(mfd_y, [mfd_a, mfd_z])
        self.assertStatusBroken(mfd_z)

        # Correct A
        #     A, B, C -> VALID
        #     X, Y -> SUBFLOW_BROKEN
        #     Z -> BROKEN
        mfd_a = mfdUtil_a.auto_fix()
        mfd_b = db.get(mfd_b.key())
        mfd_c = db.get(mfd_c.key())
        mfd_x = db.get(mfd_x.key())
        mfd_y = db.get(mfd_y.key())
        mfd_z = db.get(mfd_z.key())
        self.assertStatusValid(mfd_a)
        self.assertStatusValid(mfd_b)
        self.assertStatusValid(mfd_c)
        self.assertStatusSubFlowBroken(mfd_x, [mfd_y])
        self.assertStatusSubFlowBroken(mfd_y, [mfd_z])
        self.assertStatusBroken(mfd_z)

        # Correct Z
        # A, B, C, X, Y, Z -> VALID
        mfd_z = mfdUtil_z.auto_fix()
        mfd_a = db.get(mfd_a.key())
        mfd_b = db.get(mfd_b.key())
        mfd_c = db.get(mfd_c.key())
        mfd_x = db.get(mfd_x.key())
        mfd_y = db.get(mfd_y.key())
        self.assertStatusValid(mfd_a)
        self.assertStatusValid(mfd_b)
        self.assertStatusValid(mfd_c)
        self.assertStatusValid(mfd_x)
        self.assertStatusValid(mfd_y)
        self.assertStatusValid(mfd_z)

    def _testTooDeep(self):
        max_lvl = 105
        hierarchy = self.createLinearHierarchy([ str(max_lvl - x) for x in xrange(max_lvl) ])
        # Deepest flow can not be saved
        mfdUtil_1, _ = hierarchy[max_lvl - 1]
        self.assertRaises(MessageFlowDesignLevelTooDeepException, mfdUtil_1.auto_break)

    def testCircularFlow_A_A(self):
        hierarchy = self.createLinearHierarchy(["A"])
        mfdUtil_a, mfd_a = hierarchy[0]

        # Create loop: [ A ] > A
        self.assertRaises(MessageFlowDesignLoopException, mfdUtil_a.link_message_flow, mfd_a)

    def testLinearCircularFlows_B_A_B(self):
        hierarchy = self.createLinearHierarchy(["B", "A"])
        _, mfd_b = hierarchy[0]
        mfdUtil_a, _ = hierarchy[1]

        # Create loop: [ B > A ] > B
        self.assertRaises(MessageFlowDesignLoopException, mfdUtil_a.link_message_flow, mfd_b)

    def testLinearCircularFlows_C_B_A_C(self):
        hierarchy = self.createLinearHierarchy(["C", "B", "A"])
        _, mfd_c = hierarchy[0]
        mfdUtil_a, _ = hierarchy[2]

        # Create loop: [ C > B > A ] > C
        self.assertRaises(MessageFlowDesignLoopException, mfdUtil_a.link_message_flow, mfd_c)

    def testDelete(self):
        # Create C > B > A
        # Create X > Y > Z, A

        c_b_a = self.createLinearHierarchy(["C", "B", "A"])
        x_y_z = self.createLinearHierarchy(["X", "Y", "Z"])

        mfdUtil_y, _ = x_y_z[1]
        _, mfd_a = c_b_a[2]

        # Use A in Y
        mfdUtil_y.remove_module(mfdUtil_y.messages[0])
        sub_y_1 = mfdUtil_y.message_flows[0]
        sub_y_2 = mfdUtil_y.add_message_flow_module(mfd_a)
        msg_y_1 = mfdUtil_y.add_message_module("y_1", False, ["y_1", "y_2"])
        mfdUtil_y.design["wires"] = list()  # need to re-wire everything because module sequence has changed
        mfdUtil_y.add_wire(mfdUtil_y.start, "start", msg_y_1, "in")
        mfdUtil_y.add_wire(msg_y_1, "y_1", sub_y_1, "in")
        mfdUtil_y.add_wire(msg_y_1, "y_2", sub_y_2, "in")

        mfd_y = mfdUtil_y.save()
        self.assertStatusValid(mfd_y)

        # Can not delete B, A, Y, Z
        self.assertRaises(BusinessException, self.delete, "B")
        self.assertRaises(BusinessException, self.delete, "A")
        self.assertRaises(BusinessException, self.delete, "Y")
        self.assertRaises(BusinessException, self.delete, "Z")
        self.delete("X")
        self.delete("C")

        # Can not delete A, Z
        self.assertRaises(BusinessException, self.delete, "A")
        self.assertRaises(BusinessException, self.delete, "Z")
        self.delete("Y")
        self.delete("B")

        self.delete("A")
        self.delete("Z")

    # OLD UNIT TESTS FOR CIRCULAR FLOWS

    def _testLinearCircularFlows_C_B_A_C(self):
        hierarchy = self.createLinearHierarchy(["C", "B", "A"])
        _, mfd_c = hierarchy[0]
        mfdUtil_a, _ = hierarchy[2]

        # Create circular flow: [ C > B > A ] > C
        mfdUtil_a.link_message_flow(mfd_c)
        self.validateLinearCircularFlows(hierarchy)

    def _testLinearCircularFlows_A_A(self):
        hierarchy = self.createLinearHierarchy(["A"])
        mfdUtil_a, mfd_a = hierarchy[0]

        # Create loop: A > A
        mfd_a = mfdUtil_a.link_message_flow(mfd_a)
        self.validateLinearCircularFlows(hierarchy)

    def _testLinearCircularFlows_A_B_A(self):
        hierarchy = self.createLinearHierarchy(["B", "A"])
        _, mfd_b = hierarchy[0]
        mfdUtil_a, _ = hierarchy[1]

        # Create loop: [ B > A ] > B
        mfdUtil_a.link_message_flow(mfd_b)
        self.validateLinearCircularFlows(hierarchy)

    def _testLinearCircularFlows_C_B_A_B(self):
        hierarchy = self.createLinearHierarchy(["C", "B", "A"])
        _, mfd_c = hierarchy[0]
        _, mfd_b = hierarchy[1]
        mfdUtil_a, _ = hierarchy[2]

        # Create loop: [ C > B > A ] > B
        mfdUtil_a.link_message_flow(mfd_b)
        self.validateLinearCircularFlows([hierarchy[1], hierarchy[2]])

        self.assertStatusValid(db.get(mfd_c.key()))

    def _test2CircularFlows_X_Y_X_F_A_B_A(self):
        hierarchy_a_b = self.createLinearHierarchy(["A", "B"])
        hierarchy_x_y = self.createLinearHierarchy(["X", "Y"])

        # Create loop: [ A > B ] > A
        _, mfd_a = hierarchy_a_b[0]
        mfdUtil_b, _ = hierarchy_a_b[1]
        mfd_b = mfdUtil_b.link_message_flow(mfd_a)

        # Create loop: [ X > Y ] > X
        _, mfd_x = hierarchy_x_y[0]
        mfdUtil_y, _ = hierarchy_x_y[1]
        mfd_y = mfdUtil_y.link_message_flow(mfd_x)

        # Create flow: X < Y < X < F > A > B > A
        mfdUtil_f = MFDUtil("F")
        start_f = mfdUtil_f.add_start_module()
        msg_f_1 = mfdUtil_f.add_message_module("F", True, ["A", "X"])
        sub_f_a = mfdUtil_f.add_message_flow_module(mfd_a)
        sub_f_x = mfdUtil_f.add_message_flow_module(mfd_x)
        end_f_1 = mfdUtil_f.add_end_module()
        mfdUtil_f.add_wire(start_f, "start", msg_f_1, "in")
        mfdUtil_f.add_wire(msg_f_1, "A", sub_f_a, "in")
        mfdUtil_f.add_wire(msg_f_1, "X", sub_f_x, "in")
        mfdUtil_f.add_wire(msg_f_1, "roger that", end_f_1, "end")
        mfd_f = mfdUtil_f.save()

        self.assertStatusValid(mfd_f)

        end_f_id = create_json_id(mfd_f, "end_", "F")
        msg_f_id = create_json_id(mfd_f, "message_", "F")
        msg_a_id = create_json_id(mfd_a, "message_", "A")
        msg_b_id = create_json_id(mfd_b, "message_", "B")
        msg_x_id = create_json_id(mfd_x, "message_", "X")
        msg_y_id = create_json_id(mfd_y, "message_", "Y")

        xml_doc = parseString(mfd_f.xml)
        for child in xml_doc.documentElement.childNodes:
            if child.nodeType == xml_doc.ELEMENT_NODE:
                child_id = child.getAttribute('id')
                child_dismiss_reference = child.getAttribute('dismissReference')
                if child_id == msg_f_id:
                    self.assertEqual(child_dismiss_reference, end_f_id)
                    for answer in child.childNodes:
                        if answer.nodeType == xml_doc.ELEMENT_NODE:
                            answer_reference = answer.getAttribute('reference')
                            answer_caption = answer.getAttribute('caption')
                            if answer_caption == 'A':
                                self.assertEqual(answer_reference, msg_a_id)
                            elif answer_caption == 'X':
                                self.assertEqual(answer_reference, msg_x_id)
                elif child_id == msg_a_id:
                    self.assertEqual(child_dismiss_reference, msg_b_id)
                elif child_id == msg_b_id:
                    self.assertEqual(child_dismiss_reference, msg_a_id)
                elif child_id == msg_x_id:
                    self.assertEqual(child_dismiss_reference, msg_y_id)
                elif child_id == msg_y_id:
                    self.assertEqual(child_dismiss_reference, msg_x_id)

    def _testIncludeMySelfMultipleTimes(self):
        # A: Start -> Msg -> End
        #                 -> A
        #                 -> A
        #                 -> A
        mfdUtil_a = MFDUtil('A')
        mfdUtil_a.add_start_module()
        mfdUtil_a.add_message_module(mfdUtil_a.name, True, ['1', '2', '3'])
        mfdUtil_a.add_end_module()
        mfdUtil_a.add_wire(mfdUtil_a.start, 'start', mfdUtil_a.messages[0], 'in')
        mfdUtil_a.add_wire(mfdUtil_a.messages[0], 'roger that', mfdUtil_a.ends[0], 'end')
        mfd_a = mfdUtil_a.save()
        self.assertStatusBroken(mfd_a)  # buttons 1, 2, 3 are not wired

        for i in xrange(3):
            mfdUtil_a.add_message_flow_module(mfd_a)
            mfdUtil_a.add_wire(mfdUtil_a.messages[0], str(i + 1), mfdUtil_a.message_flows[i], 'end')

        mfd_a = mfdUtil_a.save()
        self.assertStatusValid(mfd_a)

        xml_a_doc = parseString(mfd_a.xml)
        element_child_nodes = [ n for n in xml_a_doc.documentElement.childNodes if n.nodeType == n.ELEMENT_NODE ]
        self.assertEqual(len(element_child_nodes), 2)
        self.assertEqual(len([e for e in element_child_nodes if e.nodeName == 'end']), 1)  # 1 end element
        msgs = [e for e in element_child_nodes if e.nodeName == 'message']
        self.assertEqual(len(msgs), 1)  # 1 message element
        msg = msgs[0]
        self.assertEqual(msg.nodeName, 'message')
        self.assertEqual(msg.getAttribute('dismissReference'), create_json_id(mfd_a, "end_", mfd_a.name))
        answer_nodes = [ n for n in msg.childNodes if n.nodeType == n.ELEMENT_NODE and n.nodeName == 'answer']
        self.assertEqual(len(answer_nodes), 3)
        ref = create_json_id(mfd_a, "message_", mfd_a.name)
        for answer_node in answer_nodes:
            answer_ref = answer_node.getAttribute('reference')
            self.assertEqual(answer_ref, ref)

    def _testSubFlowWithOnlyStartAndSubFlow(self):
        # Create A: Start -> Msg -> End
        #                        -> B
        # Create B: Start -> A
        mfdUtil_a = MFDUtil('A')
        mfdUtil_a.add_start_module()
        mfdUtil_a.add_message_module(mfdUtil_a.name, False, ['1', '2'])
        mfdUtil_a.add_end_module()
        mfdUtil_a.add_wire(mfdUtil_a.start, 'start', mfdUtil_a.messages[0], 'in')
        mfdUtil_a.add_wire(mfdUtil_a.messages[0], '1', mfdUtil_a.ends[0], 'end')
        mfdUtil_a.add_wire(mfdUtil_a.messages[0], '2', mfdUtil_a.ends[0], 'end')
        mfd_a = mfdUtil_a.save()

        self.assertStatusValid(mfd_a)

        mfdUtil_b = MFDUtil('B')
        mfdUtil_b.add_start_module()
        mfdUtil_b.add_message_flow_module(mfd_a)
        mfdUtil_b.add_wire(mfdUtil_b.start, 'start', mfdUtil_b.message_flows[0], 'in')
        mfd_b = mfdUtil_b.save()

        self.assertStatusValid(mfd_b)

        mfdUtil_a.design['wires'].pop()  # disconnect wire 'btn_2 -> end_a'
        mfdUtil_a.add_message_flow_module(mfd_b)
        mfdUtil_a.add_wire(mfdUtil_a.messages[0], '2', mfdUtil_a.message_flows[0], 'in')
        mfd_a = mfdUtil_a.save()
        mfd_b = db.get(mfd_b.key())

        self.assertStatusValid(mfd_a)
        self.assertStatusValid(mfd_b)

        # Check References:
        #     btn_1 -> end_a
        #     btn_2 -> msg_a

        xml_a_doc = parseString(mfd_a.xml)
        # There should be 1 end node and 1 message node
        element_child_nodes = [ n for n in xml_a_doc.documentElement.childNodes if n.nodeType == n.ELEMENT_NODE ]
        self.assertEqual(len(element_child_nodes), 2)
        self.assertEqual(len([e for e in element_child_nodes if e.nodeName == 'end']), 1)

        msgs = [e for e in element_child_nodes if e.nodeName == 'message']
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]

        self.assertFalse(msg.attributes.get('dismissReference'))
        answer_nodes = [ n for n in msg.childNodes if n.nodeType == n.ELEMENT_NODE and n.nodeName == 'answer']
        self.assertEqual(len(answer_nodes), 2)
        for answer_node in answer_nodes:
            answer_id = answer_node.getAttribute('id')
            answer_ref = answer_node.getAttribute('reference')
            if answer_id == 'button_1':
                self.assertEqual(answer_ref, create_json_id(mfd_a, "end_", mfd_a.name))
            elif answer_id == 'button_2':
                self.assertEqual(answer_ref, create_json_id(mfd_a, "message_", mfd_a.name))

    def _testBreakCircularFlow_C_B_A_C(self):
        hierarchy = self.createLinearHierarchy(["C", "B", "A"])
        _, mfd_c = hierarchy[0]
        _, mfd_b = hierarchy[1]
        mfdUtil_a, _ = hierarchy[2]

        # Create loop: [ C > B > A ] > C
        mfdUtil_a.link_message_flow(mfd_c)
        self.validateLinearCircularFlows(hierarchy)

        mfd_a = mfdUtil_a.auto_break()
        mfd_b = db.get(mfd_b.key())
        mfd_c = db.get(mfd_c.key())

        self.assertStatusBroken(mfd_a)
        self.assertStatusSubFlowBroken(mfd_b)
        self.assertStatusSubFlowBroken(mfd_c)
        self.assertEqual([mfd_a.key()], mfd_c.broken_sub_flows)
        self.assertEqual([mfd_a.key()], mfd_b.broken_sub_flows)
        self.assertFalse(mfd_a.broken_sub_flows)

    def _testEternalEmptyLoop(self):
        mfdUtil_a = MFDUtil("A")
        mfdUtil_a.add_start_module()
        mfd_a = mfdUtil_a.save()

        self.assertStatusBroken(mfd_a)

        mfdUtil_b = MFDUtil("B")
        mfdUtil_b.add_start_module()
        mfdUtil_b.add_message_flow_module(mfd_a)
        mfdUtil_b.add_wire(mfdUtil_b.start, "start", mfdUtil_b.message_flows[0], "in")
        mfd_b = mfdUtil_b.save()

        self.assertStatusSubFlowBroken(mfd_b)

        mfdUtil_a.add_message_flow_module(mfd_b)
        mfdUtil_a.add_wire(mfdUtil_a.start, "start", mfdUtil_a.message_flows[0], "in")
        mfd_a = mfdUtil_a.save()
        mfd_b = db.get(mfd_b.key())

        self.assertStatusBroken(mfd_a)
        self.assertStatusSubFlowBroken(mfd_b)

    def _testLoopWithoutEnd(self):
        # A: start -> end
        mfdUtil_a = MFDUtil("A")
        mfdUtil_a.add_start_module()
        mfdUtil_a.add_end_module()
        mfdUtil_a.add_wire(mfdUtil_a.start, 'start', mfdUtil_a.ends[0], 'end')
        mfd_a = mfdUtil_a.save()
        self.assertStatusValid(mfd_a)

        # B: start -> A
        mfdUtil_b = MFDUtil("B")
        mfdUtil_b.add_start_module()
        mfdUtil_b.add_message_flow_module(mfd_a)
        mfdUtil_b.add_wire(mfdUtil_b.start, 'start', mfdUtil_b.message_flows[0], 'in')
        mfd_b = mfdUtil_b.save()
        self.assertStatusValid(mfd_b)

        # A: start -> B
        mfdUtil_a.remove_module(mfdUtil_a.ends[0])
        mfdUtil_a.design["wires"] = list()
        mfdUtil_a.add_message_flow_module(mfd_b)
        mfdUtil_a.add_wire(mfdUtil_a.start, 'start', mfdUtil_a.message_flows[0], 'in')
        mfd_a = mfdUtil_a.save()
        self.assertStatusBroken(mfd_a)
        self.assertStatusSubFlowBroken(db.get(mfd_b.key()))

        # B: start -> end
        #     A, B -> VALID

        mfdUtil_b.remove_module(mfdUtil_b.message_flows[0])
        mfdUtil_b.design["wires"] = list()
        mfdUtil_b.add_end_module()
        mfdUtil_b.add_wire(mfdUtil_b.start, 'start', mfdUtil_b.ends[0], 'end')
        mfd_b = mfdUtil_b.save()
        self.assertStatusValid(mfd_b)
        self.assertStatusValid(db.get(mfd_a.key()))

    def testXmlCreation(self):
        m1 = users.User(u'i1@foo.com')
        create_user_profile(m1, m1.email(), "fr")
        m2 = users.User(u'i2@foo.com')
        create_user_profile(m2, m2.email(), "ar")

        _, mfd = self.createLinearHierarchy(["A", "B", "C"])[0]

        message_flow_design_to_xml(mfd.user, mfd, None, None)


        # Translate all MFLOW strings
        translate_service_strings(mfd.user)

        # Clear request cache
        self.clear_request_cache()

        _translate_all_message_flows(mfd.user)

        mfd = db.get(mfd.key())
        print mfd.xml

        members = [m1, m2]
        force_language = None
        mfr = MessageFlowRunRecord(creationtimestamp=now())

        svc_identity_user = create_service_identity_user(mfd.user, ServiceIdentity.DEFAULT)
        xml_doc = _create_message_flow_run_xml_doc(svc_identity_user, mfd, mfr, members, force_language)
        assert xml_doc

        # Test language of m1 is fr and m2 did fall back to en
        # Test that 3 definitions found: fr, en and nl
        member_run_count = definition_count = 0
        m1_found = m2_found = False
        fr_found = en_found = nl_found = False
        start_references = list()
        for childNode in xml_doc.documentElement.childNodes:
            if childNode.localName == 'definition':
                definition_count += 1
                l = childNode.getAttribute('language')
                if l == "en":
                    assert not en_found
                    en_found = True
                elif l == "fr":
                    assert not fr_found
                    fr_found = True
                elif l == "nl":
                    assert not nl_found
                    nl_found = True
                else:
                    assert False, "Unexpected language: %s" % l
                # references must be unique between languages
                start_reference = childNode.getAttribute('startReference')
                assert start_reference not in start_references
                start_references.append(start_reference)
            if childNode.localName == 'memberRun':
                member_run_count += 1
                if childNode.getAttribute('email') == m1.email():
                    m1_found = True
                    assert childNode.getAttribute('language') == "fr"
                if childNode.getAttribute('email') == m2.email():
                    m2_found = True
                    assert childNode.getAttribute('language') == "en"

        assert definition_count == 3
        assert en_found, "definition for en not found"
        assert fr_found, "definition for fr not found"
        assert nl_found, "definition for nl not found"

        assert member_run_count == 2
        assert m1_found, "memberRun for %s not found" % m1
        assert m2_found, "memberRun for %s not found" % m2

        force_language = "es"
        self.assertRaises(BusinessException, _create_message_flow_run_xml_doc, svc_identity_user, mfd, mfr, members,
                          force_language)

    def testJsFlowDefCreation(self):
        _, mfd = self.createLinearHierarchy(["A", "B", "C"])[0]

        message_flow_design_to_xml(mfd.user, mfd, None, None)

        # Translate all MFLOW strings
        translate_service_strings(mfd.user)

        # Clear request cache
        self.clear_request_cache()

        _translate_all_message_flows(mfd.user)

        mfd = db.get(mfd.key())

        for lang in get_service_profile(mfd.user).supportedLanguages:
            flow = mfd.js_flow_definitions.get_by_language(lang)
            self.assertTrue(flow, "js_flow_def with language '%s' not found" % lang)
