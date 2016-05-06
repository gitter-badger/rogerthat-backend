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

from rogerthat.dal.profile import is_service_identity_user, is_trial_service, get_user_profile
from rogerthat.rpc import users
from rogerthat.to.profile import CompleteProfileTO
from google.appengine.api import blobstore
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments


@rest("/mobi/rest/profile/avatar_upload_url", "get")
@returns(unicode)
@arguments()
def get_avatar_upload_url():
    return blobstore.create_upload_url('/mobi/profile/avator/post')

@rest("/mobi/rest/profile/get", "get")
@returns(CompleteProfileTO)
@arguments()
def get_profile_rest():
    from rogerthat.dal.profile import get_profile_info
    profile_info = get_profile_info(users.get_current_user(), skip_warning=True)
    if not profile_info:
        return None
    return CompleteProfileTO.fromProfileInfo(profile_info)

@rest("/mobi/rest/profile/update", "post")
@returns(unicode)
@arguments(name=unicode, tmp_avatar_key=str, x1=(float, int), y1=(float, int), x2=(float, int), y2=(float, int),
           language=unicode)
def update_profile(name, tmp_avatar_key, x1, y1, x2, y2, language):
    from rogerthat.bizz.profile import update_service_profile, update_user_profile
    user = users.get_current_user()
    x1 = float(x1)
    x2 = float(x2)
    y1 = float(y1)
    y2 = float(y2)
    try:
        if is_service_identity_user(user):
            update_service_profile(user, tmp_avatar_key, x1, y1, x2, y2, is_trial_service(user))
        else:
            update_user_profile(user, name, tmp_avatar_key, x1, y1, x2, y2, language)

    except Exception, e:
        logging.exception(e)
        return e.message

@rest("/mobi/rest/profile/update_avatar", "post")
@returns(unicode)
@arguments(tmp_avatar_key=str, x1=(float, int), y1=(float, int), x2=(float, int), y2=(float, int))
def update_profile_avatar(tmp_avatar_key, x1, y1, x2, y2):
    from rogerthat.bizz.profile import update_service_profile, update_user_profile
    user = users.get_current_user()
    x1 = float(x1)
    x2 = float(x2)
    y1 = float(y1)
    y2 = float(y2)
    try:
        if is_service_identity_user(user):
            update_service_profile(user, tmp_avatar_key, x1, y1, x2, y2, is_trial_service(user))
        else:
            user_profile = get_user_profile(user, False)
            update_user_profile(user, user_profile.name, tmp_avatar_key, x1, y1, x2, y2, user_profile.language)
    except Exception, e:
        logging.exception(e)
        return e.message
