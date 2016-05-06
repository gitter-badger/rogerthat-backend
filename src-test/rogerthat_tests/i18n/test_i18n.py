#!/usr/bin/python
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

from datetime import datetime
import os
import re
import sys

from rogerthat.dal.profile import get_user_profile
from rogerthat.rpc import users
from rogerthat.translations import D, DEFAULT_LANGUAGE, localize, SUPPORTED_LANGUAGES
import mc_unittest

PATH_END_RELEASE = os.path.join('src-test', 'test_release_only', 'i18n')
PATH_END_DEV = os.path.join('src-test', 'rogerthat_tests', 'i18n')
VALID_PATH_ENDINGS = [ PATH_END_DEV, PATH_END_RELEASE ]

# Giving ourselves until <TEMPORARILY_ALLOWED_INCOMPLETE_TRANSLATIONS_TIME> to complete the translations
TEMPORARILY_ALLOWED_INCOMPLETE_TRANSLATIONS = [u'pt_BR', u'fr', u'es', u'ro']
TEMPORARILY_ALLOWED_INCOMPLETE_TRANSLATIONS_TIME = datetime(2016, 6, 1)


class Test(mc_unittest.TestCase):

    def is_release_tst(self):
        return os.path.split(__file__)[0].endswith(PATH_END_RELEASE)

    def get_src_dir(self):
        src_is_ok = False
        for path_ending in VALID_PATH_ENDINGS:
            src_is_ok = src_is_ok or os.path.split(__file__)[0].endswith(path_ending)
        self.assert_(src_is_ok, 'Wrong path: %s' % os.path.split(__file__)[0])
        src_dir = os.path.normpath(os.path.join(__file__, '..', '..', '..', '..', 'src'))
        self.assert_(os.path.isdir(src_dir), "Couldn't find src dir - tried: %s" % src_dir)
        return src_dir

    def get_template_dir(self):
        src_dir = self.get_src_dir()
        template_dir = os.path.join(src_dir, "rogerthat", "templates")
        self.assert_(os.path.isdir(template_dir), "Couldnt find template dir %s" % template_dir)
        return template_dir

    def test_supported_languages(self):
        self.assert_(set(D.keys()) == set(SUPPORTED_LANGUAGES), "Wrong SUPPORTED_LANGUAGES")

    def test_incomplete_translation(self):
        default_language_keys = set(D[DEFAULT_LANGUAGE].keys())
        for lang in D.keys():
            if lang != DEFAULT_LANGUAGE:
                lang_keys = set(D[lang].keys())
                if lang_keys != default_language_keys:
                    diff = [''] + sorted(default_language_keys.symmetric_difference(lang_keys)) + ['']
                    msg = 'Incompletely translated language "%s". Inconsistent keys:%s' % (lang,
                                                                                           '\n********\n'.join(diff))
                    if lang in TEMPORARILY_ALLOWED_INCOMPLETE_TRANSLATIONS \
                            and TEMPORARILY_ALLOWED_INCOMPLETE_TRANSLATIONS_TIME > datetime.utcnow():
                        print msg
                    else:
                        self.assertTrue(False, msg)

    def test_unicode(self):
        for lang in D.keys():
            for value in D[lang].values():
                self.assert_(isinstance(value, unicode), 'Language "%s" value "%s" is not unicode' % (lang, value))

    def test_substitution(self):
        from rogerthat.bizz.profile import create_user_profile
        user_default = users.User(u'test_default@example.com')
        create_user_profile(user_default, user_default.email(), language=unicode(DEFAULT_LANGUAGE))
        user_default_profile = get_user_profile(user_default)
        self.assert_(localize(user_default_profile.language, "Test %(name)s %(number)d", name="bla bloe", number=33) == u"Test bla bloe 33", "Placeholder substitution not working well")

    def test_fallback_language(self):
        from rogerthat.bizz.profile import create_user_profile
        user_default = users.User(u'test_default@example.com')
        create_user_profile(user_default, user_default.email(), language=unicode(DEFAULT_LANGUAGE))
        user_nl = users.User(u'test_nl@example.com')
        create_user_profile(user_nl, user_nl.email(), language=u'nl')
        user_xx = users.User(u'test_xx@example.com')
        create_user_profile(user_xx, user_xx.email(), language=u'xx')
        user_es = users.User(u'test_es@example.com')
        create_user_profile(user_es, user_es.email(), language=u'es')

        user_default_profile = get_user_profile(user_default)
        user_xx_profile = get_user_profile(user_xx)
        user_nl_profile = get_user_profile(user_nl)
        user_es_profile = get_user_profile(user_es)

        # Fallback test for partially translated stuff
        TEST_KEY = "____test__ignore____"
        D[DEFAULT_LANGUAGE][TEST_KEY] = u"Test English 1€"
        D["nl"][TEST_KEY] = u"Test Nederlands 1€"
        self.assert_(localize(user_default_profile.language, TEST_KEY) == u"Test English 1€")
        self.assert_(localize(user_nl_profile.language, TEST_KEY) == u"Test Nederlands 1€")
        self.assert_(localize(user_xx_profile.language, TEST_KEY) == u"Test English 1€")  # unknown language
        self.assert_(localize(user_es_profile.language, TEST_KEY) == u"Test English 1€")  # language does not contain key -> fallback to default language + warning
        D[DEFAULT_LANGUAGE].pop(TEST_KEY)
        D["nl"].pop(TEST_KEY)

        # Fallback test for stuff that is only in code, not translated at all
        TEST_KEY_2 = "____test__ignore__2____ %(test)d"
        TEST_KEY_2_PREFIX = u"____test__ignore__2____ "
        self.assert_(localize(user_default_profile.language, TEST_KEY_2, test=1) == TEST_KEY_2_PREFIX + "1")
        self.assert_(localize(user_default_profile.language, TEST_KEY_2, test=2) == TEST_KEY_2_PREFIX + "2")
        self.assert_(localize(user_default_profile.language, TEST_KEY_2, test=3) == TEST_KEY_2_PREFIX + "3")
        self.assert_(localize(user_default_profile.language, TEST_KEY_2, test=4) == TEST_KEY_2_PREFIX + "4")


    @staticmethod
    def _parse_placeholders(self, format_string):
        """ Return all placeholders in a string. Example:
               Hi %(name)s, you scored %(percentage)d %%
               --> set with elements '(name)s' and '(percentage)d'
        """
        p = 0
        placeholders = []
        while p < len(format_string):
            if format_string[p] == '%':
                self.assert_(p + 1 < len(format_string), "Trailing %% character in %s" % format_string)
                p += 1

                # Ignore double %
                if format_string[p] == '%':
                    p += 1
                    continue
                self.assert_(format_string[p] == '(', 'Expected %%( in %s' % format_string)
                placeholder = ""
                p += 1
                while format_string[p] != ')':
                    placeholder += format_string[p]
                    p += 1
                p += 1
                placeholder_type = format_string[p]
                placeholders.append((placeholder.encode('utf-8'), placeholder_type))
            p += 1
        return placeholders

    def test_gae_placeholders(self):
        Test._test_placeholder(self, D)

    @staticmethod
    def _test_placeholder(self, translation_dict):
        for key in translation_dict[DEFAULT_LANGUAGE].keys():
            placeholders_en = set(Test._parse_placeholders(self, translation_dict[DEFAULT_LANGUAGE][key]))
            for lang in translation_dict:
                if lang != DEFAULT_LANGUAGE:
                    if key in translation_dict[lang]:
                        placeholders_lang = set(Test._parse_placeholders(self, translation_dict[lang][key]))
                        self.assert_(placeholders_en == placeholders_lang,
                                     "Different placeholders in 2 languages:\nen: %s\n%s: %s" % (
                                         translation_dict['en'][key], lang, translation_dict[lang][key]))
                    else:
                        print "Incomplete translation for key %s [%s]" % (key, lang)

    def test_code(self):
        if sys.platform == "win32":
            return
        translate_matcher = re.compile("\\{%\\s*?translate\\s+?(?P<language>[a-zA-Z0-9_]+?)\\s*?,\\s*?(?P<start>[\"\'])(?P<key>.*?)(?P=start)(?P<params>\\s*,\\s*(?P<start2>[\"\']).*(?P=start2)(\\s*?\\+\\s*?[a-zA-Z0-9_\\.\\|]*)?)*\\s*?%\\}")

        def _get_translation_keys(filename):
            if filename.endswith(".pyc"):
                return
            if filename.endswith(".py"):
                return
            f = open(filename, "rb")
            try:
                source_code = f.read()
            finally:
                f.close()

            for groups in translate_matcher.findall(source_code):
                key = groups[2].replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
                keys_found_in_code.add(unicode(key))

        def _scan_dir(path):
            for f in os.listdir(path):
                filename = os.path.join(path, f)
                if os.path.isfile(filename):
                    _get_translation_keys(filename)
                else:
                    if f.startswith("."):
                        continue
                    _scan_dir(filename)

        import ast
        testself = self
        class MyVisitor(ast.NodeVisitor):
            def visit_Call(self, node):
                if hasattr(node.func, 'id') and node.func.id == 'localize':
                    testself.assert_(len(node.args) >= 2, "Illegal number of args for %s\nfile: %s:%d" % (ast.dump(node), self.current_python_file, node.lineno))
                    key_object = node.args[1]
                    if isinstance(key_object, ast.Name):
                        testself.assertEqual('key', key_object.id)
                    else:
                        try:
                            key = key_object.s
                        except:
                            testself.assert_(False, 'Error in %s:%s' % (self.current_python_file, node.lineno))

                        substitutions = set()
                        for keyword in node.keywords:
                            substitutions.add(keyword.arg)
                        testself.assert_(re.match('^\s.*', key) == None, 'leading whitespace forbidden in [%s] - File %s:%d' % (key, self.current_python_file, node.lineno))
                        testself.assert_(re.match('.*\s$', key) == None, 'trailing whitespace forbidden in [%s] - File %s:%d' % (key, self.current_python_file, node.lineno))
                        testself.assert_(key in D[DEFAULT_LANGUAGE], 'String in code but not in default language map: [%s] - File %s:%d' % (key, self.current_python_file, node.lineno))
                        expected_substitutions = set(map(lambda x: x[0], Test._parse_placeholders(testself, D[DEFAULT_LANGUAGE][key])))
                        testself.assert_(substitutions == expected_substitutions, '\n\nUnexpected substitution:\n  File: %s:%d\n  Key: %s\n  Code args: %s\n  Substitutions: %s' % (self.current_python_file, node.lineno, key, substitutions, expected_substitutions))
                        keys_found_in_code.add(key)
                ast.NodeVisitor.generic_visit(self, node)

        m = MyVisitor()
        src_dir = self.get_src_dir()
        filenames = os.popen("find ""%s"" -name '*.py' | xargs grep 'localize *(' | cut -d: -f1 | uniq" % src_dir).read().splitlines()
        self.assert_(len(filenames) > 0, "Error: couldn't find src files with translation texts.\nIs the dir correct: %s" % src_dir)

        keys_found_in_code = set()
        for filename in filenames:
            f = open(filename, 'r')
            body = f.read()
            f.close()
            m.current_python_file = filename
            m.visit(ast.parse(body))

        translated_keys = set(D[DEFAULT_LANGUAGE].keys())

        _scan_dir(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src", "rogerthat", "pages"))
        _scan_dir(os.path.join(self.get_template_dir(), "generic"))

        if not keys_found_in_code == translated_keys:
            diff1 = keys_found_in_code.difference(translated_keys)
            diff2 = translated_keys.difference(keys_found_in_code)
            self.assert_(not diff1, "%s keys found in code but not translated:\n%s" % (len(diff1), diff1))
            self.assert_(not diff2, "%s keys translated but not found in code:\n%s" % (len(diff2), diff2))

    def test_web_and_email_templates(self):
        if not self.is_release_tst():
            return
        template_dir = self.get_template_dir()
        for lang in SUPPORTED_LANGUAGES:
            self.assert_(os.path.isdir(os.path.join(template_dir, lang)), "Could not find email/web templates for language %s" % lang)
        default_template_dir = os.path.join(template_dir, DEFAULT_LANGUAGE)
        templates = os.popen("find ""%s"" -depth 1 -name '*.tmpl'" % default_template_dir).read().splitlines()
        web_templates = os.popen("find ""%s"" -depth 1 -name '*.tmpl'" % os.path.join(default_template_dir, "web")).read().splitlines()
        self.assert_(len(templates) > 0)
        self.assert_(len(web_templates) > 0)
        from test_not_yet_translated import SKIP_TEMPLATES, SKIP_WEB_TEMPLATES

        for t in SKIP_TEMPLATES:
            print "- Skipped template: %s" % t
        for t in SKIP_WEB_TEMPLATES:
            print "- Skipped web template: %s" % t

        for lang in SUPPORTED_LANGUAGES:
            for template in templates:
                template_name = os.path.basename(template)
                if template_name not in SKIP_TEMPLATES:
                    self.assert_(os.path.isfile(os.path.join(template_dir, lang, template_name)), "Template %s not found in language %s" % (template_name, lang))
            for web_template in web_templates:
                web_template_name = os.path.basename(web_template)
                if web_template_name not in SKIP_WEB_TEMPLATES:
                    self.assert_(os.path.isfile(os.path.join(template_dir, lang, "web", web_template_name)), "Web template %s not found in language %s" % (web_template_name, lang))

    def test_web_templates_inheritance_symlinks(self):
        template_dir = self.get_template_dir()
        language_dirs = os.popen("find ""%s"" -depth 1 -type d" % template_dir).read().splitlines()
        PARENT_TEMPLATE = "base_base_mobile_simple_no_javascript.html"
        expected_target_path = os.path.join(template_dir, "generic", "web", PARENT_TEMPLATE)
        for language_dir in language_dirs:
            language = os.path.basename(language_dir)
            if language != "generic":
                symlinked_file = os.path.join(language_dir, "web", PARENT_TEMPLATE)
                self.assertTrue(os.path.islink(symlinked_file), "%s should be a symlink" % symlinked_file)
                self.assertEqual(os.path.realpath(symlinked_file), expected_target_path)

    def test_web_templates_languages(self):
        if not self.is_release_tst():
            return
        template_dir = self.get_template_dir()
        language_dirs = os.popen("find ""%s"" -depth 1 -type d" % template_dir).read().splitlines()
        languages = []
        for language_dir in language_dirs:
            language = os.path.basename(language_dir)
            if language != "generic":
                languages.append(language)
        self.assert_(set(languages) == set(SUPPORTED_LANGUAGES), "Mismatch: template languages %s but expecting languages %s" % (languages, SUPPORTED_LANGUAGES))
