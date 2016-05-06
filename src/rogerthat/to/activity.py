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

from google.appengine.ext import db
from mcfw.properties import long_property, typed_property, unicode_property


GEO_POINT_FACTOR = 1000000.0

class GeoPointTO(object):
    latitude = long_property('1')
    longitude = long_property('2')
    accuracy = long_property('3')

    @property
    def latitude_degrees(self):
        return self.latitude / GEO_POINT_FACTOR

    @property
    def longitude_degrees(self):
        return self.longitude / GEO_POINT_FACTOR

    def toGeoPoint(self):
        return db.GeoPt(self.latitude / GEO_POINT_FACTOR, self.longitude / GEO_POINT_FACTOR)

    @staticmethod
    def fromGeoPoint(geoPoint):
        to = GeoPointTO()
        to.latitude = int(geoPoint.lat * GEO_POINT_FACTOR)
        to.longitude = int(geoPoint.lon * GEO_POINT_FACTOR)
        return to

    @staticmethod
    def fromLocation(location):
        to = GeoPointTO.fromGeoPoint(location.geoPoint)
        to.accuracy = location.geoAccuracy
        return to

class GeoPointWithTimestampTO(GeoPointTO):
    timestamp = long_property('100')

    @staticmethod
    def fromLocation(location):
        to = GeoPointWithTimestampTO()
        to.latitude = int(location.geoPoint.lat * GEO_POINT_FACTOR)
        to.longitude = int(location.geoPoint.lon * GEO_POINT_FACTOR)
        to.accuracy = location.accuracy
        to.timestamp = location.timestamp
        return to

class CellTowerTO(object):
    cid = long_property('1')
    strength = long_property('2')

class RawLocationInfoTO(object):
    cid = long_property('1')
    lac = long_property('2')
    net = long_property('3')
    towers = typed_property('4', CellTowerTO, True)
    mobileDataType = long_property('5')
    signalStrength = long_property('6')

class CallRecordTO(object):
    id = long_property('1')
    phoneNumber = unicode_property('2')
    duration = long_property('3')
    type = long_property('4')
    starttime = long_property('5')
    countrycode = unicode_property('6')
    geoPoint = typed_property('7', GeoPointTO, False)
    rawLocation = typed_property('8', RawLocationInfoTO, False)

class LocationRecordTO(object):
    timestamp = long_property('1')
    geoPoint = typed_property('2', GeoPointTO, False)
    rawLocation = typed_property('3', RawLocationInfoTO, False)

class LogCallRequestTO(object):
    record = typed_property('1', CallRecordTO, False)

class LogCallResponseTO(object):
    recordId = long_property('1')

class LogLocationRecipientTO(object):
    friend = unicode_property('1')
    target = long_property('2')

class LogLocationsRequestTO(object):
    records = typed_property('1', LocationRecordTO, True)
    recipients = typed_property('2', LogLocationRecipientTO, True)

class LogLocationsResponseTO(object):
    pass
