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
import logging

from rogerthat.bizz.service.i18n import excel_export, excel_import
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.service import get_friend_serviceidentity_connection, get_service_identity
from rogerthat.models import ServiceIdentity, ProfileHashIndex
from rogerthat.rpc import users
from rogerthat.rpc.service import BusinessException
from rogerthat.templates import render
from rogerthat.to.friends import FriendTO
from rogerthat.translations import DEFAULT_LANGUAGE
from rogerthat.utils import azzert, safe_file_name, filename_friendly_time
from rogerthat.utils.channel import broadcast_via_iframe_result
from rogerthat.utils.crypto import md5_hex
from rogerthat.utils.service import add_slash_default, create_service_identity_user
from google.appengine.ext import webapp
import webapp2
import xlrd


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


class ServicePageHandler(webapp.RequestHandler):

    def get(self):
        service_email = self.request.GET.get('service')
        azzert(service_email)

        user = users.get_current_user()
        service_identity_user = add_slash_default(users.User(service_email))
        azzert(get_friend_serviceidentity_connection(user, service_identity_user), "%s tried to get service page of service %s, but is not connected" % (user.email(), service_identity_user.email()))

        params = {'service_email': service_email, 'container_id': 'servicePageContainer_%s' % md5_hex(service_email)}
        self.response.out.write(render('service_page', [DEFAULT_LANGUAGE], params, 'web'))

class ServiceMenuItemBrandingHandler(webapp.RequestHandler):

    def get(self):
        service_email = self.request.GET.get('service')
        azzert(service_email)

        user = users.get_current_user()
        service_identity_user = add_slash_default(users.User(service_email))
        azzert(get_friend_serviceidentity_connection(user, service_identity_user), "%s tried to get a menu item page of service %s, but is not connected" % (user.email(), service_identity_user.email()))

        branding = self.request.GET.get('branding')
        azzert(branding)
        params = {'container_id': 'smi_branding_container_%s' % branding, 'branding': branding, 'service_email': service_email}
        self.response.out.write(render('smi_branding', [DEFAULT_LANGUAGE], params, 'web'))

class ServiceAboutPageHandler(webapp.RequestHandler):

    def get(self):
        service_email = self.request.GET.get('service')
        azzert(service_email)

        user = users.get_current_user()
        service_identity_user = add_slash_default(users.User(service_email))
        azzert(get_friend_serviceidentity_connection(user, service_identity_user), "%s tried to get About page of service %s, but is not connected" % (user.email(), service_identity_user.email()))

        service = FriendTO.fromDBFriendMap(get_friends_map(user), service_identity_user, includeServiceDetails=True, targetUser=user)
        azzert(service.type == FriendTO.TYPE_SERVICE)

        params = {'service': service,
                  'service_name': service.name or service.email,
                  'container_id': 'serviceAboutPageContainer_%s' % md5_hex(service_email)}
        self.response.out.write(render('service_about', [DEFAULT_LANGUAGE], params, 'web'))

class EditableTranslationSetExcelDownloadHandler(webapp2.RequestHandler):

    def get(self):
        browser_timezone_str = self.request.get('tz_offset', '0')
        try:
            browser_timezone = int(browser_timezone_str)
        except ValueError:
            logging.warning("Invalid browser timezone offset: [%s]" % browser_timezone_str)
            browser_timezone = 0
        if abs(browser_timezone) > 24 * 3600:
            logging.warning("Invalid browser timezone offset: [%s]" % browser_timezone_str)
            browser_timezone = 0

        service_user = users.get_current_user()
        book, latest_export_timestamp = excel_export(service_user, browser_timezone)

        # Return
        output = StringIO()
        book.save(output)
        output.seek(0)

        filename = "Rogerthat_%s_%s.xls" % (filename_friendly_time(latest_export_timestamp), service_user.email())

        self.response.headers['Content-Type'] = 'application/vnd.ms-excel'
        self.response.headers['Content-Disposition'] = 'attachment; filename=%s' % safe_file_name(filename)
        self.response.out.write(output.getvalue())

class PostEditableTranslationSetExcelHandler(webapp2.RequestHandler):

    def post(self):
        try:
            service_user = users.get_current_user()

            file_ = self.request.POST.get('file').file
            book = xlrd.open_workbook(file_contents=file_.read())

            excel_import(service_user, book)
        except BusinessException, be:
            self.response.out.write(broadcast_via_iframe_result(u'rogerthat.service.translations.post_result', error=be.message))
            return
        except:
            self.response.out.write(broadcast_via_iframe_result(u'rogerthat.service.translations.post_result', error=u"Unknown error has occurred."))
            logging.exception("Failure receiving translations!")
            return
        self.response.out.write(broadcast_via_iframe_result(u'rogerthat.service.translations.post_result'))


class GetServiceAppHandler(webapp2.RequestHandler):

    def get_default_app_id(self, user_hash, identity):
        index = ProfileHashIndex.get(ProfileHashIndex.create_key(user_hash))
        if not index:
            logging.debug('No profile found with user_hash %s', user_hash)
            return None

        si_user = create_service_identity_user(index.user, identity)
        si = get_service_identity(si_user)
        if not si:
            logging.debug('Service identity not found: %s', si_user.email())
            return None
        return si.app_id


    def get(self):
        user_hash = self.request.GET['user']
        identity = self.request.GET.get('service_identity', ServiceIdentity.DEFAULT)
        if identity == 'None':
            identity = ServiceIdentity.DEFAULT

        self.response.out.write(json.dumps(dict(app_id=self.get_default_app_id(user_hash, identity))))
