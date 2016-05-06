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
from Cookie import BaseCookie
from urllib import urlencode

import google.appengine.api.users
import webapp2
from webob import exc

from rogerthat.bizz import session
from rogerthat.bizz.session import create_session_for_google_authenticated_user
from rogerthat.consts import DEBUG
from rogerthat.rpc import users
from rogerthat.rpc.context import run_in_context
from rogerthat.settings import get_server_settings
from rogerthat.utils.cookie import parse_cookie


#### Copied from webob.Request ####
def _get_cookies(environ):
    """
    Return a *plain* dictionary of cookies as found in the request.
    """
    source = environ.get('HTTP_COOKIE', '')
    if 'webob._parsed_cookies' in environ:
        vars_, var_source = environ['webob._parsed_cookies']
        if var_source == source:
            return vars_
    vars_ = {}
    if source:
        cookies = BaseCookie()
        cookies.load(source)
        for name in cookies:
            vars_[name] = cookies[name].value
    environ['webob._parsed_cookies'] = (vars_, source)
    return vars_


#### End Copied from webob.Request ####

class RogerthatWSGIApplication(webapp2.WSGIApplication):
    def __init__(self, handlers, set_user=False, redirect_login_required=True, uses_session=True, name=None,
                 google_authenticated=False):
        super(RogerthatWSGIApplication, self).__init__(handlers)
        self.set_user = set_user
        self.redirect_login_required = redirect_login_required
        self.uses_session = uses_session
        self.name = name
        self.google_authenticated = google_authenticated

    def get_user(self, environ):
        if self.uses_session:
            logged_in_as = environ.get('HTTP_X_LOGGED_IN_AS')
            cookies = _get_cookies(environ)
            server_settings = get_server_settings()
            if not server_settings.cookieSessionName in cookies:
                return None, None
            secret = parse_cookie(cookies[server_settings.cookieSessionName])
            if not secret:
                return None, None
            session_, user = session.validate_session(secret, logged_in_as)
            if not session_:
                return None, None
            else:
                return session_, user
        return None, None

    def __call__(self, environ, start_response):
        return run_in_context(self._call_in_context, environ, start_response, _path=environ['PATH_INFO'])

    def _call_in_context(self, environ, start_response, user=None, session_=None):
        from add_1_monkey_patches import start_suppressing

        if DEBUG:
            logging.info("Handling %s on wsgi app %s", environ['PATH_INFO'], self.name)

        if not user:
            if self.set_user:
                user = google.appengine.api.users.get_current_user()
                session_ = None
            else:
                session_, user = self.get_user(environ)
            users.set_user(user, session_)

        if self.google_authenticated and not session_:
            guser = user or google.appengine.api.users.get_current_user()
            if guser:
                session_ = create_session_for_google_authenticated_user(guser)
                users.set_user(guser, session_)

        path = environ['PATH_INFO']
        if path == '/_ah/queue/deferred':
            start_suppressing()

        return webapp2.WSGIApplication.__call__(self, environ, start_response)


class AuthenticatedRogerthatWSGIApplication(RogerthatWSGIApplication):
    def authenticate(self, environ, start_response):
        if DEBUG:
            logging.info("Handling %s on wsgi app %s", environ['PATH_INFO'], self.name)
        if self.redirect_login_required:
            environ['QUERY_STRING'] = urlencode((("continue",
                                                  environ['PATH_INFO'] + "?" + environ['QUERY_STRING'] if environ[
                                                      'QUERY_STRING'] else environ['PATH_INFO']),))
            environ['PATH_INFO'] = "/login_required"
            return webapp2.WSGIApplication.__call__(self, environ, start_response)
        else:
            return exc.HTTPUnauthorized()(environ, start_response)

    def _call_in_context(self, environ, start_response):
        session_, user = self.get_user(environ)
        if not user:
            return self.authenticate(environ, start_response)
        users.set_user(user, session_)
        return RogerthatWSGIApplication._call_in_context(self, environ, start_response, user, session_)
