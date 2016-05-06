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

from rogerthat.dal.friend import get_friends_map_cached
from rogerthat.rpc.models import Mobile
from rogerthat.rpc.users import User
from rogerthat.utils import azzert
from google.appengine.ext import db
from mcfw.cache import cached
from mcfw.rpc import returns, arguments


@returns([Mobile])
@arguments(user=User)
def get_user_mobiles(user):
    return Mobile.all().filter("user =", user)

@returns([Mobile])
@arguments(user=User)
def get_user_active_mobiles(user):
    return Mobile.all().filter("user =", user).filter("status =", Mobile.STATUS_NEW | Mobile.STATUS_ACCOUNT_CREATED | Mobile.STATUS_REGISTERED)

@returns(int)
@arguments(user=User)
def get_user_active_mobiles_count(user):
    return Mobile.all().filter("user =", user).filter("status =", Mobile.STATUS_NEW | Mobile.STATUS_ACCOUNT_CREATED | Mobile.STATUS_REGISTERED).count()

@returns([Mobile])
@arguments()
def get_active_mobiles():
    return Mobile.all().filter("status =", Mobile.STATUS_NEW | Mobile.STATUS_ACCOUNT_CREATED | Mobile.STATUS_REGISTERED)

@returns(db.Query)
@arguments()
def get_active_mobiles_keys():
    return Mobile.all(keys_only=True).filter("status =", Mobile.STATUS_NEW | Mobile.STATUS_ACCOUNT_CREATED | Mobile.STATUS_REGISTERED)

@returns(Mobile)
@arguments(user=User, mobile_id=unicode)
def get_user_mobile_by_id(user, mobile_id):
    mobile = get_mobile_by_id(mobile_id)
    azzert(mobile.user == user)
    return mobile

@returns(Mobile)
@arguments(mobile_id=unicode)
def get_mobile_by_id(mobile_id):
    return Mobile.all().filter("id =", mobile_id).get()

@cached(1, 60 * 60)
@returns(Mobile)
@arguments(mobile_id=unicode)
def get_mobile_by_id_cached(mobile_id):
    return get_mobile_by_id(mobile_id)

@returns(Mobile)
@arguments(user=User, mobile_id=unicode)
def get_user_mobile_by_id_cached(user, mobile_id):
    mobile = get_mobile_by_id_cached(mobile_id)
    azzert(mobile.user == user)
    return mobile

@returns([Mobile])
@arguments(user=User, mobile_ids=[unicode], friendsOk=bool)
def get_user_mobiles_by_id(user, mobile_ids, friendsOk):
    """
    Returns the mobiles specified by the mobile_ids list.
    The mobiles are also validated against their owner
    or friend relation ships if friendsOk == True
    """
    mobiles = [get_mobile_by_id_cached(mobile_id) for mobile_id in mobile_ids]
    friendMap = get_friends_map_cached(user)
    for mobile in mobiles:
        azzert(mobile.user == user or (friendsOk and mobile.user in friendMap.friends))
    return mobiles

@returns(Mobile)
@arguments(account=unicode)
def get_mobile_by_account(account):
    return Mobile.get_by_key_name(account)

@returns(db.Key)
@arguments(email=unicode)
def get_mobile_key_by_account(email):
    return db.Key.from_path(Mobile.kind(), email)

@returns(Mobile)
@arguments(key=db.Key)
def get_mobile_by_key(key):
    return Mobile.get(key)

@cached(1, 60 * 60)
@returns(Mobile)
@arguments(key=db.Key)
def get_mobile_by_key_cached(key):
    return get_mobile_by_key(key)

@returns([Mobile])
@arguments(token=unicode)
def get_mobiles_by_ios_push_id(token):
    return Mobile.all().filter("iOSPushId =", token.upper())
