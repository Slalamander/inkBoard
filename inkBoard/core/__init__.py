"Core modules and objects for running inkBoard instances"

from typing import TYPE_CHECKING, Literal, Final, Optional, Any, Callable
from types import MappingProxyType
import logging
from pathlib import Path
from datetime import datetime as dt

import inkBoard
from inkBoard import constants as const
from inkBoard.arguments import args

from . import util  ##Depending on how stuff moves around, may need to import util somewhere else?

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from PythonScreenStackManager.pssm.screen import PSSMScreen
    from PythonScreenStackManager.elements import Element

    from inkBoard.platforms import BaseDevice
    from inkBoard.configuration.configure import config as configuration

    from inkBoard.loaders import IntegrationLoader

IMPORT_TIME = dt.now().strftime("%H:%M:%S")

config: "configuration"
"The config object from the currently loaded configuration"

screen: "PSSMScreen"
"The screen instance managing the screen stack"

device: "BaseDevice"
"The device object managing bindings to the device"

integration_loader: "IntegrationLoader"
"Object responsible for loading integrations"

integration_objects: Final[MappingProxyType[Literal["integration_entry"],Any]]
"Objects returned by integrations"

custom_functions: MappingProxyType[str,Callable]
"Functions in the custom/functions folder of the config"


DESIGNER_RUN : bool = args.command == const.COMMAND_DESIGNER

_INTEGRATION_KEYS = {}
_INTEGRATION_OBJECTS = {}
_ELEMENT_PARSERS = {}

def add_integration_config_key(key : str, folder : Path):
    """
    Adds the key that is connected to an integration and the import function. Will call the import_func if the key is present in the config.

    Parameters
    ----------
    key : str
        The key that users can use in their config file to load in the integration
    folder : Callable
        The function that handles the processing of data under said key.
    """    
    if key in _INTEGRATION_KEYS:
        int_mod = _INTEGRATION_KEYS[key].__module__
        logger.error(f"{key} is already used for a the config of a different integration: {int_mod}")
    else:
        _INTEGRATION_KEYS[key] = folder

def get_integration_config_keys() -> MappingProxyType[str,Callable]:
    return MappingProxyType(_INTEGRATION_KEYS)

def add_element_parser(identifier : str, parser : Callable[[str],"Element"]):
    """
    Adds a parser function for custom elements. The identifier should be unique, and cannot be custom.

    Parameters
    ----------
    identifier : str
        An identifier string that indicates the element is parsed via this parser.
        Does not need the ':'
    parser : Callable[[str],&quot;Element&quot;]
        The function that parses the element. Should return the class, not an instance of the element.
    """    
    if identifier in _ELEMENT_PARSERS:
        logger.error(f"Element identifier {identifier} is already registered")
        return
    
    _ELEMENT_PARSERS[identifier] = parser

def get_element_parsers() -> MappingProxyType:
    "Returns the element parser functions and their identifiers as keys."
    return MappingProxyType(_ELEMENT_PARSERS)

_CUSTOM_FUNC_IDENTIFIER = "custom:"

def parse_custom_function(name: str, attr: str, options = {}) -> Optional[Callable]:
    """Parses a string to a function from the custom functions package. 
    """

    parse_string = name.lower()
    return custom_functions[parse_string]

