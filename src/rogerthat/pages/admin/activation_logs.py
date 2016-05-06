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

import calendar
import datetime
import os
import time

from rogerthat.dal.activation import get_activation_log
from rogerthat.utils import get_epoch_from_datetime
from dateutil.relativedelta import relativedelta
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template


class ActivationLogsHandler(webapp.RequestHandler):

    def _epoch_to_str(self, epoch):
        split = time.ctime(epoch).split(" ")
        while "" in split:
            split.remove("")
        split.remove(split[0])  # Day of week
        split.remove(split[1])  # day
        split.remove(split[1])  # timestamp
        return " ".join(split)

    def get(self):
        offset = int(self.request.GET.get("offset", 0))  # go back <offset> days in the past

        today = datetime.date.today()
        viewed_day = today - relativedelta(months=offset)
        first_day_of_viewed_month = datetime.date(viewed_day.year, viewed_day.month, 1)
        last_day_of_viewed_month = datetime.date(viewed_day.year, viewed_day.month, calendar.monthrange(viewed_day.year, viewed_day.month)[1])

        min_timestamp = get_epoch_from_datetime(first_day_of_viewed_month)
        max_timestamp = get_epoch_from_datetime(last_day_of_viewed_month)

        args = {"activations": get_activation_log(min_timestamp, max_timestamp),
                "current_day":self._epoch_to_str(min_timestamp),
                "next_url":"/mobiadmin/activation_logs?offset=%s" % (offset - 1) if offset else "",
                "back_url":"/mobiadmin/activation_logs?offset=%s" % (offset + 1)}
        path = os.path.join(os.path.dirname(__file__), 'activation_logs.html')
        self.response.out.write(template.render(path, args))
