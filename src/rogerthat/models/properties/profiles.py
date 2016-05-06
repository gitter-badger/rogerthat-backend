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
from mcfw.properties import unicode_property, long_property
from mcfw.serialization import s_long, ds_long, s_unicode, ds_unicode, get_list_serializer, get_list_deserializer, \
    s_bool, ds_bool, CustomProperty


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

class MobileDetail(object):
    account = unicode_property('1')
    type_ = long_property('2')
    pushId = unicode_property('3')  # Apple Push or Google Cloud Messaging id
    app_id = unicode_property('4')

def _serialize_mobile_detail(stream, md):
    s_unicode(stream, md.account)
    s_long(stream, md.type_)
    s_unicode(stream, md.pushId)
    s_unicode(stream, md.app_id)

def _deserialize_mobile_detail(stream, version):
    from rogerthat.models import App
    md = MobileDetail()
    md.account = ds_unicode(stream)
    md.type_ = ds_long(stream)
    md.pushId = ds_unicode(stream)
    if version < 2:
        md.app_id = App.APP_ID_ROGERTHAT
    else:
        md.app_id = ds_unicode(stream)
    return md

_serialize_mobile_detail_list = get_list_serializer(_serialize_mobile_detail)
_deserialize_mobile_detail_list = get_list_deserializer(_deserialize_mobile_detail, True)

class MobileDetails(object):

    def __init__(self):
        self._table = dict()

    def append(self, md):
        if not md or not isinstance(md, MobileDetail):
            raise ValueError
        self._table[md.account] = md
        return md

    def addNew(self, account, type_, pushId, app_id):
        md = MobileDetail()
        md.account = account
        md.type_ = type_
        md.pushId = pushId
        md.app_id = app_id
        self.append(md)
        return md

    def remove(self, account):
        self._table.pop(account, None)

    def __iter__(self):
        for val in self._table.values():
            yield val

    def __getitem__(self, key):
        return self._table[key]

    def __contains__(self, key):
        return key in self._table

    def __len__(self):
        return len(self._table)

    def values(self):
        return self._table.values()

CURRENT_MOBILE_DETAILS_VERSION = 2
def _serialize_mobile_details(stream, fds):
    s_long(stream, CURRENT_MOBILE_DETAILS_VERSION)  # version in case we need to adjust the MobileDetail structure
    if fds is None:
        s_bool(stream, False)
    else:
        s_bool(stream, True)
        _serialize_mobile_detail_list(stream, fds.values())

def _deserialize_mobile_details(stream):
    version = ds_long(stream)
    if ds_bool(stream):
        mds = MobileDetails()
        for md in _deserialize_mobile_detail_list(stream, version):
            mds.append(md)
        return mds
    else:
        return None

class MobileDetailsProperty(db.UnindexedProperty, CustomProperty):
    get_serializer = lambda self: _serialize_mobile_details
    get_deserializer = lambda self: _deserialize_mobile_details

    # Tell what the user type is.
    data_type = MobileDetails

    # For writing to datastore.
    def get_value_for_datastore(self, model_instance):
        stream = StringIO()
        _serialize_mobile_details(stream, super(MobileDetailsProperty,
                     self).get_value_for_datastore(model_instance))
        return db.Blob(stream.getvalue())

    # For reading from datastore.
    def make_value_from_datastore(self, value):
        if value is None:
            return None
        return _deserialize_mobile_details(StringIO(value))

    def validate(self, value):
        if value is not None and not isinstance(value, MobileDetails):
            raise ValueError('Property %s must be convertible to a FriendDetails instance (%s)' % (self.name, value))
        return super(MobileDetailsProperty, self).validate(value)

    def empty(self, value):
        return not value
