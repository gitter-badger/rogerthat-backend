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

from rogerthat.bizz.session import switch_to_service_identity
from rogerthat.dal.profile import get_service_profile
from rogerthat.exceptions import ServiceExpiredException
from rogerthat.rpc import users
from rogerthat.to import EmailReturnStatusTO
from rogerthat.utils.service import get_service_identity_tuple, get_service_user_from_service_identity_user
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments


@rest("/mobi/rest/user/login_as", "post")
@returns(EmailReturnStatusTO)
@arguments(account=unicode)
def do_login_as(account):
    try:
        return EmailReturnStatusTO.create(True, None, login_as(account))
    except ServiceExpiredException:
        return EmailReturnStatusTO.create(False, None, None)

@returns(unicode)
@arguments(account=unicode)
def login_as(account):
    user = users.get_current_user()
    session_ = users.get_current_session()
    if not (user and session_):
        logging.warning("login_as called from unauthenticated context")
        return
    service_profile = get_service_profile(get_service_user_from_service_identity_user(users.User(account)))
    if service_profile.expiredAt > 0:
        raise ServiceExpiredException()
    # Get service identities of session.user
    if session_.user.email() == account:
        session_ = switch_to_service_identity(session_, None, False, False)
        users.update_session_object(session_, session_.user)
        logging.info("Switching session of %s from %s to %s", session_.user, user, account)
        return session_.user.email()
    else:
        service_identity_user = users.User(account)
        logging.info("Validating if %s has a role in %s", session_.user, service_identity_user)
        if session_.has_access(account):
            session_ = switch_to_service_identity(session_, service_identity_user, False, False)
            service_user, _ = get_service_identity_tuple(service_identity_user)
            users.update_session_object(session_, service_user)
            logging.info("Switching session of %s from %s to %s", session_.user, user, service_identity_user)
            return service_identity_user.email()
    logging.critical("%s tried getting access to %s!", session_.user, account)
