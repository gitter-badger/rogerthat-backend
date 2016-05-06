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
import time
from types import NoneType

from rogerthat.bizz.i18n import get_editable_translation_set, get_all_translations, save_translations, \
    deploy_translation, sync_service_translations
from rogerthat.consts import OFFICIALLY_SUPPORTED_LANGUAGES
from rogerthat.dal.profile import get_service_profile
from rogerthat.models import ServiceTranslation
from rogerthat.rpc import users
from rogerthat.rpc.service import BusinessException
from rogerthat.to.system import TranslationSetTO, TranslationTO, TranslationValueTO
from rogerthat.utils import case_insensitive_compare, reversed_dict, get_full_language_string, now, bizz_check
from mcfw.rpc import returns, arguments
import xlrd
import xlwt


FIRST_CONTENT_ROW = 10
LANGUAGES_ROW = FIRST_CONTENT_ROW - 3

@returns(tuple)
@arguments(service_user=users.User, browser_timezone=int)
def excel_export(service_user, browser_timezone=0):
    sync_service_translations(service_user)

    service_profile = get_service_profile(service_user)
    service_languages = service_profile.supportedLanguages

    editable_translation_set = get_editable_translation_set(service_user)
    editable_translation_set.latest_export_timestamp = now()
    editable_translation_set.put()

    all_translations = get_all_translations(editable_translation_set)

    # Create Workbook
    book = xlwt.Workbook(encoding="utf-8")
    sheet = book.add_sheet("Rogerthat")

    wrap_alignment = xlwt.Alignment()
    wrap_alignment.wrap = xlwt.Alignment.WRAP_AT_RIGHT
    wrap_alignment.horz = xlwt.Alignment.HORZ_LEFT
    wrap_alignment.vert = xlwt.Alignment.VERT_CENTER
    title_alignment = xlwt.Alignment()
    title_alignment.horz = xlwt.Alignment.HORZ_CENTER
    bold_font = xlwt.Font()
    bold_font.bold = True
    red_font = xlwt.Font()
    red_font.colour_index = 10

    pattern_white = xlwt.Pattern()
    pattern_white.pattern = xlwt.Pattern.SOLID_PATTERN
    pattern_white.pattern_fore_colour = 1
    pattern_dark = xlwt.Pattern()
    pattern_dark.pattern = xlwt.Pattern.SOLID_PATTERN
    pattern_dark.pattern_fore_colour = 41
    pattern_very_dark = xlwt.Pattern()
    pattern_very_dark.pattern = xlwt.Pattern.SOLID_PATTERN
    pattern_very_dark.pattern_fore_colour = 21
    border_leftright = xlwt.Borders()
    border_leftright.left = xlwt.Borders.THIN
    border_leftright.left = xlwt.Borders.THIN

    bold_style = xlwt.XFStyle()
    bold_style.font = bold_font
    bold_style.alignment = title_alignment
    bold_style.borders = border_leftright

    regular_style1 = xlwt.XFStyle()
    regular_style1.alignment = wrap_alignment
    regular_style1.pattern = pattern_white
    regular_style1.borders = border_leftright

    red_style1 = xlwt.XFStyle()
    red_style1.alignment = wrap_alignment
    red_style1.pattern = pattern_white
    red_style1.borders = border_leftright
    red_style1.font = red_font

    regular_style2 = xlwt.XFStyle()
    regular_style2.alignment = wrap_alignment
    regular_style2.pattern = pattern_dark
    regular_style2.borders = border_leftright

    red_style2 = xlwt.XFStyle()
    red_style2.alignment = wrap_alignment
    red_style2.pattern = pattern_dark
    red_style2.borders = border_leftright
    red_style2.font = red_font

    black_style = xlwt.XFStyle()
    black_style.pattern = pattern_very_dark

    # Write header info
    export_time_str = time.strftime('%a, %d %b %Y %H:%M:%S', time.gmtime(editable_translation_set.latest_export_timestamp - browser_timezone))

    sheet.write(0, 0, "Rogerthat service:")
    sheet.write(0, 1, service_user.email())
    sheet.write(1, 0, "Export timestamp:")
    sheet.write(1, 1, export_time_str)
    sheet.write(2, 0, "Export id:")
    sheet.write(2, 1, editable_translation_set.latest_export_timestamp)

    sheet.write(4, 1, 'Text in red must be translated to every supported language.', red_style1)
    sheet.write(5, 1, 'Text in black will fall back to default language if not translated.', regular_style1)

    # Write language names
    row = LANGUAGES_ROW
    sheet.col(0).width = 8000  # translation types
    for lang in service_languages:
        i = 1 + service_languages.index(lang)
        sheet.write(row, i, lang, bold_style)
        sheet.write(row + 1, i, get_full_language_string(lang), bold_style)
        sheet.col(i).width = 20000

    # Write translation strings
    row = FIRST_CONTENT_ROW
    other_languages = zip(range(len(service_languages[1:])), service_languages[1:])

    # Fields in red must be translated. There is no fallback
    red_types = set(ServiceTranslation.MFLOW_TYPES).difference(set(ServiceTranslation.MFLOW_TYPES_ALLOWING_LANGUAGE_FALLBACK))

    if all_translations:
        for type_, translation_dict in sorted(all_translations.iteritems()):
            if translation_dict:
                for default_string in sorted(translation_dict.keys(), cmp=case_insensitive_compare):
                    translated_strings_dict = translation_dict[default_string] or dict()
                    sheet.write(row, 0, ServiceTranslation.TYPE_MAP[type_])
                    if type_ in red_types:
                        sheet.write(row, 1, default_string, red_style1 if row % 2 else red_style2)
                    else:
                        sheet.write(row, 1, default_string, regular_style1 if row % 2 else regular_style2)
                    for lang_index, lang in other_languages:
                        sheet.write(row, 2 + lang_index, translated_strings_dict.get(lang, ''), regular_style1 if row % 2 else regular_style2)
                    row += 1
                for column in range(0, 2 + len(other_languages)):
                    sheet.write(row, column, '', black_style)
                row += 1

    return book, editable_translation_set.latest_export_timestamp - browser_timezone

@returns(NoneType)
@arguments(service_user=users.User, book=xlrd.Book)
def excel_import(service_user, book):
    service_profile = get_service_profile(service_user)
    service_languages = service_profile.supportedLanguages
    sheet = book.sheet_by_name('Rogerthat')

    email_in_xls = sheet.row(0)[1].value
    if email_in_xls != service_user.email():
        raise BusinessException("The imported Excel file contains the translations of a different service.")

    editable_translation_set = get_editable_translation_set(service_user)
    export_id = sheet.row(2)[1].value
    if int(export_id) != editable_translation_set.latest_export_timestamp:
        raise BusinessException("The Excel file is out of date.\nYou can export the latest version and bring that one up to date.")

    # Read titles (languages)
    xls_languages = [cell.value for cell in sheet.row(LANGUAGES_ROW)[1:]]

    default_xls_language = xls_languages[0]
    if default_xls_language != service_profile.defaultLanguage:
        raise BusinessException("Wrong default language found (cell B%s: %s)." % (LANGUAGES_ROW + 1, default_xls_language))

    unsupported_languages = [l for l in xls_languages if l not in OFFICIALLY_SUPPORTED_LANGUAGES]
    if unsupported_languages:
        raise BusinessException("Language(s) not supported by Rogerthat: %s." % ','.join(unsupported_languages))

    unsupported_service_languages = ["* %s" % get_full_language_string(l) for l in xls_languages if l not in service_languages]
    if unsupported_service_languages:
        raise BusinessException("Language(s) not in supported languages of this service:\n%s." % '\n'.join(unsupported_service_languages))

    all_translations = get_all_translations(editable_translation_set)

    reverse_mapped_translation_types = reversed_dict(ServiceTranslation.TYPE_MAP)
    zipped_xls_other_languages = zip(range(len(xls_languages)), xls_languages)[1:]

    # Read all translations
    row = FIRST_CONTENT_ROW
    for i in xrange(row, sheet.nrows):
        xls_row = sheet.row(i)
        if not any([x.value for x in xls_row]):
            continue  # Empty row

        human_readable_type = unicode(xls_row[0].value)
        default_string = unicode(xls_row[1].value)

        translation_type = reverse_mapped_translation_types[human_readable_type]
        if translation_type not in all_translations:
            all_translations[translation_type] = dict()

        if default_string not in all_translations[translation_type]:
            all_translations[translation_type][default_string] = None

        for lang_index, lang in zipped_xls_other_languages:
            translation = unicode(xls_row[1 + lang_index].value)
            if translation:
                if all_translations[translation_type][default_string] is None:
                    all_translations[translation_type][default_string] = dict()
                all_translations[translation_type][default_string][lang] = translation

    logging.info(all_translations)

    _validate_broadcast_types(all_translations)

    save_translations(editable_translation_set, all_translations)
    deploy_translation(service_user)

def _validate_broadcast_types(all_translations):
    # Translated broadcast types should not contain duplicates
    if ServiceTranslation.BROADCAST_TYPE in all_translations:
        broadcast_types = dict()
        for translations in all_translations[ServiceTranslation.BROADCAST_TYPE].itervalues():
            if translations:
                for lang, translation in translations.iteritems():
                    if lang in broadcast_types:
                        bizz_check(translation not in broadcast_types[lang],
                                   "Duplicate translated broadcast types are not allowed.\n(%s: %s)" % (lang, translation))
                    else:
                        broadcast_types[lang] = list()
                    broadcast_types[lang].append(translation)

@returns(NoneType)
@arguments(service_user=users.User, translations=TranslationSetTO)
def translation_import(service_user, translations):
    service_profile = get_service_profile(service_user)
    service_languages = service_profile.supportedLanguages

    if translations.email != service_user.email():
        raise BusinessException("The translation object contains the translations of a different service.")

    editable_translation_set = get_editable_translation_set(service_user)
    if translations.export_id != editable_translation_set.latest_export_timestamp:
        raise BusinessException("The translation object is out of date.\nYou can export the latest version and bring that one up to date.")

    all_translations = get_all_translations(editable_translation_set)

    for translation_to in translations.translations:
        translation_type = translation_to.type
        if translation_type not in all_translations:
            all_translations[translation_type] = dict()

        default_string = translation_to.key
        if default_string not in all_translations[translation_type]:
            all_translations[translation_type][default_string] = None

        for value_to in translation_to.values:
            if value_to.language not in OFFICIALLY_SUPPORTED_LANGUAGES:
                raise BusinessException("Language not supported by Rogerthat: %s." % value_to.language)
            if value_to.language not in service_languages:
                raise BusinessException("Language not in supported languages of this service:\n%s." % value_to.language)

            if all_translations[translation_type][default_string] is None:
                all_translations[translation_type][default_string] = dict()
            all_translations[translation_type][default_string][value_to.language] = value_to.value

    logging.info(all_translations)

    _validate_broadcast_types(all_translations)

    save_translations(editable_translation_set, all_translations)
    deploy_translation(service_user)

@returns(TranslationSetTO)
@arguments(service_user=users.User)
def translation_export(service_user):
    sync_service_translations(service_user)

    editable_translation_set = get_editable_translation_set(service_user)
    editable_translation_set.latest_export_timestamp = now()
    editable_translation_set.put()

    all_translations = get_all_translations(editable_translation_set)
    logging.info("exporting %s" % all_translations)

    translation_set_to = TranslationSetTO()
    translation_set_to.translations = list()
    translation_set_to.email = service_user.email()
    translation_set_to.export_id = editable_translation_set.latest_export_timestamp

    for type_, translation_dict in sorted(all_translations.iteritems()):
        if translation_dict:
            for key, values in sorted(translation_dict.iteritems()):
                translation_to = TranslationTO()
                translation_to.type = type_
                translation_to.key = key
                translation_to.values = list()
                translation_set_to.translations.append(translation_to)

                if values:
                    for language, value in sorted(values.iteritems()):
                        translation_value_to = TranslationValueTO()
                        translation_value_to.language = language
                        translation_value_to.value = value
                        translation_to.values.append(translation_value_to)

    return translation_set_to
