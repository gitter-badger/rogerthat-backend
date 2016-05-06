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

from rogerthat.bizz.friends import makeFriends
from rogerthat.bizz.i18n import sync_service_translations, get_editable_translation_set, get_all_translations, \
    save_translations, deploy_translation, get_active_translation_set, get_translator, DummyTranslator
from rogerthat.bizz.profile import create_service_profile, create_user_profile
from rogerthat.bizz.service import create_menu_item
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.service import get_default_service_identity
from rogerthat.models import ServiceProfile
from rogerthat.rpc import users
from rogerthat.to.friends import FriendTO
from rogerthat.to.service import FindServiceItemTO
from google.appengine.ext import db
import mc_unittest


def translate_service_strings(service_user):
    service_profile = get_service_profile(service_user)
    sync_service_translations(service_user)
    translation_set = get_editable_translation_set(service_user)
    tr_dict = get_all_translations(translation_set)
    for type_, translations in tr_dict.iteritems():
        for k in translations.iterkeys():
            for l in service_profile.supportedLanguages[1:]:
                translated = "%s_%s" % (l, k)
                if tr_dict[type_][k]:
                    tr_dict[type_][k][l] = translated
                else:
                    tr_dict[type_][k] = { l: translated }
    save_translations(translation_set, tr_dict)
    deploy_translation(service_user)
    assert get_active_translation_set(service_user)

class Test(mc_unittest.TestCase):

    def _prepareService(self, email):
        service_user = users.User(unicode(email))
        service_profile, service_identity = create_service_profile(service_user, u's1')
        service_profile.supportedLanguages = ["en", "fr", "nl"]

        service_profile_attrs = ["aboutMenuItemLabel", "messagesMenuItemLabel", "shareMenuItemLabel", "callMenuItemLabel"]

        for attr in service_profile_attrs:
            setattr(service_profile, attr, attr)
        service_profile.put()

        service_identity_attrs = ["name", "qualifiedIdentifier", "description", "descriptionBranding", "menuBranding",
                                  "mainPhoneNumber", "callMenuItemConfirmation"]
        for attr in service_identity_attrs:
            setattr(service_identity, attr, attr)
        service_identity.put()

        # Create some menu items
        for coords in [[1, 0, 1], [1, 1, 1], [1, 2, 1], [1, 3, 1]]:
            create_menu_item(service_user, "3d", "000000", 'x'.join(map(str, coords)), "tag", coords, "screenBranding",
                             None, False, False, [])

        # Translate service/identity properties
        translate_service_strings(service_user)

        return service_user, service_profile

    def _prepareHumans(self, languages):
        human_users = dict([ (lang, users.User(u"%s@foo.com" % lang)) for lang in languages ])

        for lang, human_user in human_users.iteritems():
            create_user_profile(human_user, human_user.email(), lang)

        return human_users

    def testTranslatorClass(self):
        service_user, service_profile = self._prepareService('s1@foo.com')

        self.assertIsInstance(get_translator(service_user, None, service_profile.defaultLanguage), DummyTranslator)

        for lang in [None] + service_profile.supportedLanguages[1:]:
            self.assertNotIsInstance(get_translator(service_user, None, lang), DummyTranslator)


    def testServiceFriendTO(self):
        # Prepare service
        service_user, service_profile = self._prepareService('s1@foo.com')

        # Prepare human_users
        human_users = self._prepareHumans(['en', 'fr', 'nl', 'ar'])

        for human_user in human_users.itervalues():
            makeFriends(human_user, service_user, original_invitee=None, servicetag=None, origin=None)

        # Check FriendTO
        for lang, human_user in human_users.iteritems():
            friend_map = get_friends_map(human_user)
            serviceTO = FriendTO.fromDBFriendMap(friend_map, service_user, includeAvatarHash=False,
                                                 includeServiceDetails=True, targetUser=human_user)

            if lang == service_profile.defaultLanguage or lang not in service_profile.supportedLanguages:
                prefix = ""
            else:
                prefix = "%s_" % lang

            for to_attr in ["name", "description", "descriptionBranding", "qualifiedIdentifier"]:
                expected = prefix + to_attr
                self.assertEqual(getattr(serviceTO, to_attr), expected,
                                 "serviceTO.%s != '%s' (language: %s)" % (to_attr, expected, lang))

            for to_attr, service_profile_attr in {'aboutLabel': 'aboutMenuItemLabel',
                                                  'messagesLabel': 'messagesMenuItemLabel',
                                                  'shareLabel': 'shareMenuItemLabel',
                                                  'callLabel': 'callMenuItemLabel',
                                                  'callConfirmation': 'callMenuItemConfirmation'}.iteritems():
                expected = prefix + service_profile_attr
                self.assertEqual(getattr(serviceTO.actionMenu, to_attr), expected,
                                 "serviceTO.actionMenu.%s != '%s' (language: %s)" % (to_attr, expected, lang))

            for item in serviceTO.actionMenu.items:
                expected_label = prefix + "x".join(map(str, item.coords))
                self.assertEqual(item.label, expected_label,
                                 "item.label != '%s' (language: %s)" % (expected_label, lang))

                expected_screenBranding = prefix + 'screenBranding'
                self.assertEqual(item.screenBranding, expected_screenBranding,
                                 "item.screenBranding != '%s' (language: %s)" % (expected_screenBranding, lang))

    def testSearchResults(self):
        self.set_datastore_hr_probability(1)

        # Prepare services
        service_profile = self._prepareService('s1@foo.com')[1]
        si = get_default_service_identity(service_profile.user)

        # Check FindServiceItemTO
        for lang in ['en', 'fr', 'nl', 'ar']:
            if lang == service_profile.defaultLanguage or lang not in service_profile.supportedLanguages:
                prefix = ""
            else:
                prefix = "%s_" % lang

            itemTO = FindServiceItemTO.fromServiceIdentity(si, lang)

            for to_attr, si_attr in {"name": "name",
                                     "description": "description",
                                     "description_branding": "descriptionBranding",
                                     "qualified_identifier": "qualifiedIdentifier"}.iteritems():
                expected = prefix + si_attr
                self.assertEqual(getattr(itemTO, to_attr), expected,
                                 "itemTO.%s != '%s' (language: %s)" % (to_attr, expected, lang))

    def testDeploy(self):
        self.set_datastore_hr_probability(1)
        service_user, service_profile = self._prepareService('s1@foo.com')

        old_editable_set_key = service_profile.editableTranslationSet
        old_active_set_key = service_profile.activeTranslationSet

        deploy_translation(service_user)

        service_profile = ServiceProfile.get(service_profile.key())

        new_editable_set_key = service_profile.editableTranslationSet
        new_active_set_key = service_profile.activeTranslationSet

        self.assertNotEqual(old_editable_set_key, new_editable_set_key)
        self.assertNotEqual(old_active_set_key, new_active_set_key)

        assert db.get(new_editable_set_key)
        assert db.get(new_active_set_key)
