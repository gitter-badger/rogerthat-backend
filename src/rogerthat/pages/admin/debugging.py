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

from rogerthat.bizz.channel import create_channel_for_current_session
from rogerthat.bizz.debugging import start_admin_debugging, stop_debugging
from rogerthat.bizz.profile import search_users_via_name_or_email
from rogerthat.bizz.system import get_users_currently_forwarding_logs
from rogerthat.consts import APPSCALE, DEBUG
from rogerthat.dal.app import get_all_apps
from rogerthat.rpc import users
from rogerthat.settings import get_server_settings
from rogerthat.to import ReturnStatusTO, RETURNSTATUS_TO_SUCCESS
from rogerthat.to.admin import StartDebuggingReturnStatusTO
from rogerthat.to.service import UserDetailsTO
from rogerthat.utils.app import create_app_user
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments


class UserTools(webapp.RequestHandler):

    def get(self):
        context = dict(log_forwarding_users=sorted(get_users_currently_forwarding_logs(),
                                                   key=lambda x: (x.app_name, x.email)),
                       apps=sorted(get_all_apps(), key=lambda x: x.name),
                       bosh_service=get_server_settings().jabberBoshEndPoint,
                       token=create_channel_for_current_session(),
                       debug=DEBUG,
                       appscale=APPSCALE)
        path = os.path.join(os.path.dirname(__file__), 'debugging.html')
        self.response.out.write(template.render(path, context))


@rest("/mobiadmin/rest/begin_log_forwarding", "post")
@returns(StartDebuggingReturnStatusTO)
@arguments(app=unicode, email=unicode, timeout=unicode)
def begin_log_forwarding(app, email, timeout):
    app_user = create_app_user(users.User(email), app)
    try:
        cfl = start_admin_debugging(app_user, int(timeout))
        return StartDebuggingReturnStatusTO.create(xmpp_target_jid=cfl.xmpp_target,
                                                   xmpp_target_password=cfl.xmpp_target_password,
                                                   type_=cfl.type)
    except Exception, e:
        logging.debug("Failed to start log forwarding", exc_info=True)
        return StartDebuggingReturnStatusTO.create(False, str(e))


@rest("/mobiadmin/rest/end_log_forwarding", "post")
@returns(ReturnStatusTO)
@arguments(app_user_email=unicode, xmpp_target=unicode)
def end_log_forwarding(app_user_email, xmpp_target):
    try:
        stop_debugging(users.User(app_user_email), xmpp_target, None, False)
        return RETURNSTATUS_TO_SUCCESS
    except Exception, e:
        logging.debug("Failed to stop log forwarding", exc_info=True)
        return ReturnStatusTO.create(False, str(e))


@rest("/mobiadmin/rest/search_users", "get")
@returns([UserDetailsTO])
@arguments(name_or_email_term=unicode, app_id=unicode)
def search_users(name_or_email_term, app_id=None):
    return search_users_via_name_or_email(name_or_email_term, app_id)
