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

from add_1_monkey_patches import APPSCALE, DEBUG
from google.appengine.api import users

MC_DASHBOARD = users.User(u'dashboard@rogerth.at')
MC_RESERVED_TAG_PREFIX = u"__rt__"

APPSCALE = APPSCALE
DEBUG = DEBUG

MICRO_MULTIPLIER = 1000000
DAY = 60 * 60 * 24
WEEK = DAY * 7

DEFAULT_QUEUE = "default"
MIGRATION_QUEUE = "migration-queue"
HIGH_LOAD_CONTROLLER_QUEUE = "highload-controller-queue"
HIGH_LOAD_WORKER_QUEUE = "highload-worker-queue"
BROADCAST_QUEUE = "broadcast-queue"
SCHEDULED_QUEUE = "scheduled-queue"
OFFLOAD_QUEUE = "offload-queue"
FAST_QUEUE = "fast"

SESSION_TIMEOUT = WEEK * 4

MESSAGE_ACKED_NO_CHANGES = 0
MESSAGE_ACKED = 1
MESSAGE_ACK_FAILED_LOCKED = 2

MAX_BRANDING_SIZE = 400 * 1024  # 400 KiB
MAX_APP_SIZE = 400 * 1024  # 400 KiB
MAX_RPC_SIZE = 75 * 1024  # 75 KiB
MAX_BRANDING_PDF_SIZE = 900 * 1024  # 900 kiB

SERVICE_API_RESULT_RETENTION = DAY
SERVICE_API_CALLBACK_RETRY_UNIT = 30

ANDROID_MARKET_ANDROID_URI_FORMAT = u"market://details?id=%s"
ANDROID_MARKET_WEB_URI_FORMAT = u"https://market.android.com/details?id=%s"
ANDROID_BETA_MARKET_WEB_URI_FORMAT = u"https://play.google.com/apps/testing/%s/join"

IOS_APPSTORE_IOS_URI_FORMAT = u"itms://itunes.apple.com/us/app/id%s"
IOS_APPSTORE_WEB_URI_FORMAT = u"http://itunes.apple.com/us/app/id%s"

CHAT_MAX_BUTTON_REPLIES = 15

OFFICIALLY_SUPPORTED_COUNTRIES = {
    u'AF': u'Afghanistan',
    u'AX': u'Aland Islands',
    u'AL': u'Albania',
    u'DZ': u'Algeria',
    u'AS': u'American Samoa',
    u'AD': u'Andorra',
    u'AO': u'Angola',
    u'AI': u'Anguilla',
    u'AQ': u'Antarctica',
    u'AG': u'Antigua And Barbuda',
    u'AR': u'Argentina',
    u'AM': u'Armenia',
    u'AW': u'Aruba',
    u'AU': u'Australia',
    u'AT': u'Austria',
    u'AZ': u'Azerbaijan',
    u'BS': u'Bahamas',
    u'BH': u'Bahrain',
    u'BD': u'Bangladesh',
    u'BB': u'Barbados',
    u'BY': u'Belarus',
    u'BE': u'Belgium',
    u'BZ': u'Belize',
    u'BJ': u'Benin',
    u'BM': u'Bermuda',
    u'BT': u'Bhutan',
    u'BO': u'Bolivia',
    u'BA': u'Bosnia And Herzegovina',
    u'BW': u'Botswana',
    u'BV': u'Bouvet Island',
    u'BR': u'Brazil',
    u'IO': u'British Indian Ocean Territory',
    u'BN': u'Brunei Darussalam',
    u'BG': u'Bulgaria',
    u'BF': u'Burkina Faso',
    u'BI': u'Burundi',
    u'KH': u'Cambodia',
    u'CM': u'Cameroon',
    u'CA': u'Canada',
    u'CV': u'Cape Verde',
    u'KY': u'Cayman Islands',
    u'CF': u'Central African Republic',
    u'TD': u'Chad',
    u'CL': u'Chile',
    u'CN': u'China',
    u'CX': u'Christmas Island',
    u'CC': u'Cocos (Keeling) Islands',
    u'CO': u'Colombia',
    u'KM': u'Comoros',
    u'CG': u'Congo',
    u'CD': u'Congo, Democratic Republic',
    u'CK': u'Cook Islands',
    u'CR': u'Costa Rica',
    u'CI': u'Cote D\'Ivoire',
    u'HR': u'Croatia',
    u'CU': u'Cuba',
    u'CY': u'Cyprus',
    u'CZ': u'Czech Republic',
    u'DK': u'Denmark',
    u'DJ': u'Djibouti',
    u'DM': u'Dominica',
    u'DO': u'Dominican Republic',
    u'EC': u'Ecuador',
    u'EG': u'Egypt',
    u'SV': u'El Salvador',
    u'GQ': u'Equatorial Guinea',
    u'ER': u'Eritrea',
    u'EE': u'Estonia',
    u'ET': u'Ethiopia',
    u'FK': u'Falkland Islands (Malvinas)',
    u'FO': u'Faroe Islands',
    u'FJ': u'Fiji',
    u'FI': u'Finland',
    u'FR': u'France',
    u'GF': u'French Guiana',
    u'PF': u'French Polynesia',
    u'TF': u'French Southern Territories',
    u'GA': u'Gabon',
    u'GM': u'Gambia',
    u'GE': u'Georgia',
    u'DE': u'Germany',
    u'GH': u'Ghana',
    u'GI': u'Gibraltar',
    u'GR': u'Greece',
    u'GL': u'Greenland',
    u'GD': u'Grenada',
    u'GP': u'Guadeloupe',
    u'GU': u'Guam',
    u'GT': u'Guatemala',
    u'GG': u'Guernsey',
    u'GN': u'Guinea',
    u'GW': u'Guinea-Bissau',
    u'GY': u'Guyana',
    u'HT': u'Haiti',
    u'HM': u'Heard Island & Mcdonald Islands',
    u'VA': u'Holy See (Vatican City State)',
    u'HN': u'Honduras',
    u'HK': u'Hong Kong',
    u'HU': u'Hungary',
    u'IS': u'Iceland',
    u'IN': u'India',
    u'ID': u'Indonesia',
    u'IR': u'Iran, Islamic Republic Of',
    u'IQ': u'Iraq',
    u'IE': u'Ireland',
    u'IM': u'Isle Of Man',
    u'IL': u'Israel',
    u'IT': u'Italy',
    u'JM': u'Jamaica',
    u'JP': u'Japan',
    u'JE': u'Jersey',
    u'JO': u'Jordan',
    u'KZ': u'Kazakhstan',
    u'KE': u'Kenya',
    u'KI': u'Kiribati',
    u'KR': u'Korea',
    u'KW': u'Kuwait',
    u'KG': u'Kyrgyzstan',
    u'LA': u'Lao People\'s Democratic Republic',
    u'LV': u'Latvia',
    u'LB': u'Lebanon',
    u'LS': u'Lesotho',
    u'LR': u'Liberia',
    u'LY': u'Libyan Arab Jamahiriya',
    u'LI': u'Liechtenstein',
    u'LT': u'Lithuania',
    u'LU': u'Luxembourg',
    u'MO': u'Macao',
    u'MK': u'Macedonia',
    u'MG': u'Madagascar',
    u'MW': u'Malawi',
    u'MY': u'Malaysia',
    u'MV': u'Maldives',
    u'ML': u'Mali',
    u'MT': u'Malta',
    u'MH': u'Marshall Islands',
    u'MQ': u'Martinique',
    u'MR': u'Mauritania',
    u'MU': u'Mauritius',
    u'YT': u'Mayotte',
    u'MX': u'Mexico',
    u'FM': u'Micronesia, Federated States Of',
    u'MD': u'Moldova',
    u'MC': u'Monaco',
    u'MN': u'Mongolia',
    u'ME': u'Montenegro',
    u'MS': u'Montserrat',
    u'MA': u'Morocco',
    u'MZ': u'Mozambique',
    u'MM': u'Myanmar',
    u'NA': u'Namibia',
    u'NR': u'Nauru',
    u'NP': u'Nepal',
    u'NL': u'Netherlands',
    u'AN': u'Netherlands Antilles',
    u'NC': u'New Caledonia',
    u'NZ': u'New Zealand',
    u'NI': u'Nicaragua',
    u'NE': u'Niger',
    u'NG': u'Nigeria',
    u'NU': u'Niue',
    u'NF': u'Norfolk Island',
    u'MP': u'Northern Mariana Islands',
    u'NO': u'Norway',
    u'OM': u'Oman',
    u'PK': u'Pakistan',
    u'PW': u'Palau',
    u'PS': u'Palestinian Territory, Occupied',
    u'PA': u'Panama',
    u'PG': u'Papua New Guinea',
    u'PY': u'Paraguay',
    u'PE': u'Peru',
    u'PH': u'Philippines',
    u'PN': u'Pitcairn',
    u'PL': u'Poland',
    u'PT': u'Portugal',
    u'PR': u'Puerto Rico',
    u'QA': u'Qatar',
    u'RE': u'Reunion',
    u'RO': u'Romania',
    u'RU': u'Russian Federation',
    u'RW': u'Rwanda',
    u'BL': u'Saint Barthelemy',
    u'SH': u'Saint Helena',
    u'KN': u'Saint Kitts And Nevis',
    u'LC': u'Saint Lucia',
    u'MF': u'Saint Martin',
    u'PM': u'Saint Pierre And Miquelon',
    u'VC': u'Saint Vincent And Grenadines',
    u'WS': u'Samoa',
    u'SM': u'San Marino',
    u'ST': u'Sao Tome And Principe',
    u'SA': u'Saudi Arabia',
    u'SN': u'Senegal',
    u'RS': u'Serbia',
    u'SC': u'Seychelles',
    u'SL': u'Sierra Leone',
    u'SG': u'Singapore',
    u'SK': u'Slovakia',
    u'SI': u'Slovenia',
    u'SB': u'Solomon Islands',
    u'SO': u'Somalia',
    u'ZA': u'South Africa',
    u'GS': u'South Georgia And Sandwich Isl.',
    u'ES': u'Spain',
    u'LK': u'Sri Lanka',
    u'SD': u'Sudan',
    u'SR': u'Suriname',
    u'SJ': u'Svalbard And Jan Mayen',
    u'SZ': u'Swaziland',
    u'SE': u'Sweden',
    u'CH': u'Switzerland',
    u'SY': u'Syrian Arab Republic',
    u'TW': u'Taiwan',
    u'TJ': u'Tajikistan',
    u'TZ': u'Tanzania',
    u'TH': u'Thailand',
    u'TL': u'Timor-Leste',
    u'TG': u'Togo',
    u'TK': u'Tokelau',
    u'TO': u'Tonga',
    u'TT': u'Trinidad And Tobago',
    u'TN': u'Tunisia',
    u'TR': u'Turkey',
    u'TM': u'Turkmenistan',
    u'TC': u'Turks And Caicos Islands',
    u'TV': u'Tuvalu',
    u'UG': u'Uganda',
    u'UA': u'Ukraine',
    u'AE': u'United Arab Emirates',
    u'GB': u'United Kingdom',
    u'US': u'United States',
    u'UM': u'United States Outlying Islands',
    u'UY': u'Uruguay',
    u'UZ': u'Uzbekistan',
    u'VU': u'Vanuatu',
    u'VE': u'Venezuela',
    u'VN': u'Viet Nam',
    u'VG': u'Virgin Islands, British',
    u'VI': u'Virgin Islands, U.S.',
    u'WF': u'Wallis And Futuna',
    u'EH': u'Western Sahara',
    u'YE': u'Yemen',
    u'ZM': u'Zambia',
    u'ZW': u'Zimbabwe'
}

OFFICIALLY_SUPPORTED_LANGUAGES = {  u"af": u"Afrikaans",
                                    u"sq": u"Albanian",
                                    u"ar": u"Arabic (Modern Standard Arabic)",
                                    u"ar-sa": u"Arabic (Saudi Arabia)",
                                    u"ar-iq": u"Arabic (Iraq)",
                                    u"ar-eg": u"Arabic (Egypt)",
                                    u"ar-ly": u"Arabic (Libya)",
                                    u"ar-dz": u"Arabic (Algeria)",
                                    u"ar-ma": u"Arabic (Morocco)",
                                    u"ar-tn": u"Arabic (Tunisia)",
                                    u"ar-om": u"Arabic (Oman)",
                                    u"ar-ye": u"Arabic (Yemen)",
                                    u"ar-sy": u"Arabic (Syria)",
                                    u"ar-jo": u"Arabic (Jordan)",
                                    u"ar-lb": u"Arabic (Lebanon)",
                                    u"ar-kw": u"Arabic (Kuwait)",
                                    u"ar-ae": u"Arabic (U.A.E.)",
                                    u"ar-bh": u"Arabic (Bahrain)",
                                    u"ar-qa": u"Arabic (Qatar)",
                                    u"eu": u"Basque",
                                    u"bg": u"Bulgarian",
                                    u"be": u"Belarusian",
                                    u"ca": u"Catalan",
                                    u"zh-tw": u"Chinese (Taiwan)",
                                    u"zh-cn": u"Chinese (PRC)",
                                    u"zh-hk": u"Chinese (Hong Kong SAR)",
                                    u"zh-sg": u"Chinese (Singapore)",
                                    u"hr": u"Croatian",
                                    u"cs": u"Czech",
                                    u"da": u"Danish",
                                    u"nl": u"Dutch (Standard)",
                                    u"nl-be": u"Dutch (Belgium)",
                                    u"en": u"English",
                                    u"en-us": u"English (United States)",
                                    u"en-gb": u"English (United Kingdom)",
                                    u"en-au": u"English (Australia)",
                                    u"en-ca": u"English (Canada)",
                                    u"en-nz": u"English (New Zealand)",
                                    u"en-ie": u"English (Ireland)",
                                    u"en-za": u"English (South Africa)",
                                    u"en-jm": u"English (Jamaica)",
                                    u"en-bz": u"English (Belize)",
                                    u"en-tt": u"English (Trinidad)",
                                    u"et": u"Estonian",
                                    u"fo": u"Faeroese",
                                    u"fa": u"Farsi",
                                    u"fi": u"Finnish",
                                    u"fr": u"French (Standard)",
                                    u"fr-be": u"French (Belgium)",
                                    u"fr-ca": u"French (Canada)",
                                    u"fr-ch": u"French (Switzerland)",
                                    u"fr-lu": u"French (Luxembourg)",
                                    u"gd": u"Gaelic (Scotland)",
                                    u"ga": u"Irish",
                                    u"de": u"German (Standard)",
                                    u"de-ch": u"German (Switzerland)",
                                    u"de-at": u"German (Austria)",
                                    u"de-lu": u"German (Luxembourg)",
                                    u"de-li": u"German (Liechtenstein)",
                                    u"el": u"Greek",
                                    u"he": u"Hebrew",
                                    u"hi": u"Hindi",
                                    u"hu": u"Hungarian",
                                    u"is": u"Icelandic",
                                    u"id": u"Indonesian",
                                    u"it": u"Italian (Standard)",
                                    u"it-ch": u"Italian (Switzerland)",
                                    u"ja": u"Japanese",
                                    u"ko": u"Korean",
                                    u"ko": u"Korean (Johab)",
                                    u"lv": u"Latvian",
                                    u"lt": u"Lithuanian",
                                    u"mk": u"Macedonian (FYROM)",
                                    u"ms": u"Malaysian",
                                    u"mt": u"Maltese",
                                    u"no": u"Norwegian (Bokmal)",
                                    u"no": u"Norwegian (Nynorsk)",
                                    u"pl": u"Polish",
                                    u"pt-br": u"Portuguese (Brazil)",
                                    u"pt": u"Portuguese (Portugal)",
                                    u"rm": u"Rhaeto-Romanic",
                                    u"ro": u"Romanian",
                                    u"ro-mo": u"Romanian (Republic of Moldova)",
                                    u"ru": u"Russian",
                                    u"ru-mo": u"Russian (Republic of Moldova)",
                                    u"sz": u"Sami (Lappish)",
                                    u"sr": u"Serbian (Cyrillic)",
                                    u"sr": u"Serbian (Latin)",
                                    u"sk": u"Slovak",
                                    u"sl": u"Slovenian",
                                    u"sb": u"Sorbian",
                                    u"es": u"Spanish (Spain)",
                                    u"es-mx": u"Spanish (Mexico)",
                                    u"es-gt": u"Spanish (Guatemala)",
                                    u"es-cr": u"Spanish (Costa Rica)",
                                    u"es-pa": u"Spanish (Panama)",
                                    u"es-do": u"Spanish (Dominican Republic)",
                                    u"es-ve": u"Spanish (Venezuela)",
                                    u"es-co": u"Spanish (Colombia)",
                                    u"es-pe": u"Spanish (Peru)",
                                    u"es-ar": u"Spanish (Argentina)",
                                    u"es-ec": u"Spanish (Ecuador)",
                                    u"es-cl": u"Spanish (Chile)",
                                    u"es-uy": u"Spanish (Uruguay)",
                                    u"es-py": u"Spanish (Paraguay)",
                                    u"es-bo": u"Spanish (Bolivia)",
                                    u"es-sv": u"Spanish (El Salvador)",
                                    u"es-hn": u"Spanish (Honduras)",
                                    u"es-ni": u"Spanish (Nicaragua)",
                                    u"es-pr": u"Spanish (Puerto Rico)",
                                    u"sx": u"Sutu",
                                    u"sv": u"Swedish",
                                    u"sv-fi": u"Swedish (Finland)",
                                    u"th": u"Thai",
                                    u"ts": u"Tsonga",
                                    u"tn": u"Tswana",
                                    u"tr": u"Turkish",
                                    u"uk": u"Ukrainian",
                                    u"ur": u"Urdu",
                                    u"ve": u"Venda",
                                    u"vi": u"Vietnamese",
                                    u"xh": u"Xhosa",
                                    u"ji": u"Yiddish",
                                    u"zu": u"Zulu"}

# Version 4.5.0
# Grabbed from http://fortawesome.github.io/Font-Awesome/cheatsheet/
# var names=[];$('.row .col-md-4').each(function(){var s=$(this).text();var m=s.match(/fa-.*/);if(m&&m[0]){names.push(m[0]);}});
FA_ICONS = [u'fa-500px', u'fa-adjust', u'fa-adn', u'fa-align-center', u'fa-align-justify', u'fa-align-left',
            u'fa-align-right', u'fa-amazon', u'fa-ambulance', u'fa-anchor', u'fa-android', u'fa-angellist',
            u'fa-angle-double-down', u'fa-angle-double-left', u'fa-angle-double-right', u'fa-angle-double-up',
            u'fa-angle-down', u'fa-angle-left', u'fa-angle-right', u'fa-angle-up', u'fa-apple', u'fa-archive',
            u'fa-area-chart', u'fa-arrow-circle-down', u'fa-arrow-circle-left', u'fa-arrow-circle-o-down',
            u'fa-arrow-circle-o-left', u'fa-arrow-circle-o-right', u'fa-arrow-circle-o-up', u'fa-arrow-circle-right',
            u'fa-arrow-circle-up', u'fa-arrow-down', u'fa-arrow-left', u'fa-arrow-right', u'fa-arrow-up', u'fa-arrows',
            u'fa-arrows-alt', u'fa-arrows-h', u'fa-arrows-v', u'fa-asterisk', u'fa-at', u'fa-automobile',
            u'fa-backward', u'fa-balance-scale', u'fa-ban', u'fa-bank', u'fa-bar-chart', u'fa-bar-chart-o',
            u'fa-barcode', u'fa-bars', u'fa-battery-0', u'fa-battery-1', u'fa-battery-2', u'fa-battery-3',
            u'fa-battery-4', u'fa-battery-empty', u'fa-battery-full', u'fa-battery-half', u'fa-battery-quarter',
            u'fa-battery-three-quarters', u'fa-bed', u'fa-beer', u'fa-behance', u'fa-behance-square', u'fa-bell',
            u'fa-bell-o', u'fa-bell-slash', u'fa-bell-slash-o', u'fa-bicycle', u'fa-binoculars', u'fa-birthday-cake',
            u'fa-bitbucket', u'fa-bitbucket-square', u'fa-bitcoin', u'fa-black-tie', u'fa-bluetooth', u'fa-bluetooth-b',
            u'fa-bold', u'fa-bolt', u'fa-bomb', u'fa-book', u'fa-bookmark', u'fa-bookmark-o', u'fa-briefcase',
            u'fa-btc', u'fa-bug', u'fa-building', u'fa-building-o', u'fa-bullhorn', u'fa-bullseye', u'fa-bus',
            u'fa-buysellads', u'fa-cab', u'fa-calculator', u'fa-calendar', u'fa-calendar-check-o',
            u'fa-calendar-minus-o', u'fa-calendar-o', u'fa-calendar-plus-o', u'fa-calendar-times-o', u'fa-camera',
            u'fa-camera-retro', u'fa-car', u'fa-caret-down', u'fa-caret-left', u'fa-caret-right',
            u'fa-caret-square-o-down', u'fa-caret-square-o-left', u'fa-caret-square-o-right', u'fa-caret-square-o-up',
            u'fa-caret-up', u'fa-cart-arrow-down', u'fa-cart-plus', u'fa-cc', u'fa-cc-amex', u'fa-cc-diners-club',
            u'fa-cc-discover', u'fa-cc-jcb', u'fa-cc-mastercard', u'fa-cc-paypal', u'fa-cc-stripe', u'fa-cc-visa',
            u'fa-certificate', u'fa-chain', u'fa-chain-broken', u'fa-check', u'fa-check-circle', u'fa-check-circle-o',
            u'fa-check-square', u'fa-check-square-o', u'fa-chevron-circle-down', u'fa-chevron-circle-left',
            u'fa-chevron-circle-right', u'fa-chevron-circle-up', u'fa-chevron-down', u'fa-chevron-left',
            u'fa-chevron-right', u'fa-chevron-up', u'fa-child', u'fa-chrome', u'fa-circle', u'fa-circle-o',
            u'fa-circle-o-notch', u'fa-circle-thin', u'fa-clipboard', u'fa-clock-o', u'fa-clone', u'fa-close',
            u'fa-cloud', u'fa-cloud-download', u'fa-cloud-upload', u'fa-cny', u'fa-code', u'fa-code-fork',
            u'fa-codepen', u'fa-codiepie', u'fa-coffee', u'fa-cog', u'fa-cogs', u'fa-columns', u'fa-comment',
            u'fa-comment-o', u'fa-commenting', u'fa-commenting-o', u'fa-comments', u'fa-comments-o', u'fa-compass',
            u'fa-compress', u'fa-connectdevelop', u'fa-contao', u'fa-copy', u'fa-copyright', u'fa-creative-commons',
            u'fa-credit-card', u'fa-credit-card-alt', u'fa-crop', u'fa-crosshairs', u'fa-css3', u'fa-cube', u'fa-cubes',
            u'fa-cut', u'fa-cutlery', u'fa-dashboard', u'fa-dashcube', u'fa-database', u'fa-dedent', u'fa-delicious',
            u'fa-desktop', u'fa-deviantart', u'fa-diamond', u'fa-digg', u'fa-dollar', u'fa-dot-circle-o',
            u'fa-download', u'fa-dribbble', u'fa-dropbox', u'fa-drupal', u'fa-edge', u'fa-edit', u'fa-eject',
            u'fa-ellipsis-h', u'fa-ellipsis-v', u'fa-empire', u'fa-envelope', u'fa-envelope-o', u'fa-envelope-square',
            u'fa-eraser', u'fa-eur', u'fa-euro', u'fa-exchange', u'fa-exclamation', u'fa-exclamation-circle',
            u'fa-exclamation-triangle', u'fa-expand', u'fa-expeditedssl', u'fa-external-link',
            u'fa-external-link-square', u'fa-eye', u'fa-eye-slash', u'fa-eyedropper', u'fa-facebook', u'fa-facebook-f',
            u'fa-facebook-official', u'fa-facebook-square', u'fa-fast-backward', u'fa-fast-forward', u'fa-fax',
            u'fa-feed', u'fa-female', u'fa-fighter-jet', u'fa-file', u'fa-file-archive-o', u'fa-file-audio-o',
            u'fa-file-code-o', u'fa-file-excel-o', u'fa-file-image-o', u'fa-file-movie-o', u'fa-file-o',
            u'fa-file-pdf-o', u'fa-file-photo-o', u'fa-file-picture-o', u'fa-file-powerpoint-o', u'fa-file-sound-o',
            u'fa-file-text', u'fa-file-text-o', u'fa-file-video-o', u'fa-file-word-o', u'fa-file-zip-o', u'fa-files-o',
            u'fa-film', u'fa-filter', u'fa-fire', u'fa-fire-extinguisher', u'fa-firefox', u'fa-flag',
            u'fa-flag-checkered', u'fa-flag-o', u'fa-flash', u'fa-flask', u'fa-flickr', u'fa-floppy-o', u'fa-folder',
            u'fa-folder-o', u'fa-folder-open', u'fa-folder-open-o', u'fa-font', u'fa-fonticons', u'fa-fort-awesome',
            u'fa-forumbee', u'fa-forward', u'fa-foursquare', u'fa-frown-o', u'fa-futbol-o', u'fa-gamepad', u'fa-gavel',
            u'fa-gbp', u'fa-ge', u'fa-gear', u'fa-gears', u'fa-genderless', u'fa-get-pocket', u'fa-gg', u'fa-gg-circle',
            u'fa-gift', u'fa-git', u'fa-git-square', u'fa-github', u'fa-github-alt', u'fa-github-square', u'fa-gittip',
            u'fa-glass', u'fa-globe', u'fa-google', u'fa-google-plus', u'fa-google-plus-square', u'fa-google-wallet',
            u'fa-graduation-cap', u'fa-gratipay', u'fa-group', u'fa-h-square', u'fa-hacker-news', u'fa-hand-grab-o',
            u'fa-hand-lizard-o', u'fa-hand-o-down', u'fa-hand-o-left', u'fa-hand-o-right', u'fa-hand-o-up',
            u'fa-hand-paper-o', u'fa-hand-peace-o', u'fa-hand-pointer-o', u'fa-hand-rock-o', u'fa-hand-scissors-o',
            u'fa-hand-spock-o', u'fa-hand-stop-o', u'fa-hashtag', u'fa-hdd-o', u'fa-header', u'fa-headphones',
            u'fa-heart', u'fa-heart-o', u'fa-heartbeat', u'fa-history', u'fa-home', u'fa-hospital-o', u'fa-hotel',
            u'fa-hourglass', u'fa-hourglass-1', u'fa-hourglass-2', u'fa-hourglass-3', u'fa-hourglass-end',
            u'fa-hourglass-half', u'fa-hourglass-o', u'fa-hourglass-start', u'fa-houzz', u'fa-html5', u'fa-i-cursor',
            u'fa-ils', u'fa-image', u'fa-inbox', u'fa-indent', u'fa-industry', u'fa-info', u'fa-info-circle', u'fa-inr',
            u'fa-instagram', u'fa-institution', u'fa-internet-explorer', u'fa-intersex', u'fa-ioxhost', u'fa-italic',
            u'fa-joomla', u'fa-jpy', u'fa-jsfiddle', u'fa-key', u'fa-keyboard-o', u'fa-krw', u'fa-language',
            u'fa-laptop', u'fa-lastfm', u'fa-lastfm-square', u'fa-leaf', u'fa-leanpub', u'fa-legal', u'fa-lemon-o',
            u'fa-level-down', u'fa-level-up', u'fa-life-bouy', u'fa-life-buoy', u'fa-life-ring', u'fa-life-saver',
            u'fa-lightbulb-o', u'fa-line-chart', u'fa-link', u'fa-linkedin', u'fa-linkedin-square', u'fa-linux',
            u'fa-list', u'fa-list-alt', u'fa-list-ol', u'fa-list-ul', u'fa-location-arrow', u'fa-lock',
            u'fa-long-arrow-down', u'fa-long-arrow-left', u'fa-long-arrow-right', u'fa-long-arrow-up', u'fa-magic',
            u'fa-magnet', u'fa-mail-forward', u'fa-mail-reply', u'fa-mail-reply-all', u'fa-male', u'fa-map',
            u'fa-map-marker', u'fa-map-o', u'fa-map-pin', u'fa-map-signs', u'fa-mars', u'fa-mars-double',
            u'fa-mars-stroke', u'fa-mars-stroke-h', u'fa-mars-stroke-v', u'fa-maxcdn', u'fa-meanpath', u'fa-medium',
            u'fa-medkit', u'fa-meh-o', u'fa-mercury', u'fa-microphone', u'fa-microphone-slash', u'fa-minus',
            u'fa-minus-circle', u'fa-minus-square', u'fa-minus-square-o', u'fa-mixcloud', u'fa-mobile',
            u'fa-mobile-phone', u'fa-modx', u'fa-money', u'fa-moon-o', u'fa-mortar-board', u'fa-motorcycle',
            u'fa-mouse-pointer', u'fa-music', u'fa-navicon', u'fa-neuter', u'fa-newspaper-o', u'fa-object-group',
            u'fa-object-ungroup', u'fa-odnoklassniki', u'fa-odnoklassniki-square', u'fa-opencart', u'fa-openid',
            u'fa-opera', u'fa-optin-monster', u'fa-outdent', u'fa-pagelines', u'fa-paint-brush', u'fa-paper-plane',
            u'fa-paper-plane-o', u'fa-paperclip', u'fa-paragraph', u'fa-paste', u'fa-pause', u'fa-pause-circle',
            u'fa-pause-circle-o', u'fa-paw', u'fa-paypal', u'fa-pencil', u'fa-pencil-square', u'fa-pencil-square-o',
            u'fa-percent', u'fa-phone', u'fa-phone-square', u'fa-photo', u'fa-picture-o', u'fa-pie-chart',
            u'fa-pied-piper', u'fa-pied-piper-alt', u'fa-pinterest', u'fa-pinterest-p', u'fa-pinterest-square',
            u'fa-plane', u'fa-play', u'fa-play-circle', u'fa-play-circle-o', u'fa-plug', u'fa-plus', u'fa-plus-circle',
            u'fa-plus-square', u'fa-plus-square-o', u'fa-power-off', u'fa-print', u'fa-product-hunt',
            u'fa-puzzle-piece', u'fa-qq', u'fa-qrcode', u'fa-question', u'fa-question-circle', u'fa-quote-left',
            u'fa-quote-right', u'fa-ra', u'fa-random', u'fa-rebel', u'fa-recycle', u'fa-reddit', u'fa-reddit-alien',
            u'fa-reddit-square', u'fa-refresh', u'fa-registered', u'fa-remove', u'fa-renren', u'fa-reorder',
            u'fa-repeat', u'fa-reply', u'fa-reply-all', u'fa-retweet', u'fa-rmb', u'fa-road', u'fa-rocket',
            u'fa-rotate-left', u'fa-rotate-right', u'fa-rouble', u'fa-rss', u'fa-rss-square', u'fa-rub', u'fa-ruble',
            u'fa-rupee', u'fa-safari', u'fa-save', u'fa-scissors', u'fa-scribd', u'fa-search', u'fa-search-minus',
            u'fa-search-plus', u'fa-sellsy', u'fa-send', u'fa-send-o', u'fa-server', u'fa-share', u'fa-share-alt',
            u'fa-share-alt-square', u'fa-share-square', u'fa-share-square-o', u'fa-shekel', u'fa-sheqel', u'fa-shield',
            u'fa-ship', u'fa-shirtsinbulk', u'fa-shopping-bag', u'fa-shopping-basket', u'fa-shopping-cart',
            u'fa-sign-in', u'fa-sign-out', u'fa-signal', u'fa-simplybuilt', u'fa-sitemap', u'fa-skyatlas', u'fa-skype',
            u'fa-slack', u'fa-sliders', u'fa-slideshare', u'fa-smile-o', u'fa-soccer-ball-o', u'fa-sort',
            u'fa-sort-alpha-asc', u'fa-sort-alpha-desc', u'fa-sort-amount-asc', u'fa-sort-amount-desc', u'fa-sort-asc',
            u'fa-sort-desc', u'fa-sort-down', u'fa-sort-numeric-asc', u'fa-sort-numeric-desc', u'fa-sort-up',
            u'fa-soundcloud', u'fa-space-shuttle', u'fa-spinner', u'fa-spoon', u'fa-spotify', u'fa-square',
            u'fa-square-o', u'fa-stack-exchange', u'fa-stack-overflow', u'fa-star', u'fa-star-half',
            u'fa-star-half-empty', u'fa-star-half-full', u'fa-star-half-o', u'fa-star-o', u'fa-steam',
            u'fa-steam-square', u'fa-step-backward', u'fa-step-forward', u'fa-stethoscope', u'fa-sticky-note',
            u'fa-sticky-note-o', u'fa-stop', u'fa-stop-circle', u'fa-stop-circle-o', u'fa-street-view',
            u'fa-strikethrough', u'fa-stumbleupon', u'fa-stumbleupon-circle', u'fa-subscript', u'fa-subway',
            u'fa-suitcase', u'fa-sun-o', u'fa-superscript', u'fa-support', u'fa-table', u'fa-tablet', u'fa-tachometer',
            u'fa-tag', u'fa-tags', u'fa-tasks', u'fa-taxi', u'fa-television', u'fa-tencent-weibo', u'fa-terminal',
            u'fa-text-height', u'fa-text-width', u'fa-th', u'fa-th-large', u'fa-th-list', u'fa-thumb-tack',
            u'fa-thumbs-down', u'fa-thumbs-o-down', u'fa-thumbs-o-up', u'fa-thumbs-up', u'fa-ticket', u'fa-times',
            u'fa-times-circle', u'fa-times-circle-o', u'fa-tint', u'fa-toggle-down', u'fa-toggle-left',
            u'fa-toggle-off', u'fa-toggle-on', u'fa-toggle-right', u'fa-toggle-up', u'fa-trademark', u'fa-train',
            u'fa-transgender', u'fa-transgender-alt', u'fa-trash', u'fa-trash-o', u'fa-tree', u'fa-trello',
            u'fa-tripadvisor', u'fa-trophy', u'fa-truck', u'fa-try', u'fa-tty', u'fa-tumblr', u'fa-tumblr-square',
            u'fa-turkish-lira', u'fa-tv', u'fa-twitch', u'fa-twitter', u'fa-twitter-square', u'fa-umbrella',
            u'fa-underline', u'fa-undo', u'fa-university', u'fa-unlink', u'fa-unlock', u'fa-unlock-alt', u'fa-unsorted',
            u'fa-upload', u'fa-usb', u'fa-usd', u'fa-user', u'fa-user-md', u'fa-user-plus', u'fa-user-secret',
            u'fa-user-times', u'fa-users', u'fa-venus', u'fa-venus-double', u'fa-venus-mars', u'fa-viacoin',
            u'fa-video-camera', u'fa-vimeo', u'fa-vimeo-square', u'fa-vine', u'fa-vk', u'fa-volume-down',
            u'fa-volume-off', u'fa-volume-up', u'fa-warning', u'fa-wechat', u'fa-weibo', u'fa-weixin', u'fa-whatsapp',
            u'fa-wheelchair', u'fa-wifi', u'fa-wikipedia-w', u'fa-windows', u'fa-won', u'fa-wordpress', u'fa-wrench',
            u'fa-xing', u'fa-xing-square', u'fa-y-combinator', u'fa-y-combinator-square', u'fa-yahoo', u'fa-yc',
            u'fa-yc-square', u'fa-yelp', u'fa-yen', u'fa-youtube', u'fa-youtube-play', u'fa-youtube-square']
