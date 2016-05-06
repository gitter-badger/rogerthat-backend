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
import logging
from math import radians, cos, sin, asin, sqrt, degrees
import urllib

from google.appengine.api import urlfetch


VERY_FAR = 100000  # Distance larger than any distance on earth

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in km between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
#     km = 6378.1370 * c
    return km

def geo_offset(lat, lng, north, east):
    # Earth’s radius, sphere
    R = 6378137.0

    new_lat = lat + degrees(north / R)
    new_lng = lng + degrees(east / (R * cos(radians(lat))))


    return new_lat, new_lng


class GeoCodeException(Exception):
    pass


class GeoCodeZeroResultsException(GeoCodeException):
    pass


class GeoCodeStatusException(GeoCodeException):
    pass


def geo_code(address):
    # url = 'https://maps.googleapis.com/maps/api/geocode/json'
    url = 'http://rogerthat.net/geo-coder?'  # Reverse proxy to prevent OVER_QUERY_LIMIT of other gae apps running on same box
    address = address.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    params = urllib.urlencode(dict(address=address.encode('utf8'), sensor='false'))
    response = urlfetch.fetch(url + params)
    result = json.loads(response.content)
    status = result['status']
    if status == 'ZERO_RESULTS':
        raise GeoCodeZeroResultsException()
    elif status != 'OK':
        raise GeoCodeStatusException(status)

    return result['results'][0]


def address_to_coordinates(address, postal_code_required=True):
    """
    Converts an address to latitude and longitude coordinates.

    Args:
        address: The address of the location.

    Returns:
        tuple(long, long, unicode, unicode, unicode): latitude, longitude, Google place id, postal code, formatted address.

    """
    result = geo_code(address)
    lat = result['geometry']['location']['lat']
    lon = result['geometry']['location']['lng']
    address_components = result['address_components']
    postal_code = None
    for a in address_components:
        if 'postal_code' in a['types']:
            postal_code = a['short_name']
    if postal_code_required and not postal_code:
        raise GeoCodeException('Could not resolve address to coordinates')
    place_id = result['place_id']
    formatted_address = result['formatted_address']
    return lat, lon, place_id, postal_code, formatted_address


def coordinates_to_address(lat, lon):
    """
    Converts coordinates to a human readable address.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        tuple(unicode,unicode): Address, Google place id
    """
    # Reverse proxy to prevent OVER_QUERY_LIMIT of other gae apps running on same box
    url = "http://rogerthat.net/geo-coder?latlng=%s,%s" % (lat, lon)
    result = urlfetch.fetch(url)
    results = json.loads(result.content)
    if results['status'] == 'ZERO_RESULTS':
        raise GeoCodeZeroResultsException()
    elif results["status"] != "OK":
        raise GeoCodeStatusException(results['status'])

    for r in results['results']:
        address = r.get('formatted_address')
        place_id = r.get('place_id')
        postal_code = None
        for res in r['address_components']:
            if 'postal_code' in res['types']:
                postal_code = res['short_name']
        if address and place_id and postal_code:
            return address, postal_code, place_id

    logging.debug(results)
    raise GeoCodeException('Could not resolve coordinates to address')
