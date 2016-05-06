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

from rogerthat.bizz.service import SERVICE_LOCATION_INDEX
from rogerthat.to.service_map import ServiceMapTO, ServiceLocationTO
from rogerthat.utils import email_to_id
from rogerthat.utils.crypto import sha256_hex
from google.appengine.api import search
from mcfw.restapi import rest
from mcfw.rpc import returns, arguments


@rest("/mobi/rest/service_map/load", "get")
@returns(ServiceMapTO)
@arguments(distance=int, lat=float, lon=float, app_id=unicode, cursor=unicode)
def load_service_locations(distance, lat, lon, app_id=None, cursor=None):

    def get_location_sort_options(lat, lon):
        loc_expr = "distance(location, geopoint(%f, %f))" % (lat, lon)
        sort_expr = search.SortExpression(expression=loc_expr,
                                          direction=search.SortExpression.ASCENDING,
                                          default_value=distance)
        return search.SortOptions(expressions=[sort_expr])

    index = search.Index(name=SERVICE_LOCATION_INDEX)
    query_string = (u"app_ids:%s" % app_id) if app_id else u""
    query = search.Query(query_string=query_string,
                         options=search.QueryOptions(returned_fields=['service', 'name', 'location', 'description'],
                                                     sort_options=get_location_sort_options(lat, lon),
                                                     limit=100,
                                                     cursor=search.Cursor(cursor)))
    search_result = index.search(query)
    result = ServiceMapTO()
    def map_result(service_search_result):
        service = ServiceLocationTO()
        for field in service_search_result.fields:
            if field.name == "service":
                service.id = unicode(email_to_id(field.value))
                service.hash = unicode(sha256_hex(field.value))
                continue
            elif field.name == "name":
                service.name = field.value
                continue
            elif field.name == "location":
                service.lat = field.value.latitude
                service.lon = field.value.longitude
                continue
            elif field.name == "description":
                service.description = field.value
                continue
        return service
    result.services = [map_result(r) for r in search_result.results]
    result.cursor = search_result.cursor.web_safe_string if search_result.cursor else None
    return result
