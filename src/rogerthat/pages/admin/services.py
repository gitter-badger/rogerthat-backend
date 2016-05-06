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
import os
import urllib

from rogerthat.bizz.beacon import add_new_beacon
from rogerthat.bizz.job.update_friends import schedule_update_all_friends_of_service_user
from rogerthat.bizz.service import convert_user_to_service, configure_mobidick, promote_trial_service
from rogerthat.bizz.service.yourservicehere import signup
from rogerthat.dal.friend import get_friend_category_by_id, get_friend_categories
from rogerthat.dal.profile import get_service_profile, get_profile_info, is_trial_service
from rogerthat.dal.service import get_service_identity
from rogerthat.rpc import users
from rogerthat.utils.service import create_service_identity_user
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template


class ServiceTools(webapp.RequestHandler):
    URL = "/mobiadmin/services?"
    ARGS = (("result", ""), ("cts_email", ""), ("cts_checked", "CHECKED"), ("ctr_email", ""), ("ctr_description", ""),
            ("cts_email", ""), ("rtr_email", ""), ("rtr_qi", ""), ("ssm_email", ""), ("ssc_email", ""),
            ("ars_email", ""), ("ars_name", ""), ("ars_branding_url", ""), ("ars_menu_item_color", ""),
            ("ars_address", ""), ("ars_phone_number", ""), ("ars_language", ""), ("ars_currency", ""),
            ("ars_redeploy_checked", ""))

    def redirect(self, **kwargs):
        params = [(k.encode('utf8'), v.encode('utf8')) for k, v in kwargs.items()]
        logging.info(params)
        return super(ServiceTools, self).redirect(str("/mobiadmin/services?") + urllib.urlencode(params, False))

    def get(self):
        context = dict(((key, self.request.get(key, default)) for key, default in self.ARGS))
        context['ssc_categories'] = get_friend_categories()
        path = os.path.join(os.path.dirname(__file__), 'services.html')
        self.response.out.write(template.render(path, context))

class CreateTrialService(ServiceTools):

    def post(self):
        owner = self.request.POST.get("owner", None)
        email = self.request.POST.get("email", None)
        name = self.request.POST.get("name", None)
        description = self.request.POST.get("description", None)
        if not email:
            self.redirect(result="Supply the email of the user!")
            return

        owner = users.User(owner)
        profile_info = get_profile_info(owner)
        if not profile_info:
            self.redirect(result="Owner %s is not found!" % owner.email(), rts_owner=owner.email(), rts_email=email, rts_name=name, rts_description=description)
            return
        if profile_info.isServiceIdentity:
            self.redirect(result="Owner must be a human!" % owner.email(), rts_owner=owner.email(), rts_email=email, rts_name=name, rts_description=description)
            return

        user = users.User(email)
        profile_info = get_profile_info(user)
        if not profile_info:
            signup(owner, name, description, False, email)
            self.redirect(result="Trial account created and email with credentials sent to %s" % owner.email())
        else:
            if profile_info.isServiceIdentity:
                self.redirect(result="Service %s already exists!" % email, rts_owner=owner.email(), rts_email=email, rts_name=name, rts_description=description)
            else:
                self.redirect(result="A user account with email %s already exists!" % email, rts_owner=owner.email(), rts_email=email, rts_name=name, rts_description=description)

class ReleaseTrialService(ServiceTools):

    def post(self):
        email = self.request.POST.get("email", None)
        qi = self.request.POST.get("qi", None)
        if not (email and qi):
            self.redirect(result="Supply the email of the user and provide the qualified identifier!")
            return
        service_user = users.User(email)
        profile_info = get_profile_info(service_user)
        if not profile_info:
            self.redirect(result="Service %s is not found!" % email, rtr_email=email, rtr_qi=qi)
            return
        if not (profile_info.isServiceIdentity and is_trial_service(service_user)):
            self.redirect(result="%s is not a trial service account! Please enter the Rogerthat trial service account you want to promote." % email, rts_email=email, rtr_email=email, rtr_qi=qi)
            return
        try:
            promote_trial_service(service_user, qi)
            self.redirect(result="Service %s successfully promoted!" % service_user)
        except Exception, e:
            logging.warn(str(e), exc_info=1)
            self.redirect(result=str(e), rtr_email=email, rtr_qi=qi)

class ConvertToService(ServiceTools):

    def post(self):
        email = self.request.POST.get("email", None)
        if not email:
            self.redirect(result="Supply the email of the user!")
            return
        mobidick = self.request.POST.get("mobidick", "")
        logging.info("Email: %s" % email)
        logging.info("Mobidick: %s" % mobidick)
        user = users.User(email)
        profile_info = get_profile_info(user)
        if not profile_info:
            self.redirect(result="User %s is not found!" % email, cts_email=email)
            return
        if profile_info.isServiceIdentity:
            service_profile = get_service_profile(user)
            if service_profile.callBackURI != "mobidick" and mobidick == "CHECKED":
                try:
                    configure_mobidick(user)
                    self.redirect(result="Configured %s to use mobidick backend!" % email)
                except Exception, e:
                    logging.exception(e)
                    self.redirect(result=str(e), cts_email=email, cts_mobidick=mobidick)
            else:
                self.redirect(result="The user is already a service!")
            return
        try:
            convert_user_to_service(user)
            if mobidick == "CHECKED":
                configure_mobidick(user)
            self.redirect(result="%s is now a service account!" % email)
        except Exception, e:
            logging.warn(str(e), exc_info=1)
            self.redirect(result=str(e), cts_email=email)

class SetServiceMonitoring(ServiceTools):

    def post(self):
        enable = bool(self.request.POST.get("enable_monitoring"))
        email = self.request.POST.get("email")
        if not email:
            self.redirect(result="Supply the email of the user!")
            return
        enabled_str = "enabled" if enable else "disabled"
        logging.info("Setting monitoring to %s for email: %s" % (enabled_str, email))
        service_user = users.User(email)
        service_profile = get_service_profile(service_user)
        if not service_profile:
            self.redirect(result="User %s is not found!" % email, ssm_email=email)
            return

        service_profile.monitor = enable
        service_profile.put()

        self.redirect(result="Monitoring for service %s successfully %s!" % (email, enabled_str))


class SetServiceCategory(ServiceTools):

    def post(self):
        category_id = self.request.POST.get("category_id")
        email = self.request.POST.get("email")
        if not email:
            self.redirect(result="Supply the email of the user!")
            return

        service_user = users.User(email)
        service_profile = get_service_profile(service_user)
        if not service_profile:
            self.redirect(result="User %s is not found!" % email, ssc_email=email)
            return

        if not get_friend_category_by_id(category_id):
            self.redirect(result="Category with ID %s not found!" % category_id, ssc_email=email)
            return

        service_profile.category_id = category_id or None
        service_profile.version += 1
        service_profile.put()

        schedule_update_all_friends_of_service_user(service_profile, force=True)

        self.redirect(result="Category ID for service %s successfully updated to %s" % (email, category_id))

class NewBeaconForServiceIdentityUser(ServiceTools):

    def post(self):
        uuid = self.request.get('uuid')
        major = self.request.get('major')
        minor = self.request.get('minor')
        tag = self.request.get('tag')
        service = self.request.get('service')
        identity = self.request.get('identity')

        if not (uuid and major and minor and service and identity):
            return self.redirect(result='Please supply all parameters.')

        logging.info("New beacon added uuid: %s major: %s minor: %s for: %s/%s" % (uuid, major, minor, service, identity))
        try:
            service_user = users.User(service)
            service_identity_user = create_service_identity_user(service_user, identity)
            si = get_service_identity(service_identity_user)
            if not si:
                self.redirect(result='Service not found.')
                return
            name = "%s|%s" % (major, minor)

            added = add_new_beacon(uuid, name, tag, service_identity_user)
            if added:
                self.redirect(result='Added beacon with name: %s for: %s' % (name, service_identity_user))
            else:
                self.redirect(result='Beacon already exists: %s for: %s' % (name, service_identity_user))
        except Exception, e:
            logging.warn(str(e), exc_info=1)
            self.redirect(result=str(e))
