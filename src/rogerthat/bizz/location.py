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

import base64
import json
import logging
import math
import urllib
import uuid
from datetime import datetime
from struct import unpack
from types import NoneType

from babel.dates import format_datetime, get_timezone
from google.appengine.api import memcache, urlfetch
from google.appengine.api.urlfetch import fetch
from google.appengine.ext import db, deferred

from mcfw.consts import MISSING
from mcfw.rpc import returns, arguments, serialize_complex_value
from rogerthat.bizz.messaging import sendMessage, dashboardNotification
from rogerthat.capi.location import getLocation, locationResult, trackLocation
from rogerthat.consts import MC_DASHBOARD
from rogerthat.consts import SCHEDULED_QUEUE
from rogerthat.dal import parent_key
from rogerthat.dal.app import get_app_by_user, get_app_name_by_id
from rogerthat.dal.beacon import get_beacon
from rogerthat.dal.friend import get_friends_map
from rogerthat.dal.location import get_current_tracker
from rogerthat.dal.profile import get_profile_infos, get_user_profile, get_service_profile
from rogerthat.dal.service import get_service_identity
from rogerthat.models import CellTower, Message, LocationRequest, UserProfile, \
    ServiceLocationTracker
from rogerthat.rpc import users
from rogerthat.rpc.models import RpcCAPICall, Mobile, ServiceAPICallback
from rogerthat.rpc.rpc import mapping, logError, dismissError
from rogerthat.rpc.service import logServiceError, ServiceApiException
from rogerthat.rpc.users import User
from rogerthat.service.api.friends import in_reach, out_of_reach, \
    location_fix
from rogerthat.settings import get_server_settings
from rogerthat.to.activity import RawLocationInfoTO, GeoPointTO, GeoPointWithTimestampTO, LogLocationRecipientTO
from rogerthat.to.beacon import BeaconTO
from rogerthat.to.location import FriendLocationTO, GetLocationResponseTO, LocationResultResponseTO, \
    GetLocationRequestTO, LocationResultRequestTO, DeleteBeaconDiscoveryResponseTO, GetLocationErrorTO, \
    TrackLocationRequestTO, TrackLocationResponseTO
from rogerthat.to.messaging import ButtonTO, UserMemberTO
from rogerthat.to.service import UserDetailsTO
from rogerthat.translations import localize
from rogerthat.utils import channel, now, azzert
from rogerthat.utils.app import create_app_user, get_human_user_from_app_user, get_app_user_tuple
from rogerthat.utils.crypto import decrypt
from rogerthat.utils.service import get_service_identity_tuple, \
    get_service_user_from_service_identity_user, \
    get_identity_from_service_identity_user, remove_slash_default, add_slash_default

EARTH_RADIUS = 6371000
ACCURACY_COMPARATION_FACTOR = 3

class CannotDetermineLocationException(Exception):
    pass

class CanOnlyTrackServiceSubscriptionsException(ServiceApiException):
    def __init__(self):
        ServiceApiException.__init__(self, ServiceApiException.BASE_CODE_LOCATION + 1,
                                     "Can only track subscribed users.")

@returns(GeoPointTO)
@arguments(raw_info=RawLocationInfoTO)
def get_location(raw_info):

    def _to_geo_point_to(geoPoint):
        gp = GeoPointTO()
        gp.accuracy = 999
        gp.latitude = int(geoPoint.lat * 1000000)
        gp.longitude = int(geoPoint.lon * 1000000)
        return gp

    def _get_location_via_cid_lac_in_datastore():
        tower = CellTower.all().filter("cid =", raw_info.cid).filter("lac =", raw_info.lac).filter("net =", raw_info.net).get()
        if tower:
            return tower.geoPoint
        else:
            return None

    def _get_location_via_cid_lac_in_hidden_android_api():
        def encode_request():
            a = '000E00000000000000000000000000001B0000000000000000000000030000'
            b = hex(raw_info.cid)[2:].zfill(8) + hex(raw_info.lac)[2:].zfill(8)
            c = hex(divmod(raw_info.net, 100)[1])[2:].zfill(8) + hex(divmod(raw_info.net, 100)[0])[2:].zfill(8)
            return (a + b + c + 'FFFFFFFF00000000').decode('hex')

        body = encode_request()
        headers = dict()
        headers['Content-Type'] = u'application/binary'
        headers['Content-Length'] = unicode(len(body))

        try:
            logging.info("Getting location of celltower from google:\nbody:\n" + base64.encodestring(body))
            response = fetch('http://www.google.com/glm/mmap', body, 'POST', headers)
        except urlfetch.Error, e:
            logging.error(e)
            raise CannotDetermineLocationException(e)

        if response.status_code != 200:
            logging.error("Request to hidden api failed!")
            raise CannotDetermineLocationException()

        if not len(response.content) == 25:
            logging.warning("Received invalid reply:\n" + base64.encodestring(response.content))
            raise CannotDetermineLocationException()

        (_, _, _, latitude, longitude, _, _, _) = unpack(">hBiiiiih", response.content)
        return _to_geo_point_to(db.GeoPt(latitude / 1000000.0, longitude / 1000000.0))

    memcache_key = "cid_%s_lac_%s_net%s" % (raw_info.cid, raw_info.lac, raw_info.net)
    geoPoint = memcache.get(memcache_key)  # @UndefinedVariable
    if geoPoint:
        return _to_geo_point_to(geoPoint)

    geoPoint = _get_location_via_cid_lac_in_datastore()
    if geoPoint:
        memcache.set(memcache_key, geoPoint)  # @UndefinedVariable
        return _to_geo_point_to(geoPoint)

    geoPointTO = _get_location_via_cid_lac_in_hidden_android_api()
    ct = CellTower()
    ct.lac = raw_info.lac
    ct.cid = raw_info.cid
    ct.net = raw_info.net
    ct.geoPoint = db.GeoPt(geoPointTO.latitude / 1000000.0, geoPointTO.longitude / 1000000.0)
    ct.put()
    memcache.set(memcache_key, ct.geoPoint)  # @UndefinedVariable
    return geoPointTO


@returns(bool)
@arguments(loc1=GeoPointTO, loc2=GeoPointTO)
def compare(loc1, loc2):
    acc_factor = loc1.accuracy / loc2.accuracy
    if 1 / ACCURACY_COMPARATION_FACTOR < acc_factor < ACCURACY_COMPARATION_FACTOR:
        if (loc1.longitude, loc1.latitude) == (loc2.longitude, loc2.latitude):
            return True
        dist = distance(loc1, loc2)
        return min(loc1.accuracy, loc2.accuracy) > dist
    else:
        return False

@returns(float)
@arguments(loc1=GeoPointTO, loc2=GeoPointTO)
def distance(loc1, loc2):
    lat1 = loc1.latitude * math.pi / 180
    lat2 = loc2.latitude * math.pi / 180
    lon1 = loc1.longitude * math.pi / 180
    lon2 = loc2.longitude * math.pi / 180
    return math.acos(math.sin(lat1) * math.sin(lat2) + \
                     math.cos(lat1) * math.cos(lat2) * \
                     math.cos(lon2 - lon1)) * EARTH_RADIUS;

@returns(NoneType)
@arguments(app_user=User, location=GeoPointTO, timestamp=int, recipients=[LogLocationRecipientTO])
def post(app_user, location, timestamp, recipients):
    def parse_location(friend_language, accuracy, geocoded_results):
        # See https://developers.google.com/maps/documentation/geocoding/#Results
        if accuracy < 100:
            for result in results:
                if "street_address" in result["types"]:
                    return "\n" + localize(friend_language, "Location: %(address)s" , address=result["formatted_address"])
            return "\n" + localize(friend_language, "Location: %(address)s", address=results[0]["formatted_address"])

        address_types = ["neighborhood", "sublocality", "locality", "political", "route"]
        for adt in address_types:
            for result in results:
                if adt in result["types"]:
                    return "\n" + localize(friend_language, "Location: %(address)s", address=result["formatted_address"])
        logging.error("Could not parse geo-coded result!")

#    def run():
#        ul = get_user_location(user)
#        ul.geoPoint = location.toGeoPoint()
#        ul.accuracy = location.accuracy
#        ul.timestamp = timestamp
#        if not ul.members:
#            # initiate members
#            ul.members = list()
#            fmap = get_friends_map(user)
#            for friend in fmap.friends:
#                fdet = fmap.friendDetails[friend.email()]
#                if fdet.shareLocation:
#                    ul.members.append(friend)
#        ul.put()
#    db.run_in_transaction(run)
#    loc = GeoPointWithTimestampTO()
#    loc.latitude = location.latitude
#    loc.longitude = location.longitude
#    loc.accuracy = location.accuracy
#    loc.timestamp = timestamp
#    memcache.set("location_"+user.email(), loc)

    loc = GeoPointWithTimestampTO()
    loc.latitude = location.latitude
    loc.longitude = location.longitude
    loc.accuracy = location.accuracy
    loc.timestamp = timestamp

    maps_lat = loc.latitude / 1000000.0
    maps_long = loc.longitude / 1000000.0

    current_user, app_id = get_app_user_tuple(app_user)

    for recipient in (r for r in recipients if r.target == GetLocationRequestTO.TARGET_SERVICE_LOCATION_TRACKER):
        location_with_timestamp = GeoPointWithTimestampTO()
        location_with_timestamp.latitude = location.latitude
        location_with_timestamp.longitude = location.longitude
        location_with_timestamp.accuracy = location.accuracy
        location_with_timestamp.timestamp = timestamp
        handle_service_tracker_results(app_user, add_slash_default(users.User(recipient.friend)), location_with_timestamp)

    for recipient in (r for r in recipients if r.target in (GetLocationRequestTO.TARGET_MOBILE, GetLocationRequestTO.TARGET_MOBILE_FIRST_REQUEST_AFTER_GRANT)):
        friend_user = create_app_user(users.User(recipient.friend), app_id)
        def trans():
            lr = LocationRequest.get_by_key_name(friend_user.email(), parent=parent_key(app_user))
            if not lr:
                return False
            lr.delete()
            return True
        if not db.run_in_transaction(trans):
            continue


        profile, friend_profile = get_profile_infos([app_user, friend_user], expected_types=[UserProfile, UserProfile])
        if recipient.target == GetLocationRequestTO.TARGET_MOBILE:
            m = localize(friend_profile.language, """Received location of %(name)s.

Accuracy: %(accuracy)sm""", name=profile.name, accuracy=loc.accuracy)
        else:
            m = localize(friend_profile.language, """%(name)s accepted your location sharing request.
Latest information:

Accuracy: %(accuracy)sm""", name=profile.name, accuracy=loc.accuracy)
        url = "https://maps.googleapis.com/maps/api/geocode/json?latlng=%s,%s&sensor=true" % (maps_lat, maps_long)
        logging.info("Fetching URL: %s" % url)
        result = urlfetch.fetch(url)
        logging.info("Fetched result: %s" % result.content)
        logging.info("Result status code: %s" % result.status_code)
        if result.status_code == 200:
            results = json.loads(result.content)
            if results["status"] == "OK" and results["results"]:
                results = results["results"]
                location = parse_location(friend_profile.language, loc.accuracy, results)
                if location:
                    m += location
        button = ButtonTO()
        button.id = u"show_map"
        button.caption = localize(friend_profile.language, "Show map")
        button.action = u"geo://%s,%s" % (str(maps_lat).replace(',', '.'), str(maps_long).replace(',', '.'))
        button.ui_flags = 0
        sendMessage(MC_DASHBOARD, [UserMemberTO(friend_user)], Message.FLAG_ALLOW_DISMISS, 0, None, m, [button], None,
                    get_app_by_user(friend_user).core_branding_hash, None, is_mfr=False)
    mobile_recipients = [create_app_user(users.User(r.friend), app_id) for r in recipients if r.target == GetLocationRequestTO.TARGET_MOBILE_FRIENDS_ON_MAP]
    request = LocationResultRequestTO()
    request.friend = current_user.email()
    request.location = loc
    locationResult(get_location_result_response_handler, logError, mobile_recipients, request=request)
    web_recipients = [r for r in recipients if r.target == GetLocationRequestTO.TARGET_WEB]
    for recipient in web_recipients:
        friend_user = create_app_user(users.User(recipient.friend), app_id)
        channel.send_message(friend_user, 'rogerthat.location.location_response', friend=current_user.email(), location=serialize_complex_value(loc, GeoPointWithTimestampTO, False))

@returns(GeoPointWithTimestampTO)
@arguments(app_user=users.User, friend=users.User, target=int)
def get_friend_location(app_user, friend, target=0):
    myFriendMap = get_friends_map(app_user)
    if not friend.email() in myFriendMap.friendDetails:
        logging.warning("%s is not in %s his/her friendMap anymore. Ignoring getFriendLocation request.", friend, app_user)
        return
    friendDetail = myFriendMap.friendDetails[friend.email()]
    if not friendDetail.sharesLocation:
        return
    friend_profile = get_user_profile(friend)
    if not friend_profile.mobiles:
        return
    request = GetLocationRequestTO()
    request.friend = get_human_user_from_app_user(app_user).email()
    request.high_prio = False
    if target == 0:
        request.target = GetLocationRequestTO.TARGET_MOBILE if users.get_current_mobile() else GetLocationRequestTO.TARGET_WEB
    else:
        request.target = target
    xg_on = db.create_transaction_options(xg=True)
    def trans():
        capi_calls = getLocation(get_location_response_handler, get_location_response_error_handler, friend, request=request, DO_NOT_SAVE_RPCCALL_OBJECTS=True)
        lr = LocationRequest(parent=parent_key(friend), key_name=app_user.email(), timestamp=now())
        db.put_async(lr)
        for capi_call in capi_calls:
            capi_call.lr = lr.key()
            capi_call.target = target
        db.put(capi_calls)
        deferred.defer(_cancel_location_request, lr, None, target, None, _countdown=17 * 60, _transactional=True, _queue=SCHEDULED_QUEUE)
    db.run_in_transaction_options(xg_on, trans)

@returns(int)
@arguments(app_user=users.User)
def request_friend_locations(app_user):
    request = GetLocationRequestTO()
    request.high_prio = False
    request.friend = get_human_user_from_app_user(app_user).email()
    request.target = GetLocationRequestTO.TARGET_MOBILE_FRIENDS_ON_MAP if users.get_current_mobile() else GetLocationRequestTO.TARGET_WEB
    myFriendMap = get_friends_map(app_user)
    location_sharing_friends = list()
    for friend in myFriendMap.friends:
        friendDetail = myFriendMap.friendDetails[friend.email()]
        if friendDetail.sharesLocation:
            location_sharing_friends.append(friend)
    return len(getLocation(get_location_response_handler, dismissError, location_sharing_friends, request=request))

@returns([FriendLocationTO])
@arguments(app_user=users.User)
def get_friend_locations(app_user):
    request_friend_locations(app_user)
    return list()

@mapping('com.mobicage.capi.location.get_location_response_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=GetLocationResponseTO)
def get_location_response_handler(context, result):
    if result and result.error and result.error is not MISSING:
        _process_get_location_response_error(context, result.error)

@mapping('com.mobicage.capi.location.get_location_response_error_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, error=(str, unicode))
def get_location_response_error_handler(context, error):
    _process_get_location_response_error(context, None)

@mapping('com.mobicage.capi.location.get_location_result_response_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=LocationResultResponseTO)
def get_location_result_response_handler(context, result):
    pass

@mapping('com.mobicage.capi.location.track_location_response_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=TrackLocationResponseTO)
def track_location_response_handler(context, result):
    pass

@mapping('com.mobicage.capi.location.track_location_response_error_handler')
@returns(NoneType)
@arguments(context=RpcCAPICall, error=(str, unicode))
def track_location_response_error_handler(context, error):
    pass

@returns(NoneType)
@arguments(context=RpcCAPICall, error=GetLocationErrorTO)
def _process_get_location_response_error(context, error):
    if error:
        logging.debug("getLocation failed. status: %s, reason: %s", error.status, error.message)
        error_status = error.status
    else:
        error_status = GetLocationErrorTO.STATUS_TRACKING_POLICY

    if hasattr(context, 'lr'):
        location_request = db.get(context.lr)
        if location_request:
            logging.info("Failed resolving location of %s - this was requested by user %s for target %s",
                         location_request.friend, location_request.user, context.target)
            deferred.defer(_cancel_location_request, location_request, context.mobileKeyName, context.target,
                           error_status, _transactional=db.is_in_transaction())
        else:
            logging.info("Failed to cancel location_request. It was probably already deleted by the timeout.")

def _cancel_location_request(location_request, mobile_key_name, target, error_status):
    xg_on = db.create_transaction_options(xg=True)
    def trans():
        location_request_from_ds = db.get(location_request.key())
        if location_request_from_ds and location_request.timestamp == location_request_from_ds.timestamp:
            deferred.defer(_send_notification_about_failed_location_fix, location_request.user, location_request.friend,
                           mobile_key_name, target, error_status, _transactional=True)
            location_request.delete()
    db.run_in_transaction_options(xg_on, trans)

def _send_notification_about_failed_location_fix(user, friend, friend_mobile_key_name, target, error_status):
    '''
    @param user: The user who sent the location request.
    @param friend: The user who failed to execute the location request.
    @param friend_mobile_key_name: The key name of the friend's Mobile model.
    @param target: The reason of the location request. One of GetLocationRequestTO.TARGET_*.
    @param error_status: The reason of the failed location request. One of GetLocationErrorTO.STATUS_*.
    '''
    friend_profile, user_profile = get_profile_infos([friend, user], expected_types=[UserProfile, UserProfile])
    app_name = get_app_name_by_id(user_profile.app_id)
    friend_msg = None
    user_reason_msg = None
    if error_status in (GetLocationErrorTO.STATUS_AUTHORIZATION_DENIED,
                        GetLocationErrorTO.STATUS_AUTHORIZATION_ONLY_WHEN_IN_USE):
        if error_status == GetLocationErrorTO.STATUS_AUTHORIZATION_DENIED:
            friend_msg = localize(friend_profile.language, "_location_services_denied",
                                  name=user_profile.name, app_name=app_name)
            user_reason_msg = localize(user_profile.language, "_friend_denied_location_services",
                                       name=friend_profile.name, app_name=app_name)
        elif error_status == GetLocationErrorTO.STATUS_AUTHORIZATION_ONLY_WHEN_IN_USE:
            friend_msg = localize(friend_profile.language, "_location_services_denied",
                                  name=user_profile.name, app_name=app_name)
            user_reason_msg = localize(user_profile.language, "_friend_denied_location_services",
                                       name=friend_profile.name, app_name=app_name)

        if friend_msg:
            friend_mobile = Mobile.get_by_key_name(friend_mobile_key_name)
            if friend_mobile.is_ios and friend_mobile.osVersion:
                if friend_mobile.osVersion.startswith('7'):
                    friend_msg += "\n\n" + localize(friend_profile.language, "_enable_location_services_ios7",
                                                    app_name=app_name)
                elif friend_mobile.osVersion.startswith('8'):
                    friend_msg += "\n\n" + localize(friend_profile.language, "_enable_location_services_ios8",
                                                    app_name=app_name)

    if target == GetLocationRequestTO.TARGET_MOBILE:
        user_msg = localize(user_profile.language,
                            "We could not determine the location of %(name)s.",
                            name=friend_profile.name)
    elif target == GetLocationRequestTO.TARGET_MOBILE_FIRST_REQUEST_AFTER_GRANT:
        user_msg = localize(user_profile.language,
                            "%(name)s accepted your location sharing request. Unfortunately we could not determine his/her location at this moment.",
                            name=friend_profile.name)
    else:
        logging.error("Don't know what to do in _send_notification_about_failed_location_fix.\n\nLocals:\n%s" % locals())
        return

    if user_reason_msg:
        user_msg = u"%s (%s)" % (user_msg, user_reason_msg)

    if user_msg and not friend_msg:
        user_msg = u"%s\n\n%s" % (user_msg, localize(user_profile.language, "Please try again later."))

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, dashboardNotification, user, user_msg)
    if friend_msg:
        db.run_in_transaction_options(xg_on, dashboardNotification, friend, friend_msg)

@mapping('com.mobicage.capi.location.deleteBeaconDiscovery_response')
@returns(NoneType)
@arguments(context=RpcCAPICall, result=DeleteBeaconDiscoveryResponseTO)
def delete_beacon_discovery_response(context, result):
    pass

@returns(NoneType)
@arguments(app_user=users.User, service_identity_user=users.User, beacon_uuid=unicode, beacon_name=unicode,
           proximity=long)
def update_friend_in_reach(app_user, service_identity_user, beacon_uuid, beacon_name, proximity):
    from rogerthat.bizz.beacon import BEACON_PROXIMITY_MAPPING
    from rogerthat.bizz.friends import in_reach_response_receiver

    service_user, identifier = get_service_identity_tuple(service_identity_user)
    b = get_beacon(beacon_uuid, beacon_name)
    if b and b.service_user == service_user:
        service_profile = get_service_profile(service_user)
        user_details = [UserDetailsTO.fromUserProfile(get_user_profile(app_user))]
        beacon = BeaconTO.fromModel(b)
        in_reach(in_reach_response_receiver, logServiceError, service_profile,
                 service_identity=identifier, user_details=user_details, beacon=beacon,
                 proximity=BEACON_PROXIMITY_MAPPING[proximity],
                 timestamp=users.get_current_backlog_item_timestamp())

@returns(NoneType)
@arguments(app_user=users.User, service_identity_user=users.User, beacon_uuid=unicode, beacon_name=unicode)
def update_friend_out_of_reach(app_user, service_identity_user, beacon_uuid, beacon_name):
    from rogerthat.bizz.friends import out_of_reach_response_receiver

    service_user, identifier = get_service_identity_tuple(service_identity_user)
    b = get_beacon(beacon_uuid, beacon_name)
    if b and b.service_user == service_user:
        service_profile = get_service_profile(service_user)
        user_details = [UserDetailsTO.fromUserProfile(get_user_profile(app_user))]
        beacon = BeaconTO.fromModel(b)
        out_of_reach(out_of_reach_response_receiver, logServiceError, service_profile,
                     service_identity=identifier, user_details=user_details, beacon=beacon,
                     timestamp=users.get_current_backlog_item_timestamp())

@returns(unicode)
@arguments(service_identity_user=users.User, app_user=users.User, until=int, distance_filter=int)
def start_service_location_tracking(service_identity_user, app_user, until, distance_filter):
    from rogerthat.bizz.friends import areFriends
    service_profile_info, human_profile_info = get_profile_infos([service_identity_user, app_user])
    if not areFriends(service_profile_info, human_profile_info):
        raise CanOnlyTrackServiceSubscriptionsException()
    def trans():
        slt = get_current_tracker(app_user, service_identity_user)
        if slt:
            return slt.encrypted_key()
        key = ServiceLocationTracker.create_key(app_user, str(uuid.uuid4()))
        slt = ServiceLocationTracker(key=key, creation_time=now(), until=until, enabled=True,
                               service_identity_user=service_identity_user)
        slt.put()
        request = TrackLocationRequestTO()
        request.high_prio = True
        request.friend = remove_slash_default(service_identity_user).email()
        request.target = GetLocationRequestTO.TARGET_SERVICE_LOCATION_TRACKER
        request.until = until
        request.distance_filter = distance_filter
        for capi_call in trackLocation(track_location_response_handler, track_location_response_error_handler, app_user,
                                       request=request, DO_NOT_SAVE_RPCCALL_OBJECTS=True):
            capi_call.tracker = key
            capi_call.put()
        return slt.encrypted_key()
    return db.run_in_transaction(trans)

@arguments(location=GeoPointWithTimestampTO, service_identity_user=users.User, app_user=users.User, slt_key=db.Key)
def notify_location_tracking_enabled(location, service_identity_user, app_user, slt_key):
    slt = db.get(slt_key)
    server_settings = get_server_settings()
    query = urllib.urlencode((("location", "%s,%s" % (location.latitude_degrees, location.longitude_degrees)), ("timestamp", slt.until),
            ("key", server_settings.googleMapsKey)))
    response = urlfetch.fetch(url="https://maps.googleapis.com/maps/api/timezone/json?%s" % query)
    azzert(response.status_code == 200, "Failed to call google api")
    data = json.loads(response.content)
    azzert(data["status"] == "OK", "Failed to call google api")
    timezone_name = data["timeZoneId"]
    user_profile = get_user_profile(app_user)
    until = format_datetime(datetime=datetime.fromtimestamp(slt.until), format="full", tzinfo=get_timezone(timezone_name), locale=user_profile.language)
    service_identity = get_service_identity(service_identity_user)
    message = localize(user_profile.language, "notify_service_location_tracking", service=service_identity.name, until=until)
    def trans():
        slt = db.get(slt_key)
        if slt.notified:
            return
        dashboardNotification(app_user, message, False, None)
        slt.notified = True
        slt.put()
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)

def handle_service_tracker_results(app_user, service_identity_user, location):
    slt = get_current_tracker(app_user, service_identity_user)
    if not slt:
        logging.info("Not sending location as the tracker has timed out or was disabled.")
        return
    if not slt.notified:
        # Calculate timezone based on users location
        deferred.defer(notify_location_tracking_enabled, location, service_identity_user, app_user, slt.key())

    user_details = [UserDetailsTO.fromUserProfile(get_user_profile(app_user))]
    service_profile = get_service_profile(get_service_user_from_service_identity_user(service_identity_user))
    location_fix(location_fix_response_receiver, logServiceError, service_profile,
                 service_identity=get_identity_from_service_identity_user(service_identity_user),
                 user_details=user_details, location=location, tracker_key=slt.encrypted_key())

def update_location(app_user, service_identity_user, slt_key):
    from rogerthat.bizz.friends import areFriends
    slt = db.get(slt_key)
    if not slt or not slt.enabled or slt.until < now():
        return
    service_profile_info, human_profile_info = get_profile_infos([service_identity_user, app_user])
    if not areFriends(service_profile_info, human_profile_info):
        return
    request = GetLocationRequestTO()
    request.high_prio = True
    request.friend = service_identity_user.email()
    request.target = GetLocationRequestTO.TARGET_SERVICE_LOCATION_TRACKER
    for capi_call in getLocation(get_location_response_handler, dismissError, app_user, request=request, DO_NOT_SAVE_RPCCALL_OBJECTS=True):
        capi_call.tracker = slt_key
        capi_call.put()

@mapping(u'friend.location_fix.response_receiver')
@returns(NoneType)
@arguments(context=ServiceAPICallback, result=NoneType)
def location_fix_response_receiver(context, result):
    pass

def disable_service_location_tracker(service_user, encrypted_tracker_key):
    tracker = db.get(decrypt(service_user, encrypted_tracker_key))
    tracker.enabled = False
    tracker.put()
    start_service_location_tracking(tracker.service_identity_user, tracker.user, 0, 0)
