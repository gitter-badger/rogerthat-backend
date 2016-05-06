/*
 * Copyright 2016 Mobicage NV
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * @@license_version:1.1@@
 */

console.log("Loading rogerthat.api-1.0.js");
var _createRogerthatApiLib = function() {
    var MAJOR_VERSION = 0;
    var MINOR_VERSION = 1;
    var PATCH_VERSION = 0;

    var ROGERTHAT_API_PREFIX = ROGERTHAT_SCHEME + "api/";

    var resultReceivedCallbackSet = false;

    var userCallbacks = {
        resultReceived : _dummy
    };

    var callbacks = _generateCallbacksRegister(userCallbacks);
    callbacks.resultReceived = function(callback) {
        // Can only be set once
        if (resultReceivedCallbackSet) {
            throw new Error("Can only set resultReceived callback once.");
        }

        userCallbacks.resultReceived = callback;
        resultReceivedCallbackSet = true;

        // Notify the app that a resultHandler is set
        _callRogerthat("api/resultHandlerConfigured", null);
    };
    
    return {
        MAJOR_VERSION : MAJOR_VERSION,
        MAJOR_VERSION : MINOR_VERSION,
        MAJOR_VERSION : PATCH_VERSION,
        VERSION : MAJOR_VERSION + "." + MINOR_VERSION + "." + PATCH_VERSION,
        call : function(method, params, tag) {
            if (typeof (method) != "string") {
                throw new TypeError("method must be a string");
            }
            if (typeof (params) != "string") {
                throw new TypeError("params must be a string");
            }
            
            var tagJSONStr = JSON.stringify(tag);

            try {
                if (rogerthat.system && rogerthat.system.os === "android") {
                    __rogerthat__.sendApiCall(method, params, tagJSONStr);
                } else {
                    var crp = {};
                    crp.tag = tagJSONStr;
                    crp.method = method;
                    crp.params = params;
                    _callRogerthat("api/call", crp);
                }
            } catch (err) {
                console.error(err);
            }
        },
        callbacks : callbacks,
        _setResult : function(method, result, error, tagJSONStr) {
            userCallbacks.resultReceived(method, result, error, tagJSONStr === "undefined" ? undefined : JSON.parse(tagJSONStr));
        }
    };
};

rogerthat.api = _createRogerthatApiLib();