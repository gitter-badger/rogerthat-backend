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

import logging

from lxml import etree

from rogerthat.dal import parent_key, put_and_invalidate_cache
from rogerthat.dal.mfd import get_multilanguage_message_flow_designs_by_status
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.service import get_service_identities
from rogerthat.models import ServiceTranslation, ServiceTranslationSet, ServiceMenuDef, ServiceInteractionDef, \
    MessageFlowDesign
from rogerthat.rpc import users
from rogerthat.utils import channel
from rogerthat.utils.languages import convert_iso_lang_to_web_lang
from google.appengine.ext import db, deferred
from mcfw.cache import cached
from mcfw.rpc import arguments, returns


MFLOW_XPATH_MAP = {'''//definition[@language=$lang]/message/content[text()!='']/text()''': ServiceTranslation.MFLOW_TEXT,
                   '''//definition[@language=$lang]/message/answer[@caption!='']/@caption''': ServiceTranslation.MFLOW_BUTTON,
                   '''//definition[@language=$lang]/message/answer[@action!='']/@action''': ServiceTranslation.MFLOW_POPUP,
                   '''//definition[@language=$lang]/message[@brandingKey!='']/@brandingKey''': ServiceTranslation.MFLOW_BRANDING,
                   '''//definition[@language=$lang]/formMessage/content[text()!='']/text()''': ServiceTranslation.MFLOW_TEXT,
                   '''//definition[@language=$lang]/formMessage[@brandingKey!='']/@brandingKey''': ServiceTranslation.MFLOW_BRANDING,
                   '''//definition[@language=$lang]/formMessage/form[@positiveButtonConfirmation!='']/@positiveButtonConfirmation''': ServiceTranslation.MFLOW_POPUP,
                   '''//definition[@language=$lang]/formMessage/form[@negativeButtonConfirmation!='']/@negativeButtonConfirmation''': ServiceTranslation.MFLOW_POPUP,
                   '''//definition[@language=$lang]/formMessage/form[@positiveButtonCaption!='']/@positiveButtonCaption''': ServiceTranslation.MFLOW_BUTTON,
                   '''//definition[@language=$lang]/formMessage/form[@negativeButtonCaption!='']/@negativeButtonCaption''': ServiceTranslation.MFLOW_BUTTON,
                   '''//definition[@language=$lang]/formMessage/form/widget[@placeholder!='']/@placeholder''': ServiceTranslation.MFLOW_FORM,
                   '''//definition[@language=$lang]/formMessage/form/widget[@unit!='']/@unit''': ServiceTranslation.MFLOW_FORM,
                   '''//definition[@language=$lang]/formMessage/form[@type='auto_complete' or @type='text_line' or @type='text_block']/widget[@value!='']/@value''': ServiceTranslation.MFLOW_FORM,
                   '''//definition[@language=$lang]/formMessage/form/widget/choice[@label!='']/@label''': ServiceTranslation.MFLOW_FORM
                   }

MFLOW_REFERENCES = ['startReference', 'reference', 'dismissReference', 'positiveReference', 'negativeReference']

def assemble_qrcode_strings(service_user):
    button_caption_set = set()
    qry = ServiceInteractionDef.gql("WHERE ANCESTOR IS :ancestor AND deleted = FALSE AND multilanguage = TRUE")
    qry.bind(ancestor=parent_key(service_user))
    for sid in qry.fetch(None):
        button_caption_set.add(sid.description)
    button_caption_set.discard(None)
    button_caption_set.discard("")
    return {ServiceTranslation.SID_BUTTON: button_caption_set}

def assemble_homescreen_strings(service_user):
    home_text_set = set()
    home_branding_set = set()
    identity_text_set = set()
    identity_branding_set = set()
    broadcast_type_set = set()
    broadcast_branding_set = set()

    service_profile = get_service_profile(service_user)
    home_text_set.update([service_profile.aboutMenuItemLabel,
                          service_profile.messagesMenuItemLabel,
                          service_profile.shareMenuItemLabel,
                          service_profile.callMenuItemLabel])
    broadcast_type_set.update(service_profile.broadcastTypes)
    broadcast_branding_set.add(service_profile.broadcastBranding)
    qry = ServiceMenuDef.gql("WHERE ANCESTOR IS :ancestor")
    qry.bind(ancestor=parent_key(service_user))
    items = qry.fetch(None)
    for item in items:
        home_text_set.add(item.label)
        home_branding_set.add(item.screenBranding)

    for service_identity in get_service_identities(service_user):
        identity_text_set.update([service_identity.name,
                                  service_identity.qualifiedIdentifier,
                                  service_identity.description,
                                  service_identity.mainPhoneNumber,
                                  service_identity.callMenuItemConfirmation])
        identity_branding_set.update([service_identity.descriptionBranding,
                                      service_identity.menuBranding])

    strings = {ServiceTranslation.HOME_TEXT: home_text_set,
               ServiceTranslation.HOME_BRANDING: home_branding_set,
               ServiceTranslation.IDENTITY_TEXT: identity_text_set,
               ServiceTranslation.IDENTITY_BRANDING: identity_branding_set,
               ServiceTranslation.BROADCAST_TYPE: broadcast_type_set,
               ServiceTranslation.BROADCAST_BRANDING: broadcast_branding_set}

    for set_ in strings.values():
        set_.discard(None)
        set_.discard("")

    return strings

@returns(dict)
@arguments(service_user=users.User)
def assemble_message_flow_strings(service_user):
    """Go over all flows of this service user and create an in-memory dict.
       Key = translation_type e.g. ServiceTranslation.MFLOW_POPUP
       Value = set of strings in default language

       Must run from a deferred

       Returns dict(translation_type: set(default strings))
    """
    flows = get_multilanguage_message_flow_designs_by_status(service_user, MessageFlowDesign.STATUS_VALID)

    language_map = dict((translation_type, set()) for translation_type in set(MFLOW_XPATH_MAP.values()))
    default_language = get_service_profile(service_user).defaultLanguage

    for flow in flows:
        thexml = flow.xml.replace('xmlns="https://rogerth.at/api/1/MessageFlow.xsd"', '')  # Dont want complex xpath queries due to namespace
        tree = etree.fromstring(thexml.encode('utf-8'))  # @UndefinedVariable

        for (path, translation_type) in MFLOW_XPATH_MAP.iteritems():
            for default_str in tree.xpath(path, lang=default_language):
                if default_str:
                    if translation_type == ServiceTranslation.MFLOW_TEXT:
                        default_str = default_str.strip()
                    language_map[translation_type].add(default_str)
                else:
                    logging.warning("XPATH ERROR - found empty str for path %s" % path)

    return language_map

def assemble_service_strings(service_user):
    d = assemble_homescreen_strings(service_user)
    d.update(assemble_message_flow_strings(service_user))
    d.update(assemble_qrcode_strings(service_user))
    return d

def sync_service_translations(service_user):
    service_profile = get_service_profile(service_user)
    translation_set = None
    if service_profile.editableTranslationSet:
        translation_set = ServiceTranslationSet.get(db.Key(encoded=service_profile.editableTranslationSet))
        translation_set.status = ServiceTranslationSet.SYNCING
        translation_set.put()
    else:
        translation_set = ServiceTranslationSet.create_editable_set(service_user)
        translation_set.status = ServiceTranslationSet.SYNCING
        translation_set.put()
        service_profile.editableTranslationSet = str(translation_set.key())
        service_profile.put()

    current_translations = get_all_translations(translation_set)
    current_service_strings = assemble_service_strings(service_user)
    current_service_strings[ServiceTranslation.BRANDING_CONTENT] = current_translations.get(ServiceTranslation.BRANDING_CONTENT, dict())

    updated_translations = dict()

    for translation_type, default_strings in current_service_strings.iteritems():
        current_translations_for_type = current_translations.get(translation_type, dict())
        updated_translations_for_type = dict()
        for default_string in default_strings:
            updated_translations_for_type[default_string] = current_translations_for_type.get(default_string, None)
        updated_translations[translation_type] = updated_translations_for_type

    save_translations(translation_set, updated_translations)

def get_active_translation_set(service_user):
    service_profile = get_service_profile(service_user)
    if service_profile.activeTranslationSet:
        translation_set = ServiceTranslationSet.get(db.Key(encoded=service_profile.activeTranslationSet))
        return translation_set
    return None

def get_editable_translation_set(service_user):
    service_profile = get_service_profile(service_user)
    if service_profile.editableTranslationSet:
        translation_set = ServiceTranslationSet.get(db.Key(encoded=service_profile.editableTranslationSet))
        return translation_set
    return None

def get_all_translations(translation_set, translation_types=None):
    if translation_types:
        keys = [ServiceTranslation.create_key(translation_set, translation_type) for translation_type in translation_types]
        db_translations = db.get(keys)
    else:
        db_translations = ServiceTranslation.all().ancestor(translation_set).fetch(None)
    trdict = dict()
    for db_translation in db_translations:
        if db_translation:
            trdict[db_translation.translation_type] = db_translation.translation_dict
    return trdict

def save_translations(service_translation_set, multi_translation_dict):
    def trans():
        translation_keys = ServiceTranslation.all(keys_only=True).ancestor(service_translation_set).fetch(None)
        db.delete(translation_keys)
        to_put = list()
        for translation_type, translation_dict in multi_translation_dict.iteritems():
            to_put.append(ServiceTranslation.create(service_translation_set, translation_type, translation_dict))
        db.put(to_put)
    db.run_in_transaction(trans)

def deploy_translation(service_user):

    def trans():
        to_put = set()

        service_profile = get_service_profile(service_user)
        if not service_profile.editableTranslationSet:
            logging.error("Deploy translation error - no editable translation found for svc %s" % service_user.email())
            return

        # 1. Archive old active translation set
        if service_profile.activeTranslationSet:
            old_active_translation_set = ServiceTranslationSet.get(service_profile.activeTranslationSet)
            old_active_translation_set.status = ServiceTranslationSet.ARCHIVED
            to_put.add(old_active_translation_set)

        # 2. Promote old editable translation set to new active
        service_profile.activeTranslationSet = service_profile.editableTranslationSet
        to_put.add(service_profile)
        new_active_translation_set = ServiceTranslationSet.get(service_profile.activeTranslationSet)
        new_active_translation_set.status = ServiceTranslationSet.ACTIVE
        to_put.add(new_active_translation_set)

        # 3. Create new editable translation set
        new_editable_translation_set = ServiceTranslationSet.create_editable_set(service_user)
        new_editable_translation_set.latest_export_timestamp = new_active_translation_set.latest_export_timestamp
        service_profile.editableTranslationSet = str(new_editable_translation_set.key())
        to_put.add(new_editable_translation_set)

        # 4. Copy existing translations to new
        branding_translations_dict = None
        for tr in ServiceTranslation.all().ancestor(new_active_translation_set).fetch(None):
            translation_dict = tr.translation_dict
            if tr.translation_type == ServiceTranslation.BRANDING_CONTENT:
                branding_translations_dict = translation_dict
            to_put.add(ServiceTranslation.create(new_editable_translation_set, tr.translation_type, translation_dict))

        # 5. Store all in db
        put_and_invalidate_cache(*to_put)

        return service_profile, branding_translations_dict

    xg_on = db.create_transaction_options(xg=True)
    service_profile, branding_translations_dict = db.run_in_transaction_options(xg_on, trans)

    if len(service_profile.supportedLanguages) > 1:
        if branding_translations_dict:
            deferred.defer(_translate_all_app_brandings, service_user, branding_translations_dict)
        deferred.defer(_translate_all_message_flows, service_user)
        deferred.defer(_update_i18n_search_configs, service_user)
    deferred.defer(_populate_new_editable_set, service_user)


def _update_i18n_search_configs(service_user):
    from rogerthat.bizz.service import re_index
    for service_identity in get_service_identities(service_user):
        re_index(service_identity.user)


def _translate_all_app_brandings(service_user, branding_translations_dict):
    '''update all app brandings after editable set was deployed'''
    from rogerthat.bizz.branding import add_translations_to_all_app_brandings
    add_translations_to_all_app_brandings(service_user, branding_translations_dict)


def _translate_all_message_flows(service_user):
    '''update all multi-language flows after editable set was deployed'''
    from rogerthat.bizz.service.mfd import render_xml_for_message_flow_design, render_js_for_message_flow_designs, \
        get_message_flow_design_context

    logging.debug("Re-translating all message flows of %s" % service_user.email())

    translator = None
    puts = list()
    multilanguage_flows = get_multilanguage_message_flow_designs_by_status(service_user, MessageFlowDesign.STATUS_VALID)
    for mfd in multilanguage_flows:
        if translator is None:
            translator = get_translator(service_user, ServiceTranslation.MFLOW_TYPES)
        try:
            context = get_message_flow_design_context(mfd) if mfd.definition else None
            render_xml_for_message_flow_design(mfd, translator, context)
            puts.append(mfd)
        except:
            logging.warning("Could not translate msg flow", exc_info=True)


    try:
        changed_languages = render_js_for_message_flow_designs(puts)
    except:
        logging.warning("Could not render JS for flows", exc_info=True)
        changed_languages = None

    put_and_invalidate_cache(*puts)

    if not changed_languages:
        from rogerthat.bizz.job.update_friends import schedule_update_all_friends_of_service_user
        schedule_update_all_friends_of_service_user(service_user, bump_service_version=True, clear_broadcast_settings_cache=True)

def check_i18n_status_of_message_flows(service_user):
    from rogerthat.bizz.service.mfd import render_xml_for_message_flow_design

    def trans():
        translator = get_translator(service_user)
        mfds = get_multilanguage_message_flow_designs_by_status(service_user, MessageFlowDesign.STATUS_VALID)
        for mfd in mfds:
            render_xml_for_message_flow_design(mfd, translator, dict())

        put_and_invalidate_cache(*mfds)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)

    channel.send_message(service_user, u'rogerthat.mfd.changes')


def _populate_new_editable_set(service_user):
    '''copy active content to editable service translation set'''

    def trans():
        puts = list()
        service_profile = get_service_profile(service_user)
        editable_translation_set_key = db.Key(encoded=service_profile.editableTranslationSet)
        active_translation_set_key = db.Key(encoded=service_profile.activeTranslationSet)
        active_translations = ServiceTranslation.all().ancestor(active_translation_set_key).fetch(None)
        for active_translation in active_translations:
            editable_translation = ServiceTranslation.create(editable_translation_set_key,
                                                             active_translation.translation_type,
                                                             active_translation.translation_dict)
            puts.append(editable_translation)
        db.put(puts)

    logging.debug("Copying active translation set into the new editable translation set")
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


class Translator(object):

    def __init__(self, translation_dict, supported_languages):
        """
        Translation dict must not necessarily contain every translation.
        E.g. for flows, only the flow strings is enough
        """

        self.d = translation_dict
        self.default_language = supported_languages[0]
        self.supported_languages = supported_languages

    @property
    def non_default_supported_languages(self):
        return self.supported_languages[1:]

    def _translate(self, translation_type, string, target_language):
        """
        translation_type defined on ServiceTranslation

        returns <bool success>, <possibly translated string>
        """
        if not string:
            return True, string
        if target_language == self.default_language:
            return True, string
        if translation_type in self.d:
            translations = self.d[translation_type].get(string, None)
            if translations:
                target_language = convert_iso_lang_to_web_lang(target_language)
                if target_language in translations:
                    return True, translations[target_language]
                if target_language and '-' in target_language:
                    target_language = target_language.split('-')[0]
                    if target_language in translations:
                        return True, translations[target_language]
        return False, string

    def translate(self, translation_type, string, target_language):
        """
        translation_type defined on ServiceTranslation

        returns <possibly translated string>
        """
        return self._translate(translation_type, string, target_language)[1]

    def translate_flow(self, default_xml, flow_name=None):
        """
        Input = full xml (including subflows) in default language
        Output = full multilanguage xml
        """
        from rogerthat.bizz.service.mfd import get_json_from_b64id, create_b64id_from_json_dict

        result = { self.default_language:default_xml }

        for language in self.supported_languages[1:]:
            tree = etree.fromstring(default_xml.encode('utf-8'))  # @UndefinedVariable
            try:
                default_str_element = None
                for (path, translation_type) in MFLOW_XPATH_MAP.iteritems():
                    for default_str_element in tree.xpath(path, lang=self.default_language):
                        default_lang_str = unicode(default_str_element)
                        if translation_type in ServiceTranslation.MFLOW_TYPES_ALLOWING_LANGUAGE_FALLBACK:
                            if default_lang_str in self.d[translation_type] and self.d[translation_type][default_lang_str]:
                                translation = self.d[translation_type][default_lang_str].get(language, default_lang_str)
                            else:
                                # None or empty dict
                                translation = default_lang_str
                        else:
                            translation = self.d[translation_type][default_lang_str][language]
                        if default_str_element.is_text:
                            default_str_element.getparent().text = translation
                        elif default_str_element.is_attribute:
                            # Translate attribute
                            attribute_name = path.split('@')[-1]
                            default_str_element.getparent().attrib[attribute_name] = translation
                # Set language of definition
                tree.xpath('/definition')[0].attrib['language'] = language

                # Update references ('lang' value in json_dict of id attr)
                for ref in MFLOW_REFERENCES:
                    for str_element in tree.xpath('//definition[@language=$lang]//@%s' % ref, lang=language):
                        if str_element.startswith('base64:'):
                            json_dict = get_json_from_b64id(str_element)
                            json_dict['lang'] = language
                            v = create_b64id_from_json_dict(json_dict)
                            str_element.getparent().attrib[ref] = v

                            elements_with_id = tree.xpath("//definition[@language=$lang]//@id", lang=language)
                            for el in elements_with_id:
                                if el == str_element:
                                    el.getparent().attrib['id'] = v

                result[language] = etree.tounicode(tree)  # @UndefinedVariable
            except:
                logging.warning("Could not translate msg flow [%s] to lang [%s] - error with str [%s]" % (flow_name, language, unicode(default_str_element)), exc_info=True)
        return result

class DummyTranslator(Translator):
    def __init__(self, default_language):
        self.default_language = default_language
        self.supported_languages = [default_language]

    def _translate(self, translation_type, string, target_language):
        return True, string

    def translate(self, translation_type, string, target_language):
        return string

    def translate_flow(self, default_xml, flow_name=None):
        return { self.default_language:default_xml }

@cached(1, request=True, memcache=False)
@returns(Translator)
@arguments(service_user=users.User, translation_types=[int], language=unicode)
def get_translator(service_user, translation_types=None, language=None):
    """ translation_types = list of translation_types """
    service_profile = get_service_profile(service_user)
    supportedLanguages = service_profile.supportedLanguages
    # use dummy translator for default language or unsupported language
    if language != service_profile.defaultLanguage:
        if len(supportedLanguages) > 1:
            s = get_active_translation_set(service_user)
            if s:
                return Translator(get_all_translations(s, translation_types), supportedLanguages)
    return DummyTranslator(service_profile.defaultLanguage)
