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

import base64
import hashlib
import struct
import uuid

from rogerthat.consts import DEBUG
from rogerthat.utils import now, azzert

#### Copied from http://www.codekoala.com/blog/2009/aes-encryption-python-using-pycrypto/ ####
try:
    from Crypto.Cipher import AES  # @UnresolvedImport
except ImportError:  # Catch the error to make it run on designers machine
    pass
# the block size for the cipher object; must be 16, 24, or 32 for AES
BLOCK_SIZE = 32

# the character used for padding--with a block cipher such as AES, the value
# you encrypt must be a multiple of BLOCK_SIZE in length.  This character is
# used to ensure that your value is always a multiple of BLOCK_SIZE
PADDING = '{'

# one-liner to sufficiently pad the text to be encrypted
pad = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * PADDING

# one-liners to encrypt/encode and decrypt/decode a string
# encrypt with AES, encode with base64
EncodeAES = lambda c, s: base64.b64encode(c.encrypt(pad(s)))
DecodeAES = lambda c, e: c.decrypt(base64.b64decode(e)).rstrip(PADDING)

def cipher(secret):
    from rogerthat.settings import get_server_settings
    server_settings = get_server_settings()
    d = hashlib.sha256()
    d.update(base64.b64decode(server_settings.userEncryptCipherPart1.encode("utf8")))
    d.update(secret)
    d.update(base64.b64decode(server_settings.userEncryptCipherPart2.encode("utf8")))
    cipher = AES.new(d.digest())
    return cipher

def encrypt(user, value):
    return encrypt_value(user.email().encode('utf8'), value)

def decrypt(user, value):
    return decrypt_value(user.email().encode('utf8'), value)


def encrypt_value(secret, value):
    if DEBUG:
        return value
    else:
        return EncodeAES(cipher(secret), value)

def decrypt_value(secret, value):
    if DEBUG:
        return value
    else:
        return DecodeAES(cipher(secret), value)



# generate a random secret key
# secret = os.urandom(BLOCK_SIZE)
#
# # create a cipher object using the random secret
# cipher = AES.new(secret)
#
# # encode a string
# encoded = EncodeAES(cipher, 'password')
# print 'Encrypted string:', encoded
#
# # decode the encoded string
# decoded = DecodeAES(cipher, encoded)
# print 'Decrypted string:', decoded
#### End copied ####

def sha256(val):
    d = hashlib.sha256()
    d.update(val if not isinstance(val, unicode) else val.encode('utf-8'))
    return d.digest()

def sha256_hex(val):
    d = hashlib.sha256()
    d.update(val if not isinstance(val, unicode) else val.encode('utf-8'))
    return d.hexdigest()

def md5(val):
    d = hashlib.md5()
    d.update(val if not isinstance(val, unicode) else val.encode('utf-8'))
    return d.digest()

def md5_hex(val):
    d = hashlib.md5()
    d.update(val if not isinstance(val, unicode) else val.encode('utf-8'))
    return d.hexdigest()

def encrypt_for_jabber_cloud(secret, data):
    azzert(isinstance(secret, str))
    azzert(isinstance(data, str))
    challenge = str(uuid.uuid4())
    timestamp = now()
    data = struct.pack('b36si', 1, challenge, len(data)) + data
    if DEBUG:
        encrypted_data = data
    else:
        cipher = AES.new(hashlib.sha256(secret).digest())
        encrypted_data = cipher.encrypt(pad(data))
    d = hashlib.sha256(secret)
    d.update(data)
    d.update(struct.pack("q", timestamp))
    d.update(challenge)
    return challenge, struct.pack('bq32s', 1, timestamp, d.digest()) + encrypted_data

def decrypt_from_jabber_cloud(secret, challenge, data):
    pack_format = 'b36s'
    pack_size = struct.calcsize(pack_format)
    version, salt = struct.unpack(pack_format, data[:pack_size])
    if DEBUG:
        decrypted_data = data[pack_size:]
    else:
        cipher = AES.new(hashlib.sha256(secret).digest())
        decrypted_data = cipher.decrypt(data[pack_size:])
    pack_format = 'b36s36si'
    pack_size = struct.calcsize(pack_format)
    encrypted_version, encrypted_challenge, encrypted_salt, data_size = struct.unpack(pack_format, decrypted_data[:pack_size])
    azzert(version == encrypted_version)
    azzert(version == 1)
    azzert(salt == encrypted_salt)
    azzert(challenge == encrypted_challenge)
    return decrypted_data[pack_size:pack_size + data_size]
