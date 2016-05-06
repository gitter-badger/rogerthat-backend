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

from mcfw.properties import bool_property, unicode_property


class ReturnStatusTO(object):
    success = bool_property('1')
    errormsg = unicode_property('2')

    @classmethod
    def create(cls, success=True, errormsg=None):
        r = cls()
        r.success = success
        r.errormsg = unicode(errormsg) if errormsg else None
        return r

RETURNSTATUS_TO_SUCCESS = ReturnStatusTO.create()


class EmailReturnStatusTO(ReturnStatusTO):
    email = unicode_property('3')

    @classmethod
    def create(cls, success=True, errormsg=None, email=None):
        r = super(EmailReturnStatusTO, cls).create(success=success, errormsg=errormsg)
        r.email = email
        return r


class WidgetDescription(object):

    def __init__(self, model_type, to_type, fm_to_type, form_to_type, new_req_to_type, submit_resp_to_type,
                 new_form_call, submit_form_call, form_updated_call, form_updated_req_to_type, to_model_conversion,
                 model_serialize, model_deserialize, to_validate, result_type, xml_type):
        self.widget_type = model_type.TYPE
        self.model_type = model_type
        self.to_type = to_type
        self.fm_to_type = fm_to_type
        self.form_to_type = form_to_type
        self.new_req_to_type = new_req_to_type
        self.submit_resp_to_type = submit_resp_to_type
        self.new_form_call = new_form_call
        self.submit_form_call = submit_form_call
        self.form_updated_call = form_updated_call
        self.form_updated_req_to_type = form_updated_req_to_type
        self.to_model_conversion = to_model_conversion
        self.model_serialize = model_serialize
        self.model_deserialize = model_deserialize
        self.to_validate = to_validate
        self.result_type = result_type
        self.xml_type = xml_type


class WrappedMapping(object):

    def __init__(self, mapping, attr):
        self.mapping = mapping
        self.attr = attr

    def __getitem__(self, key):
        return getattr(self.mapping[key], self.attr)

    def get(self, key, defaultValue=None):
        try:
            return self[key]
        except KeyError:
            return defaultValue

    def iterkeys(self):
        return self.mapping.iterkeys()

    def iteritems(self):
        for k in self.iterkeys():
            yield (k, self[k])

    def itervalues(self):
        for _, v in self.iteritems():
            yield v

    def __str__(self):
        return str("keys: %s" % self.mapping.keys())


class Mapping(object):

    def __init__(self):
        self._stash = None

    def keys(self):
        return self.stash.keys()

    def __getitem__(self, key):
        return self.stash[key]

    def iteritems(self):
        return self.stash.iteritems()

    @property
    def stash(self):
        if self._stash is None:
            self._stash = self._create_stash()
        return self._stash

    def _create_stash(self):
        raise NotImplementedError()

class WidgetMapping(Mapping):
    def _create_stash(self):
        from rogerthat.api.messaging import submitSingleSelectForm, submitTextLineForm, submitTextBlockForm, \
            submitAutoCompleteForm, submitMultiSelectForm, submitDateSelectForm, submitSingleSliderForm, \
            submitRangeSliderForm, submitPhotoUploadForm, submitGPSLocationForm, submitMyDigiPassForm, submitAdvancedOrderForm
        from rogerthat.bizz.messaging import convert_text_line, convert_text_block, convert_auto_complete, \
            convert_single_select, convert_multi_select, convert_date_select, convert_single_slider, convert_range_slider, \
            convert_photo_upload, validate_text_line, validate_text_block, validate_auto_complete, validate_single_select, \
            validate_multi_select, validate_date_select, validate_single_slider, validate_range_slider, validate_photo_upload, \
            convert_gps_location, validate_gps_location, convert_my_digi_pass, validate_my_digi_pass, convert_advanced_order, validate_advanced_order
        from rogerthat.bizz.service.mfd.gen import TextLineWidget, TextBlockWidget, TextAutocompleteWidget, \
            SelectSingleWidget, SelectMultiWidget, SelectDateWidget, SliderWidget, RangeSliderWidget, \
            PhotoUploadWidget, GPSLocationWidget, MyDigiPassWidget, AdvancedOrderWidget
        from rogerthat.capi.messaging import newTextLineForm, newTextBlockForm, newAutoCompleteForm, \
            newSingleSelectForm, newMultiSelectForm, newDateSelectForm, newSingleSliderForm, newRangeSliderForm, \
            newPhotoUploadForm, updateTextLineForm, updateTextBlockForm, updateAutoCompleteForm, updateSingleSelectForm, \
            updateMultiSelectForm, updateDateSelectForm, updateSingleSliderForm, updateRangeSliderForm, updatePhotoUploadForm, \
            newGPSLocationForm, updateGPSLocationForm, newMyDigiPassForm, updateMyDigiPassForm, newAdvancedOrderForm, updateAdvancedOrderForm
        from rogerthat.models.properties.forms import serialize_text_line, deserialize_text_line, TextLine, \
            serialize_text_block, deserialize_text_block, TextBlock, \
            serialize_auto_complete, deserialize_auto_complete, AutoComplete, \
            serialize_single_select, deserialize_single_select, SingleSelect, \
            serialize_multi_select, deserialize_multi_select, MultiSelect, \
            serialize_date_select, deserialize_date_select, DateSelect, \
            serialize_single_slider, deserialize_single_slider, SingleSlider, \
            serialize_range_slider, deserialize_range_slider, RangeSlider, \
            serialize_photo_upload, deserialize_photo_upload, PhotoUpload, \
            serialize_gps_location, deserialize_gps_location, GPSLocation, \
            serialize_my_digi_pass, deserialize_my_digi_pass, MyDigiPass, \
            serialize_advanced_order, deserialize_advanced_order, AdvancedOrder
        from rogerthat.models.properties.forms import WidgetResult
        from rogerthat.to.messaging.forms import TextLineTO, TextLineFormMessageTO, TextLineFormTO, \
            NewTextLineFormRequestTO, SubmitTextLineFormResponseTO, UpdateTextLineFormRequestTO, \
            TextBlockTO, TextBlockFormMessageTO, TextBlockFormTO, \
            NewTextBlockFormRequestTO, SubmitTextBlockFormResponseTO, UpdateTextBlockFormRequestTO, \
            AutoCompleteTO, AutoCompleteFormMessageTO, AutoCompleteFormTO, \
            NewAutoCompleteFormRequestTO, SubmitAutoCompleteFormResponseTO, UpdateAutoCompleteFormRequestTO, \
            SingleSelectTO, SingleSelectFormMessageTO, SingleSelectFormTO, \
            NewSingleSelectFormRequestTO, SubmitSingleSelectFormResponseTO, UpdateSingleSelectFormRequestTO, \
            MultiSelectTO, MultiSelectFormMessageTO, MultiSelectFormTO, \
            NewMultiSelectFormRequestTO, SubmitMultiSelectFormResponseTO, UpdateMultiSelectFormRequestTO, \
            DateSelectTO, DateSelectFormMessageTO, DateSelectFormTO, \
            NewDateSelectFormRequestTO, SubmitDateSelectFormResponseTO, UpdateDateSelectFormRequestTO, \
            SingleSliderTO, SingleSliderFormMessageTO, SingleSliderFormTO, \
            NewSingleSliderFormRequestTO, SubmitSingleSliderFormResponseTO, UpdateSingleSliderFormRequestTO, \
            RangeSliderTO, RangeSliderFormMessageTO, RangeSliderFormTO, \
            NewRangeSliderFormRequestTO, SubmitRangeSliderFormResponseTO, UpdateRangeSliderFormRequestTO, \
            PhotoUploadTO, PhotoUploadFormMessageTO, PhotoUploadFormTO, \
            NewPhotoUploadFormRequestTO, SubmitPhotoUploadFormResponseTO, UpdatePhotoUploadFormRequestTO, \
            GPSLocationTO, GPSLocationFormMessageTO, GPSLocationFormTO, \
            NewGPSLocationFormRequestTO, SubmitGPSLocationFormResponseTO, UpdateGPSLocationFormRequestTO, \
            MyDigiPassTO, MyDigiPassFormTO, MyDigiPassFormMessageTO, \
            NewMyDigiPassFormRequestTO, SubmitMyDigiPassFormResponseTO, UpdateMyDigiPassFormRequestTO, \
            AdvancedOrderTO, AdvancedOrderFormTO, AdvancedOrderFormMessageTO, \
            NewAdvancedOrderFormRequestTO, SubmitAdvancedOrderFormResponseTO, UpdateAdvancedOrderFormRequestTO

        return {
            TextLine.TYPE: \
                WidgetDescription(TextLine, TextLineTO, TextLineFormMessageTO, TextLineFormTO,
                                  NewTextLineFormRequestTO, SubmitTextLineFormResponseTO,
                                  newTextLineForm, submitTextLineForm, updateTextLineForm,
                                  UpdateTextLineFormRequestTO, convert_text_line, serialize_text_line,
                                  deserialize_text_line, validate_text_line, WidgetResult.TYPE_UNICODE,
                                  TextLineWidget),
            TextBlock.TYPE: \
                WidgetDescription(TextBlock, TextBlockTO, TextBlockFormMessageTO, TextBlockFormTO,
                                  NewTextBlockFormRequestTO, SubmitTextBlockFormResponseTO,
                                  newTextBlockForm, submitTextBlockForm, updateTextBlockForm,
                                  UpdateTextBlockFormRequestTO, convert_text_block, serialize_text_block,
                                  deserialize_text_block, validate_text_block, WidgetResult.TYPE_UNICODE,
                                  TextBlockWidget),
            AutoComplete.TYPE: \
                WidgetDescription(AutoComplete, AutoCompleteTO, AutoCompleteFormMessageTO, AutoCompleteFormTO,
                                  NewAutoCompleteFormRequestTO, SubmitAutoCompleteFormResponseTO,
                                  newAutoCompleteForm, submitAutoCompleteForm, updateAutoCompleteForm,
                                  UpdateAutoCompleteFormRequestTO, convert_auto_complete, serialize_auto_complete,
                                  deserialize_auto_complete, validate_auto_complete, WidgetResult.TYPE_UNICODE,
                                  TextAutocompleteWidget),
            SingleSelect.TYPE: \
                WidgetDescription(SingleSelect, SingleSelectTO, SingleSelectFormMessageTO, SingleSelectFormTO,
                                  NewSingleSelectFormRequestTO, SubmitSingleSelectFormResponseTO,
                                  newSingleSelectForm, submitSingleSelectForm, updateSingleSelectForm,
                                  UpdateSingleSelectFormRequestTO, convert_single_select, serialize_single_select,
                                  deserialize_single_select, validate_single_select, WidgetResult.TYPE_UNICODE,
                                  SelectSingleWidget),
            MultiSelect.TYPE: \
                WidgetDescription(MultiSelect, MultiSelectTO, MultiSelectFormMessageTO, MultiSelectFormTO,
                                  NewMultiSelectFormRequestTO, SubmitMultiSelectFormResponseTO,
                                  newMultiSelectForm, submitMultiSelectForm, updateMultiSelectForm,
                                  UpdateMultiSelectFormRequestTO, convert_multi_select, serialize_multi_select,
                                  deserialize_multi_select, validate_multi_select, WidgetResult.TYPE_UNICODE_LIST,
                                  SelectMultiWidget),
            DateSelect.TYPE: \
                WidgetDescription(DateSelect, DateSelectTO, DateSelectFormMessageTO, DateSelectFormTO,
                                  NewDateSelectFormRequestTO, SubmitDateSelectFormResponseTO,
                                  newDateSelectForm, submitDateSelectForm, updateDateSelectForm,
                                  UpdateDateSelectFormRequestTO, convert_date_select, serialize_date_select,
                                  deserialize_date_select, validate_date_select, WidgetResult.TYPE_LONG,
                                  SelectDateWidget),
            SingleSlider.TYPE: \
                WidgetDescription(SingleSlider, SingleSliderTO, SingleSliderFormMessageTO, SingleSliderFormTO,
                                  NewSingleSliderFormRequestTO, SubmitSingleSliderFormResponseTO,
                                  newSingleSliderForm, submitSingleSliderForm, updateSingleSliderForm,
                                  UpdateSingleSliderFormRequestTO, convert_single_slider, serialize_single_slider,
                                  deserialize_single_slider, validate_single_slider, WidgetResult.TYPE_FLOAT,
                                  SliderWidget),
            RangeSlider.TYPE: \
                WidgetDescription(RangeSlider, RangeSliderTO, RangeSliderFormMessageTO, RangeSliderFormTO,
                                  NewRangeSliderFormRequestTO, SubmitRangeSliderFormResponseTO,
                                  newRangeSliderForm, submitRangeSliderForm, updateRangeSliderForm,
                                  UpdateRangeSliderFormRequestTO, convert_range_slider, serialize_range_slider,
                                  deserialize_range_slider, validate_range_slider, WidgetResult.TYPE_FLOAT_LIST,
                                  RangeSliderWidget),
            PhotoUpload.TYPE: \
                WidgetDescription(PhotoUpload, PhotoUploadTO, PhotoUploadFormMessageTO, PhotoUploadFormTO,
                                  NewPhotoUploadFormRequestTO, SubmitPhotoUploadFormResponseTO,
                                  newPhotoUploadForm, submitPhotoUploadForm, updatePhotoUploadForm,
                                  UpdatePhotoUploadFormRequestTO, convert_photo_upload, serialize_photo_upload,
                                  deserialize_photo_upload, validate_photo_upload, WidgetResult.TYPE_UNICODE,
                                  PhotoUploadWidget),
            GPSLocation.TYPE: \
                WidgetDescription(GPSLocation, GPSLocationTO, GPSLocationFormMessageTO, GPSLocationFormTO,
                                  NewGPSLocationFormRequestTO, SubmitGPSLocationFormResponseTO,
                                  newGPSLocationForm, submitGPSLocationForm, updateGPSLocationForm,
                                  UpdateGPSLocationFormRequestTO, convert_gps_location, serialize_gps_location,
                                  deserialize_gps_location, validate_gps_location, WidgetResult.TYPE_LOCATION,
                                  GPSLocationWidget),
            MyDigiPass.TYPE: \
                WidgetDescription(MyDigiPass, MyDigiPassTO, MyDigiPassFormMessageTO, MyDigiPassFormTO,
                                  NewMyDigiPassFormRequestTO, SubmitMyDigiPassFormResponseTO,
                                  newMyDigiPassForm, submitMyDigiPassForm, updateMyDigiPassForm,
                                  UpdateMyDigiPassFormRequestTO, convert_my_digi_pass, serialize_my_digi_pass,
                                  deserialize_my_digi_pass, validate_my_digi_pass, WidgetResult.TYPE_MYDIGIPASS,
                                  MyDigiPassWidget),
            AdvancedOrder.TYPE: \
                WidgetDescription(AdvancedOrder, AdvancedOrderTO, AdvancedOrderFormMessageTO, AdvancedOrderFormTO,
                                  NewAdvancedOrderFormRequestTO, SubmitAdvancedOrderFormResponseTO,
                                  newAdvancedOrderForm, submitAdvancedOrderForm, updateAdvancedOrderForm,
                                  UpdateAdvancedOrderFormRequestTO, convert_advanced_order, serialize_advanced_order,
                                  deserialize_advanced_order, validate_advanced_order, WidgetResult.TYPE_ADVANCED_ORDER,
                                  AdvancedOrderWidget)
        }

class WidgetResultDescription(object):

    def __init__(self, model_type, to_type, to_model_conversion, model_serialize, model_deserialize):
        self.result_type = model_type.TYPE
        self.model_type = model_type
        self.to_type = to_type
        self.to_model_conversion = to_model_conversion
        self.model_serialize = model_serialize
        self.model_deserialize = model_deserialize


class WidgetResultMapping(Mapping):

    def _create_stash(self):
        from rogerthat.bizz.messaging import convert_long_list_widget_result, convert_long_widget_result, \
            convert_unicode_list_widget_result, convert_unicode_widget_result, convert_float_widget_result, \
            convert_float_list_widget_result, convert_location_widget_result, convert_mydigipass_widget_result, \
            convert_advanced_order_widget_result
        from rogerthat.models.properties.forms import WidgetResult, \
            UnicodeWidgetResult, serialize_unicode_widget_result, deserialize_unicode_widget_result, \
            UnicodeListWidgetResult, serialize_unicode_list_widget_result, deserialize_unicode_list_widget_result, \
            LongWidgetResult, serialize_long_widget_result, deserialize_long_widget_result, \
            LongListWidgetResult, serialize_long_list_widget_result, deserialize_long_list_widget_result, \
            FloatWidgetResult, serialize_float_widget_result, deserialize_float_widget_result, \
            FloatListWidgetResult, serialize_float_list_widget_result, deserialize_float_list_widget_result, \
            LocationWidgetResult, serialize_location_widget_result, deserialize_location_widget_result, \
            MyDigiPassWidgetResult, serialize_mydigipass_widget_result, deserialize_mydigipass_widget_result, \
            AdvancedOrderWidgetResult, serialize_advanced_order_widget_result, deserialize_advanced_order_widget_result
        from rogerthat.to.messaging.forms import UnicodeWidgetResultTO, UnicodeListWidgetResultTO, \
            LongWidgetResultTO, LongListWidgetResultTO, FloatWidgetResultTO, FloatListWidgetResultTO, \
            LocationWidgetResultTO, MyDigiPassWidgetResultTO, AdvancedOrderWidgetResultTO

        return {
            WidgetResult.TYPE_UNICODE: \
                WidgetResultDescription(UnicodeWidgetResult, UnicodeWidgetResultTO, convert_unicode_widget_result,
                                        serialize_unicode_widget_result, deserialize_unicode_widget_result),
            WidgetResult.TYPE_UNICODE_LIST: \
                WidgetResultDescription(UnicodeListWidgetResult, UnicodeListWidgetResultTO, convert_unicode_list_widget_result,
                                        serialize_unicode_list_widget_result, deserialize_unicode_list_widget_result),
            WidgetResult.TYPE_LONG: \
                WidgetResultDescription(LongWidgetResult, LongWidgetResultTO, convert_long_widget_result,
                                        serialize_long_widget_result, deserialize_long_widget_result),
            WidgetResult.TYPE_LONG_LIST: \
                WidgetResultDescription(LongListWidgetResult, LongListWidgetResultTO, convert_long_list_widget_result,
                                        serialize_long_list_widget_result, deserialize_long_list_widget_result),
            WidgetResult.TYPE_FLOAT: \
                WidgetResultDescription(FloatWidgetResult, FloatWidgetResultTO, convert_float_widget_result,
                                        serialize_float_widget_result, deserialize_float_widget_result),
            WidgetResult.TYPE_FLOAT_LIST: \
                WidgetResultDescription(FloatListWidgetResult, FloatListWidgetResultTO, convert_float_list_widget_result,
                                        serialize_float_list_widget_result, deserialize_float_list_widget_result),
            WidgetResult.TYPE_LOCATION: \
                WidgetResultDescription(LocationWidgetResult, LocationWidgetResultTO, convert_location_widget_result,
                                        serialize_location_widget_result, deserialize_location_widget_result),
            WidgetResult.TYPE_MYDIGIPASS: \
                WidgetResultDescription(MyDigiPassWidgetResult, MyDigiPassWidgetResultTO, convert_mydigipass_widget_result,
                                        serialize_mydigipass_widget_result, deserialize_mydigipass_widget_result),
            WidgetResult.TYPE_ADVANCED_ORDER: \
                WidgetResultDescription(AdvancedOrderWidgetResult, AdvancedOrderWidgetResultTO, convert_advanced_order_widget_result, \
                                        serialize_advanced_order_widget_result, deserialize_advanced_order_widget_result),
        }

class MessageTypeDescription(object):

    def __init__(self, root_to_type, root_model_to_conversion, to_type, model_to_conversion, include_member_in_conversion):
        self.root_to_type = root_to_type
        self.root_model_to_conversion = root_model_to_conversion
        self.to_type = to_type
        self.model_to_conversion = model_to_conversion
        self.include_member_in_conversion = include_member_in_conversion


class MessageTypeMapping(Mapping):

    def _create_stash(self):
        from rogerthat.models import Message, FormMessage
        from rogerthat.to.messaging import MessageTO, RootMessageTO
        from rogerthat.to.messaging.forms import WebFormMessageTO, RootFormMessageTO
        return {
            Message.TYPE: \
                MessageTypeDescription(RootMessageTO, RootMessageTO.fromMessage, MessageTO, MessageTO.fromMessage, True),
            FormMessage.TYPE: \
                MessageTypeDescription(RootFormMessageTO, RootFormMessageTO.fromFormMessage, WebFormMessageTO, \
                                       WebFormMessageTO.fromMessage, False)
        }


WIDGET_MAPPING = WidgetMapping()
WIDGET_MODEL_MAPPING = WrappedMapping(WIDGET_MAPPING, 'model_type')
WIDGET_TO_MAPPING = WrappedMapping(WIDGET_MAPPING, 'to_type')

WIDGET_RESULT_MAPPING = WidgetResultMapping()
WIDGET_RESULT_MODEL_MAPPING = WrappedMapping(WIDGET_RESULT_MAPPING, 'model_type')
WIDGET_RESULT_TO_MAPPING = WrappedMapping(WIDGET_RESULT_MAPPING, 'to_type')

MESSAGE_TYPE_MAPPING = MessageTypeMapping()
MESSAGE_TYPE_TO_MAPPING = WrappedMapping(MESSAGE_TYPE_MAPPING, 'to_type')
ROOT_MESSAGE_TYPE_TO_MAPPING = WrappedMapping(MESSAGE_TYPE_MAPPING, 'root_to_type')

del WrappedMapping
del Mapping
del WidgetMapping
del WidgetResultMapping
del MessageTypeMapping
