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

from google.appengine.ext import db

from rogerthat.models import App, AppSettings, AppTranslations, AppAndTranslations
from rogerthat.rpc import users
from rogerthat.utils.app import get_app_id_from_app_user
from mcfw.cache import cached
from mcfw.rpc import returns, arguments


@returns([App])
@arguments()
def get_all_apps():
    return App.all()

@returns([App])
@arguments()
def get_visible_apps():
    return App.all().filter("visible =", True)


@returns([App])
@arguments()
def get_extra_apps():
    return App.all().filter("demo =", False).filter("visible =", True)


@returns([App])
@arguments(app_types=[int], only_visible=bool)
def get_apps(app_types, only_visible=True):
    qry = App.all().filter('type IN', app_types)
    if only_visible:
        qry.filter("visible =", True)
    return qry


@cached(1, request=True, lifetime=0)
@returns(App)
@arguments(app_id=unicode)
def get_app_by_id(app_id):
    return App.get(App.create_key(app_id))


@cached(1, request=True, lifetime=0)
@returns(AppAndTranslations)
@arguments(app_id=unicode)
def get_app_and_translations_by_app_id(app_id):
    return AppAndTranslations(*db.get((App.create_key(app_id), AppTranslations.create_key(app_id))))


@returns(unicode)
@arguments(app_id=unicode)
def get_app_name_by_id(app_id):
    return get_app_by_id(app_id).name


@returns(App)
@arguments(app_user=users.User)
def get_app_by_user(app_user):
    app_id = get_app_id_from_app_user(app_user)
    return get_app_by_id(app_id)


@cached(1, memcache=True, request=True, datastore="get_default_app", lifetime=0)
@returns(App)
@arguments()
def get_default_app():
    @db.non_transactional
    def f():
        return App.all().filter('is_default =', True).get()
    return f()


@cached(1, memcache=True, request=True, datastore="get_default_app_key", lifetime=0)
@returns(db.Key)
@arguments()
def get_default_app_key():
    @db.non_transactional
    def f():
        return App.all(keys_only=True).filter('is_default =', True).get()
    return f()


@cached(1, request=True, lifetime=0)
@returns(AppSettings)
@arguments(app_id=unicode)
def get_app_settings(app_id):
    return AppSettings.get(AppSettings.create_key(app_id))
