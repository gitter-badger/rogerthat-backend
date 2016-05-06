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
from rogerthat.utils import foreach, azzert
from google.appengine.ext import db
from mcfw.cache import cached, CachedModelMixIn
from mcfw.rpc import returns, arguments


@returns(db.Key)
@arguments(user=users.User, solution=unicode)
def parent_key(user, solution=u'mc-tracker'):
    azzert('/' not in user.email(), 'Cannot create parent_key (/) for %s' % user.email())
    return parent_key_unsafe(user, solution)

@cached(1, memcache=False)
@returns(db.Key)
@arguments(user=users.User, solution=unicode)
def parent_key_unsafe(user, solution=u'mc-tracker'):
    return db.Key.from_path(solution, user.email())

@cached(1, memcache=False)
@returns(db.Key)
@arguments()
def system_parent_key():
    return db.Key.from_path(u'mc-tracker', 'system')

def generator(iterator):
    return (o for o in iterator)

def put_and_invalidate_cache(*models):
    db.put(models)
    foreach(lambda m: m.invalidateCache(), (m for m in models if isinstance(m, CachedModelMixIn)))
