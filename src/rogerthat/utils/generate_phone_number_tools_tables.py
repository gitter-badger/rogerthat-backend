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

from phone_number_tools import info1, info2, info3


remove1 = []
remove2 = []
remove3 = []

result = []

for (cname3, ciso3, ccall3) in info3:

    found2 = []
    for (mcc2, ciso2, cname2) in info2:
        if (ciso3 == ciso2):
            remove3.append((cname3, ciso3, ccall3))
            remove2.append((mcc2, ciso2, cname2))
            found2.append((mcc2, ciso2, cname2))

    found1 = []
    for (cname1, ccall1, cexit1, ctrunk1) in info1:
        if (ccall3 == ccall1):
            remove1.append((cname1, ccall1, cexit1, ctrunk1))
            found1.append((cname1, ccall1, cexit1, ctrunk1))

    if len(found1)>1:
        # something fishy
        print '=' * 10 + "INFO1" + "=" * 10
        print found1
        print (cname3, ciso3, ccall3)

    if len(found1)==0:
        # something fishy
        print 'aaaaargh - ' + ciso3

    if  len(found2)==0:
        # something fishy
        print '=' * 10 + "INFO2" + '=' * 10
        print found2
        print (cname3, ciso3, ccall3)

    # cname3, ciso, mcc, ccall, cexit, ctrunk
    result.append((cname3, ciso3, found2[0][0], ccall3, found1[0][2], found1[0][3]))



print '-' * 10
print set(info1).difference(set(remove1))

print '-' * 10
print set(info2).difference(set(remove2))

print '-' * 10
print set(info3).difference(set(remove3))

print '-' * 10
for t in result:
    print unicode(t) + ','
