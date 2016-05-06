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

from contextlib import closing
import itertools
import json
import os
from types import NoneType

from rogerthat.utils import azzert
from google.appengine.ext import db
from mcfw.consts import MISSING
from mcfw.properties import simple_types
from mcfw.serialization import s_str, s_long, s_unicode, s_long_list, ds_str, ds_long, ds_unicode, ds_long_list, \
    CustomProperty
from mcfw.utils import chunks


MAX_BUCKET_SIZE = 900 * 1024
MAX_KEY_LENGHT = 50
MAX_STRING_PROPERTY_LENGTH = 500

try:
    from cStringIO import StringIO
    from StringIO import StringIO as _StringIO
    with closing(StringIO()) as s:
        STRING_IO_TYPES = (type(s), _StringIO)
    del s
except ImportError:
    from StringIO import StringIO
    STRING_IO_TYPES = (StringIO,)


class InvalidKeyError(Exception):
    def __init__(self, message, key=None):
        self.key = key
        super(InvalidKeyError, self).__init__(message)


class KVBucket(db.Expando):

    @property
    def id(self):
        return self.key().id()

    @classmethod
    def create_key(cls, bucket_id, parent):
        return db.Key.from_path(cls.kind(), bucket_id, parent=parent)


class KVBlobBucket(db.Model):
    data = db.BlobProperty()

    @property
    def id(self):
        return self.key().id()

    @classmethod
    def create_key(cls, blob_bucket_id, parent):
        return db.Key.from_path(cls.kind(), blob_bucket_id, parent=parent)


LOADED_FROM_DATA_STORE = 'LOADED_FROM_DATA_STORE'


class KVStore(object):

    def __init__(self, ancestor_key):
        azzert(ancestor_key == LOADED_FROM_DATA_STORE or isinstance(ancestor_key, db.Key))
        self._ancestor = ancestor_key
        self._bucket_sizes = dict()  # Holds bucket id to bucket size references { bucket_id: bucket_size }
        self._keys = dict()  # Holds key to bucket id references { key: bucket_id }
        self._blob_keys = dict()  # Holds key to bucket id list references { key: [blob_bucket_id] }
        self._loaded_buckets = dict()  # Holds bucket id to bucket references { bucket_id: bucket }
        self._to_be_deleted_models = set()  # Set with keys that need to be deleted when writing to the DS
        self._to_be_put_blob_buckets = dict()  # Blob buckets that need to be written to the DS { key: [blob_bucket] }
        self._to_be_put_buckets = set()  # Buckets that need to be written to the DS
        self._newly_added_keys = set()  # Set with keys to prevent deletion of newly added keys

    def _get_bucket(self, bucket_id):
        bucket = self._loaded_buckets.get(bucket_id, None)
        if bucket is None:
            bucket = KVBucket.get_by_id(bucket_id, self._ancestor)
            azzert(bucket is not None)
            self._loaded_buckets[bucket_id] = bucket
        return bucket

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __getitem__(self, key):
        bucket_id = self._keys.get(key, None)
        if bucket_id is not None:
            bucket = self._get_bucket(bucket_id)
            return getattr(bucket, key)

        blob_bucket_ids = self._blob_keys.get(key, None)
        if blob_bucket_ids is None:
            raise KeyError(key)

        # Try to get from memory first
        buckets = self._to_be_put_blob_buckets.get(key)
        if not buckets:
            buckets = db.get([db.Key.from_path(KVBlobBucket.kind(), blob_bucket_id, parent=self._ancestor)
                              for blob_bucket_id in blob_bucket_ids])

        stream = StringIO()
        for bucket in buckets:
            stream.write(bucket.data)
        stream.seek(0)
        return stream

    def _calculate_updated_bucket_size(self, bucket, key, new_value_size):
        original_bucket_size = self._bucket_sizes[bucket.id]
        original_value_size = _calculate_size_for_value(key, getattr(bucket, key, MISSING))
        return original_bucket_size - original_value_size + new_value_size

    def _find_existing_bucket_for_simple_value(self, key, value):
        bucket_id = self._keys.get(key, None)
        new_value_size = _calculate_size_for_value(key, value)
        if bucket_id is not None:
            bucket = self._get_bucket(bucket_id)
            updated_bucket_size = self._calculate_updated_bucket_size(bucket, key, new_value_size)
            if updated_bucket_size <= MAX_BUCKET_SIZE:
                return bucket, updated_bucket_size

            # Bucket size exceeds the MAX_BUCKET_SIZE because of this updated VALUE.
            # The key must be removed from this bucket and be put in a new/other bucket.
            delattr(bucket, key)
            self._to_be_put_buckets.add(bucket)

        # Try to find an other bucket which is already loaded (to prevent additional gets) and in which VALUE might fit.
        for other_bucket_id, other_bucket in self._loaded_buckets.iteritems():
            if other_bucket_id == bucket_id:
                continue  # We already tried this bucket

            updated_other_bucket_size = self._bucket_sizes[other_bucket_id] + new_value_size
            if updated_other_bucket_size <= MAX_BUCKET_SIZE:
                return other_bucket, updated_other_bucket_size

        # Try the bucket not yet loaded from the data_store.
        for other_bucket_id, other_bucket_size in self._bucket_sizes.iteritems():
            if other_bucket_id in self._loaded_buckets:
                continue  # We already tried this bucket

            updated_other_bucket_size = other_bucket_size + new_value_size
            if updated_other_bucket_size <= MAX_BUCKET_SIZE:
                return self._get_bucket(other_bucket_id), updated_other_bucket_size

        return None, None  # There is no bucket in which VALUE fits. We'll have to create a new bucket.

    def _set_simple_value(self, key, value):
        bucket, updated_bucket_size = self._find_existing_bucket_for_simple_value(key, value)
        if bucket:
            bucket_id = bucket.id
        else:
            # We did not find an existing bucket. Let's create a new one.
            self._newly_added_keys.add(key)
            bucket_id = self._allocate_ids(KVBucket.create_key(1, self._ancestor), 1)[0]
            bucket = KVBucket(key=KVBucket.create_key(bucket_id, self._ancestor))
            self._loaded_buckets[bucket_id] = bucket
            updated_bucket_size = _calculate_size_for_value(key, value)

        setattr(bucket, key, value)
        self._to_be_put_buckets.add(bucket)
        self._keys[key] = bucket_id
        self._bucket_sizes[bucket_id] = updated_bucket_size

    @db.non_transactional
    def _allocate_ids(self, key, count):
        return db.allocate_ids(key, count)

    def _set_blob(self, key, value):
        existing_blob_bucket_ids = self._blob_keys.get(key)
        if existing_blob_bucket_ids is not None and key not in self._to_be_put_blob_buckets:
            # We need to overwrite all these blob buckets
            self._to_be_deleted_models.update((KVBlobBucket.create_key(id_, self._ancestor)
                                               for id_ in existing_blob_bucket_ids))
        else:
            self._newly_added_keys.add(key)

        # Calculate how much blob buckets we need
        value.seek(0, os.SEEK_END)
        size = value.tell()
        value.seek(0)
        buckets_count = size / MAX_BUCKET_SIZE
        if size % MAX_BUCKET_SIZE:
            buckets_count += 1

        # Create blobs
        blob_buckets = list()
        id_range = self._allocate_ids(KVBlobBucket.create_key(1, self._ancestor), buckets_count)
        blob_bucket_ids = range(id_range[0], id_range[1] + 1)
        for blob_bucket_id in blob_bucket_ids:
            blob_buckets.append(KVBlobBucket(key=KVBlobBucket.create_key(blob_bucket_id, self._ancestor),
                                             data=db.Blob(value.read(MAX_BUCKET_SIZE))))
        self._to_be_put_blob_buckets[key] = blob_buckets
        self._blob_keys[key] = blob_bucket_ids

    @staticmethod
    def _validate_types(simple_type_list):
        # allow None in str/unicode list
        # allow int/long in long/int list
        types = set()
        for v in simple_type_list:
            if isinstance(v, int):
                types.add(long)
            else:
                types.add(type(v))
        l = len(types)
        if l < 2:
            return True
        elif l == 2:
            return NoneType in types and (unicode in types or str in types)
        else:
            return False

    @staticmethod
    def _is_simple_type(value):
        if isinstance(value, basestring) and len(value) > MAX_STRING_PROPERTY_LENGTH:
            return False
        if type(value) in simple_types:
            return True
        if isinstance(value, list) and all(type(v) in simple_types for v in value) and KVStore._validate_types(value):
            return True
        return False

    def __setitem__(self, key, value):
        azzert(db.is_in_transaction())
        azzert(isinstance(key, unicode) and len(key) <= MAX_KEY_LENGHT)

        if key in self._keys:
            existing_type = 'simple'
        elif key in self._blob_keys:
            existing_type = 'blob'
        else:
            existing_type = 'new'

        # check the type of value. if StringIO then BlobBucket, else Bucket
        if isinstance(value, STRING_IO_TYPES):
            if existing_type == 'simple':
                del self[key]
            self._set_blob(key, value)
        else:
            # If value is a str or unicode, check if the length is less than MAX_STRING_PROPERTY_LENGTH
            azzert(not isinstance(value, basestring) or len(value) <= MAX_STRING_PROPERTY_LENGTH)
            azzert(self._is_simple_type(value))
            if key.startswith('_'):  # db.Expando doesn't save properties starting with an underscore
                raise InvalidKeyError('Invalid key: %s' % key, key)
            if existing_type == 'blob':
                del self[key]
            self._set_simple_value(key, value)

    def iterkeys(self):
        return itertools.chain(self._keys, self._blob_keys)

    def keys(self):
        return list(self.iterkeys())

    def has_key(self, key):
        return key in self._keys or key in self._blob_keys

    __contains__ = has_key

    def clear(self):
        azzert(db.is_in_transaction())
        self._to_be_put_blob_buckets.clear()
        self._to_be_put_buckets.clear()
        self._to_be_deleted_models.update(KVBucket.create_key(i, self._ancestor)
                                          for i in self._keys.itervalues())
        for blob_bucket_ids in self._blob_keys.itervalues():
            self._to_be_deleted_models.update(KVBlobBucket.create_key(i, self._ancestor)
                                              for i in blob_bucket_ids)
        self._keys.clear()
        self._blob_keys.clear()
        self._bucket_sizes.clear()
        self._loaded_buckets.clear()
        self._newly_added_keys.clear()

    def __delitem__(self, key):
        azzert(db.is_in_transaction())
        if key in self._newly_added_keys:
            raise ValueError('Hey! Make up your mind!')

        bucket_id = self._keys.get(key, None)
        if bucket_id is not None:
            bucket = self._get_bucket(bucket_id)
            # Check if this was the last key in this bucket
            if len(bucket.dynamic_properties()) == 1:
                try:
                    self._to_be_put_buckets.remove(bucket)
                except KeyError:
                    pass
                self._to_be_deleted_models.add(bucket.key())
                del self._bucket_sizes[bucket_id]
            else:
                value = getattr(bucket, key)
                value_size = _calculate_size_for_value(key, value)
                self._bucket_sizes[bucket_id] -= value_size
                delattr(bucket, key)
                self._to_be_put_buckets.add(bucket)
            del self._keys[key]
            return

        blob_bucket_ids = self._blob_keys.get(key, None)
        if blob_bucket_ids is not None:
            try:
                del self._to_be_put_blob_buckets[key]
            except KeyError:
                pass
            self._to_be_deleted_models.update((KVBlobBucket.create_key(id_, self._ancestor)
                                               for id_ in blob_bucket_ids))
            del self._blob_keys[key]
            return

        raise KeyError(key)

    def from_json_dict(self, json_dict, remove_none_values=False):
        for key, value in json_dict.iteritems():
            if isinstance(key, str):
                key = key.decode('utf-8')
            if remove_none_values and value is None:
                try:
                    del self[key]
                except KeyError:
                    pass
            else:
                if self._is_simple_type(value):
                    self[key] = value
                else:
                    # value is a LIST or a DICT
                    with closing(StringIO()) as stream:
                        json.dump(value, stream)
                        self[key] = stream

        # remove keys which are in self, but not in json_dict
        for to_be_deleted_key in set(json_dict.keys()) - set(self.iterkeys()):
            try:
                del self[to_be_deleted_key]
            except KeyError:
                pass

    def to_json_dict(self):
        d = dict()
        for k in self._keys:
            d[k] = self[k]
        for k in self._blob_keys:
            d[k] = json.load(self[k])
        return d


class KeyValueProperty(db.UnindexedProperty, CustomProperty):
    # Tell what the user type is.
    data_type = KVStore

    # For writing to datastore.
    def get_value_for_datastore(self, model_instance):
        kv_store = super(KeyValueProperty, self).get_value_for_datastore(model_instance)
        if kv_store is not None:
            for chunk in chunks(list(kv_store._to_be_deleted_models), 200):
                db.delete(chunk)
            to_be_put_models = set(kv_store._to_be_put_buckets)
            for blob_buckets in kv_store._to_be_put_blob_buckets.itervalues():
                to_be_put_models.update(blob_buckets)
            for chunk in chunks(list(to_be_put_models), 200):
                db.put(chunk)

        stream = StringIO()
        _serialize_kv_store(stream, kv_store)
        return db.Blob(stream.getvalue())

    # For reading from datastore.
    def make_value_from_datastore(self, value):
        if value is None:
            return None
        return _deserialize_kv_store(StringIO(value))

    def validate(self, value):
        if value is not None and not isinstance(value, KVStore):
            raise ValueError('Property %s must be convertible to a KVStore instance (%s)' % (self.name, value))
        return super(KeyValueProperty, self).validate(value)

    def empty(self, value):
        return not value

    def get_deserializer(self):
        return _deserialize_kv_store

    def get_serializer(self):
        return _serialize_kv_store


TYPE_SIZE_CALCULATORS = {int: lambda v: 8,
                         long: lambda v: 8,
                         float: lambda v: 8,
                         bool: lambda v: 1,
                         NoneType: lambda v: 1,
                         str: lambda v: len(v) + 8,
                         unicode: lambda v: len(v.encode('utf-8')) + 8
                         }


def _calculate_size_for_value(key, value):
    if value is MISSING:
        return 0
    size = len(key)
    if isinstance(value, list):
        size += 8
        size += sum(TYPE_SIZE_CALCULATORS[type(v)](v) for v in value)
    else:
        size += TYPE_SIZE_CALCULATORS[type(value)](value)
    return size


def _serialize_dict(stream, d, key_serializer, value_serializer):
    s_long(stream, len(d))
    for k, v in d.iteritems():
        key_serializer(stream, k)
        value_serializer(stream, v)


def _deserialize_dict(stream, key_deserializer, value_deserializer):
    d = dict()
    size = ds_long(stream)
    for _ in xrange(size):
        k = key_deserializer(stream)
        d[k] = value_deserializer(stream)
    return d


def _serialize_kv_store(stream, kv_store):
    azzert(kv_store is None or isinstance(kv_store._ancestor, db.Key))
    s_long(stream, 1)  # version
    if kv_store:
        s_str(stream, str(kv_store._ancestor))
        _serialize_dict(stream, kv_store._bucket_sizes, s_long, s_long)
        _serialize_dict(stream, kv_store._keys, s_unicode, s_long)
        _serialize_dict(stream, kv_store._blob_keys, s_unicode, s_long_list)
    else:
        s_str(stream, None)


def _deserialize_kv_store(stream):
    ds_long(stream)  # version
    ancestor_key = ds_str(stream)
    if ancestor_key is None:
        return None
    kv_store = KVStore(db.Key(ancestor_key))
    kv_store._bucket_sizes = _deserialize_dict(stream, ds_long, ds_long)
    kv_store._keys = _deserialize_dict(stream, ds_unicode, ds_long)
    kv_store._blob_keys = _deserialize_dict(stream, ds_unicode, ds_long_list)
    return kv_store
