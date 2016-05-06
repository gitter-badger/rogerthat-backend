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

from rogerthat.to.activity import GeoPointWithTimestampTO
from mcfw.properties import unicode_property, typed_property, long_property, bool_property


class GetFriendLocationRequestTO(object):
    friend = unicode_property('1')

class GetFriendLocationResponseTO(object):
    location = typed_property('1', GeoPointWithTimestampTO, False)

class GetFriendsLocationRequestTO(object):
    pass

class FriendLocationTO(object):
    email = unicode_property('1')
    location = typed_property('2', GeoPointWithTimestampTO, False)

class GetFriendsLocationResponseTO(object):
    locations = typed_property('1', FriendLocationTO, True)

class GetLocationErrorTO(object):
    STATUS_INVISIBLE = 1  # when INVISBLE MODE is switched on in settings
    STATUS_TRACKING_POLICY = 2  # denied because of location tracking settings in WEB
    STATUS_AUTHORIZATION_DENIED = 3  # iOS: kCLAuthorizationStatusDenied
    STATUS_AUTHORIZATION_ONLY_WHEN_IN_USE = 4  # iOS: kCLAuthorizationStatusAuthorizedWhenInUse
    STATUS_AUTHORIZATION_RESTRICTED = 5  # iOS: kCLAuthorizationStatusRestricted
    message = unicode_property('1')
    status = long_property('2')

class GetLocationRequestTO(object):
    # TARGET numbers for getting a location once should be less than 1000
    TARGET_WEB = 1
    TARGET_MOBILE = 2
    TARGET_MOBILE_FRIENDS_ON_MAP = 3
    TARGET_MOBILE_FIRST_REQUEST_AFTER_GRANT = 4
    # TARGET numbers for tracking should be greater than 1000
    TARGET_SERVICE_LOCATION_TRACKER = 1001
    friend = unicode_property('1')
    target = long_property('2')
    high_prio = bool_property('3')

class GetLocationResponseTO(object):
    error = typed_property('1', GetLocationErrorTO, False)

class LocationResultRequestTO(object):
    friend = unicode_property('1')
    location = typed_property('2', GeoPointWithTimestampTO, False)

class LocationResultResponseTO(object):
    pass

class TrackLocationRequestTO(GetLocationRequestTO):
    until = long_property('50')
    distance_filter = long_property('51')

class TrackLocationResponseTO(GetLocationResponseTO):
    pass

class BeaconDiscoveredRequestTO(object):
    uuid = unicode_property('1')
    name = unicode_property('2')

class BeaconDiscoveredResponseTO(object):
    friend_email = unicode_property('1')
    tag = unicode_property('2', default=None)

class DeleteBeaconDiscoveryRequestTO(object):
    uuid = unicode_property('1')
    name = unicode_property('2')

class DeleteBeaconDiscoveryResponseTO(object):
    pass

class BeaconInReachRequestTO(object):
    friend_email = unicode_property('1')
    uuid = unicode_property('2')
    name = unicode_property('3')
    proximity = long_property('4')

class BeaconInReachResponseTO(object):
    pass

class BeaconOutOfReachRequestTO(object):
    friend_email = unicode_property('1')
    uuid = unicode_property('2')
    name = unicode_property('3')

class BeaconOutOfReachResponseTO(object):
    pass
