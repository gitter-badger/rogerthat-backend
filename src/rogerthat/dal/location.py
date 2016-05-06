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

import logging
from types import NoneType

from rogerthat.dal import parent_key
from rogerthat.models import UserLocation, ServiceLocationTracker
from rogerthat.rpc import users
from rogerthat.utils import now
from mcfw.rpc import arguments, returns


@returns(UserLocation)
@arguments(user=users.User)
def get_or_insert_user_location(user):
    return UserLocation.get_or_insert(user.email(), parent=parent_key(user))

@returns(UserLocation)
@arguments(user=users.User)
def get_user_location(user):
    pkey = parent_key(user)
    key_name = user.email()
    ul = UserLocation.get_by_key_name(key_name, pkey)
    return ul if ul else UserLocation(pkey, key_name)

@returns([UserLocation])
@arguments(user=users.User)
def get_friends_location(user):
    qry = UserLocation.gql("WHERE members = :member")
    qry.bind(member=user)
    return (ul for ul in qry.run())

@returns(NoneType)
@arguments(user=users.User)
def delete_user_location(user):
    pkey = parent_key(user)
    key_name = user.email()
    ul = UserLocation.get_by_key_name(key_name, pkey)
    if ul:
        ul.delete()

@returns(ServiceLocationTracker)
@arguments(app_user=users.User, service_identity_user=users.User)
def get_current_tracker(app_user, service_identity_user):
    logging.info("Getting current location tracker for %s of %s", app_user, service_identity_user)
    slt = ServiceLocationTracker.all().ancestor(parent_key(app_user)).filter("service_identity_user =", service_identity_user) \
        .filter("until >=", now()).filter("enabled =", True).get()
    if slt:
        logging.info("Found location tracker")
    else:
        logging.info("No location tracker found")
    return slt
