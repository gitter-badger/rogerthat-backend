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

from google.appengine.api import users as gusers

from rogerthat.rpc import users
from rogerthat.utils import OFFLOAD_TYPE_WEB, offload
from mcfw.consts import MISSING
from mcfw.restapi import register_postcall_hook, INJECTED_FUNCTIONS
from mcfw.rpc import serialize_value, get_type_details

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'pytz'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'xlwt.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'xlrd.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'slimit-0.7.4-py2.7.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'ply-3.4-py2.7.egg'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'babel'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'icalendar-3.5.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'python-dateutil-1.5.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'qrcode.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'pydkim.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'dnspython.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'futures-2.1.6.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'html5lib-0.999.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'PyPDF2-1.33.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'reportlab-3.1.42.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'xhtml2pdf-0.0.6.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'stripe-1.19.1.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'twitter-1.17.1.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'cloudstorage.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'httplib2.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'uritemplate.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'google-api-python-client-1.4.2.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'six.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'html2text.zip'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib', 'oauth2client.zip'))

dummy = lambda: None

def log_restapi_call_result(function, success, kwargs, result_or_error):
    if function.meta['silent']:
        request_data = "****"
    else:
        kwarg_types = function.meta[u"kwarg_types"]
        request_data = dict()
        for arg, value in kwargs.iteritems():
            if arg == 'accept_missing':
                continue
            if value == MISSING:
                continue
            request_data[arg] = serialize_value(value, *get_type_details(kwarg_types[arg]), skip_missing=True)

    if function.meta['silent_result']:
        result = "****"
    elif isinstance(result_or_error, Exception):
        result = unicode(result_or_error)
    else:
        result = result_or_error
    offload(users.get_current_user() or gusers.get_current_user(), OFFLOAD_TYPE_WEB, request_data,
            result, function.meta['uri'], success)

register_postcall_hook(log_restapi_call_result)
INJECTED_FUNCTIONS.get_current_session = users.get_current_session

del log_restapi_call_result
