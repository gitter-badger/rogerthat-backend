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

import StringIO
import base64
import hashlib
import json
import sys
import uuid
import zlib

from google.appengine.ext import db

import mc_unittest
from mcfw.consts import MISSING
from mcfw.properties import get_members
from mcfw.rpc import arguments, returns
from rogerthat.bizz.friends import makeFriends, ORIGIN_USER_INVITE
from rogerthat.bizz.messaging import _generate_push_json, _ellipsize_for_json, store_chunk, _add_attachments, \
    _validate_attachments, InvalidAttachmentException
from rogerthat.bizz.profile import create_user_profile, create_service_profile
from rogerthat.bizz.service import create_service_identity
from rogerthat.consts import MC_DASHBOARD
from rogerthat.dal.messaging import get_transfer_chunks, get_transfer_result
from rogerthat.dal.profile import get_service_profile
from rogerthat.models import APIKey, Message, ServiceIdentity
from rogerthat.models.properties.forms import Form
from rogerthat.models.properties.messaging import MemberStatus, Buttons, MemberStatuses, _serialize_attachments, \
    _deserialize_attachments, Attachments
from rogerthat.restapi.web import load_web
from rogerthat.rpc import users
from rogerthat.rpc.http import process
from rogerthat.rpc.models import Mobile
from rogerthat.rpc.rpc import api_callbacks
from rogerthat.rpc.service import process_service_api_call, register_service_api_calls, service_api
from rogerthat.service.api import messaging
from rogerthat.settings import get_server_settings
from rogerthat.to import WIDGET_MAPPING
from rogerthat.to.messaging import UserMemberTO, AttachmentTO
from rogerthat.to.messaging.forms import FormTO, TextLineTO, SingleSelectTO, MultiSelectTO, SingleSliderTO, \
    RangeSliderTO, TextBlockTO, AutoCompleteTO, UnicodeWidgetResultTO, UnicodeListWidgetResultTO, LongWidgetResultTO, \
    LongListWidgetResultTO, FloatWidgetResultTO, FloatListWidgetResultTO, DateSelectTO, PhotoUploadTO
from rogerthat.to.service import ServiceIdentityDetailsTO
from rogerthat.utils import now
from rogerthat.utils.service import create_service_identity_user
from rogerthat_tests import register_tst_mobile, set_current_user, set_current_mobile

JSON_WIDGET_MAPPING = {
    TextLineTO.TYPE: ['"value": null, "place_holder": "Name", "max_chars": 100',
                      '"value": null, "max_chars": 100',
                      '"place_holder": "Name", "max_chars": 100',
                      '"max_chars": 100'],
    TextBlockTO.TYPE: ['"value": null, "place_holder": "Name", "max_chars": 100',
                      '"value": null, "max_chars": 100',
                      '"place_holder": "Name", "max_chars": 100',
                      '"max_chars": 100'],
    AutoCompleteTO.TYPE: ['"value": null, "place_holder": "Name", "max_chars": 100, "suggestions": ["value1", "value2", "value3", "value4"]'],
    SingleSelectTO.TYPE: ['"value": null, "choices": [{"label": "label1", "value": "value1"}, {"label": "label2", "value": "value2"}, {"label": "label3", "value": "value3"}, {"label": "label4", "value": "value4"}]'],
    MultiSelectTO.TYPE: ['"values": [], "choices": [{"label": "label1", "value": "value1"}, {"label": "label2", "value": "value2"}, {"label": "label3", "value": "value3"}, {"label": "label4", "value": "value4"}]'],
    DateSelectTO.TYPE: ['"mode": "time"',
                        '"mode": "time", "date": %s, "min_date": 0, "max_date": %s, "unit": "Time: <value/>"' % (22 * 3600, 24 * 3600),
                        '"mode": "date"',
                        '"mode": "date", "date": %s, "min_date": 0, "max_date": %s, "unit": "Time: <value/>"' % (20 * 86400, 5000 * 86400),
                        '"mode": "date_time"',
                        '"mode": "date_time", "date": 1334060880, "min_date": 0, "max_date": 1334064900, "unit": "Time: <value/>", "minute_interval":2'
                        ],
    SingleSliderTO.TYPE: ['"max": 100, "min": 0, "step": 2, "unit": "$<value/>", "value": 10, "precision": 2',
                          '"max": 100, "min": 0, "step": 2, "unit": "$<value/>", "value": 10',
                          '"max": 100, "min": 0, "step": 2, "unit": "$<value/>"',
                          '"max": 100, "min": 0, "unit": "$<value/>"',
                          '"max": 100, "min": 0',
                          '"max": 3.50, "min": 1.50, "step": 0.10, "unit": "$<value/>"'],
    RangeSliderTO.TYPE: ['"max": 100, "min": 0, "step": 2, "unit": "$<low_value/> - $<high_value/>", "low_value": 10, "high_value": 90, "precision": 2',
                         '"max": 100, "min": 0, "step": 2, "unit": "$<low_value/> - $<high_value/>", "low_value": 10, "high_value": 90',
                         '"max": 100, "min": 0, "step": 2, "unit": "$<low_value/> - $<high_value/>"',
                         '"max": 100, "min": 0, "unit": "$<low_value/> - $<high_value/>"'],
    PhotoUploadTO.TYPE: ['"ratio": "200x200", "quality": "best", "gallery": true, "camera": true',
                        '"ratio" : "10x20", "quality": "user", "gallery" : true, "camera" : true',
                        '"ratio" : "200x200", "quality": "user", "camera" : true',
                        '"ratio" : "200x200", "quality": "100000", "gallery" : true',
                        '"quality": "best", "gallery" : true, "camera" : true',
                        '"quality": "user", "gallery" : true, "camera" : true'],
}

JSON_RESULT_MAPPING = {
    UnicodeWidgetResultTO.TYPE: '{"value": "value"}',
    UnicodeListWidgetResultTO.TYPE: '{"values": ["value1", "value2"]}',
    LongWidgetResultTO.TYPE: '{"value": 10}',
    LongListWidgetResultTO.TYPE: '{"values": [20, 80]}',
    FloatWidgetResultTO.TYPE: '{"value": 10.2}',
    FloatListWidgetResultTO.TYPE: '{"values": [20.5, 80.3]}',
}

FORM_RESULT_REQUEST_STR = """
{
    "av": 1,
    "c": [{
            "f": "%(f)s",
            "ci": "%(ci)s",
            "av": 1,
            "a": {
                "request": {
                    "parent_message_key": %(pm_key)s,
                    "message_key": "%(fm_key)s",
                    "timestamp": %(t)s,
                    "button_id": "%(button_id)s",
                    "result": %(result)s
                }
            },
            "t": %(t)s
        }
    ],
    "r": [],
    "a": []
}"""

@service_api("test.unit_test", cache_result=False)
@returns(unicode)
@arguments()
def test_service_api_call():
    return unicode(uuid.uuid4())


class Test(mc_unittest.TestCase):

    def testSendLongMessageWithoutSpaces(self):
        from rogerthat.bizz.messaging import sendMessage
        server_settings = get_server_settings()
        # Set current mobile to iPhone
        users.get_current_mobile().type = Mobile.TYPE_IPHONE_HTTP_APNS_KICK
        # Send message
        message = u"qwertyuiopasdfghjklzxcvbnm1234567890qwertyuiopasdfghjklzxcvbnm1234567890qwertyuiopasdfghjklzxcvbnm1234567890qwertyuiopasdfghjklzxcvbnm1234567890qwertyuiopasdfghjklzxcvbnm1234567890"
        m = sendMessage(MC_DASHBOARD, [UserMemberTO(users.get_current_user())], 1, 0, None, message, [], None, None, None, is_mfr=False)
        sendMessage(MC_DASHBOARD, [UserMemberTO(users.get_current_user())], 1, 0, m.mkey, message, [], None, None, None, is_mfr=False)

    def testSendMixedMemberTypeMessage(self):
        self.set_datastore_hr_probability(1)

        # setup environment
        john = users.User(u'john_doe@foo.com')
        create_user_profile(john, u"John Doe")
        john_mobile = register_tst_mobile(john.email())

        jane = users.User(u'jane_doe@foo.com')
        create_user_profile(jane, u"Jane Doe")
        jane_mobile = register_tst_mobile(jane.email())

        service = users.User(u'monitoring@rogerth.at')
        _, service_identity = create_service_profile(service, u"Monitoring service")
        assert service_identity.is_default
        assert service_identity.user == create_service_identity_user(service_identity.service_user, ServiceIdentity.DEFAULT)

        sProfile = get_service_profile(service_identity.service_user)
        sProfile.callBackJid = u"test@example.com"
        sProfile.sik = u"sik"
        sProfile.enabled = True
        sProfile.put()

        api_key = APIKey()
        api_key.name = u"api_key"
        api_key.timestamp = now()
        api_key.user = service
        api_key.put()

        # make them friends
        makeFriends(john, service, service, None, origin=ORIGIN_USER_INVITE)
        makeFriends(jane, service, service, None, origin=ORIGIN_USER_INVITE)

        register_service_api_calls(messaging)

        call_body = """{
    "params": {
        "sender_answer": null,
        "parent_key": null,
        "branding": null,
        "tag": "37AAF801-CE21-4AC5-9F43-E8E403E1EB5F",
        "answers": [
            {
                "action": null,
                "caption": "fine",
                "ui_flags": 0,
                "type": "button",
                "id": "fine"
            },
            {
                "action": null,
                "caption": "could do better",
                "ui_flags": 0,
                "type": "button",
                "id": "notfine"
            }
        ],
        "dismiss_button_ui_flags": 0,
        "flags": 17,
        "alert_flags": 1,
        "members": [
            "%s",
            {
                "member": "%s",
                "alert_flags": 72
            }
        ],
        "message": "Hey how are you"
    },
    "id": "%s",
    "method": "messaging.send"
}""" % (john.email(), jane.email(), unicode(uuid.uuid4()))
        set_current_user(service)
        json_result_str, method, _, _, error_code, _, _ = process_service_api_call(call_body, api_key)

        self.assert_(error_code == 0)
        self.assert_(method == "messaging.send")

        json_result = json.loads(json_result_str)
        self.assert_(not json_result['error'])
        message_key = json_result.get('result')
        self.assertTrue(message_key)

        set_current_mobile(jane_mobile)
        call_jane = self._receive_message()
        set_current_mobile(john_mobile)
        call_john = self._receive_message()

        self.assertTrue(call_jane and call_john)

        self.assertEquals(call_jane["a"]["request"]["message"]["alert_flags"], 72)
        self.assertEquals(call_john["a"]["request"]["message"]["alert_flags"], 1)


    def _getTextLineFormTO(self):
        formTO = FormTO()
        formTO.negative_button = u"Negative"
        formTO.positive_button = u"Positive"
        formTO.negative_button_ui_flags = 0
        formTO.positive_button_ui_flags = 0
        formTO.negative_confirmation = None
        formTO.positive_confirmation = None
        formTO.javascript_validation = None
        formTO.type = TextLineTO.TYPE
        formTO.widget = TextLineTO()
        formTO.widget.max_chars = 100
        formTO.widget.place_holder = None
        formTO.widget.value = None
        return formTO

    def testSendForm(self):
        from rogerthat.bizz.messaging import sendForm, sendMessage
        formTO = self._getTextLineFormTO()

        member = users.User(u'member1@rogerth.at')
        create_user_profile(member, u"Member1")

        set_current_user(member)

        svc_user = users.User(u'service1@rogerth.at')
        _, svc_identity = create_service_profile(svc_user, u"Service1")

        makeFriends(member, svc_identity.user, svc_identity.user, None, origin=ORIGIN_USER_INVITE)

        msg = u"bla"
        print "Sending message 1"
        m1 = sendMessage(svc_identity.user, [UserMemberTO(member)], 1, 0, None, msg, [], None, None, None, is_mfr=False)
        print "Sending form message 1"
        sendForm(svc_identity.user, m1.mkey, member, msg, formTO, 1, None, None, is_mfr=False)
        print "Sending form message 2"
        sendForm(svc_identity.user, m1.mkey, member, msg, formTO, 1, None, None, is_mfr=False)

    def _receive_message(self):
        comm_request_str = '{"av":1, "c":[], "r":[], "a":[]}'

        comm_response_str = process(comm_request_str)
        comm_response = json.loads(comm_response_str)

        for call in comm_response["c"]:
            if call["f"] == "com.mobicage.capi.messaging.newMessage":
                received_request_str = '{"av":1, "c":[], "r":[{"r":{"received_timestamp":%(t)s},"ci":"%(ci)s","av":1,"s":"success","t":%(t)s}],"a":[]}'
                process(received_request_str % call)
                return call
        return

    def _receive_form_message(self, form_type):
        print "Receiving '%s' form" % form_type
        comm_request_str = '{"av":1, "c":[], "r":[], "a":[]}'

        comm_response_str = process(comm_request_str)
        comm_response = json.loads(comm_response_str)

        ci = None
        for call in comm_response["c"]:
            if call["f"] == WIDGET_MAPPING[form_type].new_form_call.meta['alias']:
                form_json = call['a']['request']['form_message']['form']
                self.assert_(form_json['widget'])
                self.assert_(form_json['positive_confirmation'])
                self.assert_(form_json['negative_confirmation'])
                self.assertEqual(form_json['javascript_validation'], u"")

                # Test that all attributes of the TO are also present in the received JSON object
                for member_tuple in get_members(WIDGET_MAPPING[form_type].to_type):
                    for attr in member_tuple:
                        self.assertTrue(attr[0] in form_json['widget'])



                ci = call['ci']
                received_request_str = u'{"av":1, "c":[], "r":[{"r":{"received_timestamp":%(t)s},"ci":"%(ci)s","av":1,"s":"success","t":%(t)s}],"a":[]}'
                received_response_str = process(received_request_str % call)
                received_reponse = json.loads(received_response_str)
                self.assertTrue(ci in received_reponse['a'])
                break
        self.assert_(ci)

    def _answer_form(self, fm_key, pm_key, form_type, positive_button_pressed):
        print "%s '%s' form" % (positive_button_pressed and "Submitting" or "Canceling", form_type)
        ci = unicode(uuid.uuid4())
        widget_descr = WIDGET_MAPPING[form_type]
        req = FORM_RESULT_REQUEST_STR % {"f": "com.mobicage.api.messaging.%s" % widget_descr.submit_form_call.__name__, \
                                         "ci":ci, "t":now(), "fm_key":fm_key, "pm_key":pm_key and ('"%s"' % pm_key) or "null", \
                                         "result":positive_button_pressed and JSON_RESULT_MAPPING[widget_descr.result_type] or "null", \
                                         "button_id":positive_button_pressed and Form.POSITIVE or Form.NEGATIVE}
        answer_response_str = process(req)
        answer_response = json.loads(answer_response_str)
        resp = None
        for r in answer_response["r"]:
            if ci == r["ci"]:
                resp = r
                break

        self.assert_(resp)
        if "e" in resp:
            print resp
        self.assertFalse("e" in resp)
        self.assertFalse(resp["s"] == "fail")

    def _sendForm(self, form_type, pkey, member, api_key, i):
        print "Sending '%s' form %s" % (form_type, i + 1)
        json_request = """
{
    "id": "%(id)s",
    "method": "messaging.send_form",
    "params": {
        "alert_flags": 2,
        "parent_key": %(pkey)s,
        "branding": null,
        "member": "%(member)s",
        "tag": "37AAF801-CE21-4AC5-9F43-E8E403E1EB5F",
        "flags": 31,
        "dismiss_button_ui_flags": 0,
        "message": "%(type)s",
        "form": {
            "type": "%(type)s",
            "positive_button": "Submit",
            "negative_button": "Abort",
            "positive_button_ui_flags": 0,
            "negative_button_ui_flags": 0,
            "positive_confirmation": "Are you sure you want to proceed?",
            "negative_confirmation": "Are you sure you wish to abort?",
            "javascript_validation" : "",
            "widget": {
                %(widget)s
            }
        }
    }
}"""

        call_body = json_request % {"member":member.email(), "pkey":('"%s"' % pkey) if pkey else "null",
                                    "type":form_type, "widget":JSON_WIDGET_MAPPING[form_type][i],
                                    "id":unicode(uuid.uuid4())}
        json_result_str, method, _, _, error_code, error_message, _ = process_service_api_call(call_body, api_key)

        if  error_code:
            print error_message
        self.assertEqual(0, error_code)
        self.assertEqual("messaging.send_form", method)

        json_result = json.loads(json_result_str)
        self.assert_(not json_result['error'])
        fm_key = json_result.get('result')
        self.assert_(fm_key)
        return fm_key

    def testRoundTripSendForm(self):

        self.set_datastore_hr_probability(1)

        # setup environment
        member = users.User(u'member1@rogerth.at')
        create_user_profile(member, u"Member1")
        mMobile = register_tst_mobile(member.email())

        service = users.User(u'service1@rogerth.at')
        create_service_profile(service, u"Service1")
        sProfile = get_service_profile(service)
        sProfile.callBackJid = u"test@example.com"
        sProfile.sik = u"sik"
        sProfile.enabled = True
        sProfile.put()
        assert sProfile.enabled

        service_profile1 = get_service_profile(service, cached=False)
        assert service_profile1.enabled

        service_profile2 = get_service_profile(service)
        assert service_profile2.enabled

        api_key = APIKey()
        api_key.name = u"api_key"
        api_key.timestamp = now()
        api_key.user = service
        api_key.put()

        # make them friends
        makeFriends(member, service, service, None, origin=ORIGIN_USER_INVITE)

        register_service_api_calls(messaging)

        # send & submit & cancel all types of forms
        parent_key = None
        for positive_button_pressed in [True, False]:
            for form_type in JSON_WIDGET_MAPPING.keys():
                for i in xrange(len(JSON_WIDGET_MAPPING[form_type])):
                    # service sends form message
                    set_current_user(service)
                    fm_key = self._sendForm(form_type, parent_key, member, api_key, i)

                    # client receives & answers form message
                    set_current_mobile(mMobile)
                    self._receive_form_message(form_type)
                    self._answer_form(fm_key, parent_key, form_type, positive_button_pressed)

                    # look for form_update in api_callbacks
                    found = False
                    for _, ac, _, _, _ in api_callbacks.items:
                        req = json.loads(ac)
                        req = json.loads(req["c"])
                        if req['method'] == u'messaging.form_update' and req['params']['message_key'] == fm_key:
                            found = True
                            form_result = req['params']['form_result']
                            if positive_button_pressed:
                                self.assertEqual(form_result['type'], WIDGET_MAPPING[form_type].result_type)

                                widget_result = form_result['result']
                                self.assertTrue('value' in widget_result or 'values' in widget_result)
                            else:
                                self.assertFalse(form_result)
                            break

                    self.assertTrue(found)

                    if parent_key is None:
                        parent_key = fm_key

        print "Load messages for web"
        set_current_user(member)
        load_web()

    def testPreventDoubleApiCallExecution(self):
        self.set_datastore_hr_probability(1)

        # setup environment
        member = users.User(u'member2@rogerth.at')
        create_user_profile(member, u"Member2")

        service = users.User(u'service2@rogerth.at')
        create_service_profile(service, u"Service2")
        sProfile = get_service_profile(service)
        sProfile.callBackJid = u"test2@example.com"
        sProfile.sik = u"sik"
        sProfile.enabled = True
        sProfile.put()

        api_key = APIKey()
        api_key.name = u"api_key"
        api_key.timestamp = now()
        api_key.user = service
        api_key.put()

        # make them friends
        makeFriends(member, service, service, None, origin=ORIGIN_USER_INVITE)

        register_service_api_calls(messaging)
        register_service_api_calls(sys.modules[__name__])

        # send message
        set_current_user(service)

        fm_key = self._sendForm(TextLineTO.TYPE, None, member, api_key, 0)

        lock_json_request = """
{
"id": "%(id)s",
"method": "messaging.seal",
"params": {
    "parent_message_key": null,
    "message_key": "%(key)s",
    "dirty_behavior": 1
}
}
"""

        call_body_1 = lock_json_request % ({"id": str(uuid.uuid4()), "key": fm_key})
        call_body_2 = lock_json_request % ({"id": str(uuid.uuid4()), "key": fm_key})

        lock_result_str_1, _, _, _, error_code1, _, _ = process_service_api_call(call_body_1, api_key)
        lock_result_str_2, _, _, _, _, _, from_cache2 = process_service_api_call(call_body_1, api_key)
        lock_result_str_3, _, _, _, error_code3, _, _ = process_service_api_call(call_body_2, api_key)
        lock_result_str_4, _, _, _, _, _, from_cache4 = process_service_api_call(call_body_1, api_key)

        print lock_result_str_1
        print lock_result_str_2
        print lock_result_str_3
        print lock_result_str_4

        self.assertEqual(error_code1, 0)
        self.assertEqual(from_cache2, True)
        self.assertNotEqual(error_code3, 0)
        self.assertEqual(from_cache4, True)

        self.assertEqual(lock_result_str_1, lock_result_str_2)
        self.assertEqual(lock_result_str_1, lock_result_str_4)
        self.assertNotEqual(lock_result_str_1, lock_result_str_3)

        test_json_request = """
{
"id": "%(id)s",
"method": "test.unit_test",
"params": { }
}
"""
        call_body = test_json_request % ({"id": str(uuid.uuid4())})

        test_result_str_1, _, _, _, _, _, _ = process_service_api_call(call_body, api_key)
        test_result_str_2, _, _, _, _, _, _ = process_service_api_call(call_body, api_key)

        print test_result_str_1
        print test_result_str_2

        self.assertNotEquals(test_result_str_1, test_result_str_2)

    def _populate(self, message):
        message.alert_flags = Message.ALERT_FLAG_VIBRATE
        message.childMessages = list()
        message.branding = None
        message.buttons = Buttons()
        message.creationTimestamp = now()
        message.dismiss_button_ui_flags = 0
        message.flags = 31
        message.generation = 1
        message.originalFlags = message.flags
        message.senderMobile = None
        message.tag = None
        message.timeout = 0
        message.timestamp = message.creationTimestamp
        message.memberStatusses = MemberStatuses()
        for i in xrange(len(message.members)):
            ms = MemberStatus()
            ms.status = 0
            ms.received_timestamp = 0
            ms.acked_timestamp = 0
            ms.index = i
            ms.dismissed = False
            ms.button_index = -1
            ms.custom_reply = None
            ms.form_result = None
            ms.ack_device = None
            message.memberStatusses.add(ms)
        message.attachments = Attachments()

    def testGeneratePushJSON(self):
        self.set_datastore_hr_probability(1)

        # setup environment
        puts = list()

        member1 = users.User(u'bart.ios.43.simulator@example.com')
        create_user_profile(member1, u"Bart - iOS 4.3 Simulator")

        member2 = users.User(u'bart@example.com')
        create_user_profile(member2, u"Bart test")

        key1 = unicode(uuid.uuid4())
        key2 = unicode(uuid.uuid4())

        parent_message = Message(key_name=key1)
        parent_message.sender = member1
        parent_message.message = """Lkdjsg;lkdfjg;ldskfjg;sdlkfgj
Dsfglkjdsg;flkjdsf
Dslfgkjdf;lgkjd;flgkj
Dslgfkjdf;lgkjd;lfghdlfkgskdjfglfkdj lkfjdlkjfdlk jdflkgj ldkjfdlgkj dlfkjgldfk jldfkjg lkjdfglkjdf lkjgfdlkgjldfkjgdjfgkdjfngmdfngn lkdfjglkdjfgdlkfjg dflkjgldfkjgdlfkjgdlfkjgl kjdfglkjfdlgkj;dflkjgdfglkj fd;l"""
        parent_message.members = [member2, member1]
        self._populate(parent_message)
        puts.append(parent_message)

        message = Message(key_name=key2, parent=parent_message)
        message.sender = member2
        message.message = "Ttt"
        message.members = [member1, member2]
        self._populate(message)
        puts.append(message)

        db.put(puts)

        _generate_push_json(message, parent_message, member1, False)

    def testGeneratePushJSON2(self):
        self.set_datastore_hr_probability(1)
        svc_user = users.User(u'cars@example.com')
        create_service_profile(svc_user, 'Garage MK Motors', is_trial=False)

        to = ServiceIdentityDetailsTO()
        to.app_data = None
        to.identifier = u'2098'
        to.name = u'GARAGE HAYEZ'
        to.created = 0
        to.qualified_identifier = to.description = to.description_branding = to.menu_branding = to.phone_number = \
            to.phone_call_popup = to.search_config = None
        to.admin_emails = list()
        to.recommend_enabled = False
        to.description_use_default = to.description_branding_use_default = to.menu_branding_use_default = \
            to.phone_number_use_default = to.phone_call_popup_use_default = to.search_use_default = \
            to.email_statistics_use_default = to.app_ids_use_default = False
        to.app_data = None
        to.email_statistics = False
        to.beacons = list()
        to.app_ids = list()
        to.beacon_auto_invite = True
        to.content_branding_hash = None
        create_service_identity(svc_user, to)

        sender = users.User(u'cars@example.com/2098')
        member = users.User(u'bart@example.com')

        key1 = u'f7631cf2834973705501be84b1e076f790c4ae6498fa6bc2b4ce308c741b0281'

        message = Message(key_name=key1)
        self._populate(message)
        message.sender = sender
        message.message = u"""HGSI signifie Hyundai Global Satisfaction Index et donne une indication de la satisfaction clientèle pour chaque Réparateur Agréé.

Nous tenons donc à en savoir plus au sujet de votre contact avec Hyundai et ses employés.

Nous apprécierions sincèrement votre participation à notre enquête internationale sur la satisfaction clientèle en fonction du service fourni par nos Réparateurs Agréés.

Cordialement,

Hyundai BeLux
"""
        message.members = [sender, member]
        message.alert_flags = 0

        result = base64.decodestring(_generate_push_json(message, None, member, True))
        result = json.dumps(json.loads(result), separators=None)
        print result
        assert result == '{"aps": {"content-available": 1, "sound": "n.aiff", "badge": 1, "alert": {"loc-args": ["GARAGE HAYEZ", "HGSI signifie Hyundai Global Satisfaction Index et donne une..."], "loc-key": "NM"}}, "n": "f7631cf2834973705501be84b1e076f790c4ae6498fa6bc2b4ce308c741b0281"}'

    def testMemberIndexStatuses(self):
        msg = Message(key_name=unicode(uuid.uuid4()))
        m1 = users.User('joske')
        m2 = users.User('jefke')

        msg.addStatusIndex(m1, (Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX, Message.MEMBER_INDEX_STATUS_NOT_RECEIVED))
        self.assert_(Message.MEMBER_INDEX_STATUS_NOT_RECEIVED in msg.member_status_index)

        msg.addStatusIndex(m2, (Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX, Message.MEMBER_INDEX_STATUS_NOT_RECEIVED, Message.MEMBER_INDEX_STATUS_NOT_DELETED))
        self.assert_(Message.MEMBER_INDEX_STATUS_NOT_RECEIVED in msg.member_status_index)

        msg.removeStatusIndex(m1, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX)
        self.assert_(Message.MEMBER_INDEX_STATUS_NOT_RECEIVED in msg.member_status_index)

        msg.removeStatusIndex(m1, Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX)
        self.assert_(Message.MEMBER_INDEX_STATUS_NOT_RECEIVED in msg.member_status_index)

        msg.removeStatusIndex(m2, (Message.MEMBER_INDEX_STATUS_NOT_DELETED, Message.MEMBER_INDEX_STATUS_NOT_RECEIVED))
        self.assert_(Message.MEMBER_INDEX_STATUS_NOT_RECEIVED in msg.member_status_index)

        msg.removeStatusIndex(m1, Message.MEMBER_INDEX_STATUS_NOT_RECEIVED)
        self.assertFalse(Message.MEMBER_INDEX_STATUS_NOT_RECEIVED in msg.member_status_index)

        msg.addStatusIndex(m2, (Message.MEMBER_INDEX_STATUS_SHOW_IN_INBOX, Message.MEMBER_INDEX_STATUS_NOT_RECEIVED, Message.MEMBER_INDEX_STATUS_NOT_DELETED))
        self.assert_(Message.MEMBER_INDEX_STATUS_NOT_RECEIVED in msg.member_status_index)

    def testEllipsize(self):
        s = u'Please measure your blood pressure'
        assert _ellipsize_for_json(s, 3, True) == '...'
        assert _ellipsize_for_json(s, 3, False) == '...'

    def testStoreChunk(self):
        chunk_content1 = "bla"
        b64_zipped_content1 = base64.b64encode(zlib.compress(chunk_content1))
        hash_ = hashlib.sha256(chunk_content1)

        chunk_content2 = "bla2"
        b64_zipped_content2 = base64.b64encode(zlib.compress(chunk_content2))
        hash_2 = hashlib.sha256(chunk_content2)

        hash_ = hash_.hexdigest().upper()
        service_identity_user = users.User("s1@foo.com/+default+")

        store_chunk(users.get_current_user(), service_identity_user, "parent_message_key", "message_key", 2, 1,
                    b64_zipped_content1, hash_, None)


        hash_2 = hash_2.hexdigest().upper()
        store_chunk(users.get_current_user(), service_identity_user, "parent_message_key", "message_key", 2, 2,
                    b64_zipped_content2, hash_2, None)

        photo_upload_result = get_transfer_result("parent_message_key", "message_key")
        assert photo_upload_result.total_chunks == 2

        chunks = get_transfer_chunks(photo_upload_result.key())
        len_chunks = 0
        for photo_upload_chunk in chunks:
            len_chunks = len_chunks + 1
        assert photo_upload_result.total_chunks == len_chunks

        chunk_id_check = 1
        for photo_upload_chunk in chunks:
            assert photo_upload_chunk.number == chunk_id_check
            chunk_id_check += 1

    def testValidAttachments(self):
        msg = Message(key_name=unicode(uuid.uuid4()))

        a1 = AttachmentTO()
        a1.content_type = AttachmentTO.CONTENT_TYPE_IMG_JPG
        a1.download_url = u"http://www.rogerthat.net/wp-content/uploads/2012/12/home-bg.jpg"
        a1.name = u"blabla"
        a1.size = 4096

        a2 = AttachmentTO()
        a2.content_type = AttachmentTO.CONTENT_TYPE_PDF
        a2.download_url = u"http://www.rogerthat.net/wp-content/uploads/data/rogerthat_brochure.pdf"
        a2.name = u"blabla"
        a2.size = 8192

        a3 = AttachmentTO()
        a3.content_type = AttachmentTO.CONTENT_TYPE_VIDEO_MP4
        a3.download_url = u"http://techslides.com/demos/sample-videos/small.mp4"
        a3.name = u"blabla3"
        a3.size = 383631

        # check properties
        attachmentTOs = _validate_attachments([a1, a2, a3])
        _add_attachments(attachmentTOs, msg)

        # check serialization
        stream = StringIO.StringIO()
        _serialize_attachments(stream, msg.attachments)
        stream.seek(0)
        deserialized = _deserialize_attachments(stream)
        for a in deserialized.values():
            self.assertEqual(a.content_type, attachmentTOs[a.index].content_type)
            self.assertEqual(a.download_url, attachmentTOs[a.index].download_url)


    def testInvalidAttachments(self):
        # validate missing attachments
        self.assertEqual([], _validate_attachments(None))
        self.assertEqual([], _validate_attachments(MISSING))

        a1 = AttachmentTO()
        a1.download_url = u"http://www.rogerthat.net/wp-content/uploads/data/rogerthat_brochure.pdf"
        a1.name = u"blabla"
        a1.size = 4096

        # validate content_type
        a1.content_type = None
        self.assertRaises(InvalidAttachmentException, _validate_attachments, [a1])

        a1.content_type = AttachmentTO.CONTENT_TYPE_IMG_JPG
        _validate_attachments([a1])

        a2 = AttachmentTO()
        a2.content_type = AttachmentTO.CONTENT_TYPE_IMG_PNG
        a2.name = u"blabla"
        a2.size = 4096

        # validate download_url
        a2.download_url = None
        self.assertRaises(InvalidAttachmentException, _validate_attachments, [a2])

        a2.download_url = u"file:///tmp/test"
        self.assertRaises(InvalidAttachmentException, _validate_attachments, [a2])

        a2.download_url = u"http://www.rogerthat.net/wp-content/uploads/data/rogerthat_brochure.pdf"
        _validate_attachments([a2])
