# -*- coding: utf-8 -*-
import test

import os

from rogerthat.bizz.service.mfd.mfd_javascript import _render_flow_definitions, _get_js_mfr_code

WIDGETS_FLOW_XML = u"""<?xml version="1.0" encoding="utf-8"?>
<messageFlowDefinitionSet xmlns="https://rogerth.at/api/1/MessageFlow.xsd">
    <definition name="A" language="en" startReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9hXzEifQ==">
        <end id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAiZW5kXzEifQ==" waitForFollowUpMessage="false"/>
        <message id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9hXzEifQ==" alertIntervalType="NONE" alertType="BEEP" allowDismiss="true" vibrate="false" dismissReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgMCJ9" autoLock="true">
            <content>a_1</content>
        </message>
        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgMCJ9" alertIntervalType="NONE" alertType="BEEP" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgMSJ9" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgMSJ9">
            <content>élève 0</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextLineWidget" maxChars="50"/>
            </form>
        </formMessage>
        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgMSJ9" alertIntervalType="NONE" alertType="BEEP" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgMiJ9" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgMiJ9">
            <content>élève 1</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextBlockWidget" maxChars="50"/>
            </form>
        </formMessage>
        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgMiJ9" alertIntervalType="NONE" alertType="BEEP" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgMyJ9" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgMyJ9">
            <content>élève 2</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextAutocompleteWidget" maxChars="50">
                    <suggestion value="abc"/>
                    <suggestion value="def"/>
                </widget>
            </form>
        </formMessage>
        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgMyJ9" alertIntervalType="NONE" alertType="BEEP" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgNCJ9" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgNCJ9">
            <content>élève 3</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="SelectSingleWidget">
                    <choice value="a" label="A"/>
                    <choice value="b" label="B"/>
                    <choice value="c" label="C"/>
                    <choice value="d" label="D"/>
                </widget>
            </form>
        </formMessage>
        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgNCJ9" alertIntervalType="NONE" alertType="BEEP" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgNSJ9" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgNSJ9">
            <content>élève 4</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="SelectMultiWidget">
                    <choice value="a" label="A"/>
                    <choice value="b" label="B"/>
                    <choice value="c" label="C"/>
                    <choice value="d" label="D"/>
                    <value value="a"/>
                    <value value="b"/>
                    <value value="c"/>
                </widget>
            </form>
        </formMessage>
        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgNSJ9" alertIntervalType="NONE" alertType="BEEP" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgNiJ9" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgNiJ9">
            <content>élève 5</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="SelectDateWidget" minuteInterval="15" mode="date_time"/>
            </form>
        </formMessage>
        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgNiJ9" alertIntervalType="NONE" alertType="BEEP" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgNyJ9" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgNyJ9">
            <content>élève 6</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="SliderWidget" max="10.000000" step="1.000000" precision="0" min="0.000000" value="0.000000"/>
            </form>
        </formMessage>
        <formMessage id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAibWVzc2FnZV9cdTAwZTlsXHUwMGU4dmUgNyJ9" alertIntervalType="NONE" alertType="BEEP" positiveReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAiZmx1c2hfMSJ9" vibrate="false" autoLock="true" negativeReference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAiZmx1c2hfMSJ9">
            <content>élève 7</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit" negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="RangeSliderWidget" max="10.000000" step="1.000000" precision="0" min="0.000000" lowValue="0.000000" highValue="10.000000"/>
            </form>
        </formMessage>
        <resultsFlush id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAiZmx1c2hfMSJ9" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAiZmx1c2hfMiJ9"/>
        <resultsFlush id="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAiZmx1c2hfMiJ9" reference="base64:eyJsYW5nIjogImVuIiwgIm1mZCI6ICJhZzF0YjJKcFkyRm5aV05zYjNWa2NqSUxFZ3B0WXkxMGNtRmphMlZ5SWdwek1VQm1iMjh1WTI5dERBc1NFVTFsYzNOaFoyVkdiRzkzUkdWemFXZHVJZ0ZCREEiLCAiaWQiOiAiZW5kXzEifQ=="/>
    </definition>
</messageFlowDefinitionSet>
"""  # This is the xml of message flow created in mfd_js.py in function testJSFlowDef

FLOW_CODE_XML = u"""<?xml version="1.0" encoding="utf-8"?>
<messageFlowDefinitionSet xmlns="https://rogerth.at/api/1/MessageFlow.xsd">
    <definition name="messages" language="en"
                startReference="start_1">
        <end id="end_1"
             waitForFollowUpMessage="false"/>
        <message
                id="start_1"
                alertIntervalType="NONE" alertType="SILENT" allowDismiss="true" vibrate="false"
                dismissReference="message_text_line_2"
                autoLock="true">
            <content>message 1\n\nmessage 1</content>
        </message>
        <message
                id="message_4"
                alertIntervalType="NONE" alertType="SILENT" allowDismiss="true" vibrate="false"
                dismissReference="end_1"
                autoLock="true">
            <content>message 4\n\nmessage 4</content>
        </message>
        <formMessage
                id="message_text_line_2"
                alertIntervalType="NONE" alertType="SILENT"
                positiveReference="flow_code_1"
                vibrate="false" autoLock="true"
                negativeReference="flow_code_1">
            <content>text line 2\n\ntext line 2</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit"
                  negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextLineWidget" maxChars="50"/>
            </form>
        </formMessage>
        <formMessage
                id="message_text_line_6"
                alertIntervalType="NONE" alertType="SILENT"
                positiveReference="flow_code_2"
                vibrate="false" autoLock="true"
                negativeReference="flow_code_2">
            <content>text line 6\n\ntext line 6</content>
            <form positiveButtonConfirmation="" negativeButtonCaption="Cancel" positiveButtonCaption="Submit"
                  negativeButtonConfirmation="">
                <widget xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="TextLineWidget" maxChars="50"/>
            </form>
        </formMessage>
        <flowCode
                id="flow_code_1"
                exceptionReference="message_4">
            <outlet reference="message_text_line_6"
                    name="default" value="default"/>
            <javascriptCode>var run = function (rogerthat, messageFlowRun) {
                /*while(true){};*/
                var flowId = messageFlowRun[&apos;flow_id&apos;];
                var steps = messageFlowRun[&apos;steps&apos;];
                var user = rogerthat[&apos;user&apos;];
                var service = rogerthat[&apos;service&apos;];
                var system = rogerthat[&apos;system&apos;];

                rogerthat.user.data.__rt__disabledBroadcastTypes = ['Events', 'Nieuws', 'Test'];
                rogerthat.user.put();

                var nextStepResult = {};
                nextStepResult.outlet = null;
                nextStepResult.defaultValue = null;

                if (steps[steps.length - 1][&apos;form_result&apos;][&quot;result&quot;][&apos;value&apos;] == &quot;1&quot;) {
                    nextStepResult.outlet = &quot;default&quot;;
                    return nextStepResult;
                }
                nextStepResult.outlet = &quot;exception&quot;;
                return nextStepResult;
            };</javascriptCode>
        </flowCode>
        <flowCode
                id="flow_code_2"
                exceptionReference="message_text_line_2">
            <outlet reference="message_4"
                    name="default" value="default"/>
            <javascriptCode>var run = function (rogerthat, messageFlowRun) {
                /* test */
                var flowId = messageFlowRun[&apos;flow_id&apos;];
                var steps = messageFlowRun[&apos;steps&apos;];
                var user = rogerthat[&apos;user&apos;];
                var service = rogerthat[&apos;service&apos;];
                var system = rogerthat[&apos;system&apos;];

                var nextStepResult = {};
                nextStepResult.outlet = null;
                nextStepResult.defaultValue = null;

                if (steps[steps.length - 1][&apos;form_result&apos;][&quot;result&quot;][&apos;value&apos;] == &quot;1&quot;) {
                    nextStepResult.outlet = &quot;default&quot;;
                    return nextStepResult;
                }
                nextStepResult.outlet = &quot;exception&quot;;
                return nextStepResult;
            };</javascriptCode>
        </flowCode>
    </definition>
</messageFlowDefinitionSet>"""
FLOW_DEFINITIONS = {
    'widgets_flow.js': lambda: (_render_flow_definitions(None, WIDGETS_FLOW_XML).values()[0][0], 'JsMfrWidgetsTest'),
    'flow_code.js': lambda: (_render_flow_definitions(None, FLOW_CODE_XML).values()[0][0], 'JsMfrFlowCodeTest'),
}

dir_name = os.path.dirname(__file__)

directory = os.path.join(dir_name, 'gen')
if not os.path.exists(directory):
    os.makedirs(directory)

for test_file in os.listdir(dir_name):
    if not test_file.endswith('.js') or test_file not in FLOW_DEFINITIONS:
        continue

    flow_def, unit_test_class = FLOW_DEFINITIONS[test_file]()
    flow_def = flow_def.replace('flowDefinition =', '%s.prototype.flowDefinition =' % unit_test_class)

    file_name = os.path.join(dir_name, 'gen', "flow_def_%s" % test_file)
    with open(file_name, 'w+') as f:
        f.write(flow_def.encode('utf-8'))
        print 'Generated %s' % file_name

    with open(test_file, 'r') as f:
        minified_full_code = _get_js_mfr_code(f.read() + '\n' + flow_def).replace(unit_test_class, "Minified" + unit_test_class)

    mini_file_name = os.path.join(dir_name, 'gen', "minified_%s" % test_file)
    with open(mini_file_name, 'w+') as f:
        f.write(minified_full_code.encode('utf-8'))
        print 'Generated %s' % mini_file_name
