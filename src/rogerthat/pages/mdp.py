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

import base64
import json
import logging
import urllib
import uuid

from rogerthat.dal.app import get_app_by_id
from rogerthat.dal.profile import get_user_profile
from rogerthat.models import MyDigiPassProfilePointer, MyDigiPassState
from rogerthat.models.properties.forms import MyDigiPassEidProfile, MyDigiPassEidAddress, MyDigiPassAddress, \
    MyDigiPassProfile, MdpScope
from rogerthat.pages import UserAwareRequestHandler
from rogerthat.rpc import users
from rogerthat.rpc.service import BusinessException
from rogerthat.to.messaging.forms import MyDigiPassWidgetResultTO
from rogerthat.translations import localize
from google.appengine.api import urlfetch
from google.appengine.ext import db
from mcfw.properties import azzert
from mcfw.rpc import serialize_complex_value, parse_complex_value
from mcfw.utils import Enum


class MissingScopesException(BusinessException):
    def __init__(self, user_language, missing_scopes):
        localized_scopes = set()
        for scope in missing_scopes:
            if scope == MdpScope.EMAIL:
                localized_scopes.add(localize(user_language, 'E-mail address'))
            elif scope == MdpScope.ADDRESS:
                localized_scopes.add(localize(user_language, 'Address'))
            elif scope == MdpScope.PHONE:
                localized_scopes.add(localize(user_language, 'Phone number'))
            elif scope == MdpScope.PROFILE:
                localized_scopes.add(localize(user_language, 'Profile'))
            elif scope in (MdpScope.EID_ADDRESS, MdpScope.EID_PHOTO, MdpScope.EID_PROFILE):
                localized_scopes.add(localize(user_language, 'eID data'))
        missing_data = u''.join((u'\n• %s' % scope for scope in sorted(localized_scopes)))
        BusinessException.__init__(self, localize(user_language, u'mdp_missing_scopes', missing_data=missing_data))


class MdpEndpoint(Enum):
    USER_DATA = 'user_data'
    EID_DATA = 'eid_data'
    EID_PHOTO = 'eid_photo_data'


def get_redirect_uri(app_id):
    return u'mdp-%s://x-callback-url/mdp_callback' % app_id


class InitMyDigiPassSessionHandler(UserAwareRequestHandler):

    def get(self):
        if not self.set_user():
            self.abort(401)
            return

        app_user = users.get_current_user()
        app_id = users.get_current_app_id()
        app = get_app_by_id(app_id)
        azzert(app and app.supports_mdp)
        state = str(uuid.uuid4())

        mdp_state = MyDigiPassState(key=MyDigiPassState.create_key(app_user),
                                    state=state)
        mdp_state.put()

        self.response.headers['Content-Type'] = "application/json"
        self.response.out.write(json.dumps(dict(client_id=app.mdp_client_id,
                                                state=state)))

    post = get


class AuthorizedMyDigiPassHandler(UserAwareRequestHandler):

    SCOPE_TO_ENDPOINT_MAPPING = {MdpScope.EMAIL : MdpEndpoint.USER_DATA,
                                 MdpScope.PHONE : MdpEndpoint.USER_DATA,
                                 MdpScope.ADDRESS : MdpEndpoint.USER_DATA,
                                 MdpScope.PROFILE : MdpEndpoint.USER_DATA,
                                 MdpScope.EID_PROFILE : MdpEndpoint.EID_DATA,
                                 MdpScope.EID_ADDRESS : MdpEndpoint.EID_DATA,
                                 MdpScope.EID_PHOTO : MdpEndpoint.EID_PHOTO}

    def language(self):
        if not hasattr(self, '_language'):
            self._language = get_user_profile(users.get_current_user()).language
        return self._language

    def post(self):
        if not self.set_user():
            self.abort(401)
            return

        connect_rpc = None
        try:
            authorization_code = self.request.POST['authorization_code']
            state = self.request.POST['state']
            scopes = self.request.POST['scope'].split(' ')
            logging.debug('POST params: %s', dict(self.request.POST))

            app_user = users.get_current_user()
            app_id = users.get_current_app_id()
            app = get_app_by_id(app_id)
            azzert(app and app.supports_mdp)

            mdp_state = MyDigiPassState.get(MyDigiPassState.create_key(app_user))
            azzert(mdp_state.state == state)
            db.delete_async(mdp_state)

            mdp_result, connect_rpc = self.authorize_mdp(app_user, app, authorization_code, scopes)
            # mdp_result: dict with following keys: uuid, access_token, scope
            mdp_profile_pointer = MyDigiPassProfilePointer.create(app_user, mdp_result['uuid'])
            mdp_profile_pointer.put()

            endpoints = { self.SCOPE_TO_ENDPOINT_MAPPING[s] for s in scopes }
            rpcs = {endpoint: self.get_mdp_data_async(mdp_result['access_token'], endpoint)
                    for endpoint in endpoints}

            result = MyDigiPassWidgetResultTO(initialize=True)
            for endpoint, rpc in rpcs.iteritems():
                response = rpc.get_result()
                if response.status_code != 200:
                    raise Exception('Failed to get %s data for MDP user %s: %s' % (endpoint, app_user.email(), response.content))

                if endpoint == MdpEndpoint.EID_PHOTO:
                    logging.debug('Got MDP %s for %s', endpoint, app_user.email())
                    photo = response.content
                    if not photo:
                        raise BusinessException(localize(self.language(), u'mdp_missing_eid_data'))
                    result.eid_photo = base64.b64encode(photo).decode('utf-8')

                elif endpoint == MdpEndpoint.EID_DATA:
                    logging.debug('Got MDP %s for %s:\n%s', endpoint, app_user.email(), response.content)
                    response_dict = json.loads(response.content)
                    if not response_dict:
                        raise BusinessException(localize(self.language(), u'mdp_missing_eid_data'))

                    if MdpScope.EID_PROFILE in scopes:
                        result.eid_profile = parse_complex_value(MyDigiPassEidProfile, response_dict, False)
                    if MdpScope.EID_ADDRESS in scopes:
                        result.eid_address = parse_complex_value(MyDigiPassEidAddress, response_dict, False)

                elif endpoint == MdpEndpoint.USER_DATA:
                    logging.debug('Got MDP %s for %s:\n%s', endpoint, app_user.email(), response.content)
                    response_dict = json.loads(response.content)

                    if MdpScope.EMAIL in scopes:
                        result.email = response_dict['email']
                        if not result.email:
                            raise BusinessException(localize(self.language(), u'mdp_missing_email'))

                    if MdpScope.PHONE in scopes:
                        result.phone = response_dict['phone_number']
                        if not result.phone:
                            raise BusinessException(localize(self.language(), u'mdp_missing_phone'))

                    if MdpScope.ADDRESS in scopes:
                        result.address = parse_complex_value(MyDigiPassAddress, response_dict, False)
                        if not all((result.address.address_1, result.address.zip, result.address.country)):
                            raise BusinessException(localize(self.language(), u'mdp_missing_address'))

                    if MdpScope.PROFILE in scopes:
                        result.profile = parse_complex_value(MyDigiPassProfile, response_dict, False)
                        if not all((result.profile.first_name, result.profile.last_name)):
                            raise BusinessException(localize(self.language(), u'mdp_missing_profile'))

                else:
                    azzert(False, 'Unexpected endpoint: %s' % endpoint)

            result_dict = serialize_complex_value(result, MyDigiPassWidgetResultTO, False, skip_missing=True)
        except BusinessException, e:
            result_dict = dict(error=e.message,
                               mdp_update_required=isinstance(e, MissingScopesException))

        logging.info('Returning MDP result: %s', result_dict)
        self.response.headers['Content-Type'] = "application/json"
        self.response.out.write(json.dumps(result_dict))

        if connect_rpc:
            self.finish_connect_mdp(app_user, connect_rpc)

    def authorize_mdp(self, app_user, app, authorization_code, scopes):
        redirect_uri = get_redirect_uri(app.app_id)
        payload = urllib.urlencode(dict(code=authorization_code,
                                        client_id=app.mdp_client_id,
                                        client_secret=app.mdp_client_secret,
                                        redirect_uri=redirect_uri,
                                        grant_type='authorization_code'))
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        result = urlfetch.fetch(u'https://www.mydigipass.com/oauth/token',
                                payload=payload,
                                method=urlfetch.POST,
                                headers=headers,
                                follow_redirects=False)

        if result.status_code != 200:
            raise Exception('Failed to authorize MDP user %s.\nStatus code: %s\n%s'
                            % (app_user.email(), result.status_code, result.content))

        logging.debug('Authorized MDP user %s: %s', app_user.email(), result.content)
        result_dict = json.loads(result.content)

        # We must execute the connect call to avoid the account being locked
        connect_rpc = self.connect_mdp_async(app_user, app, result_dict['uuid'])

        # Users must use MDP Authenticator 3.0. We can detect a lower version if the scope in result_dict is no subset
        # of the provided scope parameter
        if "scope" in result_dict:
            missing_scopes = set(scopes).difference(result_dict["scope"].split(' '))
            if missing_scopes:
                logging.info('MDP user %s is missing scopes %s', app_user.email(), missing_scopes)
                self.finish_connect_mdp(app_user, connect_rpc)
                raise MissingScopesException(self.language(), missing_scopes)

        return result_dict, connect_rpc

    def connect_mdp_async(self, app_user, app, mdp_uuid):
        payload = json.dumps(dict(uuids=[mdp_uuid]))
        logging.debug('Connecting MDP user %s: %s', app_user.email(), payload)
        rpc = urlfetch.create_rpc()
        headers = {'Content-Type': 'application/json',
                   'Authorization': 'Basic %s' % base64.b64encode("%s:%s" % (app.mdp_client_id, app.mdp_client_secret))}
        urlfetch.make_fetch_call(rpc,
                                 u'https://www.mydigipass.com/api/uuids/connected',
                                 payload=payload,
                                 method=urlfetch.POST,
                                 headers=headers)
        return rpc

    def finish_connect_mdp(self, app_user, connect_rpc):
        # A failed connect is not really a failure.
        # However, if a connect failed for 3 times, the MDP.COM <APP_ID> might be locked
        try:
            connect_response = connect_rpc.get_result()
            if connect_response.status_code == 201:
                logging.debug('Connected MDP user %s: %s', app_user.email(), connect_response.content)
            else:
                logging.error("An error happened while connecting MDP user %s. Status code: %s.\nContent: %s",
                              app_user.email(), connect_response.status_code, connect_response.content)
        except:
            logging.exception("An Exception happened while connecting MDP user %s", app_user.email())

    def get_mdp_data_async(self, access_token, endpoint):
        url = u'https://www.mydigipass.com/oauth/%s' % endpoint
        logging.debug('Creating RPC item for %s', url)

        rpc = urlfetch.create_rpc()
        urlfetch.make_fetch_call(rpc, url, headers=dict(Authorization=u'Bearer %s' % access_token))
        return rpc
