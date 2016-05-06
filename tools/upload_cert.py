#!/usr/bin/python
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

import argparse
import os
import sys
from OpenSSL import crypto
from getpass import getpass
import datetime
import time
import base64
import hashlib
from Crypto.Cipher import AES
from urllib2 import Request, urlopen
from urllib import urlencode

BLOCK_SIZE = 32
PADDING = '{'
DEFAULT_CLOUD = "https://rogerth.at"

pad = lambda data: data + (BLOCK_SIZE - len(data) % BLOCK_SIZE) * PADDING
encryptAES = lambda secret, data: base64.b64encode(AES.new(hashlib.sha256(secret).digest()).encrypt(pad(data)))

def main(args):
    if not os.path.exists(args.p12file):
        print sys.stderr, "File '%s' not found!" % args.p12file
        exit(1)

    pwd = args.p12password or getpass("Enter password to decrypt p12 file: ")
    p12 = crypto.load_pkcs12(file(args.p12file, 'rb').read(), pwd)

    cert = p12.get_certificate()
    valid_until = cert.get_notAfter()
    valid_until = int(time.mktime(datetime.datetime.strptime(valid_until, "%Y%m%d%H%M%SZ").timetuple()))
    cert_pem = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
    key_pem = crypto.dump_privatekey(crypto.FILETYPE_PEM, p12.get_privatekey())

    secret = args.secret or getpass("Enter certificate protection secret: ")

    cert_pem = encryptAES(secret, cert_pem)
    key_pem = encryptAES(secret, key_pem)

    digester = hashlib.sha256()
    digester.update(args.appid)
    digester.update(cert_pem)
    digester.update(args.appid)
    digester.update(key_pem)
    digester.update(args.appid)
    digester.update(str(valid_until))
    digester.update(args.appid)
    checksum = digester.hexdigest()

    cloudsecret = args.cloudsecret or getpass("Enter cloud secret: ")

    data = urlencode({"app_id":args.appid, "cert":cert_pem, "key": key_pem, "checksum": checksum, "valid_until": str(valid_until)})

    q = Request("%s/unauthenticated/mobi/apps/upload_cert" % args.cloud.rstrip('/'))
    q.add_header('X-Nuntiuz-Secret', cloudsecret)
    resp = urlopen(q, data=data).read()
    if not resp:
        raise Exception("Failed to upload cert. Check server logs.")
    print resp

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Update Apple Push keys and certificates.')
    parser.add_argument('appid', help='App identifier')
    parser.add_argument('p12file', help='Password protected p12 file')
    parser.add_argument('--p12password', help='Password to decrypt p12 file. If omitted will be read from stdin.')
    parser.add_argument('--secret', help='Secret with which pem files will be protected. If omitted will be read from stdin.')
    parser.add_argument('--cloud', help='Url to cloud to which the Apple Certs need to be uploaded', default=DEFAULT_CLOUD)
    parser.add_argument('--cloudsecret', help='Secret used by the cloud to identify the upload request')
    args = parser.parse_args()
    main(args)
