#!/usr/bin/env python3

from collections.abc import Mapping
import datetime
import logging
from json import dumps
from os import mkdir, path
import sys
import urllib.request

from ruamel.yaml import YAML
from ruamel.yaml.comments import TaggedScalar
from ruamel.yaml.scalarbool import ScalarBoolean


logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

 
def scalar(obj):
    if obj is None:
        return None
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return str(obj)
    if isinstance(obj, ScalarBoolean):
        return obj == 1
    if isinstance(obj, bool):
        return bool(obj)
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, float):
        return float(obj)
    if isinstance(obj, tuple):
        return "_".join([str(x) for x in obj])
    if isinstance(obj, Mapping):
        return "_".join([f"{k}-{v}" for k, v in obj.items()])
    if not isinstance(obj, str):
        print("type", type(obj))

    return obj


def prep(obj):
    if isinstance(obj, dict):
        return {scalar(k): prep(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [prep(elem) for elem in obj]
    if isinstance(obj, TaggedScalar):
        return prep(obj.value)

    return scalar(obj)


def json_dump(data):
    return dumps(prep(data), indent=2)


def additional_properties(data):
    if isinstance(data, dict):
        if "properties" in data:
            if "additionalProperties" not in data:
                data["additionalProperties"] = False
        for _, v in data.items():
            additional_properties(v)
    return data


def replace_int_or_string(data):
    new = {}
    try:
        for k, v in iter(data.items()):
            new_v = v
            if isinstance(v, dict):
                if "format" in v and v["format"] == "int-or-string":
                    new_v = {"oneOf": [{"type": "string"}, {"type": "integer"}]}
                else:
                    new_v = replace_int_or_string(v)
            elif isinstance(v, list):
                new_v = list()
                for x in v:
                    new_v.append(replace_int_or_string(x))
            else:
                new_v = v
            new[k] = new_v
        return new
    except AttributeError:
        return data


def generate_json_schema(documents):
    for document in documents:
        if document is None:
            continue

        if document.get("items") is not None:
            generate_json_schema(document.get("items"))
            continue

        if document.get("kind") != "CustomResourceDefinition":
            continue

        spec = document.get("spec", {})
        for document_version in spec.get("versions"):
            kind = spec.get("names", {}).get("kind")
            group = spec.get("group")
            version = document_version.get("name")
            filename = f"{group}/{kind}_{version}.json".lower()
            if not path.isdir(group):
                mkdir(group)

            with open(filename, "w", encoding="utf-8") as f:
                schema = document_version.get("schema", {}).get("openAPIV3Schema")
                schema = additional_properties(schema)
                schema = replace_int_or_string(schema)
                f.write(json_dump(schema))


def cli(source: list[str]):
    for src in source:
        logger.info(f"reading from {src}")
        if src.startswith("http"):
            f = urllib.request.urlopen(src)
        else:
            f = open(src)
        with f:
            generate_json_schema(YAML(typ="rt", pure=True).load_all(f))

    if not sys.stdin.isatty():
        logger.info("reading from stdin")
        generate_json_schema(YAML(typ="rt", pure=True).load_all(sys.stdin))


if __name__ == '__main__':
    cli(sys.argv[1:])
