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
import re

from rogerthat.bizz.job import run_job, hookup_with_default_services
from rogerthat.bizz.service import ServiceWithEmailDoesNotExistsException
from rogerthat.bizz.system import update_settings_response_handler
from rogerthat.capi.system import updateSettings
from rogerthat.dal import put_and_invalidate_cache
from rogerthat.dal.app import get_app_settings
from rogerthat.dal.profile import get_user_profile_keys_by_app_id, get_user_profiles_by_app_id
from rogerthat.dal.service import get_service_identities_by_service_identity_users
from rogerthat.models import App, AppSettings, UserProfile
from rogerthat.models.properties.app import AutoConnectedService
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile
from rogerthat.rpc.rpc import logError
from rogerthat.rpc.service import ServiceApiException, BusinessException
from rogerthat.to.app import AppSettingsTO
from rogerthat.to.system import UpdateSettingsRequestTO, SettingsTO
from rogerthat.utils.service import add_slash_default
from google.appengine.ext import db, deferred
from mcfw.consts import MISSING
from mcfw.rpc import returns, arguments


class AppDoesNotExistException(ServiceApiException):
    def __init__(self, app_id):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_APP + 0,
                                     u"App does not exist", app_id=app_id)


class AppAlreadyExistsException(ServiceApiException):
    def __init__(self, app_id):
        message = u"App %(app_id)s already exists" % dict(app_id=app_id)
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_APP + 1, message, app_id=app_id)


@returns(App)
@arguments(app_id=unicode)
def get_app(app_id):
    def trans():
        app = App.get(App.create_key(app_id))
        if not app:
            raise AppDoesNotExistException(app_id)
        return app

    return trans() if db.is_in_transaction() else db.run_in_transaction(trans)

@returns()
@arguments(app_id=unicode, services=[AutoConnectedService], auto_connect_now=bool)
def add_auto_connected_services(app_id, services, auto_connect_now=True):
    def trans():
        app = get_app(app_id)
        to_be_put = [app]

        si_users = [add_slash_default(users.User(acs.service_identity_email)) for acs in services]
        service_identities = get_service_identities_by_service_identity_users(si_users)
        for si, acs in zip(service_identities, services):
            if not si:
                raise ServiceWithEmailDoesNotExistsException(acs.service_identity_email)
            if app_id not in si.appIds:
                si.appIds.append(app_id)
                to_be_put.append(si)

            acs.service_identity_email = si.user.email()
            app.auto_connected_services.add(acs)

        put_and_invalidate_cache(*to_be_put)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)

    if auto_connect_now:
        for acs in services:
            logging.info("There is a new auto-connected service for %s: %s", app_id, acs.service_identity_email)
            run_job(get_user_profile_keys_by_app_id, [app_id],
                    hookup_with_default_services.run_for_auto_connected_service, [acs, None])


@returns()
@arguments(service_user=users.User, app_id=unicode, service_identity_email=unicode)
def delete_auto_connected_service(service_user, app_id, service_identity_email):
    def trans():
        app = get_app(app_id)
        if service_identity_email in app.auto_connected_services:
            app.auto_connected_services.remove(service_identity_email)
            app.put()

    db.run_in_transaction(trans)


@returns(bool)
@arguments(service_user=users.User, app_id=unicode, regexes=[unicode])
def put_user_regexes(service_user, app_id, regexes):
    def trans():
        app = get_app(app_id)
        user_regexes = app.user_regex.splitlines()
        updated = False
        for regex in regexes:
            if regex not in user_regexes:
                user_regexes.append(regex)
                updated = True
        if updated:
            app.user_regex = '\n'.join(user_regexes)
            app.put()
        return updated

    return db.run_in_transaction(trans)


@returns(bool)
@arguments(service_user=users.User, app_id=unicode, regexes=[unicode])
def del_user_regexes(service_user, app_id, regexes):
    def trans():
        app = get_app(app_id)
        user_regexes = app.user_regex.splitlines()
        updated = False
        for regex in regexes:
            if regex in user_regexes:
                user_regexes.remove(regex)
                updated = True
        if updated:
            app.user_regex = '\n'.join(user_regexes)
            app.put()
        return updated

    return db.run_in_transaction(trans)


@returns(AppSettings)
@arguments(service_user=users.User, app_id=unicode, settings=AppSettingsTO)
def put_settings(service_user, app_id, settings):
    def trans():
        updated = False
        app_settings = get_app_settings(app_id)
        if not app_settings:
            app_settings = AppSettings(key=AppSettings.create_key(app_id))
            updated = True

        if settings.wifi_only_downloads is not MISSING \
                and app_settings.wifi_only_downloads != settings.wifi_only_downloads:
            app_settings.wifi_only_downloads = settings.wifi_only_downloads
            updated = True

        if settings.background_fetch_timestamps is not MISSING \
                and app_settings.background_fetch_timestamps != settings.background_fetch_timestamps:
            app_settings.background_fetch_timestamps = settings.background_fetch_timestamps
            updated = True

        if updated:
            app_settings.put()
            deferred.defer(_app_settings_updated, app_id, _transactional=True)

        return app_settings

    return db.run_in_transaction(trans)


@returns()
@arguments(app_id=unicode)
def _app_settings_updated(app_id):
    run_job(get_user_profiles_by_app_id, [app_id],
            push_app_settings_to_user, [app_id])


@returns()
@arguments(user_profile=UserProfile, app_id=unicode)
def push_app_settings_to_user(user_profile, app_id):
    if user_profile.mobiles:
        keys = [AppSettings.create_key(app_id)] + [Mobile.create_key(mobile_detail.account)
                                                   for mobile_detail in user_profile.mobiles]
        entities = db.get(keys)
        app_settings = entities.pop(0)
        for mobile in entities:
            mobile_settings = mobile.settings()
            mobile_settings.version += 1
            mobile_settings.put()

            request = UpdateSettingsRequestTO()
            request.settings = SettingsTO.fromDBSettings(mobile_settings, app_settings)
            updateSettings(update_settings_response_handler, logError, mobile.user, request=request)


def validate_user_regex(user_regex):
    all_ok = True
    error_message = "Invalid user regex:\\n\\n"
    regexes = user_regex.splitlines()

    for i, regex in enumerate(regexes):
        try:
            re.match(regex, "")
        except:
            all_ok = False
            error_message += 'line %s: %s\\n' % (i + 1, regex)
    if not all_ok:
        raise BusinessException(error_message)
