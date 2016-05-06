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

from rogerthat.bizz.friends import makeFriends, ORIGIN_USER_INVITE
from rogerthat.dal.friend import get_friend_invitation_history_by_last_attempt_key
from rogerthat.rpc import users
from rogerthat.utils import azzert
from google.appengine.ext import webapp


class ConnectHandler(webapp.RequestHandler):
    """
    This request handler is called when a user presses the link in his invitation email to connect with the invitor.
    """

    def get(self, connect_string):
        user = users.get_current_user()
        invitation = get_friend_invitation_history_by_last_attempt_key(connect_string)
        azzert(invitation)
        makeFriends(invitation.user, user, invitation.invitee, invitation.tag, origin=ORIGIN_USER_INVITE)
        self.redirect("/")
