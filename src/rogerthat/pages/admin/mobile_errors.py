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
import os

from rogerthat.rpc.models import ClientError, MobicageError
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import template
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments


class MobileErrorHandler(webapp.RequestHandler):

    def get(self):
        cursor = self.request.get("cursor", None)
        qry = ClientError.all().order("-timestamp")
        qry.with_cursor(cursor)
        errors = qry.fetch(20)
        path = os.path.join(os.path.dirname(__file__), 'client_error.html')

        self.response.out.write(template.render(path,
            {
                'errors': errors,
                'cursor': qry.cursor() if len(errors) > 0 else None
            }))

@rest("/mobiadmin/client_errors/get_error_details", "get")
@returns(unicode)
@arguments(error_key=unicode)
def get_error_details(error_key):
    e = MobicageError.get(error_key)
    s = StringIO()
    for prop_name, prop_value in sorted(db.to_dict(e).iteritems()):
        s.write(prop_name)
        s.write(": ")
        s.write(prop_value if isinstance(prop_value, basestring) else str(prop_value))
        s.write("\n\n")
    return s.getvalue()
