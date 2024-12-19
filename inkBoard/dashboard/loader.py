"""
The yaml loader that parses the dashboard config (element types and the like)
"""

import yaml
import logging
from typing import Callable, Literal
from pathlib import Path

from PythonScreenStackManager import elements
from PythonScreenStackManager.pssm.screen import DuplicateElementError

from .. import core as CORE
from ..configuration import loaders, const

from .validate import validate_general

logger = logging.getLogger(__package__)

## Loading here kinda messes with things.
##Reload before building then. -> should be fine since it is not interfaced with

##This should be fine to do here since it imports from PSSM
default_elements = CORE.util.get_module_elements(elements)

#elements that are part of the default pack, i.e. parsed without an identifier

class DashboardLoader(loaders.BaseSafeLoader):
    """
    A special yaml loader that is able to construct elements from dicts with settings.
    The type of element is parsed using the `'type'` keyword, so be mindful when using that (in general, don't do it).
    Integrations can register prefixes for element types (for example ha or custom) which allows users to use elements from those integrations by setting the type to `ha:Climate`, for example.
    It can be used directly on a yaml document/stream, however it's main use is to parse the dashboard nodes that were not parsed into a dict by the main config loader.
    For this, you can instantiate the class without a stream argument, and on that instance call `construct_dashboard_node` to parse the elements defined in that node. The main advantage of this is that it preserves the line numbers in the yaml document, which makes for clearer error messages.
    """
    ##The constructors have an added depth argument, which indicates, somewhat, at what depth the node is generated, since the deep parameter tends to be true, i.e. it functions recursively and hence should work
    ##This is mainly used to set the correct validator, since when validating layouts, there may still be elements defined in the layouts themselves.

    _config_error = False
    _CORE: CORE = None

    _validator : Callable[[Literal["Element_class"],Literal["Requested_type"]],None] = validate_general
    "Function used to validate parsed elements. Passed to the parser function."

    def __init__(self, stream = None):
        if stream != None:
            super().__init__(stream)

    def parse_element_type(self, elt_type: str, validator: Callable[[Literal["Element_class"],Literal["Requested_type"]],None] = validate_general) -> elements.Element:
        
        ##Maybe put the parsing logic entirely in core?
        if elt_type == "None" and validator == validate_general:
            return None
        
        if ":" not in elt_type:
            return default_elements[elt_type]
        else:
            idf, elt_type_str = elt_type.split(":")
            parsers = self._CORE.get_element_parsers()
            if idf not in parsers:
                msg = f"No integration registered the element identifier {idf}"
                logger.error(msg)
                raise SyntaxWarning(msg)
            else:
                parser = parsers[idf]
                elt_class = parser(elt_type_str)

        validator(elt_class,elt_type)

        return elt_class

    def construct_mapping(self, node : yaml.MappingNode, deep=True, depth = 0):

        d = {}
        for (key_node, value_node) in node.value:
            val = self.construct_dashboard_node(value_node,deep, depth=depth+1)
            d[key_node.value] = val

        if "type" not in d:
            return d

        if d["type"] == "None" and len(d) == 1:
            return None

        if depth <= 1:
            validator = DashboardLoader._validator
        else:
            validator = validate_general

        try:
            elt_type = self.parse_element_type(d["type"], validator)
        except (TypeError, KeyError):
            yaml_line = node.start_mark.line
            if "id" in d:
                msg = f"Invalid element type '{d['type']}' (id {d['id']}) in configuration file {Path(node.start_mark.name).name}, line {yaml_line}"
            else:
                msg = f"Invalid element type '{d['type']}' in configuration file {Path(node.start_mark.name).name}, line {yaml_line}"
            logger.error(msg)
            self.__class__._config_error = True
            return None
        except SyntaxWarning:
            yaml_line = node.start_mark.line
            if "id" in d:
                msg = f"Invalid element identifier in configuration file {Path(node.start_mark.name).name}, line {yaml_line}: {d['type']}  (id {d['id']})"
            else:
                msg = f"Invalid element identifier in configuration file {Path(node.start_mark.name).name}, line {yaml_line}: {d['type']}"
            logger.error(msg)
            self.__class__._config_error = True
            return None
        
        if elt_type == None:
            return d
        
        type_str = d.pop("type")
        
        try:
            elt = elt_type(**d)
        except TypeError as e:
            yaml_line = node.start_mark.line
            elt_str = type_str
            if "id" in d:
                elt_str = f"[{elt_str}: {d['id']}]"
            msg = f"Error constructing element {type_str} in configuration file {node.start_mark.name}, line {yaml_line}: {e}"
            logger.error(msg)
            self.__class__._config_error = True
            return None
        except DuplicateElementError as e:
            yaml_line = node.start_mark.line
            if "id" in d:
                elt_id = d["id"]
                msg = f"An element with id {elt_id} has already been registered. Duplicate element is located in configuration file {node.start_mark.name}, line {yaml_line}."
            else:
                msg = f"Element {type_str} in configuration file {node.start_mark.name}, line {yaml_line} got a duplicate ID: {e}"
            logger.error(msg)
            self.__class__._config_error = True
            return None
        return elt

    def construct_sequence(self, node, deep = True, depth = 0):
        seq_vals = []
        for sequence_node in node.value:
            v = self.construct_dashboard_node(sequence_node, deep, depth=depth+1)
            seq_vals.append(v)
        return seq_vals
        
    def construct_dashboard_node(self, node, deep, depth = 0):
        if isinstance(node, yaml.MappingNode):
            v = self.construct_mapping(node,deep, depth)
        elif isinstance(node, yaml.SequenceNode):
            v = self.construct_sequence(node,deep, depth)
        elif isinstance(node, yaml.ScalarNode):
            if getattr(node,"tag",None) in self.yaml_constructors:
                tag_constructor = self.yaml_constructors[node.tag]
                v = tag_constructor(self,node)
            else:
                v = self.construct_scalar(node)
        return v


