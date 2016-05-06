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

import time
import types

from rogerthat.rpc.users import User
from google.appengine.ext import db
from mcfw.rpc import returns, arguments


class SerializerMixin(object):
    
    def to_dict(self):
        def serialize(value):
            if isinstance(value, User):
                return value.email()
            else:
                return value
        d = dict(((p, serialize(getattr(self, p))) for p in self.properties()))
        d['_id'] = self.key().id()
        return d
    
def addId(modelObj):
    modelObj.id = modelObj.key().id()
    return modelObj

@returns(int)
@arguments(qry=(db.Query, db.GqlQuery))
def delete_all(qry):
    """
    Deletes all keys which are retrieved by the passed bound Query
    
    @param qry: Bound query which returns only the keys of the objects to be deleted
    @type qry: google.appengine.ext.db.Query
    
    @return: Number of objects removed from datastore
    @rtype: int
    
    @raise ValueError: Raised when the passed qry does not returns keys
    """
    deleted_count = 0
    keys = qry.fetch(1000)
    while keys:
        if not isinstance(keys[0], db.Key):
            raise ValueError("Query is expected to return keys instead of objects")
        deleted_count += len(keys)
        db.delete(keys)
        time.sleep(1)
        keys = qry.fetch(1000)
    return deleted_count

@returns(int)
@arguments(qry=(db.Query, db.GqlQuery), function=types.FunctionType)
def run_all(qry, function):
    """
    Run all objects which are retrieved by the passed bound Query
    
    @param qry: Bound query which returns the objects to be passed as the signle argument to the passed function
    @type qry: google.appengine.ext.db.Query
    @param function: Function which will do something with a signle object retrieved by the qry
    @type function: types.FunctionType
    
    @return: Number of objects from datastore which were processed
    @rtype: int
    """
    processed_count = 0
    objects = qry.fetch(500)
    while objects:
        for o in objects:
            function(o)
            processed_count += 1
        time.sleep(1)
        objects = qry.fetch(500)
    return processed_count
