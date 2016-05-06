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
from zipfile import ZipFile, ZIP_DEFLATED

from mcfw.rpc import returns, arguments


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

@returns(str)
@arguments(zip_file=ZipFile, to_be_replaced_file_name=unicode, new_file_content=str)
def replace_file_in_zip(zip_file, to_be_replaced_file_name, new_file_content):
    replaced = False
    try:
        new_zip_stream = StringIO()
        new_zip = ZipFile(new_zip_stream, 'w', compression=ZIP_DEFLATED)
        try:
            for file_name in set(zip_file.namelist()):
                if file_name == to_be_replaced_file_name:
                    logging.debug("Replacing '%s' with new content" % file_name)
                    new_zip.writestr(file_name, str(new_file_content))
                    replaced = True
                else:
                    new_zip.writestr(file_name, zip_file.read(file_name))
        finally:
            new_zip.close()
    finally:
        zip_file.close()
    if not replaced:
        logging.warn("Did not replace %s because it was not found in the provided zip", to_be_replaced_file_name)
    return new_zip_stream.getvalue()


@returns(str)
@arguments(zip_file=ZipFile, to_be_renamed_file_name=unicode, new_file_name=unicode)
def rename_file_in_zip(zip_file, to_be_renamed_file_name, new_file_name):
    renamed = False
    try:
        new_zip_stream = StringIO()
        new_zip = ZipFile(new_zip_stream, 'w', compression=ZIP_DEFLATED)
        try:
            for file_name in set(zip_file.namelist()):
                dest_file_name = file_name
                if file_name == to_be_renamed_file_name:
                    logging.debug("Renaming '%s' to '%s' in zip file" % (dest_file_name, new_file_name))
                    dest_file_name = new_file_name
                    renamed = True
                new_zip.writestr(dest_file_name, zip_file.read(file_name))
        finally:
            new_zip.close()
    finally:
        zip_file.close()
    if not renamed:
        logging.warn("Did not rename %s to %s because it was not found in the provided zip", to_be_renamed_file_name,
                     new_file_name)
    return new_zip_stream.getvalue()


@returns(str)
@arguments(zip_blob=str, to_be_replaced_file_name=unicode, new_file_content=str)
def replace_file_in_zip_blob(zip_blob, to_be_replaced_file_name, new_file_content):
    zip_file = ZipFile(StringIO(zip_blob))
    return replace_file_in_zip(zip_file, to_be_replaced_file_name, new_file_content)


@returns(str)
@arguments(zip_blob=str, to_be_renamed_file_name=unicode, new_file_name=unicode)
def rename_file_in_zip_blob(zip_blob, to_be_renamed_file_name, new_file_name):
    zip_file = ZipFile(StringIO(zip_blob))
    return rename_file_in_zip(zip_file, to_be_renamed_file_name, new_file_name)
