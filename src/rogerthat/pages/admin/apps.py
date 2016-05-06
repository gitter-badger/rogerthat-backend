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

import hashlib
import json
import logging
import os
import urllib
import zlib
from cgi import FieldStorage
from zipfile import ZipFile, BadZipfile

import jinja2
import webapp2
from google.appengine.ext import webapp, db

from rogerthat.bizz.app import validate_user_regex
from rogerthat.bizz.branding import BrandingValidationException, store_branding_zip
from rogerthat.bizz.job import run_job, hookup_with_default_services
from rogerthat.bizz.job.update_beacon_regions import schedule_update_beacon_regions_for_all_users
from rogerthat.bizz.qrtemplate import store_template
from rogerthat.bizz.service import create_qr_template_key_name
from rogerthat.bizz.system import qrcode
from rogerthat.dal import put_and_invalidate_cache
from rogerthat.dal.app import get_app_by_id, get_visible_apps, get_default_app_key, get_default_app, get_apps
from rogerthat.dal.profile import get_user_profile_keys_by_app_id, is_service_identity_user, get_profile_key
from rogerthat.dal.roles import get_service_roles_by_ids, list_service_roles
from rogerthat.dal.service import get_service_identity
from rogerthat.models import App, UserProfile, ServiceIdentity, QRTemplate, BeaconRegion, AppTranslations
from rogerthat.models.properties.app import AutoConnectedService, AutoConnectedServices
from rogerthat.rpc import users
from rogerthat.rpc.service import BusinessException
from rogerthat.to import ReturnStatusTO
from rogerthat.to.app import AppTO
from rogerthat.to.roles import RolesReturnStatusTO, RoleTO
from rogerthat.utils import now, bizz_check
from rogerthat.utils.service import get_service_user_from_service_identity_user, add_slash_default
from rogerthat.utils.transactions import on_trans_committed
from mcfw.cache import invalidate_cache
from mcfw.restapi import rest
from mcfw.rpc import parse_complex_value, returns, arguments, serialize_complex_value

JINJA_ENVIRONMENT = jinja2.Environment(loader=jinja2.FileSystemLoader([os.path.join(os.path.dirname(__file__))]))


class AppsTools(webapp.RequestHandler):

    def get_request_params(self):
        return {p: self.request.get(p) for p in ('result', 'app_id', 'name', 'app_type', 'fb_app_id', 'ios_app_id',
                                                 'android_app_id', 'dashboard_email_address', 'contact_email_address',
                                                 'user_regex', 'demo', 'beta', 'mdp_client_id', 'mdp_client_secret')}

    def write_app_details(self, app):
        template = JINJA_ENVIRONMENT.get_template('app_detail.html')
        context = self.get_request_params()
        context['app_types'] = sorted(App.TYPE_STRINGS.items(), key=lambda (k, v): v.lower())
        if app:
            context["id"] = app.app_id,
            context["app"] = app
        else:
            context["new_app"] = 1
            context['all_apps'] = list(get_apps([App.APP_TYPE_CITY_APP]))

        self.response.out.write(template.render(context))

    def get(self):
        url_app_id = self.request.get('id')
        if url_app_id:
            app = get_app_by_id(url_app_id)
            if app:
                self.write_app_details(app)
                return

        url_new_app = self.request.get('new_app')
        if url_new_app:
            self.write_app_details(None)
            return

        rogerthat_app = get_app_by_id(App.APP_ID_ROGERTHAT)
        if rogerthat_app is None:
            rogerthat_app = App(key=App.create_key(App.APP_ID_ROGERTHAT))
            rogerthat_app.name = "Rogerthat"
            rogerthat_app.type = App.APP_TYPE_ROGERTHAT
            rogerthat_app.creation_time = now()
            rogerthat_app.visible = False
            rogerthat_app.put()

        template = JINJA_ENVIRONMENT.get_template('apps.html')
        context = self.get_request_params()
        context['apps'] = sorted(get_visible_apps(), key=lambda app: (app.is_default, app.name))
        self.response.out.write(template.render(context))


class CreateAppHandler(webapp.RequestHandler):

    def post(self):
        success = False
        app_id = self.request.POST.get("app_id", None)
        name = self.request.POST.get("name", None)
        app_type = self.request.POST.get("app_type", None)
        fb_app_id = self.request.POST.get("fb_app_id", None)
        ios_app_id = self.request.POST.get("ios_app_id", None)
        android_app_id = self.request.POST.get("android_app_id", None)
        dashboard_email_address = self.request.POST.get('dashboard_email_address', None)
        contact_email_address = self.request.POST.get("contact_email_address", None)
        user_regex = self.request.POST.get("user_regex", None)
        qr_templates_count = int(self.request.POST.get("qr_templates_count", 0))
        default_qr_template_index = int(self.request.POST.get("default_qr_template_index", 0))
        auto_connected_services_string = self.request.POST.get("auto_connected_services", "[]")
        logging.debug("auto_connected_services = %s", auto_connected_services_string)
        beacon_major_str = self.request.POST.get("beacon_major", 0)
        beacon_major = int(beacon_major_str) if beacon_major_str else 0
        demo = bool(self.request.POST.get("demo", ''))
        beta = bool(self.request.POST.get("beta", ''))
        mdp_client_id = self.request.POST.get('mdp_client_id', None)
        mdp_client_secret = self.request.POST.get('mdp_client_secret', None)
        orderable_apps = self.request.get_all('orderable_apps')
        auto_connected_services = parse_complex_value(AutoConnectedService,
                                                      json.loads(auto_connected_services_string),
                                                      True)
        admin_services = json.loads(self.request.POST.get('admin_services', '[]'))
        beacon_regions = json.loads(self.request.POST.get("beacon_regions", "[]"))

        try:
            app_type = None if not app_type else int(app_type)
        except Exception:
            app_type = None

        try:
            fb_app_id = None if not fb_app_id else int(fb_app_id)
        except Exception:
            fb_app_id = None

        if not app_id:
            result = "Failed to create new app (app_id was empty)!"
        elif [c for c in app_id if c not in '-abcdefghijklmnopqrstuvwxyz0123456789']:
            result = "App ids should only contain (-, lower case alphabet characters and numbers)"
        elif not name:
            result = "Failed to create new app (name was empty)!"
        elif app_type is None:
            result = "Failed to create new app (app_type was empty)!"
        elif not ios_app_id:
            result = "Failed to create new app (ios_app_id was empty)!"
        elif not android_app_id:
            result = "Failed to create new app (android_app_id was empty)!"
        elif not dashboard_email_address:
            result = "Failed to create new app (dashboard_email_address was empty)!"
        else:
            try:
                if user_regex:
                    validate_user_regex(user_regex)

                zip_stream = self.request.POST.get('core_branding').file
                zip_stream.seek(0)
                try:
                    zip_ = ZipFile(zip_stream)
                except BadZipfile, e:
                    raise BrandingValidationException(e.message)

                branding = store_branding_zip(None, zip_, u"Core branding of %s" % app_id)

                app = App(key=App.create_key(app_id))
                to_be_put = []
                app.qrtemplate_keys = []
                for i in xrange(qr_templates_count):
                    file_ = self.request.POST.get('qr_template_%s' % i)
                    description = self.request.POST.get("qr_template_description_%s" % i)
                    color = self.request.POST.get("qr_template_color_%s" % i)
                    file_ = file_.file.getvalue() if isinstance(file_, FieldStorage) else None
                    key_name = create_qr_template_key_name(app_id, description)
                    store_template(None, file_, description, color, key_name)
                    if default_qr_template_index == i:
                        app.qrtemplate_keys.insert(0, key_name)
                    else:
                        app.qrtemplate_keys.append(key_name)

                app.name = name
                app.type = app_type
                app.core_branding_hash = branding.hash
                app.facebook_app_id = fb_app_id
                app.ios_app_id = ios_app_id
                app.android_app_id = android_app_id
                app.dashboard_email_address = dashboard_email_address
                app.contact_email_address = contact_email_address
                app.user_regex = user_regex
                app.creation_time = now()
                app.is_default = get_default_app_key() is None
                app.demo = demo
                app.beta = beta
                app.mdp_client_id = mdp_client_id or None
                app.mdp_client_secret = mdp_client_secret or None

                app.auto_connected_services = AutoConnectedServices()
                for acs in auto_connected_services:
                    service_identity_user = add_slash_default(users.User(acs.service_identity_email))
                    si = get_service_identity(service_identity_user)
                    bizz_check(si, "ServiceIdentity %s not found" % service_identity_user)
                    if app_id not in si.appIds:
                        si.appIds.append(app_id)
                        to_be_put.append(si)

                    acs.service_identity_email = service_identity_user.email()
                    app.auto_connected_services.add(acs)

                admin_profiles = db.get([get_profile_key(u) for u in map(users.User, admin_services)])
                non_existing = list()
                for admin_email, admin_profile in zip(admin_services, admin_profiles):
                    if not admin_profile:
                        non_existing.append(admin_email)
                bizz_check(not non_existing, "Non existing services specified: %s" % non_existing)
                app.admin_services = admin_services
                app.beacon_major = beacon_major
                app.beacon_last_minor = 0
                put_and_invalidate_cache(*to_be_put)

                to_be_put = []
                for beacon_region in beacon_regions:
                    uuid = beacon_region.get("uuid")
                    major = beacon_region.get("major")
                    minor = beacon_region.get("minor")
                    br = BeaconRegion(key=BeaconRegion.create_key(app.key(), uuid, major, minor))
                    br.uuid = uuid.lower()
                    br.major = major
                    br.minor = minor
                    br.creation_time = now()
                    to_be_put.append(br)

                app.orderable_app_ids = list(orderable_apps)
                apps = db.get(map(App.create_key, app.orderable_app_ids))
                for a in apps:
                    a.orderable_app_ids.append(app_id)
                    to_be_put.append(a)
                to_be_put.append(app)
                put_and_invalidate_cache(*to_be_put)

                for acs in app.auto_connected_services:
                    logging.info("There is a new auto-connected service: %s", acs.service_identity_email)
                    run_job(get_user_profile_keys_by_app_id, [app_id],
                            hookup_with_default_services.run_for_auto_connected_service, [acs, None])

                result = "Created new app!"
                success = True
            except BusinessException, e:
                logging.info("BusinessException: %s", e, exc_info=1)
                result = e.message
            except Exception, e:
                logging.exception(str(e), exc_info=1)
                result = "Unknown error has occurred."

        rr = {"result": result}
        if app_id:
            rr["app_id"] = app_id
        if name:
            rr["name"] = name
        if app_type is not None:
            rr["app_type"] = app_type
        if fb_app_id:
            rr["fb_app_id"] = fb_app_id
        if ios_app_id:
            rr["ios_app_id"] = ios_app_id
        if android_app_id:
            rr["android_app_id"] = android_app_id
        if dashboard_email_address:
            rr["dashboard_email_address"] = dashboard_email_address
        if contact_email_address:
            rr["contact_email_address"] = contact_email_address
        if user_regex:
            rr["user_regex"] = user_regex

        if not success:
            rr["new_app"] = 1
        self.redirect("/mobiadmin/apps?%s" % urllib.urlencode(rr))

class GetAppHandler(webapp.RequestHandler):

    def post(self):
        app_id = self.request.POST.get("app_id", None)
        self.response.headers['Content-Type'] = 'text/json'
        if app_id:
            app = get_app_by_id(app_id)
            if app:
                app_dict = serialize_complex_value(AppTO.fromModel(app, True), AppTO, False)
                # append service_role_names to app_dict
                for acs in app_dict['auto_connected_services']:
                    service_user = get_service_user_from_service_identity_user(users.User(acs['service_identity_email']))
                    acs['service_role_names'] = [r.name for r in get_service_roles_by_ids(service_user,
                                                                                          acs['service_roles'])]
                logging.debug("Returning %s", app_dict)
                self.response.out.write(json.dumps(dict(success=True, errormsg=None, app=app_dict)))
                return
        self.response.out.write(json.dumps(dict(success=False, errormsg=u"Could not find app")))


class UpdateAppHandler(webapp.RequestHandler):

    def post(self):
        success = False
        app_id = self.request.POST.get("app_id_hidden", None)
        name = self.request.POST.get("name", None)
        app_type = self.request.POST.get("app_type", None)
        fb_app_id = self.request.POST.get("fb_app_id", None)
        ios_app_id = self.request.POST.get("ios_app_id", None)
        android_app_id = self.request.POST.get("android_app_id", None)
        dashboard_email_address = self.request.POST.get("dashboard_email_address", None)
        contact_email_address = self.request.POST.get("contact_email_address", None)
        user_regex = self.request.POST.get("user_regex", None)
        qr_templates_count = int(self.request.POST.get("qr_templates_count", 0))
        default_qr_template_index = int(self.request.POST.get("default_qr_template_index", 0))
        has_core_branding = self.request.POST.get("has_core_branding", None)
        auto_connected_services_string = self.request.POST.get("auto_connected_services", "[]")
        logging.debug("auto_connected_services = %s", auto_connected_services_string)
        auto_connected_services = parse_complex_value(AutoConnectedService,
                                                      json.loads(auto_connected_services_string),
                                                      True)
        admin_services = json.loads(self.request.POST.get('admin_services', '[]'))
        qr_templates_to_delete = json.loads(self.request.POST.get("qr_templates_to_delete", "[]"))
        beacon_regions = json.loads(self.request.POST.get("beacon_regions", "[]"))
        beacon_major_str = self.request.POST.get("beacon_major", 0)
        beacon_major = int(beacon_major_str) if beacon_major_str else 0
        demo = bool(self.request.POST.get("demo", ''))
        beta = bool(self.request.POST.get("beta", ''))
        mdp_client_id = self.request.POST.get('mdp_client_id', None)
        mdp_client_secret = self.request.POST.get('mdp_client_secret', None)

        try:
            has_core_branding = None if not has_core_branding else int(has_core_branding)
        except Exception:
            has_core_branding = None

        try:
            app_type = None if not app_type else int(app_type)
        except Exception:
            app_type = None

        try:
            fb_app_id = None if not fb_app_id else int(fb_app_id)
        except Exception:
            fb_app_id = None

        if not app_id:
            result = "BUG!!! Failed to update app (app_id was empty)!"
        if not name:
            result = "Failed to update app (name was empty)!"
        elif app_type is None:
            result = "Failed to update app (app_type was empty)!"
        elif not ios_app_id:
            result = "Failed to update app (ios_app_id was empty)!"
        elif not android_app_id:
            result = "Failed to update app (android_app_id was empty)!"
        elif not dashboard_email_address:
            result = "Failed to update app (dashboard_email_address was empty)!"
        else:
            app = get_app_by_id(app_id)
            if app:
                try:
                    if user_regex:
                        validate_user_regex(user_regex)

                    to_be_put = [app]
                    app.name = name
                    app.type = app_type

                    if has_core_branding:
                        zip_stream = self.request.POST.get('core_branding').file
                        zip_stream.seek(0)
                        try:
                            zip_ = ZipFile(zip_stream)
                        except BadZipfile, e:
                            raise BrandingValidationException(e.message)

                        branding = store_branding_zip(None, zip_, u"Core branding of %s" % app_id)
                        app.core_branding_hash = branding.hash

                    for qr_template_key_name in qr_templates_to_delete:
                        app.qrtemplate_keys.remove(qr_template_key_name)

                    for i in xrange(qr_templates_count):
                        description = self.request.POST.get("qr_template_description_%s" % i)
                        key_name = create_qr_template_key_name(app_id, description)
                        if self.request.POST.get('qr_template_new_%s' % i) == "1":
                            file_ = self.request.POST.get('qr_template_%s' % i)
                            color = self.request.POST.get("qr_template_color_%s" % i)
                            file_ = file_.file.getvalue() if isinstance(file_, FieldStorage) else None
                            store_template(None, file_, description, color, key_name)
                            if default_qr_template_index == i:
                                app.qrtemplate_keys.insert(0, key_name)
                            else:
                                app.qrtemplate_keys.append(key_name)
                        else:
                            if default_qr_template_index == i:
                                app.qrtemplate_keys.remove(key_name)
                                app.qrtemplate_keys.insert(0, key_name)

                    app.facebook_app_id = fb_app_id
                    app.ios_app_id = ios_app_id
                    app.android_app_id = android_app_id
                    app.dashboard_email_address = dashboard_email_address
                    app.contact_email_address = contact_email_address
                    app.user_regex = user_regex
                    app.demo = demo
                    app.beta = beta
                    app.mdp_client_id = mdp_client_id or None
                    app.mdp_client_secret = mdp_client_secret or None

                    old_auto_connected_services = {acs.service_identity_email for acs in app.auto_connected_services}

                    app.auto_connected_services = AutoConnectedServices()
                    for acs in auto_connected_services:
                        service_identity_user = add_slash_default(users.User(acs.service_identity_email))
                        si = get_service_identity(service_identity_user)
                        bizz_check(si, "ServiceIdentity %s not found" % service_identity_user)
                        if app_id not in si.appIds:
                            si.appIds.append(app_id)
                            to_be_put.append(si)

                        acs.service_identity_email = service_identity_user.email()
                        app.auto_connected_services.add(acs)

                    admin_profiles = db.get([get_profile_key(u) for u in map(users.User, admin_services)])
                    non_existing = list()
                    for admin_email, admin_profile in zip(admin_services, admin_profiles):
                        if not admin_profile:
                            non_existing.append(admin_email)
                    bizz_check(not non_existing, "Non existing services specified: %s" % non_existing)
                    app.admin_services = admin_services

                    old_beacon_regions = list(app.beacon_regions(keys_only=True))
                    new_beacon_regions = list()

                    should_update_beacon_regions = False

                    for beacon_region in beacon_regions:
                        uuid = beacon_region.get("uuid")
                        major = beacon_region.get("major")
                        minor = beacon_region.get("minor")
                        br_key = BeaconRegion.create_key(app.key(), uuid, major, minor)
                        new_beacon_regions.append(br_key)
                        if br_key not in old_beacon_regions:
                            should_update_beacon_regions = True
                            br = BeaconRegion(key=br_key)
                            br.uuid = uuid.lower()
                            br.major = major
                            br.minor = minor
                            br.creation_time = now()
                            to_be_put.append(br)

                    to_be_deleted = []
                    for beacon_region_key in old_beacon_regions:
                        if beacon_region_key not in new_beacon_regions:
                            should_update_beacon_regions = True
                            to_be_deleted.append(beacon_region_key)

                    app.beacon_major = beacon_major
                    app.beacon_last_minor = app.beacon_last_minor if app.beacon_last_minor else 0

                    put_and_invalidate_cache(*to_be_put)
                    if to_be_deleted:
                        db.delete(db.get(to_be_deleted))

                    for acs in app.auto_connected_services:
                        if acs.service_identity_email not in old_auto_connected_services:
                            logging.info("There is a new auto-connected service: %s", acs.service_identity_email)
                            run_job(get_user_profile_keys_by_app_id, [app_id],
                                    hookup_with_default_services.run_for_auto_connected_service, [acs, None])

                    if should_update_beacon_regions:
                        schedule_update_beacon_regions_for_all_users(app_id)

                    result = "Updated app!"
                    success = True
                except BusinessException, e:
                    logging.info("BusinessException: %s", e, exc_info=1)
                    result = e.message
                except Exception, e:
                    logging.exception(str(e), exc_info=1)
                    result = "Unknown error has occurred."
            else:
                result = "Could not update unknown app"

        rr = {"result": result}
        if not success:
            rr["id"] = app_id
        self.redirect("/mobiadmin/apps?%s" % urllib.urlencode(rr))


class DeleteAppHandler(webapp.RequestHandler):

    def post(self):
        app_id = self.request.POST.get("app_id", None)

        self.response.headers['Content-Type'] = 'text/json'
        if not app_id:
            self.response.out.write(json.dumps(dict(success=False, errormsg=u"Failed to delete app (app_id was empty)!")))
        else:
            app = get_app_by_id(app_id)
            if app:
                if len(UserProfile.all().filter('app_id =', app_id).fetch(1)) > 0:
                    self.response.out.write(json.dumps(dict(success=False, errormsg=u"Failed to remove app (has users)")))
                else:
                    if len(ServiceIdentity.all().filter('app_ids =', app_id).fetch(1)) > 0:
                        self.response.out.write(json.dumps(dict(success=False, errormsg=u"Failed to remove app (service_identies contain app)")))
                    else:
                        app.delete()
                        self.response.out.write(json.dumps(dict(success=True, errormsg=u"Successfully removed app!")))
            else:
                self.response.out.write(json.dumps(dict(success=False, errormsg=u"Could not delete unknown app")))


class UploadAppAppleCertsHandler(webapp.RequestHandler):

    def post(self):
        from rogerthat.settings import get_server_settings
        settings = get_server_settings()
        secret = self.request.headers.get("X-Nuntiuz-Secret", None)
        if secret != settings.jabberSecret:
            logging.error(u"Received unauthenticated callback response, ignoring ...")
            return

        app_id = self.request.POST.get("app_id", None)
        cert = self.request.POST.get("cert", None)
        key = self.request.POST.get("key", None)
        valid_until = int(self.request.POST.get("valid_until", None))
        checksum = self.request.POST.get("checksum", None)

        digester = hashlib.sha256()
        digester.update(app_id)
        digester.update(cert)
        digester.update(app_id)
        digester.update(key)
        digester.update(app_id)
        digester.update(str(valid_until))
        digester.update(app_id)
        checksum_calculated = digester.hexdigest()

        if checksum != checksum_calculated:
            self.response.write("Checksum does not pass.")
            self.error(400)
            return

        app = get_app_by_id(app_id)
        if not app:
            self.response.write("App not found.")
            self.error(400)
            return

        app.apple_push_cert = cert
        app.apple_push_key = key
        app.apple_push_cert_valid_until = valid_until
        app.put()

        self.response.write("Certificate and key successfully updated!")


class QRTemplateHandler(webapp.RequestHandler):

    def get(self):
        from rogerthat.settings import get_server_settings
        key_name = self.request.get("key_name")
        template = QRTemplate.get_by_key_name(key_name)
        self.response.headers['Content-Type'] = "image/png"
        url = "%s/" % get_server_settings().baseUrl
        self.response.out.write(qrcode(url, template.blob, map(int, template.body_color), False))


class AppTranslationsHandler(webapp2.RequestHandler):
    def get(self, app_id):
        template = JINJA_ENVIRONMENT.get_template('app_translations.html')
        js_template = JINJA_ENVIRONMENT.get_template('app_translations_part.html').render()
        app = App.get(App.create_key(app_id))
        if not app:
            self.response.out.write('app %s does not exist' % app_id)
            return
        app_translations_key = AppTranslations.create_key(app_id)
        translations = AppTranslations.get_or_insert(app_translations_key.name(), parent=app_translations_key.parent())
        parameters = {
            'templates': json.dumps({'app_translations_part': js_template}),
            'translations': json.dumps(
                zlib.decompress(translations.translations) if translations.translations else None),
            'app': json.dumps(serialize_complex_value(AppTO.fromModel(app), AppTO, False))
        }
        self.response.out.write(template.render(parameters))


@rest("/mobiadmin/apps/translations/app/save", "post")
@returns(ReturnStatusTO)
@arguments(app_id=unicode, translations=unicode)
def rest_save_translations(app_id, translations):
    trans = AppTranslations.get(AppTranslations.create_key(app_id))
    trans.translations = zlib.compress(translations.encode('utf-8'))
    put_and_invalidate_cache(trans)
    return ReturnStatusTO.create(True, None)


@rest("/mobiadmin/apps/get_service_roles", "get")
@returns(RolesReturnStatusTO)
@arguments(email=unicode)
def get_service_roles(email):
    service_identity_user = add_slash_default(users.User(email))
    if not email.endswith('/') and is_service_identity_user(service_identity_user):
        service_user = get_service_user_from_service_identity_user(service_identity_user)
        return RolesReturnStatusTO.create(roles=map(RoleTO.fromServiceRole, list_service_roles(service_user)),
                                          service_identity_email=service_identity_user.email())
    else:
        return RolesReturnStatusTO.create(success=False,
                                          errormsg=u"Service identity not found: %s" % service_identity_user.email())


@rest("/mobiadmin/apps/set_default_app", "post")
@returns()
@arguments(app_id=unicode)
def set_default_app(app_id):
    def trans(old_default_app_key):
        new_default_app = get_app_by_id(app_id)
        if new_default_app.key() == old_default_app_key:
            return

        new_default_app.is_default = True

        if old_default_app_key:
            old_default_app = App.get(old_default_app_key)
            old_default_app.is_default = False
            put_and_invalidate_cache(new_default_app, old_default_app)
            on_trans_committed(logging.info, "Default app updated from %s (%s) to %s (%s)", old_default_app.app_id,
                               old_default_app.name, new_default_app.app_id, new_default_app.name)
        else:
            put_and_invalidate_cache(new_default_app)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans, get_default_app_key())

    invalidate_cache(get_default_app)
    invalidate_cache(get_default_app_key)
