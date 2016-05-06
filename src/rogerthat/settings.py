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

from google.appengine.api import app_identity
from google.appengine.ext import db

from mcfw.cache import CachedModelMixIn, cached
from mcfw.rpc import returns, arguments
from mcfw.serialization import deserializer, ds_model, serializer, s_model, register
from rogerthat.models.utils import add_meta


class ServerSettings(CachedModelMixIn, db.Model):
    messageFlowRunnerAddress = add_meta(db.StringProperty(indexed=False),
                                        doc="Message flow runner address",
                                        order=5)
    mobidickAddress = add_meta(db.StringProperty(indexed=False),
                               doc="Mobidick address:",
                               order=5)
    secret = add_meta(db.StringProperty(indexed=False),
                      doc="Server secret",
                      order=5)
    baseUrl = add_meta(db.StringProperty(indexed=False),
                       doc="Rogerthat cloud address",
                       order=5)
    jabberDomain = add_meta(db.StringProperty(indexed=False),
                            doc="Jabber domain",
                            order=10)
    jabberSecret = add_meta(db.StringProperty(indexed=False),
                            doc="Jabber secret",
                            order=10)
    jabberEndPoints = add_meta(db.StringListProperty(indexed=False),
                               doc="Jabber endpoints (one ip/port combination per port. eg: 192.168.10.23:8001)",
                               order=10)
    jabberBoshEndPoint = add_meta(db.StringProperty(indexed=False),
                               doc="Jabber bosh endpoint",
                               order=10)
    dashboardEmail = add_meta(db.StringProperty(indexed=False),
                              doc="Dashboard e-mail address",
                              order=5)
    brandingRendererUrl = add_meta(db.StringProperty(indexed=False),
                                   doc="Branding renderer address",
                                   order=5)
    srvEndPoints = add_meta(db.StringListProperty(indexed=False),
                            doc="DNS SRV records (ip:port:priority. eg: 192.168.10.23:5222:0)",
                            order=11)
    smtpserverHost = add_meta(db.StringProperty(indexed=False),
                              order=30)
    smtpserverPort = add_meta(db.StringProperty(indexed=False),
                              order=30)
    smtpserverLogin = add_meta(db.StringProperty(indexed=False),
                               order=30)
    smtpserverPassword = add_meta(db.StringProperty(indexed=False),
                                  order=30)
    dkimPrivateKey = add_meta(db.TextProperty(indexed=False),
                              doc="DKIM private key",
                              order=40)

    stripePublicKey = add_meta(db.StringProperty(indexed=False),
                              doc="Stripe public key",
                              order=50)
    stripeSecretKey = add_meta(db.StringProperty(indexed=False),
                              doc="Stripe secret key",
                              order=51)

    offloadHostname = add_meta(db.StringProperty(indexed=False),
                               doc="SSH server hostname",
                               order=70)
    offloadPort = add_meta(db.IntegerProperty(indexed=False),
                           doc="SSH server port",
                           order=71)
    offloadHostKey = add_meta(db.StringProperty(indexed=False),
                              doc="SSH server host key (cat /etc/ssh/ssh_host_rsa_key.pub)",
                              order=72)
    offloadUsername = add_meta(db.StringProperty(indexed=False),
                               doc="SSH server username",
                               order=73)
    offloadPassword = add_meta(db.StringProperty(indexed=False),
                               doc="SSH server password",
                               order=74)

    gcmKey = add_meta(db.StringProperty(indexed=False), doc="Google Cloud Messaging Key", order=60)
    googleMapsKey = add_meta(db.StringProperty(indexed=False), doc="Google Maps Key", order=61)


    registrationMainSignature = add_meta(db.StringProperty(indexed=False), doc="baee64 version of main registration signature", order=80)
    registrationEmailSignature = add_meta(db.StringProperty(indexed=False), doc="baee64 version of email registration signature", order=81)
    registrationPinSignature = add_meta(db.StringProperty(indexed=False), doc="baee64 version of pin registration signature", order=82)

    userEncryptCipherPart1 = add_meta(db.StringProperty(indexed=False), doc="User encrypt cipher part 1 (base64.b64encode(SECRET_KEY).decode('utf-8'))", order=83)
    userEncryptCipherPart2 = add_meta(db.StringProperty(indexed=False), doc="User encrypt cipher part 2 (base64.b64encode(SECRET_KEY).decode('utf-8'))", order=84)
    cookieSecretKey = add_meta(db.StringProperty(indexed=False), doc="Secret key to encrypt the session (base64.b64encode(SECRET_KEY).decode('utf-8'))", order=85)
    cookieSessionName = add_meta(db.StringProperty(indexed=False), doc="Cookie name for the session", order=86)
    cookieQRScanName = add_meta(db.StringProperty(indexed=False), doc="Cookie name for qr codes", order=87)

    supportEmail = add_meta(db.StringProperty(indexed=False), doc="Main email address to contact support", order=88)
    supportWorkers = add_meta(db.StringListProperty(indexed=False),
                               order=89)

    xmppInfoMembers = add_meta(db.StringListProperty(indexed=False),
                               order=90)

    serviceCreators = add_meta(db.StringListProperty(indexed=False),
                               doc="Service creators  (2 entries per combination. eg: - solution - test@example.com)",
                               order=91)

    staticPinCodes = add_meta(db.StringListProperty(indexed=False),
                              doc="Static pin codes  (2 entries per combination. eg: - pincode - test@example.com)",
                              order=92)

    ysaaaMapping = add_meta(db.StringListProperty(indexed=False),
                              doc="YSAAA mapping  (2 entries per combination. eg: - hash - test@example.com)",
                              order=93)


    @property
    def senderEmail(self):
        return "Rogerthat Dashboard <%s>" % self.dashboardEmail

    @property
    def senderEmail2ToBeReplaced(self):
        return "Rogerthat Dashboard <rogerthat@%s.appspotmail.com>" % app_identity.get_application_id()

    @property
    def domain(self):
        return self.jabberDomain

    def invalidateCache(self):
        logging.info("ServerSettings removed from cache.")
        get_server_settings.invalidate_cache()


@deserializer
def ds_ss(stream):
    return ds_model(stream, ServerSettings)

@serializer
def s_ss(stream, server_settings):
    s_model(stream, server_settings, ServerSettings)

register(ServerSettings, s_ss, ds_ss)

@cached(1)
@returns(ServerSettings)
@arguments()
@db.non_transactional
def get_server_settings():
    ss = ServerSettings.get_by_key_name("MainSettings")
    if not ss:
        ss = ServerSettings(key_name="MainSettings")
    return ss

del ds_ss
del s_ss
