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

import json
import new, inspect
import pprint
import time, logging
import traceback
from types import NoneType

from rogerthat.models import Code
from rogerthat.rpc import users
from rogerthat.to.explorer import CodeTO, RunResultTO
from rogerthat.utils import now, xml_escape
from google.appengine.api import xmpp
from google.appengine.ext import deferred
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments
from rogerthat.settings import get_server_settings


@rest('/mobiadmin/rest/explore/code/compile', 'post')
@returns(object)
@arguments(source=unicode, name=str)
def compile_source(source, name):
    user = users.get_current_user()
    m = new.module(str(name))
    try:
        exec source in m.__dict__
    except Exception:
        logging.warn("Compilation failed for [%s]" % name, exc_info=True)
        to = CodeTO()
        to.id = None
        to.timestamp = -1
        to.author = None
        to.name = None
        to.source = None
        to.functions = []
        to.version = -1
        to.compile_error = unicode(traceback.format_exc())
        return to

    functions = inspect.getmembers(m, lambda x: inspect.isfunction(x) and x.__module__ == m.__name__)
    code = Code().all().filter("name =", name).get()
    if not code:
        code = Code()
    code.author = user
    code.timestamp = now()
    code.name = name
    code.source = source
    code.functions = [unicode(f[0]) for f in functions]
    code.version = code.version + 1 if code.version else 1
    code.put()
    to = CodeTO.fromDBCode(code)
    to.compile_error = None
    return to

@rest('/mobiadmin/rest/explore/code/get', 'get')
@returns([CodeTO])
@arguments()
def get():
    return (CodeTO.fromDBCode(code) for code in Code.all().order('name'))

@rest('/mobiadmin/rest/explore/code/delete', 'post')
@returns(NoneType)
@arguments(codeid=(long, int))
def delete(codeid):
    Code.get_by_id(codeid).delete()

@rest('/mobiadmin/rest/explore/code/run', 'post', silent_result=True)
@returns(RunResultTO)
@arguments(codeid=(long, int), version=int, function=unicode, in_a_deferred=bool)
def run(codeid, version, function, in_a_deferred=False):
    if in_a_deferred:
        deferred.defer(_run_deferred, codeid, version, function)
        return None
    code = Code.get_by_id(codeid)
    m = new.module(str(code.name))
    exec code.source in m.__dict__
    f = getattr(m, function)
    start = time.time()
    try:
        r = f()
        runtime = time.time() - start
        rr = RunResultTO()
        rr.result = xml_escape(pprint.pformat(r).decode(errors='replace'))
        rr.succeeded = True
        rr.time = int(runtime)
        return rr
    except:
        runtime = time.time() - start
        rr = RunResultTO()
        format_exc = traceback.format_exc()
        rr.result = xml_escape(format_exc.decode(errors='replace'))
        rr.succeeded = False
        rr.time = int(runtime)
        return rr

def _run_deferred(codeid, version, function):
    code = Code.get_by_id(codeid)
    m = new.module(str(code.name))
    exec code.source in m.__dict__
    f = getattr(m, function)
    start = time.time()
    try:
        r = f()
        runtime = time.time() - start
        rr = dict(result=unicode(r), succeeded=True, time=int(runtime))
    except:
        runtime = time.time() - start
        rr = dict(result=unicode(traceback.format_exc()), succeeded=False, time=int(runtime))
    server_settings = get_server_settings()
    xmpp.send_message(server_settings.xmppInfoMembers, json.dumps(rr))
