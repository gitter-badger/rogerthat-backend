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

from mcfw.properties import unicode_property, typed_property


class JSEmbeddingItemTO(object):
    name = unicode_property('1')
    hash = unicode_property('2')

class UpdateJSEmbeddingRequestTO(object):
    items = typed_property('1', JSEmbeddingItemTO, True)

    @staticmethod
    def fromDBJSEmbedding(embeddings):
        jsembedding = UpdateJSEmbeddingRequestTO()
        jsembedding.items = list()
        for embedding in embeddings:
            item = JSEmbeddingItemTO()
            item.name = embedding.name
            item.hash = embedding.hash
            jsembedding.items.append(item)
        return jsembedding

class UpdateJSEmbeddingResponseTO(object):
    pass

class GetJSEmbeddingRequestTO(object):
    pass

class GetJSEmbeddingResponseTO(UpdateJSEmbeddingRequestTO):

    @staticmethod
    def fromDBJSEmbedding(embeddings):
        super_to = UpdateJSEmbeddingRequestTO.fromDBJSEmbedding(embeddings)
        to = GetJSEmbeddingResponseTO()
        to.__dict__ = super_to.__dict__
        return to
