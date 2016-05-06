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

import StringIO
import math
import sys

from rogerthat.models.properties.keyvalue import KeyValueProperty, KVStore, KVBlobBucket, MAX_BUCKET_SIZE, KVBucket
from rogerthat.utils import now
from google.appengine.ext import db
import mc_unittest


try:
    import cStringIO
except ImportError:
    cStringIO = None


class MyTestModel(db.Model):
    data = KeyValueProperty()

    @classmethod
    def create_key(cls, id_or_name):
        return db.Key.from_path(cls.kind(), id_or_name)


class TestKVStore(mc_unittest.TestCase):

    def test_none_kvstore(self):
        self.set_datastore_hr_probability(1)

        key = MyTestModel.create_key('id_or_name')
        MyTestModel(key=key).put()
        self.assertIsNone(db.get(key).data)

    def test_simple_types(self):
        self.set_datastore_hr_probability(1)
        now_ = now()

        def _assert(data):
            self.assertEqual(1, data[u'int'])
            self.assertEqual(2, data[u'long'])
            self.assertEqual(3.4, data[u'float'])
            self.assertEqual(True, data[u'bool'])
            self.assertEqual(None, data[u'None'])
            self.assertEqual('str', data[u'str'])
            self.assertEqual(u'ünîcødé', data[u'unicode'])
            self.assertListEqual([], data[u'empty_list'])
            self.assertListEqual([1, 2, 3, 0, -5], data[u'int_list'])
            self.assertListEqual([1L, 1234567890L, 1000000L * now_], data[u'long_list'])
            self.assertListEqual([1.0, 1.1, 1.2, 1.3, sys.float_info.max], data[u'float_list'])
            self.assertListEqual([True, False, True, True], data[u'bool_list'])
            self.assertListEqual(['a', 'b', 'c', None], data[u'str_list'])
            self.assertListEqual([u'ünîcødé', u'blabla', u'123-élève', None], data[u'unicode_list'])
            self.assertTrue({u'int',
                             u'long',
                             u'float',
                             u'bool',
                             u'None',
                             u'str',
                             u'unicode',
                             u'empty_list',
                             u'int_list',
                             u'long_list',
                             u'float_list',
                             u'bool_list',
                             u'str_list',
                             u'unicode_list'}.issuperset(data.keys()))


        def trans():
            model = MyTestModel(key=MyTestModel.create_key('id_or_name'))
            model.data = KVStore(model.key())
            model.data[u'int'] = 1
            model.data[u'long'] = 2
            model.data[u'float'] = 3.4
            model.data[u'bool'] = True
            model.data[u'None'] = None
            model.data[u'str'] = 'str'
            model.data[u'unicode'] = u'ünîcødé'
            model.data[u'empty_list'] = []
            model.data[u'int_list'] = [1, 2, 3, 0, -5]
            model.data[u'long_list'] = [1L, 1234567890L, 1000000L * now_]
            model.data[u'float_list'] = [1.0, 1.1, 1.2, 1.3, sys.float_info.max]
            model.data[u'bool_list'] = [True, False, True, True]
            model.data[u'str_list'] = ['a', 'b', 'c', None]
            model.data[u'unicode_list'] = [u'ünîcødé', u'blabla', u'123-élève', None]
            with self.assertRaises(AssertionError):
                model.data[u'mixed-list'] = [1, '1', True]
            with self.assertRaises(AssertionError):
                model.data[u'mixed-list'] = [1, '1']
            with self.assertRaises(AssertionError):
                model.data[u'mixed-list'] = [u'1', '1']

            _assert(model.data)
            model.put()
            _assert(model.data)
            return model

        model = db.run_in_transaction(trans)
        _assert(model.data)

        with self.assertRaises(AssertionError):
            # must be in transaction
            model.data[u'int'] = 1

        self.assertRaises(KeyError, lambda: model.data['not-existing-key'])

        model = db.get(model.key())
        _assert(model.data)

        def trans_del():
            model.data.clear()
            model.put()
            with self.assertRaises(KeyError):
                del model.data['int']

        db.run_in_transaction(trans_del)
        self.assertEqual(0, KVBucket.all().count())
        self.assertEqual(0, KVBlobBucket.all().count())

    def test_big_simple_store(self):
        self.set_datastore_hr_probability(1)

        key = MyTestModel.create_key('big brother')
        value = 50 * u"0123456789"
        def trans():
            model = MyTestModel(key=key)
            model.data = KVStore(model.key())
            for x in xrange(3000):
                model.data[u'prop' + str(x)] = value
            model.put()

        db.run_in_transaction(trans)

        bucket_count = KVBucket.all().count()
        self.assertGreater(bucket_count, 1)

        def trans_update():
            model = db.get(key)
            self.assertEquals(value, model.data[u'prop2999'])
            model.data[u'prop1564'] = 1564
            model.data[u'prop2'] = 2
            model.data[u'prop754'] = 754
            model.put()

        db.run_in_transaction(trans_update)
        model = db.get(key)
        self.assertEqual(bucket_count, KVBucket.all().count())
        self.assertEqual(1564, model.data[u'prop1564'])
        self.assertEqual(2, model.data[u'prop2'])
        self.assertEqual(754, model.data[u'prop754'])

    def test_blob_type_with_cStringIO(self):
        if cStringIO:
            self._test_blob_type(cStringIO.StringIO)

    def test_blob_type_with_StringIO(self):
        self._test_blob_type(StringIO.StringIO)

    def test_blob_type_with_large_blob(self):
        self._test_blob_type(StringIO.StringIO, 1000)

    def _test_blob_type(self, string_io_cls, multiplier=1):
        self.set_datastore_hr_probability(1)

        stream = string_io_cls()
        with open(__file__, 'r') as f:
            file_content = f.read()
        stream_size = 0.0
        for _ in xrange(multiplier):
            stream.write(file_content)
            stream_size += len(file_content)

        total_bucket_count = int(math.ceil(stream_size / MAX_BUCKET_SIZE))

        def _assert(data):
            stream = data[u'stream']
            self.assertEqual(multiplier * file_content, stream.getvalue())
            self.assertListEqual([u'stream'], data.keys())

        key = MyTestModel.create_key('id_or_name')
        def trans_create():
            model = db.get(key) or MyTestModel(key=key)
            if not model.data:
                model.data = KVStore(model.key())
            model.data[u'stream'] = stream
            _assert(model.data)
            model.put()
            _assert(model.data)
            return model

        model = db.run_in_transaction(trans_create)
        _assert(model.data)

        with self.assertRaises(AssertionError):
            # must be in transaction
            stream.seek(0)
            model.data[u'stream'] = stream

        self.assertRaises(KeyError, lambda: model.data['not-existing-key'])

        model = db.get(model.key())
        _assert(model.data)

        self.assertEqual(total_bucket_count, KVBlobBucket.all().count(None))

        model = db.run_in_transaction(trans_create)
        self.assertEqual(total_bucket_count, KVBlobBucket.all().count(None))

        with self.assertRaises(AssertionError):
            # must be in transaction
            del model.data[u'stream']

        def trans_del():
            del model.data[u'stream']
            self.assertRaises(KeyError, lambda: model.data[u'stream'])
            model.put()
            self.assertRaises(KeyError, lambda: model.data[u'stream'])

        db.run_in_transaction(trans_del)
        self.assertEqual(0, KVBlobBucket.all().count(None))

        self.assertRaises(KeyError, lambda: model.data[u'stream'])

        db.run_in_transaction(trans_create)
        def trans_update():
            model = db.get(key)
            stream = string_io_cls()
            stream.write(file_content)
            model.data[u'stream'] = stream
            model.put()
            return model

        model = db.run_in_transaction(trans_update)
        self.assertEqual(file_content, model.data[u'stream'].getvalue())
        self.assertEqual(1, KVBlobBucket.all().count(None))

        def trans_clear():
            model = db.get(key)
            model.data.clear()
            model.put()
        db.run_in_transaction(trans_clear)
        self.assertEqual(0, KVBucket.all().count(None))
        self.assertEqual(0, KVBlobBucket.all().count(None))

    def test_changing_type(self):
        self.set_datastore_hr_probability(1)

        stream = StringIO.StringIO()
        stream.write('testen he pol')

        key = MyTestModel.create_key('id_or_name')
        def trans1():
            model = db.get(key) or MyTestModel(key=key)
            if not model.data:
                model.data = KVStore(model.key())
            model.data[u'akey'] = stream
            with self.assertRaises(ValueError):
                model.data[u'akey'] = 1
            model.put()

        db.run_in_transaction(trans1)
        model = db.get(key)
        self.assertIsNotNone(model.data[u'akey'])
        self.assertEqual(1, KVBlobBucket.all().count())
        self.assertEqual(0, KVBucket.all().count())

        def trans2():
            model = db.get(key)
            model.data[u'akey'] = 2
            model.put()

        db.run_in_transaction(trans2)
        model = db.get(key)

        self.assertEqual(2, model.data[u'akey'])
        self.assertEqual(0, KVBlobBucket.all().count())
        self.assertEqual(1, KVBucket.all().count())

    def test_iterkeys(self):
        self.set_datastore_hr_probability(1)

        stream = StringIO.StringIO()
        stream.write('testen he pol')

        def _assert(data):
            self.assertTrue({u'stream', u'int'}.issuperset(data.keys()))
            self.assertTrue(data.has_key(u'stream'))
            self.assertTrue('stream' in data)
            self.assertTrue(data.has_key(u'int'))
            self.assertTrue(u'int' in data)
            self.assertFalse(data.has_key(u'non-existing-key'))
            self.assertFalse(u'non-existing-key' in data)

        key = MyTestModel.create_key('id_or_name')
        def trans1():
            model = MyTestModel(key=key)
            model.data = KVStore(key)
            model.data[u'stream'] = stream
            model.data[u'int'] = 1
            _assert(model.data)
            model.put()
            _assert(model.data)

        db.run_in_transaction(trans1)

        model = db.get(key)
        _assert(model.data)

    def test_from_and_to_json_dict(self):
        self.set_datastore_hr_probability(1)

        key = MyTestModel.create_key('id_or_name')
        MyTestModel(key=key, data=KVStore(key)).put()
        def trans1(d):
            model = MyTestModel.get(key)
            model.data.clear()
            model.data.from_json_dict(d)
            model.put()
            return model

        json_dict1 = dict(ints=[1, 2, 3],
                          long_str='a' * 2000)
        model = db.run_in_transaction(trans1, json_dict1)
        self.assertDictEqual(json_dict1, model.data.to_json_dict())

        json_dict1.update(dict(a1=[4, 5, 6],
                               b1='b1' * 5000,
                               c1='c1' * 5000))
        model = db.run_in_transaction(trans1, json_dict1)
        self.assertDictEqual(json_dict1, model.data.to_json_dict())

        json_dict1.update(dict(a2='a2' * 5000,
                               b2='b2' * 5000,
                               c2='c2' * 5000))
        model = db.run_in_transaction(trans1, json_dict1)
        self.assertDictEqual(json_dict1, model.data.to_json_dict())
