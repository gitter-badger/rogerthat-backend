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

from rogerthat.to import WIDGET_MODEL_MAPPING, WIDGET_MAPPING, WIDGET_RESULT_MODEL_MAPPING, WIDGET_RESULT_MAPPING
from google.appengine.ext import db
from mcfw.consts import MISSING
from mcfw.properties import unicode_property, long_property, typed_property, unicode_list_property, long_list_property, \
    float_property, float_list_property, bool_property
from mcfw.serialization import s_long, s_unicode, ds_long, ds_unicode, get_list_serializer, get_list_deserializer, \
    s_unicode_list, ds_unicode_list, s_long_list, ds_long_list, ds_float, s_float, s_float_list, ds_float_list, s_bool, \
    ds_bool, ds_long_long, s_long_long
from mcfw.utils import Enum


try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

class Widget(object):
    TYPE_TEXT_LINE = u"text_line"
    TYPE_TEXT_BLOCK = u"text_block"
    TYPE_AUTO_COMPLETE = u"auto_complete"
    TYPE_SINGLE_SELECT = u"single_select"
    TYPE_MULTI_SELECT = u"multi_select"
    TYPE_DATE_SELECT = u"date_select"
    TYPE_SINGLE_SLIDER = u"single_slider"
    TYPE_RANGE_SLIDER = u"range_slider"
    TYPE_PHOTO_UPLOAD = u"photo_upload"
    TYPE_GPS_LOCATION = u"gps_location"
    TYPE_MYDIGIPASS = u"mydigipass"
    TYPE_ADVANCED_ORDER = u"advanced_order"

class TextWidget(Widget):
    value = unicode_property('51')
    place_holder = unicode_property('52')
    max_chars = long_property('53')

class TextLine(TextWidget):
    TYPE = Widget.TYPE_TEXT_LINE

class TextBlock(TextWidget):
    TYPE = Widget.TYPE_TEXT_BLOCK

class Choice(object):
    label = unicode_property('1')
    value = unicode_property('2')

    def __init__(self, label=None, value=None):
        self.label = label
        self.value = value

    def __str__(self):
        return "{label: %s, value: %s}" % (self.label, self.value)

    __repr__ = __str__

class AutoComplete(TextWidget):
    TYPE = Widget.TYPE_AUTO_COMPLETE
    suggestions = unicode_list_property('101')

class SelectWidget(Widget):
    choices = typed_property('51', Choice, True)

class SingleSelect(SelectWidget):
    TYPE = Widget.TYPE_SINGLE_SELECT
    value = unicode_property('101', empty_string_is_null=True)

class MultiSelect(SelectWidget):
    TYPE = Widget.TYPE_MULTI_SELECT
    values = unicode_list_property('101')

class DateSelect(Widget):
    TYPE = Widget.TYPE_DATE_SELECT
    MODE_TIME = u"time"
    MODE_DATE = u"date"
    MODE_DATE_TIME = u"date_time"
    MODES = (MODE_TIME, MODE_DATE, MODE_DATE_TIME)
    DEFAULT_MINUTE_INTERVAL = 15
    DEFAULT_UNIT = u"<value/>"
    date = long_property('51')
    max_date = long_property('52')
    min_date = long_property('53')
    has_date = bool_property('54')
    has_min_date = bool_property('55')
    has_max_date = bool_property('56')
    minute_interval = long_property('57')
    mode = unicode_property('58')
    unit = unicode_property('59')

class SliderWidget(Widget):
    min = float_property('51')  # @ReservedAssignment
    max = float_property('52')  # @ReservedAssignment
    step = float_property('53')
    unit = unicode_property('54')
    precision = long_property('55')

class SingleSlider(SliderWidget):
    TYPE = Widget.TYPE_SINGLE_SLIDER
    value = float_property('101')

class RangeSlider(SliderWidget):
    TYPE = Widget.TYPE_RANGE_SLIDER
    low_value = float_property('101')
    high_value = float_property('102')

class PhotoUpload(Widget):
    TYPE = Widget.TYPE_PHOTO_UPLOAD
    QUALITY_BEST = u"best"
    QUALITY_USER = u"user"
    quality = unicode_property('51')
    gallery = bool_property('52')
    camera = bool_property('53')
    ratio = unicode_property('54')

class GPSLocation(Widget):
    TYPE = Widget.TYPE_GPS_LOCATION
    gps = bool_property('51')


class MdpScope(Enum):
    EMAIL = u'email'
    PHONE = u'phone'
    PROFILE = u'profile'
    ADDRESS = u'address'
    EID_ADDRESS = u'eid_address'
    EID_PROFILE = u'eid_profile'
    EID_PHOTO = u'eid_photo'


class MyDigiPass(Widget):
    TYPE = Widget.TYPE_MYDIGIPASS
    scope = unicode_property('51', default=MdpScope.EID_PROFILE)


class AdvancedOrderItem(object):
    id = unicode_property('151')
    name = unicode_property('152')
    description = unicode_property('153', default=None)
    value = long_property('154')
    unit = unicode_property('155')
    unit_price = long_property('156')
    step = long_property('157')
    step_unit = unicode_property('158', default=None)
    step_unit_conversion = long_property('159', default=0)
    image_url = unicode_property('160')
    has_price = bool_property('161', default=True)


class AdvancedOrderCategory(object):
    id = unicode_property('101')
    name = unicode_property('102')
    items = typed_property('103', AdvancedOrderItem, True)


class AdvancedOrder(Widget):
    TYPE = Widget.TYPE_ADVANCED_ORDER
    currency = unicode_property('51')
    leap_time = long_property('52')  # deprecated since of 26 Jan 2016
    categories = typed_property('53', AdvancedOrderCategory, True)

    def auto_complete(self):
        for category in self.categories:
            for item in category.items:
                if item.has_price is not MISSING:
                    return
                item.has_price = getattr(AdvancedOrderItem.has_price, 'default')


def _serialize_choice(stream, c):
    s_long(stream, 1)  # version
    s_unicode(stream, c.label)
    s_unicode(stream, c.value)

def _deserialize_choice(stream):
    c = Choice()
    ds_long(stream)  # version
    c.label = ds_unicode(stream)
    c.value = ds_unicode(stream)
    return c

_serialize_choice_list = get_list_serializer(_serialize_choice)
_deserialize_choice_list = get_list_deserializer(_deserialize_choice)

def _serialize_text_widget(stream, w):
    s_unicode(stream, w.value)
    s_unicode(stream, w.place_holder)
    s_long(stream, w.max_chars)

def _deserialize_text_widget(stream, w):
    w.value = ds_unicode(stream)
    w.place_holder = ds_unicode(stream)
    w.max_chars = ds_long(stream)
    return w

def serialize_text_line(stream, w):
    s_long(stream, 1)  # version
    _serialize_text_widget(stream, w)

def deserialize_text_line(stream):
    ds_long(stream)  # version
    w = _deserialize_text_widget(stream, TextLine())
    return w

def serialize_text_block(stream, w):
    s_long(stream, 1)  # version
    _serialize_text_widget(stream, w)

def deserialize_text_block(stream):
    ds_long(stream)  # version
    w = _deserialize_text_widget(stream, TextBlock())
    return w

def serialize_auto_complete(stream, w):
    s_long(stream, 1)  # version
    _serialize_text_widget(stream, w)
    s_unicode_list(stream, w.suggestions)

def deserialize_auto_complete(stream):
    ds_long(stream)  # version
    w = _deserialize_text_widget(stream, AutoComplete())
    w.suggestions = ds_unicode_list(stream)
    return w


def _serialize_select_widget(stream, w):
    _serialize_choice_list(stream, w.choices)

def _deserialize_select_widget(stream, w):
    w.choices = _deserialize_choice_list(stream)
    return w

def serialize_single_select(stream, w):
    s_long(stream, 1)  # version
    _serialize_select_widget(stream, w)
    s_unicode(stream, w.value)

def deserialize_single_select(stream):
    ds_long(stream)  # version
    w = _deserialize_select_widget(stream, SingleSelect())
    w.value = ds_unicode(stream)
    return w

def serialize_multi_select(stream, w):
    s_long(stream, 1)  # version
    _serialize_select_widget(stream, w)
    s_unicode_list(stream, w.values)

def deserialize_multi_select(stream):
    ds_long(stream)  # version
    w = _deserialize_select_widget(stream, MultiSelect())
    w.values = ds_unicode_list(stream)
    return w


def serialize_date_select(stream, w):
    s_long(stream, 1)  # version
    s_bool(stream, w.has_date)
    s_bool(stream, w.has_max_date)
    s_bool(stream, w.has_min_date)
    s_long(stream, w.date)
    s_long(stream, w.max_date)
    s_long(stream, w.min_date)
    s_long(stream, w.minute_interval)
    s_unicode(stream, w.mode)
    s_unicode(stream, w.unit)

def deserialize_date_select(stream):
    ds_long(stream)  # version
    w = DateSelect()
    w.has_date = ds_bool(stream)
    w.has_max_date = ds_bool(stream)
    w.has_min_date = ds_bool(stream)
    w.date = ds_long(stream)
    w.max_date = ds_long(stream)
    w.min_date = ds_long(stream)
    w.minute_interval = ds_long(stream)
    w.mode = ds_unicode(stream)
    w.unit = ds_unicode(stream)
    return w


def _serialize_slider_widget(stream, w):
    s_float(stream, w.min)
    s_float(stream, w.max)
    s_float(stream, w.step)
    s_unicode(stream, w.unit)
    s_long(stream, w.precision)

def _deserialize_slider_widget(stream, w, version):
    w.min = ds_float(stream)
    w.max = ds_float(stream)
    w.step = ds_float(stream)
    w.unit = ds_unicode(stream)
    if version >= 2:
        w.precision = ds_long(stream)
    return w

def serialize_single_slider(stream, w):
    s_long(stream, 2)  # version
    _serialize_slider_widget(stream, w)
    s_float(stream, w.value)

def deserialize_single_slider(stream):
    version = ds_long(stream)
    w = _deserialize_slider_widget(stream, SingleSlider(), version)
    w.value = ds_float(stream)
    return w

def serialize_range_slider(stream, w):
    s_long(stream, 2)  # version
    _serialize_slider_widget(stream, w)
    s_float(stream, w.low_value)
    s_float(stream, w.high_value)

def deserialize_range_slider(stream):
    version = ds_long(stream)
    w = _deserialize_slider_widget(stream, RangeSlider(), version)
    w.low_value = ds_float(stream)
    w.high_value = ds_float(stream)
    return w

def serialize_photo_upload(stream, w):
    s_long(stream, 3)  # version
    s_unicode(stream, w.quality)
    s_bool(stream, w.gallery)
    s_bool(stream, w.camera)
    s_unicode(stream, w.ratio)

def deserialize_photo_upload(stream):
    version = ds_long(stream)
    w = PhotoUpload()
    w.quality = ds_unicode(stream)
    w.gallery = False if version < 2 else ds_bool(stream)
    w.camera = False if version < 2 else ds_bool(stream)
    w.ratio = None if version < 3 else ds_unicode(stream)
    return w

def serialize_gps_location(stream, w):
    s_long(stream, 1)  # version
    s_bool(stream, w.gps)

def deserialize_gps_location(stream):
    ds_long(stream)
    w = GPSLocation()
    w.gps = ds_bool(stream)
    return w

def serialize_my_digi_pass(stream, w):
    s_long(stream, 2)  # version
    s_unicode(stream, w.scope)

def deserialize_my_digi_pass(stream):
    version = ds_long(stream)
    w = MyDigiPass()
    w.scope = ds_unicode(stream) if version >= 2 else MyDigiPass.scope.default
    return w

def _serialize_advanced_order_item(stream, i):
    s_long(stream, 3)  # version
    s_unicode(stream, i.id)
    s_unicode(stream, i.name)
    s_unicode(stream, i.description)
    s_long(stream, i.value)
    s_unicode(stream, i.unit)
    s_long(stream, i.unit_price)
    s_long(stream, i.step)
    s_unicode(stream, i.step_unit)
    s_long(stream, i.step_unit_conversion)
    s_unicode(stream, i.image_url)
    s_bool(stream, i.has_price)

def _deserialize_advanced_order_item(stream):
    version = ds_long(stream)
    i = AdvancedOrderItem()
    i.id = ds_unicode(stream)
    i.name = ds_unicode(stream)
    i.description = ds_unicode(stream)
    i.value = ds_long(stream)
    i.unit = ds_unicode(stream)
    i.unit_price = ds_long(stream)
    i.step = ds_long(stream)
    i.step_unit = ds_unicode(stream)
    i.step_unit_conversion = ds_long(stream)
    i.image_url = ds_unicode(stream) if version >= 2 else None
    i.has_price = ds_bool(stream) if version >= 3 else True
    return i

_serialize_advanced_order_item_list = get_list_serializer(_serialize_advanced_order_item)
_deserialize_advanced_order_item_list = get_list_deserializer(_deserialize_advanced_order_item)

def _serialize_advanced_order_category(stream, c):
    s_long(stream, 1)  # version
    s_unicode(stream, c.id)
    s_unicode(stream, c.name)
    _serialize_advanced_order_item_list(stream, c.items)

def _deserialize_advanced_order_category(stream):
    c = AdvancedOrderCategory()
    ds_long(stream)  # version
    c.id = ds_unicode(stream)
    c.name = ds_unicode(stream)
    c.items = _deserialize_advanced_order_item_list(stream)
    return c

_serialize_advanced_order_category_list = get_list_serializer(_serialize_advanced_order_category)
_deserialize_advanced_order_category_list = get_list_deserializer(_deserialize_advanced_order_category)

def serialize_advanced_order(stream, w):
    s_long(stream, 1)  # version
    s_unicode(stream, w.currency)
    s_long(stream, w.leap_time)
    _serialize_advanced_order_category_list(stream, w.categories)

def deserialize_advanced_order(stream):
    ds_long(stream)
    w = AdvancedOrder()
    w.currency = ds_unicode(stream)
    w.leap_time = ds_long(stream)
    w.categories = _deserialize_advanced_order_category_list(stream)
    return w

def serialize_advanced_order_widget_result(stream, result):
    s_long(stream, 1)  # version
    s_unicode(stream, result.currency)
    _serialize_advanced_order_category_list(stream, result.categories)

def deserialize_advanced_order_widget_result(stream):
    ds_long(stream)
    w = AdvancedOrderWidgetResult()
    w.currency = ds_unicode(stream)
    w.categories = _deserialize_advanced_order_category_list(stream)
    return w

def serialize_form(stream, f):
    s_long(stream, 2)  # version
    s_unicode(stream, f.type)
    WIDGET_MAPPING[f.type].model_serialize(stream, f.widget)
    s_unicode(stream, f.javascript_validation)

def deserialize_form(stream):
    version = ds_long(stream)  # version
    f = Form()
    f.type = ds_unicode(stream)
    f.widget = WIDGET_MAPPING[f.type].model_deserialize(stream)
    f.javascript_validation = ds_unicode(stream) if version >= 2 else None
    return f


class Form(object):
    POSITIVE = u"positive"
    NEGATIVE = u"negative"
    type = unicode_property('1')  # @ReservedAssignment
    widget = typed_property('2', Widget, False, subtype_attr_name="type", subtype_mapping=WIDGET_MODEL_MAPPING)
    javascript_validation = unicode_property('3')

class FormProperty(db.UnindexedProperty):

    data_type = Form

    def get_value_for_datastore(self, model_instance):
        stream = StringIO.StringIO()
        serialize_form(stream, super(FormProperty, self).get_value_for_datastore(model_instance))
        return db.Blob(stream.getvalue())

    def make_value_from_datastore(self, value):
        if value is None:
            return None
        return deserialize_form(StringIO.StringIO(value))


class WidgetResult(object):
    TYPE_UNICODE = u"unicode_result"
    TYPE_UNICODE_LIST = u"unicode_list_result"
    TYPE_LONG = u"long_result"
    TYPE_LONG_LIST = u"long_list_result"
    TYPE_FLOAT = u"float_result"
    TYPE_FLOAT_LIST = u"float_list_result"
    TYPE_LOCATION = u"location_result"
    TYPE_MYDIGIPASS = u"mydigipass_result"
    TYPE_ADVANCED_ORDER = u"advanced_order_result"

    def get_value(self):
        raise NotImplementedError()

class UnicodeWidgetResult(WidgetResult):
    TYPE = WidgetResult.TYPE_UNICODE
    value = unicode_property('51')

    def get_value(self):
        return self.value

class UnicodeListWidgetResult(WidgetResult):
    TYPE = WidgetResult.TYPE_UNICODE_LIST
    values = unicode_list_property('51')

    def get_value(self):
        return self.values

class LongWidgetResult(WidgetResult):
    TYPE = WidgetResult.TYPE_LONG
    value = long_property('51')

    def get_value(self):
        return self.value

class LongListWidgetResult(WidgetResult):
    TYPE = WidgetResult.TYPE_LONG_LIST
    values = long_list_property('51')

    def get_value(self):
        return self.values

class FloatWidgetResult(WidgetResult):
    TYPE = WidgetResult.TYPE_FLOAT
    value = float_property('51')

    def get_value(self):
        return self.value

class FloatListWidgetResult(WidgetResult):
    TYPE = WidgetResult.TYPE_FLOAT_LIST
    values = float_list_property('51')

    def get_value(self):
        return self.values

class LocationWidgetResult(WidgetResult):
    TYPE = WidgetResult.TYPE_LOCATION
    horizontal_accuracy = float_property('51', default=-1)
    vertical_accuracy = float_property('55', default=-1)
    latitude = float_property('52')
    longitude = float_property('53')
    altitude = float_property('54')
    timestamp = long_property('56', default=0)

    def get_value(self):
        return self


class MyDigiPassEidProfile(object):
    first_name = unicode_property('1')
    first_name_3 = unicode_property('2')
    last_name = unicode_property('3')
    gender = unicode_property('4')
    nationality = unicode_property('5')
    date_of_birth = unicode_property('6')
    location_of_birth = unicode_property('7')
    noble_condition = unicode_property('8')
    issuing_municipality = unicode_property('9')
    card_number = unicode_property('10')
    chip_number = unicode_property('11')
    validity_begins_at = unicode_property('12')
    validity_ends_at = unicode_property('13')
    created_at = unicode_property('14')


class MyDigiPassEidAddress(object):
    street_and_number = unicode_property('1')
    zip_code = unicode_property('2')
    municipality = unicode_property('3')


class MyDigiPassProfile(object):
    updated_at = unicode_property('1')
    first_name = unicode_property('2')
    last_name = unicode_property('3')
    born_on = unicode_property('4')
    preferred_locale = unicode_property('5')
    uuid = unicode_property('6')


class MyDigiPassAddress(object):
    address_1 = unicode_property('1')
    address_2 = unicode_property('2')
    city = unicode_property('3')
    zip = unicode_property('4')
    country = unicode_property('5')
    state = unicode_property('6')


class MyDigiPassWidgetResult(WidgetResult):
    TYPE = WidgetResult.TYPE_MYDIGIPASS
    eid_profile = typed_property('50', MyDigiPassEidProfile, default=None)
    eid_address = typed_property('51', MyDigiPassEidAddress, default=None)
    eid_photo = unicode_property('52', default=None)
    email = unicode_property('53', default=None)
    phone = unicode_property('54', default=None)
    profile = typed_property('55', MyDigiPassProfile, default=None)
    address = typed_property('56', MyDigiPassAddress, default=None)

    def get_value(self):
        return self

class AdvancedOrderWidgetResult(WidgetResult):
    TYPE = WidgetResult.TYPE_ADVANCED_ORDER
    currency = unicode_property('50')
    categories = typed_property('51', AdvancedOrderCategory, True)

    def get_value(self):
        return self

    def auto_complete(self):
        # For backwards compatibility
        for category in self.categories:
            for item in category.items:
                if item.has_price is not MISSING:
                    return
                item.has_price = getattr(AdvancedOrderItem.has_price, 'default')


def serialize_unicode_widget_result(stream, result):
    s_long(stream, 1)  # version
    s_unicode(stream, result.value)

def deserialize_unicode_widget_result(stream):
    ds_long(stream)  # version
    result = UnicodeWidgetResult()
    result.value = ds_unicode(stream)
    return result

def serialize_unicode_list_widget_result(stream, result):
    s_long(stream, 1)  # version
    s_unicode_list(stream, result.values)

def deserialize_unicode_list_widget_result(stream):
    ds_long(stream)  # version
    result = UnicodeListWidgetResult()
    result.values = ds_unicode_list(stream)
    return result


def serialize_long_widget_result(stream, result):
    s_long(stream, 2)  # version
    s_long_long(stream, result.value)

def deserialize_long_widget_result(stream):
    version = ds_long(stream)
    result = LongWidgetResult()
    result.value = ds_long(stream) if version < 2 else ds_long_long(stream)
    return result


def serialize_long_list_widget_result(stream, result):
    s_long(stream, 1)  # version
    s_long_list(stream, result.values)

def deserialize_long_list_widget_result(stream):
    ds_long(stream)  # version
    result = LongListWidgetResult()
    result.values = ds_long_list(stream)
    return result


def serialize_float_widget_result(stream, result):
    s_long(stream, 1)  # version
    s_float(stream, result.value)

def deserialize_float_widget_result(stream):
    ds_long(stream)  # version
    result = FloatWidgetResult()
    result.value = ds_float(stream)
    return result


def serialize_float_list_widget_result(stream, result):
    s_long(stream, 1)  # version
    s_float_list(stream, result.values)

def deserialize_float_list_widget_result(stream):
    ds_long(stream)  # version
    result = FloatListWidgetResult()
    result.values = ds_float_list(stream)
    return result


def serialize_location_widget_result(stream, result):
    s_long(stream, 2)  # version
    s_float(stream, result.horizontal_accuracy)
    s_float(stream, result.latitude)
    s_float(stream, result.longitude)
    s_float(stream, result.altitude)
    s_long(stream, result.timestamp)
    s_float(stream, result.vertical_accuracy)

def deserialize_location_widget_result(stream):
    version = ds_long(stream)
    result = LocationWidgetResult()
    result.horizontal_accuracy = ds_float(stream)
    result.latitude = ds_float(stream)
    result.longitude = ds_float(stream)
    result.altitude = ds_float(stream)
    result.timestamp = 0 if version < 2 else ds_long(stream)
    result.vertical_accuracy = -1 if version < 2 else ds_float(stream)
    return result


def serialize_mydigipass_eid_profile(stream, eid_profile):
    s_unicode(stream, eid_profile.first_name)
    s_unicode(stream, eid_profile.first_name_3)
    s_unicode(stream, eid_profile.last_name)
    s_unicode(stream, eid_profile.gender)
    s_unicode(stream, eid_profile.nationality)
    s_unicode(stream, eid_profile.date_of_birth)
    s_unicode(stream, eid_profile.location_of_birth)
    s_unicode(stream, eid_profile.noble_condition)
    s_unicode(stream, eid_profile.issuing_municipality)
    s_unicode(stream, eid_profile.card_number)
    s_unicode(stream, eid_profile.chip_number)
    s_unicode(stream, eid_profile.validity_begins_at)
    s_unicode(stream, eid_profile.validity_ends_at)
    s_unicode(stream, eid_profile.created_at)

def deserialize_mydigipass_eid_profile(stream, version):
    eid_profile = MyDigiPassEidProfile()
    eid_profile.first_name = ds_unicode(stream)
    eid_profile.first_name_3 = ds_unicode(stream)
    eid_profile.last_name = ds_unicode(stream)
    eid_profile.gender = ds_unicode(stream)
    eid_profile.nationality = ds_unicode(stream)
    eid_profile.date_of_birth = ds_unicode(stream)
    eid_profile.location_of_birth = ds_unicode(stream)
    eid_profile.noble_condition = ds_unicode(stream)
    eid_profile.issuing_municipality = ds_unicode(stream)
    eid_profile.card_number = ds_unicode(stream)
    eid_profile.chip_number = ds_unicode(stream)
    eid_profile.validity_begins_at = ds_unicode(stream)
    eid_profile.validity_ends_at = ds_unicode(stream)
    eid_profile.created_at = ds_unicode(stream)
    return eid_profile


def serialize_mydigipass_eid_address(stream, eid_address):
    s_unicode(stream, eid_address.street_and_number)
    s_unicode(stream, eid_address.zip_code)
    s_unicode(stream, eid_address.municipality)


def deserialize_mydigipass_eid_address(stream, version):
    eid_address = MyDigiPassEidAddress()
    eid_address.street_and_number = ds_unicode(stream)
    eid_address.zip_code = ds_unicode(stream)
    eid_address.municipality = ds_unicode(stream)


def serialize_mydigipass_profile(stream, profile):
    s_unicode(stream, profile.updated_at)
    s_unicode(stream, profile.first_name)
    s_unicode(stream, profile.last_name)
    s_unicode(stream, profile.born_on)
    s_unicode(stream, profile.preferred_locale)
    s_unicode(stream, profile.uuid)

def deserialize_mydigipass_profile(stream, version):
    profile = MyDigiPassProfile()
    profile.updated_at = ds_unicode(stream)
    profile.first_name = ds_unicode(stream)
    profile.last_name = ds_unicode(stream)
    profile.born_on = ds_unicode(stream)
    profile.preferred_locale = ds_unicode(stream)
    profile.uuid = ds_unicode(stream)
    return profile


def serialize_mydigipass_address(stream, address):
    s_unicode(stream, address.address_1)
    s_unicode(stream, address.address_2)
    s_unicode(stream, address.zip)
    s_unicode(stream, address.city)
    s_unicode(stream, address.state)
    s_unicode(stream, address.country)

def deserialize_mydigipass_address(stream, version):
    address = MyDigiPassAddress()
    address.address_1 = ds_unicode(stream)
    address.address_2 = ds_unicode(stream)
    address.zip = ds_unicode(stream)
    address.city = ds_unicode(stream)
    address.state = ds_unicode(stream)
    address.country = ds_unicode(stream)
    return address


def serialize_mydigipass_widget_result(stream, result):
    s_long(stream, 2)  # version
    if result.eid_profile is None:
        s_bool(stream, False)
    else:
        s_bool(stream, True)
        serialize_mydigipass_eid_profile(stream, result.eid_profile)

    if result.eid_address is None:
        s_bool(stream, False)
    else:
        s_bool(stream, True)
        serialize_mydigipass_eid_address(stream, result.eid_address)

    s_unicode(stream, result.eid_photo)
    s_unicode(stream, result.email)
    s_unicode(stream, result.phone)

    if result.profile is None:
        s_bool(stream, False)
    else:
        s_bool(stream, True)
        serialize_mydigipass_profile(stream, result.profile)

    if result.address is None:
        s_bool(stream, False)
    else:
        s_bool(stream, True)
        serialize_mydigipass_address(stream, result.address)

def deserialize_mydigipass_widget_result(stream):
    version = ds_long(stream)  # version
    result = MyDigiPassWidgetResult()

    if version == 1 or ds_bool(stream):
        result.eid_profile = deserialize_mydigipass_eid_profile(stream, version)
    else:
        result.eid_profile = None

    if version > 1 and ds_bool(stream):
        result.eid_address = deserialize_mydigipass_eid_address(stream, version)
    else:
        result.eid_address = None

    if version > 1:
        result.eid_photo = ds_unicode(stream)
        result.email = ds_unicode(stream)
        result.phone = ds_unicode(stream)
    else:
        result.eid_photo = None
        result.email = None
        result.phone = None

    if version > 1 and ds_bool(stream):
        result.profile = deserialize_mydigipass_profile(stream, version)
    else:
        result.profile = None

    if version > 1 and ds_bool(stream):
        result.address = deserialize_mydigipass_address(stream, version)
    else:
        result.address = None

    return result

def serialize_form_result(stream, fr):
    s_long(stream, 1)  # version
    if fr:
        s_unicode(stream, fr.type)
        WIDGET_RESULT_MAPPING[fr.type].model_serialize(stream, fr.result)
    else:
        s_unicode(stream, "")

def deserialize_form_result(stream):
    ds_long(stream)  # version
    type = ds_unicode(stream)  # @ReservedAssignment
    if not type:
        return None
    fr = FormResult()
    fr.type = type
    fr.result = WIDGET_RESULT_MAPPING[fr.type].model_deserialize(stream)
    return fr


class FormResult(object):
    type = unicode_property('1')  # @ReservedAssignment
    result = typed_property('2', WidgetResult, False, subtype_attr_name="type", subtype_mapping=WIDGET_RESULT_MODEL_MAPPING)

class FormResultProperty(db.UnindexedProperty):

    data_type = FormResult

    def get_value_for_datastore(self, model_instance):
        stream = StringIO.StringIO()
        serialize_form_result(stream, super(FormResultProperty, self).get_value_for_datastore(model_instance))
        return db.Blob(stream.getvalue())

    def make_value_from_datastore(self, value):
        if value is None:
            return None
        return deserialize_form_result(StringIO.StringIO(value))
