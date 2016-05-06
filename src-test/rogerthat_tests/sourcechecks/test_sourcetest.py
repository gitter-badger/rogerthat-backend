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

import os
import sys

from rogerthat import translations
from rogerthat.consts import OFFICIALLY_SUPPORTED_LANGUAGES
from rogerthat.utils import azzert, get_full_language_string
from rogerthat.utils.languages import OFFICIALLY_SUPPORTED_ISO_LANGUAGES, WEB_TO_ISO_LANGUAGES
import mc_unittest


PATH_END = os.path.join('src-test', 'rogerthat_tests', 'sourcechecks')

class Test(mc_unittest.TestCase):

    def get_src_dir(self):
        src_is_ok = os.path.split(__file__)[0].endswith(PATH_END)
        self.assert_(src_is_ok, 'Wrong path: %s' % os.path.split(__file__)[0])
        src_dir = os.path.normpath(os.path.join(__file__, '..', '..', '..', '..', 'src'))
        self.assert_(os.path.isdir(src_dir), "Couldn't find src dir - tried: %s" % src_dir)
        return src_dir

    def test_get_server_settings(self):
        src_dir = self.get_src_dir()
        for root, _, files in os.walk(src_dir):
            for pfile in (f for f in files if f.endswith('.py')):
                filen_name = os.path.join(root, pfile)
                with open(filen_name, 'r') as fin:
                    for i, line in enumerate(fin.readlines()):
                        self.assert_(not ('get_server_settings()' in line and line[:4] == "   " and line[:4] != "def "),
                                     "Do not use get_server_settings at module level in %s at line %s!" % (filen_name,
                                                                                                           i + 1))

    def test_python_baseclasses(self):
        if sys.platform == "win32":
            return

        import ast
        testself = self

        class MyVisitor(ast.NodeVisitor):
            def visit_ClassDef(self, node):
                baseclasses = []
                for base in node.bases:
                    if hasattr(base, 'id'):
                        parentclassname = base.id
                    elif hasattr(base, 'value') and hasattr(base.value, 'id') and hasattr(base, 'attr'):
                        parentclassname = base.value.id + '.' + base.attr
                    testself.assert_(parentclassname, "Could not interprate base class for node %s\nfile=%s" % (ast.dump(node), self.current_python_file))
                    baseclasses.append(parentclassname)
                testself.assert_(len(baseclasses) > 0, "Could not find baseclasses for node %s\nfile=%s" % (ast.dump(node), self.current_python_file))
                testself.assert_('CachedModelMixIn' not in baseclasses or baseclasses[0] == 'CachedModelMixIn', 'CachedModelMixIn MUST be first parent class!!\n--> class %s\n    file %s' % (node.name, self.current_python_file))
                ast.NodeVisitor.generic_visit(self, node)

        m = MyVisitor()
        src_dir = self.get_src_dir()
        filenames = os.popen("find ""%s"" -name '*.py'" % src_dir).read().splitlines()
        self.assert_(len(filenames) > 0, "Error: couldn't find src files.\nIs the dir correct: %s" % src_dir)

        for filename in filenames:
            if filename.endswith('rogerthat/bizz/service/mfd/gen.py'):
                continue
            f = open(filename, 'r')
            body = f.read()
            f.close()
            m.current_python_file = filename
            try:
                m.visit(ast.parse(body))
            except:
                print filename
                raise

    def test_language_dicts(self):
        for D in (OFFICIALLY_SUPPORTED_LANGUAGES, WEB_TO_ISO_LANGUAGES, OFFICIALLY_SUPPORTED_ISO_LANGUAGES):
            for (a, b) in D.iteritems():
                self.assertEqual(unicode, type(a))
                self.assertEqual(unicode, type(b))

    def test_full_languages(self):
        for s in translations.SUPPORTED_LANGUAGES:
            azzert(s in OFFICIALLY_SUPPORTED_ISO_LANGUAGES)
            azzert(get_full_language_string(s))
