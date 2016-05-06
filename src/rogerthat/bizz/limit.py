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

from types import NoneType

from rogerthat.rpc import users
from rogerthat.utils import now
from google.appengine.api import memcache, xmpp
from mcfw.rpc import arguments, returns
from rogerthat.settings import get_server_settings


SIGNUP_RP_RATE_USER_KEY = "signup_rp_user_key_%s"
SIGNUP_RP_RATE_USER_WINDOW = 60
SIGNUP_RP_RATE_USER_LIMIT = 5

SIGNUP_RP_RATE_IP_KEY = "signup_rp_ip_key_%s"
SIGNUP_RP_RATE_IP_WINDOW = 60
SIGNUP_RP_RATE_IP_LIMIT = 20

LOGIN_RATE_USER_KEY = "login_user_key_%s"
LOGIN_RATE_USER_WINDOW = 1
LOGIN_RATE_USER_LIMIT = 3

@returns(bool)
@arguments(key=str, window=int, limit=int)
def rate(key, window, limit):
    """
    Rate limit implementation based on memcache.
    
    @param key Key which represents the functionality which needs rate limiting.
    @type str
    @param window Time in minutes to limit the number of executions
    @type int
    @param limit Maximum number of calls to be executed in window minutes 
    """

    cache_key = "rate_" + key
    items = memcache.get(cache_key)  # @UndefinedVariable
    items = items if items else list()
    mepoch = now() / 60
    items = [x for x in items if x[0] >= mepoch - window]  # filter elapsed executions
    count = sum(x[1] for x in items)
    if count < limit:
        if len(items) > 0 and items[-1][0] == mepoch:
            items[-1] = (mepoch, items[-1][1] + 1)
        else:
            items.append((mepoch, 1))
        memcache.set(cache_key, items, time=(window + 1) * 60)  # @UndefinedVariable
        return True
    else:
        return False

@returns(NoneType)
@arguments(key=str)
def clear_rate(key):
    cache_key = "rate_" + key
    memcache.delete(cache_key)  # @UndefinedVariable

@returns(bool)
@arguments(user=users.User, ip=str)
def rate_signup_reset_password(user, ip):
    if not rate(SIGNUP_RP_RATE_USER_KEY % user.email(), SIGNUP_RP_RATE_USER_WINDOW, SIGNUP_RP_RATE_USER_LIMIT):
        server_settings = get_server_settings()
        xmpp.send_message(server_settings.xmppInfoMembers, "Signup rate limited for user %s." % user, message_type=xmpp.MESSAGE_TYPE_CHAT)
        return False

    if ip and not rate(SIGNUP_RP_RATE_IP_KEY % ip, SIGNUP_RP_RATE_IP_WINDOW, SIGNUP_RP_RATE_IP_LIMIT):
        server_settings = get_server_settings()
        xmpp.send_message(server_settings.xmppInfoMembers, "Signup rate limited for ip %s." % ip, message_type=xmpp.MESSAGE_TYPE_CHAT)
        return False

    return True

@returns(bool)
@arguments(user=users.User)
def rate_login(user):
    if not rate(LOGIN_RATE_USER_KEY % user.email(), LOGIN_RATE_USER_WINDOW, LOGIN_RATE_USER_LIMIT):
        server_settings = get_server_settings()
        xmpp.send_message(server_settings.xmppInfoMembers, "Login rate limited for user %s." % user, message_type=xmpp.MESSAGE_TYPE_CHAT)
        return False

    return True

@returns(NoneType)
@arguments(user=users.User)
def clear_rate_login(user):
    clear_rate(LOGIN_RATE_USER_KEY % user.email())
