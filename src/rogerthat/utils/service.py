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
import string

from rogerthat.models import ServiceIdentity
from rogerthat.rpc import users
from rogerthat.utils import azzert, get_python_stack_trace
from mcfw.rpc import arguments, returns


SVC_IDENTIFIER_ALLOWED_CHARACTERS = set(string.ascii_lowercase + string.digits + '.-_')

@returns(users.User)
@arguments(service_identity_user=users.User)
def get_service_user_from_service_identity_user(service_identity_user):
    return get_service_identity_tuple(service_identity_user)[0]

@returns(unicode)
@arguments(service_identity_user=users.User)
def get_identity_from_service_identity_user(service_identity_user):
    return get_service_identity_tuple(service_identity_user)[1]

@returns(tuple)
@arguments(service_identity_user=users.User)
def get_service_identity_tuple(service_identity_user):
    full_name = service_identity_user.email()
    if '/' in full_name:
        service_email, identity = full_name.split('/')
    else:
        service_email, identity = full_name, ServiceIdentity.DEFAULT
    return users.User(service_email), identity

@returns(users.User)
@arguments(service_user=users.User, identity=unicode)
def create_service_identity_user(service_user, identity=ServiceIdentity.DEFAULT):
    azzert('/' not in service_user.email(), "service_user.email() should not contain /")
    azzert(identity, "identity should not be empty")
    return users.User(u"%s/%s" % (service_user.email(), identity))

@returns(users.User)
@arguments(service_identity_user=users.User)
def add_slash_default(service_identity_user):
    '''Add /+default+ if needed'''
    if '/' not in service_identity_user.email():
        return create_service_identity_user(service_identity_user, ServiceIdentity.DEFAULT)
    return service_identity_user

@returns(users.User)
@arguments(service_identity_user=users.User, warn=bool)
def remove_slash_default(service_identity_user, warn=False):
    '''Remove /+default+ if needed'''
    if service_identity_user.email().endswith("/%s" % ServiceIdentity.DEFAULT):
        if warn:
            logging.warn("Implicit removed /+default+\n%s" % get_python_stack_trace())
        return get_service_user_from_service_identity_user(service_identity_user)
    return service_identity_user

@returns(bool)
@arguments(identifier=unicode)
def is_valid_service_identifier(identifier):
    if identifier == ServiceIdentity.DEFAULT:
        return True
    return set(identifier) <= SVC_IDENTIFIER_ALLOWED_CHARACTERS
