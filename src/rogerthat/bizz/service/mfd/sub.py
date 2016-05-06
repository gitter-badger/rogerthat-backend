#!/usr/bin/env python
# @@xxx_skip_license@@
#
# @PydevCodeAnalysisIgnore
# @PydevCodeAnalysisIgnore
# Generated Fri Feb  5 15:04:13 2016 by generateDS.py version 2.7a.
#

import sys

from rogerthat.bizz.service.mfd import gen as supermod

etree_ = None
Verbose_import_ = False
(XMLParser_import_none, XMLParser_import_lxml,
    XMLParser_import_elementtree
    ) = range(3)
XMLParser_import_library = None
try:
    # lxml
    from lxml import etree as etree_
    XMLParser_import_library = XMLParser_import_lxml
    if Verbose_import_:
        print("running with lxml.etree")
except ImportError:
    try:
        # cElementTree from Python 2.5+
        import xml.etree.cElementTree as etree_
        XMLParser_import_library = XMLParser_import_elementtree
        if Verbose_import_:
            print("running with cElementTree on Python 2.5+")
    except ImportError:
        try:
            # ElementTree from Python 2.5+
            import xml.etree.ElementTree as etree_
            XMLParser_import_library = XMLParser_import_elementtree
            if Verbose_import_:
                print("running with ElementTree on Python 2.5+")
        except ImportError:
            try:
                # normal cElementTree install
                import cElementTree as etree_
                XMLParser_import_library = XMLParser_import_elementtree
                if Verbose_import_:
                    print("running with cElementTree")
            except ImportError:
                try:
                    # normal ElementTree install
                    import elementtree.ElementTree as etree_
                    XMLParser_import_library = XMLParser_import_elementtree
                    if Verbose_import_:
                        print("running with ElementTree")
                except ImportError:
                    raise ImportError("Failed to import ElementTree from any known place")

def parsexml_(*args, **kwargs):
    if (XMLParser_import_library == XMLParser_import_lxml and
        'parser' not in kwargs):
        # Use the lxml ElementTree compatible parser so that, e.g.,
        #   we ignore comments.
        kwargs['parser'] = etree_.ETCompatXMLParser()
    doc = etree_.parse(*args, **kwargs)
    return doc

#
# Globals
#

ExternalEncoding = 'utf-8'

#
# Data representation classes
#

class AttachmentSub(supermod.Attachment):
    def __init__(self, url=None, contentType=None, name=None, size=None):
        super(AttachmentSub, self).__init__(url, contentType, name, size,)
supermod.Attachment.subclass = AttachmentSub
# end class AttachmentSub


class FlowElementSub(supermod.FlowElement):
    def __init__(self, id=None, extensiontype_=None):
        super(FlowElementSub, self).__init__(id, extensiontype_,)
supermod.FlowElement.subclass = FlowElementSub
# end class FlowElementSub


class AnswerSub(supermod.Answer):
    def __init__(self, action=None, caption=None, id=None, reference=None):
        super(AnswerSub, self).__init__(action, caption, id, reference,)
supermod.Answer.subclass = AnswerSub
# end class AnswerSub


class MessageSub(supermod.Message):
    def __init__(self, id=None, alertIntervalType=None, alertType=None, brandingKey=None, allowDismiss=None, vibrate=None, dismissReference=None, autoLock=None, content=None, answer=None, attachment=None):
        super(MessageSub, self).__init__(id, alertIntervalType, alertType, brandingKey, allowDismiss, vibrate, dismissReference, autoLock, content, answer, attachment,)
supermod.Message.subclass = MessageSub
# end class MessageSub


class ResultsFlushSub(supermod.ResultsFlush):
    def __init__(self, id=None, reference=None):
        super(ResultsFlushSub, self).__init__(id, reference,)
supermod.ResultsFlush.subclass = ResultsFlushSub
# end class ResultsFlushSub


class ResultsEmailSub(supermod.ResultsEmail):
    def __init__(self, id=None, reference=None, emailAdmins=None, email=None):
        super(ResultsEmailSub, self).__init__(id, reference, emailAdmins, email,)
supermod.ResultsEmail.subclass = ResultsEmailSub
# end class ResultsEmailSub


class FlowCodeSub(supermod.FlowCode):
    def __init__(self, id=None, exceptionReference=None, outlet=None, javascriptCode=None):
        super(FlowCodeSub, self).__init__(id, exceptionReference, outlet, javascriptCode,)
supermod.FlowCode.subclass = FlowCodeSub
# end class FlowCodeSub


class WidgetSub(supermod.Widget):
    def __init__(self, extensiontype_=None):
        super(WidgetSub, self).__init__(extensiontype_,)
supermod.Widget.subclass = WidgetSub
# end class WidgetSub


class BaseSliderWidgetSub(supermod.BaseSliderWidget):
    def __init__(self, max=None, step=None, precision=None, unit=None, min=None, extensiontype_=None):
        super(BaseSliderWidgetSub, self).__init__(max, step, precision, unit, min, extensiontype_,)
supermod.BaseSliderWidget.subclass = BaseSliderWidgetSub
# end class BaseSliderWidgetSub


class SliderWidgetSub(supermod.SliderWidget):
    def __init__(self, max=None, step=None, precision=None, unit=None, min=None, value=None):
        super(SliderWidgetSub, self).__init__(max, step, precision, unit, min, value,)
supermod.SliderWidget.subclass = SliderWidgetSub
# end class SliderWidgetSub


class RangeSliderWidgetSub(supermod.RangeSliderWidget):
    def __init__(self, max=None, step=None, precision=None, unit=None, min=None, lowValue=None, highValue=None):
        super(RangeSliderWidgetSub, self).__init__(max, step, precision, unit, min, lowValue, highValue,)
supermod.RangeSliderWidget.subclass = RangeSliderWidgetSub
# end class RangeSliderWidgetSub


class PhotoUploadWidgetSub(supermod.PhotoUploadWidget):
    def __init__(self, ratio=None, camera=None, quality=None, gallery=None):
        super(PhotoUploadWidgetSub, self).__init__(ratio, camera, quality, gallery,)
supermod.PhotoUploadWidget.subclass = PhotoUploadWidgetSub
# end class PhotoUploadWidgetSub


class GPSLocationWidgetSub(supermod.GPSLocationWidget):
    def __init__(self, gps=None):
        super(GPSLocationWidgetSub, self).__init__(gps,)
supermod.GPSLocationWidget.subclass = GPSLocationWidgetSub
# end class GPSLocationWidgetSub


class TextWidgetSub(supermod.TextWidget):
    def __init__(self, maxChars=None, placeholder=None, value=None, extensiontype_=None):
        super(TextWidgetSub, self).__init__(maxChars, placeholder, value, extensiontype_,)
supermod.TextWidget.subclass = TextWidgetSub
# end class TextWidgetSub


class TextLineWidgetSub(supermod.TextLineWidget):
    def __init__(self, maxChars=None, placeholder=None, value=None):
        super(TextLineWidgetSub, self).__init__(maxChars, placeholder, value,)
supermod.TextLineWidget.subclass = TextLineWidgetSub
# end class TextLineWidgetSub


class TextBlockWidgetSub(supermod.TextBlockWidget):
    def __init__(self, maxChars=None, placeholder=None, value=None):
        super(TextBlockWidgetSub, self).__init__(maxChars, placeholder, value,)
supermod.TextBlockWidget.subclass = TextBlockWidgetSub
# end class TextBlockWidgetSub


class ValueSub(supermod.Value):
    def __init__(self, value=None, extensiontype_=None):
        super(ValueSub, self).__init__(value, extensiontype_,)
supermod.Value.subclass = ValueSub
# end class ValueSub


class FloatValueSub(supermod.FloatValue):
    def __init__(self, value=None):
        super(FloatValueSub, self).__init__(value,)
supermod.FloatValue.subclass = FloatValueSub
# end class FloatValueSub


class AdvancedOrderCategorySub(supermod.AdvancedOrderCategory):
    def __init__(self, id=None, name=None, item=None):
        super(AdvancedOrderCategorySub, self).__init__(id, name, item,)
supermod.AdvancedOrderCategory.subclass = AdvancedOrderCategorySub
# end class AdvancedOrderCategorySub


class AdvancedOrderItemSub(supermod.AdvancedOrderItem):
    def __init__(self, stepUnit=None, description=None, stepUnitConversion=None, imageUrl=None, value=None, hasPrice=True, step=None, unitPrice=None, id=None, unit=None, name=None):
        super(AdvancedOrderItemSub, self).__init__(stepUnit, description, stepUnitConversion, imageUrl, value, hasPrice, step, unitPrice, id, unit, name,)
supermod.AdvancedOrderItem.subclass = AdvancedOrderItemSub
# end class AdvancedOrderItemSub


class TextAutocompleteWidgetSub(supermod.TextAutocompleteWidget):
    def __init__(self, maxChars=None, placeholder=None, value=None, suggestion=None):
        super(TextAutocompleteWidgetSub, self).__init__(maxChars, placeholder, value, suggestion,)
supermod.TextAutocompleteWidget.subclass = TextAutocompleteWidgetSub
# end class TextAutocompleteWidgetSub


class ChoiceSub(supermod.Choice):
    def __init__(self, value=None, label=None):
        super(ChoiceSub, self).__init__(value, label,)
supermod.Choice.subclass = ChoiceSub
# end class ChoiceSub


class SelectWidgetSub(supermod.SelectWidget):
    def __init__(self, choice=None, extensiontype_=None):
        super(SelectWidgetSub, self).__init__(choice, extensiontype_,)
supermod.SelectWidget.subclass = SelectWidgetSub
# end class SelectWidgetSub


class SelectSingleWidgetSub(supermod.SelectSingleWidget):
    def __init__(self, choice=None, value=None):
        super(SelectSingleWidgetSub, self).__init__(choice, value,)
supermod.SelectSingleWidget.subclass = SelectSingleWidgetSub
# end class SelectSingleWidgetSub


class SelectMultiWidgetSub(supermod.SelectMultiWidget):
    def __init__(self, choice=None, value=None):
        super(SelectMultiWidgetSub, self).__init__(choice, value,)
supermod.SelectMultiWidget.subclass = SelectMultiWidgetSub
# end class SelectMultiWidgetSub


class SelectDateWidgetSub(supermod.SelectDateWidget):
    def __init__(self, minuteInterval=None, maxDate=None, mode=None, date=None, unit=None, minDate=None):
        super(SelectDateWidgetSub, self).__init__(minuteInterval, maxDate, mode, date, unit, minDate,)
supermod.SelectDateWidget.subclass = SelectDateWidgetSub
# end class SelectDateWidgetSub


class MyDigiPassWidgetSub(supermod.MyDigiPassWidget):
    def __init__(self, scope=None):
        super(MyDigiPassWidgetSub, self).__init__(scope,)
supermod.MyDigiPassWidget.subclass = MyDigiPassWidgetSub
# end class MyDigiPassWidgetSub


class AdvancedOrderWidgetSub(supermod.AdvancedOrderWidget):
    def __init__(self, currency=None, leapTime=None, category=None):
        super(AdvancedOrderWidgetSub, self).__init__(currency, leapTime, category,)
supermod.AdvancedOrderWidget.subclass = AdvancedOrderWidgetSub
# end class AdvancedOrderWidgetSub


class FormSub(supermod.Form):
    def __init__(self, positiveButtonConfirmation=None, negativeButtonCaption=None, positiveButtonCaption=None, negativeButtonConfirmation=None, widget=None, javascriptValidation=None):
        super(FormSub, self).__init__(positiveButtonConfirmation, negativeButtonCaption, positiveButtonCaption, negativeButtonConfirmation, widget, javascriptValidation,)
supermod.Form.subclass = FormSub
# end class FormSub


class FormMessageSub(supermod.FormMessage):
    def __init__(self, id=None, alertIntervalType=None, alertType=None, brandingKey=None, positiveReference=None, vibrate=None, member=None, autoLock=None, negativeReference=None, content=None, form=None, attachment=None):
        super(FormMessageSub, self).__init__(id, alertIntervalType, alertType, brandingKey, positiveReference, vibrate, member, autoLock, negativeReference, content, form, attachment,)
supermod.FormMessage.subclass = FormMessageSub
# end class FormMessageSub


class OutletSub(supermod.Outlet):
    def __init__(self, reference=None, name=None, value=None):
        super(OutletSub, self).__init__(reference, name, value,)
supermod.Outlet.subclass = OutletSub
# end class OutletSub


class EndSub(supermod.End):
    def __init__(self, id=None, waitForFollowUpMessage=False):
        super(EndSub, self).__init__(id, waitForFollowUpMessage,)
supermod.End.subclass = EndSub
# end class EndSub


class MessageFlowDefinitionSub(supermod.MessageFlowDefinition):
    def __init__(self, name=None, language=None, startReference=None, end=None, message=None, formMessage=None, resultsFlush=None, resultsEmail=None, flowCode=None):
        super(MessageFlowDefinitionSub, self).__init__(name, language, startReference, end, message, formMessage, resultsFlush, resultsEmail, flowCode,)
supermod.MessageFlowDefinition.subclass = MessageFlowDefinitionSub
# end class MessageFlowDefinitionSub


class MessageFlowDefinitionSetSub(supermod.MessageFlowDefinitionSet):
    def __init__(self, definition=None):
        super(MessageFlowDefinitionSetSub, self).__init__(definition,)
supermod.MessageFlowDefinitionSet.subclass = MessageFlowDefinitionSetSub
# end class MessageFlowDefinitionSetSub


class StepSub(supermod.Step):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, extensiontype_=None):
        super(StepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, extensiontype_,)
supermod.Step.subclass = StepSub
# end class StepSub


class BaseMessageStepSub(supermod.BaseMessageStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, extensiontype_=None):
        super(BaseMessageStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, extensiontype_,)
supermod.BaseMessageStep.subclass = BaseMessageStepSub
# end class BaseMessageStepSub


class MessageStepSub(supermod.MessageStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, answer=None):
        super(MessageStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, answer,)
supermod.MessageStep.subclass = MessageStepSub
# end class MessageStepSub


class WidgetStepSub(supermod.WidgetStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, formButton=None, displayValue=None, extensiontype_=None):
        super(WidgetStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, formButton, displayValue, extensiontype_,)
supermod.WidgetStep.subclass = WidgetStepSub
# end class WidgetStepSub


class TextWidgetStepSub(supermod.TextWidgetStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, formButton=None, displayValue=None, value=None):
        super(TextWidgetStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, formButton, displayValue, value,)
supermod.TextWidgetStep.subclass = TextWidgetStepSub
# end class TextWidgetStepSub


class SliderWidgetStepSub(supermod.SliderWidgetStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, formButton=None, displayValue=None, value=None):
        super(SliderWidgetStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, formButton, displayValue, value,)
supermod.SliderWidgetStep.subclass = SliderWidgetStepSub
# end class SliderWidgetStepSub


class RangeSliderWidgetStepSub(supermod.RangeSliderWidgetStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, formButton=None, displayValue=None, value=None):
        super(RangeSliderWidgetStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, formButton, displayValue, value,)
supermod.RangeSliderWidgetStep.subclass = RangeSliderWidgetStepSub
# end class RangeSliderWidgetStepSub


class PhotoUploadWidgetStepSub(supermod.PhotoUploadWidgetStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, formButton=None, displayValue=None, value=None):
        super(PhotoUploadWidgetStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, formButton, displayValue, value,)
supermod.PhotoUploadWidgetStep.subclass = PhotoUploadWidgetStepSub
# end class PhotoUploadWidgetStepSub


class GPSLocationWidgetStepSub(supermod.GPSLocationWidgetStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, formButton=None, displayValue=None, timestamp=None, altitude=None, longitude=None, horizontalAccuracy=None, latitude=None, verticalAccuracy=None):
        super(GPSLocationWidgetStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, formButton, displayValue, timestamp, altitude, longitude, horizontalAccuracy, latitude, verticalAccuracy,)
supermod.GPSLocationWidgetStep.subclass = GPSLocationWidgetStepSub
# end class GPSLocationWidgetStepSub


class MyDigiPassEidProfileSub(supermod.MyDigiPassEidProfile):
    def __init__(self, locationOfBirth=None, validityEndsAt=None, firstName=None, chipNumber=None, lastName=None, nobleCondition=None, validityBeginsAt=None, dateOfBirth=None, cardNumber=None, firstName3=None, gender=None, nationality=None, createdAt=None, issuingMunicipality=None):
        super(MyDigiPassEidProfileSub, self).__init__(locationOfBirth, validityEndsAt, firstName, chipNumber, lastName, nobleCondition, validityBeginsAt, dateOfBirth, cardNumber, firstName3, gender, nationality, createdAt, issuingMunicipality,)
supermod.MyDigiPassEidProfile.subclass = MyDigiPassEidProfileSub
# end class MyDigiPassEidProfileSub


class MyDigiPassEidAddressSub(supermod.MyDigiPassEidAddress):
    def __init__(self, municipality=None, streetAndNumber=None, zipCode=None):
        super(MyDigiPassEidAddressSub, self).__init__(municipality, streetAndNumber, zipCode,)
supermod.MyDigiPassEidAddress.subclass = MyDigiPassEidAddressSub
# end class MyDigiPassEidAddressSub


class MyDigiPassProfileSub(supermod.MyDigiPassProfile):
    def __init__(self, uuid=None, firstName=None, lastName=None, preferredLocale=None, updatedAt=None, bornOn=None):
        super(MyDigiPassProfileSub, self).__init__(uuid, firstName, lastName, preferredLocale, updatedAt, bornOn,)
supermod.MyDigiPassProfile.subclass = MyDigiPassProfileSub
# end class MyDigiPassProfileSub


class MyDigiPassAddressSub(supermod.MyDigiPassAddress):
    def __init__(self, city=None, zip=None, address1=None, address2=None, state=None, country=None):
        super(MyDigiPassAddressSub, self).__init__(city, zip, address1, address2, state, country,)
supermod.MyDigiPassAddress.subclass = MyDigiPassAddressSub
# end class MyDigiPassAddressSub


class MyDigiPassWidgetStepSub(supermod.MyDigiPassWidgetStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, formButton=None, displayValue=None, phone=None, email=None, eidPhoto=None, eidProfile=None, eidAddress=None, profile=None, address=None):
        super(MyDigiPassWidgetStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, formButton, displayValue, phone, email, eidPhoto, eidProfile, eidAddress, profile, address,)
supermod.MyDigiPassWidgetStep.subclass = MyDigiPassWidgetStepSub
# end class MyDigiPassWidgetStepSub


class SelectSingleWidgetStepSub(supermod.SelectSingleWidgetStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, formButton=None, displayValue=None, value=None):
        super(SelectSingleWidgetStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, formButton, displayValue, value,)
supermod.SelectSingleWidgetStep.subclass = SelectSingleWidgetStepSub
# end class SelectSingleWidgetStepSub


class SelectMultiWidgetStepSub(supermod.SelectMultiWidgetStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, formButton=None, displayValue=None, selection=None):
        super(SelectMultiWidgetStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, formButton, displayValue, selection,)
supermod.SelectMultiWidgetStep.subclass = SelectMultiWidgetStepSub
# end class SelectMultiWidgetStepSub


class SelectDateWidgetStepSub(supermod.SelectDateWidgetStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, formButton=None, displayValue=None, date=None):
        super(SelectDateWidgetStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, formButton, displayValue, date,)
supermod.SelectDateWidgetStep.subclass = SelectDateWidgetStepSub
# end class SelectDateWidgetStepSub


class AdvancedOrderWidgetStepSub(supermod.AdvancedOrderWidgetStep):
    def __init__(self, definition=None, previousStep=None, button=None, nextStep=None, message=None, creationTimestamp=None, id=None, receivedTimestamp=None, acknowledgedTimestamp=None, formButton=None, displayValue=None, currency=None, category=None):
        super(AdvancedOrderWidgetStepSub, self).__init__(definition, previousStep, button, nextStep, message, creationTimestamp, id, receivedTimestamp, acknowledgedTimestamp, formButton, displayValue, currency, category,)
supermod.AdvancedOrderWidgetStep.subclass = AdvancedOrderWidgetStepSub
# end class AdvancedOrderWidgetStepSub


class MemberRunSub(supermod.MemberRun):
    def __init__(self, status=None, userData=None, endReference=None, name=None, language=None, avatarUrl=None, appId=None, email=None, step=None):
        super(MemberRunSub, self).__init__(status, userData, endReference, name, language, avatarUrl, appId, email, step,)
supermod.MemberRun.subclass = MemberRunSub
# end class MemberRunSub


class MessageFlowRunSub(supermod.MessageFlowRun):
    def __init__(self, serviceDisplayEmail=None, serviceData=None, serviceName=None, launchTimestamp=None, serviceEmail=None, definition=None, memberRun=None):
        super(MessageFlowRunSub, self).__init__(serviceDisplayEmail, serviceData, serviceName, launchTimestamp, serviceEmail, definition, memberRun,)
supermod.MessageFlowRun.subclass = MessageFlowRunSub
# end class MessageFlowRunSub


class contentTypeSub(supermod.contentType):
    def __init__(self, valueOf_=None):
        super(contentTypeSub, self).__init__(valueOf_,)
supermod.contentType.subclass = contentTypeSub
# end class contentTypeSub


class javascriptCodeTypeSub(supermod.javascriptCodeType):
    def __init__(self, valueOf_=None):
        super(javascriptCodeTypeSub, self).__init__(valueOf_,)
supermod.javascriptCodeType.subclass = javascriptCodeTypeSub
# end class javascriptCodeTypeSub


class contentType1Sub(supermod.contentType1):
    def __init__(self, valueOf_=None):
        super(contentType1Sub, self).__init__(valueOf_,)
supermod.contentType1.subclass = contentType1Sub
# end class contentType1Sub



def get_root_tag(node):
    tag = supermod.Tag_pattern_.match(node.tag).groups()[-1]
    rootClass = None
    if hasattr(supermod, tag):
        rootClass = getattr(supermod, tag)
    return tag, rootClass


def parse(inFilename):
    doc = parsexml_(inFilename)
    rootNode = doc.getroot()
    rootTag, rootClass = get_root_tag(rootNode)
    if rootClass is None:
        rootTag = 'Attachment'
        rootClass = supermod.Attachment
    rootObj = rootClass.factory()
    rootObj.build(rootNode)
    # Enable Python to collect the space used by the DOM.
    doc = None
    sys.stdout.write('<?xml version="1.0" ?>\n')
    rootObj.export(sys.stdout, 0, name_=rootTag,
        namespacedef_='')
    doc = None
    return rootObj


def parseString(inString):
    from StringIO import StringIO
    doc = parsexml_(StringIO(inString))
    rootNode = doc.getroot()
    rootTag, rootClass = get_root_tag(rootNode)
    if rootClass is None:
        rootTag = 'Attachment'
        rootClass = supermod.Attachment
    rootObj = rootClass.factory()
    rootObj.build(rootNode)
    # Enable Python to collect the space used by the DOM.
    doc = None
    sys.stdout.write('<?xml version="1.0" ?>\n')
    rootObj.export(sys.stdout, 0, name_=rootTag,
        namespacedef_='')
    return rootObj


def parseLiteral(inFilename):
    doc = parsexml_(inFilename)
    rootNode = doc.getroot()
    rootTag, rootClass = get_root_tag(rootNode)
    if rootClass is None:
        rootTag = 'Attachment'
        rootClass = supermod.Attachment
    rootObj = rootClass.factory()
    rootObj.build(rootNode)
    # Enable Python to collect the space used by the DOM.
    doc = None
    sys.stdout.write('#from ??? import *\n\n')
    sys.stdout.write('import ??? as model_\n\n')
    sys.stdout.write('rootObj = model_.Attachment(\n')
    rootObj.exportLiteral(sys.stdout, 0, name_="Attachment")
    sys.stdout.write(')\n')
    return rootObj


USAGE_TEXT = """
Usage: python ???.py <infilename>
"""

def usage():
    print USAGE_TEXT
    sys.exit(1)


def main():
    args = sys.argv[1:]
    if len(args) != 1:
        usage()
    infilename = args[0]
    root = parse(infilename)


if __name__ == '__main__':
    # import pdb; pdb.set_trace()
    main()


