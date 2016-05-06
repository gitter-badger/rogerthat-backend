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

from rogerthat.rpc import users
from google.appengine.ext import db
from mcfw.properties import unicode_property, long_property, bool_property
from mcfw.serialization import s_unicode, s_long, s_bool, ds_unicode, ds_bool, \
    get_list_serializer, get_list_deserializer, ds_long


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

class BaseFriendDetail(object):
    TYPE_USER = 1
    TYPE_SERVICE = 2

    email = unicode_property('1')
    name = unicode_property('2')
    avatarId = long_property('3')
    shareLocation = bool_property('4')
    sharesLocation = bool_property('5')
    sharesContacts = bool_property('6')
    type = long_property('7')  #@ReservedAssignment
    hasUserData = bool_property('8', default=False)


class FriendDetail(BaseFriendDetail):
    relationVersion = long_property('51', default=0, doc="bumped when data related to the friend relation is updated. "
                                    "Eg. location sharing, broadcast settings, user data.")

    @property
    def isService(self):
        return self.type == FriendDetail.TYPE_SERVICE

    def __hash__(self):
        return hash("%s%s%s%s%s" % (self.email, self.name, self.avatarId, self.shareLocation, self.sharesLocation, \
                                    self.sharesContacts, self.type))

    def __eq__(self, other):
        if not other or not isinstance(other, FriendDetail):
            return False
        return self.email == other.email \
            and self.name == other.name \
            and self.avatarId == other.avatarId \
            and self.shareLocation == other.shareLocation \
            and self.sharesLocation == other.sharesLocation \
            and self.type == other.type \
            and self.hasUserData == other.hasUserData \
            and self.relationVersion == other.relationVersion


def _serialize_friend_detail(stream, fd):
    s_unicode(stream, fd.email)
    s_unicode(stream, fd.name)
    s_long(stream, fd.avatarId)
    s_bool(stream, fd.shareLocation)
    s_bool(stream, fd.sharesLocation)
    s_bool(stream, fd.sharesContacts)
    s_long(stream, fd.type)
    s_bool(stream, fd.hasUserData)
    s_long(stream, fd.relationVersion)

def _deserialize_friend_detail(stream, version):
    fd = FriendDetail()
    fd.email = ds_unicode(stream)
    fd.name = ds_unicode(stream)
    fd.avatarId = ds_long(stream)
    fd.shareLocation = ds_bool(stream)
    fd.sharesLocation = ds_bool(stream)
    fd.sharesContacts = ds_bool(stream)
    if version == 1:
        from rogerthat.dal.profile import is_service_identity_user
        is_svc = is_service_identity_user(users.User(fd.email))
        fd.type = FriendDetail.TYPE_SERVICE if is_svc else FriendDetail.TYPE_USER
    else:
        fd.type = ds_long(stream)
    fd.hasUserData = False if version < 3 else ds_bool(stream)
    fd.relationVersion = 0 if version < 4 else ds_long(stream)
    return fd

_serialize_friend_detail_list = get_list_serializer(_serialize_friend_detail)
_deserialize_friend_detail_list = get_list_deserializer(_deserialize_friend_detail, True)


class FriendDetails(object):

    def __init__(self):
        self._table = dict()

    def append(self, fd):
        if not fd or not isinstance(fd, FriendDetail):
            raise ValueError
        self._table[fd.email] = fd

    def addNew(self, user, name, avatarId, shareLocation=False, sharesLocation=False, sharesContacts=True,
               type_=FriendDetail.TYPE_USER, hasUserData=False):
        from rogerthat.utils.service import remove_slash_default
        fd = FriendDetail()
        fd.email = remove_slash_default(user, warn=True).email()
        fd.name = name
        fd.avatarId = avatarId
        fd.shareLocation = shareLocation
        fd.sharesLocation = sharesLocation
        fd.sharesContacts = sharesContacts
        fd.type = type_
        fd.hasUserData = hasUserData
        fd.relationVersion = 0
        self.append(fd)
        return fd

    def remove(self, email):
        self._table.pop(email, None)

    def __iter__(self):
        for val in self._table.values():
            yield val

    def __getitem__(self, key):
        return self._table[key]

    def __contains__(self, key):
        return key in self._table

    def values(self):
        return self._table.values()

CURRENT_FRIENDMAP_VERSION = 4
def _serialize_friend_details(stream, fds):
    s_long(stream, CURRENT_FRIENDMAP_VERSION)  # version in case we need to adjust the friendmap structure
    _serialize_friend_detail_list(stream, fds.values())

def _deserialize_friend_details(stream):
    fds = FriendDetails()
    version = ds_long(stream)
    for fd in _deserialize_friend_detail_list(stream, version):
        fds.append(fd)
    return fds

class FriendDetailsProperty(db.UnindexedProperty):

    # Tell what the user type is.
    data_type = FriendDetails

    # For writing to datastore.
    def get_value_for_datastore(self, model_instance):
        stream = StringIO()
        _serialize_friend_details(stream, super(FriendDetailsProperty,
                     self).get_value_for_datastore(model_instance))
        return db.Blob(stream.getvalue())

    # For reading from datastore.
    def make_value_from_datastore(self, value):
        if value is None:
            return None
        return _deserialize_friend_details(StringIO(value))

    def validate(self, value):
        if value is not None and not isinstance(value, FriendDetails):
            raise ValueError('Property %s must be convertible '
                                'to a FriendDetails instance (%s)' %
                                (self.name, value))
        return super(FriendDetailsProperty, self).validate(value)


    def empty(self, value):
        return not value
