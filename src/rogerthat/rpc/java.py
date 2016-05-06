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

import inspect
import os
from StringIO import StringIO
from types import NoneType

from mcfw.properties import get_members, simple_types
from mcfw.serialization import List


def generate(rootdir):
    _generate_transfer_objects(rootdir)
    parse_types = list()
    parse_types.extend(_generate_api_functions(rootdir))
    parse_types.extend(_generate_capi_functions(rootdir))
    parse_types = map(lambda type_: List(type_[0]) if isinstance(type_, list) else type_, parse_types)
    parse_types = map(lambda type_: (str, unicode) if type_ in (str, unicode) else type_, parse_types)
    parse_types = filter(lambda type_: type_ != NoneType, parse_types)
    _generate_type_parsers(rootdir, set(parse_types))
    _generate_priority_map(rootdir)

def _generate_priority_map(rootdir):
    from rogerthat.rpc.calls import high_priority_calls
    c = StringIO()
    c.write("""package com.mobicage.rpc;

import java.util.HashSet;
import java.util.Set;

public class PriorityMap {
    private final static Set<String> sPrioritySet = new HashSet<String>();

    static {
""")
    for f in high_priority_calls:
        c.write('        sPrioritySet.add("%s");\n' % f)
    c.write("""    }

    public static boolean hasPriority(String function) {
        return sPrioritySet.contains(function);
    }

}\n""")
    file_name = os.path.join(rootdir, 'rogerthat', 'rpc', 'PriorityMap.java')
    _write_file(c, file_name)

def _get_real_type(type_):
    if isinstance(type_, List):
        type_ = type_.type
    elif isinstance(type_, (list, tuple)):
        type_ = type_[0]
    return type_

def _get_complex_types_for_function(f, stash):
    def get_sub_types(type_):
        if type_ in stash:
            return
        stash.append(type_)
        complex_members, _ = get_members(type_)
        for _, prop in complex_members:
            get_sub_types(prop.type)
    if not hasattr(f, "meta") or "kwarg_types" not in f.meta or "return_type" not in f.meta:
        raise ValueError("Cannot inspect function %s. Meta data is missing" % f)
    type_ = f.meta["return_type"]
    type_ = _get_real_type(type_)
    if not type_ in simple_types:
        get_sub_types(type_)
    for type_ in f.meta["kwarg_types"].itervalues():
        type_ = _get_real_type(type_)
        if not type_ in simple_types:
            get_sub_types(type_)

def _get_package_name(type_):
    mod = inspect.getmodule(type_)
    return mod.__name__

def _get_full_class_name(type_):
    return "%s.%s" % (_get_package_name(type_), type_.__name__)

def _write_file(c, file_name):
    directory_name = os.path.dirname(file_name)
    if not os.path.exists(directory_name):
        os.makedirs(directory_name)
    f = open(file_name, "w")
    try:
        f.write("""/* 
 * Copyright (C) 2010, Mobicage. All rights reserved.
 * 
 * Copyright is held by the following entity:
 * Mobicage BVBA, Kerkstraat 66, 9290 Overmere, Belgium.
 * 
 * ALTHOUGH YOU MAY BE ABLE TO READ THE CONTENT OF THIS FILE, THIS FILE AND ITS 
 * CONTENT CONSIST OF TRADE SECRETS AND/OR CONFIDENTIAL INFORMATION AND/OR 
 * COPYRIGHT PROTECTED CONTENT OF MOBICAGE BVBA.
 * 
 * THIS FILE OR ALL OR ANY PORTION OF ITS CONTENT MAY ALSO BE SUBJECT TO PATENT
 * AND/OR OTHER INTELLECTUAL PROPERTY RIGHTS OWNED BY MOBICAGE BVBA
 * 
 * NEITHER YOU NOR ANY OTHER PERSON OR ENTITY ARE PERMITTED TO RECEIVE, ACCESS,
 * VIEW, USE, DISCLOSE, PUBLISH, MODIFY, EMBED, DISTRIBUTE, COPY, DISPLAY, CREATE 
 * DERIVATIVE WORKS OR COMPILATIONS OF, ADAPT, LICENSE, SUBLICENSE, SELL,
 * OFFER FOR SALE, ENCUMBER, TRANSFER OR OTHERWISE EXPLOIT THIS FILE OR ANY
 * PORTION OF ITS CONTENTS EXCEPT TO THE EXTENT EXPRESSLY STATED IN A LICENSE
 * AGREEMENT EXECUTED BY A DULY AUTHORIZED REPRESENTATIVE OF MOBICAGE BVBA.
 * 
 * @@license_version:1.0@@
 */
 """)
        f.write(c.getvalue())
    finally:
        f.close()

_java_type_map = \
    {str: "java.lang.String",
     unicode: "java.lang.String",
     float: "double",
     int: "long",
     long: "long",
     bool: "boolean",
     NoneType: "void"}
_java_boxed_type_map = {str: "java.lang.String",
     unicode: "java.lang.String",
     float: "java.lang.Double",
     int: "java.lang.Long",
     long: "java.lang.Long",
     bool: "java.lang.Boolean",
     NoneType: "Void"}
_java_value_type = [float, int, long, bool]

def _convert_from_Object(type_, var_name):
    if type_ in (str, unicode):
        return "(java.lang.String)%s" % var_name
    elif type_ in (int, long):
        return "((java.lang.Long)%s).longValue()" % var_name
    elif type_ == float:
        return "((java.lang.Double)%s).doubleValue()" % var_name
    elif type_ == bool:
        return "((java.lang.Boolean)%s).booleanValue()" % var_name
    else:
        return

def _generate_transfer_object_fields(complex_members, simple_members, c):
    field_template = "    public %s%s %s;\n"
    map(lambda (name, prop):c.write(field_template % (_java_type_map[_get_real_type(prop.type)], "[]" if prop.list else "", name)), simple_members)
    map(lambda (name, prop):c.write(field_template % (_get_full_class_name(prop.type), "[]" if prop.list else "", name)), complex_members)


def _generate_simple_members_into_toJSONMap_method(simple_members, c):
    for name, prop in simple_members:
        if prop.list:
            c.write("        if (this.%s == null) {\n" % name)
            c.write("            obj.put(\"%s\", null);\n" % name)
            c.write("        } else {\n")
            c.write("            org.json.simple.JSONArray arr = new org.json.simple.JSONArray();\n")
            c.write("            for (int i=0; i < this.%s.length; i++) {\n" % name)
            c.write("                arr.add(this.%s[i]);\n" % name)
            c.write("            }\n")
            c.write("            obj.put(\"%s\", arr);\n" % name)
            c.write("        }\n")
        else:
            c.write("        obj.put(\"%s\", this.%s);\n" % (name, name))

def _generate_complex_members_into_toJSONMap_method(complex_members, c):
    for name, prop in complex_members:
        if prop.list:
            c.write("        if (this.%s == null) {\n" % name)
            c.write("            obj.put(\"%s\", null);\n" % name)
            c.write("        } else {\n")
            c.write("            org.json.simple.JSONArray arr = new org.json.simple.JSONArray();\n")
            c.write("            for (int i=0; i < this.%s.length; i++) {\n" % name)
            c.write("                arr.add(this.%s[i] == null ? null : this.%s[i].toJSONMap());\n" % (name, name))
            c.write("            }\n")
            c.write("            obj.put(\"%s\", arr);\n" % name)
            c.write("        }\n")
        else:
            c.write("        obj.put(\"%s\", this.%s == null ? null : this.%s.toJSONMap());\n" % (name, name, name))

def _is_java_value_type_or_string(type_):
    if _is_java_value_type(type_):
        return True
    is_string = lambda x: x in (str, unicode)
    if isinstance(type_, tuple):
        return any(filter(is_string, type_))
    return is_string(type_)

def _is_java_value_type(type_):
    if isinstance(type_, tuple):
        return any(filter(lambda x: x in _java_value_type, type_))
    return type_ in _java_value_type

def _add_suppress_warnings_if_necessary(complex_members, simple_members, c, allow_simple_lists=False, check_singles=False):
    all_members = list()
    all_members.extend(complex_members)
    all_members.extend(simple_members)
    if any(filter(lambda (name, prop):(prop.list and (not _is_java_value_type_or_string(prop.type) or not allow_simple_lists)) or (check_singles and not prop.list and not _is_java_value_type_or_string(prop.type) and (name, prop) in complex_members), all_members)):
        c.write("    @SuppressWarnings(\"unchecked\")\n")

def _generate_toJSONMap_method(complex_members, simple_members, c):
    _add_suppress_warnings_if_necessary(complex_members, simple_members, c)
    c.write("    @Override\n")
    c.write("    public java.util.Map<java.lang.String, java.lang.Object> toJSONMap() {\n")
    c.write("        java.util.Map<java.lang.String, java.lang.Object> obj = new java.util.LinkedHashMap<java.lang.String, java.lang.Object>();\n")
    _generate_simple_members_into_toJSONMap_method(simple_members, c)
    _generate_complex_members_into_toJSONMap_method(complex_members, c)
    c.write("        return obj;\n")
    c.write("    }\n\n")

def _generate_simple_members_for_fromJSONMap_method(complex_members, c):
    for name, prop in complex_members:
        c.write("        val = json.get(\"%s\");\n" % name)
        c.write("        if ( val != null ) {\n")
        if prop.list:
            c.write("            org.json.simple.JSONArray val_arr = (org.json.simple.JSONArray)val;\n")
            c.write("            value.%s = new %s[val_arr.size()];\n" % (name, _java_type_map[_get_real_type(prop.type)]))
            c.write("            for ( int i=0; i < val_arr.size(); i++ ) {\n")
            c.write("                value.%s[i] = %s;\n" % (name, _convert_from_Object(_get_real_type(prop.type), "val_arr.get(i)")))
            c.write("            }\n")
        else:
            c.write("            value.%s = %s;\n" % (name, _convert_from_Object(_get_real_type(prop.type), "val")))
        c.write("        }\n")

def _generate_complex_members_for_fromJSONMap_method(complex_members, c):
    for name, prop in complex_members:
        c.write("        val = json.get(\"%s\");\n" % name)
        c.write("        if ( val != null ) {\n")
        if prop.list:
            c.write("            org.json.simple.JSONArray val_arr = (org.json.simple.JSONArray)val;\n")
            c.write("            value.%s = new %s[val_arr.size()];\n" % (name, _get_full_class_name(_get_real_type(prop.type))))
            c.write("            for ( int i=0; i < val_arr.size(); i++ ) {\n")
            c.write("                java.lang.Object item = val_arr.get(i);\n")
            c.write("                if ( item != null ) {\n")
            c.write("                    value.%s[i] = %s.fromJSONMap((java.util.Map<java.lang.String, java.lang.Object>)item);\n" % (name, _get_full_class_name(_get_real_type(prop.type))))
            c.write("                }\n")
            c.write("            }\n")
        else:
            c.write("            value.%s = %s.fromJSONMap((java.util.Map<java.lang.String, java.lang.Object>)val);\n" % (name, _get_full_class_name(_get_real_type(prop.type))))
        c.write("        }\n")


def _generate_fromJSONMap_method(type_, complex_members, simple_members, c):
    _add_suppress_warnings_if_necessary(complex_members, simple_members, c, True, True)
    c.write("    public static %s fromJSONMap(java.util.Map<java.lang.String, java.lang.Object> json) {\n" % type_.__name__)
    c.write("        %s value = new %s();\n" % (type_.__name__, type_.__name__))
    if simple_members or complex_members:
        c.write("        java.lang.Object val;\n")
        _generate_simple_members_for_fromJSONMap_method(simple_members, c)
        _generate_complex_members_for_fromJSONMap_method(complex_members, c)
    c.write("        return value;\n")
    c.write("    }\n\n")

def _generate_transfer_object(rootdir, type_):
    complex_members, simple_members = get_members(type_)
    package = _get_package_name(type_)
    c = StringIO()
    c.write("package ")
    c.write(package)
    c.write(";\n\n")
    c.write("public class %s implements com.mobicage.rpc.IJSONable {\n" % type_.__name__)
    _generate_transfer_object_fields(complex_members, simple_members, c)
    c.write("\n")
    _generate_toJSONMap_method(complex_members, simple_members, c)
    _generate_fromJSONMap_method(type_, complex_members, simple_members, c)
    c.write("}\n")
    file_name = os.path.join(rootdir, *(package.split(".") + ["%s.java" % type_.__name__]))
    _write_file(c, file_name)
    return

def _write_type(c, type_, value=True):
    rtype_ = _get_real_type(type_)
    if rtype_ in simple_types:
        c.write(_java_type_map[rtype_] if value else _java_boxed_type_map[rtype_])
    else:
        c.write(_get_full_class_name(rtype_))
    if isinstance(type_, list):
        c.write("[]")

def _get_type(type_, value=True):
    c = StringIO()
    _write_type(c, type_, value)
    return c.getvalue()

def _get_function_args(function):
    args = list()
    for name, type_ in function.meta["kwarg_types"].iteritems():
        ca = StringIO()
        _write_type(ca, type_)
        ca.write(" %s" % name)
        args.append(ca.getvalue())
    return args

def _generate_function_header(c, function):
    type_ = function.meta["return_type"]
    if any(filter(lambda type_: isinstance(type_, list), function.meta["kwarg_types"].itervalues())):
        c.write("    @SuppressWarnings(\"unchecked\")\n")
    c.write("    public static void ")
    c.write("%s(com.mobicage.rpc.IResponseHandler<" % function.__name__)
    _write_type(c, type_, False)
    c.write("> responseHandler ")
    args = _get_function_args(function)
    if args:
        c.write(",")
        c.write(", ".join(args))
    c.write(") throws Exception {\n")

def _generate_function(c, function, full_function_name):
    _generate_function_header(c, function)
    c.write("        java.util.Map<java.lang.String, java.lang.Object> arguments = new java.util.LinkedHashMap<java.lang.String, java.lang.Object>();\n")
    for name, type_ in function.meta["kwarg_types"].iteritems():
        if not type_ in _java_value_type:
            c.write("        if (%s == null) {\n" % name)
            c.write("            arguments.put(\"%s\", null);\n" % name)
            c.write("        } else {\n")
        else:
            c.write("        {\n")
        rtype_ = _get_real_type(type_)
        islist = isinstance(type_, list)
        issimple = rtype_ in simple_types
        if islist:
            c.write("            org.json.simple.JSONArray %s_arr = new org.json.simple.JSONArray();\n" % name)
            c.write("            for (int i=0; i < %s.length; i++) {\n" % name)
            c.write("                %s_arr.add(" % name)
            if issimple:
                c.write("%s[i]" % name)
            else:
                c.write("(%s[i] == null) ? null : %s[i].toJSONMap()" % (name, name))
            c.write(");\n")
            c.write("            }\n")
            c.write("            arguments.put(\"%s\", %s_arr);\n" % (name, name))
        else:
            c.write("            arguments.put(\"%s\", %s%s);\n" % (name, name, "" if issimple else ".toJSONMap()"))
        c.write("        }\n")
    c.write("        com.mobicage.rpc.Rpc.call(\"%s\", arguments, responseHandler);\n" % full_function_name)
    c.write("    }\n")
    return function.meta["return_type"]

_camel = lambda x: x[0].upper() + x[1:]

def _get_parser_function(type_):
    rtype_ = _get_real_type(type_)
    islist = isinstance(type_, (List, list))
    fn = "parseAs" + "".join(map(_camel, _java_type_map[rtype_].split("."))) if rtype_ in simple_types else "".join(map(_camel, _get_full_class_name(rtype_).split(".")))
    if islist:
        fn += "Array"
    return fn

def _generate_type_parser(c, type_):
    rtype_ = _get_real_type(type_)
    islist = isinstance(type_, (List, list))
    type_name = _java_type_map[rtype_] if rtype_ in simple_types else _get_full_class_name(rtype_)
    function_name = _get_parser_function(type_)
    if not rtype_ in simple_types:
        c.write("    @SuppressWarnings(\"unchecked\")\n")
    c.write("    public static %s%s %s(Object value) {\n" % (type_name, "[]" if islist else "", function_name))
    if rtype_ not in simple_types or islist:
        c.write("        if ( value == null)\n")
        c.write("            return null;\n")
    if rtype_ in simple_types:
        if islist:
            c.write("        ")
            _write_type(c, type_)
            c.write("[] values = new %s[((org.json.simple.JSONArray)value).size()];\n" % _java_type_map[rtype_])
            c.write("        for (int i=0; i < values.length; i++) {\n")
            c.write("            values[i] = (%s)(((org.json.simple.JSONArray)value).get(i));\n" % _java_type_map[rtype_])
            c.write("        }\n")
            c.write("        return values;\n")
        else:
            c.write("        return %s;\n" % _convert_from_Object(rtype_, "value"))
    else:
        if islist:
            c.write("        ")
            _write_type(c, type_)
            c.write("[] values = new %s[((org.json.simple.JSONArray)value).size()];\n" % _get_full_class_name(rtype_))
            c.write("        for (int i=0; i < values.length; i++) {\n")
            c.write("            values[i] = %s.fromJSONMap((java.util.Map)((org.json.simple.JSONArray)value)get(i));\n" % _get_full_class_name(rtype_))
            c.write("        }\n")
            c.write("        return values;\n")
        else:
            c.write("        return %s.fromJSONMap((java.util.Map<java.lang.String, java.lang.Object>)value);\n" % _get_full_class_name(rtype_))
    c.write("    }\n\n")

def _generate_api_function_set(rootdir, class_name_parts, functions):
    package_name = ".".join(class_name_parts)
    class_name = "Rpc"
    c = StringIO()
    c.write("package ")
    c.write(package_name)
    c.write(";\n\n")
    c.write("public class %s {\n\n" % class_name)
    for details in functions.itervalues():
        yield details["full_function_name"], _generate_function(c, details["function"], details["full_function_name"])
        c.write("\n")
    c.write("}\n")
    file_name = os.path.join(rootdir, *(package_name.split(".") + ["%s.java" % class_name]))
    _write_file(c, file_name)
    return

def _generate_capi_function_set(rootdir, class_name_parts, functions):
    package_name = ".".join(class_name_parts)
    class_name = "IClientRpc"
    c = StringIO()
    c.write("package ")
    c.write(package_name)
    c.write(";\n\n")
    c.write("public interface %s {\n\n" % class_name)
    arg_types = list()
    function_details = dict()
    full_interface_name = "%s.%s" % (package_name, class_name)
    for name, details in functions.iteritems():
        function = details["function"]
        c.write("    ")
        _write_type(c, function.meta["return_type"])
        c.write(" %s(" % name)
        args = _get_function_args(function)
        c.write(", ".join(args))
        c.write(") throws java.lang.Exception;\n\n")
        arg_types.extend(function.meta["kwarg_types"].itervalues())
        function_details[function] = (details, full_interface_name, name)
    c.write("}\n")
    file_name = os.path.join(rootdir, *(package_name.split(".") + ["%s.java" % class_name]))
    _write_file(c, file_name)
    return full_interface_name, arg_types, function_details

def _arange_functions_by_class(function_mapping):
    class_map = dict()
    for name, function in function_mapping.iteritems():
        name_parts = name.split(".")
        class_name, function_name = ".".join(name_parts[:-1]), name_parts[-1]
        if not class_name in class_map:
            class_map[class_name] = dict()
        class_map[class_name][function_name] = {"function":function, "full_function_name":name}
    return class_map

_interface_member_name = lambda x: x.split(".")[0] + "".join(map(_camel, x.split(".")[1:]))
def _generate_capi_functions(rootdir):
    from rogerthat.rpc.calls import client_mapping
    class_map = _arange_functions_by_class(client_mapping)
    arg_types = list()
    interfaces = list()
    functions = dict()
    for class_name, class_functions in class_map.iteritems():
        interface_name, class_function_arg_types, class_functions = _generate_capi_function_set(rootdir, class_name.split("."), class_functions)
        interfaces.append(interface_name)
        arg_types.extend(class_function_arg_types)
        functions.update(class_functions)
    c = StringIO()
    c.write("package com.mobicage.rpc;\n\n")
    c.write("public class CallReceiver {\n\n")
    for interface in interfaces:
        c.write("    public static volatile %s %s = null;\n\n" % (interface, _interface_member_name(interface)))
    c.write("    public static IJSONable processCall(final RpcCall call) throws Exception {\n")
    c.write("        String function = call.function;\n")
    for fn, function in client_mapping.iteritems():
        c.write("        if ( \"%s\".equals(function) ) {\n" % fn)
        type_ = function.meta["return_type"]
        c.write("            ")
        if type_ != NoneType:
            c.write("return ")
        c.write("%s.%s(" % (_interface_member_name(functions[function][1]), functions[function][2]))
        args = list()
        for name, atype_ in function.meta['kwarg_types'].iteritems():
            args.append("com.mobicage.rpc.Parser.%s(call.arguments.get(\"%s\"))" % (_get_parser_function(atype_), name))
        c.write(", ".join(args))
        c.write(");\n")
        if type_ == NoneType:
            c.write("                return null;\n")
        c.write("        }\n")
    c.write("        return null;\n")
    c.write("    }\n")
    c.write("}\n")
    file_name = os.path.join(rootdir, 'rogerthat', 'rpc', 'CallReceiver.java')
    _write_file(c, file_name)
    return arg_types

def _generate_api_functions(rootdir):
    from rogerthat.rpc.calls import mapping
    class_map = _arange_functions_by_class(mapping)
    function_return_types = list()
    for class_name, functions in class_map.iteritems():
        function_return_types.extend(_generate_api_function_set(rootdir, class_name.split("."), functions))
    return_types = set(map(lambda (name, type_): type_, function_return_types))

    packed = dict()
    for f, t in function_return_types:
        if not t in packed:
            packed[t] = list()
        packed[t].append(f)

    c = StringIO()
    c.write("package com.mobicage.rpc;\n\n")
    c.write("public class ResponseReceiverHandler {\n\n")
    c.write('    @SuppressWarnings("unchecked")\n')
    c.write("    public static void handle (final RpcResult rpcr, final IResponseHandler<?> responseHandler) {\n")
    c.write("        final java.lang.String function = responseHandler.getFunction();\n")
    for t, fs in packed.iteritems():
        c.write("        if (")
        c.write(" || ".join(('function.equals("%s")' % f for f in fs)))
        c.write(") {\n")
        c.write("            final Response<")
        _write_type(c, t, False)
        c.write("> resp = new Response<")
        _write_type(c, t, False)
        c.write(">();\n")
        c.write("            resp.setError(rpcr.error);\n")
        c.write("            resp.setSuccess(rpcr.success);\n")
        c.write("            resp.setCallId(rpcr.callId);\n")
        c.write('            if (rpcr.success)\n')
        c.write("                resp.setResult(com.mobicage.rpc.Parser.")
        c.write(_get_parser_function(t))
        c.write("(rpcr.result));\n")
        c.write("            ((IResponseHandler<")
        _write_type(c, t, False)
        c.write(">)responseHandler).handle(resp);\n")
        c.write("        }\n")
    c.write("    }\n")
    c.write("}\n")
    file_name = os.path.join(rootdir, 'rogerthat', 'rpc', 'ResponseReceiverHandler.java')
    _write_file(c, file_name)

    return return_types

def _generate_transfer_objects(rootdir):
    from rogerthat.rpc.calls import mapping, client_mapping
    tos = list()
    all_funcs = dict()
    all_funcs.update(mapping)
    all_funcs.update(client_mapping)
    map(lambda f: _get_complex_types_for_function(f, tos), all_funcs.itervalues())
    map(lambda to: _generate_transfer_object(rootdir, to), tos)

def _generate_type_parsers(rootdir, types):
    c = StringIO()
    c.write("package com.mobicage.rpc;\n\n")
    c.write("public class Parser {\n\n")
    c.write("    public static Void parseAsVoid(Object result) {\n")
    c.write("        return null;")
    c.write("    }\n\n")
    for type_ in types:
        _generate_type_parser(c, type_)
    c.write("}\n")
    file_name = os.path.join(rootdir, 'rogerthat', 'rpc', 'Parser.java')
    _write_file(c, file_name)
