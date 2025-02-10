"""
yaml safeloader classes for the inkBoard config
"""

import sys
import logging
from types import MappingProxyType
from typing import TYPE_CHECKING
from string import Template
from pathlib import Path

import yaml

from yaml import SafeLoader as FastestAvailableSafeLoader
try:
    from yaml import CSafeLoader as FastestAvailableSafeLoader
except ImportError:
    pass

from inkBoard.helpers import YAMLNodeDict

from . import const

if TYPE_CHECKING:
    from yaml import SafeLoader as FastestAvailableSafeLoader

_LOGGER = logging.getLogger(__name__)

def secret_constructor(loader: "BaseSafeLoader", node: yaml.nodes.ScalarNode) -> str:
    
    key = loader.construct_scalar(node)
    if key in loader._secrets:
        return loader._secrets[key]
    else:
        _LOGGER.error(f"{key} is not defined in secrets.yaml")

def entity_constructor(loader: "BaseSafeLoader", node: yaml.nodes.ScalarNode) -> str:
    
    ##Probably see if the yaml line can be logged here.
    key = loader.construct_scalar(node)
    if key in loader._entities:
        return loader._entities[key]
    else:
        _LOGGER.error(f"{key} is not defined in entitities.yaml")

def include_constructor(loader: "BaseSafeLoader", node: yaml.nodes.ScalarNode) -> str:
    """Get appropriate entries from secrets.yaml"""
    file = loader.construct_scalar(node)
    file_path = Path(file)
    if not file_path.is_absolute():
        file_path = loader._base_folder / file_path
    
    if not file_path.exists():
        _LOGGER.error(f"Included file {file} cannot be found in {str(loader._base_folder)}")
        return {}

    with open(file_path) as f:
        c = yaml.load(f, Loader=BaseSafeLoader)

    return c

class BaseSafeLoader(FastestAvailableSafeLoader):
    "Base config loader for inkBoard. Used to register tags and the like."
    
    _base_folder: Path = None
    _substitutions: dict
    _opened_files = set()

    def __init__(self, stream):
        self.__class__._opened_files.add(stream.name)
        super().__init__(stream)

    @classmethod
    def read_secrets(cls):
        secrets_file = cls._base_folder / const.SECRETS_YAML
        if secrets_file.exists():
            with open(secrets_file) as f:
                cls._secrets = MappingProxyType(yaml.load(f, Loader=cls))
                return
        else:
            cls._secrets = MappingProxyType({})

    @classmethod
    def read_entities(cls):
        entity_file = cls._base_folder / const.ENTITIES_YAML
        if entity_file.exists():
            with open(entity_file) as f:
                cls._entities = MappingProxyType(yaml.load(f, Loader=cls))
                return
        else:
            cls._entities = MappingProxyType({})

    def construct_scalar(self, node):
        val = super().construct_scalar(node)
        if "$" in val and hasattr(self, "_substitutions"):
            val = Template(val).safe_substitute(**self.__class__._substitutions)
        return val
    
    def construct_mapping(self, node, deep = False):
        
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if isinstance(value_node, yaml.MappingNode):
                value = self.construct_mapping(value_node, deep)
            else:
                value = self.construct_object(value_node, deep=deep)
            mapping[key] =  value

        return YAMLNodeDict(mapping,node)

BaseSafeLoader.add_constructor("!secret",secret_constructor)
BaseSafeLoader.add_constructor("!entity",entity_constructor)
BaseSafeLoader.add_constructor("!include", include_constructor)

class MainConfigLoader(BaseSafeLoader):
    
    _dashboardNodes = {}

    def __init__(self, stream):
        self._top_node = True
        super().__init__(stream)

    def construct_mapping(self, node, deep=False):

        d = {}
        if self._top_node:
            self._top_node = False
            parse_later = {}

            for (key_node, value_node) in node.value:
                key = self.construct_object(key_node, deep)
                if key == "substitutions":
                    if isinstance(value_node, yaml.MappingNode):
                        val = super().construct_mapping(value_node, deep)
                    else:
                        val = self.construct_object(value_node, deep)
                    
                    d[key] = val
                    BaseSafeLoader._substitutions = MappingProxyType(val)

                elif key in const.DASHBOARD_KEYS:
                    _LOGGER.verbose(f"dashboard node is {value_node}")
                    parse_later[key] = value_node
                    self._dashboardNodes[key] = value_node
                else:
                    parse_later[key] = value_node

            for node_name, value_node in parse_later.items():
                if isinstance(value_node, yaml.MappingNode):
                    val = self.construct_mapping(value_node, deep)
                else:
                    val = super().construct_object(value_node, deep)

                d[node_name] = val
            d = YAMLNodeDict(d, node)
        else:
            d = super().construct_mapping(node, deep)

        #Not returning mappingproxies, as it leads to quite some difficulties
        #I.e. JSON not wanting to dump stuff when it is a MappingProxy.

        return d
    
    
    def construct_object(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            obj = self.construct_mapping(node, deep)
            return obj
        else:
            obj = super().construct_object(node, deep)
            return obj

    def construct_document(self, node):
        data = super().construct_document(node)
        return data