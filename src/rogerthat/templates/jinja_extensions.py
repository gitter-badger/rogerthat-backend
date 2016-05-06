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

from rogerthat.translations import localize
from jinja2 import nodes
from jinja2.ext import Extension


class TranslateExtension(Extension):
    tags = set(['translate'])

    def parse(self, parser):
        _ = parser.parse_expression()  # translate tag
        args = parser.parse_tuple()
        args = [a for a in args.iter_child_nodes()]
        return nodes.Output([self.call_method('_translate', args), ])

    def _translate(self, language, key, *args):
        try:
            kwargs = dict()
            for arg in args:
                arg_pieces = arg.split('=', 1)
                kwargs[arg_pieces[0]] = arg_pieces[1]
            translation = localize(language, key, **kwargs)
            if "_html" in kwargs:
                translation = translation.replace('\n', '<br>')
            return translation
        except:
            logging.error("Failed to translate %s" % key, exc_info=1)
            raise
