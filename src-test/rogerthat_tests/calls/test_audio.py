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

from rogerthat.rpc.rpc import expose
from mcfw.properties import unicode_property, long_property, unicode_list_property, typed_property
from mcfw.rpc import returns, arguments

@expose(('api',))
@returns(float)
@arguments(start=float, end=[float])
def log(start, end):
    return sum(end)/len(end) - start

class Address(object):
    street = unicode_property('1')
    house_number = long_property('2')
    bus = unicode_property('3')
    zipcode = unicode_property('4')
    city = unicode_property('5')
    country = unicode_property('6')

class ExtraInfo(object):
    first_name = unicode_property('1')
    christian_names = unicode_list_property('2')
    age = long_property('3')
    addresses = typed_property('4', Address, True)
    
class ExtraResultDetail(object):
    lol = unicode_property('1')
    
class ExtraResult(object):
    details = typed_property('1', ExtraResultDetail, True)
    
@expose(('api',))
@returns(ExtraResult)
@arguments(info=ExtraInfo)
def updateContact(info):
    er = ExtraResult()
    er.details = []
    d = ExtraResultDetail()
    d.lol = info.addresses[0].street
    er.details.append(d)
    d = ExtraResultDetail()
    d.lol = info.addresses[1].street
    er.details.append(d)
    return er
