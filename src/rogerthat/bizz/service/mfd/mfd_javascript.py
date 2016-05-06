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

import base64
import json
import os

import slimit
from google.appengine.ext.webapp import template

from rogerthat.models import Message
from rogerthat.rpc import users
from mcfw.rpc import returns, arguments


with open(os.path.join(os.path.dirname(__file__), 'js_mfr_code.js'), 'r') as f:
    JS_MFR_CODE = f.read()

template.register_template_library('rogerthat.templates.filter')

def xpath_pick_first(obj, xpath_query):
    value = obj.xpath(xpath_query)
    if len(value) == 0:
        return None
    return value[0]

class dynobject(object):
    pass

def get_mfd_id(objid):
    return unicode(json.loads(base64.decodestring(objid[7:]))['mfd']) if objid.startswith('base64:') else None

def to_bool(s):
    if s is None:
        return None
    return s == 'true'

def to_float(s):
    if s is None:
        return None
    return float(s)

def to_long(s):
    if s is None:
        return None
    return long(s)

def to_unicode(s):
    if s is None:
        return None
    return unicode(s)

VIBRATION_ALERT_TYPES = {
    True: Message.ALERT_FLAG_VIBRATE,
    False: 0
}

ALERT_TYPES = {
    'BEEP' : 0,
    'SILENT' : Message.ALERT_FLAG_SILENT,
    'RING_5' : Message.ALERT_FLAG_RING_5,
    'RING_15' : Message.ALERT_FLAG_RING_15,
    'RING_30' : Message.ALERT_FLAG_RING_30,
    'RING_60' : Message.ALERT_FLAG_RING_60
}

ALERT_INTERVAL_TYPES = {
    'NONE' : 0,
    'INTERVAL_5' : Message.ALERT_FLAG_INTERVAL_5,
    'INTERVAL_15' : Message.ALERT_FLAG_INTERVAL_15,
    'INTERVAL_30' : Message.ALERT_FLAG_INTERVAL_30,
    'INTERVAL_60' : Message.ALERT_FLAG_INTERVAL_60,
    'INTERVAL_300' : Message.ALERT_FLAG_INTERVAL_300,
    'INTERVAL_900' : Message.ALERT_FLAG_INTERVAL_900,
    'INTERVAL_3600' : Message.ALERT_FLAG_INTERVAL_3600,
}

def to_alert_flags(vibrate, alert_type, alert_interval_type):
    return VIBRATION_ALERT_TYPES[vibrate] | ALERT_TYPES[alert_type] | ALERT_INTERVAL_TYPES[alert_interval_type]

def to_message_flags(allow_dismiss, auto_lock):
    flags = Message.FLAG_SENT_BY_JS_MFR
    if allow_dismiss:
        flags |= Message.FLAG_ALLOW_DISMISS
    if auto_lock:
        flags |= Message.FLAG_AUTO_LOCK
    return flags

@returns(dict)
@arguments(flow_xml=unicode)
def parse_flow_xml(flow_xml):
    import logging
    logging.debug(flow_xml)

    # xml must be a <str> to be able to be parsed
    if isinstance(flow_xml, unicode):
        flow_xml = flow_xml.encode('utf-8')

    parsed_flows = dict()
    if 'messageFlowDefinitionSet' in flow_xml:
        from rogerthat.bizz.service.mfd import parse_message_flow_definition_set_xml
        mf_defs = parse_message_flow_definition_set_xml(flow_xml)
        for mf_def in mf_defs.definition:
            parsed_flows[to_unicode(mf_def.language)] = mf_def
    else:
        from rogerthat.bizz.service.mfd import parse_message_flow_definition_xml
        mf_def = parse_message_flow_definition_xml(flow_xml)
        parsed_flows[to_unicode(mf_def.language)] = mf_def

    return parsed_flows

@returns(dict)
@arguments(service_user=users.User, flow_xml=unicode, context=unicode, parent_message_key=unicode, must_validate=bool)
def _render_flow_definitions(service_user, flow_xml, context=None, parent_message_key=None, must_validate=False):
    output = dict()
    for lang, mf_def in parse_flow_xml(flow_xml).iteritems():
        if must_validate:
            from rogerthat.bizz.service.mfd import validate_message_flow_definition
            validate_message_flow_definition(mf_def, service_user, True)

        tmpl = os.path.join(os.path.dirname(__file__), 'mfr_template.tmpl')
        branding_hashes = set()
        attachemnt_urls = set()
        for m in (mf_def.message + mf_def.formMessage):
            if m.brandingKey:
                branding_hashes.add(to_unicode(m.brandingKey))
            for a in m.attachment:
                attachemnt_urls.add(to_unicode(a.url))

        output[lang] = (template.render(tmpl, dict(f=mf_def, context=context, parent_message_key=parent_message_key)),
                        list(branding_hashes),
                        list(attachemnt_urls))
    return output

def _get_js_mfr_code(js_def, minify=True):
    if minify:
        return slimit.minify(JS_MFR_CODE + js_def, mangle=True, mangle_toplevel=False)  # @UndefinedVariable
    else:
        return JS_MFR_CODE + js_def

@returns(dict)
@arguments(service_user=users.User, flow_xml=unicode, context=unicode, minify=bool, parent_message_key=unicode,
           must_validate=bool)
def generate_js_flow(service_user, flow_xml, context=None, minify=False, parent_message_key=None, must_validate=False):
    output = dict()
    for lang, (js_def, brandings, attachment_urls) \
            in _render_flow_definitions(service_user, flow_xml, context, parent_message_key, must_validate).iteritems():
        tmpl = os.path.join(os.path.dirname(__file__), 'static_flow.html.tmpl')
        js_mfr_code = _get_js_mfr_code(js_def, minify)
        output[lang] = (template.render(tmpl, {'js_mfr_code': js_mfr_code}), brandings, attachment_urls)
    return output
