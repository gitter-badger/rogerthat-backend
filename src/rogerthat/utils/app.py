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

from rogerthat.models import App
from rogerthat.rpc import users
from rogerthat.utils import azzert
from mcfw.rpc import returns, arguments


@returns(users.User)
@arguments(app_user=users.User)
def get_human_user_from_app_user(app_user):
    return get_app_user_tuple(app_user)[0]


@returns(unicode)
@arguments(app_user=users.User)
def get_app_id_from_app_user(app_user):
    return get_app_user_tuple(app_user)[1]


@returns(tuple)
@arguments(app_user=users.User)
def get_app_user_tuple(app_user):
    return get_app_user_tuple_by_email(app_user.email())


@returns(tuple)
@arguments(app_user_email=unicode)
def get_app_user_tuple_by_email(app_user_email):
    azzert('/' not in app_user_email, "app_user_email should not contain /")
    if ':' in app_user_email:
        human_user_email, app_id = app_user_email.split(':')
    else:
        from rogerthat.dal.app import get_default_app
        human_user_email, app_id = app_user_email, get_default_app().app_id
    return users.User(human_user_email), app_id


@returns(users.User)
@arguments(human_user=users.User, app_id=unicode)
def create_app_user(human_user, app_id=None):
    return create_app_user_by_email(human_user.email().decode('utf-8'), app_id)


@returns(users.User)
@arguments(human_user_email=unicode, app_id=unicode)
def create_app_user_by_email(human_user_email, app_id=None):
    azzert('/' not in human_user_email, "human_user_email should not contain /")
    azzert(':' not in human_user_email, "human_user_email should not contain :")
    if app_id is None:
        from rogerthat.dal.app import get_default_app
        app_id = get_default_app().app_id
    else:
        azzert(app_id, "app_id should not be empty")
    if app_id != App.APP_ID_ROGERTHAT:
        return users.User(u"%s:%s" % (human_user_email, app_id))
    return users.User(human_user_email)

def sanitize_app_user(app_user):
    app_user_email = app_user.email()
    azzert(':' in app_user_email, "app_user_email should contain :")
    human_user_email, app_id = app_user_email.split(':')
    return create_app_user_by_email(human_user_email, app_id)


@returns(users.User)
@arguments(user=users.User)
def remove_app_id(user):
    # user can be a service_identity_user
    if user is None or not isinstance(user, users.User):
        return user
    if '/' in user.email():
        return user
    if ':' not in user.email():
        return user
    return users.User(user.email().split(':')[0])
