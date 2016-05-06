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

from rogerthat.dal import parent_key, generator
from rogerthat.models import MessageFlowDesign, MessageFlowRunRecord, ServiceMenuDef, ServiceInteractionDef
from rogerthat.rpc import users
from rogerthat.utils import azzert
from rogerthat.utils.tree import TreeItem
from google.appengine.ext import db
from mcfw.rpc import returns, arguments


@returns([MessageFlowDesign])
@arguments(service_user=users.User)
def get_service_message_flow_designs(service_user):
    qry = MessageFlowDesign.gql("WHERE ANCESTOR IS :ancestor and deleted = false ORDER BY multilanguage DESC, name ASC")
    qry.bind(ancestor=parent_key(service_user))
    return generator(qry.run())

@returns([MessageFlowDesign])
@arguments(service_user=users.User)
def get_multilanguage_message_flow_designs(service_user):
    qry = MessageFlowDesign.gql("WHERE ANCESTOR IS :ancestor and deleted = false and multilanguage = true")
    qry.bind(ancestor=parent_key(service_user))
    return qry.fetch(None)

@returns([MessageFlowDesign])
@arguments(service_user=users.User, status=int)
def get_message_flow_designs_by_status(service_user, status):
    qry = MessageFlowDesign.gql("WHERE ANCESTOR IS :ancestor and deleted = false and status = :status")
    qry.bind(ancestor=parent_key(service_user), status=status)
    return qry.fetch(None)

@returns([MessageFlowDesign])
@arguments(service_user=users.User, status=int)
def get_multilanguage_message_flow_designs_by_status(service_user, status):
    qry = MessageFlowDesign.gql("WHERE ANCESTOR IS :ancestor and deleted = false and multilanguage = true and status = :status")
    qry.bind(ancestor=parent_key(service_user), status=status)
    return qry.fetch(None)

@returns(MessageFlowDesign)
@arguments(service_user=users.User, name=unicode)
def get_service_message_flow_design_by_name(service_user, name):
    return db.get(get_service_message_flow_design_key_by_name(service_user, name))

@returns(db.Key)
@arguments(service_user=users.User, name=unicode)
def get_service_message_flow_design_key_by_name(service_user, name):
    return db.Key.from_path(MessageFlowDesign.kind(), name, parent=parent_key(service_user))

@returns(MessageFlowRunRecord)
@arguments(service_user=users.User, message_flow_run_id=unicode)
def get_message_flow_run_record(service_user, message_flow_run_id):
    return MessageFlowRunRecord.get_by_key_name(MessageFlowRunRecord.createKeyName(service_user, message_flow_run_id))

@returns([db.Key])
@arguments(flow_key=db.Key)
def get_message_flow_design_keys_by_sub_flow_key(flow_key):
    kind = MessageFlowDesign.kind()
    azzert(flow_key.kind() == kind)
    qry = MessageFlowDesign.gql("WHERE sub_flows = :flow AND ANCESTOR IS :ancestor AND deleted = false")
    qry.bind(flow=flow_key, ancestor=flow_key.parent())
    for mfd in qry.run():
        yield mfd.key()

@returns(bool)
@arguments(mfd=MessageFlowDesign)
def is_message_flow_used_by_menu_item(mfd):
    return ServiceMenuDef.all().ancestor(parent_key(mfd.user)).filter('staticFlowKey =', str(mfd.key())).count() > 0

@returns(bool)
@arguments(mfd=MessageFlowDesign)
def is_message_flow_used_by_qr_code(mfd):
    return ServiceInteractionDef.all().ancestor(parent_key(mfd.user)).filter('staticFlowKey =', str(mfd.key())).count() > 0

@returns([MessageFlowDesign])
@arguments(flow_key=db.Key)
def get_message_flow_designs_by_sub_flow_key(flow_key):
    kind = MessageFlowDesign.kind()
    azzert(flow_key.kind() == kind)
    qry = MessageFlowDesign.gql("WHERE sub_flows = :flow AND ANCESTOR IS :ancestor AND deleted = false")
    qry.bind(flow=flow_key, ancestor=flow_key.parent())
    return generator(qry.run())

@returns([MessageFlowDesign])
@arguments(message_flow_design=MessageFlowDesign)
def get_super_message_flows(message_flow_design):
    # Build possibly out of date set of super flows
    result_set = set()
    super_keys_to_check_set = set()
    super_keys_checked_set = set()
    super_keys_to_check_set.add(message_flow_design.key())
    while super_keys_to_check_set:
        flow_key = super_keys_to_check_set.pop()
        super_keys_checked_set.add(flow_key)
        for flow in get_message_flow_designs_by_sub_flow_key(flow_key):
            message_flow_key = flow.key()
            result_set.add(message_flow_design if message_flow_key == message_flow_design.key() else flow)
            if not message_flow_key in super_keys_checked_set:
                super_keys_to_check_set.add(message_flow_key)

    # Create tree of super_flows to determine a correct super_flow tree
    tree_lookup = dict()
    message_flow_design_tree_item = TreeItem(message_flow_design)
    tree_lookup[message_flow_design.key()] = message_flow_design_tree_item
    for flow in result_set:
        flow_key = flow.key()
        if not flow_key in tree_lookup:
            tree_lookup[flow_key] = TreeItem(flow)
    for flow in result_set:
        super_flow_tree_item = tree_lookup[flow.key()]
        for sub_flow_key in flow.sub_flows:
            if sub_flow_key in tree_lookup:
                tree_lookup[sub_flow_key].parents.add(super_flow_tree_item)

    # Flatten the super_flow tree into a set
    result_set = set()
    def add_parents_to_set(tree_item):
        for parent_tree_item in tree_item.parents:
            if not parent_tree_item.tag in result_set:
                result_set.add(parent_tree_item.tag)
                add_parents_to_set(parent_tree_item)
    add_parents_to_set(message_flow_design_tree_item)

    return list(result_set)

@returns([MessageFlowDesign])
@arguments(message_flow_design=MessageFlowDesign, context=dict)
def get_sub_message_flows(message_flow_design, context):
    result = list()
    keys_to_fetch = set()
    keys_fetched = set()
    keys_to_fetch.update(message_flow_design.sub_flows)
    while keys_to_fetch:
        designs = db.get(keys_to_fetch)
        _check_for_empty_message_flows(keys_to_fetch, designs)
        designs = [ context.get(f.key(), f) for f in designs ]
        result.extend(designs)
        keys_fetched.update(keys_to_fetch)
        keys_to_fetch.clear()
        for design in designs:
            for flow_key in (k for k in design.sub_flows if not k in keys_fetched):
                keys_to_fetch.add(flow_key)
    return result

def _check_for_empty_message_flows(keys, objects):
    for key, obj in zip(keys, objects):
        if not obj or obj.deleted:
            azzert(False, "Message flow %s does not exist!" % key.name())
