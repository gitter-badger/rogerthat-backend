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

from StringIO import StringIO
from rogerthat.bizz.profile import create_user_profile, create_service_profile
from rogerthat.dal.profile import get_user_profile, get_profile_infos, _get_profile
from rogerthat.models import UserProfile, ServiceIdentity
from rogerthat.rpc import rpc, users
from google.appengine.api import memcache
from mcfw.cache import cached, flush_request_cache, get_from_request_cache
from mcfw.consts import MISSING
from mcfw.rpc import returns, arguments
import mc_unittest
import time


class Test(mc_unittest.TestCase):
    cache_hit = True

    def testCache(self):

        @cached(1, 1)
        @returns(int)
        @arguments(arg1=int, arg2=int)
        def divide(arg1, arg2):
            Test.cache_hit = False
            return arg1 / arg2

        result = divide(35, 6)
        assert not Test.cache_hit
        assert result == 5

        Test.cache_hit = True
        result = divide(35, 6)
        assert Test.cache_hit
        assert result == 5

        time.sleep(1)
        flush_request_cache()
        result = divide(35, 6)
        assert not Test.cache_hit
        assert result == 5

        Test.cache_hit = True
        self.assertRaises(ZeroDivisionError, lambda:divide(35, 0))
        assert not Test.cache_hit

        Test.cache_hit = True
        self.assertRaises(ZeroDivisionError, lambda:divide(35, 0))
        assert not Test.cache_hit

    def testCacheDefaultArgs(self):

        @cached(1, 1)
        @returns(int)
        @arguments(arg1=int, arg2=int)
        def divide(arg1, arg2=6):
            Test.cache_hit = False
            return arg1 / arg2

        Test.cache_hit = False
        result = divide(36, 12)
        assert result == 3
        assert not Test.cache_hit

        result = divide(36, 6)
        assert result == 6
        assert not Test.cache_hit
        Test.cache_hit = True
        result = divide(36, 6)
        assert result == 6
        assert Test.cache_hit
        result = divide(36)
        assert result == 6
        assert Test.cache_hit

        result = divide(60)
        assert result == 10
        assert not Test.cache_hit
        Test.cache_hit = True
        result = divide(60)
        assert result == 10
        assert Test.cache_hit
        result = divide(60, 6)
        assert result == 10
        assert Test.cache_hit

    def testListArgs(self):
        @cached(1, 1)
        @returns(int)
        @arguments(arg1=int, arg2=[int])
        def add(arg1=2, arg2=[1, 2, 3]):
            Test.cache_hit = False
            return arg1 + sum(arg2)

        Test.cache_hit = False
        assert add(3, []) == 3
        assert not Test.cache_hit

        assert add() == 8
        assert not Test.cache_hit
        Test.cache_hit = True
        assert add() == 8
        assert Test.cache_hit

        assert add(arg2=[1, 2, 3], arg1=2) == 8
        assert Test.cache_hit


    def testCacheDatastore(self):

        @cached(1, 0, memcache=False, datastore="divide_results")
        @returns(int)
        @arguments(arg1=int, arg2=int)
        def divide2(arg1, arg2):
            Test.cache_hit = False
            return arg1 / arg2

        result = divide2(35, 6)
        assert not Test.cache_hit
        assert result == 5

        rpc.wait_for_rpcs()

        Test.cache_hit = True
        result = divide2(35, 6)
        assert Test.cache_hit
        assert result == 5

        time.sleep(1)
        flush_request_cache()
        result = divide2(35, 6)
        assert Test.cache_hit
        assert result == 5

        Test.cache_hit = True
        self.assertRaises(ZeroDivisionError, lambda:divide2(35, 0))
        assert not Test.cache_hit

        Test.cache_hit = True
        self.assertRaises(ZeroDivisionError, lambda:divide2(35, 0))
        assert not Test.cache_hit

    def testProfileCache(self):
        john = users.User(u"john.doe@foo.com")
        create_user_profile(john, u"John Doe")

        jane = users.User(u"jane.doe@foo.com")
        create_user_profile(jane, u"John Doe")

        service = users.User(u"service@foo.com")
        create_service_profile(service, u"Tha service")

        flush_request_cache()

        john_cache_key = _get_profile.cache_key(john)  # @UndefinedVariable
        jane_cache_key = _get_profile.cache_key(jane)  # @UndefinedVariable
        service_cache_key = _get_profile.cache_key(service)  # @UndefinedVariable
        assert MISSING == get_from_request_cache(john_cache_key)
        assert MISSING == get_from_request_cache(jane_cache_key)  # @UndefinedVariable
        assert MISSING == get_from_request_cache(service_cache_key)  # @UndefinedVariable

        get_user_profile(john)
        assert MISSING != get_from_request_cache(john_cache_key)

        rpc.wait_for_rpcs()

        memcache_result = memcache.get(john_cache_key)  # @UndefinedVariable
        buf = StringIO(memcache_result)
        success, result = _get_profile.deserializer(buf)  # @UndefinedVariable
        assert success
        assert result.user == john

        get_profile_infos([john, jane, service], False, False, expected_types=[UserProfile, UserProfile, ServiceIdentity])

        assert MISSING != get_from_request_cache(john_cache_key)
        assert MISSING == get_from_request_cache(jane_cache_key)  # @UndefinedVariable
        assert MISSING == get_from_request_cache(service_cache_key)  # @UndefinedVariable

        get_profile_infos([john, jane, service], False, True, expected_types=[UserProfile, UserProfile, ServiceIdentity])

        rpc.wait_for_rpcs()

#        memcache_result = memcache.get(jane_cache_key) #@UndefinedVariable
#        buf = StringIO(memcache_result)
#        success, result = get_profile.deserializer(buf) #@UndefinedVariable
#        assert success
#        assert result.user == jane
#        memcache_result = memcache.get(service_cache_key) #@UndefinedVariable
#        buf = StringIO(memcache_result)
#        success, result = get_profile.deserializer(buf) #@UndefinedVariable
#        assert success
#        assert result.user == service
#
#        get_profiles([john, jane, service], True, True)
#
#        assert MISSING != get_from_request_cache(john_cache_key)
#        assert MISSING != get_from_request_cache(jane_cache_key) #@UndefinedVariable
#        assert MISSING != get_from_request_cache(service_cache_key) #@UndefinedVariable
#
#        flush_request_cache()
#        get_profiles([john, jane, service], True, True)
