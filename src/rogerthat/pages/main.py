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

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from rogerthat.bizz.channel import create_channel_for_current_session
from rogerthat.bizz.profile import create_user_profile
from rogerthat.consts import DEBUG, APPSCALE
from rogerthat.dal.mobile import get_user_active_mobiles_count
from rogerthat.dal.profile import is_trial_service, get_profile_info, get_service_profile
from rogerthat.dal.service import get_service_identities_by_service_identity_users
from rogerthat.restapi.roles import login_as
from rogerthat.rpc import users
from rogerthat.utils.service import get_service_user_from_service_identity_user, create_service_identity_user


class CrossDomainDotXml(webapp.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'text/xml'
        self.response.out.write("""<?xml version="1.0"?>
<!DOCTYPE cross-domain-policy SYSTEM "http://www.macromedia.com/xml/dtds/cross-domain-policy.dtd">
<cross-domain-policy>
  <allow-access-from domain="*" />
</cross-domain-policy>
""")

class RobotsTxt(webapp.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write("""User-agent: *
Disallow:
""")


class MainPage(webapp.RequestHandler):

    def head(self):
        pass

    def get(self):
        user = users.get_current_user()
        session_ = None

        user_services = None
        owning_user_services = None
        should_show_service_picker = False
        session_user = None
        session_service_identity_user = None
        loading_enabled = False
        if user:
            session_ = users.get_current_session()

            # Support reloading
            user_account = self.request.get("user")
            if user_account and user_account != user.email():
                if not login_as(user_account):
                    self.response.write("<html><body>You don't have access to account %s. This problem is logged and may cause legal action against you.</body></html>" % user_account)
                    return
                user = users.get_current_user()
                session_ = users.get_current_session()

            token = create_channel_for_current_session()
            mobile_count = get_user_active_mobiles_count(user)
            my_profile_info = get_profile_info(user, skip_warning=True)
            if not my_profile_info:
                my_profile_info = create_user_profile(user, user.email())

            myavatarid = my_profile_info.avatarId
            if my_profile_info.isServiceIdentity:
                myname = my_profile_info.name or my_profile_info.qualifiedIdentifier or user.email()
            else:
                myname = my_profile_info.name or user.email()
                if my_profile_info.owningServiceEmails and my_profile_info.isCreatedForService:
                    should_show_service_picker = True

                    my_owning_service_identity_users = [create_service_identity_user(users.User(owning_service_email)) for owning_service_email in my_profile_info.owningServiceEmails]
                    my_owning_service_identities = get_service_identities_by_service_identity_users(my_owning_service_identity_users)

                    result = list()
                    for si in my_owning_service_identities:
                        result.append(dict(is_default=si.is_default,
                                           service_user=si.service_user.email(),
                                           service_identity_user=si.service_identity_user.email(),
                                           name=si.name,
                                           description=si.description,
                                           avatar_url=si.avatarUrl))

                    owning_user_services = result

            myname = myname.replace("\\", "\\\\").replace("'", "\\'")
            is_service = my_profile_info.isServiceIdentity
            is_trial_service_ = is_trial_service(get_service_user_from_service_identity_user(user)) if is_service else False
            loading_enabled = not is_service
            user_services = session_.service_users
            session_user = session_.user
            session_service_identity_user = session_.service_identity_user
        else:
            token = None
            mobile_count = 0
            my_profile_info = None
            myavatarid = None
            myname = None
            is_service = False
            is_trial_service_ = False
            user_services = None
            owning_user_services = None

        template_params = {
            'appscale': APPSCALE,
            'continue': "/",
            'debug': DEBUG,
            'user': user,
            'myavatarid': myavatarid,
            'myname': myname,
            'token': token,
            'mobile_count': mobile_count,
            'is_service': is_service,
            'is_trial_service': is_trial_service_,
            'session': users.create_logout_url("/") if user else users.create_login_url("/"),
            "loading_enabled": loading_enabled,
            'user_services': user_services,
            'owning_user_services': owning_user_services,
            'session_user': session_user,
            'session_service_identity_user': session_service_identity_user,
            'service_profile': None,
            'email': self.request.get("email", None)}

        if is_service:
            service_profile = get_service_profile(my_profile_info.service_user)
            template_params['service_profile'] = service_profile

            if not self.request.get('sp') and service_profile.solution:
                params = self.request.GET
                redirect_url = '/%s/' % service_profile.solution
                if params:
                    params = dict((k, v.decode('utf8')) for k, v in params.iteritems())
                    redirect_url = "%s?%s" % (redirect_url, urllib.urlencode(params))
                logging.info("Redirecting to url: %s" % redirect_url)
                self.redirect(redirect_url)
                return

        if user:
            if should_show_service_picker:
                page = "pick_account.html"
            else:
                page = "main.html"
        else:
            template_params["bg_image_uri"] = _get_front_page_image_by_ip(os.environ.get('HTTP_X_FORWARDED_FOR', None))
            page = 'main_unauthenticated.html'

        path = os.path.join(os.path.dirname(__file__), page)
        self.response.out.write(template.render(path, template_params))


FRONT_PAGE_IMAGES = [([41, 189, 192, 0], [41, 189, 223, 255], "/static/images/bg-image-cd.jpg"),
                     ([41, 243, 0, 0], [41, 243, 255, 255], "/static/images/bg-image-cd.jpg"),
                     ([197, 189, 0, 0], [197, 189, 127, 255], "/static/images/bg-image-cd.jpg")]

def _get_front_page_image_by_ip(ip_addresses):
    if ip_addresses:
        exceptions = list()
        splitted = ip_addresses.split(',')
        for ip_address in splitted:
            try:
                ip_parts = [int(part) for part in ip_address.strip().split(".")]
                for from_ip, to_ip, url in FRONT_PAGE_IMAGES:
                    if from_ip <= ip_parts <= to_ip:
                        return url
            except Exception, e:
                logging.debug("Could not determine background image for IP '%s'.", ip_address, exc_info=True)
                exceptions.append(e)
        if splitted and len(splitted) == len(exceptions):
            logging.error("Could not determine background image for IP '%s'. Showing the default background image.",
                          ip_addresses)

    return "/static/images/bg-image.jpg"


class AboutPageHandler(webapp.RequestHandler):

    def get(self):
        user = users.get_current_user()
        path = os.path.join(os.path.dirname(__file__), "about.html")

        self.response.out.write(template.render(path, {
            'user':user,
            'session':users.create_logout_url("/") if user else users.create_login_url("/")}))
