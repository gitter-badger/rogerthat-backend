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
from types import NoneType

from rogerthat.bizz.friends import _send_invitation_message_from_service_to_user, ORIGIN_BEACON_DETECTED, \
    BEACON_DISCOVERY
from rogerthat.dal.app import get_app_name_by_id
from rogerthat.dal.beacon import get_beacon, get_beacons
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.profile import get_user_profile
from rogerthat.dal.service import get_service_identity, get_friend_serviceidentity_connection
from rogerthat.models import Beacon, BeaconDiscovery, BeaconRegion
from rogerthat.models.properties.friend import FriendDetail, FriendDetails
from rogerthat.rpc import users
from rogerthat.rpc.models import RpcCAPICall
from rogerthat.rpc.rpc import mapping
from rogerthat.to.beacon import BeaconTO, UpdateBeaconRegionsResponseTO
from rogerthat.to.friends import FriendTO, UpdateFriendRequestTO
from rogerthat.translations import localize
from rogerthat.utils import now
from rogerthat.utils.app import get_app_id_from_app_user
from rogerthat.utils.service import get_identity_from_service_identity_user, \
    get_service_user_from_service_identity_user, remove_slash_default
from google.appengine.api import xmpp
from google.appengine.ext import db
from mcfw.consts import MISSING
from mcfw.rpc import returns, arguments
from rogerthat.settings import get_server_settings


BEACON_PROXIMITY_UNKNOWN = 0
BEACON_PROXIMITY_IMMEDIATE = 1
BEACON_PROXIMITY_NEAR = 2
BEACON_PROXIMITY_FAR = 3

BEACON_PROXIMITY_MAPPING = {BEACON_PROXIMITY_UNKNOWN: "UNKNOWN",
                            BEACON_PROXIMITY_IMMEDIATE: "IMMEDIATE",
                            BEACON_PROXIMITY_NEAR: "NEAR",
                            BEACON_PROXIMITY_FAR: "FAR"}

@returns(bool)
@arguments(beacon_uuid=unicode, beacon_name=unicode, tag=unicode, service_identity_user=users.User)
def add_new_beacon(beacon_uuid, beacon_name, tag, service_identity_user):
    keyy = Beacon.create_key(service_identity_user, beacon_name)
    beacon = Beacon.get(keyy)
    if beacon:
        return False
    beacon = Beacon(key=keyy)
    beacon.uuid = beacon_uuid.lower()
    beacon.name = beacon_name
    beacon.tag = tag
    beacon.service_identity = get_identity_from_service_identity_user(service_identity_user)
    beacon.creation_time = now()
    beacon.put()
    return True

@returns(tuple)
@arguments(app_user=users.User, beacon_uuid=unicode, beacon_name=unicode)
def add_new_beacon_discovery(app_user, beacon_uuid, beacon_name):
    '''A human user has discovered a beacon'''
    beacon_uuid = beacon_uuid.lower()
    beacon = get_beacon(beacon_uuid, beacon_name)
    if not beacon:
        logging.warn("Beacon not found: {uuid: %s, name: %s}", beacon_uuid, beacon_name)
        return None, None

    keyy = BeaconDiscovery.create_key(app_user, beacon.service_identity_user)
    beaconDiscovery = BeaconDiscovery.get(keyy)
    if beaconDiscovery:
        return beacon.service_identity_user, beacon.tag

    BeaconDiscovery(key=keyy, creation_time=now()).put()

    si = get_service_identity(beacon.service_identity_user)
    if not si:
        logging.error("Service identity not found for service_identity_user: %s" % beacon.service_identity_user)
    elif not si.beacon_auto_invite:
        logging.info("Beacon detected but %s does not allow auto invite {user %s, uuid: %s, name: %s}",
                     beacon.service_identity_user, app_user, beacon_uuid, beacon_name)
    elif get_app_id_from_app_user(app_user) not in si.appIds:
        logging.info("Beacon detected but %s does not contain app_id of user %s: {uuid: %s, name: %s}",
                     beacon.service_identity_user, app_user, beacon_uuid, beacon_name)
        return None, None
    elif get_friend_serviceidentity_connection(app_user, beacon.service_identity_user):
        logging.info("Beacon detected but %s and %s were already friends: {uuid: %s, name: %s}",
                     app_user, beacon.service_identity_user, beacon_uuid, beacon_name)
    else:
        # Fake a deleted connection between service and human user to be able to show the service's avatar on the phone
        friend_map = get_friends_map(app_user)
        friend_map.generation += 1
        friend_map.version += 1
        friend_map.put()

        friend_detail = FriendDetails().addNew(remove_slash_default(beacon.service_identity_user),
                                               si.name, si.avatarId, type_=FriendDetail.TYPE_SERVICE)
        friend_detail.relationVersion = -1

        from rogerthat.bizz.job.update_friends import _do_update_friend_request
        _do_update_friend_request(app_user, friend_detail, UpdateFriendRequestTO.STATUS_ADD, friend_map,
                                  extra_conversion_kwargs=dict(existence=FriendTO.FRIEND_EXISTENCE_DELETED,
                                                               includeServiceDetails=False))

        user_profile = get_user_profile(app_user)
        app_name = get_app_name_by_id(user_profile.app_id)
        m = localize(user_profile.language, "_automatic_detection_invitation", app_name=app_name, service_name=si.name)
        _send_invitation_message_from_service_to_user(app_user, beacon.service_identity_user, m,
                                                      si.descriptionBranding, user_profile.language,
                                                      ORIGIN_BEACON_DETECTED, BEACON_DISCOVERY)

        message = "Beacon detected at %s (%s) with tag: %s" % (si.name.encode('utf8'),
                                                               remove_slash_default(si.service_identity_user).email().encode('utf8'),
                                                               beacon.tag.encode('utf8'))

        server_settings = get_server_settings()
        xmpp.send_message(server_settings.xmppInfoMembers, message, message_type=xmpp.MESSAGE_TYPE_CHAT)

    return beacon.service_identity_user, beacon.tag

@returns(bool)
@arguments(app_user=users.User, service_identity_user=users.User)
def remove_beacon_discovery(app_user, service_identity_user):
    keyy = BeaconDiscovery.create_key(app_user, service_identity_user)
    beaconDiscovery = BeaconDiscovery.get(keyy)
    if beaconDiscovery:
        logging.info("removed BeaconDiscovery between user: %s and siu: %s" % (app_user, service_identity_user))
        beaconDiscovery.delete()
        return True
    else:
        return False

@returns(NoneType)
@arguments(service_identity_user=users.User, beacons=[BeaconTO])
def update_beacons(service_identity_user, beacons):
    from rogerthat.bizz.service import BeaconAlreadyCoupledException, NoBeaconRegionFoundException

    if beacons is MISSING or beacons is None:
        beacons = list()

    service_user = get_service_user_from_service_identity_user(service_identity_user)
    identifier = get_identity_from_service_identity_user(service_identity_user)

    @db.non_transactional
    def _validate_beacon(beacon_name, beacon_uuid, beacon_major, beacon_minor, supported_app_ids):
        b = get_beacon(beacon_uuid, beacon_name)
        if b and b.service_identity_user != service_identity_user:
            raise BeaconAlreadyCoupledException(beacon_uuid, beacon_major, beacon_minor)

        for beacon_region in BeaconRegion.all().filter('uuid', beacon_uuid):
            if beacon_region.major is not None:
                if beacon_region.major != beacon_major:
                    continue  # the beacon does not belong to this region

                if beacon_region.minor is not None:
                    if beacon_region.mino != beacon_minor:
                        continue  # the beacon does not belong to this region

            if beacon_region.app_id not in supported_app_ids:
                continue  # the service_identity does not support this app

            break
        else:
            raise NoBeaconRegionFoundException(beacon_uuid, beacon_major, beacon_minor)


    def trans():
        l = get_beacons(service_user, identifier)
        db.delete(l)
        beacons_to_put = list()
        for beacon in beacons:
            beacon_name = u"%s|%s" % (beacon.major, beacon.minor)
            beacon_uuid = beacon.uuid.lower()
            _validate_beacon(beacon_name, beacon_uuid, beacon.major, beacon.minor,
                             get_service_identity(service_identity_user).appIds)
            b = Beacon(key=Beacon.create_key(service_identity_user, beacon_name))
            b.uuid = beacon_uuid
            b.name = beacon_name
            b.tag = beacon.tag
            b.service_identity = identifier
            b.creation_time = now()
            beacons_to_put.append(b)
        if beacons_to_put:
            db.put(beacons_to_put)

    if db.is_in_transaction():
        return trans()
    else:
        return db.run_in_transaction(trans)

@mapping('com.mobicage.capi.location.update_beacon_regions_response')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=UpdateBeaconRegionsResponseTO)
def update_beacon_regions_response(context, result):
    pass
