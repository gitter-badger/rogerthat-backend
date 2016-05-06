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

import datetime
import logging
import time
from types import NoneType

from dateutil.relativedelta import relativedelta
from google.appengine.ext import db

from mcfw.cache import cached
from mcfw.rpc import arguments, returns
from rogerthat.dal import parent_key, generator
from rogerthat.models import APIKey, SIKKey, FriendServiceIdentityConnection, ServiceInteractionDef, MFRSIKey, \
    ServiceMenuDef, ServiceIdentity, Broadcast, QRTemplate, ServiceIdentityStatistic, UserProfile, \
    ServiceProfile, FriendServiceIdentityConnectionArchive
from rogerthat.rpc import users, rpc
from rogerthat.rpc.models import ServiceLog, ServiceAPICallback
from rogerthat.utils import now, azzert, get_epoch_from_datetime
from rogerthat.utils.service import create_service_identity_user, get_service_user_from_service_identity_user


@returns([ServiceAPICallback])
@arguments(service_user=users.User)
def get_service_api_callback_records(service_user):
    qry = ServiceAPICallback.gql("WHERE ANCESTOR IS :ancestor")
    qry.bind(ancestor=parent_key(service_user))
    return generator(qry.run())


@returns(db.GqlQuery)
@arguments(service_user=users.User)
def get_service_api_callback_records_query(service_user):
    qry = ServiceAPICallback.gql("WHERE ANCESTOR IS :ancestor")
    qry.bind(ancestor=parent_key(service_user))
    return qry


@returns([APIKey])
@arguments(service_user=users.User)
def get_api_keys(service_user):
    return APIKey.all().filter("user =", service_user).filter("mfr =", False)


@returns(long)
@arguments(service_user=users.User)
def get_api_key_count(service_user):
    return APIKey.all().filter("user =", service_user).filter("mfr =", False).count()


@cached(1, request=True, memcache=True)
@returns(APIKey)
@arguments(service_user=users.User)
def get_mfr_api_key(service_user):
    return APIKey.all().filter("user =", service_user).filter("mfr =", True).get()


@cached(1, request=True, memcache=True)
@returns(APIKey)
@arguments(key=unicode)
def get_api_key(key):
    return APIKey.get_by_key_name(key)


@cached(1, request=True, memcache=True)
@returns(SIKKey)
@arguments(key=unicode)
def get_sik(key):
    return SIKKey.get_by_key_name(key)


@cached(1, request=True, memcache=True, lifetime=0)
@returns(MFRSIKey)
@arguments(service_user=users.User)
def get_mfr_sik(service_user):
    key = service_user.email()
    parent = parent_key(service_user)
    return MFRSIKey.get_by_key_name(key, parent=parent)


@returns(FriendServiceIdentityConnection)
@arguments(friend_user=users.User, service_identity_user=users.User)
def get_friend_serviceidentity_connection(friend_user, service_identity_user):
    return db.get(FriendServiceIdentityConnection.createKey(friend_user, service_identity_user))


@returns(NoneType)
@arguments(service_user=users.User, rpc_id=unicode, type_=int, status=int, function=unicode, request=unicode,
           response=unicode,
           error_code=int, error_message=unicode)
def log_service_activity(service_user, rpc_id, type_, status, function, request, response, error_code=0,
                         error_message=None):
    rpc.rpc_items.append(
        db.put_async(
            ServiceLog(parent=db.Key.from_path(u'ServiceLogParent', rpc_id), user=service_user, type=type_,
                       status=status, function=function, request=request, response=response,
                       timestamp=int(time.time() * 1000), error_code=error_code, error_message=error_message)),
        _log_service_activity_deferred, service_user, rpc_id, type_, status, function, request, response, error_code,
        error_message)


def _log_service_activity_deferred(service_user, rpc_id, type_, status, function, request, response, error_code,
                                   error_message):
    ServiceLog(parent=db.Key.from_path(u'ServiceLogParent', rpc_id), user=service_user, type=type_, status=status,
               function=function, request=request, response=response, timestamp=int(time.time() * 1000),
               error_code=error_code, error_message=error_message).put()


@returns([ServiceLog])
@arguments(service_user=users.User, timestamp=long)
def get_service_log(service_user, timestamp):
    if timestamp == 0:
        timestamp = (now() + 1) * 1000
    qry = ServiceLog.gql("WHERE user = :user AND timestamp < :timestamp ORDER BY timestamp DESC")
    qry.bind(user=service_user, timestamp=timestamp)
    return qry.fetch(100)


@returns(db.GqlQuery)
@arguments(service_identity_user=users.User, app_id=unicode)
def get_friend_service_identity_connections_of_service_identity_query(service_identity_user, app_id=None):
    azzert('/' in service_identity_user.email(), 'no slash in %s' % service_identity_user.email())
    qry_string = "WHERE service_identity_email = :service_identity_email"
    qry_params = dict(service_identity_email=service_identity_user.email())
    if app_id:
        qry_string += " AND app_id = :app_id"
        qry_params['app_id'] = app_id
    qry_string += " ORDER BY friend_name ASC"
    qry = FriendServiceIdentityConnection.gql(qry_string)
    qry.bind(**qry_params)
    return qry


@returns(db.GqlQuery)
@arguments(service_identity_user=users.User)
def get_friend_service_identity_connections_of_service_identity_keys_query(service_identity_user):
    azzert('/' in service_identity_user.email(), 'no slash in %s' % service_identity_user.email())
    qry = db.GqlQuery("SELECT __key__ FROM FriendServiceIdentityConnection " \
                      "WHERE service_identity_email = :service_identity_email ORDER BY friend_name ASC")
    qry.bind(service_identity_email=service_identity_user.email())
    return qry


@returns(db.GqlQuery)
@arguments(service_identity_user=users.User, min_age=(int, long, NoneType), max_age=(int, long, NoneType),
           gender=(NoneType, int), app_id=(NoneType, int), broadcast_type=unicode)
def get_broadcast_audience_of_service_identity_keys_query(service_identity_user, min_age=None, max_age=None,
                                                          gender=None, app_id=None, broadcast_type=None):
    azzert('/' in service_identity_user.email(), 'no slash in %s' % service_identity_user.email())
    qry_string = "SELECT __key__ FROM FriendServiceIdentityConnection " \
                 "WHERE service_identity_email = :service_identity_email"
    qry_params = dict(service_identity_email=service_identity_user.email())
    if min_age is not None:
        if min_age > 130:
            min_age = 130
        # must find users that are born BEFORE today - x years
        # eg. today is 3 jan 2014, min_age is 29; then look for users born before 3 jan 1985 (first day a user can be 29)
        qry_string += " AND birthdate <= :max_birthdate"
        qry_params['max_birthdate'] = get_epoch_from_datetime(datetime.date.today() - relativedelta(years=min_age))
    if max_age is not None:
        if max_age > 130:
            max_age = 130
        # must find users that are born AFTER today + 1 day - (x + 1) years
        # eg. today is 3 jan 2014, max_age is 29; then look for users born after 4 jan 1984 (last day a user can be 29)
        qry_string += " AND birthdate >= :min_birthdate"
        qry_params['min_birthdate'] = get_epoch_from_datetime(
            datetime.date.today() - relativedelta(years=max_age + 1, days=-1))
    if gender is not None and gender != UserProfile.GENDER_MALE_OR_FEMALE:
        qry_string += " AND gender = :gender"
        qry_params['gender'] = gender
    if app_id is not None:
        qry_string += " AND app_id = :app_id"
        qry_params['app_id'] = app_id
    if broadcast_type is not None:
        qry_string += " AND enabled_broadcast_types = :broadcast_type"
        qry_params['broadcast_type'] = broadcast_type
    logging.debug("Broadcast audience query: %s\nparams: %s", qry_string, qry_params)

    qry = db.GqlQuery(qry_string)
    qry.bind(**qry_params)
    return qry


@returns(db.GqlQuery)
@arguments(app_user=users.User)
def get_friend_service_identity_connections_keys_of_app_user_query(app_user):
    app_user_email = app_user.email()
    azzert('/' not in app_user_email, 'no slash expected in %s' % app_user_email)
    qry = db.GqlQuery("SELECT __key__ FROM FriendServiceIdentityConnection WHERE ANCESTOR IS :ancestor")
    qry.bind(ancestor=parent_key(app_user))
    return qry


@returns(db.GqlQuery)
@arguments(app_user=users.User)
def get_friend_service_identity_connections_of_app_user_query(app_user):
    app_user_email = app_user.email()
    azzert('/' not in app_user_email, 'no slash expected in %s' % app_user_email)
    qry = db.GqlQuery("SELECT * FROM FriendServiceIdentityConnection WHERE ANCESTOR IS :ancestor")
    qry.bind(ancestor=parent_key(app_user))
    return qry


@returns(tuple)
@arguments(service_identity_user=users.User, cursor=unicode, count=int, app_id=unicode)
def get_users_connected_to_service_identity(service_identity_user, cursor, count=50, app_id=None):
    qry = get_friend_service_identity_connections_of_service_identity_query(service_identity_user, app_id)
    qry.with_cursor(cursor if cursor else None, None)
    connections = qry.fetch(count)
    return connections, qry.cursor() if len(connections) > 0 else ""


@returns(int)
@arguments(service_identity_user=users.User)
def count_users_connected_to_service_identity(service_identity_user):
    return get_friend_service_identity_connections_of_service_identity_keys_query(service_identity_user).count(1000000)


@returns(db.GqlQuery)
@arguments(service_user=users.User)
def get_all_service_friend_keys_query(service_user):
    """Returns a query that results in all FriendServiceIdentityConnection of a service and all its identities."""
    # service_user can be a service_identity_user
    email = get_service_user_from_service_identity_user(service_user).email() + '/'
    qry = db.GqlQuery(
        "SELECT __key__ FROM FriendServiceIdentityConnection WHERE service_identity_email >= :from_service_identity_email AND service_identity_email < :to_service_identity_email")
    qry.bind(from_service_identity_email=email, to_service_identity_email=email + u"\ufffd")
    return qry


@returns(db.Query)
@arguments(service_user=users.User)
def get_all_archived_service_friend_keys_query(service_user):
    """Returns a query that results in all FriendServiceIdentityConnectionArchive of a service and all its identities.
    """
    email = get_service_user_from_service_identity_user(service_user).email() + '/'
    return FriendServiceIdentityConnectionArchive.all(keys_only=True) \
        .filter('service_identity_email >=', email) \
        .filter('service_identity_email <', email + u"\ufffd")


@returns(db.GqlQuery)
@arguments(service_user=users.User, app_user=users.User)
def get_friend_service_identity_connections_keys_query(service_user, app_user):
    """Returns a query that results in all FriendServiceIdentityConnection between a service and a user."""
    email = service_user.email()
    qry = db.GqlQuery("SELECT __key__ FROM FriendServiceIdentityConnection"
                      "  WHERE ANCESTOR is :ancestor"
                      "  AND service_identity_email >= :from_service_identity_email"
                      "  AND service_identity_email < :to_service_identity_email")
    qry.bind(ancestor=parent_key(app_user),
             from_service_identity_email=email + '/',
             to_service_identity_email=email + u"/\ufffd")
    return qry


@returns(db.GqlQuery)
@arguments(service_identity_user=users.User, app_user=users.User)
def get_one_friend_service_identity_connection_keys_query(service_identity_user, app_user):
    """Returns a query that results in o FriendServiceIdentityConnection between a service identity and a user."""
    service_identity_email = service_identity_user.email()
    qry = db.GqlQuery("SELECT __key__ FROM FriendServiceIdentityConnection"
                      "  WHERE ANCESTOR is :ancestor AND service_identity_email = :service_identity_email")
    qry.bind(ancestor=parent_key(app_user),
             service_identity_email=service_identity_email)
    return qry


@returns(ServiceInteractionDef)
@arguments(service_user=users.User, sid=(int, long))
def get_service_interaction_def(service_user, sid):
    return ServiceInteractionDef.get_by_id(sid, parent_key(service_user))


@returns(dict)
@arguments(service_user=users.User, identifier=unicode, cursor=unicode, include_deleted=bool)
def get_service_interaction_defs(service_user, identifier, cursor, include_deleted=False):
    if identifier is None:
        if include_deleted:
            qry_string = "WHERE ANCESTOR IS :ancestor ORDER BY timestamp DESC"
        else:
            qry_string = "WHERE ANCESTOR IS :ancestor AND deleted = FALSE ORDER BY timestamp DESC"
        qry = ServiceInteractionDef.gql(qry_string)
        qry.bind(ancestor=parent_key(service_user))
    else:
        if include_deleted:
            qry_string = "WHERE ANCESTOR IS :ancestor AND service_identity = :identifier ORDER BY timestamp DESC"
        else:
            qry_string = "WHERE ANCESTOR IS :ancestor AND service_identity = :identifier AND deleted = FALSE ORDER BY timestamp DESC"
        qry = ServiceInteractionDef.gql(qry_string)
        qry.bind(identifier=identifier, ancestor=parent_key(service_user))
    qry.with_cursor(cursor if cursor else None, None)
    defs = qry.fetch(10)
    return {
        "defs": defs,
        "cursor": qry.cursor() if len(defs) > 0 else ""
    }


@returns([ServiceMenuDef])
@arguments(service_identity_user=users.User)
def get_service_menu_items(service_identity_user):
    svc_user = get_service_user_from_service_identity_user(service_identity_user)
    qry = ServiceMenuDef.gql("WHERE ANCESTOR IS :ancestor")
    qry.bind(ancestor=parent_key(svc_user))
    return generator(qry.run())


@returns(ServiceMenuDef)
@arguments(service_identity_user=users.User, coords=[(int, long)])
def get_service_menu_item_by_coordinates(service_identity_user, coords):
    service_user = get_service_user_from_service_identity_user(service_identity_user)
    return ServiceMenuDef.get_by_key_name("x".join((str(x) for x in coords)), parent=parent_key(service_user))


@returns([ServiceMenuDef])
@arguments(service_user=users.User, limit=int)
def get_broadcast_settings_items(service_user, limit):
    # No limit when limit is less than 1
    return ServiceMenuDef.all().ancestor(parent_key(service_user)).filter("isBroadcastSettings =", True).fetch(
        limit if limit > 0 else None)


@returns(bool)
@arguments(service_identity_user=users.User, friend_user=users.User, broadcast_type=unicode)
def is_broadcast_type_enabled(service_identity_user, friend_user, broadcast_type):
    friend_service_identity_connection = get_friend_serviceidentity_connection(friend_user, service_identity_user)
    return not friend_service_identity_connection is None and broadcast_type not in friend_service_identity_connection.disabled_broadcast_types


@cached(1, request=True, lifetime=0)
@returns(ServiceIdentity)
@arguments(service_identity_user=users.User)
def get_service_identity(service_identity_user):
    return get_service_identity_not_cached(service_identity_user)


@returns([ServiceIdentity])
@arguments(service_identity_users=[users.User])
def get_service_identities_not_cached(service_identity_users):
    # XXX: populate cache
    return ServiceIdentity.get(
        [ServiceIdentity.keyFromUser(service_identity_user) for service_identity_user in service_identity_users])


@returns(ServiceIdentity)
@arguments(service_user=users.User)
def get_default_service_identity(service_user):
    return get_service_identity(create_service_identity_user(service_user, ServiceIdentity.DEFAULT))


@returns(ServiceIdentity)
@arguments(service_identity_user=users.User)
def get_service_identity_not_cached(service_identity_user):
    # XXX: populate cache
    return ServiceIdentity.get(ServiceIdentity.keyFromUser(service_identity_user))


@returns(ServiceIdentity)
@arguments(service_user=users.User)
def get_default_service_identity_not_cached(service_user):
    # XXX: populate cache
    return get_service_identity_not_cached(create_service_identity_user(service_user, ServiceIdentity.DEFAULT))


@returns(db.Query)
@arguments(service_user=users.User, keys_only=bool)
def get_service_identities_query(service_user, keys_only=False):
    return ServiceIdentity.all(keys_only=keys_only).ancestor(parent_key(service_user))


@returns([ServiceIdentity])
@arguments(service_user=users.User)
def get_service_identities(service_user):
    qry = get_service_identities_query(service_user)
    return generator(qry)


@returns([ServiceIdentity])
@arguments(service_identity_users=[users.User], app_id=unicode, organization_type=int)
def get_service_identities_by_service_identity_users(service_identity_users, app_id=None,
                                                     organization_type=ServiceProfile.ORGANIZATION_TYPE_UNSPECIFIED):
    # XXX: populate cache
    service_identities = db.get([ServiceIdentity.keyFromUser(u) for u in service_identity_users])
    if app_id is not None:
        service_identities = [si for si in service_identities if app_id in si.appIds]

    if organization_type != ServiceProfile.ORGANIZATION_TYPE_UNSPECIFIED:
        from rogerthat.dal.profile import get_service_profiles
        service_profiles = get_service_profiles([si.service_user for si in service_identities])
        for si, sp in zip(service_identities, service_profiles):
            if sp.organizationType != organization_type:
                service_identities.remove(si)

    return service_identities


@returns([ServiceIdentity])
@arguments(service_user=users.User)
def get_child_identities(service_user):
    return [si for si in get_service_identities(service_user) if not si.is_default]


@returns([Broadcast])
@arguments(service_user=users.User)
def list_broadcasts(service_user):
    return Broadcast.all().ancestor(parent_key(service_user)).fetch(None)


@returns(tuple)
@arguments(service_user=users.User, cursor=unicode)
def get_qr_templates(service_user, cursor):
    qry = QRTemplate.gql("WHERE deleted = False AND ANCESTOR is :1", parent_key(service_user))
    qry.with_cursor(cursor or None)
    templates = qry.fetch(None)
    return templates, qry.cursor() if len(templates) else None


@returns(ServiceIdentityStatistic)
@arguments(service_identity_user=users.User)
def get_identity_statistics(service_identity_user):
    return ServiceIdentityStatistic.get(ServiceIdentityStatistic.create_key(service_identity_user))


@returns([ServiceIdentityStatistic])
@arguments(service_user=users.User)
def get_all_statistics_by_service_user(service_user):
    return generator(ServiceIdentityStatistic.all().ancestor(parent_key(service_user)).run())


@returns(db.GqlQuery)
@arguments()
def get_service_idenities_by_send_email_statistics():
    qry = ServiceIdentity.gql("WHERE emailStatistics = True")
    return qry
