"Create and parse template elements."

import yaml
from yaml.constructor import BaseConstructor
from yaml.nodes import Node, MappingNode, ScalarNode, SequenceNode


import inkBoard
from inkBoard.configuration import loaders
from inkBoard.exceptions import TemplateElementError, TemplateLoadError
from inkBoard.helpers import YAMLNodeDict

from .loader import DashboardLoader, const

_LOGGER = inkBoard.getLogger(__name__)

class TemplateLoader(loaders.BaseSafeLoader):
    """YAML Loader for inkBoard templates
    """

    _allowed_entries = ("defaults", "element")

    def __init__(self, name, template_node : yaml.nodes.MappingNode):
        # assert name not in self._templates, f"template {name} is already registered"
        self._name = name

        # self._templates[name] = self
        self._variables = set()
        self._map_extends = set()
        self._sequence_extends = set()

        BaseConstructor.__init__(self)

        self._base_node = template_node

    ##In here -> parse up to elements (i.e. just parse default variable values)
        ##Do run through the entire thing immediately too, use it to determine required and optional variables
    ##Main thing to think about: how to handle the return type? I.e. the DashboardLoader should be used I believe?

    def __repr__(self):
        return f"<inkBoard Template loader {self._name}>"
        return super().__repr__()

    def template_variable_constructor(self, variable: yaml.nodes.ScalarNode, *args):
        self._variables.add(variable.value)
        return variable.value

    def template_variable_extender(self, parent_node, key_node, value_node = None):
        if isinstance(parent_node, MappingNode):
            self._map_extends.add(value_node.value)
        else:
            self._sequence_extends.add(key_node.value)
        return super().template_variable_extender(parent_node, key_node, value_node)

    def construct_template(self):
        data = self.construct_document(self._base_node)
        errors = False

        if "element" not in data:
            msg = f"Template {self._name}: A template must have an element entry"
            _LOGGER.error(msg, extra={"YAML": data})
            errors = True
        
        if v := [x for x in data if x not in TemplateLoader._allowed_entries]:
            plur = f"entry {v[0]}" if len(v) == 1 else f"entries {v}"
            msg = f"Template {self._name}: has invalid {plur}, only {TemplateLoader._allowed_entries} are allowed"
            _LOGGER.error(msg, extra={"YAML": data})
            errors = True

        if (n := self._map_extends & self._sequence_extends):
            plur = f"variable {n} is" if len(n) == 1 else f"variables {n} are"
            msg = f"Template {self._name}: {plur} are used for both mapping and list extension"
            _LOGGER.error(msg, extra={"YAML": data})
            errors = True
            # raise TemplateElementError(msg)

        for node_key, node_map in self._base_node.value:
            if node_key.value == "element":

                ##These should go into a template object instead.
                template_node = node_map
        
        defaults = data.get("defaults", {})
        vars = self._variables.copy()

        optionals = {}
        for default in defaults:
            if default in self._map_extends:
                val = defaults[default]
                if not isinstance(val, YAMLNodeDict):
                    msg = f"{self}: default for mapping variable {default} must be a mapping"
                    _LOGGER.error(msg, extra={"YAML": defaults})
                    errors = True
                else:
                    optionals[default] = val
            
            elif default in self._sequence_extends:
                val = defaults[default]
                if not isinstance(val, list):
                    msg = f"{self}: default for sequence variable {default} must be a sequence"
                    _LOGGER.error(msg, extra={"YAML": defaults})
                    errors = True
                else:
                    optionals[default] = val

            if default in vars:
                vars.remove(default)
                optionals.setdefault(default, defaults[default])
            elif default in self._map_extends | self._sequence_extends:
                pass
            else:
                _LOGGER.warning(f"Default variable {default} is not used in template {self._name}")

        if errors:
            raise TemplateLoadError(f"Cannot create template {self._name}, see logs")
        
        return TemplateElement(self._name, template_node, tuple(vars),
                            sequence_variables=self._sequence_extends, mapping_variables=self._map_extends,
                            optional_variables=optionals)



# TemplateLoader.add_constructor("!var", TemplateLoader.add_variable)
# TemplateLoader.add_constructor("!variable", TemplateLoader.add_variable)

class TemplateElement:

    _templates = {}

    def __init__(self, template : str, template_node: yaml.nodes.MappingNode,
                required_variables : tuple, sequence_variables : set, mapping_variables : set,
                optional_variables : dict = {},):
        
        self._template = template
        self._template_node = template_node
        self._required_variables = required_variables
        self._optional_variables = optional_variables
        self._sequence_variables = sequence_variables
        self._mapping_variables = mapping_variables

        self._templates[self._template] = self

        ##Add elt_type property (parsed from under element; use for validator)
        ##Nope, that can be a variable as well

    def __repr__(self):
        return f"<{self}>"
    
    def __str__(self):
        return f"inkBoard Template Element: {self._template}"

    def construct_element(self, variables : loaders.YAMLNodeDict = {}) -> "TemplateElement":
        """Constructs an element using the given variables
        """        

        ##Construct

        errors = False
        try:
            missing = [x for x in self._required_variables if x not in variables]
            assert len(missing) == 0
        except AssertionError:
            plur = f"variable {missing[0]}" if len(missing) == 1 else f"variables {missing}"
            msg = f"Template {self._template} is missing required {plur}"
            _LOGGER.error(msg, extra={"YAML": variables})
            errors = True

        try:
            err = [v for v in self._mapping_variables if v in variables and not isinstance(variables[v],dict)]
            assert len(err) == 0
        except AssertionError:
            plur = f"variable {err[0]}" if len(err) == 1 else f"variables {err}"
            msg = f"{plur} in template {self._template} must be a mapping"
            _LOGGER.error(msg, extra={"YAML": variables})
            errors = True

        try:
            # err = [v for v in self._sequence_variables if (v in variables and isinstance(variables[v],list))]
            err = [v for v in self._sequence_variables if v in variables and not isinstance(variables[v],list)]
            assert len(err) == 0
        except AssertionError:
            plur = f"variable {err[0]}" if len(err) == 1 else f"variables {err}"
            msg = f"{plur} in template {self._template} must be a sequence"
            _LOGGER.error(msg, extra={"YAML": variables})
            errors = True

        if errors:
            raise TemplateElementError(f"Unable to parse template {self._template}")

        template_vars = self._optional_variables | variables    ##This should overwrite keys present in optionals

        # res = TemplateParser(template_vars).construct_document(self._template_node)
        res = TemplateParser(template_vars).construct_dashboard_node(self._template_node, 2)

        # except Exception as exce:
        #     _LOGGER.error(exce)
        #     raise TemplateElementError from exce

        ##Todo: improve logging (i.e. missing variables etc)
        ##Check logging when an unknown template is requested
        ##Test usage of defaults
        ##Error handling in the DasboardLoader constructor (i.e. add exception case for TemplateError)
        
        ##I.e. create defaults for state_styles for example that can then be made bigger via the template
        return res


class TemplateParser(DashboardLoader):
    """Parses to an element from a template node
    """

    def __init__(self, variables : dict):

        self._variables = variables
        BaseConstructor.__init__(self)

    def template_variable_constructor(self, variable: yaml.nodes.ScalarNode):

        return self._variables[variable.value]

    def template_variable_extender(self, parent_node, key_node, value_node = None):
        if isinstance(parent_node,MappingNode):
            val = self._variables.get(value_node.value, {})
        else:
            val = self._variables.get(key_node.value, [])
        return val
        return super().template_variable_extender(parent_node, key_node, value_node)

    def construct_mapping(self, node, deep=True, depth=0):
        return super().construct_mapping(node, deep, depth)

    ##How to:
    ##Use nodes from the template definition
    ##Allow passing variables
    ##Use !variable (!var?) anchor to indicate a variable that will be passed

    ##Instead of a yaml loader for this, maybe use an Element that calls the parser?

def parse_template(template):

    return TemplateElement._templates[template]