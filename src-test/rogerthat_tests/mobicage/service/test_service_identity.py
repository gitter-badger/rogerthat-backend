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

from rogerthat_tests import set_current_user

from rogerthat.bizz.friends import share_service_identity
from rogerthat.bizz.profile import create_service_profile, create_user_profile
from rogerthat.bizz.service import create_service_identity, create_qr, create_default_qr_templates, \
    _update_inheriting_service_identities
from rogerthat.dal import parent_key
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.service import get_service_identity, get_service_interaction_defs
from rogerthat.models import ServiceIdentity, QRTemplate, App
from rogerthat.rpc import users
from rogerthat.to.service import ServiceIdentityDetailsTO
from rogerthat.utils import azzert
from rogerthat.utils.service import create_service_identity_user
from google.appengine.ext import db
import mc_unittest
from mcfw.consts import MISSING
from mcfw.rpc import serialize_complex_value


class Test(mc_unittest.TestCase):

    def testUppercaseSpecialUsers(self):
        e = 'carl@example.com'
        u = users.User(e)
        assert u.email() == e
        assert type(u.email() == unicode)

        e = 'carl@eXAmplE.com'
        u = users.User(e)
        assert u.email() == e.lower()
        assert type(u.email() == unicode)

    def prepare_svc(self, svc_user_email, app_ids):
        svc_user = users.User(svc_user_email)
        create_service_profile(svc_user, u"Default name")

        svc_id_user_default = create_service_identity_user(svc_user, ServiceIdentity.DEFAULT)
        id_default = get_service_identity(svc_id_user_default)
        id_default.qualifiedIdentifier = u'qual1'
        id_default.menuBranding = u"MENUBR"
        id_default.descriptionBranding = u"DESCBR"
        id_default.mainPhoneNumber = u"123456123123"
        id_default.appIds = app_ids
        id_default.put()

        assert len(get_service_interaction_defs(svc_user, ServiceIdentity.DEFAULT, None, True)['defs']) == 1
        assert len(get_service_interaction_defs(svc_user, ServiceIdentity.DEFAULT, None, False)['defs']) == 0
        assert len(get_service_interaction_defs(svc_user, None, None, True)['defs']) == 1
        assert len(get_service_interaction_defs(svc_user, None, None, False)['defs']) == 0

        create_default_qr_templates(svc_user)
        qrtemplates = QRTemplate.gql("WHERE deleted = FALSE AND ANCESTOR is :1", parent_key(svc_user)).fetch(None)
        assert qrtemplates

        create_qr(svc_user, u'qr description', u'tag', u'qr%d' % qrtemplates[0].key().id(), ServiceIdentity.DEFAULT, None)
        create_qr(svc_user, u'qr description', u'tag', u'qr%d' % qrtemplates[0].key().id(), ServiceIdentity.DEFAULT, None)

        sids = get_service_interaction_defs(svc_user, None, None)['defs']
        assert len(sids) == 2

        sids = get_service_interaction_defs(svc_user, ServiceIdentity.DEFAULT, None)['defs']
        assert len(sids) == 2

        sids = get_service_interaction_defs(svc_user, None, None, True)['defs']
        assert len(sids) == 3

        sids = get_service_interaction_defs(svc_user, ServiceIdentity.DEFAULT, None, True)['defs']
        assert len(sids) == 3

        sidkey = unicode(sids[0].key())
        id_default.shareEnabled = True
        id_default.shareSIDKey = sidkey
        id_default.put()

        to = ServiceIdentityDetailsTO()
        to.app_data = None
        to.identifier = u'childid'
        to.name = u'child'
        to.created = 100000
        to.qualified_identifier = to.description = to.description_branding = to.menu_branding = to.phone_number = \
            to.phone_call_popup = to.search_config = None
        to.admin_emails = list()
        to.recommend_enabled = False
        to.description_use_default = to.description_branding_use_default = to.menu_branding_use_default = \
            to.phone_number_use_default = to.phone_call_popup_use_default = to.search_use_default = \
            to.email_statistics_use_default = to.app_ids_use_default = False
        to.email_statistics = False
        to.beacons = list()
        to.app_ids = list()
        to.beacon_auto_invite = True
        to.content_branding_hash = None
        id_child = create_service_identity(svc_user, to)
        id_child.description = u'Child description'
        id_child.inheritanceFlags = ServiceIdentity.FLAG_INHERIT_PHONE_NUMBER | ServiceIdentity.FLAG_INHERIT_DESCRIPTION_BRANDING
        id_child.put()

        _update_inheriting_service_identities(default_service_identity=id_default, is_trial=False)
        id_child = db.get(id_child.key())

        assert len(get_service_interaction_defs(svc_user, u'childid', None, True)['defs']) == 1
        assert len(get_service_interaction_defs(svc_user, u'childid', None, False)['defs']) == 0
        assert len(get_service_interaction_defs(svc_user, ServiceIdentity.DEFAULT, None, True)['defs']) == 3
        assert len(get_service_interaction_defs(svc_user, ServiceIdentity.DEFAULT, None, False)['defs']) == 2
        assert len(get_service_interaction_defs(svc_user, None, None, True)['defs']) == 4
        assert len(get_service_interaction_defs(svc_user, None, None, False)['defs']) == 2

        create_qr(svc_user, u'qr description', u'tag', u'qr%d' % qrtemplates[0].key().id(), u'childid', None)

        assert len(get_service_interaction_defs(svc_user, u'childid', None, True)['defs']) == 2
        assert len(get_service_interaction_defs(svc_user, u'childid', None, False)['defs']) == 1
        assert len(get_service_interaction_defs(svc_user, ServiceIdentity.DEFAULT, None, True)['defs']) == 3
        assert len(get_service_interaction_defs(svc_user, ServiceIdentity.DEFAULT, None, False)['defs']) == 2
        assert len(get_service_interaction_defs(svc_user, None, None, True)['defs']) == 5
        assert len(get_service_interaction_defs(svc_user, None, None, False)['defs']) == 3

        return id_default, id_child

    def testSvcIdentityDetailsTOs(self):

        id_default, id_child = self.prepare_svc('info@example.com', [u"rogerthat"])

        default_dict = {'phone_number': u'123456123123',
                        'search_use_default': False,
                        'description_use_default': False,
                        'description_branding': u'DESCBR',
                        'description': u'Default name (info@example.com)',
                        'created': id_default.creationTimestamp,
                        'qualified_identifier': u'qual1',
                        'phone_number_use_default': False,
                        'phone_call_popup': None,
                        'phone_call_popup_use_default': False,
                        'admin_emails': [],
                        'search_config':{'keywords': None,
                                         'enabled': False,
                                         'locations': []},
                        'menu_branding_use_default': False,
                        'menu_branding': u'MENUBR',
                        'recommend_enabled': id_default.shareEnabled,
                        'identifier': u'+default+',
                        'description_branding_use_default': False,
                        'name': u'Default name',
                        'email_statistics': False,
                        'email_statistics_use_default': False,
                        'app_data': None,
                        'beacons':[],
                        'app_ids_use_default':False,
                        'app_ids':[App.APP_ID_ROGERTHAT],
                        'app_names':["Rogerthat"],
                        'can_edit_supported_apps':False,
                        'beacon_auto_invite' : True,
                        'content_branding_hash': None}

        service_profile = get_service_profile(users.User(u'info@example.com'))

#        print serialize_complex_value(ServiceIdentityDetailsTO.fromServiceIdentity(id_default, service_profile), ServiceIdentityDetailsTO, False)
#        print default_dict
        azzert(serialize_complex_value(ServiceIdentityDetailsTO.fromServiceIdentity(id_default, service_profile), ServiceIdentityDetailsTO, False) == default_dict)

        child_dict = default_dict.copy()
        child_dict['menu_branding'] = None
        child_dict['name'] = u'child'
        child_dict['qualified_identifier'] = None
        child_dict['identifier'] = u'childid'
        child_dict['description_branding_use_default'] = True
        child_dict['phone_number_use_default'] = True
        child_dict['description'] = u'Child description'
        child_dict['created'] = id_child.creationTimestamp
        child_dict['recommend_enabled'] = False
        child_dict['email_statistics'] = False

#        print serialize_complex_value(ServiceIdentityDetailsTO.fromServiceIdentity(id_child, service_profile), ServiceIdentityDetailsTO, False)
#        print child_dict
        azzert(serialize_complex_value(ServiceIdentityDetailsTO.fromServiceIdentity(id_child, service_profile), ServiceIdentityDetailsTO, False) == child_dict)

    def test_recommend_svc_identity(self):
        id_default, id_child = self.prepare_svc(u'info2@example.com', [u"rogerthat"])
        assert id_child

        invitor = users.User(u'invitorke@example.com')
        create_user_profile(invitor, u"an invitor", language='nl')
        set_current_user(invitor)

        # Share to non-existing user
        # logging.error(invitor.email())
        # logging.error(id_default.user.email())
        share_service_identity(invitor, id_default.user, users.User(u'nonexisting@example.com'))

        # Share to existing user
        human_user = users.User(u'ahuman@example.com')
        create_user_profile(human_user, u"a human", language='nl')
        share_service_identity(invitor, id_default.user, human_user)

        # Share to a service
        self.assertRaises(Exception, share_service_identity, invitor, id_default.user, id_default.service_user)

    def test_share_crap_email(self):
        # Test that we immediately return for crappy recipient email address
        share_service_identity(None, None, users.User('bla@bla.com/bla'))

    def test_invite_nonexisting_user(self):
        from rogerthat.service.api.friends import invite

        _, _ = self.prepare_svc(u'info3@example.com', [u"rogerthat", u"be-loc"])

        set_current_user(users.User('info3@example.com'))
        invite("nonexisting@example.com", "Non existing", "Welkom!", "en", "tag", None)
        invite("nonexisting@example.com", "Non existing", "Welkom!", "en", "tag", MISSING)
        invite("nonexisting@example.com", "Non existing", "Welkom!", "en", "tag", ServiceIdentity.DEFAULT)

        invite("nonexisting@example.com", "Non existing", "Welkom!", "en", "tag", None, app_id=u"be-loc")
        invite("nonexisting@example.com", "Non existing", "Welkom!", "en", "tag", MISSING, app_id=u"be-loc")
        invite("nonexisting@example.com", "Non existing", "Welkom!", "en", "tag", ServiceIdentity.DEFAULT, app_id=u"be-loc")
