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

from rogerthat.models.properties.forms import serialize_form_result, deserialize_form_result, \
    FormResult
from rogerthat.utils.languages import convert_iso_lang_to_web_lang
from google.appengine.ext import db
from mcfw.properties import unicode_property, long_property, bool_property, typed_property, unicode_list_property
from mcfw.serialization import s_long, s_unicode, ds_long, ds_unicode, get_list_serializer, \
    get_list_deserializer, s_bool, ds_bool, s_unicode_list, ds_unicode_list


try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

class Button(object):
    id = unicode_property('1')  # @ReservedAssignment
    index = long_property('2')
    caption = unicode_property('3')
    action = unicode_property('4')
    ui_flags = long_property('5')

def _serialize_button(stream, b):
    s_unicode(stream, b.id)
    s_long(stream, b.index)
    s_unicode(stream, b.caption)
    s_unicode(stream, b.action)
    s_long(stream, b.ui_flags)

def _deserialize_button(stream, version):
    b = Button()
    b.id = ds_unicode(stream)
    b.index = ds_long(stream)
    b.caption = ds_unicode(stream)
    b.action = ds_unicode(stream)
    b.ui_flags = ds_long(stream) if version >= 2 else 0
    return b

_serialize_button_list = get_list_serializer(_serialize_button)
_deserialize_button_list = get_list_deserializer(_deserialize_button, True)

class SpecializedList(object):

    def __init__(self):
        self._table = dict()

    def __getitem__(self, key):
        if isinstance(key, (str, unicode)):
            return self._table[key]
        elif isinstance(key, int):
            for x in self.values():
                if x.index == key:
                    return x
        raise KeyError()

    def __iter__(self):
        for b in self._table.values():
            yield b

    def __contains__(self, key):
        try:
            self[key]
            return True
        except KeyError:
            return False

    def __len__(self):
        return len(self._table)

    def values(self):
        return self._table.values()


class DuplicateButtonIdException(Exception):
    pass

class Buttons(SpecializedList):

    def add(self, button):
        if button.id in self._table:
            raise DuplicateButtonIdException()
        self._table[button.id] = button

def _serialize_buttons(stream, buttons):
    s_long(stream, 2)  # version in case we need to adjust the buttons structure
    _serialize_button_list(stream, buttons.values())

def _deserialize_buttons(stream):
    version = ds_long(stream)
    buttons = Buttons()
    for b in _deserialize_button_list(stream, version):
        buttons.add(b)
    return buttons

class ButtonsProperty(db.UnindexedProperty):

    # Tell what the user type is.
    data_type = Buttons

    # For writing to datastore.
    def get_value_for_datastore(self, model_instance):
        stream = StringIO.StringIO()
        _serialize_buttons(stream, super(ButtonsProperty, self).get_value_for_datastore(model_instance))
        return db.Blob(stream.getvalue())

    # For reading from datastore.
    def make_value_from_datastore(self, value):
        if value is None:
            return None
        return _deserialize_buttons(StringIO.StringIO(value))

    def validate(self, value):
        if value is not None and not isinstance(value, Buttons):
            raise ValueError('Property %s must be convertible to a Buttons instance (%s)' % (self.name, value))
        return super(ButtonsProperty, self).validate(value)

    def empty(self, value):
        return not value

class MemberStatus(object):
    STATUS_RECEIVED = 1
    STATUS_ACKED = 2
    STATUS_READ = 4
    STATUS_DELETED = 8
    STATUS_ACCOUNT_DELETED = 16

    status = long_property('1')
    received_timestamp = long_property('2')
    acked_timestamp = long_property('3')
    index = long_property('4')
    dismissed = bool_property('5')
    button_index = long_property('6')
    custom_reply = unicode_property('7')
    form_result = typed_property('8', FormResult, False)
    ack_device = unicode_property('9')

def _serialize_member_status(stream, r):
    s_long(stream, r.status)
    s_long(stream, r.received_timestamp)
    s_long(stream, r.acked_timestamp)
    s_long(stream, r.index)
    s_bool(stream, r.dismissed)
    s_long(stream, r.button_index)
    s_unicode(stream, r.custom_reply)
    serialize_form_result(stream, r.form_result)
    s_unicode(stream, r.ack_device)

def _deserialize_member_status(stream, version):
    r = MemberStatus()
    r.status = ds_long(stream)
    r.received_timestamp = ds_long(stream)
    r.acked_timestamp = ds_long(stream)
    r.index = ds_long(stream)
    r.dismissed = ds_bool(stream)
    r.button_index = ds_long(stream)
    r.custom_reply = ds_unicode(stream)
    r.form_result = deserialize_form_result(stream) if version >= 2 else None
    r.ack_device = ds_unicode(stream) if version >= 3 else None
    return r

_serialize_member_status_list = get_list_serializer(_serialize_member_status)
_deserialize_member_status_list = get_list_deserializer(_deserialize_member_status, True)

class DuplicateMemberIndexException(Exception):
    pass

class MemberStatuses(SpecializedList):

    def add(self, memberStatus):
        if memberStatus.index in self._table:
            raise DuplicateMemberIndexException()
        self._table[memberStatus.index] = memberStatus
        return memberStatus

def _serialize_member_statuses(stream, memberStatuses):
    s_long(stream, 3)  # version
    _serialize_member_status_list(stream, memberStatuses.values())

def _deserialize_member_statuses(stream):
    version = ds_long(stream)
    memberStatuses = MemberStatuses()
    for ms in _deserialize_member_status_list(stream, version):
        memberStatuses.add(ms)
    return memberStatuses

class MemberStatusesProperty(db.UnindexedProperty):

    # Tell what the user type is.
    data_type = MemberStatuses

    # For writing to datastore.
    def get_value_for_datastore(self, model_instance):
        stream = StringIO.StringIO()
        _serialize_member_statuses(stream, super(MemberStatusesProperty,
                     self).get_value_for_datastore(model_instance))
        return db.Blob(stream.getvalue())

    # For reading from datastore.
    def make_value_from_datastore(self, value):
        if value is None:
            return None
        return _deserialize_member_statuses(StringIO.StringIO(value))

    def validate(self, value):
        if value is not None and not isinstance(value, MemberStatuses):
            raise ValueError('Property %s must be convertible to a MemberStatuses instance (%s)' % (self.name, value))
        return super(MemberStatusesProperty, self).validate(value)

    def empty(self, value):
        return not value


class Attachment(object):
    index = long_property('1')
    content_type = unicode_property('2')
    download_url = unicode_property('3')
    size = long_property('4')
    name = unicode_property('5')


def _serialize_attachment(stream, a):
    s_long(stream, a.index)
    s_unicode(stream, a.content_type)
    s_unicode(stream, a.download_url)
    s_long(stream, a.size)
    s_unicode(stream, a.name)


def _deserialize_attachment(stream, version):
    a = Attachment()
    a.index = ds_long(stream)
    a.content_type = ds_unicode(stream)
    a.download_url = ds_unicode(stream)
    a.size = ds_long(stream)
    a.name = None if version < 2 else ds_unicode(stream)
    return a


_serialize_attachment_list = get_list_serializer(_serialize_attachment)
_deserialize_attachment_list = get_list_deserializer(_deserialize_attachment, True)


class Attachments(SpecializedList):

    def add(self, attachment):
        self._table[attachment.index] = attachment
        return attachment


def _serialize_attachments(stream, attachments):
    s_long(stream, 2)  # version
    _serialize_attachment_list(stream, [] if attachments is None else attachments.values())


def _deserialize_attachments(stream):
    version = ds_long(stream)
    attachments = Attachments()
    for a in _deserialize_attachment_list(stream, version):
        attachments.add(a)
    return attachments


class AttachmentsProperty(db.UnindexedProperty):

    # Tell what the user type is.
    data_type = Attachments

    # For writing to datastore.
    def get_value_for_datastore(self, model_instance):
        stream = StringIO.StringIO()
        _serialize_attachments(stream, super(AttachmentsProperty, self).get_value_for_datastore(model_instance))
        return db.Blob(stream.getvalue())

    # For reading from datastore.
    def make_value_from_datastore(self, value):
        if value is None:
            return None
        return _deserialize_attachments(StringIO.StringIO(value))

    def validate(self, value):
        if value is not None and not isinstance(value, Attachments):
            raise ValueError('Property %s must be convertible to a Attachments instance (%s)' % (self.name, value))
        return super(AttachmentsProperty, self).validate(value)

    def empty(self, value):
        return not value


class JsFlowDefinition(object):
    language = unicode_property('1')
    hash_ = unicode_property('2')
    definition = unicode_property('3')
    brandings = unicode_list_property('4')
    attachments = unicode_list_property('5')

class JsFlowDefinitions(SpecializedList):

    def add(self, js_flow_definition):
        self._table[js_flow_definition.language] = js_flow_definition
        return js_flow_definition

    def get_by_language(self, language):
        return self._table.get(convert_iso_lang_to_web_lang(language))

    def get_by_hash(self, static_flow_hash):
        for v in self._table.itervalues():
            if v.hash_ == static_flow_hash:
                return v
        return None

class JsFlowDefinitionsProperty(db.UnindexedProperty):

    data_type = JsFlowDefinitions

    def get_value_for_datastore(self, model_instance):
        stream = StringIO.StringIO()
        _serialize_js_flow_definitions(stream, super(JsFlowDefinitionsProperty, self).get_value_for_datastore(model_instance))
        return db.Blob(stream.getvalue())

    # For reading from datastore.
    def make_value_from_datastore(self, value):
        if value is None:
            return None
        return _deserialize_js_flow_definitions(StringIO.StringIO(value))

    def validate(self, value):
        if value is not None and not isinstance(value, JsFlowDefinitions):
            raise ValueError('Property %s must be convertible to a JsFlowDefinitions instance (%s)' % (self.name, value))
        return super(JsFlowDefinitionsProperty, self).validate(value)

    def empty(self, value):
        return not value

def _serialize_js_flow_definition(stream, jfd):
    s_unicode(stream, jfd.language)
    s_unicode(stream, jfd.hash_)
    s_unicode(stream, jfd.definition)
    s_unicode_list(stream, jfd.brandings)
    s_unicode_list(stream, jfd.attachments)

def _deserialize_js_flow_definition(stream, version):
    jfd = JsFlowDefinition()
    jfd.language = ds_unicode(stream)
    jfd.hash_ = ds_unicode(stream)
    jfd.definition = ds_unicode(stream)
    jfd.brandings = ds_unicode_list(stream) if version >= 4 else list()
    jfd.attachments = ds_unicode_list(stream) if version >= 5 else list()
    return jfd

_serialize_js_flow_definition_list = get_list_serializer(_serialize_js_flow_definition)
_deserialize_js_flow_definition_list = get_list_deserializer(_deserialize_js_flow_definition, True)

def _serialize_js_flow_definitions(stream, js_flow_definitions):
    s_long(stream, 5)  # version
    _serialize_js_flow_definition_list(stream, js_flow_definitions.values() if js_flow_definitions else list())

def _deserialize_js_flow_definitions(stream):
    version = ds_long(stream)
    js_flow_definitions = JsFlowDefinitions()
    for jfd in _deserialize_js_flow_definition_list(stream, version):
        js_flow_definitions.add(jfd)
    return js_flow_definitions
