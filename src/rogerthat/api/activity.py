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

import logging

from rogerthat.rpc import users
from rogerthat.rpc.rpc import expose
from rogerthat.to.activity import LogCallRequestTO, LogCallResponseTO, LogLocationsResponseTO, LogLocationsRequestTO
from rogerthat.utils import foreach
from mcfw.rpc import returns, arguments


@expose(('api',))
@returns(LogCallResponseTO)
@arguments(request=LogCallRequestTO)
def logCall(request):
    record = request.record
    response = LogCallResponseTO()
    response.recordId = record.id
    return response

@expose(('api',))
@returns(LogLocationsResponseTO)
@arguments(request=LogLocationsRequestTO)
def logLocations(request):
    records = request.records
    from rogerthat.bizz.location import get_location, post, CannotDetermineLocationException
    user = users.get_current_user()
    mobile = users.get_current_mobile()

    def logLocation(record):
        if not record.geoPoint and not record.rawLocation:
            logging.error("Received location record without location details!\nuser = %s\nmobile = %s" \
                          % (user, mobile.id))
        else:
            try:
                geoPoint = record.geoPoint if record.geoPoint else get_location(record.rawLocation)
                post(user, geoPoint, record.timestamp, request.recipients)
            except CannotDetermineLocationException:
                pass

    foreach(logLocation, records)
