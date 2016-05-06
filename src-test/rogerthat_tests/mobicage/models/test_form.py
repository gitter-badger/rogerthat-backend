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

import time
import uuid

from rogerthat.bizz.messaging import InvalidWidgetValueException, ValueTooLongException, NoChoicesSpecifiedException, \
    DuplicateChoiceValueException, DuplicateChoiceLabelException, ValueNotInChoicesException, DuplicateValueException, \
    InvalidBoundariesException, InvalidRangeException, ValueNotWithinBoundariesException, MultipleChoicesNeededException, \
    InvalidUnitException, SuggestionTooLongException, InvalidDateSelectMinuteIntervalException, \
    InvalidDateSelectModeException, MinuteIntervalNotEvenlyDividedInto60Exception, InvalidStepValue, \
    DateSelectValuesShouldBeMultiplesOfMinuteInterval, InvalidValueInDateSelectWithModeDate, \
    InvalidValueInDateSelectWithModeTime
from rogerthat.models import FormMessage
from rogerthat.models.properties.forms import Widget, Form, AutoComplete, Choice, RangeSlider, TextLine, TextBlock, \
    SingleSelect, MultiSelect, SingleSlider, FormResult, UnicodeWidgetResult, UnicodeListWidgetResult, FloatWidgetResult, \
    FloatListWidgetResult, DateSelect, PhotoUpload
from rogerthat.models.properties.messaging import Button, Buttons, MemberStatuses, MemberStatus, Attachments
from rogerthat.rpc import users
from rogerthat.to import WIDGET_MAPPING
from rogerthat.to.messaging.forms import FormMessageTO, RangeSliderTO, SingleSliderTO, MultiSelectTO, ChoiceTO, \
    SingleSelectTO, AutoCompleteTO, TextLineTO, TextBlockTO, DateSelectTO
from rogerthat.utils import now
from google.appengine.ext import db
import mc_unittest
from mcfw.consts import MISSING


class TestForms(mc_unittest.TestCase):

    def _getBaseFormMessage(self, msg):
        pos_btn = Button()
        pos_btn.action = None
        pos_btn.caption = u"Submit"
        pos_btn.id = u"positive"
        pos_btn.index = 0
        pos_btn.ui_flags = 0

        neg_btn = Button()
        neg_btn.action = None
        neg_btn.caption = u"Cancel"
        neg_btn.id = u"negative"
        neg_btn.index = 1
        neg_btn.ui_flags = 0

        buttons = Buttons()
        buttons.add(pos_btn)
        buttons.add(neg_btn)

        ms = MemberStatus()
        ms.acked_timestamp = 0
        ms.button_index = -1
        ms.custom_reply = None
        ms.dismissed = False
        ms.form_result = None
        ms.index = 0
        ms.received_timestamp = now()
        ms.status = MemberStatus.STATUS_RECEIVED
        ms.ack_device = None

        memberStatuses = MemberStatuses()
        memberStatuses.add(ms)

        m = FormMessage()
        m.sender = users.User(email=u"sender@rogerth.at")
        m.members = [users.User(email=u"member1@rogerth.at")]
        m.flags = 31
        m.alert_flags = 2
        m.branding = None
        m.message = msg
        m.buttons = buttons
        m.memberStatusses = memberStatuses
        m.creationTimestamp = now()
        m.generation = 1
        m.tag = u"tag 123"
        m.timestamp = now()

        m.attachments = Attachments()

        return m


    def _getTextLineForm(self):
        widget = TextLine()
        widget.max_chars = 100
        widget.place_holder = u"Car Brand"
        widget.value = u"Skoda"

        form = Form()
        form.type = Widget.TYPE_TEXT_LINE
        form.widget = widget
        form.javascript_validation = u"function run(result){return true;}"

        m = self._getBaseFormMessage(u"Enter the brand of your car")
        m.form = form
        return m, form, widget


    def testTextLineForm(self):
        m, form, widget = self._getTextLineForm()
        db.put(m)

        m2 = db.get(m.key())
        self.assert_(m2)
        self.assertEquals(m2.form.type, form.type)
        self.assertEquals(m2.form.widget.value, widget.value)


    def _getTextBlockForm(self):
        widget = TextBlock()
        widget.max_chars = 400
        widget.place_holder = u"Comments"
        widget.value = u"Comments Comments Comments Comments Comments Comments"

        form = Form()
        form.type = Widget.TYPE_TEXT_BLOCK
        form.widget = widget
        form.javascript_validation = u"function run(result){return true;}"

        m = self._getBaseFormMessage(u"Please enter comments about your order")
        m.form = form
        return m, form, widget


    def testTextBlockForm(self):
        m, form, widget = self._getTextBlockForm()
        db.put(m)

        m2 = db.get(m.key())
        self.assert_(m2)
        self.assertEquals(m2.form.type, form.type)
        self.assertEquals(m2.form.widget.value, widget.value)


    def _getAutoCompleteForm(self):
        widget = AutoComplete()
        widget.suggestions = [u"Audi", u"Seat", u"Skoda", u"Volkswagen"]
        widget.max_chars = 100
        widget.place_holder = u"Car Brand"
        widget.value = u"Skoda"

        form = Form()
        form.type = Widget.TYPE_AUTO_COMPLETE
        form.widget = widget
        form.javascript_validation = u"function run(result){return true;}"

        m = self._getBaseFormMessage(u"Enter the brand of your car")
        m.form = form
        return m, form, widget


    def testAutoCompleteForm(self):
        m, form, widget = self._getAutoCompleteForm()
        db.put(m)

        m2 = db.get(m.key())
        self.assert_(m2)
        self.assertEquals(m2.form.type, form.type)
        self.assertEquals(m2.form.widget.value, widget.value)
        self.assert_(m2.form.widget.suggestions)


    def _getSingleSelectForm(self):
        widget = SingleSelect()
        widget.choices = list()
        widget.choices.append(Choice(label=u"Audi", value=u"4"))
        widget.choices.append(Choice(label=u"Seat", value=u"1"))
        widget.choices.append(Choice(label=u"Skoda", value=u"2"))
        widget.choices.append(Choice(label=u"Volkswagen", value=u"3"))
        widget.value = u"2"

        form = Form()
        form.type = Widget.TYPE_SINGLE_SELECT
        form.widget = widget
        form.javascript_validation = u"function run(result){return true;}"

        m = self._getBaseFormMessage(u"Select the brand of your car")
        m.form = form
        return m, form, widget


    def testSingleSelectForm(self):
        m, form, widget = self._getSingleSelectForm()
        db.put(m)

        m2 = db.get(m.key())
        self.assert_(m2)
        self.assertEquals(m2.form.type, form.type)
        self.assertEquals(m2.form.widget.value, widget.value)
        self.assert_(m2.form.widget.choices)


    def _getMultiSelectForm(self):
        widget = MultiSelect()
        widget.choices = list()
        widget.choices.append(Choice(label=u"Beetle", value=u"3"))
        widget.choices.append(Choice(label=u"Golf", value=u"1"))
        widget.choices.append(Choice(label=u"Jetta", value=u"6"))
        widget.choices.append(Choice(label=u"Passat", value=u"2"))
        widget.choices.append(Choice(label=u"Polo", value=u"4"))
        widget.choices.append(Choice(label=u"Scirocco", value=u"5"))
        widget.values = [u"3", u"6"]

        form = Form()
        form.type = Widget.TYPE_MULTI_SELECT
        form.widget = widget
        form.javascript_validation = u"function run(result){return true;}"

        m = self._getBaseFormMessage(u"Select your favorite Volkswagen cars")
        m.form = form
        return m, form, widget


    def testMultiSelectForm(self):
        m, form, widget = self._getMultiSelectForm()
        db.put(m)

        m2 = db.get(m.key())
        self.assert_(m2)
        self.assertEquals(m2.form.type, form.type)
        self.assertEquals(m2.form.widget.values, widget.values)
        self.assert_(m2.form.widget.choices)


    def _getDateSelectForm(self):
        widget = DateSelect()
        widget.minute_interval = 15
        now = int(time.time())
        widget.date = now - now % (60 * widget.minute_interval)
        widget.has_date = True
        widget.has_max_date = True
        widget.has_min_date = True
        widget.min_date = 0
        widget.max_date = widget.date + 86400 * 7
        widget.mode = DateSelect.MODE_DATE_TIME
        widget.unit = u"<value/>"

        form = Form()
        form.type = Widget.TYPE_DATE_SELECT
        form.widget = widget
        form.javascript_validation = u"function run(result){return true;}"

        m = self._getBaseFormMessage(u"Select a date")
        m.form = form

        return m, form, widget


    def testDateSelectForm(self):
        m, form, widget = self._getDateSelectForm()
        db.put(m)

        m2 = db.get(m.key())
        self.assert_(m2)
        self.assertEquals(m2.form.type, form.type)
        self.assertEquals(m2.form.widget.unit, widget.unit)
        self.assertEquals(m2.form.widget.mode, widget.mode)
        self.assertEquals(m2.form.widget.max_date, widget.max_date)
        self.assertEquals(m2.form.widget.min_date, widget.min_date)
        self.assertEquals(m2.form.widget.date, widget.date)


    def _getSingleSliderForm(self):
        widget = SingleSlider()
        widget.max = 100
        widget.min = 0
        widget.precision = 2
        widget.step = 2
        widget.unit = u"<value/> EUR"
        widget.value = 70

        form = Form()
        form.type = Widget.TYPE_SINGLE_SLIDER
        form.widget = widget
        form.javascript_validation = u"function run(result){return true;}"

        m = self._getBaseFormMessage(u"Enter price")
        m.form = form
        return m, form, widget


    def testSingleSliderForm(self):
        m, form, widget = self._getSingleSliderForm()
        db.put(m)

        m2 = db.get(m.key())
        self.assert_(m2)
        self.assertEquals(m2.form.type, form.type)
        self.assertEquals(m2.form.widget.value, widget.value)


    def _getRangeSliderForm(self):
        widget = RangeSlider()
        widget.high_value = 90
        widget.low_value = 70
        widget.max = 100
        widget.min = 0
        widget.precision = 2
        widget.step = 2
        widget.unit = u"<low_value/> - <high_value/> EUR"

        form = Form()
        form.type = Widget.TYPE_RANGE_SLIDER
        form.widget = widget
        form.javascript_validation = u"function run(result){return true;}"

        m = self._getBaseFormMessage(u"Enter price range")
        m.form = form
        return m, form, widget


    def testRangeSliderForm(self):
        m, form, widget = self._getRangeSliderForm()
        db.put(m)

        m2 = db.get(m.key())
        self.assert_(m2)
        self.assertEquals(m2.form.type, form.type)
        self.assertEquals(m2.form.widget.high_value, widget.high_value)
        self.assertEquals(m2.form.widget.low_value, widget.low_value)


    def _getPhotoUploadForm(self):
        widget = PhotoUpload()
        widget.quality = PhotoUpload.QUALITY_BEST
        widget.gallery = True
        widget.camera = True
        widget.ratio = u"200x200"

        form = Form()
        form.type = Widget.TYPE_PHOTO_UPLOAD
        form.widget = widget
        form.javascript_validation = None

        m = self._getBaseFormMessage(u"Upload a photo")
        m.form = form

        return m, form, widget


    def testPhotoUploadFrom(self):
        m, form, widget = self._getPhotoUploadForm()
        db.put(m)

        m2 = db.get(m.key())
        self.assert_(m2)
        self.assertEquals(m2.form.type, form.type)
        self.assertEquals(m2.form.widget.quality, widget.quality)
        self.assertEquals(m2.form.widget.gallery, widget.gallery)
        self.assertEquals(m2.form.widget.camera, widget.camera)
        self.assertEquals(m2.form.widget.ratio, widget.ratio)


    def _getBaseFormMessageTO(self, msg):
        fmTO = FormMessageTO()
        fmTO.alert_flags = 2
        fmTO.branding = None
        fmTO.flags = 31
        fmTO.key = unicode(uuid.uuid4())
        fmTO.message = msg
        fmTO.parent_key = None
        fmTO.sender = users.get_current_user().email()
        fmTO.threadTimestamp = 0
        fmTO.timestamp = 0
        return fmTO


    def testTextLineTO(self):
        fm, form, widget = self._getTextLineForm()
        db.put(fm)
        fmTO = FormMessageTO.fromFormMessage(fm)
        self.assertEqual(fmTO.form.type, form.type)
        self.assertEqual(fmTO.form.widget.value, widget.value)

    def testValidateTextLineTO(self):
        _, _, widget = self._getTextLineForm()
        validate = WIDGET_MAPPING[widget.TYPE].to_validate
        validate(TextLineTO.fromWidget(widget))

        # max_chars >= 0
        w = TextLineTO.fromWidget(widget)
        w.max_chars = -2
        self.assertRaises(InvalidWidgetValueException, validate, w)
        w.max_chars = 0
        self.assertRaises(InvalidWidgetValueException, validate, w)

        # len(value) <= max_chars
        w = TextLineTO.fromWidget(widget)
        w.value = u"x" * (w.max_chars + 1)
        self.assertRaises(ValueTooLongException, validate, w)
        w.value = u"x" * w.max_chars
        validate(w)


    def testTextBlockTO(self):
        fm, form, widget = self._getTextBlockForm()
        db.put(fm)
        fmTO = FormMessageTO.fromFormMessage(fm)
        self.assertEqual(fmTO.form.type, form.type)
        self.assertEqual(fmTO.form.widget.value, widget.value)

    def testValidateTextBlockTO(self):
        _, _, widget = self._getTextBlockForm()
        validate = WIDGET_MAPPING[widget.TYPE].to_validate
        validate(TextBlockTO.fromWidget(widget))

        # max_chars >= 0
        w = TextBlockTO.fromWidget(widget)
        w.max_chars = -2
        self.assertRaises(InvalidWidgetValueException, validate, w)
        w.max_chars = 0
        self.assertRaises(InvalidWidgetValueException, validate, w)

        # len(value) <= max_chars
        w = TextBlockTO.fromWidget(widget)
        w.value = u"x" * (w.max_chars + 1)
        self.assertRaises(ValueTooLongException, validate, w)
        w.value = u"x" * w.max_chars
        validate(w)


    def testAutoCompleteTO(self):
        fm, form, widget = self._getAutoCompleteForm()
        db.put(fm)
        fmTO = FormMessageTO.fromFormMessage(fm)
        self.assertEqual(fmTO.form.type, form.type)
        self.assertEqual(fmTO.form.widget.value, widget.value)
        self.assertEqual(fmTO.form.widget.choices, widget.suggestions)  # phones: choices, API: suggestions

    def testValidateAutoCompleteTO(self):
        _, _, widget = self._getAutoCompleteForm()
        validate = WIDGET_MAPPING[widget.TYPE].to_validate
        validate(AutoCompleteTO.fromWidget(widget))

        # has suggestions
        w = AutoCompleteTO.fromWidget(widget)
        w.suggestions = list()
        validate(w)

        # no duplicate suggestions values
        w = AutoCompleteTO.fromWidget(widget)
        w.suggestions = [u"x", u"x"]
        self.assertRaises(DuplicateChoiceValueException, validate, w)

        # max_chars >= 0
        w = AutoCompleteTO.fromWidget(widget)
        w.max_chars = -2
        self.assertRaises(InvalidWidgetValueException, validate, w)
        w.max_chars = 0
        self.assertRaises(InvalidWidgetValueException, validate, w)

        # len(value) <= max_chars
        w = AutoCompleteTO.fromWidget(widget)
        w.value = u"x" * (w.max_chars + 1)
        self.assertRaises(ValueTooLongException, validate, w)
        w.value = u"x" * w.max_chars
        validate(w)
        w.value = u"x" * (w.max_chars - 1)
        validate(w)

        # len(suggestions[x]) <= max_chars
        w = AutoCompleteTO.fromWidget(widget)
        w.suggestions = [u"x" * (w.max_chars + 1)]
        self.assertRaises(SuggestionTooLongException, validate, w)
        w.suggestions = [u"1", u"12", u"123", u"x" * (w.max_chars * 2)]
        self.assertRaises(SuggestionTooLongException, validate, w)
        w.suggestions = [u"x" * w.max_chars]
        validate(w)
        w.suggestions = [u"x" * (w.max_chars - 1)]
        validate(w)
        w.max_chars -= 2
        self.assertRaises(SuggestionTooLongException, validate, w)


    def testSingleSelectTO(self):
        fm, form, widget = self._getSingleSelectForm()
        db.put(fm)
        fmTO = FormMessageTO.fromFormMessage(fm)
        self.assertEqual(fmTO.form.type, form.type)
        self.assertEqual(fmTO.form.widget.value, widget.value)

    def testValidateSingleSelectTO(self):
        _, _, widget = self._getSingleSelectForm()
        validate = WIDGET_MAPPING[widget.TYPE].to_validate
        validate(SingleSelectTO.fromWidget(widget))

        # has choices
        w = SingleSelectTO.fromWidget(widget)
        w.choices = list()
        self.assertRaises(MultipleChoicesNeededException, validate, w)
        w.choices = [ChoiceTO(u"x", u"x")]
        self.assertRaises(MultipleChoicesNeededException, validate, w)

        # no duplicate labels in choices
        w = SingleSelectTO.fromWidget(widget)
        w.choices = [ChoiceTO(u"label", x) for x in [u"a", u"b"]]
        self.assertRaises(DuplicateChoiceLabelException, validate, w)

        # no duplicate values in choices
        w = SingleSelectTO.fromWidget(widget)
        w.choices = [ChoiceTO(x, u"value") for x in [u"a", u"b"]]
        self.assertRaises(DuplicateChoiceValueException, validate, w)

        # value in choices
        w = SingleSelectTO.fromWidget(widget)
        w.value = u"not in choices"
        self.assertRaises(ValueNotInChoicesException, validate, w)
        w.value = w.choices[0].value
        validate(w)


    def testMultiSelectTO(self):
        fm, form, widget = self._getMultiSelectForm()
        db.put(fm)
        fmTO = FormMessageTO.fromFormMessage(fm)
        self.assertEqual(fmTO.form.type, form.type)
        self.assertEqual(fmTO.form.widget.values, widget.values)

    def testValidateMultiSelectTO(self):
        _, _, widget = self._getMultiSelectForm()
        validate = WIDGET_MAPPING[widget.TYPE].to_validate
        validate(MultiSelectTO.fromWidget(widget))

        # has choices
        w = MultiSelectTO.fromWidget(widget)
        w.choices = list()
        self.assertRaises(NoChoicesSpecifiedException, validate, w)

        # no duplicate labels in choices
        w = MultiSelectTO.fromWidget(widget)
        w.choices = [ChoiceTO(u"label", x) for x in [u"a", u"b"]]
        self.assertRaises(DuplicateChoiceLabelException, validate, w)

        # no duplicate values in choices
        w = MultiSelectTO.fromWidget(widget)
        w.choices = [ChoiceTO(x, u"value") for x in [u"a", u"b"]]
        self.assertRaises(DuplicateChoiceValueException, validate, w)

        # no duplicate values
        w = MultiSelectTO.fromWidget(widget)
        w.values = [w.choices[0].value, w.choices[0].value]
        self.assertRaises(DuplicateValueException, validate, w)

        # values in choices
        w = MultiSelectTO.fromWidget(widget)
        w.values = [w.choices[0].value, u"not in choices"]
        self.assertRaises(ValueNotInChoicesException, validate, w)
        w.values = [w.choices[0].value, w.choices[1].value]
        validate(w)

    def testDateSelectTO(self):
        fm, form, widget = self._getDateSelectForm()
        db.put(fm)
        fmTO = FormMessageTO.fromFormMessage(fm)
        self.assertEquals(fmTO.form.type, form.type)
        self.assertEquals(fmTO.form.widget.unit, widget.unit)
        self.assertEquals(fmTO.form.widget.mode, widget.mode)
        self.assertEquals(fmTO.form.widget.max_date, widget.max_date)
        self.assertEquals(fmTO.form.widget.min_date, widget.min_date)
        self.assertEquals(fmTO.form.widget.date, widget.date)

    def testValidateDateSelectTO(self):
        _, _, widget = self._getDateSelectForm()
        validate = WIDGET_MAPPING[widget.TYPE].to_validate
        validate(DateSelectTO.fromWidget(widget))

        # min_date <= max_date
        w = DateSelectTO.fromWidget(widget)
        w.min_date = w.max_date + 1
        self.assertRaises(InvalidBoundariesException, validate, w)
        w.min_date = w.date = w.max_date
        validate(w)

        # min_date <= date
        w = DateSelectTO.fromWidget(widget)
        w.date = w.min_date - 1
        self.assertRaises(ValueNotWithinBoundariesException, validate, w)
        w.date = w.min_date
        validate(w)

        # date <= max_date
        w = DateSelectTO.fromWidget(widget)
        w.date = w.max_date + 1
        self.assertRaises(ValueNotWithinBoundariesException, validate, w)
        w.date = w.max_date
        validate(w)

        # invalid unit
        w = DateSelectTO.fromWidget(widget)
        w.unit = u"$"
        self.assertRaises(InvalidUnitException, validate, w)
        w.unit = u"$<value/>"
        validate(w)

        # invalid minute_interval
        w = DateSelectTO.fromWidget(widget)
        w.minute_interval = -1
        self.assertRaises(InvalidDateSelectMinuteIntervalException, validate, w)
        w.minute_interval = 0
        self.assertRaises(InvalidDateSelectMinuteIntervalException, validate, w)
        w.minute_interval = 60
        self.assertRaises(InvalidDateSelectMinuteIntervalException, validate, w)
        w.minute_interval = 1
        validate(w)
        w.minute_interval = 30
        validate(w)

        # minute_interval must be evenly divided into 60
        w = DateSelectTO.fromWidget(widget)
        w.minute_interval = 8
        self.assertRaises(MinuteIntervalNotEvenlyDividedInto60Exception, validate, w)
        w.minute_interval = 13
        self.assertRaises(MinuteIntervalNotEvenlyDividedInto60Exception, validate, w)
        w.minute_interval = 4
        validate(w)

        # date/min_date/max_date should be multiples of minute_interval
        w = DateSelectTO.fromWidget(widget)
        w.min_date = 13
        self.assertRaises(DateSelectValuesShouldBeMultiplesOfMinuteInterval, validate, w)
        w = DateSelectTO.fromWidget(widget)
        w.max_date = w.date + 123
        self.assertRaises(DateSelectValuesShouldBeMultiplesOfMinuteInterval, validate, w)
        w = DateSelectTO.fromWidget(widget)
        w.date = w.min_date + 123
        self.assertRaises(DateSelectValuesShouldBeMultiplesOfMinuteInterval, validate, w)

        # invalid mode
        w = DateSelectTO.fromWidget(widget)
        w.mode = u"invalid_mode"
        self.assertRaises(InvalidDateSelectModeException, validate, w)

        # mode date
        w = DateSelectTO.fromWidget(widget)
        good_date = 86400 * 5
        good_min_date = 86400 * 3
        good_max_date = 86400 * 10
        bad_date = int(86400 * 3.5)
        bad_min_date = int(86400 * 1.5)
        bad_max_date = int(86400 * 5.5)
        w.mode = DateSelect.MODE_DATE
        w.date = good_date
        w.max_date = good_max_date
        w.min_date = bad_min_date
        self.assertRaises(InvalidValueInDateSelectWithModeDate, validate, w)
        w.min_date = good_min_date
        validate(w)
        w.max_date = bad_max_date
        self.assertRaises(InvalidValueInDateSelectWithModeDate, validate, w)
        w.max_date = good_max_date
        validate(w)
        w.date = bad_date
        self.assertRaises(InvalidValueInDateSelectWithModeDate, validate, w)
        w.date = good_date
        validate(w)

        # mode time
        w = DateSelectTO.fromWidget(widget)
        w.mode = DateSelect.MODE_TIME
        good_min_date = 20 * 3600
        good_max_date = 24 * 3600
        bad_min_date = -86490
        bad_max_date = 86490
        w.date = 23 * 3600
        w.max_date = good_max_date
        w.min_date = bad_min_date
        self.assertRaises(InvalidValueInDateSelectWithModeTime, validate, w)
        w.min_date = good_min_date
        validate(w)
        w.max_date = bad_max_date
        self.assertRaises(InvalidValueInDateSelectWithModeTime, validate, w)
        w.max_date = good_max_date
        validate(w)

    def testSingleSliderTO(self):
        fm, form, widget = self._getSingleSliderForm()
        db.put(fm)
        fmTO = FormMessageTO.fromFormMessage(fm)
        self.assertEqual(fmTO.form.type, form.type)
        self.assertEqual(fmTO.form.widget.value, widget.value)

    def testValidateSingleSliderTO(self):
        _, _, widget = self._getSingleSliderForm()
        validate = WIDGET_MAPPING[widget.TYPE].to_validate
        validate(SingleSliderTO.fromWidget(widget))

        # min <= max
        w = SingleSliderTO.fromWidget(widget)
        w.step = 1
        w.min = w.max + 1
        self.assertRaises(InvalidBoundariesException, validate, w)
        w.min = w.value = w.max
        self.assertRaises(InvalidStepValue, validate, w)

        # min <= value
        w = SingleSliderTO.fromWidget(widget)
        w.value = w.min - 1
        self.assertRaises(ValueNotWithinBoundariesException, validate, w)
        w.value = w.min
        validate(w)

        # value <= max
        w = SingleSliderTO.fromWidget(widget)
        w.value = w.max + 1
        self.assertRaises(ValueNotWithinBoundariesException, validate, w)
        w.value = w.max
        validate(w)

        # invalid unit
        w = SingleSliderTO.fromWidget(widget)
        w.unit = u"$"
        self.assertRaises(InvalidUnitException, validate, w)
        w.unit = u"$<value/>"
        validate(w)

        # invalid step
        w = SingleSliderTO.fromWidget(widget)
        w.step = -1
        self.assertRaises(InvalidWidgetValueException, validate, w)
        w.step = 0
        self.assertRaises(InvalidWidgetValueException, validate, w)
        w.step = MISSING
        validate(w)
        w.step = 0.1
        validate(w)
        w.step = 2
        validate(w)

        # invalid precision
        w = SingleSliderTO.fromWidget(widget)
        w.precision = -1
        self.assertRaises(InvalidWidgetValueException, validate, w)
        w.precision = MISSING
        validate(w)
        w.precision = 0
        validate(w)
        w.precision = 2
        validate(w)


    def testRangeSliderTO(self):
        fm, form, widget = self._getRangeSliderForm()
        db.put(fm)
        fmTO = FormMessageTO.fromFormMessage(fm)
        self.assertEqual(fmTO.form.type, form.type)
        self.assertEqual(fmTO.form.widget.high_value, widget.high_value)
        self.assertEqual(fmTO.form.widget.low_value, widget.low_value)

    def testValidateRangeSliderTO(self):
        _, _, widget = self._getRangeSliderForm()
        validate = WIDGET_MAPPING[widget.TYPE].to_validate
        validate(RangeSliderTO.fromWidget(widget))

        # min <= max
        w = RangeSliderTO.fromWidget(widget)
        w.step = 1
        w.min = w.max + 1
        self.assertRaises(InvalidBoundariesException, validate, w)
        w.min = w.low_value = w.high_value = w.max
        self.assertRaises(InvalidStepValue, validate, w)

        # min <= low_value
        w = RangeSliderTO.fromWidget(widget)
        w.low_value = w.min - 1
        self.assertRaises(ValueNotWithinBoundariesException, validate, w)
        w.low_value = w.min
        validate(w)

        # low_value <= high_value
        w = RangeSliderTO.fromWidget(widget)
        w.low_value = w.high_value + 1
        self.assertRaises(InvalidRangeException, validate, w)
        w.low_value = w.high_value
        validate(w)

        # high_value <= max
        w = RangeSliderTO.fromWidget(widget)
        w.high_value = w.max + 1
        self.assertRaises(ValueNotWithinBoundariesException, validate, w)
        w.high_value = w.max
        validate(w)

        # invalid unit
        w = RangeSliderTO.fromWidget(widget)
        w.unit = u"$"
        self.assertRaises(InvalidUnitException, validate, w)
        w.unit = u"$<high_value/>"
        self.assertRaises(InvalidUnitException, validate, w)
        w.unit = u"$<low_value/>"
        self.assertRaises(InvalidUnitException, validate, w)
        w.unit = u"$<value/>"
        self.assertRaises(InvalidUnitException, validate, w)
        w.unit = u"$<low_value/> - $<high_value/>"
        validate(w)


    def testUnicodeWidgetResult(self):
        fm, _, _ = self._getTextLineForm()

        r = UnicodeWidgetResult()
        r.value = u"value"

        fr = FormResult()
        fr.type = r.TYPE
        fr.result = r

        ms = fm.memberStatusses[0]
        ms.button_index = fm.buttons[Form.POSITIVE].index
        ms.dismissed = False
        ms.form_result = fr
        ms.received_timestamp = now()
        ms.status = ms.STATUS_ACKED | ms.STATUS_RECEIVED
        db.put(fm)

        fm2 = db.get(fm.key())
        self.assert_(fm2)


    def testUnicodeListWidgetResult(self):
        fm, _, _ = self._getMultiSelectForm()

        r = UnicodeListWidgetResult()
        r.values = [u"value1", u"value2"]

        fr = FormResult()
        fr.type = r.TYPE
        fr.result = r

        ms = fm.memberStatusses[0]
        ms.button_index = fm.buttons[Form.POSITIVE].index
        ms.dismissed = False
        ms.form_result = fr
        ms.received_timestamp = now()
        ms.status = ms.STATUS_ACKED | ms.STATUS_RECEIVED
        db.put(fm)

        fm2 = db.get(fm.key())
        self.assert_(fm2)


    def testFloatWidgetResult(self):
        fm, _, _ = self._getSingleSliderForm()

        r = FloatWidgetResult()
        r.value = 1

        fr = FormResult()
        fr.type = r.TYPE
        fr.result = r

        ms = fm.memberStatusses[0]
        ms.button_index = fm.buttons[Form.POSITIVE].index
        ms.dismissed = False
        ms.form_result = fr
        ms.received_timestamp = now()
        ms.status = ms.STATUS_ACKED | ms.STATUS_RECEIVED
        db.put(fm)

        fm2 = db.get(fm.key())
        self.assert_(fm2)


    def testFloatListWidgetResult(self):
        fm, _, _ = self._getRangeSliderForm()

        r = FloatListWidgetResult()
        r.values = [20, 80]

        fr = FormResult()
        fr.type = r.TYPE
        fr.result = r

        ms = fm.memberStatusses[0]
        ms.button_index = fm.buttons[Form.POSITIVE].index
        ms.dismissed = False
        ms.form_result = fr
        ms.received_timestamp = now()
        ms.status = ms.STATUS_ACKED | ms.STATUS_RECEIVED
        db.put(fm)

        fm2 = db.get(fm.key())
        self.assert_(fm2)


    def testConfirmation(self):
        # Without confirmation
        fm, _, _ = self._getTextLineForm()
        db.put(fm)
        fmTO = FormMessageTO.fromFormMessage(fm)
        self.assertFalse(fmTO.form.positive_confirmation)
        self.assertFalse(fmTO.form.negative_confirmation)

        # With confirmation
        fm, _, _ = self._getTextLineForm()
        for btn in fm.buttons:
            btn.action = "confirm://test_%s" % btn.id
        db.put(fm)
        fmTO = FormMessageTO.fromFormMessage(fm)
        self.assertEqual(fmTO.form.positive_confirmation, "test_%s" % Form.POSITIVE)
        self.assertEqual(fmTO.form.negative_confirmation, "test_%s" % Form.NEGATIVE)
