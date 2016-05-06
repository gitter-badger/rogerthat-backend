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

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging

from rogerthat.bizz import roles
from rogerthat.bizz.friends import makeFriends, ORIGIN_USER_INVITE
from rogerthat.bizz.profile import create_service_profile, update_password_hash
from rogerthat.bizz.roles import grant_role
from rogerthat.bizz.service import configure_mobidick
from rogerthat.dal.profile import get_trial_service_by_owner, get_user_profile
from rogerthat.models import TrialServiceAccount, ServiceIdentity
from rogerthat.rpc import users
from rogerthat.settings import get_server_settings
from rogerthat.templates import render
from rogerthat.to.profile import TrialServiceTO
from rogerthat.translations import DEFAULT_LANGUAGE
from rogerthat.utils import generate_password, now, send_mail_via_mime
from rogerthat.utils.crypto import sha256_hex
from rogerthat.utils.service import create_service_identity_user
from google.appengine.api import xmpp
from google.appengine.ext import db, deferred
from mcfw.rpc import arguments, returns


@returns(TrialServiceTO)
@arguments(user=users.User, service_name=unicode, service_description=unicode, return_existing=bool, service_email=unicode)
def signup(user, service_name, service_description, return_existing, service_email=None):
    server_settings = get_server_settings()
    def trans(owner_profile, ts, is_new_trial_service):
        if is_new_trial_service:
            deferred.defer(_configure_mobidick, ts.service, _transactional=True)

        deferred.defer(_friend_trial_service, user, ts.service, _transactional=True, _countdown=5)

        context = dict(name=owner_profile.name, email=ts.service.email(), password=ts.password)
        body = render("trial_service_signup", [DEFAULT_LANGUAGE], context)
        html = render("trial_service_signup_html", [DEFAULT_LANGUAGE], context)
        logging.info("Sending message to %s\n%s" % (ts.owner.email(), body))

        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Rogerthat trial service"
        msg['From'] = server_settings.senderEmail
        msg['To'] = ts.owner.email()
        msg.attach(MIMEText(body.encode('utf-8'), 'plain', 'utf-8'))
        msg.attach(MIMEText(html.encode('utf-8'), 'html', 'utf-8'))
        send_mail_via_mime(server_settings.senderEmail, ts.owner.email(), msg)

        return TrialServiceTO.fromDBTrialServiceAccount(ts)


    message = "%s is signing up for a trial account!" % (user.email().encode('utf8'))
    xmpp.send_message(server_settings.xmppInfoMembers, message, message_type=xmpp.MESSAGE_TYPE_CHAT)
    logging.info(message)

    owner_profile = get_user_profile(user)

    ts = get_trial_service_by_owner(user) if return_existing else None

    if ts is None:
        logging.info("%s does not have a trial service account yet" % (user.email().encode('utf8')))

        ts = TrialServiceAccount()
        ts.owner = user
        ts.password = generate_password(6)
        now_ = now()
        ts.creationDate = now_
        ts.put()

        service_email = service_email or u"service-%s@trials.rogerth.at" % ts.key().id()
        service_name = service_name or u"Trial Service %s" % ts.key().id()

        def update_service(service_profile, si):
            si.description = service_description
            update_password_hash(service_profile, sha256_hex(ts.password), now_)

        try:
            ts.service = users.User(service_email)
            ts.put()
            service_profile, service_identity, _ = create_service_profile(ts.service, service_name, is_trial=True,
                                                                          update_func=update_service)
        except:
            ts.delete()
            raise

        try:
            xg_on = db.create_transaction_options(xg=True)
            return db.run_in_transaction_options(xg_on, trans, owner_profile, ts, is_new_trial_service=True)
        except:
            db.delete([ts, service_profile, service_identity])
            raise

    else:
        logging.info("%s has already a trial service with account %s" % (user.email().encode('utf8'), ts.service))

        xg_on = db.create_transaction_options(xg=True)
        return db.run_in_transaction_options(xg_on, trans, owner_profile, ts, is_new_trial_service=False)

def _friend_trial_service(user, service):
    logging.info("Hooking up %s with %s" % (user, service))
    service_identity_user = create_service_identity_user(service, ServiceIdentity.DEFAULT)
    def trans():
        makeFriends(service_identity_user, user, user, None, notify_invitee=True, origin=ORIGIN_USER_INVITE)
        grant_role(service_identity_user, user, roles.ROLE_ADMIN)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)

def _configure_mobidick(service):
    configure_mobidick(service)
