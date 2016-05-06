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
import re
import uuid
import zlib
from types import NoneType

from google.appengine.ext import db

from rogerthat.bizz.i18n import Translator, get_translator
from rogerthat.bizz.service.mfd.gen import MessageFlowDefinition
from rogerthat.bizz.service.mfd.mfd_javascript import generate_js_flow
from rogerthat.bizz.service.mfd.sub import MessageFlowDefinitionSub, EndSub, MessageSub, contentTypeSub, AnswerSub, \
    OutletSub, FormMessageSub, FormSub, TextLineWidgetSub, TextWidgetSub, TextBlockWidgetSub, \
    TextAutocompleteWidgetSub, ValueSub, SelectSingleWidgetSub, ChoiceSub, SelectMultiWidgetSub, SelectDateWidgetSub, \
    SliderWidgetSub, RangeSliderWidgetSub, contentType1Sub, ResultsFlushSub, MessageFlowDefinitionSetSub, parsexml_, \
    PhotoUploadWidgetSub, ResultsEmailSub, GPSLocationWidgetSub, AttachmentSub, FlowCodeSub, MyDigiPassWidgetSub, \
    javascriptCodeTypeSub, AdvancedOrderWidgetSub, AdvancedOrderCategorySub, AdvancedOrderItemSub
from rogerthat.dal import parent_key
from rogerthat.dal.mfd import get_service_message_flow_design_by_name, get_super_message_flows, \
    get_sub_message_flows, get_message_flow_design_keys_by_sub_flow_key, \
    get_message_flow_designs_by_sub_flow_key, is_message_flow_used_by_menu_item, is_message_flow_used_by_qr_code
from rogerthat.dal.profile import get_service_profile
from rogerthat.dal.service import get_service_menu_items
from rogerthat.models import MessageFlowDesign, MessageFlowDesignBackup, ServiceTranslation
from rogerthat.models.properties.forms import MdpScope
from rogerthat.models.properties.messaging import JsFlowDefinition, JsFlowDefinitions
from rogerthat.rpc import users
from rogerthat.rpc.service import ServiceApiException, BusinessException
from rogerthat.to import WIDGET_MAPPING
from rogerthat.to.messaging.forms import TextLineTO, TextBlockTO, AutoCompleteTO, SingleSelectTO, MultiSelectTO, \
    SingleSliderTO, RangeSliderTO, DateSelectTO, PhotoUploadTO, GPSLocationTO, MyDigiPassTO, \
    AdvancedOrderTO
from rogerthat.utils import now, channel, bizz_check, azzert, \
    reversed_dict, xml_escape
from rogerthat.utils.attachment import get_attachment_content_type_and_length
from rogerthat.utils.crypto import md5_hex
from rogerthat.utils.service import add_slash_default
from mcfw.rpc import arguments, returns
from rogerthat.bizz.messaging import MessageFlowValidationException

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

TO_CONVERSION_MAPPING = {
    TextLineWidgetSub: TextLineTO,
    TextBlockWidgetSub: TextBlockTO,
    TextAutocompleteWidgetSub: AutoCompleteTO,
    SelectSingleWidgetSub: SingleSelectTO,
    SelectMultiWidgetSub: MultiSelectTO,
    SelectDateWidgetSub: DateSelectTO,
    SliderWidgetSub: SingleSliderTO,
    RangeSliderWidgetSub: RangeSliderTO,
    PhotoUploadWidgetSub : PhotoUploadTO,
    GPSLocationWidgetSub: GPSLocationTO,
    MyDigiPassWidgetSub: MyDigiPassTO,
    AdvancedOrderWidgetSub: AdvancedOrderTO
}


MFD_MODULE_START = 'Start'
MFD_MODULE_END = 'End'
MFD_MODULE_MESSAGE_FLOW = 'Message flow'
MFD_MODULE_MESSAGE = 'Message'
MFD_MODULE_TEXT_LINE = 'Text line'
MFD_MODULE_TEXT_BLOCK = 'Text block'
MFD_MODULE_AUTO_COMPLETE = 'Text autocomplete'
MFD_MODULE_SINGLE_SELECT = 'Single select'
MFD_MODULE_MULTI_SELECT = 'Multi select'
MFD_MODULE_DATE_SELECT = 'Date select'
MFD_MODULE_SINGLE_SLIDER = 'Single slider'
MFD_MODULE_RANGE_SLIDER = 'Range slider'
MFD_MODULE_PHOTO_UPLOAD = 'Photo upload'
MFD_MODULE_GPS_LOCATION = 'GPS Location'
MFD_MODULE_MYDIGIPASS = 'MYDIGIPASS'
MFD_MODULE_ADVANCED_ORDER = 'Advanced order'
MFD_MODULE_RESULTS_FLUSH = 'Results flush'
MFD_MODULE_RESULTS_EMAIL = 'Results email'
MFD_MODULE_FLOW_CODE = 'Flow code'

MFD_WIDGET_MODULE_MAPPING = { MFD_MODULE_TEXT_LINE : TextLineWidgetSub,
                              MFD_MODULE_TEXT_BLOCK : TextBlockWidgetSub,
                              MFD_MODULE_AUTO_COMPLETE : TextAutocompleteWidgetSub,
                              MFD_MODULE_SINGLE_SELECT : SelectSingleWidgetSub,
                              MFD_MODULE_MULTI_SELECT : SelectMultiWidgetSub,
                              MFD_MODULE_DATE_SELECT : SelectDateWidgetSub,
                              MFD_MODULE_SINGLE_SLIDER : SliderWidgetSub,
                              MFD_MODULE_RANGE_SLIDER : RangeSliderWidgetSub,
                              MFD_MODULE_PHOTO_UPLOAD : PhotoUploadWidgetSub,
                              MFD_MODULE_GPS_LOCATION : GPSLocationWidgetSub,
                              MFD_MODULE_MYDIGIPASS : MyDigiPassWidgetSub,
                              MFD_MODULE_ADVANCED_ORDER : AdvancedOrderWidgetSub}

# Reversed mapping needed to map instance type to module name (for XML-only flows)
MFD_WIDGET_STUB_MODULE_MAPPING = reversed_dict(MFD_WIDGET_MODULE_MAPPING)

# Used in unit tests
MFD_FORM_MODULES = [MFD_MODULE_TEXT_LINE, MFD_MODULE_TEXT_BLOCK, MFD_MODULE_AUTO_COMPLETE, MFD_MODULE_SINGLE_SELECT,
                    MFD_MODULE_MULTI_SELECT, MFD_MODULE_DATE_SELECT, MFD_MODULE_SINGLE_SLIDER, MFD_MODULE_RANGE_SLIDER,
                    MFD_MODULE_PHOTO_UPLOAD, MFD_MODULE_GPS_LOCATION, MFD_MODULE_MYDIGIPASS, MFD_MODULE_ADVANCED_ORDER]

class MessageFlowDesignLoopException(Exception):

    def __init__(self, message_flow_design):
        self.message_flow_design = message_flow_design

class MessageFlowDesignLevelTooDeepException(Exception):

    def __init__(self, message_flow_design):
        self.message_flow_design = message_flow_design


@returns(tuple)
@arguments(message_flow_design=MessageFlowDesign, context=dict, parsed_mf_defs=dict, circular_refs=dict)
def message_flow_design_to_message_flow_definition(message_flow_design, context, parsed_mf_defs=None, circular_refs=None):
    definition = json.loads(message_flow_design.definition)
    sub_flows = set()
    result = MessageFlowDefinitionSub(name=message_flow_design.name)
    if parsed_mf_defs is None:
        parsed_mf_defs = dict()
    if circular_refs is None:
        circular_refs = dict()

    parsed_mf_defs[message_flow_design.key()] = None

    def set_reference(elem, attr, target_id):
        if isinstance(target_id, db.Key):  # sub_flow
            if not target_id in circular_refs:
                circular_refs[target_id] = list()
            circular_refs[target_id].append((elem, attr))
        else:
            setattr(elem, attr, target_id)

    def parseStart(module):
        module['id'] = create_json_id(message_flow_design, "start_", str(uuid.uuid4()))
        return 'start'

    def parseEnd(module):
        ed = module['value']
        bizz_check(ed.get('id'), "'End' exit with empty id field detected.")
        id_ = create_json_id(message_flow_design, 'end_', ed['id'])
        module['id'] = id_
        end = EndSub(id=id_, waitForFollowUpMessage=ed.get('waitForFollowUpMessage', False))
        result.add_end(end)
        return end

    def parseResultsFlush(module):
        w = module['value']
        bizz_check(w.get('id'), "Results Flush has an empty id field!")
        id_ = create_json_id(message_flow_design, 'flush_', w['id'])
        module['id'] = id_
        rflush = ResultsFlushSub(id=id_)
        result.add_resultsFlush(rflush)
        return rflush

    def parseResultsEmail(module):
        w = module['value']
        bizz_check(w.get('id'), "Results Email has an empty id field!")
        id_ = create_json_id(message_flow_design, 'email_', w['id'])
        module['id'] = id_
        remail = ResultsEmailSub(id=id_)
        remail.set_emailAdmins(w.get('emailadmins'))
        emails_list = w.get('emails_group')['emails_list']
        remail.set_email([ ValueSub(value=s['email']) for s in emails_list ])
        result.add_resultsEmail(remail)
        return remail

    def parseFlowCode(module):
        w = module['config']['sourceDef']
        bizz_check(w.get('id'), "Flow code has an empty id field!")
        id_ = create_json_id(message_flow_design, 'flow_code_', w['id'])
        module['id'] = id_
        fcSub = FlowCodeSub(id=id_)
        for outlet in w['outlets_group']['outlets_list']:
            fcSub.add_outlet(OutletSub(name=outlet, value=outlet))
        fcSub.set_javascriptCode(javascriptCodeTypeSub(valueOf_=w['javascript_code']))
        result.add_flowCode(fcSub)
        return fcSub

    def parseSubMessageFlow(module):
        # nmessage_flow is just a typo from Bart we got stuck with
        mfd_id = module['value']['nmessage_flow']
        bizz_check(mfd_id, "Please select a message flow")
        mfd_key = db.Key(mfd_id)
        sub_flows.add(mfd_key)
        if context is None:  # if context is supplied we need to build the doc recursively.
            id_ = create_json_id(message_flow_design, "end_", str(uuid.uuid4()))
            module['id'] = id_
            end = EndSub(id=id_)
            result.add_end(end)
            return end
        elif mfd_key in parsed_mf_defs:
            mf_def = parsed_mf_defs[mfd_key]
            module['id'] = mf_def.startReference if mf_def else mfd_key
            return None
        else:
            mf = context.get(mfd_key)
            if not mf:
                mf = db.get(mfd_key)
                bizz_check(mf, "Selected message flow (%s) does not exist" % mfd_key.name())
                context[mfd_key] = mf
            if mf.xml:
                default_language = get_service_profile(mf.user).defaultLanguage
                if 'messageFlowDefinitionSet' in mf.xml:
                    mf_defs = parse_message_flow_definition_set_xml(mf.xml.encode('utf-8'))
                    for mf_def in mf_defs.definition:
                        if mf_def.language == default_language:
                            break
                    else:
                        mf_def = mf_defs.definition[0]
                else:
                    mf_def = parse_message_flow_definition_xml(mf.xml)
            else:
                mf_def = message_flow_design_to_message_flow_definition(mf, context, parsed_mf_defs, circular_refs)[0]

            parsed_mf_defs[mfd_key] = mf_def
            if mf_def.startReference:
                module['id'] = mf_def.startReference
            else:
                # startReference of sub flow must point to a flow which we are currently parsing (recursively)
                # so it should be found in circular_refs
                for k, v in circular_refs.iteritems():
                    for sub_mf_def, _ in v:
                        if sub_mf_def == mf_def:
                            module['id'] = k
                            break
                    else:
                        continue
                    break
                else:
                    bizz_check(False, "Could not determine start of message flow '%s'" % mf.name)

            return mf_def

    def populateAttachment(attachment):
        attachment.contentType, attachment.size = get_attachment_content_type_and_length(attachment.url)
        return attachment


    def parseMessage(module):
        md = module['config']['messageDef']
        if not md.get('id'):
            bizz_check(False, "Message '%s' has an empty id field!" % (xml_escape(md['message']).replace('\n', ' ')))
        id_ = create_json_id(message_flow_design, 'message_', md['id'])
        module['id'] = id_
        message = MessageSub(id=id_)
        message.vibrate = md['settings_group']['vibrate']
        message.alertType = md['settings_group']['alert_type']
        message.alertIntervalType = md['settings_group']['alert_interval']
        message.autoLock = md['settings_group']['auto_lock']
        message.allowDismiss = md['settings_group']['rogerthat_button']
        message.dismissReference = None
        message.brandingKey = md['settings_group']['branding'] or None
        message.content = contentTypeSub()
        message.content.valueOf_ = md['message'].strip()
        for button in md['buttons_group']['buttons_list']:
            message.add_answer(AnswerSub(action=button['action'], caption=button['caption'], id='button_' + button['id']))
        if 'attachments_group' in md:
            for attachment in md['attachments_group']['attachments_list']:
                message.add_attachment(populateAttachment(AttachmentSub(url=attachment['value'],
                                                                        name=attachment['label'])))
        result.add_message(message)
        return message

    def parseFormMessage(module):
        try:
            w = module['config']['formMessageDef']
        except:
            w = module['value']

        form = FormSub()
        form.positiveButtonCaption = w['form_settings_group']['positive_caption']
        form.positiveButtonConfirmation = w['form_settings_group']['positive_confirmation']
        form.negativeButtonCaption = w['form_settings_group']['negative_caption']
        form.negativeButtonConfirmation = w['form_settings_group']['negative_confirmation']
        form.javascriptValidation = w['form_settings_group'].get('javascript_validation', None)

        bizz_check(w.get('id'), "%s '%s' has an empty id field!" % (module['name'], xml_escape(w['message']).replace('\n', ' ')))
        id_ = create_json_id(message_flow_design, 'message_', w['id'])
        module['id'] = id_
        fm = FormMessageSub(id=id_)
        fm.brandingKey = w['message_settings_group']['branding'] or None
        fm.vibrate = w['message_settings_group']['vibrate']
        fm.alertType = w['message_settings_group']['alert_type']
        fm.alertIntervalType = w['message_settings_group']['alert_interval']
        fm.autoLock = w['message_settings_group']['auto_lock']
        fm.content = contentType1Sub()
        fm.content.valueOf_ = w['message'].strip()
        fm.form = form

        if 'attachments_group' in w:
            for attachment in w['attachments_group']['attachments_list']:
                fm.add_attachment(populateAttachment(AttachmentSub(url=attachment['value'],
                                                                   name=attachment['label'])))
        result.add_formMessage(fm)
        return fm

    def _parseNumber(value_str, type_, value_name, fm_sub, defaultValue=None):
        if not value_str:
            if defaultValue is None:
                fm = fm_sub.content.valueOf_.replace('\n', ' ')
                bizz_check(False, "%s is a required field in form message '%s'" % (value_name, fm))
            else:
                return defaultValue
        try:
            return type_(value_str)
        except Exception:
            fm = fm_sub.content.valueOf_.replace('\n', ' ')
            bizz_check(False, "%s is an invalid value for '%s' in form message '%s'" % (value_str, value_name, fm))

    def _populateTextWidget(w_sub, module, fm_sub):
        try:
            form_settings = module['config']['formMessageDef']['form_settings_group']
        except:
            form_settings = module['value']['form_settings_group']
        w_sub.maxChars = _parseNumber(form_settings['max_chars'], long, "Max chars", fm_sub)
        w_sub.placeholder = form_settings['place_holder'] or None
        w_sub.value = form_settings['value'] or None
        return w_sub

    def _populateSelectWidget(w_sub, module):
        try:
            choices_list = module['config']['formMessageDef']['choices_group']['choices_list']
        except:
            choices_list = module['value']['choices_group']['choices_list']
        w_sub.choice = [ ChoiceSub(label=c['label'], value=c['value']) for c in choices_list ]
        return w_sub

    def _populateSliderWidget(w_sub, module, fm_sub):
        try:
            form_settings = module['config']['formMessageDef']['form_settings_group']
        except:
            form_settings = module['value']['form_settings_group']
        w_sub.min = _parseNumber(form_settings['min'], float, "Minimum value", fm_sub)
        w_sub.max = _parseNumber(form_settings['max'], float, "Maximum value", fm_sub)
        w_sub.step = _parseNumber(form_settings['step'], float, "Step", fm_sub, defaultValue=1)
        w_sub.precision = _parseNumber(form_settings['precision'], long, "Precision", fm_sub, defaultValue=0)
        w_sub.unit = form_settings['unit'] or None
        return w_sub

    def parseTextLine(module):
        fm = parseFormMessage(module)
        fm.form.widget = _populateTextWidget(MFD_WIDGET_MODULE_MAPPING[module['name']](), module, fm)
        fm.form.widget.set_extensiontype_('TextLineWidget')
        return fm

    def parseTextBlock(module):
        fm = parseFormMessage(module)
        fm.form.widget = _populateTextWidget(MFD_WIDGET_MODULE_MAPPING[module['name']](), module, fm)
        fm.form.widget.set_extensiontype_('TextBlockWidget')
        return fm

    def parseAutoComplete(module):
        fm = parseFormMessage(module)
        fm.form.widget = _populateTextWidget(MFD_WIDGET_MODULE_MAPPING[module['name']](), module, fm)
        try:
            suggestions_list = module['config']['formMessageDef']['suggestions_group']['suggestions_list']
        except:
            suggestions_list = module['value']['suggestions_group']['suggestions_list']
        fm.form.widget.suggestion = [ ValueSub(value=s['value']) for s in suggestions_list ]
        fm.form.widget.set_extensiontype_('TextAutocompleteWidget')
        return fm

    def parseSingleSelect(module):
        fm = parseFormMessage(module)
        fm.form.widget = _populateSelectWidget(MFD_WIDGET_MODULE_MAPPING[module['name']](), module)
        try:
            form_settings = module['config']['formMessageDef']['form_settings_group']
        except:
            form_settings = module['value']['form_settings_group']

        fm.form.widget.value = form_settings['value'] or None
        fm.form.widget.set_extensiontype_('SelectSingleWidget')
        return fm

    def parseMultiSelect(module):
        fm = parseFormMessage(module)
        fm.form.widget = _populateSelectWidget(MFD_WIDGET_MODULE_MAPPING[module['name']](), module)
        try:
            initial_choices_list = module['config']['formMessageDef']['initial_choices_group']['initial_choices_list']
        except:
            initial_choices_list = module['value']['initial_choices_group']['initial_choices_list']
        fm.form.widget.value = [ ValueSub(value=c['value']) for c in initial_choices_list ]
        fm.form.widget.set_extensiontype_('SelectMultiWidget')
        return fm

    def parseDateSelect(module):
        try:
            form_settings = module['config']['formMessageDef']['form_settings_group']
        except:
            form_settings = module['value']['form_settings_group']
        fm = parseFormMessage(module)
        fm.form.widget = MFD_WIDGET_MODULE_MAPPING[module['name']]()
        fm.form.widget.date = None
        fm.form.widget.maxDate = None
        fm.form.widget.minDate = None
        fm.form.widget.minuteInterval = _parseNumber(form_settings['minute_interval'], long, "Minute interval", \
                                                     fm, defaultValue=DateSelectTO.DEFAULT_MINUTE_INTERVAL)
        fm.form.widget.mode = form_settings['mode']
        fm.form.widget.unit = form_settings['unit'] or None
        fm.form.widget.set_extensiontype_('SelectDateWidget')
        return fm

    def parseSingleSlider(module):
        fm = parseFormMessage(module)
        fm.form.widget = _populateSliderWidget(MFD_WIDGET_MODULE_MAPPING[module['name']](), module, fm)
        try:
            form_settings = module['config']['formMessageDef']['form_settings_group']
        except:
            form_settings = module['value']['form_settings_group']
        fm.form.widget.value = _parseNumber(form_settings['value'], float, "Value", fm, \
                                    defaultValue=fm.form.widget.min)
        fm.form.widget.set_extensiontype_('SliderWidget')
        return fm

    def parseRangeSlider(module):
        fm = parseFormMessage(module)
        fm.form.widget = _populateSliderWidget(MFD_WIDGET_MODULE_MAPPING[module['name']](), module, fm)
        try:
            form_settings = module['config']['formMessageDef']['form_settings_group']
        except:
            form_settings = module['value']['form_settings_group']
        fm.form.widget.lowValue = _parseNumber(form_settings['low_value'], float, \
                                               "Low value", fm, defaultValue=fm.form.widget.min)
        fm.form.widget.highValue = _parseNumber(form_settings['high_value'], float, \
                                                "High value", fm, defaultValue=fm.form.widget.max)
        fm.form.widget.set_extensiontype_('RangeSliderWidget')
        return fm

    def parsePhotoUpload(module):
        form_settings = module['value']['form_settings_group']
        fm = parseFormMessage(module)
        fm.form.widget = MFD_WIDGET_MODULE_MAPPING[module['name']]()
        if form_settings['crop']:
            fm.form.widget.ratio = form_settings['ratio'] or u'0x0'
        else:
            fm.form.widget.ratio = None

        fm.form.widget.quality = form_settings['quality']

        if str(form_settings['source']) == 'gallery':
            fm.form.widget.gallery = True
            fm.form.widget.camera = False
        elif str(form_settings['source']) == 'camera':
            fm.form.widget.camera = True
            fm.form.widget.gallery = False
        elif str(form_settings['source']) == 'gallery_camera':
            fm.form.widget.gallery = True
            fm.form.widget.camera = True
        fm.form.widget.set_extensiontype_('PhotoUploadWidget')
        return fm

    def parseGPSLocation(module):
        form_settings = module['value']['form_settings_group']
        fm = parseFormMessage(module)
        fm.form.widget = MFD_WIDGET_MODULE_MAPPING[module['name']]()
        fm.form.widget.gps = form_settings['gps']
        fm.form.widget.set_extensiontype_('GPSLocationWidget')
        return fm

    def parseMyDigiPass(module):
        fm = parseFormMessage(module)
        fm.form.widget = MFD_WIDGET_MODULE_MAPPING[module['name']]()
        fm.form.widget.scope = " ".join(sorted((scope for scope in MdpScope.all()
                                                if module['value']['mdp_scopes_group'][scope])))
        fm.form.widget.set_extensiontype_('MyDigiPassWidget')
        return fm

    def parseAdvancedOrder(module):
        try:
            form_settings = module['config']['formMessageDef']['form_settings_group']
        except:
            form_settings = module['value']['form_settings_group']

        try:
            w = module['config']['formMessageDef']['advanced_order_group']
        except:
            w = module['value']['advanced_order_group']

        bizz_check(form_settings['currency'], "%s has an empty currency field!" % (module['name']))

        fm = parseFormMessage(module)
        fm.form.widget = MFD_WIDGET_MODULE_MAPPING[module['name']]()
        fm.form.widget.currency = form_settings['currency']
        fm.form.widget.leapTime = 0
        fm.form.widget.category = []

        for c in w['category_list']:
            category = AdvancedOrderCategorySub(c['id'], c['name'])
            for i in c['category_item_list']:
                unit_price = i['unitPrice'] or 0
                item = AdvancedOrderItemSub(id=i['id'],
                                            name=i['name'],
                                            description=i['description'],
                                            value=i['value'] or 0,
                                            unit=i['unit'],
                                            unitPrice=unit_price,
                                            hasPrice=False if unit_price == 0 else True,
                                            step=i['step'] or 0,
                                            stepUnit=i['stepUnit'],
                                            stepUnitConversion=i['stepUnitConversion'] or 0,
                                            imageUrl=i["imageUrl"])

                category.add_item(item)
            fm.form.widget.add_category(category)
        fm.form.widget.set_extensiontype_('AdvancedOrderWidget')
        return fm

    moduleParsers = {
        MFD_MODULE_START: parseStart,
        MFD_MODULE_END: parseEnd,
        MFD_MODULE_MESSAGE_FLOW: parseSubMessageFlow,
        MFD_MODULE_MESSAGE: parseMessage,
        MFD_MODULE_TEXT_LINE: parseTextLine,
        MFD_MODULE_TEXT_BLOCK: parseTextBlock,
        MFD_MODULE_AUTO_COMPLETE: parseAutoComplete,
        MFD_MODULE_SINGLE_SELECT: parseSingleSelect,
        MFD_MODULE_MULTI_SELECT: parseMultiSelect,
        MFD_MODULE_DATE_SELECT: parseDateSelect,
        MFD_MODULE_SINGLE_SLIDER: parseSingleSlider,
        MFD_MODULE_RANGE_SLIDER: parseRangeSlider,
        MFD_MODULE_RESULTS_FLUSH: parseResultsFlush,
        MFD_MODULE_PHOTO_UPLOAD: parsePhotoUpload,
        MFD_MODULE_RESULTS_EMAIL: parseResultsEmail,
        MFD_MODULE_GPS_LOCATION: parseGPSLocation,
        MFD_MODULE_MYDIGIPASS: parseMyDigiPass,
        MFD_MODULE_FLOW_CODE: parseFlowCode,
        MFD_MODULE_ADVANCED_ORDER: parseAdvancedOrder
    }

    for module in definition['modules']:
        elem = moduleParsers.get(module['name'], lambda x: x)(module)
        if elem is None:
            # We already parsed this module, or we are already parsing this module
            continue
        elif isinstance(elem, MessageFlowDefinition):
            result.end.extend(elem.end)
            result.message.extend(elem.message)
            result.formMessage.extend(elem.formMessage)
            result.resultsFlush.extend(elem.resultsFlush)
            result.resultsEmail.extend(elem.resultsEmail)
            result.flowCode.extend(elem.flowCode)
        else:
            module['elem'] = elem
            module_id = module.get('id')
            if not module_id:
                logging.info("Empty flow element identifier detected!\n%s" % module)
                bizz_check(False, "Empty flow element identifier detected!")

    for wire in definition['wires']:
        target_module = definition['modules'][wire['tgt']['moduleId']]
        source_module = definition['modules'][wire['src']['moduleId']]

        terminal = wire['src']['terminal']

        if terminal == 'in' or (terminal == 'end' and isinstance(source_module['elem'], EndSub)):
            # We must swap source and target
            source_object = target_module['elem']
            target_object = source_module.get('elem')
            target_id = source_module['id']
            endpoint = terminal  # 'in' or 'end'
            terminal = wire['tgt']['terminal']
        else:
            source_object = source_module['elem']
            target_object = target_module.get('elem')
            target_id = target_module['id']
            endpoint = wire['tgt']['terminal']  # 'in' or 'end'

        bizz_check(endpoint in ['in', 'end'], "Inlet name '%s' not expected." % endpoint)
        if target_object:
            set_reference(target_object, 'inletReference', 1)  # indicate that this in/end inlet is connected

        if source_object == 'start':
            bizz_check(not result.startReference, "Maximum one 'Start' entry point is allowed.")
            set_reference(result, 'startReference', target_id)
        elif isinstance(source_object, MessageSub):
            message = source_object
            if terminal == 'roger that':
                set_reference(message, 'dismissReference', target_id)
            else:
                for answer in message.answer:
                    if answer.caption == terminal:
                        set_reference(answer, 'reference', target_id)
                        break
        elif isinstance(source_object, FormMessageSub):
            fm = source_object
            if terminal == 'positive':
                set_reference(fm, 'positiveReference', target_id)
            elif terminal == 'negative':
                set_reference(fm, 'negativeReference', target_id)
            else:
                bizz_check(False, "Unexpected terminal found.")
        elif isinstance(source_object, ResultsFlushSub):
            resultsFlush = source_object
            if terminal == 'out':
                set_reference(resultsFlush, 'reference', target_id)
            else:
                bizz_check(False, "Unexpected terminal found.")
        elif isinstance(source_object, ResultsEmailSub):
            resultsEmail = source_object
            if terminal == 'out':
                set_reference(resultsEmail, 'reference', target_id)
            else:
                bizz_check(False, "Unexpected terminal found.")
        elif isinstance(source_object, FlowCodeSub):
            flowCode = source_object
            if terminal == 'exception':
                set_reference(flowCode, 'exceptionReference', target_id)
            else:
                for outlet in flowCode.outlet:
                    if outlet.value == terminal:
                        set_reference(outlet, 'reference', target_id)
                        break

    for elem, attr in circular_refs.get(message_flow_design.key(), list()):
        logging.info("%s %s = %s", (elem.__class__, attr, result.startReference))
        setattr(elem, attr, result.startReference)

    return result, list(sub_flows)

def get_json_from_b64id(b64id):
    return json.loads(base64.b64decode(b64id[7:]))

def get_printable_id_from_b64id(b64id, cutprefix=''):
    return get_json_from_b64id(b64id)['id'][len(cutprefix):] if b64id and b64id.startswith('base64:') else b64id

@returns(NoneType)
@arguments(mfdef=MessageFlowDefinitionSub, service_user=users.User, from_xml_only_flow=bool)
def validate_message_flow_definition(mfdef, service_user, from_xml_only_flow=False):
    ids = list()
    references = {mfdef.startReference}
    bizz_check(mfdef.end, "An 'End' exit is missing!", MessageFlowValidationException)

    for end in mfdef.end:
        ids.append(end.id)
        if not from_xml_only_flow:
            bizz_check(hasattr(end, 'inletReference'),
                       "Inlet not wired for End '%s'" % get_printable_id_from_b64id(end.id, 'end_'),
                       MessageFlowValidationException)
    bizz_check(mfdef.startReference, "A 'Start' entry point is missing!", MessageFlowValidationException)

    for message in mfdef.message:
        printable_id = get_printable_id_from_b64id(message.id, 'message_')
        if not from_xml_only_flow:
            bizz_check(hasattr(message, 'inletReference'),
                       "Inlet not wired for Message '%s'" % printable_id,
                       MessageFlowValidationException)
        bizz_check(message.answer or message.allowDismiss,
                   "At least the 'Roger that!' or a custom button is required in Message '%s'!" % printable_id,
                   MessageFlowValidationException)
        if message.allowDismiss:
            bizz_check(message.allowDismiss and message.dismissReference,
                       "The 'Roger that!' connector of Message '%s' is not wired!" % printable_id,
                       MessageFlowValidationException)
            references.add(message.dismissReference)
        captions = []
        for answer in message.answer:
            bizz_check(answer.caption and answer.caption.strip(),
                       "Button with empty label in Message '%s'" % printable_id,
                       MessageFlowValidationException)
            bizz_check(answer.caption not in ['roger that', 'in'],
                       "'%s' is an illegal label for a button in Message '%s'" % (answer.caption, printable_id),
                       MessageFlowValidationException)
            captions.append(answer.caption.strip())
        bizz_check(len(captions) == len(set(captions)),
                   "Button labels must be unique in Message '%s'!" % printable_id,
                   MessageFlowValidationException)
        answerids = []
        for answer in message.answer:
            bizz_check(answer.reference,
                       "Button '%s' of Message '%s' is not wired!" % (answer.caption, printable_id),
                       MessageFlowValidationException)
            bizz_check(answer.id != 'button_',
                       "Button '%s' of Message '%s' has an empty id field!" % (answer.caption, printable_id),
                       MessageFlowValidationException)
            if answer.action:
                bizz_check(re.match("^(http://|https://|confirm://|tel://|geo://|mailto://).*", answer.action),
                           "Button '%s' of Message '%s' has an illegal action '%s'. Supported actions are http://, https://, tel://, geo://, confirm:// and mailto:// ." % (answer.caption, printable_id, answer.action),
                           MessageFlowValidationException)
            answerids.append(answer.id)
            references.add(answer.reference)
        bizz_check(len(answerids) == len(set(answerids)),
                   "Button ids must be unique in Message '%s'!" % printable_id,
                   MessageFlowValidationException)
        ids.append(message.id)

    checked_mdp = False
    for mf in mfdef.formMessage:
        printable_id = get_printable_id_from_b64id(mf.id, 'message_')
        mf.module_name = MFD_WIDGET_STUB_MODULE_MAPPING[mf.form.widget.__class__]
        if not from_xml_only_flow:
            bizz_check(hasattr(mf, 'inletReference'), "Inlet not wired for %s '%s'" % (mf.module_name, printable_id),
                       MessageFlowValidationException)
        bizz_check(mf.positiveReference, "Green button of %s '%s' is not wired!" % (mf.module_name, printable_id),
                   MessageFlowValidationException)
        bizz_check(mf.negativeReference, "Red button of %s '%s' is not wired!" % (mf.module_name, printable_id),
                   MessageFlowValidationException)
        bizz_check(mf.form.positiveButtonCaption,
                   "Green button label is not set for %s '%s'!" % (mf.module_name, printable_id),
                   MessageFlowValidationException)
        bizz_check(mf.form.negativeButtonCaption,
                   "Red button label is not set for %s '%s'!" % (mf.module_name, printable_id),
                   MessageFlowValidationException)
        to = TO_CONVERSION_MAPPING[mf.form.widget.__class__].fromWidgetXmlSub(mf.form.widget)
        try:
            WIDGET_MAPPING[to.TYPE].to_validate(to)
        except ServiceApiException, e:
            fields = xml_escape("%s - " % e.fields) if e.fields else ""
            bizz_check(False, "%s%s For %s '%s'" % (fields, e.message, mf.module_name, printable_id),
                       MessageFlowValidationException)
        ids.append(mf.id)
        references.add(mf.positiveReference)
        references.add(mf.negativeReference)

        if not checked_mdp and to.TYPE == MyDigiPassTO.TYPE:
            from rogerthat.bizz.messaging import validate_my_digi_pass_support
            validate_my_digi_pass_support(service_user)
            checked_mdp = True

    for results_flush in mfdef.resultsFlush:
        printable_id = get_printable_id_from_b64id(results_flush.id, 'flush_')
        if not from_xml_only_flow:
            bizz_check(hasattr(results_flush, 'inletReference'),
                       "Inlet not wired for Results Flush '%s'" % printable_id,
                       MessageFlowValidationException)
        bizz_check(results_flush.reference,
                   "Outlet of Results Flush with id %s is not wired!" % printable_id,
                   MessageFlowValidationException)
        ids.append(results_flush.id)
        references.add(results_flush.reference)

    for results_email in mfdef.resultsEmail:
        printable_id = get_printable_id_from_b64id(results_email.id, 'email_')
        if not from_xml_only_flow:
            bizz_check(hasattr(results_email, 'inletReference'),
                       "Inlet not wired for Results Email '%s'" % printable_id,
                       MessageFlowValidationException)
        bizz_check(results_email.reference,
                   "Outlet of Results Email with id %s is not wired!" % printable_id,
                   MessageFlowValidationException)
        for email in results_email.email:
            bizz_check(email.value and email.value.strip(),
                       "Empty email value in Results email '%s'" % printable_id,
                       MessageFlowValidationException)
        ids.append(results_email.id)
        references.add(results_email.reference)

    for fc in mfdef.flowCode:
        printable_id = get_printable_id_from_b64id(fc.id, 'flow_code_')
        if not from_xml_only_flow:
            bizz_check(hasattr(fc, 'inletReference'), "Inlet not wired for Flow code '%s'" % printable_id,
                       MessageFlowValidationException)
        bizz_check(fc.exceptionReference,
                   "Flow code %s has no exception reference" % printable_id,
                   MessageFlowValidationException)
        outlet_names = []
        for outlet in fc.outlet:
            outlet_names.append(outlet.value)
            bizz_check(outlet.value != "exception",
                       "'exception' is an illegal outlet value in Flow code '%s'!" % printable_id,
                       MessageFlowValidationException)
            bizz_check(len(outlet_names) == len(set(outlet_names)),
                       "Outlets must be unique in Flow code '%s'!" % printable_id,
                       MessageFlowValidationException)
            bizz_check(outlet.reference, "Outlet '%s' of Flow code '%s' is not wired!" % (outlet.name, printable_id),
                       MessageFlowValidationException)
            references.add(outlet.reference)
        ids.append(fc.id)
        references.add(fc.exceptionReference)

    vertices = set(ids)
    bizz_check(len(ids) == len(vertices),
               "Duplicate flow element ids found: " + ", ".join(("(%s: %s times)" % (get_printable_id_from_b64id(a[0]), a[1])
                                                                 for a in ((id_, ids.count(id_)) for id_ in set(ids))
                                                                 if a[1] > 1)),
               MessageFlowValidationException)

    if from_xml_only_flow:
        for id_ in ids:
            bizz_check(id_ in references,
                       "Inlet not wired for '%s'" % get_printable_id_from_b64id(id_),
                       MessageFlowValidationException)
        for reference in references:
            bizz_check(reference in ids,
                       "Referencing a non-existing element '%s'" % get_printable_id_from_b64id(reference),
                       MessageFlowValidationException)

    # Detect orphans (unescapable circular loops)
    class dummy(object):
        user = service_user
        language = mfdef.language
        def key(self):
            return db.Key.from_path(MessageFlowDesign.kind(), mfdef.name, parent=parent_key(service_user))

    start_vertex = create_json_id(dummy(), "start", "start")
    vertices.add(start_vertex)
    edges = set()
    edges.add((start_vertex, mfdef.startReference))
    for message in mfdef.message:
        if message.allowDismiss:
            edges.add((message.id, message.dismissReference))
        for answer in message.answer:
            edges.add((message.id, answer.reference))
    for form in mfdef.formMessage:
        edges.add((form.id, form.positiveReference))
        edges.add((form.id, form.negativeReference))
    for resultsFlush in mfdef.resultsFlush:
        edges.add((resultsFlush.id, resultsFlush.reference))
    for resultsEmail in mfdef.resultsEmail:
        edges.add((resultsEmail.id, resultsEmail.reference))
    for flowCode in mfdef.flowCode:
        edges.add((flowCode.id, flowCode.exceptionReference))
        for outlet in flowCode.outlet:
            edges.add((flowCode.id, outlet.reference))
    sinks = set()
    for end in mfdef.end:
        sinks.add(end.id)
    # Verify top to bottom
    orphans = _find_orphans(vertices, edges, sinks)
    if orphans:
        orphans = list(orphans)
        orphans.append(orphans[0])
        bizz_check(False, "Unescapable path detected: " + ' > '.join((json.loads(base64.b64decode(a[7:]))["id"] for a in orphans)),
                   MessageFlowValidationException)


@returns(unicode)
@arguments(stub=object, tag_name=unicode, use_namespace=bool)
def to_xml_unicode(stub, tag_name, use_namespace):
    outfile = StringIO()
    outfile.write("""<?xml version="1.0" encoding="utf-8"?>\n""")
    namespacedef = 'xmlns="https://rogerth.at/api/1/MessageFlow.xsd"' if use_namespace else ''
    stub.export(outfile, 0, namespace_='', name_=tag_name, namespacedef_=namespacedef)
    return outfile.getvalue().decode('utf-8')

@returns(dict)
@arguments(message_flow_design=MessageFlowDesign)
def get_message_flow_design_context(message_flow_design):
    sub_flows = get_sub_message_flows(message_flow_design, {})
    subflow_dict = dict([(f.key(), f) for f in sub_flows])
    return subflow_dict

@returns(tuple)
@arguments(service_user=users.User, message_flow_design=MessageFlowDesign, translator=Translator, context=dict)
def message_flow_design_to_xml(service_user, message_flow_design, translator, context):
    if message_flow_design.definition:
        default_mfd = message_flow_design_to_message_flow_definition(message_flow_design, context)[0]
    else:
        # re-render XML (including translations)
        mf_defs = parse_message_flow_definition_set_xml(message_flow_design.xml.encode('utf-8'))
        default_language = get_service_profile(message_flow_design.user).defaultLanguage
        for mf_def in mf_defs.definition:
            if mf_def.language == default_language:
                default_mfd = mf_def
                break
        else:
            azzert(False, "Could not find service default language (%s) in mfd xml: %s"
                                % (message_flow_design.user.email(), message_flow_design.xml))
    return message_flow_definition_to_xml(service_user, default_mfd, translator, context)


@returns(unicode)
@arguments(default_language=unicode, default_mfd=MessageFlowDefinition)
def _message_flow_defintion_object_to_xml(default_language, default_mfd):
    default_mfd.language = default_language
    mfds = MessageFlowDefinitionSetSub()
    mfds.add_definition(default_mfd)
    return to_xml_unicode(mfds, 'messageFlowDefinitionSet', True)


@returns(tuple)
@arguments(service_user=users.User, default_mfd=MessageFlowDefinition, translator=Translator, context=dict)
def message_flow_definition_to_xml(service_user, default_mfd, translator, context):
    service_profile = get_service_profile(service_user)
    xml = _message_flow_defintion_object_to_xml(service_profile.defaultLanguage, default_mfd)

    mfd_supported_languages = [default_mfd.language]

    if translator:
        default_xml = to_xml_unicode(default_mfd, 'definition', False)

        xml, mfd_supported_languages = _translate_flow_xml(xml, default_mfd, default_xml, translator)

    return xml, mfd_supported_languages, service_profile.supportedLanguages

def _translate_flow_xml(mfd_set_xml, default_mfd, default_xml, translator):
    translation_dict = translator.translate_flow(default_xml, default_mfd.name)
    mfd_supported_languages = translation_dict.keys()

    del translation_dict[default_mfd.language]
    if translation_dict:
        definitions_xml = '\n'.join(translation_dict.itervalues())
        mfd_set_xml = mfd_set_xml.replace('</definition>', '</definition>\n%s' % definitions_xml)

    return mfd_set_xml, mfd_supported_languages

def _get_or_create_message_flow(service_user, mfd_name, design, language, multilanguage, mfd=None):
    azzert(db.is_in_transaction())
    if mfd is None:
        mfd = get_service_message_flow_design_by_name(service_user, mfd_name)

    if mfd:
        db.put_async(MessageFlowDesignBackup(parent=mfd, definition=mfd.definition, design_timestamp=mfd.design_timestamp))
    else:
        mfd = MessageFlowDesign(parent=parent_key(service_user), key_name=mfd_name)

    mfd.deleted = False
    mfd.definition = design
    mfd.name = mfd_name
    mfd.language = language
    mfd.design_timestamp = now()
    mfd.model_version = 2
    mfd.multilanguage = multilanguage
    return mfd

@returns(MessageFlowDesign)
@arguments(service_user=users.User, xml=unicode, multilanguage=bool, force=bool)
def save_message_flow_by_xml(service_user, xml, multilanguage=False, force=False):
    from rogerthat.bizz.service.mfr import InvalidMessageFlowXmlException, MessageFlowDesignValidationException, \
        InvalidMessageFlowLanguageException

    # xml must be a <str> to be able to be parsed
    if isinstance(xml, unicode):
        xml = xml.encode('utf-8')

    default_language = get_service_profile(service_user).defaultLanguage

    if 'messageFlowDefinitionSet' in xml:
        mf_defs = parse_message_flow_definition_set_xml(xml)
        for mf_def in mf_defs.definition:
            if mf_def.language == default_language:
                break
    else:
        mf_def = parse_message_flow_definition_xml(xml)

    mfd_name = mf_def.name
    if not mfd_name:
        raise InvalidMessageFlowXmlException()  # name is required in XSD

    if mf_def.language != default_language:
        raise InvalidMessageFlowLanguageException(default_language, mf_def.language)

    translator = get_translator(service_user, translation_types=ServiceTranslation.MFLOW_TYPES) if multilanguage else None

    def trans():
        # Check if the flow's xml has been modified. Do nothing if the XML is not modified.
        mfd = get_service_message_flow_design_by_name(service_user, mfd_name)
        if not force and mfd and mfd.xml == _message_flow_defintion_object_to_xml(default_language, mf_def):
            logging.info("The XML of MessageFlow %s hasn't changed. Doing nothing.", mfd.name)
            return mfd

        mfd = _get_or_create_message_flow(service_user, mfd_name, design=None, language=None,
                                          multilanguage=multilanguage, mfd=mfd)
        mfd.design = None
        mfd.language = None
        mfd.sub_flows = list()
        mfd.broken_sub_flows = list()

        try:
            validate_message_flow_definition(mf_def, service_user, True)

            mfd.status = MessageFlowDesign.STATUS_VALID
            mfd.validation_error = None
        except BusinessException, e:
            mfd.status = MessageFlowDesign.STATUS_BROKEN
            mfd.validation_error = e.fields['reason'] if isinstance(e, MessageFlowValidationException) else e.message

        if mfd.status != MessageFlowDesign.STATUS_VALID:
            logging.info("mfd.validation_error=%s\nmfd.status=%s\nmfd.user = %s\nmfd.name = %s" %
                         (mfd.validation_error, mfd.status, mfd.user, mfd.name))
            raise MessageFlowDesignValidationException(mfd)

        # Update XML
        if mfd.status == MessageFlowDesign.STATUS_VALID:
            mfd.xml, mfd_languages, service_languages = message_flow_definition_to_xml(service_user, mf_def, translator, None)
            update_i18n_warning(mfd, service_languages, mfd_languages)
            render_js_for_message_flow_designs([mfd], True)
        else:
            mfd.js_flow_definitions = JsFlowDefinitions()
            mfd.xml = None
            mfd.i18n_warning = None

        mfd.put()
        return mfd

    return db.run_in_transaction(trans)

@returns(MessageFlowDesign)
@arguments(service_user=users.User, mfd_name=unicode, design=unicode, language=unicode, force=bool, multilanguage=bool)
def save_message_flow(service_user, mfd_name, design, language, force, multilanguage=False):
    VALID = MessageFlowDesign.STATUS_VALID
    BROKEN = MessageFlowDesign.STATUS_BROKEN
    SUBFLOW_BROKEN = MessageFlowDesign.STATUS_SUBFLOW_BROKEN

    translator = get_translator(service_user, translation_types=ServiceTranslation.MFLOW_TYPES)

    def trace(flow, breadcrumbs, context):
        breadcrumbs.append(flow.key())
        for sub_flow_key in flow.sub_flows:
            if sub_flow_key in breadcrumbs:
                breadcrumbs.append(sub_flow_key)
                return True
            sub_flow = context.get(sub_flow_key)
            if not sub_flow:
                sub_flow = db.get(sub_flow_key)
                context[sub_flow_key] = sub_flow
            if trace(sub_flow, breadcrumbs, context):
                return True
        breadcrumbs.pop()

    def analyze(mfd, context, updates, ancestors):
        parent_keys_to_be_analyzed = set()
        try:
            # Parse without context
            mf_def, mfd.sub_flows = message_flow_design_to_message_flow_definition(mfd, None)

            # Check for circular dependencies
            if ancestors is not None:
                circle = list()
                if mfd.key() in mfd.sub_flows:
                    circle = [mfd.key(), mfd.key()]
                else:
                    for sf_key in mfd.sub_flows:
                        if sf_key in ancestors:
                            # Circle detected
                            trace(mfd, circle, context)
                            break

                if circle:
                    mfd.status = BROKEN
                    mfd.validation_error = "Circular dependency detected: %s " % (" > ".join([k.name() for k in circle]))
                    raise MessageFlowDesignLoopException(mfd)

            # Validate this message flow on its own
            validate_message_flow_definition(mf_def, service_user)

            mfd.status = VALID
            mfd.validation_error = None

        except BusinessException, e:
            mfd.status = BROKEN
            mfd.validation_error = e.fields['reason'] if isinstance(e, MessageFlowValidationException) else e.message
            mfd.sub_flows = list()
            mfd.broken_sub_flows = list()

        else:
            # We know that in isolation we are OK ourself
            sub_flows = [ context.get(sf_key, db.get(sf_key)) for sf_key in mfd.sub_flows ]
            mfd.broken_sub_flows = [ f.key() for f in sub_flows if f.status != VALID ]
            if mfd.broken_sub_flows:
                mfd.status = SUBFLOW_BROKEN

        if mfd.status != VALID and not force:
            from rogerthat.bizz.service.mfr import MessageFlowDesignValidationException
            logging.info("mfd.status = %s\nmfd.user = %s\nmfd.name = %s" % (mfd.status, mfd.user, mfd.name))
            raise MessageFlowDesignValidationException(mfd)

        # Possibly update our parents
        parent_flows = dict([(f.key(), f) for f in get_message_flow_designs_by_sub_flow_key(mfd.key())])
        for parent_key in parent_flows.iterkeys():
            parent = context[parent_key]
            if mfd.status == VALID:
                # Find SUBFLOW_BROKEN parents -> remove myself from broken_sub_flows if I'm in it + analyze
                if parent.status == SUBFLOW_BROKEN:
                    if mfd.key() in parent.broken_sub_flows:
                        parent.broken_sub_flows.remove(mfd.key())
                        if parent.broken_sub_flows:
                            updates[parent_key] = parent
                        else:
                            parent_keys_to_be_analyzed.add(parent_key)
            else:
                if parent.status == VALID:
                    parent_keys_to_be_analyzed.add(parent_key)
                elif parent.status == SUBFLOW_BROKEN:
                    if mfd.key() not in parent.broken_sub_flows:
                        parent.broken_sub_flows.append(mfd.key())
                        updates[parent_key] = parent


        # Update XML
        if mfd.status == MessageFlowDesign.STATUS_VALID:
            had_i18n_warning = bool(mfd.i18n_warning)

            render_xml_for_message_flow_design(mfd, translator, context)

            if had_i18n_warning != bool(mfd.i18n_warning):
                parent_keys_to_be_analyzed.update([k for k, v in parent_flows.iteritems() if v.multilanguage])
        else:
            mfd.js_flow_definitions = JsFlowDefinitions()
            mfd.xml = None
            mfd.i18n_warning = None

        updates[mfd.key()] = mfd
        return parent_keys_to_be_analyzed


    def txn():
        mfd = _get_or_create_message_flow(service_user, mfd_name, design, language, multilanguage)
        updates = dict()
        already_analyzed = set()

        # Get ancestors
        ancestors = dict(((f.key(), f) for f in get_super_message_flows(mfd)))
        context = dict(ancestors)
        context[mfd.key()] = mfd

        # Validate this message flow
        parent_keys_to_be_analyzed = analyze(mfd, context, updates, ancestors)
        already_analyzed.add(mfd.key())

        # Analyze parents
        counter = 0
        while parent_keys_to_be_analyzed:
            counter += 1
            if counter > 100:
                mfd.status = BROKEN
                mfd.validation_error = "Includes of sub message flows of more than 100 levels deep are not allowed"
                mfd.put()
                raise MessageFlowDesignLevelTooDeepException(mfd)
            new_parent_keys_to_be_analyzed = set()
            for parent_mfd_key in parent_keys_to_be_analyzed:
                new_parent_keys_to_be_analyzed.update(analyze(context[parent_mfd_key], context, updates, None))
                already_analyzed.add(parent_mfd_key)
            parent_keys_to_be_analyzed = new_parent_keys_to_be_analyzed

        for ancestor in ancestors.itervalues():
            if ancestor.status == VALID and ancestor.key() not in already_analyzed:
                # Ancestor was valid before and it's status did not change
                render_xml_for_message_flow_design(ancestor, translator, context)
                updates[ancestor.key()] = ancestor

        render_js_for_message_flow_designs(updates.values())

        db.put(updates.values())
        return mfd

    if db.is_in_transaction():
        result = txn()
    else:
        xg_on = db.create_transaction_options(xg=True)
        result = db.run_in_transaction_options(xg_on, txn)
    channel.send_message(service_user, u'rogerthat.mfd.changes')
    return result

def parse_message_flow_definition_set_xml(xml):
    from rogerthat.bizz.service.mfr import InvalidMessageFlowXmlException
    mf_defs = MessageFlowDefinitionSetSub.factory()
    try:
        azzert(isinstance(xml, str))
        mf_defs.build(parsexml_(StringIO(xml)).getroot())
    except:
        logging.debug("Could not parse XML:\n%s" % xml)
        logging.debug("Stacktrace", exc_info=1)
        raise InvalidMessageFlowXmlException()
    if not mf_defs.definition:  # mf_defs is probably empty because of bad XML
        logging.debug("Invalid MFD XML: %s" % xml)
        raise InvalidMessageFlowXmlException()
    return mf_defs

def parse_message_flow_definition_xml(xml):
    from rogerthat.bizz.service.mfr import InvalidMessageFlowXmlException
    mf_def = MessageFlowDefinitionSub.factory()
    try:
        azzert(isinstance(xml, str))
        mf_def.build(parsexml_(StringIO(xml)).getroot())
    except:
        logging.debug("Could not parse XML:\n%s" % xml)
        logging.debug("Stacktrace", exc_info=1)
        raise InvalidMessageFlowXmlException()
    if mf_def.name is None:  # mf_def is probably empty because of bad XML
        logging.debug("Invalid MFD XML: %s" % xml)
        raise InvalidMessageFlowXmlException()
    return mf_def

@returns(NoneType)
@arguments(mfd=MessageFlowDesign, translator=Translator, context=dict)
def render_xml_for_message_flow_design(mfd, translator, context):
    '''Render flow XML and translate'''
    logging.debug("Rendering XML for message flow '%s' of %s", mfd.name, mfd.user.email())
    mfd.xml, mfd_languages, service_languages = message_flow_design_to_xml(mfd.user, mfd, translator, context)
    update_i18n_warning(mfd, service_languages, mfd_languages)

def update_i18n_warning(mfd, service_languages, mfd_languages):
    if mfd.multilanguage and not set(service_languages).issubset(set(mfd_languages)):
        missing_languages = sorted([lang for lang in service_languages if lang not in mfd_languages])
        mfd.i18n_warning = "Missing languages: %s" % (', '.join(missing_languages))
    else:
        mfd.i18n_warning = None

@returns(set)
@arguments(mfds=[MessageFlowDesign], notify_friends=bool)
def render_js_for_message_flow_designs(mfds, notify_friends=True):
    changed_languages = set()

    mfds_with_xml = [ mfd for mfd in mfds if mfd.xml ]

    if mfds_with_xml:
        service_menu_items = get_service_menu_items(add_slash_default(mfds_with_xml[0].user))
        static_flow_keys = [ smi.staticFlowKey for smi in service_menu_items if smi.staticFlowKey ]

        for mfd in mfds_with_xml:
            js_flow_definition_dict = generate_js_flow(mfd.user, mfd.xml)

            referenced_by_smi = str(mfd.key()) in static_flow_keys
            old_js_flow_definitions = mfd.js_flow_definitions

            mfd.js_flow_definitions = JsFlowDefinitions()
            for language, (flow_definition, brandings, attachments) in js_flow_definition_dict.iteritems():
                new_jfd = JsFlowDefinition()
                new_jfd.language = language
                new_jfd.definition = compress_js_flow_definition(flow_definition)
                new_jfd.hash_ = unicode(md5_hex(new_jfd.definition))
                new_jfd.brandings = brandings
                new_jfd.attachments = attachments
                mfd.js_flow_definitions.add(new_jfd)

                if referenced_by_smi:
                    if old_js_flow_definitions:
                        old_jfd = old_js_flow_definitions.get_by_language(language)

                        if not old_jfd or old_jfd.hash_ != new_jfd.hash_:
                            changed_languages.add(language)
                    else:
                        changed_languages.add(language)

            if referenced_by_smi and old_js_flow_definitions:
                for old_jfd in old_js_flow_definitions.values():
                    if old_jfd.language not in js_flow_definition_dict:
                        changed_languages.add(old_jfd.language)

    if notify_friends and changed_languages:
        # TODO: only notify friends with changed language
        if db.is_in_transaction():
            service_profile_or_user = get_service_profile(mfds[0].user, False)
        else:
            service_profile_or_user = mfds[0].user
        from rogerthat.bizz.job.update_friends import schedule_update_all_friends_of_service_user
        schedule_update_all_friends_of_service_user(service_profile_or_user,
                                                    bump_service_version=True,
                                                    clear_broadcast_settings_cache=False)

    return changed_languages

@returns(unicode)
@arguments(flow_definition=unicode)
def compress_js_flow_definition(flow_definition):
    return unicode(base64.b64encode(zlib.compress(flow_definition.encode('utf-8'))))


@returns(bool)
@arguments(service_user=users.User, message_flow_design=MessageFlowDesign)
def delete_message_flow(service_user, message_flow_design):
    if not message_flow_design:
        return False

    from rogerthat.bizz.service.mfr import MessageFlowDesignInUseException

    azzert(message_flow_design.user == service_user)
    flows_using_this_flow = [ k.name() for k in get_message_flow_design_keys_by_sub_flow_key(message_flow_design.key()) ]
    if len(flows_using_this_flow) > 0:
        s = 's' if len(flows_using_this_flow) > 1 else ''
        flows = ', '.join(flows_using_this_flow)
        raise MessageFlowDesignInUseException("This message flow is used in the following flow%s: %s" % (s, flows))

    if is_message_flow_used_by_menu_item(message_flow_design):
        raise MessageFlowDesignInUseException("This message flow is used by one or more menu items")

    if is_message_flow_used_by_qr_code(message_flow_design):
        raise MessageFlowDesignInUseException("This message flow is used by one or more QR codes")

    message_flow_design.deleted = True
    message_flow_design.put()
    channel.send_message(service_user, u'rogerthat.mfd.changes')
    return True


@returns(NoneType)
@arguments(service_user=users.User, mfd_name=unicode)
def delete_message_flow_by_name(service_user, mfd_name):
    bizz_check(mfd_name, "Name must not be empty")
    delete_message_flow(service_user, get_service_message_flow_design_by_name(service_user, mfd_name))


@returns(MessageFlowDesign)
@arguments(service_user=users.User, mfd_key_or_name=unicode)
def get_message_flow_by_key_or_name(service_user, mfd_key_or_name):
    try:
        mfd = MessageFlowDesign.get(mfd_key_or_name)
    except:
        mfd = None
    if not mfd:
        mfd = get_service_message_flow_design_by_name(service_user, mfd_key_or_name)
    return mfd

def _find_orphans(vertices, edges, sinks):
    ok = sinks.copy()
    added = len(ok)
    while added > 0:
        ok_size = len(ok)
        for (b, e) in edges:
            if e in ok and (not b in ok):
                ok.add(b)
        added = len(ok) - ok_size
    orphans = vertices.difference(ok)
    return orphans

def create_json_id(message_flow_design, step_prefix, id_):
    return create_b64id_from_json_dict({"id": step_prefix + id_,
                                        "mfd": str(message_flow_design.key()),
                                        "lang": get_service_profile(message_flow_design.user).defaultLanguage})

def create_b64id_from_json_dict(json_dict):
    return "base64:" + base64.b64encode(json.dumps(json_dict))
