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

console.log("Loading rogerthat-1.0.js");
var ROGERTHAT_SCHEME = "rogerthat://";

var MAJOR_VERSION = 0;
var MINOR_VERSION = 1;
var PATCH_VERSION = 0;
var FEATURE_CHECKING = 0;
var FEATURE_SUPPORTED = 1;
var FEATURE_NOT_SUPPORTED = 2;

var PROXIMITY_UNKNOWN = 0;
var PROXIMITY_IMMEDIATE = 1;
var PROXIMITY_NEAR = 2;
var PROXIMITY_FAR = 3;

var _dummy = function() {
};

var rogerthat = {
    MAJOR_VERSION : MAJOR_VERSION,
    MINOR_VERSION : MINOR_VERSION,
    PATCH_VERSION : PATCH_VERSION,
    PROXIMITY_UNKNOWN : PROXIMITY_UNKNOWN,
    PROXIMITY_IMMEDIATE : PROXIMITY_IMMEDIATE,
    PROXIMITY_NEAR : PROXIMITY_NEAR,
    PROXIMITY_FAR : PROXIMITY_FAR,
    VERSION : MAJOR_VERSION + "." + MINOR_VERSION + "." + PATCH_VERSION,
    util : {
        uuid : function() {
            var S4 = function() {
                return (((1 + Math.random()) * 0x10000) | 0).toString(16).substring(1);
            };
            return (S4() + S4() + "-" + S4() + "-" + S4() + "-" + S4() + "-" + S4() + S4() + S4());
        },
        _translations : {
            defaultLanguage : "en",
            values : {
            // eg; "Name": { "fr": "Nom", "nl": "Naam" }
            }
        },
        _translateHTML : function() {
            $("x-rogerthat-t").each(function(i, elem) {
                var t = $(elem);
                var html = t.html();
                t.replaceWith(rogerthat.util.translate(html));
            });
        },
        translate : function(key, parameters) {
            var language = rogerthat.user.language || rogerthat.util._translations.defaultLanguage;
            var translation = undefined;
            if (language != rogerthat.util._translations.defaultLanguage) {
                var translationSet = rogerthat.util._translations.values[key];
                if (translationSet) {
                    translation = translationSet[language];
                    if (translation === undefined) {
                        if (language.indexOf('_') != -1) {
                            language = language.split('_')[0];
                            translation = translationSet[language];
                        }
                    }
                }
            }

            if (translation == undefined) {
                // language is defaultLanguage / key is missing / key is not translated
                translation = key;
            }

            if (parameters) {
                $.each(parameters, function(param, value) {
                    translation = translation.replace('%(' + param + ')s', value);
                });
            }
            return translation;
        }
    },
    features : {
        base64URI : FEATURE_CHECKING,
        backgroundSize : FEATURE_CHECKING,
        beacons : FEATURE_CHECKING,
        callback : undefined
    },
    camera : {
        FRONT : "front",
        BACK : "back"
    }
};

var _checkCapabilities = function() {
    // Test base64 url support
    var callbackBase64URI = function() {
        rogerthat.features.base64URI = this.width == 1 && this.height == 1 ? FEATURE_SUPPORTED : FEATURE_NOT_SUPPORTED;
        if (rogerthat.features.callback !== undefined)
            rogerthat.features.callback('base64URI');
    };

    var img = new Image();
    img.onload = img.onerror = img.onabort = callbackBase64URI;
    img.src = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";

    // Test css3 support
    rogerthat.features.backgroundSize = $.support.backgroundSize ? FEATURE_SUPPORTED : FEATURE_NOT_SUPPORTED;
    if (rogerthat.features.callback !== undefined)
        rogerthat.features.callback('backgroundSize');
};

$.support.backgroundSize = (function() {
    var thisBody = document.documentElement || document.body, thisStyle = thisBody.style, support = thisStyle.backgroundSize !== undefined;

    return support;
})();

_checkCapabilities();

/*-
 * Generate methods to be able to subscribe the callbacks.
 * eg.
 * rogerthat.callbacks.ready(function () {
 *     console.log("rogerthat lib ready!");
 * });
 */
var _generateCallbacksRegister = function(callbacks) {
    var callbacksRegister = {};
    $.each(callbacks, function(i) {
        callbacksRegister[i] = function(callback) {
            callbacks[i] = callback; // TODO: wrap with try/catch?
        };
    });
    return callbacksRegister;
};

var _callRogerthat = function(action, parameters) {
    var log = action !== 'log/';
    var method = typeof __rogerthat__ !== 'undefined' && __rogerthat__.version !== undefined
            && __rogerthat__.version() >= 1 ? 'invoke' : 'window.location';
    if (method !== 'invoke') {
        var completeUrl = ROGERTHAT_SCHEME + action;
        if (parameters) {
            var params = [];
            $.each(parameters, function(param, value) {
                params.push(param + '=' + encodeURIComponent(value));
            });
            if (params.length > 0)
                completeUrl += '?' + params.join('&');
        }

        if (log)
            console.log("Calling rogerthat with url: " + completeUrl);

        var iframe = document.createElement("IFRAME");
        iframe.setAttribute("src", completeUrl);
        document.documentElement.appendChild(iframe);
        iframe.parentNode.removeChild(iframe);
        iframe = null;

        return;
    }
    var params = parameters ? JSON.stringify(parameters) : null;
    if (log)
        console.log('Calling rogerthat with action ' + action + ' and parameters ' + params);
    __rogerthat__.invoke(action, params);
};

console.log("Creating rogerthat lib");
var _createRogerthatLib = function() {
    var uniqueId = 0;
    var resultHandlers = {};

    var registerResultHandler = function(id, onSuccess, onError) {
        resultHandlers[id] = {
            success : onSuccess,
            error : onError
        };
    };

    var userCallbacks = {
        backPressed : _dummy, // overridden by code below
        ready : _dummy,
        onPause : _dummy,
        onResume : _dummy,
        userDataUpdated : _dummy,
        serviceDataUpdated : _dummy,
        onBeaconInReach : _dummy,
        onBeaconOutOfReach : _dummy,
        qrCodeScanned : _dummy,
        onBackendConnectivityChanged : _dummy
    };

    var callbacksRegister = _generateCallbacksRegister(userCallbacks);
    callbacksRegister.backPressed = function(callback) {
        _callRogerthat("back/" + (callback ? "" : "un") + "registerListener", null);
        userCallbacks.backPressed = function(requestId) {
            var handled = false;
            if (callback) {
                try {
                    handled = callback() === true;
                } catch (e) {
                    handled = false;
                    console.error(e);
                }
            }
            var crp = {};
            crp.requestId = requestId;
            crp.handled = handled == true;
            _callRogerthat("back/backPressedCallback", crp);
        };
    };

    var getStackTrace = function(e) {
        if (rogerthat.system !== undefined && rogerthat.system.os == "android") {
            var stack = (e.stack + '\n').replace(/^\S[^\(]+?[\n$]/gm, '') //
            .replace(/^\s+(at eval )?at\s+/gm, '') //
            .replace(/^([^\(]+?)([\n$])/gm, '{anonymous}()@$1$2') //
            .replace(/^Object.<anonymous>\s*\(([^\)]+)\)/gm, '{anonymous}()@$1').split('\n');
            stack.pop();
            return stack.join('\n');
        } else {
            return e.stack.replace(/\[native code\]\n/m, '') //
            .replace(/^(?=\w+Error\:).*$\n/m, '') //
            .replace(/^@/gm, '{anonymous}()@');
        }
    };

    var patchConsoleErrorFunction = function() {
        console.error = function(e) {
            console.log(e);
            if (e.stack) {
                e = e.name + ": " + e.message + "\n" + getStackTrace(e);
            }
            var crp = {};
            crp.e = e;
            _callRogerthat("log/", crp);
        };
    };

    var setRogerthatData = function(info) {
        $.each(info, function(key, value) {
            rogerthat[key] = value;
        });

        if (rogerthat.system === undefined) {
            rogerthat.system = {
                os : "unknown",
                version : "unknown",
                appVersion : "unknown"
            };
            rogerthat.features.beacons = FEATURE_NOT_SUPPORTED;
        } else {
            if (rogerthat.system.os == "ios" && rogerthat.system.version !== undefined
                    && rogerthat.system.appVersion !== undefined) {
                var version = rogerthat.system.version.split(".");
                if (parseInt(version[0]) >= 7) {
                    rogerthat.features.beacons = FEATURE_SUPPORTED;
                } else {
                    rogerthat.features.beacons = FEATURE_NOT_SUPPORTED;
                }
            } else if (rogerthat.system.os == "android" && rogerthat.system.version !== undefined) {
                if (parseInt(rogerthat.system.version) >= 18) {
                    rogerthat.features.beacons = FEATURE_SUPPORTED;
                } else {
                    rogerthat.features.beacons = FEATURE_NOT_SUPPORTED;
                }
            } else {
                rogerthat.features.beacons = FEATURE_NOT_SUPPORTED;
            }
        }
        if (rogerthat.features.callback !== undefined)
            rogerthat.features.callback('beacons');

        rogerthat.user.put = function() {
            var crp = {};
            crp.u = JSON.stringify(rogerthat.user.data);
            _callRogerthat("user/put", crp);
        };
    };

    var setRogerthatFunctions = function() {
        
        rogerthat.system.onBackendConnectivityChanged = function(onSuccess, onError) {
            var id = uniqueId++;
            registerResultHandler(id, onSuccess, onError);
            _callRogerthat("system/onBackendConnectivityChanged", {
                id : id
            });
        };
        
        rogerthat.util.isConnectedToInternet = function(onSuccess, onError) {
            var id = uniqueId++;
            registerResultHandler(id, onSuccess, onError);
            _callRogerthat("util/isConnectedToInternet", {
                id : id
            });
        };

        rogerthat.util.playAudio = function(url, onSuccess, onError) {
            var id = uniqueId++;
            registerResultHandler(id, onSuccess, onError);
            _callRogerthat("util/playAudio", {
                id : id,
                url : url
            });
        };

        rogerthat.service.getBeaconsInReach = function(onSuccess, onError) {
            var id = uniqueId++;
            registerResultHandler(id, onSuccess, onError);
            _callRogerthat("service/getBeaconsInReach", {
                id : id
            });
        };

        rogerthat.camera.startScanningQrCode = function(cameraType, onSuccess, onError) {
            var id = uniqueId++;
            registerResultHandler(id, onSuccess, onError);
            _callRogerthat("camera/startScanningQrCode", {
                id : id,
                camera_type : cameraType
            });
        };

        rogerthat.camera.stopScanningQrCode = function(cameraType, onSuccess, onError) {
            var id = uniqueId++;
            registerResultHandler(id, onSuccess, onError);
            _callRogerthat("camera/stopScanningQrCode", {
                id : id,
                camera_type : cameraType
            });
        };
    };

    patchConsoleErrorFunction();

    rogerthat._bridgeLogging = function() {
        console = new Object();
        console.log = function(log) {
            var crp = {};
            crp.m = log;
            _callRogerthat("log/", crp);
        };
        console.error = console.log;
        console.warn = console.log;
        console.info = console.log;
        console.debug = console.log;
        patchConsoleErrorFunction();
    };
    rogerthat._setInfo = function(info) {
        setRogerthatData(info);
        setRogerthatFunctions();
        rogerthat.util._translateHTML();
        userCallbacks.ready();
    };
    rogerthat._userDataUpdated = function(userData) {
        rogerthat.user.data = userData;
        userCallbacks.userDataUpdated();
    };
    rogerthat._serviceDataUpdated = function(serviceData) {
        rogerthat.service.data = serviceData;
        userCallbacks.serviceDataUpdated();
    };
    rogerthat._onPause = function() {
        userCallbacks.onPause();
    };
    rogerthat._onResume = function() {
        userCallbacks.onResume();
    };
    rogerthat._backPressed = function(requestId) {
        userCallbacks.backPressed(requestId);
    };
    rogerthat._onBeaconInReach = function(beacon) {
        userCallbacks.onBeaconInReach(beacon);
    };
    rogerthat._onBeaconOutOfReach = function(beacon) {
        userCallbacks.onBeaconOutOfReach(beacon);
    };
    rogerthat._qrCodeScanned = function(result) {
        userCallbacks.qrCodeScanned(result);
    };
    rogerthat._onBackendConnectivityChanged = function(connected) {
        userCallbacks.onBackendConnectivityChanged(connected);
    };
    rogerthat._setResult = function(requestId, result, error) {
        setTimeout(function() {
            try {
                if (error) {
                    if (resultHandlers[requestId] && resultHandlers[requestId].error) {
                        resultHandlers[requestId].error(error);
                    }
                } else {
                    if (resultHandlers[requestId] && resultHandlers[requestId].success) {
                        resultHandlers[requestId].success(result);
                    }
                }
            } finally {
                resultHandlers[requestId] = undefined;
            }
        }, 1);
    };
    rogerthat.ui = {
        hideKeyboard : function(element) {
            if (rogerthat.system !== undefined && rogerthat.system.os === "android") {
                try {
                    __rogerthat__.hideKeyboard();
                } catch (err) {
                    console.log(err);
                }
            }
        }
    };
    rogerthat.callbacks = callbacksRegister;
};

_createRogerthatLib();

console.log("Rogerthat binding ready for use");

function getStackTrace(e, isAndroid) {
    if (isAndroid) {
        var stack = (e.stack + '\n').replace(/^\S[^\(]+?[\n$]/gm, '').replace(/^\s+(at eval )?at\s+/gm, '').replace(
                /^([^\(]+?)([\n$])/gm, '{anonymous}()@$1$2').replace(/^Object.<anonymous>\s*\(([^\)]+)\)/gm,
                '{anonymous}()@$1').split('\n');
        stack.pop();
        return stack.join('\n');
    } else {
        return e.stack.replace(/\[native code\]\n/m, '').replace(/^(?=\w+Error\:).*$\n/m, '').replace(/^@/gm,
                '{anonymous}()@');
    }
}

window.addEventListener('error', function(evt) {
    var error = "";
    $.each(evt, function(attr, value) {
        error += attr + ": " + value + "\n";
    });
    console.error("Uncaught javascript exception in HTML-app:\n" + error);
});