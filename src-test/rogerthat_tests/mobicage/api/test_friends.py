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
from rogerthat_tests import register_tst_mobile, set_current_user
import time

from rogerthat import utils
from rogerthat.api.friends import getFriendsList, getFriendEmails, getFriend, findFriend
from rogerthat.bizz.friends import invite, ACCEPT_ID, PersonInvitationOverloadException, \
    PersonAlreadyInvitedThisWeekException, breakFriendShip, invited_response_receiver, UNIT_TEST_REFS, userCode, \
    ORIGIN_USER_INVITE, makeFriends
from rogerthat.bizz.profile import create_user_profile, find_rogerthat_users_via_email, create_service_profile, \
    _re_index, set_profile_data
from rogerthat.bizz.service import convert_user_to_service, InvalidKeyException
from rogerthat.consts import WEEK
from rogerthat.dal.friend import get_friends_map, get_friend_invitation_history
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.service import get_friend_serviceidentity_connection, get_default_service_identity
from rogerthat.models import Message, UserData, App
from rogerthat.restapi.messaging import getMessages, ackMessage
from rogerthat.rpc import users
from rogerthat.service.api import system
from rogerthat.service.api.friends import invite as service_invite
from rogerthat.to.friends import FriendTO, GetFriendsListRequestTO, GetFriendEmailsRequestTO, GetFriendRequestTO, \
    FindFriendRequestTO
from rogerthat.to.messaging import AckMessageRequestTO
from rogerthat.utils import now, is_clean_app_user_email
from rogerthat.utils.service import remove_slash_default
from google.appengine.ext import db
import mc_unittest


class Test(mc_unittest.TestCase):

    def test_friends(self):
        non_nuntiuz_user = users.User(u'moehahaha@foo.com')
        # setup env
        invitor = users.get_current_user()
        invitee = users.User(u'john.doe@foo.com')
        create_user_profile(invitee, invitee.email())
        register_tst_mobile(invitee.email())
        service_user = users.User(u'info@example.com')
        create_user_profile(service_user, u"Mobicage NV")
        convert_user_to_service(service_user)
        svc_identity = get_default_service_identity(service_user)
        svc_identity_user = svc_identity.user
        service_profile = get_service_profile(service_user)
        service_profile.callBackJid = "test@example.com"
        service_profile.sik = "test"
        service_profile.put()

        # assert invitee and invitor are not friends
        myFriendMap = get_friends_map(invitor)
        hisFriendMap = get_friends_map(invitee)
        assert not invitee in myFriendMap.friends
        assert not invitor in hisFriendMap.friends

        # assert friend generation
        assert myFriendMap.generation == 0
        assert hisFriendMap.generation == 0

        # invite, sending email
        invite(invitor, non_nuntiuz_user.email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=App.APP_ID_ROGERTHAT)
        set_current_user(non_nuntiuz_user, skip_create_session=True)
        messages = getMessages(None).messages
        assert not messages  # email was sent

        # trigger to much invites this week
        self.assertRaises(PersonAlreadyInvitedThisWeekException, lambda: invite(invitor, non_nuntiuz_user.email(), None, None, \
                                                                                None, None, origin=ORIGIN_USER_INVITE, app_id=App.APP_ID_ROGERTHAT))
        get_friend_invitation_history(invitor, non_nuntiuz_user).delete()

        # trigger too much invites
        original_now = utils._now_impl
        utils._now_impl = lambda: original_now() - WEEK - WEEK - WEEK
        invite(invitor, invitee.email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=App.APP_ID_ROGERTHAT)
        utils._now_impl = lambda: original_now() - WEEK - WEEK
        invite(invitor, invitee.email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=App.APP_ID_ROGERTHAT)
        utils._now_impl = lambda: original_now() - WEEK
        invite(invitor, invitee.email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=App.APP_ID_ROGERTHAT)
        utils._now_impl = original_now
        self.assertRaises(PersonInvitationOverloadException, lambda: invite(invitor, invitee.email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=App.APP_ID_ROGERTHAT))
        get_friend_invitation_history(invitor, invitee).delete()

        # invite two nuntiuz users
        invite(invitor, invitee.email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=App.APP_ID_ROGERTHAT)
        set_current_user(invitee)
        messages = getMessages(None).messages
        assert messages
        invitation = messages[0]
        myFriendMap = get_friends_map(invitor)
        hisFriendMap = get_friends_map(invitee)
        assert myFriendMap.generation == 0
        assert hisFriendMap.generation == 0
        request = AckMessageRequestTO()
        request.button_id = ACCEPT_ID
        request.message_key = invitation.key
        request.custom_reply = None
        request.parent_message_key = None
        request.timestamp = now()
        ackMessage(request)
        myFriendMap = get_friends_map(invitor)
        hisFriendMap = get_friends_map(invitee)
        assert myFriendMap.generation == 1
        assert hisFriendMap.generation == 1

        # assert invitee and invitor are friends
        assert invitee in myFriendMap.friends
        assert invitor in hisFriendMap.friends

        # assert svc_identity_user and invitee are not friends
        assert remove_slash_default(svc_identity_user) not in hisFriendMap.friends
        assert not get_friend_serviceidentity_connection(invitee, svc_identity_user)

        # Cleanup previously sent messages
        db.delete(Message.all())

        # svc_identity_user invites friend
        set_current_user(service_user)
        service_invite(invitee.email(), None, "Ghellooooo", "fr", "tzal wezen bakske frezen",
                       service_identity=svc_identity.identifier)

        # assert svc_identity_user and invitee are not friends
        hisFriendMap = get_friends_map(invitee)
        assert remove_slash_default(svc_identity_user) not in hisFriendMap.friends
        assert not get_friend_serviceidentity_connection(invitee, svc_identity_user)

        # accept message and verify
        set_current_user(invitee)
        messages = getMessages(None).messages
        assert messages
        invitation = messages[0]
        request = AckMessageRequestTO()
        request.button_id = ACCEPT_ID
        request.message_key = invitation.key
        request.custom_reply = None
        request.parent_message_key = None
        request.timestamp = now()
        ackMessage(request)
        hisFriendMap = get_friends_map(invitee)
        assert remove_slash_default(svc_identity_user) in hisFriendMap.friends
        assert get_friend_serviceidentity_connection(invitee, svc_identity_user)

        # breakup friends invitor & invitee
        breakFriendShip(invitor, invitee)
        myFriendMap = get_friends_map(invitor)
        hisFriendMap = get_friends_map(invitee)
        assert myFriendMap.generation == 2
        assert hisFriendMap.generation == 3

        # assert invitee and invitor are not friends
        assert not invitee in myFriendMap.friends
        assert not invitor in hisFriendMap.friends

        # breakup friends svc_identity_user & invitee
        breakFriendShip(svc_identity_user, invitee)
        hisFriendMap = get_friends_map(invitee)
        assert hisFriendMap.generation == 4

        # assert invitee and svc_identity_user are not friends
        assert remove_slash_default(svc_identity_user) not in hisFriendMap.friends
        assert not get_friend_serviceidentity_connection(invitee, svc_identity_user)

        # Cleanup previously sent messages
        db.delete(Message.all())

        # friend invites svc_identity_user
        set_current_user(invitor)
        invite(invitor, remove_slash_default(svc_identity_user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=App.APP_ID_ROGERTHAT)
        myFriendMap = get_friends_map(invitor)
        print myFriendMap.generation
        invited_response_receiver(UNIT_TEST_REFS["invited"], ACCEPT_ID)
        myFriendMap = get_friends_map(invitor)
        assert remove_slash_default(svc_identity_user) in myFriendMap.friends
        print myFriendMap.generation
        assert myFriendMap.generation == 3
        assert get_friend_serviceidentity_connection(invitor, svc_identity_user)
        assert not myFriendMap.friendDetails[remove_slash_default(svc_identity_user).email()].hasUserData

        # Cleanup previously sent messages
        db.delete(Message.all())

        # invite two nuntiuz users via user code
        invite(invitor, unicode(userCode(users.User(invitee.email()))), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=App.APP_ID_ROGERTHAT)
        set_current_user(invitee)
        messages = getMessages(None).messages
        assert messages
        invitation = messages[0]
        myFriendMap = get_friends_map(invitor)
        hisFriendMap = get_friends_map(invitee)
        assert myFriendMap.generation == 3
        assert hisFriendMap.generation == 4
        request = AckMessageRequestTO()
        request.button_id = ACCEPT_ID
        request.message_key = invitation.key
        request.custom_reply = None
        request.parent_message_key = None
        request.timestamp = now()
        ackMessage(request)
        myFriendMap = get_friends_map(invitor)
        hisFriendMap = get_friends_map(invitee)
        assert myFriendMap.generation == 4
        assert hisFriendMap.generation == 5

        # assert invitee and invitor are friends
        assert invitee in myFriendMap.friends
        assert invitor in hisFriendMap.friends

        assert not myFriendMap.friendDetails[invitee.email()].hasUserData
        assert not hisFriendMap.friendDetails[invitor.email()].hasUserData

    def test_clean_email(self):
        assert is_clean_app_user_email(users.User(u'aap@bbb.com'))
        assert is_clean_app_user_email(users.User(u'aasdf.sadfap@bbb.com'))
        assert not is_clean_app_user_email(users.User(u'aldksjdas@bb.com/ccc'))
        assert not is_clean_app_user_email(users.User(u'aldksjdas@dsjkads.com@lksdd'))
        assert not is_clean_app_user_email(users.User(u'@dsjkads.com'))
        assert not is_clean_app_user_email(users.User(u'aaaa.sdfs@'))

    def test_find_users_via_email(self):
        user_me = users.get_current_user()

        users_ = [users.User(u'test@example.com'), users.User(u'carl@example.com'), user_me]
        assert find_rogerthat_users_via_email(user_me, users_) == [user_me]

        users_ = [users.User(u'test@example.com/blabla'), users.User(u'carl@example.com'), user_me]
        assert find_rogerthat_users_via_email(user_me, users_) == [user_me]

        svc_user = users.User(u'infotje@example.com')
        create_service_profile(svc_user, u"Default name")
        users_ = [users.User(u'test@example.com/blabla'), users.User(u'infotje@example.com'), user_me]
        assert find_rogerthat_users_via_email(user_me, users_) == [user_me]

    def test_invite_response_with_user_data(self):
        user_data = { 'test1': 'bla1', 'test2': 'bla2' }

        # friend invites svc_identity_user
        invitor = users.get_current_user()

        svc_user = users.User(u's%s@example.com' % time.time())
        si = create_service_profile(svc_user, u"Default name")[1]

        invite(invitor, remove_slash_default(si.user).email(), None, None, None, None, origin=ORIGIN_USER_INVITE, app_id=App.APP_ID_ROGERTHAT)
        invited_response_receiver(UNIT_TEST_REFS["invited"], json.dumps(user_data))
        myFriendMap = get_friends_map(invitor)
        assert remove_slash_default(si.user) in myFriendMap.friends
        assert myFriendMap.generation > 0
        assert get_friend_serviceidentity_connection(invitor, si.user)

        user_data_string = FriendTO.fromDBFriendMap(myFriendMap, si.user, True, True, invitor).userData
        self.assertIsNotNone(user_data_string)
        user_data['__rt__disabledBroadcastTypes'] = list()
        self.assertDictEqual(user_data, json.loads(user_data_string))

        # test cleanup of UserData
        breakFriendShip(invitor, si.user)
        self.assertIsNone(db.get(UserData.createKey(invitor, si.user)))

    def test_invalid_user_data(self):
        invitor = users.get_current_user()
        svc_user = users.User(u's%s@example.com' % time.time())
        si = create_service_profile(svc_user, u"Default name")[1]
        makeFriends(invitor, si.user, invitor, servicetag=None, origin=ORIGIN_USER_INVITE)

        invalid_user_data = json.dumps(dict(_invalid_key=False, valid_key=True))
        set_current_user(si.service_user)
        with self.assertRaises(InvalidKeyException) as ctx:
            system.put_user_data(invitor.email(), invalid_user_data)
        self.assertEqual('_invalid_key', ctx.exception.fields['key'])

    def test_get_friends(self):
        FRIEND_AMOUNT = 14

        for x in xrange(1, FRIEND_AMOUNT + 1):
            print 'Creating friend', x
            friend_email = u'myfriend-%s@example.com' % x
            friend_user = users.User(friend_email)
            create_user_profile(friend_user, friend_email)
            if x % 2:
                convert_user_to_service(friend_user)
            print 'Connecting with friend', x
            makeFriends(users.get_current_user(), friend_user, users.get_current_user(), servicetag=None,
                        origin=ORIGIN_USER_INVITE)

        start = time.time()
        response = getFriendsList(GetFriendsListRequestTO())
        print 'getFriends took', time.time() - start, 'seconds'
        self.assertEqual(FRIEND_AMOUNT, len(response.friends))

    def test_get_friend_emails(self):
        FRIEND_AMOUNT = 14

        for x in xrange(1, FRIEND_AMOUNT + 1):
            print 'Creating friend', x
            friend_email = u'myfriend-%s@example.com' % x
            friend_user = users.User(friend_email)
            create_user_profile(friend_user, friend_email)
            if x % 2:
                convert_user_to_service(friend_user)
            print 'Connecting with friend', x
            makeFriends(users.get_current_user(), friend_user, users.get_current_user(), servicetag=None,
                        origin=ORIGIN_USER_INVITE)

        start = time.time()
        response = getFriendEmails(GetFriendEmailsRequestTO())
        l = list()
        for email in response.emails:
            r = GetFriendRequestTO()
            r.email = email
            r.avatar_size = 100
            l.append(getFriend(r))

        print 'getFriendEmails took', time.time() - start, 'seconds'
        self.assertEqual(FRIEND_AMOUNT, len(response.emails))
        self.assertEqual(FRIEND_AMOUNT, len(l))

    def test_find_friends(self):
        FRIEND_AMOUNT = 7
        for x in xrange(1, FRIEND_AMOUNT + 1):
            friend_email = u'myfriend-%s@example.com' % x
            print 'Creating friend', x
            friend_user = users.User(friend_email)
            create_user_profile(friend_user, u"myfriend-%s" % x)
            set_profile_data(users.User(u'app_admin@rogerth.at'), friend_user, "{}")
            _re_index(friend_user)

        start = time.time()
        req = FindFriendRequestTO()
        req.search_string = u""
        req.cursor = None
        req.avatar_size = 50
        response = findFriend(req)
        print 'findFriend took', time.time() - start, 'seconds' , len(response.items), 'results'
        self.assertEqual(FRIEND_AMOUNT, len(response.items))
