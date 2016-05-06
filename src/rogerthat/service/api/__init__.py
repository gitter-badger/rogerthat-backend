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

from google.appengine.ext import webapp
from mcfw.rpc import arguments, returns


DIR = os.path.dirname(__file__)

@returns(str)
@arguments(version=int)
def get_schema_path(version):
    return os.path.join(DIR, 'MessageFlow.%s.xsd' % version)

@returns(str)
@arguments(version=int)
def get_schema(version):
    path = get_schema_path(version)
    return file(path).read();

class XMLSchemaHandler(webapp.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'text/xml'
        self.response.headers['Content-disposition'] = 'attachment; filename=MessageFlow.xsd';
        self.response.out.write(get_schema(int(1)))
