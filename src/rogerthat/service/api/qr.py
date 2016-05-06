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

from rogerthat.bizz.service.mfd import get_message_flow_by_key_or_name
from rogerthat.bizz.service.mfr import MessageFlowNotFoundException
from rogerthat.dal.service import get_qr_templates
from rogerthat.rpc import users
from rogerthat.rpc.service import service_api
from rogerthat.to.qr import QRDetailsTO
from rogerthat.to.qrtemplates import QRTemplateTO, QRTemplateListResultTO
from rogerthat.utils.crypto import decrypt, encrypt
from rogerthat.utils.service import get_identity_from_service_identity_user
from mcfw.rpc import returns, arguments


@service_api(function=u"qr.create")
@returns(QRDetailsTO)
@arguments(description=unicode, tag=unicode, template_key=unicode, service_identity=unicode, flow=unicode,
           branding=unicode)
def create(description, tag, template_key, service_identity=None, flow=None, branding=None):
    from rogerthat.bizz.service import create_qr
    from rogerthat.bizz.service import get_and_validate_service_identity_user
    service_user = users.get_current_user()
    service_identity_user = get_and_validate_service_identity_user(service_user, service_identity)
    mfd_name = None
    if flow:
        mfd = get_message_flow_by_key_or_name(service_user, flow)
        if not mfd:
            raise MessageFlowNotFoundException()
        mfd_name = mfd.name
    return create_qr(service_user, description, tag, template_key,
                     get_identity_from_service_identity_user(service_identity_user), mfd_name, branding)


@service_api(function=u"qr.list_templates", cache_result=False)
@returns(QRTemplateListResultTO)
@arguments(cursor=unicode)
def list_templates(cursor=None):
    service_user = users.get_current_user()
    if cursor:
        try:
            cursor = decrypt(service_user, cursor)
        except:
            from rogerthat.bizz.exceptions import InvalidCursorException
            raise InvalidCursorException()

    templates, new_cursor = get_qr_templates(service_user, cursor)

    result = QRTemplateListResultTO()
    result.cursor = unicode(encrypt(service_user, new_cursor)) if new_cursor else None
    result.templates = map(QRTemplateTO.fromDBQRTemplate, sorted(templates, key=lambda i:i.description.upper()))
    return result
