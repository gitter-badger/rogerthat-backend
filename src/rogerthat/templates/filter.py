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
import time

from rogerthat.rpc.models import Mobile
from rogerthat.to import WIDGET_MAPPING
from google.appengine._internal.django.template.defaultfilters import escapejs
from google.appengine._internal.django.utils.safestring import mark_safe
from google.appengine.api import xmpp
from google.appengine.ext import webapp
from mcfw.rpc import serialize_complex_value


register = webapp.template.create_template_register()

def datestring(timestamp):
    return time.ctime(timestamp)

def elapsed(duration):
    hours = duration / 3600
    left = duration % 3600
    minutes = left / 60
    left = left % 60
    seconds = left
    return u"%s%s%ss" % ("%sh " % hours if hours else "", "%sm " % minutes if minutes else "", seconds)

def none(value):
    return "-" if value == None else value

def mobileStatus(mobile):
    if mobile.status >= Mobile.STATUS_UNREGISTERED:
        return '<span style="color: red;">delete scheduled</span>'
    elif xmpp.get_presence(mobile.account):
        return '<span style="color: green;">online</span>'
    else:
        return '<span style="color: blue;">offline</span>'

def mcjs(var):
    if var is None:
        return 'null'

    if isinstance(var, bool):
        return 'true' if var else 'false'

    if isinstance(var, (str, unicode)):
        return mark_safe(u"'%s'" % escapejs(var))

    if isinstance(var, (float, int, long)):
        return var

    raise RuntimeError('unexpected var type: %s - %s' % (var, type(var)))


def js_mfr_alert_flags(message):
    from rogerthat.bizz.service.mfd.mfd_javascript import VIBRATION_ALERT_TYPES, ALERT_TYPES, ALERT_INTERVAL_TYPES
    return mcjs(VIBRATION_ALERT_TYPES[message.vibrate] \
                | ALERT_TYPES[message.alertType] \
                | ALERT_INTERVAL_TYPES[message.alertIntervalType])


def js_mfr_flags(message):
    from rogerthat.models import Message
    flags = Message.FLAG_SENT_BY_JS_MFR
    if getattr(message, 'allowDismiss', False):
        flags |= Message.FLAG_ALLOW_DISMISS
    if message.autoLock:
        flags |= Message.FLAG_AUTO_LOCK
    return mcjs(flags)


def js_mfr_get_widget_description(form):
    for form_type, widget_descr in WIDGET_MAPPING.iteritems():
        if isinstance(form.widget, widget_descr.xml_type):
            return form_type, widget_descr
    raise Exception('Unexpected form: %s' % form)


def js_mfr_form_func(form):
    _, widget_descr = js_mfr_get_widget_description(form)
    return mcjs(widget_descr.new_form_call.func_dict['meta']['alias'])


def js_mfr_form_type(form):
    form_type, _ = js_mfr_get_widget_description(form)
    return mcjs(form_type)


def js_mfr_form_widget_json(form):
    _, widget_descr = js_mfr_get_widget_description(form)

    widgetTO = widget_descr.to_type.fromWidgetXmlSub(form.widget, replace_empty_values_by_missing=False)
    d = serialize_complex_value(widgetTO, widget_descr.to_type, False)
    return json.dumps(d)


def localize(language, key):
    from rogerthat.translations import localize as rogerthat_localize
    return rogerthat_localize(language, key)


register.simple_tag(localize)
register.filter('datestring', datestring)
register.filter('elapsed', elapsed)
register.filter('none', none)
register.filter('mobileStatus', mobileStatus)
register.filter('mcjs', mcjs)
register.filter('js_mfr_alert_flags', js_mfr_alert_flags)
register.filter('js_mfr_flags', js_mfr_flags)
register.filter('js_mfr_form_func', js_mfr_form_func)
register.filter('js_mfr_form_type', js_mfr_form_type)
register.filter('js_mfr_form_widget_json', js_mfr_form_widget_json)
