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

import json
import re
from Queue import Queue, Empty
from threading import Thread
from types import NoneType

from google.appengine.ext import db

from mcfw.rpc import returns, arguments
from rogerthat.bizz import app as bizz_app
from rogerthat.bizz.profile import put_loyalty_user_profile
from rogerthat.bizz.service import validate_app_admin, AppFailedToResovelUrlException
from rogerthat.dal.friend import get_friends_map_key_by_user
from rogerthat.dal.profile import get_user_profiles_by_app_id, get_service_profile
from rogerthat.dal.service import get_default_service_identity
from rogerthat.models import ProfilePointer
from rogerthat.models.properties.app import AutoConnectedService
from rogerthat.rpc import users
from rogerthat.rpc.service import service_api
from rogerthat.to.app import AppInfoTO, AppUserListResultTO, AppUserTO, AppSettingsTO
from rogerthat.to.beacon import BeaconRegionTO
from rogerthat.utils.app import create_app_user
from rogerthat.utils.crypto import decrypt, encrypt


#############################################
# DO NOT DOCUMENT THIS SERVICE API FUNCTION #
@service_api(function=u'app.get_info')
@returns(AppInfoTO)
@arguments(app_id=unicode)
def get_info(app_id):
    app = bizz_app.get_app(app_id)
    return AppInfoTO.fromModel(app) if app else None


@service_api(function=u'app.get_beacon_regions')
@returns([BeaconRegionTO])
@arguments(app_id=unicode)
def get_beacon_regions(app_id):
    service_user = users.get_current_user()
    validate_app_admin(service_user, [app_id])
    app = bizz_app.get_app(app_id)
    return map(BeaconRegionTO.from_model, app.beacon_regions())


@service_api(function=u'app.put_user_regexes')
@returns()
@arguments(app_id=unicode, regexes=[unicode])
def put_user_regexes(app_id, regexes):
    service_user = users.get_current_user()
    validate_app_admin(service_user, [app_id])
    bizz_app.put_user_regexes(service_user, app_id, regexes)


@service_api(function=u'app.del_user_regexes')
@returns()
@arguments(app_id=unicode, regexes=[unicode])
def del_user_regexes(app_id, regexes):
    service_user = users.get_current_user()
    validate_app_admin(service_user, [app_id])
    bizz_app.del_user_regexes(service_user, app_id, regexes)


@service_api(function=u'app.add_auto_connected_services')
@returns(NoneType)
@arguments(app_id=unicode, services=[AutoConnectedService], auto_connect_now=bool)
def add_auto_connected_services(app_id, services, auto_connect_now=True):
    service_user = users.get_current_user()
    validate_app_admin(service_user, [app_id])
    bizz_app.add_auto_connected_services(app_id, services, auto_connect_now)


@service_api(function=u'app.delete_auto_connected_service')
@returns(NoneType)
@arguments(app_id=unicode, service_identity_email=unicode)
def delete_auto_connected_service(app_id, service_identity_email):
    service_user = users.get_current_user()
    validate_app_admin(service_user, [app_id])
    bizz_app.delete_auto_connected_service(service_user, app_id, service_identity_email)


@service_api(function=u'app.put_profile_data')
@returns(NoneType)
@arguments(email=unicode, profile_data=unicode, app_id=unicode)
def put_profile_data(email, profile_data, app_id):
    from rogerthat.bizz.profile import set_profile_data
    service_user = users.get_current_user()
    validate_app_admin(service_user, [app_id])
    set_profile_data(service_user, create_app_user(users.User(email), app_id), profile_data)


@service_api(function=u'app.del_profile_data')
@returns(NoneType)
@arguments(email=unicode, profile_data_keys=[unicode], app_id=unicode)
def del_profile_data(email, profile_data_keys, app_id):
    from rogerthat.bizz.profile import set_profile_data
    service_user = users.get_current_user()
    validate_app_admin(service_user, [app_id])
    set_profile_data(service_user,
                     create_app_user(users.User(email), app_id),
                     json.dumps(dict(((key, None) for key in profile_data_keys))))


@service_api(function=u'app.list_users')
@returns(AppUserListResultTO)
@arguments(app_id=unicode, cursor=unicode)
def list_users(app_id, cursor):
    service_user = users.get_current_user()
    validate_app_admin(service_user, [app_id])

    if cursor:
        cursor = decrypt(service_user, cursor)

    query = get_user_profiles_by_app_id(app_id)
    query.with_cursor(cursor)
    user_profiles = query.fetch(1000)
    cursor = query.cursor()
    extra_key = query.fetch(1)

    result = AppUserListResultTO()
    result.cursor = unicode(encrypt(service_user, cursor)) if len(extra_key) > 0 else None

    work = Queue()
    results = Queue()
    for items in [user_profiles[x:x + 50] for x in xrange(0, len(user_profiles), 50)]:
        work.put(items)

    def slave():
        while True:
            try:
                user_profiles = work.get_nowait()
            except Empty:
                break  # No more work, goodbye
            try:
                friendMaps = db.get([get_friends_map_key_by_user(user_profile.user) for user_profile in user_profiles])
                for user_profile, friendMap in zip(user_profiles, friendMaps):
                    results.put(AppUserTO(user_profile, friendMap))
            except Exception, e:
                results.put(e)

    threads = list()
    for _ in xrange(10):
        t = Thread(target=slave)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    result.users = list()
    while not results.empty():
        app_user = results.get()
        if isinstance(app_user, AppUserTO):
            result.users.append(app_user)
        else:
            raise app_user

    return result


@service_api(function=u'app.put_settings')
@returns()
@arguments(settings=AppSettingsTO, app_id=unicode)
def put_settings(settings, app_id=None):
    service_user = users.get_current_user()
    if not app_id:
        app_id = get_default_service_identity(service_user).app_id

    validate_app_admin(service_user, [app_id])
    bizz_app.put_settings(app_id, settings)


@service_api(function=u'app.put_loyalty_user')
@returns()
@arguments(url=unicode, email=unicode)
def put_loyalty_user(url, email):
    service_user = users.get_current_user()
    url = url.upper()
    m = re.match("(HTTPS?://)(.*)/(M|S)/(.*)", url)
    if m:
        from rogerthat.pages.shortner import get_short_url_by_code
        code = m.group(4)
        su = get_short_url_by_code(code)

        if su.full.startswith("/q/i"):
            user_code = su.full[4:]
            pp = ProfilePointer.get(user_code)
            if not pp:
                service_profile = get_service_profile(service_user)
                si = get_default_service_identity(service_user)
                put_loyalty_user_profile(email.strip(), si.app_id, user_code, su.key().id(),
                                         service_profile.defaultLanguage)
        else:
            raise AppFailedToResovelUrlException(url)
    else:
        raise AppFailedToResovelUrlException(url)

#############################################
