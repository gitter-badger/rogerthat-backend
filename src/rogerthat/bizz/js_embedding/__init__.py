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

import hashlib
import logging
import os
from types import NoneType
from zipfile import ZipFile, ZIP_DEFLATED

from google.appengine.ext import db

from mcfw.rpc import returns, arguments
from rogerthat.bizz.job.update_js_embedding import schedule_update_embedded_js_for_all_users
from rogerthat.models import JSEmbedding
from rogerthat.utils import now

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

CURRENT_DIR = os.path.dirname(__file__)


@returns([JSEmbedding])
@arguments()
def get_js_embedding_packets_disk():
    packets = list()
    dirs = os.walk(CURRENT_DIR).next()[1]
    for d in dirs:
        jse = JSEmbedding(key_name=d)
        zip_content, hash_ = zipdir(os.path.join(CURRENT_DIR, d))
        jse.content = zip_content
        jse.hash = hash_
        jse.hash_files = calculate_hash(os.path.join(CURRENT_DIR, d))
        jse.creation_time = now()
        packets.append(jse)
    return packets


@returns(NoneType)
@arguments()
def deploy_new_js_embedding():
    l = list()
    packets = list()
    dirs = os.walk(CURRENT_DIR).next()[1]
    logging.info("deploy_new_js_embedding with dirs: %s" % dirs)
    for d in dirs:
        jse = JSEmbedding(key_name=d)
        zip_content, hash_ = zipdir(os.path.join(CURRENT_DIR, d))
        jse.content = zip_content
        jse.hash = hash_
        jse.hash_files = calculate_hash(os.path.join(CURRENT_DIR, d))
        jse.creation_time = now()
        packets.append(jse)
        l.append(jse.key())

    def run():
        db.put(packets)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, run)

    schedule_update_embedded_js_for_all_users(l)


def zipdir(path):
    new_zip_stream = StringIO()
    new_zip_ = ZipFile(new_zip_stream, 'w', compression=ZIP_DEFLATED)
    for root, _, files in os.walk(path):
        for f in files:
            new_zip_.write(os.path.join(root, f), os.path.join(root, f).replace(path, ''))

    new_zip_.close()
    zip_content = new_zip_stream.getvalue()
    return zip_content, hashlib.sha256(zip_content).hexdigest().upper()


def calculate_hash(path):
    hash_ = hashlib.sha256()
    for root, _, files in os.walk(path):
        for f in files:
            with open(os.path.join(root, f)) as ff:
                hash_.update(ff.read())
    return hash_.hexdigest().upper()
