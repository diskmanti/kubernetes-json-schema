#!/usr/bin/env python3

from collections.abc import Mapping
from dataclasses import dataclass
import datetime
import logging
import json
import os
from typing import Optional
import re
import sys
import urllib.request

from github import Github, GitRelease

from ruamel.yaml import YAML
from ruamel.yaml.comments import TaggedScalar
from ruamel.yaml.scalarbool import ScalarBoolean


logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
github = Github(os.getenv("GITHUB_TOKEN"))

 
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
    return json.dumps(prep(data), indent=2)


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
            if not os.path.isdir(group):
                os.mkdir(group)

            logger.info(f"writing crd {group}.{kind}_{version}")
            with open(filename, "w", encoding="utf-8") as f:
                schema = document_version.get("schema", {}).get("openAPIV3Schema")
                schema = additional_properties(schema)
                schema = replace_int_or_string(schema)
                f.write(json_dump(schema))


def openapi2jsonschema(url: str):
    with urllib.request.urlopen(url) as f:
        generate_json_schema(YAML(typ="rt", pure=True).load_all(f))


@dataclass
class CrdsConfig:
   github_repository: str
   asset_name: Optional[str]
   crds_urls: list[str]

   def get_release(self) -> GitRelease:
        for release in github.get_repo(self.github_repository).get_releases():
            if release.draft == True or release.prerelease == True:
                continue

            if re.search(r'v?\d+.\d+.\d+', release.tag_name):
                return release

        raise Exception("no release found")

   def openapi2jsonschema(self) -> None:
        release = self.get_release()
        print(self.github_repository)
        print(release.tag_name)
        if self.asset_name is not None:
            for asset in release.get_assets():
                if asset.name == self.asset_name:
                    openapi2jsonschema(asset.browser_download_url)
                
        for url in self.crds_urls:
            openapi2jsonschema(url.format(version = release.tag_name))


def load_config() -> dict[str, CrdsConfig]:
    with open(f"config.json", "r", encoding="utf-8") as f:
        crds_configs = {}
        for k, v in json.load(f).items():
            crds_configs[k] = CrdsConfig(
                github_repository=v.get("github_repository"),
                asset_name=v.get("asset_name", None),
                crds_urls= v.get("urls", []),
            ) 

        return crds_configs


if __name__ == '__main__':
    config = load_config()
    if (len(sys.argv) == 2):
       config.get(sys.argv[1]).openapi2jsonschema()
    else:
        for crds_config in config.values():
            crds_config.openapi2jsonschema()
