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

import datetime
import time

from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile
from google.appengine.ext import db
import mc_unittest
from mcfw.serialization import serialize, deserialize, List


class Serialization(mc_unittest.TestCase):

    def test_str(self):
        original = "De kat krabt de krollen van de trap"
        serialized = deserialize(str, serialize(str, original))
        assert original == serialized
        assert deserialize(str, serialize(str, None)) is None
        assert deserialize(str, serialize(str, '')) == ''

    def test_unicode(self):
        original = u'\xe8\xb2\x93\xe8\x99\x9f\xe5\x8f\xab\xe7\xb4\x84\xe6\x9d\x9f\xe7\x9a\x84\xe6\xa8\x93\xe6\xa2\xaf'
        serialized = deserialize(unicode, serialize(unicode, original))
        assert original == serialized
        assert deserialize(unicode, serialize(unicode, None)) is None
        assert deserialize(unicode, serialize(unicode, '')) == ''

    def test_bool(self):
        assert deserialize(bool, serialize(bool, True))
        assert not deserialize(bool, serialize(bool, False))
        assert deserialize(bool, serialize(bool, None)) is None

    def test_int(self):
        assert deserialize(int, serialize(int, 345)) == 345
        assert deserialize(int, serialize(int, -345)) == -345
        assert deserialize(int, serialize(int, None)) is None

    def test_float(self):
        assert deserialize(float, serialize(float, 3.141516)) == 3.141516
        assert deserialize(float, serialize(float, -3.141516)) == -3.141516
        assert deserialize(float, serialize(float, None)) == None

    def test_datetime(self):
        now = datetime.datetime.fromtimestamp(int(time.time()))
        assert deserialize(datetime.datetime, serialize(datetime.datetime, now)) == now
        assert deserialize(datetime.datetime, serialize(datetime.datetime, None)) == None

    def test_mobile(self):
        mobile = users.get_current_mobile()
        assert deserialize(Mobile, serialize(Mobile, mobile)).user.email() == mobile.user.email()

    def test_str_list(self):
        l = ['Geert', 'Audenaert']
        assert deserialize(List(str), serialize(List(str), l)) == l
        assert deserialize(List(str), serialize(List(str), None)) is None
        l = ['Geert', None, 'Audenaert']
        assert deserialize(List(str), serialize(List(str), l)) == l

    def test_key(self):
        key = db.Key.from_path('test', 'test')
        assert deserialize(db.Key, serialize(db.Key, key)) == key
        assert deserialize(db.Key, serialize(db.Key, None)) is None
