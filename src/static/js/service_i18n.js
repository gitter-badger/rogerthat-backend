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

var SUPPORTED_LANGUAGE_LINE = '<span short_lang="${short_lang}">${long_lang} <a style="float:right" href="#" class="action-link" long_lang="${long_lang}" short_lang="${short_lang}">Remove</a><br></span>';

var i18nScript = function () {
    var container = "#serviceI18nContainer";
    var lj = mctracker.getLocaljQuery(container);
    var removeLanguageDialog;
    var configuration;
    
    function applyJQueryInUI() {
        lj("#serviceLanguagesContainer").panel({
            collapsible: false
        });
        lj("#uploadContainer").panel({
            collapsible:false
        });
        lj("#downloadContainer").panel({
            collapsible:false
        });
        lj("#upload_button").button().click(upload);
        lj("#download_button").button().click(download);

        removeLanguageDialog = lj("#removeLanguageDialog").dialog({
            width: 600,
            title: 'Remove supported language',
            buttons: {
                Remove: function () {
                    var short_lang = $(this).attr('short_lang');
                    setSupportedLanguage(short_lang, false);
                    configuration.nonDefaultSupportedLanguages.splice(configuration.nonDefaultSupportedLanguages.indexOf(short_lang),1);
                    lj("span[short_lang='" + short_lang + "']").remove();
                    removeLanguageDialog.dialog('close');
                },
                Cancel: function () {
                    removeLanguageDialog.dialog('close');
                }
            }
        }).dialog('close');
        $('#download_translations', removeLanguageDialog).click(download);
    };

    var upload = function() {
        lj("#upload_error").hide();
        if (! lj("#file").val()) {
            lj("#file_error").fadeIn('slow');
            return;
        }
        mctracker.showProcessing();

        lj("#upload").submit();
        lj("#file_error, #description_error").fadeOut('slow');
    };

    var download = function () {
        window.location = '/mobi/service/translations?tz_offset=' + mctracker.timezoneOffset;
    };

    var processMessage = function (data) {
        if ( data.type == "rogerthat.service.translations.post_result" ) {
            mctracker.hideProcessing();
            if (data.error) {
                lj("#upload_error").empty().append($("<br>"));
                lj("#upload_error").append("There was an error while importing translations!").append($("<br>"));
                if (data.error_code) {
                    lj("#upload_error").append("Error code: " + data.error_code).append($("<br>"));
                }
                lj("#upload_error").append("Error description: " + data.error).fadeIn('slow');
            } else {
                mctracker.alert("Translations imported successfully!");
            }
        }
    };
    
    var showRemoveLanguageDialog = function (aElement) {
        $('span', removeLanguageDialog).text(aElement.attr('long_lang'));
        removeLanguageDialog.attr('short_lang', aElement.attr('short_lang'))
                            .attr('long_lang', aElement.attr('long_lang'))
                            .dialog('open');
    }

    var showConfiguration = function () {
        lj("#serviceLanguagesContainer #default_language").text(mctracker.htmlEncode(configuration.defaultLanguageStr));

        var supportedLanguagesList = lj("#serviceLanguagesContainer #supported_languages_list");
        var serviceLanguagesList = lj("#serviceLanguagesContainer #service_languages_list").empty();

        $.each(configuration.nonDefaultSupportedLanguages, function(i, short_lang) {
            var long_lang = configuration.allLanguagesStr[configuration.allLanguages.indexOf(short_lang)];
            serviceLanguagesList.append($.tmpl(SUPPORTED_LANGUAGE_LINE, {long_lang: long_lang, short_lang: short_lang}));
        });

        $("a", serviceLanguagesList).click(function () {
            showRemoveLanguageDialog($(this));
        });

        var allLanguagesList = $("#all_languages_list", supportedLanguagesList).empty();
        var allLanguagesListHtml = '<select><option value=""></option>';
        for (var i = 0; i < configuration.allLanguages.length; i++) {
            var short_lang = configuration.allLanguages[i];
            if (configuration.nonDefaultSupportedLanguages.indexOf(short_lang) > -1) {
                continue;
            }
            long_lang = mctracker.htmlEncode(configuration.allLanguagesStr[i]);
            allLanguagesListHtml += '<option value="' + short_lang + '">' + long_lang + '</option>';
        }
        allLanguagesListHtml += '</select> <a href="#" class="action-link">Add</a>';
        allLanguagesList.html(allLanguagesListHtml);
        var allLanguagesSelect = $("select", allLanguagesList).css('margin-top', '0').css('margin-left', '8px');

        $("a", allLanguagesList).click(function () {
            var short_lang = allLanguagesSelect.val();
            if (!short_lang) {
                mctracker.alert("Please select a language");
                return;
            }
            allLanguagesSelect.val('');

            if (configuration.nonDefaultSupportedLanguages.indexOf(short_lang) > -1) {
                return;
            }
            setSupportedLanguage(short_lang, true);
            configuration.nonDefaultSupportedLanguages.push(short_lang);

            var long_lang = configuration.allLanguagesStr[configuration.allLanguages.indexOf(short_lang)];
            var element = $.tmpl(SUPPORTED_LANGUAGE_LINE, {long_lang: long_lang, short_lang: short_lang})
            serviceLanguagesList.append(element);

            $("a", element).click(function () {
                showRemoveLanguageDialog($(this));
            });

        });
    };

    var setSupportedLanguage = function (language, enabled) {
        mctracker.call({
            url: '/mobi/rest/service/set_supported_language',
            type: 'post',
            data: {
                data: JSON.stringify({
                    language: language,
                    enabled: enabled
                })
            }
        });
    }

    var initScreen = function () {
        mctracker.call({
           url: "/mobi/rest/service/get_translation_configuration",
           type: "GET",
           success: function (data) {
               configuration = data;
               showConfiguration();
           }
        });
    };

    return function () {
        mctracker.registerMsgCallback(processMessage);
        applyJQueryInUI();
        initScreen();
    };
};

mctracker.registerLoadCallback("serviceI18nContainer", i18nScript());