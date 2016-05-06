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
import logging

from rogerthat.bizz.system import delete_xmpp_account
from rogerthat.rpc.models import Mobile
from rogerthat.utils import now
from rogerthat.utils.models import delete_all
from google.appengine.ext import webapp, db


class Cleanup(webapp.RequestHandler):

    def _cleanup_mobiles(self, mobiles):
        cleanup_size = 0
        for mobile in mobiles:
            delete_xmpp_account(mobile.account , mobile.key())
            cleanup_size += 1

        return cleanup_size

    def get(self):
        now_ = now()
        yesterday = datetime.datetime.fromtimestamp(now_ - 24 * 3600)

        cleanup_size = 0
        mobiles = Mobile.all().filter("status =", Mobile.STATUS_NEW | Mobile.STATUS_ACCOUNT_CREATED).filter("timestamp <", yesterday)
        for mobile in mobiles:
            if mobile.status >= Mobile.STATUS_ACCOUNT_CREATED:
                delete_xmpp_account(mobile.account , mobile.key())
            else:
                mobile.delete()
        logging.info("Cleanup %s timedout unfinished registration Mobile records" % cleanup_size)
        mobiles = Mobile.all().filter("status =", Mobile.STATUS_NEW | Mobile.STATUS_ACCOUNT_CREATED | Mobile.STATUS_REGISTERED | Mobile.STATUS_DELETE_REQUESTED | Mobile.STATUS_UNREGISTERED)
        cleanup_size = self._cleanup_mobiles(mobiles)
        mobiles = Mobile.all().filter("status =", Mobile.STATUS_NEW | Mobile.STATUS_ACCOUNT_CREATED | Mobile.STATUS_REGISTERED | Mobile.STATUS_DELETE_REQUESTED).filter("timestamp <", yesterday)
        cleanup_size += self._cleanup_mobiles(mobiles)
        logging.info("Cleanup %s to be deleted mobile records" % cleanup_size)

class CleanupTMPBlobs(webapp.RequestHandler):

    def get(self):
        qry = db.GqlQuery("SELECT __key__ FROM TempBlob WHERE timeout < :epoch")
        qry.bind(epoch=now())
        cleanup_size = delete_all(qry)
        logging.info("CleanupTMPBlobs len(%s)", cleanup_size)
