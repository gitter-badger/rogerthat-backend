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

from rogerthat.rpc.rpc import capi
from rogerthat.to.beacon import UpdateBeaconRegionsResponseTO, UpdateBeaconRegionsRequestTO
from rogerthat.to.location import GetLocationRequestTO, GetLocationResponseTO, LocationResultRequestTO, \
    LocationResultResponseTO, DeleteBeaconDiscoveryResponseTO, DeleteBeaconDiscoveryRequestTO, TrackLocationResponseTO, \
    TrackLocationRequestTO
from mcfw.rpc import returns, arguments


@capi('com.mobicage.capi.location.getLocation')
@returns(GetLocationResponseTO)
@arguments(request=GetLocationRequestTO)
def getLocation(request):
    pass

@capi('com.mobicage.capi.location.locationResult')
@returns(LocationResultResponseTO)
@arguments(request=LocationResultRequestTO)
def locationResult(request):
    pass

@capi('com.mobicage.capi.location.trackLocation')
@returns(TrackLocationResponseTO)
@arguments(request=TrackLocationRequestTO)
def trackLocation(request):
    pass

@capi('com.mobicage.capi.location.deleteBeaconDiscovery')
@returns(DeleteBeaconDiscoveryResponseTO)
@arguments(request=DeleteBeaconDiscoveryRequestTO)
def deleteBeaconDiscovery(request):
    pass

@capi('com.mobicage.capi.location.updateBeaconRegions')
@returns(UpdateBeaconRegionsResponseTO)
@arguments(request=UpdateBeaconRegionsRequestTO)
def updateBeaconRegions(request):
    pass
