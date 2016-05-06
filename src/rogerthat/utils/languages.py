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

from rogerthat.consts import OFFICIALLY_SUPPORTED_LANGUAGES
from mcfw.rpc import returns, arguments


@returns(unicode)
@arguments(web_lang=unicode)
def convert_web_lang_to_iso_lang(web_lang):
    if web_lang and '-' in web_lang:
        lang, region = web_lang.split('-', 1)
        return u"%s_%s" % (lang.lower(), region.upper())
    else:
        return web_lang


@returns(unicode)
@arguments(iso_lang=unicode)
def convert_iso_lang_to_web_lang(iso_lang):
    if iso_lang is None:
        return None
    return iso_lang.replace('_', '-').lower()


WEB_TO_ISO_LANGUAGES = dict(((web_lang, convert_web_lang_to_iso_lang(web_lang))
                             for web_lang in OFFICIALLY_SUPPORTED_LANGUAGES))
OFFICIALLY_SUPPORTED_ISO_LANGUAGES = dict(((WEB_TO_ISO_LANGUAGES[web_lang], language)
                                           for web_lang, language in OFFICIALLY_SUPPORTED_LANGUAGES.iteritems()))

@returns(unicode)
@arguments(web_lang_or_iso_lang=unicode)
def get_iso_lang(web_lang_or_iso_lang):
    return WEB_TO_ISO_LANGUAGES.get(web_lang_or_iso_lang, web_lang_or_iso_lang)
