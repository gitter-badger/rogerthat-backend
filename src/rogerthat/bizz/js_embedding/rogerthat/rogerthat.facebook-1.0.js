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

console.log("Loading rogerthat.facebook-1.0.js");
var _createFacebookLib = function() {
    var MAJOR_VERSION = 0;
    var MINOR_VERSION = 1;
    var PATCH_VERSION = 0;

    var ROGERTHAT_FB_PREFIX = ROGERTHAT_SCHEME + "facebook/";

    var uniqueId = 0;
    var resultHandlers = {};

    var registerResultHandler = function(id, onSuccess, onError) {
        resultHandlers[id] = {
            success : onSuccess,
            error : onError
        };
    };

    return {
        MAJOR_VERSION : MAJOR_VERSION,
        MAJOR_VERSION : MINOR_VERSION,
        MAJOR_VERSION : PATCH_VERSION,
        VERSION : MAJOR_VERSION + "." + MINOR_VERSION + "." + PATCH_VERSION,
        login : function(properties, onSuccess, onError) {
            if (typeof (properties) != "string") {
                throw new TypeError("properties must be a comma seperated string");
            }
            var id = uniqueId++;
            registerResultHandler(id, onSuccess, onError);
            var crp = {};
            crp.id = id;
            crp.properties = properties;
            _callRogerthat("facebook/login", crp);
        },
        post : function(postParams, onSuccess, onError) {
            if (typeof (postParams) != "object") {
                throw new TypeError("postParams must be an object");
            }
            var id = uniqueId++;
            registerResultHandler(id, onSuccess, onError);
            var crp = {};
            crp.id = id;
            crp.postParams = JSON.stringify(postParams);
            _callRogerthat("facebook/post", crp);
        },
        ticker : function(type, postParams, onSuccess, onError) {
            if (typeof (postParams) != "object") {
                throw new TypeError("postParams must be an object");
            }
            var id = uniqueId++;
            registerResultHandler(id, onSuccess, onError);
            var crp = {};
            crp.id = id;
            crp.type = type;
            crp.postParams = JSON.stringify(postParams);
            _callRogerthat("facebook/ticker", crp);
        },
        _setResult : function(requestId, result, error) {
            setTimeout(function() {
                try {
                    if (error){
                        if (resultHandlers[requestId] && resultHandlers[requestId].error) {
                            resultHandlers[requestId].error(error);
                        }
                    }else{
                        if (resultHandlers[requestId] && resultHandlers[requestId].success) {
                            resultHandlers[requestId].success(result);
                        }
                    }
                } finally {
                    resultHandlers[requestId] = undefined;
                }
            }, 1);
        }
    };
};

rogerthat.facebook = _createFacebookLib();