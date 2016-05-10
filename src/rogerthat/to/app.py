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

from add_1_monkey_patches import DEBUG
from rogerthat.models import QRTemplate
from rogerthat.models.properties.app import AutoConnectedService
from rogerthat.models.properties.friend import FriendDetail
from rogerthat.models.properties.oauth import OAuthSettings
from rogerthat.to.beacon import BeaconRegionTO
from rogerthat.utils.app import get_human_user_from_app_user
from mcfw.properties import bool_property, unicode_property, long_property, typed_property, unicode_list_property, \
    long_list_property


class AppInfoTO(object):
    id = unicode_property('0')
    name = unicode_property('1')
    ios_appstore_url = unicode_property('2')
    android_playstore_url = unicode_property('3')

    @staticmethod
    def fromModel(model):
        app = AppInfoTO()
        app.id = model.app_id
        app.name = model.name
        app.ios_appstore_url = model.ios_appstore_web_uri
        app.android_playstore_url = model.android_market_android_uri
        return app

class AppQRTemplateTO(object):
    key_name = unicode_property('1')
    is_default = bool_property('2')
    description = unicode_property('3')
    body_color = unicode_property('4')

    @staticmethod
    def fromKeyName(key_name, is_default):
        qr_template = QRTemplate.get_by_key_name(key_name)
        qrt = AppQRTemplateTO()
        qrt.key_name = key_name
        qrt.is_default = is_default
        qrt.description = qr_template.description
        qrt.body_color = u"".join(("%X" % c).rjust(2, '0') for c in qr_template.body_color)
        return qrt


class AppTO(object):
    id = unicode_property('0')
    name = unicode_property('1')
    type = long_property('2')
    core_branding_hash = unicode_property('3')
    facebook_app_id = long_property('4')
    ios_app_id = unicode_property('5')
    android_app_id = unicode_property('6')
    creation_time = long_property('7')
    auto_connected_services = typed_property('8', AutoConnectedService, True)
    is_default = bool_property('9')
    qr_templates = typed_property('10', AppQRTemplateTO, True)
    user_regex = unicode_property('11')
    dashboard_email_address = unicode_property('12')
    admin_services = unicode_list_property('13')
    beacon_regions = typed_property('14', BeaconRegionTO, True)
    beacon_major = long_property('15')
    beacon_last_minor = long_property('16')
    demo = bool_property('17')
    beta = bool_property('18')
    mdp_client_id = unicode_property('19')
    mdp_client_secret = unicode_property('20')
    contact_email_address = unicode_property('21')

    @staticmethod
    def fromModel(model, include_qr_templates=False):
        app = AppTO()
        app.id = model.app_id
        app.name = model.name
        app.type = model.type
        app.core_branding_hash = model.core_branding_hash
        app.facebook_app_id = model.facebook_app_id
        app.ios_app_id = model.ios_app_id
        app.android_app_id = model.android_app_id
        app.creation_time = model.creation_time
        if model.auto_connected_services:
            app.auto_connected_services = list(model.auto_connected_services)
        else:
            app.auto_connected_services = list()
        app.is_default = model.is_default
        if include_qr_templates:
            app.qr_templates = [AppQRTemplateTO.fromKeyName(k, i == 0) for i, k in enumerate(model.qrtemplate_keys)]
        else:
            app.qr_templates = list()
        app.user_regex = model.user_regex
        app.dashboard_email_address = model.dashboard_email_address
        app.admin_services = model.admin_services
        app.beacon_regions = map(BeaconRegionTO.from_model, model.beacon_regions())
        app.beacon_major = model.beacon_major
        app.beacon_last_minor = model.beacon_last_minor
        app.demo = model.demo
        app.beta = model.beta
        app.mdp_client_id = model.mdp_client_id
        app.mdp_client_secret = model.mdp_client_secret
        app.contact_email_address = model.contact_email_address
        return app


class AppUserRelationTO(object):
    email = unicode_property('1')
    name = unicode_property('2')
    type = unicode_property('3')  # human / application

    def __init__(self, email, name, type_):
        self.email = email
        self.name = name
        self.type = type_

class AppUserTO(object):
    email = unicode_property('1')
    name = unicode_property('2')
    relations = typed_property('3', AppUserRelationTO, True)

    def __init__(self, user_profile, friendMap):
        self.email = get_human_user_from_app_user(user_profile.user).email()
        self.name = user_profile.name
        self.relations = list()
        if friendMap:
            for f in friendMap.friendDetails:
                self.relations.append(AppUserRelationTO(f.email, f.name, u"human" if f.type == FriendDetail.TYPE_USER else u"application"))

class AppUserListResultTO(object):
    cursor = unicode_property('1')
    users = typed_property('2', AppUserTO, True)


class AppSettingsTO(object):
    wifi_only_downloads = bool_property('1')
    background_fetch_timestamps = long_list_property('2')
    oauth = typed_property('3', OAuthSettings, False)


class CreateAppRequestTO(object):
    app_id = unicode_property('1')
    app_name = unicode_property('2')
    app_type = long_property('3')
    dashboard_email_address = unicode_property('4')
    core_branding = unicode_property('5')
    qr_template_type = unicode_property('6')
    custom_qr_template = unicode_property('7')
    custom_qr_template_color = unicode_property('8')
    auto_connected_services = typed_property('9', AutoConnectedService, True)
    orderable_apps = unicode_list_property('10')
    beacon_regions_to = typed_property('11', BeaconRegionTO, True)
    facebook_registration_enabled = bool_property('12')
    facebook_app_id = long_property('13')
    facebook_secret = unicode_property('14')
    facebook_user_access_token = unicode_property('15')

    @classmethod
    def create(cls, app_id, app_name, app_type, facebook_registration_enabled, facebook_app_id, facebook_secret,
               facebook_user_access_token, dashboard_email_address, core_branding, qr_template_type, custom_qr_template,
               custom_qr_template_color, auto_connected_services, orderable_apps, beacon_regions_to):
        to = cls()
        to.app_id = app_id
        to.app_name = app_name
        to.app_type = app_type
        to.facebook_registration_enabled = facebook_registration_enabled
        to.facebook_app_id = facebook_app_id
        to.facebook_secret = facebook_secret
        to.facebook_user_access_token = facebook_user_access_token
        to.dashboard_email_address = dashboard_email_address
        to.core_branding = core_branding
        to.qr_template_type = qr_template_type
        to.custom_qr_template = custom_qr_template
        to.custom_qr_template_color = custom_qr_template_color
        to.auto_connected_services = auto_connected_services
        to.orderable_apps = orderable_apps
        to.beacon_regions_to = beacon_regions_to
        return to


class FacebookException(object):
    message = unicode_property('1')
    type = unicode_property('2')
    code = long_property('3')
    fbtrace_id = unicode_property('4')
    error_user_msg = unicode_property('5')
    error_user_title = unicode_property('6')
    error_subcode = long_property('7')
    is_transient = bool_property('8')


class FacebookErrorTO(object):
    error = typed_property('1', FacebookException, False)


class FacebookAccessTokenTO(object):
    access_token = unicode_property('1')
    token_type = unicode_property('2')
    error = typed_property('3', FacebookException, False)


class FacebookRoleTO(object):
    ROLE_ADMINISTRATOR = u'administrators'
    ROLE_DEVELOPER = u'developers'
    ROLE_TESTER = u'testers'
    ROLE_INSIGHT_USER = u'insights users'
    user = long_property('1')
    role = unicode_property('2', "enum{'administrators', 'developers', 'testers', 'insights users'}")

    @classmethod
    def create(cls, user_id, role):
        to = cls()
        to.user = user_id
        to.role = role
        return to


class FacebookAppDomainTO(object):
    app_domains = unicode_property('1')
    website_url = unicode_property('2')

    @classmethod
    def create(cls, app_domains, website_url):
        to = cls()
        to.app_domains = app_domains
        to.website_url = website_url
        return to

    @classmethod
    def create_for_bob(cls):
        to = cls()
        if DEBUG:
            to.app_domains = u"['localhost']"
            to.website_url = u"http://localhost"
        else:
            to.app_domains = u"['bob.rogerthat.net']"
            to.website_url = u"https://bob.rogerthat.net"
        return to
