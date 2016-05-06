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

from rogerthat.utils.transactions import on_trans_committed, run_in_transaction
from google.appengine.api.datastore_errors import TransactionFailedError
from google.appengine.ext import db
import mc_unittest


class TransactionActionsCount(db.Model):
    count = db.IntegerProperty()

    @classmethod
    def create_key(cls):
        return db.Key.from_path(cls.kind(), "TransactionActionsCount")

class Test(mc_unittest.TestCase):


    def testTransactionActions(self):

        def trans():
            transActionsCount = TransactionActionsCount(key=TransactionActionsCount.create_key())
            transActionsCount.count = 0
            transActionsCount.put()
            on_trans_committed(update_count, False)
            on_trans_committed(update_count, False)
            on_trans_committed(update_count, True)
            on_trans_committed(update_count, False)
            on_trans_committed(update_count, False)

        def update_count(should_raise):
            transActionsCount = TransactionActionsCount.get(TransactionActionsCount.create_key())
            transActionsCount.count += 1
            if should_raise:
                raise TransactionFailedError()
            transActionsCount.put()

        run_in_transaction(trans)


        def check_count():
            transActionsCount = TransactionActionsCount.get(TransactionActionsCount.create_key())
            self.assertEqual(4, transActionsCount.count)
        run_in_transaction(check_count)


    def testTransactionActionsWithNestedTrans(self):

        raised = [False]  # we only want to raise 1 time

        def trans():
            transActionsCount = TransactionActionsCount(key=TransactionActionsCount.create_key())
            transActionsCount.count = 0
            transActionsCount.put()
            on_trans_committed(update_count, False)
            on_trans_committed(update_count, False)
            on_trans_committed(update_count, True)
            on_trans_committed(update_count, False)
            on_trans_committed(update_count, False)

        def update_count(should_raise):
            def inner_trans(should_raise):
                transActionsCount = TransactionActionsCount.get(TransactionActionsCount.create_key())
                transActionsCount.count += 1
                if not raised[0] and should_raise:
                    raised[0] = True
                    raise TransactionFailedError()
                transActionsCount.put()
            return run_in_transaction(inner_trans, False, should_raise)

        run_in_transaction(trans)

        def check_count():
            transActionsCount = TransactionActionsCount.get(TransactionActionsCount.create_key())
            self.assertEqual(5, transActionsCount.count)
        run_in_transaction(check_count)
