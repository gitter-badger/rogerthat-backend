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

(function () {
    "use strict";
    var language = 'en';
    render();

    function render () {
        var availableLanguages = [];
        for (var lang in TRANSLATIONS) {
            if (TRANSLATIONS.hasOwnProperty(lang)) {
                availableLanguages.push(lang);
            }
        }
        console.log(JSON.stringify(TRANSLATIONS));
        var html = $.tmpl(TEMPLATES.app_translations_part, {
            app: app,
            translations: TRANSLATIONS,
            language: language,
            availableLanguages: availableLanguages
        });
        $('#main-content').html(html);

        $('#select-language').on('change', function () {
            language = $(this).val();
            render();
        });
        $('#add-language-button').click(function () {
            var lang = $('#add-language').val();
            if (lang && !TRANSLATIONS[lang]) {
                TRANSLATIONS[lang] = {};
                language = lang;
                if (!TRANSLATIONS['en']) {
                    TRANSLATIONS['en'] = {};
                }
                render();
            }
        });

        $('#add-translation-key-button').click(function () {
            var key = $('#add-translation-key').val();
            if (key && !TRANSLATIONS['en'][key]) {
                TRANSLATIONS['en'][key] = '';
            } else {
                sln.alert('translation key ' + key + ' does already exist');
            }
            render();
        });

        $(document).keyup(function (e) {
            var $this = $(e.target);
            var lang = $this.attr('data-language');
            if (lang) {
                TRANSLATIONS[lang][$this.attr('data-key')] = $this.val();
            }
        });

        $('.remove-translation').click(function () {
            var key = $(this).attr('data-key');
            for (var lang in TRANSLATIONS) {
                if (TRANSLATIONS.hasOwnProperty(lang)) {
                    delete TRANSLATIONS[lang][key];
                }
            }
            render();
        });

        $('#save-translations').click(function () {
            sln.call({
                url: '/mobiadmin/apps/translations/app/save',
                method: 'post',
                data: {
                    data: JSON.stringify({
                        app_id: app.id,
                        translations: JSON.stringify(TRANSLATIONS)
                    })
                },
                success: function (data) {
                    if (data.success === true) {
                        sln.alert('Saved!');
                    }
                }
            });
        });

        $('#remove-language').click(function () {
            var lang = $('#select-language').val();
            if (lang === 'en') {
                sln.alert('You cannot delete the english translations');
            } else {
                sln.confirm('Are you sure you want to delete the language "' + lang + '"?', function () {
                    delete TRANSLATIONS[lang];
                    render();
                });
            }
        });
    }
})();