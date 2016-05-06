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

from StringIO import StringIO
import base64
import json
import os
import sys
from rogerthat_tests import set_current_user
import time

from rogerthat.bizz.friends import makeFriends
from rogerthat.bizz.i18n import get_all_translations, get_editable_translation_set
from rogerthat.bizz.profile import create_service_profile, create_user_profile
from rogerthat.bizz.service import ReservedMenuItemException, InvalidMenuItemCoordinatesException, \
    CanNotDeleteBroadcastTypesException, InvalidNameException, ServiceAlreadyExistsException, CreateServiceDeniedException, \
    FriendNotFoundException, InvalidJsonStringException
from rogerthat.bizz.service.mfr import MessageFlowDesignInUseException, InvalidMessageFlowXmlException, \
    MessageFlowDesignValidationException
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.service import get_default_service_identity
from rogerthat.models import ServiceIdentity, ServiceTranslation
from rogerthat.rpc import users
from rogerthat.service.api import qr
from rogerthat.service.api.messaging import start_flow
from rogerthat.service.api.system import put_identity, get_identity, get_translations, put_translations, delete_flow, \
    put_menu_item, delete_menu_item, store_branding, put_broadcast_types, put_reserved_menu_item_label, list_broadcast_types, \
    put_flow, put_service, put_user_data, del_user_data, get_user_data
from rogerthat.to.friends import FriendTO
from rogerthat.to.messaging.flow import MessageFlowDesignTO
from rogerthat.to.service import ServiceIdentityDetailsTO
from rogerthat.to.system import TranslationSetTO, TranslationValueTO
from rogerthat.utils.transactions import run_in_xg_transaction
import mc_unittest
from mcfw.rpc import parse_complex_value, serialize_complex_value
from rogerthat_tests.mobicage.bizz import test_mfd


VALID_XML1 = u'<messageFlowDefinition name="Flow 1" language="en" startReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogIm1lc3NhZ2VfMSJ9">\n        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0=" waitForFollowUpMessage="false"/>\n        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogIm1lc3NhZ2VfMSJ9" alertIntervalType="NONE" alertType="SILENT" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImZsdXNoXzEifQ==" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0=">\n            <content>Beste klant,\n\nBenader ons met al uw vragen inzake ons aanbod. Wij proberen u zo spoedig mogelijk te antwoorden.</content>\n            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">\n                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextBlockWidget" maxChars="50"/>\n            </form>\n        </formMessage>\n        <resultsFlush id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImZsdXNoXzEifQ==" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0="/>\n    </messageFlowDefinition>'
VALID_XML2 = '<messageFlowDefinitionSet xmlns="https://rogerth.at/api/1/MessageFlow.xsd">\n    <definition name="Flow 2" language="en" startReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogIm1lc3NhZ2VfMSJ9">\n        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0=" waitForFollowUpMessage="false"/>\n        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogIm1lc3NhZ2VfMSJ9" alertIntervalType="NONE" alertType="SILENT" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImZsdXNoXzEifQ==" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0=">\n            <content>Beste klant,\n\nBenader ons met al uw vragen inzake ons aanbod. Wij proberen u zo spoedig mogelijk te antwoorden.</content>\n            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">\n                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextBlockWidget" maxChars="50"/>\n            </form>\n        </formMessage>\n        <resultsFlush id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImZsdXNoXzEifQ==" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0="/>\n    </definition>\n</messageFlowDefinitionSet>\n'

class Test(mc_unittest.TestCase):

    def _put_identity_json(self, json_dict):
        to = parse_complex_value(ServiceIdentityDetailsTO, json_dict, False)
        return put_identity(to)


    def _test_create_identity(self, service_user):
        json_dict = dict(description_branding_use_default=True, description_use_default=True, identifier=u'1',
                    menu_branding_use_default=True, name=u'test', phone_call_popup_use_default=True, phone_number=u'123',
                    qualified_identifier=u'si_test1@foo.com', recommend_enabled=False, search_use_default=True, beacon_auto_invite=True)

        self._put_identity_json(json_dict)

        si_details = get_identity(u'1')
        self.assertEqual(json_dict['description_branding_use_default'], si_details.description_branding_use_default)
        self.assertIsNone(si_details.description_branding)
        self.assertEqual(json_dict['description_use_default'], si_details.description_use_default)
        self.assertTrue(si_details.description)
        self.assertEqual(json_dict['identifier'], si_details.identifier)
        self.assertEqual(json_dict['menu_branding_use_default'], si_details.menu_branding_use_default)
        self.assertIsNone(si_details.menu_branding)
        self.assertEqual(json_dict['name'], si_details.name)
        self.assertEqual(json_dict['phone_call_popup_use_default'], si_details.phone_call_popup_use_default)
        self.assertIsNone(si_details.phone_call_popup)
        self.assertEqual(json_dict['phone_number'], si_details.phone_number)
        self.assertFalse(si_details.phone_number_use_default)
        self.assertEqual(json_dict['qualified_identifier'], si_details.qualified_identifier)
        self.assertEqual(json_dict['recommend_enabled'], si_details.recommend_enabled)
        self.assertEqual(json_dict['search_use_default'], si_details.search_use_default)
        self.assertTrue(si_details.search_config)
        self.assertFalse(si_details.search_config.enabled)
        self.assertFalse(si_details.search_config.keywords)

        return si_details

    def _test_update_identity(self):
        old_si_details = get_identity(u'1')

        # update the name of default identity (no identifier in json_dict)
        json_dict = dict(name=u'default_identity_name')
        self._put_identity_json(json_dict)
        self.assertEqual(json_dict['name'], get_identity(ServiceIdentity.DEFAULT).name)

        # update the name of identity 1
        json_dict = dict(name=u'identity_1_name', identifier=u'1')
        self._put_identity_json(json_dict)
        new_si_details = get_identity(u'1')
        self._put_identity_json(json_dict)
        self.assertEqual(json_dict['name'], new_si_details.name)
        self.assertEqual(old_si_details.qualified_identifier, new_si_details.qualified_identifier)
        self.assertFalse(new_si_details.search_config.enabled)

        # enable the search_config of identity 1
        json_dict = dict(identifier=u'1', search_config=dict(enabled=True, keywords=u'test'))
        self._put_identity_json(json_dict)
        new_si_details = get_identity(u'1')
        self.assertTrue(new_si_details.search_config.enabled)
        self.assertTrue(json_dict['search_config']['enabled'] is True)
        self.assertEquals(0, len(new_si_details.search_config.locations))

        # test app_data
        app_data = dict(test1='1', test2='2')
        json_dict = dict(app_data=json.dumps(app_data).decode('utf8'))
        self._put_identity_json(json_dict)
        new_si_details = get_identity()
        self.assertDictEqual(json.loads(new_si_details.app_data), app_data)

        return new_si_details

    def _prepare_svc(self, email=None):
        service_user = users.User(email or u'svc_test%s@foo.com' % time.time())
        create_service_profile(service_user, u'Test Name')
        set_current_user(service_user)
        return service_user

    def test_put_service_identity(self):
        service_user = self._prepare_svc()

        self._test_create_identity(service_user)
        self._test_update_identity()

    def test_put_translations(self):
        service_user = self._prepare_svc()
        service_profile = get_service_profile(service_user)

        service_profile.supportedLanguages.extend([u'nl'])
        service_profile.put()

        si = get_default_service_identity(service_user)
        si.description = u"Test Description"
        si.put()

        put_flow(VALID_XML1)
        put_menu_item("3d", "label", "tag", [1, 1, 0], "999999")

        translation_set = get_translations()
        assert translation_set.export_id
        assert service_user.email() == translation_set.email

        print
        print 'TranslationSet in datastore:'
        print get_all_translations(get_editable_translation_set(service_user))
        print
        print 'TranslationSet transfer object:'
        print serialize_complex_value(translation_set, TranslationSetTO, False)

        # Name and description are the only properties that are filled in
        # Let's translate them in Dutch

        NL_NAME = u'Test Naam'
        NL_DESCR = u'Test Beschrijving'

        name_found = description_found = False
        for translation in translation_set.translations:
            if translation.type == ServiceTranslation.IDENTITY_TEXT:
                if translation.key == si.name:
                    name_found = True
                    assert not translation.values
                    nl_value = TranslationValueTO()
                    nl_value.language = u'nl'
                    nl_value.value = NL_NAME
                    translation.values = [ nl_value ]
                if translation.key == si.description:
                    description_found = True
                    assert not translation.values
                    nl_value = TranslationValueTO()
                    nl_value.language = u'nl'
                    nl_value.value = NL_DESCR
                    translation.values = [ nl_value ]

        print
        print 'Updated TranslationSet transfer object:'
        print serialize_complex_value(translation_set, TranslationSetTO, False)

        assert name_found
        assert description_found

        put_translations(translation_set)

        print
        print 'Updated TranslationSet in datastore:'
        print get_all_translations(get_editable_translation_set(service_user))

        # Test that nl name and description are in FriendTO
        human_user = users.User(u'a@foo.com')
        create_user_profile(human_user, human_user.email(), language=u'nl')
        makeFriends(human_user, service_user, None, None, None)

        friendTO = FriendTO.fromDBFriendMap(get_friends_map(human_user), service_user, includeServiceDetails=True,
                                            targetUser=human_user)
        assert friendTO.name == NL_NAME
        assert friendTO.description == NL_DESCR

        # Test protection against overwriting
        time.sleep(1)  # making sure export_id is unique, since it's the current epoch in seconds
        get_translations()  # will save new export_id
        self.assertRaises(Exception, put_translations, translation_set)  # translation_set still has old export_id

        translations = get_translations()
        translations.email = u"another_email@foo.com"
        self.assertRaises(Exception, put_translations, translation_set)

    def _create_flow(self, flow_or_list):
        utils = test_mfd.Test('setUp')
        if isinstance(flow_or_list, (list, tuple)):
            return [ MessageFlowDesignTO.fromMessageFlowDesign(o[1]) for o in utils.createLinearHierarchy(flow_or_list) ]
        else:
            return MessageFlowDesignTO.fromMessageFlowDesign(utils.createLinearHierarchy(flow_or_list)[0][1])

    def test_menu_items(self):
        if sys.platform == "win32":
            return

        self._prepare_svc()

        icon_name = u"chat emoticon"
        tag = u"tag"
        label = u"label"

        self.assertRaises(ReservedMenuItemException, put_menu_item, icon_name, label, tag, [0, 0, 0])
        self.assertRaises(InvalidMenuItemCoordinatesException, put_menu_item, icon_name, label, tag, [4, 0, 0])

        self.assertRaises(ReservedMenuItemException, delete_menu_item, [0, 0, 0])
        self.assertRaises(ReservedMenuItemException, delete_menu_item, [1, 0, 0])
        self.assertRaises(ReservedMenuItemException, delete_menu_item, [2, 0, 0])
        self.assertRaises(ReservedMenuItemException, delete_menu_item, [3, 0, 0])
        self.assertRaises(InvalidMenuItemCoordinatesException, delete_menu_item, [4, 0, 0])

        mfd_a = self._create_flow('a')
        put_menu_item(icon_name, label, tag, [1, 1, 1], static_flow=mfd_a.identifier)
        put_menu_item(icon_name, label, tag, [1, 1, 1], static_flow=mfd_a.name)

        with open(os.path.join(os.path.dirname(__file__), "..", "bizz", "nuntiuz.zip")) as f:
            stream = StringIO()
            stream.write(f.read())
        stream.seek(0)
        branding = store_branding(u'description', base64.b64encode(stream.read()))

        put_broadcast_types(['News', 'Coupons'])

        put_menu_item(icon_name, label, tag, [0, 1, 0], is_broadcast_settings=True, broadcast_branding=branding.id)
        put_menu_item(icon_name, label, tag, [0, 1, 0], screen_branding=branding.id)
        put_menu_item(icon_name, label, tag, [0, 1, 0])

        self.assertTrue(delete_menu_item([1, 1, 1]))
        self.assertTrue(delete_menu_item([0, 1, 0]))
        self.assertFalse(delete_menu_item([2, 1, 1]))

        put_reserved_menu_item_label(0, 'About 2')
        put_reserved_menu_item_label(0, 'Messages 2')
        put_reserved_menu_item_label(0, 'Call 2')
        put_reserved_menu_item_label(0, 'Recommend 2')
        self.assertRaises(InvalidMenuItemCoordinatesException, put_reserved_menu_item_label, 5, 'Invalid')

    def test_delete_flow(self):
        self._prepare_svc()

        mfd_a, mfd_b, mfd_c = self._create_flow(['a', 'b', 'c'])

        self.assertRaises(MessageFlowDesignInUseException, delete_flow, mfd_c.identifier)
        self.assertRaises(MessageFlowDesignInUseException, delete_flow, mfd_c.name)

        self.assertRaises(MessageFlowDesignInUseException, delete_flow, mfd_b.identifier)
        self.assertRaises(MessageFlowDesignInUseException, delete_flow, mfd_b.name)

        self.assertTrue(delete_flow(mfd_a.name))
        self.assertTrue(delete_flow(mfd_b.identifier))
        self.assertTrue(delete_flow(mfd_c.name))
        self.assertFalse(delete_flow('I dont exist'))

        mfd_d = self._create_flow('d')
        qr.create('description d', 'tag d', None, None, mfd_d.name)
        self.assertRaises(MessageFlowDesignInUseException, delete_flow, mfd_d.name)

        mfd_e = self._create_flow('e')
        qr.create('description e', 'tag e', None, None, mfd_e.identifier)
        self.assertRaises(MessageFlowDesignInUseException, delete_flow, mfd_e.identifier)

    def test_put_flow(self):
        service_user = self._prepare_svc()

        # Test rubbish xml
        self.assertRaises(InvalidMessageFlowXmlException, put_flow, '<div></div>')
        self.assertRaises(InvalidMessageFlowXmlException, put_flow, 'invalid')

        # Test valid xml

        mfd1 = put_flow(VALID_XML1)
        self.assertEqual('Flow 1', mfd1.name)
        self.assertTrue(mfd1.identifier)

        mfd2 = put_flow(VALID_XML2)
        self.assertEqual('Flow 2', mfd2.name)
        self.assertTrue(mfd2.identifier)

        # Test breaking flows
        invalid_xml1 = '<messageFlowDefinition name="Stel een vraag" language="en" startReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogIm1lc3NhZ2VfMSJ9">\n        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0=" waitForFollowUpMessage="false"/>\n        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogIm1lc3NhZ2VfMSJ9" alertIntervalType="NONE" alertType="SILENT" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImZsdXNoXzEifQ==" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0=">\n            <content>Beste klant,\n\nBenader ons met al uw vragen inzake ons aanbod. Wij proberen u zo spoedig mogelijk te antwoorden.</content>\n            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">\n                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextBlockWidget" maxChars="50"/>\n            </form>\n        </formMessage>\n</messageFlowDefinition>'
        self.assertRaises(MessageFlowDesignValidationException, put_flow, invalid_xml1)  # referencing unknown element

        invalid_xml2 = '<messageFlowDefinition name="Stel een vraag" language="en" startReference="base64:XXXeyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogIm1lc3NhZ2VfMSJ9">\n        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0=" waitForFollowUpMessage="false"/>\n        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogIm1lc3NhZ2VfMSJ9" alertIntervalType="NONE" alertType="SILENT" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImZsdXNoXzEifQ==" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0=">\n            <content>Beste klant,\n\nBenader ons met al uw vragen inzake ons aanbod. Wij proberen u zo spoedig mogelijk te antwoorden.</content>\n            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">\n                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextBlockWidget" maxChars="50"/>\n            </form>\n        </formMessage>\n        <resultsFlush id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImZsdXNoXzEifQ==" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0="/>\n    </messageFlowDefinition>'
        self.assertRaises(MessageFlowDesignValidationException, put_flow, invalid_xml2)  # unknown startReference

        invalid_xml3 = '<messageFlowDefinition name="" language="en" startReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogIm1lc3NhZ2VfMSJ9">\n        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0=" waitForFollowUpMessage="false"/>\n        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogIm1lc3NhZ2VfMSJ9" alertIntervalType="NONE" alertType="SILENT" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImZsdXNoXzEifQ==" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0=">\n            <content>Beste klant,\n\nBenader ons met al uw vragen inzake ons aanbod. Wij proberen u zo spoedig mogelijk te antwoorden.</content>\n            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">\n                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextBlockWidget" maxChars="50"/>\n            </form>\n        </formMessage>\n        <resultsFlush id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImZsdXNoXzEifQ==" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhaE5rWlhaLWJXOWlhV05oWjJWamJHOTFaR2h5Y2o4TEVncHRZeTEwY21GamEyVnlJZ3B5TVVCbWIyOHVZMjl0REFzU0VVMWxjM05oWjJWR2JHOTNSR1Z6YVdkdUlnNVRkR1ZzSUdWbGJpQjJjbUZoWnd3IiwgImlkIjogImVuZF8xIn0="/>\n    </messageFlowDefinition>'
        self.assertRaises(InvalidMessageFlowXmlException, put_flow, invalid_xml3)  # name is empty

        # Test start_flow
        human_user = users.User(u'a@foo.com')
        create_user_profile(human_user, human_user.email(), language=u'nl')
        makeFriends(human_user, service_user, None, None, None)

        start_flow(None, None, mfd2.identifier, [human_user.email()])

    def test_broadcast_types(self):
        self._prepare_svc()

        self.assertFalse(list_broadcast_types())
        put_broadcast_types(['a', 'b'])

        self.assertEqual(['a', 'b'], list_broadcast_types())
        put_menu_item("3d", "label", "tag", [0, 1, 0], is_broadcast_settings=True)
        self.assertRaises(CanNotDeleteBroadcastTypesException, put_broadcast_types, [])
        put_broadcast_types([], force=True)

    def test_put_service(self):
        self._prepare_svc('djmatic@example.com')

        cfg = put_service('new_jukebox@foo.com', 'My New Jukebox', 'my_password')
        self.assertTrue(cfg.apiKeys)
        self.assertTrue(cfg.apiKeys[0].key)
        self.assertTrue(cfg.sik)

        self.assertRaises(ServiceAlreadyExistsException, put_service, 'new_jukebox@foo.com', 'My New Jukebox', 'my_password')
        self.assertRaises(InvalidNameException, put_service, 'new2_jukebox@foo.com', 'My New Jukebox' * 25, 'my_password')

    def test_put_service_denied(self):
        self._prepare_svc()
        self.assertRaises(CreateServiceDeniedException, put_service, 'new_jukebox3@foo.com', 'My New Jukebox', 'my_password')


    def test_user_data(self):
        service_user = self._prepare_svc()

        friend_email = u"a%s@foo.com" % time.time()

        data = json.dumps(dict(test="hihihi")).decode('utf8')

        self.assertRaises(FriendNotFoundException, put_user_data, friend_email, data)  # non-existing user

        human_user = users.User(friend_email)
        create_user_profile(human_user, friend_email, language=u'nl')
        self.assertRaises(FriendNotFoundException, put_user_data, friend_email, data)  # user is no friend

        makeFriends(human_user, service_user, None, None, None)

        data = json.dumps(dict(test="ikkel", moe="hahaha")).decode('utf8')
        put_user_data(friend_email, data)

        data = json.dumps(dict(test="tikkel", john="doe")).decode('utf8')
        put_user_data(friend_email, data)

        get_friendto = lambda: run_in_xg_transaction(lambda: FriendTO.fromDBFriendMap(get_friends_map(human_user),
                                                                                      service_user,
                                                                                      True,
                                                                                      True,
                                                                                      human_user))

        self.assertDictEqual(dict(test="tikkel", moe="hahaha", john="doe", __rt__disabledBroadcastTypes=[]),
                             json.loads(get_friendto().userData))
        self.assertTrue(get_friendto().hasUserData)

        self.assertRaises(InvalidJsonStringException, put_user_data, friend_email, "invalid user data")
        self.assertRaises(InvalidJsonStringException, put_user_data, friend_email, "")

        del_user_data(friend_email, ["test"])
        self.assertTrue(get_friendto().hasUserData)

        del_user_data(friend_email, ["moe", "john"])
        self.assertFalse(get_friendto().hasUserData)

        japanese = u"スキーに行くのが好きです。"
        data_dict = dict(test="ikkel", moe="hahaha", japanese=japanese)
        data = json.dumps(data_dict).decode('utf8')
        put_user_data(friend_email, data)
        data = json.loads(get_user_data(friend_email, ["japanese"]))
        self.assertEqual(japanese, data["japanese"])

        data = json.loads(get_user_data(friend_email, ["japanese", "test", "moe"]))
        self.assertDictEqual(data, data_dict)
