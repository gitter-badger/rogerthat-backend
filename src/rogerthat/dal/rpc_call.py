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

from rogerthat.dal import generator, parent_key
from rogerthat.rpc import users
from rogerthat.rpc.models import Mobile, RpcCAPICall
from google.appengine.ext import db
from mcfw.rpc import returns, arguments


@returns(db.Key)
@arguments(mobile=Mobile)
def get_rpc_capi_backlog_parent_by_mobile(mobile):
    return get_rpc_capi_backlog_parent_by_account(mobile.user, mobile.account)

@returns(db.Key)
@arguments(user=users.User, account=unicode)
def get_rpc_capi_backlog_parent_by_account(user, account):
    return db.Key.from_path("Backlog", account, parent=parent_key(user))

@returns([RpcCAPICall])
@arguments(mobile=Mobile)
def get_complete_backlog(mobile):
    qry = RpcCAPICall.gql("WHERE ANCESTOR IS :ancestor")
    qry.bind(ancestor=get_rpc_capi_backlog_parent_by_mobile(mobile))
    return generator(qry.run())

@returns([RpcCAPICall])
@arguments(mobile=Mobile, limit=int)
def get_limited_backlog(mobile, limit):
    qry = RpcCAPICall.gql("WHERE ANCESTOR IS :ancestor ORDER BY priority DESC, timestamp ASC")
    qry.bind(ancestor=get_rpc_capi_backlog_parent_by_mobile(mobile))
    return generator(qry.fetch(limit))

@returns([RpcCAPICall])
@arguments(mobile=Mobile, method=unicode)
def get_filtered_backlog(mobile, method):
    qry = RpcCAPICall.gql("WHERE ANCESTOR IS :ancestor AND method = :method ORDER BY priority DESC, timestamp ASC")
    qry.bind(ancestor=get_rpc_capi_backlog_parent_by_mobile(mobile), method=method)
    return generator(qry)
