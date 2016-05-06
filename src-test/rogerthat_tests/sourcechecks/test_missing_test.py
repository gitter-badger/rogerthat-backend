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

import mcfw.consts
import mc_unittest
import pickle
import sys

def find_Missing_class(klz_module, klz_name):
    getattr(sys.modules[klz_module], klz_name)

class Test(mc_unittest.TestCase):

    def test_missing(self):
        m1 = mcfw.consts.MISSING
        m2 = pickle.loads(pickle.dumps(m1))
        assert m1 == m2
        assert m1 is m2

        assert m2 is getattr(mcfw.consts, 'MISSING')
        klz_module, klz_name = mcfw.consts.MISSING.__class__.__module__, mcfw.consts.MISSING.__class__.__name__
        assert getattr(sys.modules[klz_module], 'MISSING') is m2

        self.assertRaises(AttributeError, find_Missing_class, klz_module, klz_name)
