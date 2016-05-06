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

import webapp2

from add_1_monkey_patches import dummy2
from add_2_zip_imports import dummy
from rogerthat.bizz.rtemail import EmailHandler
from rogerthat.cron.log_retention import SendLogs
from rogerthat.cron.rpc import Cleanup, CleanupTMPBlobs
from rogerthat.cron.rpc_api_result_retention import CleanupRpcAPIResultHandler
from rogerthat.cron.rpc_capi_call_retention import CleanupRpcCAPICallHandler
from rogerthat.cron.rpc_outstanding_gcm_kicks import Reschedule
from rogerthat.cron.send_unread_reminder import UnreadMessageReminderHandler
from rogerthat.cron.service_api_callback_retention import ProcessServiceAPICallbackHandler
from rogerthat.cron.service_api_result_retention import CleanupServiceAPIResultHandler
from rogerthat.cron.statistics import StatisticsHandler, ServiceStatisticsEmailHandler
from rogerthat.pages.admin import debugging, apps, mobile_errors, installation_logs
from rogerthat.pages.admin.activation_logs import ActivationLogsHandler
from rogerthat.pages.admin.apps import AppsTools, GetAppHandler, CreateAppHandler, UpdateAppHandler, DeleteAppHandler, \
    QRTemplateHandler, AppTranslationsHandler
from rogerthat.pages.admin.channel import ChannelConnectedHandler, ChannelDisconnectedHandler
from rogerthat.pages.admin.client_distro import ClientDistroPage, ClientDistroPostHandler, Publish
from rogerthat.pages.admin.debugging import UserTools
from rogerthat.pages.admin.explorer import ExplorerPage
from rogerthat.pages.admin.installation_logs import InstallationLogsHandler
from rogerthat.pages.admin.js_embedding import JSEmbeddingTools, DeployJSEmbeddingHandler
from rogerthat.pages.admin.mobile_errors import MobileErrorHandler
from rogerthat.pages.admin.services import ConvertToService, ServiceTools, CreateTrialService, ReleaseTrialService, \
    SetServiceMonitoring, SetServiceCategory, NewBeaconForServiceIdentityUser
from rogerthat.pages.admin.settings import ServerSettingsHandler
from rogerthat.restapi import explorer, admin
from rogerthat.wsgi import RogerthatWSGIApplication
from google.appengine.ext.deferred.deferred import TaskHandler
from mcfw.restapi import rest_functions


dummy()
dummy2()

class WarmupRequestHandler(webapp2.RequestHandler):
    # noinspection PyUnresolvedReferences
    def get(self):
        from rogerthat import models  # @UnusedImport
        from rogerthat.bizz import branding, service, friends, limit, location, messaging, profile, qrtemplate, registration, session, system, user  # @UnusedImport
        from rogerthat.rpc import rpc, http, calls, service as srv, users  # @UnusedImport
        # do not remove the imports, unless you have a very good reason


handlers = [
    ('/cron/rpc/cleanup', Cleanup),
    ('/cron/rpc/cleanup_rpc_api_result', CleanupRpcAPIResultHandler),
    ('/cron/rpc/cleanup_rpc_capi_call', CleanupRpcCAPICallHandler),
    ('/cron/rpc/cleanup_service_api_result', CleanupServiceAPIResultHandler),
    ('/cron/rpc/cleanup_tmp_blobs', CleanupTMPBlobs),
    ('/cron/rpc/process_service_api_callback', ProcessServiceAPICallbackHandler),
    ('/cron/rpc/outstanding_kicks', Reschedule),
    ('/cron/rpc/unread_messages_reminder', UnreadMessageReminderHandler),
    ('/cron/rpc/statistics', StatisticsHandler),
    ('/cron/rpc/service_statistics_email', ServiceStatisticsEmailHandler),
    ('/cron/log_retention', SendLogs),
    ('/mobiadmin/distros', ClientDistroPage),
    ('/mobiadmin/distros/post', ClientDistroPostHandler),
    ('/mobiadmin/distros/publish', Publish),
    ('/mobiadmin/explorer', ExplorerPage),
    ('/mobiadmin/services', ServiceTools),
    ('/mobiadmin/release_trial_service', ReleaseTrialService),
    ('/mobiadmin/create_trial_service', CreateTrialService),
    ('/mobiadmin/convert_to_service', ConvertToService),
    ('/mobiadmin/set_service_category', SetServiceCategory),
    ('/mobiadmin/set_service_monitoring', SetServiceMonitoring),
    ('/mobiadmin/new_beacon_for_service_identity_user' , NewBeaconForServiceIdentityUser),
    ('/mobiadmin/installation_logs', InstallationLogsHandler),
    ('/mobiadmin/activation_logs', ActivationLogsHandler),
    ('/mobiadmin/client_errors', MobileErrorHandler),
    ('/mobiadmin/settings', ServerSettingsHandler),
    ('/mobiadmin/debugging', UserTools),
    ('/mobiadmin/js_embedding', JSEmbeddingTools),
    ('/mobiadmin/deploy_js_embedding', DeployJSEmbeddingHandler),
    ('/mobiadmin/apps', AppsTools),
    ('/mobiadmin/apps/create', CreateAppHandler),
    ('/mobiadmin/apps/get', GetAppHandler),
    ('/mobiadmin/apps/update', UpdateAppHandler),
    ('/mobiadmin/apps/delete', DeleteAppHandler),
    ('/mobiadmin/apps/qr_template_example', QRTemplateHandler),
    ('/mobiadmin/apps/translations/app/(.*)/', AppTranslationsHandler),
    ('/_ah/queue/deferred', TaskHandler),
    ('/_ah/warmup', WarmupRequestHandler),
    ('/_ah/channel/connected/', ChannelConnectedHandler),
    ('/_ah/channel/disconnected/', ChannelDisconnectedHandler),
    EmailHandler.mapping()
]

handlers.extend(rest_functions(explorer))
handlers.extend(rest_functions(admin))
handlers.extend(rest_functions(debugging))
handlers.extend(rest_functions(apps))
handlers.extend(rest_functions(installation_logs))
handlers.extend(rest_functions(mobile_errors))

app = RogerthatWSGIApplication(handlers, True, name="main_admin", google_authenticated=True)
