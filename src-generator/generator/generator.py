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

import os
os.environ['SERVER_SOFTWARE'] = 'generator'  # Do not remove this line
os.environ['AUTH_DOMAIN'] = 'gmail.com'  # Do not remove this line

from class_definition import ClassDefinition, AttrDefinition, PackageDefinition, FunctionDefinition
from django.conf import settings
from google.appengine.ext.webapp import template
import licenses
from mcfw.consts import MISSING
from mcfw.properties import simple_types, get_members, object_factory


register = template.create_template_register()
template.register_template_library('generator.custom.filters')
template.register_template_library('generator.custom.java_filters')
template.register_template_library('generator.custom.objc_filters')
template.register_template_library('generator.custom.csharp_filters')

settings.TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

DEVPATHS = [
                "/Users/carl/work/dev/git/",
                "/Users/bart/mobicage/git/",
                "/Users/geert/mobicage/git/",
                "/Users/rubenmattan/mobicage/git/",
                "D:\_mobicage\GIT_rogerthat.net",
                "/testing/"
           ]

DELIMITER = '*' * 50

def _get_collection_type(type_):
    return isinstance(type_, list) and list.__name__ or None

def _get_type_string(type_):
    real_type = _get_real_type(type_)
    if real_type in simple_types:
        return real_type.__name__
    else:
        return '%s.%s' % (real_type.__module__, real_type.__name__)

def _get_real_type(type_):
    if (type_ == str):
        raise RuntimeError('str type not allowed (use unicode)')
    if (type_ in [(str, unicode), (unicode, str)]):
        raise RuntimeError('str+unicode tuple type found (use unicode)')
    if isinstance(type_, (list, tuple)):
        return type_[0]
    return type_

def _sort_values_by_keys(mapping):
    return [mapping[k] for k in sorted(mapping.keys())]

def populate_class_def_fields(class_def, type_, prop, name):
    type_name = _get_type_string(type_)
    collection = list.__name__ if prop.list else None
    attr_def = AttrDefinition(name=name, type_=type_name, collection_type=collection, doc=prop.doc, default=prop.default)
    class_def.fields.append(attr_def)

def build_class_definition(type_, stash):
    complex_props, simple_props = get_members(type_)
    for (_, prop) in complex_props:
        if isinstance(prop.type, object_factory):
            continue  # XXX: implement when needed
        process_type(prop.type, stash)

    class_def = ClassDefinition(package=type_.__module__, name=type_.__name__, doc=type_.__doc__)

    for (name, prop) in (complex_props + simple_props):
        if isinstance(prop.type, object_factory):
            continue  # XXX: implement when needed
        populate_class_def_fields(class_def, prop.type, prop, name)

    return class_def

def process_type(type_, stash):
    type_ = _get_real_type(type_)
    if type_ in simple_types or type_ in stash:
        return
    class_def = build_class_definition(type_, stash)
    stash[_get_type_string(type_)] = class_def

def check_function_validity(f, max_argument_count):
    if not hasattr(f, "meta") or "kwarg_types" not in f.meta or "return_type" not in f.meta:
        raise ValueError("Cannot inspect function %s. Meta data is missing" % f)

    if _get_collection_type(f.meta.get('return_type')) == list.__name__:
        raise ValueError('List return type not supported')

    from custom.filters import SIMPLE_TYPES
    if f.meta.get('return_type') in SIMPLE_TYPES:
        raise ValueError("Only TOs are supported as return type")

    if len(f.meta.get("kwarg_types")) > max_argument_count:
        raise ValueError("Only %s argument(s) allowed" % max_argument_count)

def process_function(f, stash, max_argument_count):
    check_function_validity(f, max_argument_count)
    # process return type
    process_type(f.meta["return_type"], stash)
    # process argument types
    for kwarg_type in f.meta["kwarg_types"].itervalues():
        process_type(kwarg_type, stash)

def generate_TOs(mapping, client_mapping, max_argument_count):
    tos = dict()
    all_funcs = dict()
    all_funcs.update(mapping)
    all_funcs.update(client_mapping)
    for f in all_funcs.itervalues():
        process_function(f, tos, max_argument_count)
    return _sort_values_by_keys(tos)

def generate_CAPI_packages(capi_functions, max_argument_count):
    return generate_packages(capi_functions, max_argument_count)

def generate_API_packages(api_functions, max_argument_count):
    return generate_packages(api_functions, max_argument_count)

# TODO: should refactor and reuse the type analysis code in this method and in build_class_definition
def generate_packages(functions, max_argument_count):
    stash = dict()
    for full_function_name in sorted(functions.keys()):
        f = functions[full_function_name]
        check_function_validity(f, max_argument_count)

        package, short_function_name = full_function_name.rsplit('.', 1)
        if (package not in stash):
            stash[package] = PackageDefinition(package)

        func = FunctionDefinition(short_function_name)

        stash[package].functions.append(func)

        arg_list = f.meta.get('fargs')[0]
        arg_dict = f.meta.get('kwarg_types')

        for arg in arg_list:
            arg_def = AttrDefinition(arg, _get_type_string(arg_dict[arg]), _get_collection_type(arg_dict[arg]))
            func.args.append(arg_def)

        func.rtype = AttrDefinition(type_=_get_type_string(f.meta.get('return_type')))

    return _sort_values_by_keys(stash)

def render(tos, api_packages, capi_packages, paths, target):
    license_text = _read_file(os.path.join(os.path.dirname(__file__), "..", "..", "..", "tools", "change_license", "apache_license.tmpl"))
    for path in paths:
        if not os.path.isdir(path):
            continue
        tmpl = os.path.join(os.path.dirname(__file__), 'templates', '%s.tmpl' % target)
        license_string = licenses.get_license(license_text, target)
        context = {'DELIMITER':DELIMITER, "LICENSE":license_string, 'tos':tos, 'CS_API_packages':api_packages,
                   'SC_API_packages':capi_packages, 'path':path, 'MISSING':MISSING}
        gen_content = template.render(tmpl, context)
        # _write_file(gen_content, "%s.gen.tmp" % target)
        _process_gen_file(gen_content, path)

def _process_gen_file(gen_content, path):
    current_file = None
    current_content = list()
    for line in gen_content.splitlines():
        if line == DELIMITER:
            if current_file:
                _write_file('\n'.join(current_content), current_file)
                current_file = None
                current_content = list()
        elif not current_file:
            if not line:
                continue
            current_file = os.path.join(path, line)
        else:
            current_content.append(line)

def _write_file(content, file_name):
    path = os.path.dirname(file_name)
    if path and not os.path.exists(path):
        os.makedirs(path)
    f = open(file_name, "w")
    try:
        f.write(content)
    finally:
        f.close()
    print "gen file: %s" % file_name

def _read_file(file_name):
    if not os.path.exists(file_name):
        raise RuntimeError("File '%s' does not exist" % os.path.abspath(file_name))
    f = open(file_name, "r")
    try:
        return f.read()
    finally:
        f.close()

def generate(target, mapping, client_mapping, rootDirs=DEVPATHS, max_argument_count=1):
    print "generating", target
    render(generate_TOs(mapping, client_mapping, max_argument_count),
           generate_API_packages(mapping, max_argument_count),
           generate_CAPI_packages(client_mapping, max_argument_count),
           rootDirs,
           target)
