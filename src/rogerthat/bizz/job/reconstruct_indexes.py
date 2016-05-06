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

from types import NoneType

from rogerthat.bizz.job import run_job
from rogerthat.utils import azzert
from google.appengine.ext import db
from mcfw.rpc import returns, arguments


def job(type_):
    run_job(get_object_keys, [type_], re_insert_model, [])

def get_object_keys(type_):
    azzert(issubclass(type_, db.Model))
    return type_.all(keys_only=True)

# used for reconstructing broken indexes
@returns(NoneType)
@arguments(key=db.Key)
def re_insert_model(key):
    def trans():
        db.put(db.get(key))
    db.run_in_transaction(trans)
