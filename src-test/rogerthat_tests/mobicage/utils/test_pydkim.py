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

import mc_unittest
from email.message import Message

class Test(mc_unittest.TestCase):

    def testDKIM(self):

        privKey = """-----BEGIN RSA PRIVATE KEY-----
MIICXQIBAAKBgQDe/Uq1hSUvQStzcpHTiGymukXBEQOxrk8uu4/5aT5AHi6HC1MY
8fiCoi6sdUL/3VLLvqH0Bb2H5jqz7KAs7wwNRJvAXPzs8MTNFyeg6702H+R5t9/W
h0mBBwuD9yaYWuOsXrhn9mq7nWcWhiDe1HGLUa1nte/MlhR6MsPm1GOHhwIDAQAB
AoGAbo3NuGkmomMBE9+9hM6ib5bydmHlHvZ4s4ayPsl633cXQkTPEhMFTl7yHPaW
HRyxq+n7iWw/J11xxTqPvzdVFWHuMA7oTfz+3gdKlbEnbfKFGo4rboYNnOBpYlKg
mnmPywWjMTl3av/rXHNAgjHi1ZREORFKXwjbQGK8y2ExXCECQQD07IIT0NCOOJej
UUr9Qt94NJASsYbD4/fMpnExYwv8QKT2YxTIXtFAlXi5azRpkAvxli0r+qZLklsh
/gQIGyHjAkEA6RLZFMJelrLy8BkLzyyY0nYKte50sAuJToPv2nJK9UNHyEfIQSve
VDJNimzSdGwDHfUGHeVDYsnnXK81qv8lDQJBAIe4Nyx73dWxjnW1qnRFBkg5+Ewj
i6YpQTtqT/cqB4401DSkGvQddp7vNQKqYVTNuZCZw1ZHgrcF1vIzLFDBmDkCQBNA
KEfrqe5eh2xHVU9eSp0PfOD7+g1UVpnykcwEJqbNUM99BlBDtFBV+0uUo2lURomh
5Ehx2Df/nylrm04tVr0CQQDP1g/PckPzOzKVoppKiFFYGzd/W0NF0dUwA4r0Qv/Y
v8T0kOg+O9/myj6AFk1G56PQRT4Fjlb/ey8ALGkjyKYO
-----END RSA PRIVATE KEY-----"""

        body = """Hi There,

This is a simple message that will be signed by pydkim

--The signer
"""

        msg = Message()
        msg['From'] = 'Sender <sender@topdog-software.com>'
        msg['To'] = 'Recipient <recipient@example.com>'
        msg['Subject'] = 'Test message'
        msg.set_payload(body)

        headers = ['To', 'From', 'Subject']
        email = msg.as_string()
        import dkim
        sig = dkim.sign(email, 'default', 'topdog-software.com', privKey, include_headers=headers)
        print sig, email
