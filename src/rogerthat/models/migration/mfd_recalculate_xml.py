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
from xml.dom.minidom import parseString

from rogerthat.bizz.i18n import get_translator
from rogerthat.bizz.job import run_job
from rogerthat.bizz.service.mfd import save_message_flow, get_message_flow_design_context, message_flow_design_to_xml
from rogerthat.bizz.service.mfr import MessageFlowDesignValidationException
from rogerthat.models import MessageFlowDesign, ServiceTranslation
from google.appengine.ext import db, deferred
from mcfw.rpc import arguments


def job(cursor=None):
    query = db.GqlQuery("SELECT __key__ FROM MessageFlowDesign where status = 0 and deleted = false")
    query.with_cursor(cursor)
    keys = query.fetch(10)
    for key in keys:
        mfd_ds = db.get(key)
        if mfd_ds.status == MessageFlowDesign.STATUS_VALID:
            try:
                save_message_flow(mfd_ds.user, mfd_ds.key().name(), mfd_ds.definition, mfd_ds.language, False)
            except MessageFlowDesignValidationException:
                pass
    if keys:
        deferred.defer(job, query.cursor())

def job2():
    run_job(flows, list(), task, list())

def flows():
    return db.GqlQuery("SELECT __key__ FROM MessageFlowDesign where status = 0 and deleted = false")

@arguments(mfd_key=db.Key)
def task(mfd_key):
    mfd_ds = db.get(mfd_key)
    if mfd_ds.status == MessageFlowDesign.STATUS_VALID:
        try:
            if mfd_ds.definition:
                save_message_flow(mfd_ds.user, mfd_ds.key().name(), mfd_ds.definition, mfd_ds.language, False)
            elif mfd_ds.xml:
                # Must regenerate xml
                subflowdict = get_message_flow_design_context(mfd_ds)
                translator = get_translator(mfd_ds.user, ServiceTranslation.MFLOW_TYPES)
                definition_doc = parseString(message_flow_design_to_xml(mfd_ds.user, mfd_ds, translator, subflowdict)[0].encode('utf-8'))
                mfd_ds.xml = definition_doc.toxml('utf-8')
                mfd_ds.put()
            else:
                logging.warn("Failed to update message flow design with key: %s", mfd_key)
        except MessageFlowDesignValidationException:
            pass
