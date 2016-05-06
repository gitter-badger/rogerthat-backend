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

import logging

from rogerthat.translations import DEFAULT_LANGUAGE, localize
from google.appengine.api import urlfetch
from mcfw.rpc import arguments, returns


@returns(tuple)
@arguments(url=unicode, language=unicode)
def get_attachment_content_type_and_length(url, language=DEFAULT_LANGUAGE):
    from rogerthat.bizz.service.mfr import InvalidMessageAttachmentException
    from rogerthat.to.messaging import AttachmentTO

    if url is None or not (url.startswith("http://") or url.startswith("https://")):
        logging.debug("Invalid download_url (%(url)s). It must be reachable over http or https." % {'url':url})
        raise InvalidMessageAttachmentException(localize(language, "Invalid download_url (%(url)s). It must be reachable over http or https.", url=url))

    logging.info('Downloading attachment: %s', url)
    try:
        result = urlfetch.fetch(url, method="HEAD", deadline=10)
    except:
        logging.debug("Could not download attachment %(url)s" % {'url':url}, exc_info=True)
        raise InvalidMessageAttachmentException(localize(language, "Could not download attachment %(url)s", url=url))

    if result.status_code != 200:
        logging.debug("Could not download attachment %s. Response status code: %s", url,
                      result.status_code)
        raise InvalidMessageAttachmentException(localize(language, "Could not download attachment %(url)s", url=url))

    logging.debug(result.headers)

    content_type_header = result.headers.get('Content-Type')
    if not content_type_header:
        logging.debug("Could not determine Content-Type for attachment %s.", url)
        raise InvalidMessageAttachmentException(localize(language, "Could not determine file type for attachment %(url)s", url=url))

    if content_type_header not in AttachmentTO.CONTENT_TYPES:
        logging.debug("Invalid Content-Type (%s) for attachment %s. Valid content types are: %s",
                      content_type_header, url, AttachmentTO.CONTENT_TYPES)
        raise InvalidMessageAttachmentException(localize(language, "_unsupported_attachment_file_type", url=url))

    content_type = unicode(content_type_header)

    content_length_header = result.headers.get('Content-Length')
    content_length = -1 if content_length_header is None else long(content_length_header)

    return content_type, content_length
