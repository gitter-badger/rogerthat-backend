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

from mcfw.properties import unicode_property, long_property, typed_property, bool_property


class BeaconTO(object):
    uuid = unicode_property('1')
    major = long_property('2')
    minor = long_property('3')
    tag = unicode_property('4', default=None)

    @staticmethod
    def fromModel(beacon):
        b = BeaconTO()
        b.uuid = beacon.uuid
        name = beacon.name.split("|")
        b.major = int(name[0])
        b.minor = int(name[1])
        b.tag = beacon.tag
        return b


class BeaconRegionTO(object):
    uuid = unicode_property('1')
    major = long_property('2')
    minor = long_property('3')
    has_major = bool_property('4')
    has_minor = bool_property('5')

    @classmethod
    def from_model(cls, model):
        return cls.create(model.uuid, model.major, model.minor)

    @classmethod
    def create(cls, uuid, major, minor):
        to = cls()
        to.uuid = uuid
        if major is None:
            to.major = -1
            to.has_major = False
        else:
            to.major = major
            to.has_major = True

        if minor is None:
            to.minor = -1
            to.has_minor = False
        else:
            to.minor = minor
            to.has_minor = True
        return to


class UpdateBeaconRegionsRequestTO(object):
    pass

class UpdateBeaconRegionsResponseTO(object):
    pass

class GetBeaconRegionsRequestTO(object):
    pass

class GetBeaconRegionsResponseTO(object):
    regions = typed_property('1', BeaconRegionTO, True)

    @staticmethod
    def fromDBBeaconRegions(brs):
        gbr = GetBeaconRegionsResponseTO()
        gbr.regions = map(BeaconRegionTO.from_model, brs)
        return gbr
