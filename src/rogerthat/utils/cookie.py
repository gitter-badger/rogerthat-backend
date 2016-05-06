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

import Cookie
import base64
import email.utils
import hashlib
import hmac
import logging

from rogerthat.consts import SESSION_TIMEOUT, DEBUG
from rogerthat.utils import now
from rogerthat.settings import get_server_settings


#### Copied from https://github.com/facebook/python-sdk/blob/master/examples/oauth/facebookoauth.py ####
def set_cookie(response, name, value, domain=None, path="/", expires=None):
    """Generates and signs a cookie for the give name/value"""
    if not isinstance(name, str):
        name = name.encode("utf8")
    timestamp = unicode(now())
    value = base64.b64encode(value)
    signature = cookie_signature(value, timestamp)
    cookie = Cookie.BaseCookie()
    cookie[name] = "|".join([value, timestamp, signature])
    cookie[name]["path"] = path
    if not DEBUG:
        cookie[name]["secure"] = True
    if domain: cookie[name]["domain"] = domain
    if expires:
        cookie[name]["expires"] = email.utils.formatdate(expires, localtime=False, usegmt=True)
    response.headers["Set-Cookie"] = cookie.output()[12:] + '; httponly'


def parse_cookie(value):
    """Parses and verifies a cookie value from set_cookie"""
    if not value: return None
    parts = value.split("|")
    if len(parts) != 3: return None
    if cookie_signature(parts[0], parts[1]) != parts[2]:
        logging.warning("Invalid cookie signature %r", value)
        return None
    timestamp = int(parts[1])
    if timestamp < now() - SESSION_TIMEOUT:
        logging.warning("Expired cookie %r", value)
        return None
    try:
        return base64.b64decode(parts[0]).strip()
    except:
        return None

def cookie_signature(*parts):
    server_settings = get_server_settings()
    """Generates a cookie signature."""
    the_hash = hmac.new(base64.b64decode(server_settings.cookieSecretKey.encode("utf8")), digestmod=hashlib.sha1)
    for part in parts: the_hash.update(part)
    return the_hash.hexdigest()

#### End copied ####
