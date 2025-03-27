"""
The yaml loader that parses the dashboard config (element types and the like)
"""

import yaml
import logging
from typing import Callable, Literal, TYPE_CHECKING

from PythonScreenStackManager import elements
from PythonScreenStackManager.pssm.screen import DuplicateElementError

from inkBoard import util
from inkBoard.exceptions import TemplateTypeError, inkBoardTemplateError

from inkBoard import CORE as CORE
from inkBoard.configuration import loaders, const
from inkBoard.constants import DEBUGGING

from .validate import validate_general

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .templates import TemplateElement

## Loading here kinda messes with things.
##Reload before building then. -> should be fine since it is not interfaced with

##This should be fine to do here since it imports from PSSM
default_elements = util.get_module_elements(elements)

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

    _validator : const.validatortype = validate_general
    "Function used to validate parsed elements. Passed to the parser function."

    _TemplateClass : type["TemplateElement"]

    def __init__(self, stream = None):
        if stream is not None:
            super().__init__(stream)

    def parse_element_type(self, elt_type: str, validator: Callable[[Literal["Element_class"],Literal["Requested_type"]],None] = validate_general) -> elements.Element:
        
        ##Maybe put the parsing logic entirely in core?
        if elt_type == "None" and validator == validate_general:
            return None
        
        if ":" not in elt_type:
            return default_elements[elt_type]
        else:
            idf, elt_type_str = elt_type.split(":")
            parsers = self._CORE.elementParsers
            if idf not in parsers:
                msg = f"No integration registered the element identifier {idf}"
                # logger.error(msg)
                raise SyntaxWarning(msg)
            else:
                parser = parsers[idf]
                elt_class = parser(elt_type_str, idf)

        if idf == "template":
            ##Validating comes later for templates.
            pass
        else:
            validator(elt_class,elt_type)

        return elt_class

    def construct_mapping(self, node : yaml.MappingNode, deep=True, depth = 0):

        d = {}
        for (key_node, value_node) in node.value:
            if key_node.tag in const.TEMPLATE_EXTEND_TAGS:
                val = self.template_variable_extender(node, key_node, value_node)
                d = util.update_nested_dict(val, d)
            else:
                val = self.construct_dashboard_node(value_node,deep, depth=depth+1)
                d[key_node.value] = val

        if "type" not in d:
            return loaders.YAMLNodeDict(d,node)

        if d["type"] == "None" and len(d) == 1:
            return None

        if depth <= 1:
            validator = self.__class__._validator
        else:
            validator = validate_general

        try:
            elt_type = self.parse_element_type(d["type"], validator)
        except (TypeError, KeyError):
            if "id" in d:
                msg = f"Invalid element type '{d['type']}' (id {d['id']})"
            else:
                msg = f"Invalid element type '{d['type']}'"
            _LOGGER.error(msg, extra={"YAML": node})
            self.__class__._config_error = True
            return None
        except SyntaxWarning:
            if "id" in d:
                msg = f"Invalid element identifier: {d['type']}  (id {d['id']})"
            else:
                msg = f"Invalid element identifier: {d['type']}"
            _LOGGER.error(msg, exc_info=True, extra={"YAML": node})
            self.__class__._config_error = True
            return None
        
        if elt_type is None:
            return d
        
        type_str = d.pop("type")
        
        try:
            if isinstance(elt_type, DashboardLoader._TemplateClass):
                v = loaders.YAMLNodeDict(d, node)
                elt = elt_type.construct_element(**v)
                try:
                    validator(type(elt), type_str)
                except TypeError as exce:
                    raise TemplateTypeError from exce
            else:
                elt = elt_type(**d)
        except DuplicateElementError as e:
            if "id" in d:
                elt_id = d["id"]
                msg = f"An element with id {elt_id} has already been registered."
            else:
                msg = f"Element {type_str} got a duplicate ID: {e}"
            _LOGGER.error(msg, exc_info=True, extra={"YAML": node})
            self.__class__._config_error = True
            if DEBUGGING:
                raise
        except inkBoardTemplateError as e:
            _LOGGER.error(e, extra={"YAML": node}, exc_info=DEBUGGING)
            self.__class__._config_error = True
            if DEBUGGING:
                raise
        except Exception as e:
            elt_str = type_str
            if "id" in d:
                elt_str = f"[{elt_str}: {d['id']}]"
            msg = f"Error constructing element {type_str}: {e}"
            _LOGGER.error(msg, extra={"YAML": node}, exc_info=DEBUGGING)
            self.__class__._config_error = True
            if DEBUGGING:
                raise
        else:
            return elt

    def construct_sequence(self, node, deep = True, depth = 0):
        seq_vals = []
        for sequence_node in node.value:
            if sequence_node.tag in const.TEMPLATE_EXTEND_TAGS:
                seq_vals.extend(self.template_variable_extender(node, sequence_node))
            else:
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


