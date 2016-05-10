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

from add_1_monkey_patches import dummy2
from add_2_zip_imports import dummy
from mcfw.restapi import rest_functions
from rogerthat.pages.admin.apps import UploadAppAppleCertsHandler
from rogerthat.pages.admin.client_distro import GetClientDistroPackageHandler
from rogerthat.pages.app import AppUrlHandler
from rogerthat.pages.branding import BrandingDownloadHandler, BrandingHandler
from rogerthat.pages.icons import LibraryIconHandler
from rogerthat.pages.install import InstallationRequestHandler
from rogerthat.pages.invite import InviteQRCodeRequestHandler, InviteUserRequestHandler
from rogerthat.pages.js_embedding import JSEmbeddingDownloadHandler
from rogerthat.pages.logging_page import LogExceptionHandler
from rogerthat.pages.login import LoginHandler, AuthenticationRequiredHandler, OfflineDebugLoginHandler, \
    TermsAndConditionsRequiredHandler, SetPasswordHandler, ResetPasswordHandler, AutoLogin
from rogerthat.pages.main import MainPage, RobotsTxt, AboutPageHandler, CrossDomainDotXml
from rogerthat.pages.mdp import InitMyDigiPassSessionHandler, AuthorizedMyDigiPassHandler
from rogerthat.pages.message import MessageHandler
from rogerthat.pages.photo import ServiceDownloadPhotoHandler
from rogerthat.pages.profile import GetAvatarHandler, GetCachedAvatarHandler
from rogerthat.pages.qrinstall import QRInstallRequestHandler
from rogerthat.pages.register_mobile import RegisterMobileViaGoogleOrFacebookHandler, FinishRegistrationHandler, \
    InitiateRegistrationViaEmailVerificationHandler, VerifyEmailWithPinHandler, RegisterInstallIdentifierHandler, \
    RegisterMobileViaFacebookHandler, LogRegistrationStepHandler, InitServiceAppHandler, RegisterMobileViaQRHandler, \
    GetRegistrationOauthInfoHandler, OauthRegistrationHandler
from rogerthat.pages.service_disabled import ServiceDisabledHandler
from rogerthat.pages.service_interact import ServiceInteractRequestHandler, ServiceInteractQRCodeRequestHandler
from rogerthat.pages.service_map import ServiceMapHandler
from rogerthat.pages.service_page import GetServiceAppHandler
from rogerthat.pages.settings import ForwardLog, DebugLog
from rogerthat.pages.shortner import ShortUrlHandler
from rogerthat.pages.subscribe_service import SubscribeHandler
from rogerthat.pages.unsubscribe_reminder_service import UnsubscribeReminderHandler, UnsubscribeBroadcastHandler
from rogerthat.restapi import user, srv, service_map
from rogerthat.restapi.admin import ApplePushFeedbackHandler, ServerTimeHandler, ApplePushCertificateDownloadHandler
from rogerthat.rpc.http import JSONRPCRequestHandler
from rogerthat.rpc.service import ServiceApiHandler, register_service_api_calls, CallbackResponseReceiver
from rogerthat.service.api import app, friends, messaging, qr, XMLSchemaHandler, system
from rogerthat.wsgi import RogerthatWSGIApplication

dummy2()
dummy()

handlers = [
    ('/', MainPage),
    ('/robots.txt', RobotsTxt),
    ('/crossdomain.xml', CrossDomainDotXml),
    ('/login', LoginHandler),
    ('/login_required', AuthenticationRequiredHandler),
    ('/tac_required', TermsAndConditionsRequiredHandler),
    ('/unauthenticated/mobi/registration/init_via_email', InitiateRegistrationViaEmailVerificationHandler),
    ('/unauthenticated/mobi/registration/register_install', RegisterInstallIdentifierHandler),
    ('/unauthenticated/mobi/registration/verify_email', VerifyEmailWithPinHandler),
    ('/unauthenticated/mobi/registration/register_facebook', RegisterMobileViaFacebookHandler),
    ('/unauthenticated/mobi/registration/register_qr', RegisterMobileViaQRHandler),
    ('/unauthenticated/mobi/registration/finish', FinishRegistrationHandler),
    ('/unauthenticated/mobi/registration/log_registration_step', LogRegistrationStepHandler),
    ('/unauthenticated/mobi/registration/init_service_app', InitServiceAppHandler),
    ('/unauthenticated/mobi/registration/oauth/info', GetRegistrationOauthInfoHandler),
    ('/unauthenticated/mobi/registration/oauth/registered', OauthRegistrationHandler),
    ('/unauthenticated/mobi/distros/get/(.*)', GetClientDistroPackageHandler),
    ('/unauthenticated/mobi/cached/avatar/(.*)', GetCachedAvatarHandler),
    ('/unauthenticated/mobi/avatar/(.*)', GetAvatarHandler),
    ('/unauthenticated/mobi/branding/(.*)', BrandingDownloadHandler),
    ('/unauthenticated/qrinstall', QRInstallRequestHandler),
    ('/unauthenticated/mobi/service/photo/download/(.*)', ServiceDownloadPhotoHandler),
    ('/unauthenticated/mobi/logging/exception', LogExceptionHandler),
    ('/unauthenticated/mobi/apps/upload_cert', UploadAppAppleCertsHandler),
    ('/unauthenticated/forward_log', ForwardLog),
    ('/unauthenticated/debug_log', DebugLog),
    ('/unauthenticated/service-map', ServiceMapHandler),
    ('/unauthenticated/service-app', GetServiceAppHandler),
    ('/message', MessageHandler),
    ('/json-rpc', JSONRPCRequestHandler),
    ('/api/1', ServiceApiHandler),
    ('/api/1/MessageFlow.xsd', XMLSchemaHandler),
    ('/branding/(.*)/(.*)', BrandingHandler),
    ('/login/.dev', OfflineDebugLoginHandler),
    ('/subscribe', SubscribeHandler),
    ('/invite', InviteQRCodeRequestHandler),
    ('/q/i(.*)', InviteUserRequestHandler),
    ('/si/(.*)/(.*)', ServiceInteractQRCodeRequestHandler),
    ('/q/s/(.*)/(.*)', ServiceInteractRequestHandler),
    ('/(M|S)/(.*)', ShortUrlHandler),
    ('/A/(.*)', AppUrlHandler),
    ('/about', AboutPageHandler),
    ('/register', RegisterMobileViaGoogleOrFacebookHandler),
    ('/setpassword', SetPasswordHandler),
    ('/resetpassword', ResetPasswordHandler),
    ('/install', InstallationRequestHandler),
    ('/api/1/callback', CallbackResponseReceiver),
    ('/api/1/apple_feedback', ApplePushFeedbackHandler),
    ('/api/1/apple_certs', ApplePushCertificateDownloadHandler),
    ('/api/1/servertime', ServerTimeHandler),
    ('/unsubscribe_reminder', UnsubscribeReminderHandler),
    ('/unsubscribe_broadcast', UnsubscribeBroadcastHandler),
    ('/auto_login', AutoLogin),
    ('/mobi/js_embedding/(.*)', JSEmbeddingDownloadHandler),
    ('/mobi/rest/mdp/session/init', InitMyDigiPassSessionHandler),
    ('/mobi/rest/mdp/session/authorized', AuthorizedMyDigiPassHandler),
    ('/mobi/service/menu/icons/lib/(.*)', LibraryIconHandler),
    ('/service_disabled', ServiceDisabledHandler)
]

register_service_api_calls(app)
register_service_api_calls(friends)
register_service_api_calls(messaging)
register_service_api_calls(qr)
register_service_api_calls(system)

handlers.extend(rest_functions(user))
handlers.extend(rest_functions(srv))
handlers.extend(rest_functions(service_map))

app = RogerthatWSGIApplication(handlers, name="main_unauthenticated")
