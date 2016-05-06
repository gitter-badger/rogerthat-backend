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

from google.appengine.ext import db, deferred


def update_index(model_name, cursor=None):
    query = db.GqlQuery("SELECT __key__ FROM %s" % model_name)
    query.with_cursor(cursor)

    keys = query.fetch(10)
    for key in keys:
        def trans():
            obj = db.get(key)
            obj.put()
        db.run_in_transaction(trans)

    if len(keys) > 0:
        deferred.defer(update_index, model_name, query.cursor())
