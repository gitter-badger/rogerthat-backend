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

from google.appengine.ext import db

from rogerthat.models.properties.messaging import SpecializedList
from mcfw.properties import unicode_property, bool_property, unicode_list_property, long_list_property
from mcfw.serialization import s_long, s_unicode, ds_long, get_list_serializer, get_list_deserializer, s_unicode_list, \
    ds_unicode_list, ds_unicode, s_bool, ds_bool, s_long_list, ds_long_list, \
    CustomProperty

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

class AutoConnectedService(object):
    service_identity_email = unicode_property('1')
    removable = bool_property('2')
    local = unicode_list_property('3')
    service_roles = long_list_property('4')

    @classmethod
    def create(cls, service_identity_email, removable, local, service_roles):
        to = cls()
        to.service_identity_email = service_identity_email
        to.removable = removable
        to.local = local if local else list()
        to.service_roles = service_roles if service_roles else list()
        return to

def _serialize_auto_connected_service(stream, acs):
    s_unicode(stream, acs.service_identity_email)
    s_bool(stream, acs.removable)
    s_unicode_list(stream, acs.local)
    s_long_list(stream, acs.service_roles)


def _deserialize_auto_connected_service(stream, version):
    a = AutoConnectedService()
    a.service_identity_email = ds_unicode(stream)
    a.removable = ds_bool(stream)
    a.local = ds_unicode_list(stream)
    a.service_roles = [] if version < 2 else ds_long_list(stream)
    return a


_serialize_auto_connected_service_list = get_list_serializer(_serialize_auto_connected_service)
_deserialize_auto_connected_service_list = get_list_deserializer(_deserialize_auto_connected_service, True)


class AutoConnectedServices(SpecializedList):

    def add(self, autoConnectedService):
        self._table[autoConnectedService.service_identity_email] = autoConnectedService
        return autoConnectedService

    def get(self, service_identity_email):
        return self._table[service_identity_email] if service_identity_email in self._table else None

    def remove(self, service_identity_email):
        self._table.pop(service_identity_email, 1)


def _serialize_auto_connected_services(stream, autoConnectedServices):
    s_long(stream, 2)  # version
    _serialize_auto_connected_service_list(stream, [] if autoConnectedServices is None else autoConnectedServices.values())


def _deserialize_auto_connected_services(stream):
    version = ds_long(stream)
    acs = AutoConnectedServices()
    for a in _deserialize_auto_connected_service_list(stream, version):
        acs.add(a)
    return acs


class AutoConnectedServicesProperty(db.UnindexedProperty, CustomProperty):
    get_serializer = lambda self: _serialize_auto_connected_services
    get_deserializer = lambda self: _deserialize_auto_connected_services

    # Tell what the user type is.
    data_type = AutoConnectedServices

    # For writing to datastore.
    def get_value_for_datastore(self, model_instance):
        stream = StringIO.StringIO()
        _serialize_auto_connected_services(stream, super(AutoConnectedServicesProperty, self).get_value_for_datastore(model_instance))
        return db.Blob(stream.getvalue())

    # For reading from datastore.
    def make_value_from_datastore(self, value):
        if value is None:
            return None
        return _deserialize_auto_connected_services(StringIO.StringIO(value))

    def validate(self, value):
        if value is not None and not isinstance(value, AutoConnectedServices):
            raise ValueError('Property %s must be convertible to a AutoConnectedServices instance (%s)' % (self.name, value))
        return super(AutoConnectedServicesProperty, self).validate(value)

    def empty(self, value):
        return not value
