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

from rogerthat.bizz.service import poke_service_callback_response_receiver
from rogerthat.to.messaging import ButtonTO
from rogerthat.to.messaging.forms import SingleSliderTO, FormTO
from mcfw.properties import long_property, unicode_property, bool_property, float_property, unicode_list_property, \
    typed_property, get_hash
from mcfw.rpc import arguments, returns, parse_parameter, serialize_complex_value
import json
import mc_unittest
import logging

class Test(mc_unittest.TestCase):

    def testTypedProperty(self):
        widget = SingleSliderTO()
        widget.max = 24
        widget.min = 1
        widget.step = 1
        widget.unit = u"EUR"
        widget.value = 12

        form = FormTO()
        form.type = u"single_slider"
        form.positive_button = u"Submit"
        form.negative_button = u"Cancel"
        form.widget = widget
        assert(form)

    def testInvalidTypedProperty(self):
        self.assertRaises(ValueError, setattr, FormTO(), "widget", ButtonTO())

    def testTypeNotSet(self):
        self.assertRaises(ValueError, setattr, FormTO(), "widget", SingleSliderTO())

    def testPolySingleType(self):

        class MemberTO(object):
            flags = long_property('1')
            member = unicode_property('2')

        @returns(bool)
        @arguments(sender=unicode, member=(unicode, MemberTO))
        def polySingleArgument(sender, member):
            assert((sender == "eef" and isinstance(member, MemberTO)) or (sender == "geert" and isinstance(member, unicode)))
            return True

        m = MemberTO()
        m.flags = 20
        m.member = u"geert"

        polySingleArgument(u"eef", m)

    def testPolyArrayType(self):

        class MemberTO(object):
            flags = long_property('1')
            member = unicode_property('2')

        class MemberkesTO(object):
            flags = long_property('1')
            member = unicode_property('2')

        @returns(bool)
        @arguments(sender=unicode, members=[(unicode, MemberTO)])
        def polyArrayArgument(sender, members):
            assert(isinstance(members[0], MemberTO))
            assert(isinstance(members[1], unicode))
            return True

        m = MemberTO()
        m.flags = 20
        m.member = u"geert"

        polyArrayArgument(u"eef", [m, u"carl"])

        m2 = MemberkesTO()
        m2.flags = 30
        m2.member = u"mieke"

        self.assertRaises(ValueError, lambda: polyArrayArgument(u"eef", [m2, u"carl"]))


    def testSerializeWithMISSING(self):
        RESULT_STR = """{"id":"ef0da970-eaec-11e2-9eeb-af96f4efab6f","result":{"type":"form","value":{"attachments":[],"message":"Beste Test agent 11, \\n\\nselecteer de dag waarvan u de schedule wil bekijken:","flags":0,"alert_flags":0,"branding":"9D104A3966ADA1E11B2508606944E6EFC2E1DF49DC9A041A23CF8C4114CF5F5C","tag":"{\\"_id\\":\\"select_date_get_schedule\\"}","form":{"positive_button":"Verder","positive_confirmation":null,"positive_button_ui_flags":1,"negative_button":"Annuleren","negative_confirmation":null,"negative_button_ui_flags":0,"type":"date_select","widget":{"date":0,"min_date":1373587200,"max_date":1405123200,"minute_interval":30,"mode":"date","unit":null}}}},"error":null}"""
        resp = json.loads(RESULT_STR)

        f = poke_service_callback_response_receiver
        type_ = f.meta[u"kwarg_types"][u"result"]
        result = parse_parameter(u"result", type_, resp["result"])

        d = serialize_complex_value(result, type_, False, skip_missing=True)
        json.dumps(d)  # this crashes if MISSING is in the serialized result

        self.assertRaises(Exception, json.dumps, serialize_complex_value(result, type_, False, skip_missing=False))

    def testGetHash(self):

        class InnerDummy(object):
            g1 = unicode_property('1')

        class Dummy(object):
            f1 = unicode_property('1')
            f2 = bool_property('2')
            f3 = float_property('3')
            f4 = long_property('4')
            f5 = unicode_list_property('5')
            f6 = typed_property('6', InnerDummy)
            f7 = typed_property('7', InnerDummy, True)

        d = Dummy()
        d.f1 = u'moehaha'
        d.f2 = True
        d.f3 = 3.14159265358979323846264338327950288419716939937510
        d.f4 = 5
        d.f5 = [u"test", u"ikkel"]
        id_ = InnerDummy()
        id_.g1 = None
        d.f6 = id_
        d.f7 = [id_]

        h1 = get_hash(d)
        logging.info("h1 = %s", h1)

        d1 = Dummy()
        d1.f1 = u'moehaha'
        d1.f2 = True
        d1.f3 = 3.14159265358979323846264338327950288419716939937510
        d1.f4 = 5
        d1.f5 = [u"test", u"ikkel"]
        d1.f6 = id_
        d1.f7 = [id_]

        h2 = get_hash(d1)

        self.assertEqual(h1, h2)

        d1.f7 = [id_, None]

        h3 = get_hash(d1)

        self.assertNotEqual(h1, h3)

        d1.f5 = [u"test", u"tikkel"]

        h4 = get_hash(d1)

        self.assertNotEqual(h3, h4)


    def testReturnsWithListWithTuple(self):

        @returns([(int, long)])
        @arguments(response_type=type)
        def test(response_type):
            return [1, 2, 3L]

        test([(int, long)])
        test([int])
        test([list])
        test(int)
        test(str)
        self.assertRaises(ValueError, lambda: test([int, int]))
        self.assertRaises(ValueError, lambda: test([1, 2, 3]))
        self.assertRaises(ValueError, lambda: test("boom"))
