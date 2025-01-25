"Core modules and objects for running inkBoard instances"

from typing import TYPE_CHECKING, Literal, Final, Optional, Any, Callable
from types import MappingProxyType
from functools import cached_property
import logging
from pathlib import Path
from datetime import datetime as dt

import inkBoard
from inkBoard import constants as const
from inkBoard.arguments import parse_args

from PythonScreenStackManager.tools import classproperty

from . import util  ##Depending on how stuff moves around, may need to import util somewhere else?

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from PythonScreenStackManager.pssm.screen import PSSMScreen
    from PythonScreenStackManager.elements import Element

    from inkBoard.platforms import BaseDevice
    from inkBoard.configuration.configure import config as configuration

    from inkBoard.loaders import IntegrationLoader

IMPORT_TIME = dt.now().isoformat()

config: "configuration"
"The config object from the currently loaded configuration"

screen: "PSSMScreen"
"The screen instance managing the screen stack"

device: "BaseDevice"
"The device object managing bindings to the device"

integration_loader: "IntegrationLoader"
"Object responsible for loading integrations"

integration_objects: Final[MappingProxyType[Literal["integration_entry"],Any]]


custom_functions: MappingProxyType[str,Callable]
"Functions in the custom/functions folder of the config"


DESIGNER_RUN : bool = parse_args().command == const.COMMAND_DESIGNER

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
        _LOGGER.error(f"{key} is already used for a the config of a different integration: {int_mod}")
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
        _LOGGER.error(f"Element identifier {identifier} is already registered")
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
    if parse_string not in custom_functions:
        _LOGGER.error(f"No custom function called {parse_string}")
        return
    return custom_functions[parse_string]


class _CORE:

    _START_TIME: str

    def __init__(self):
        ##The __init__ 

        cls = self.__class__
        assert not hasattr(cls._START_TIME), "CORE has already been set up"

        cls._START_TIME = dt.now().isoformat()
        return
    
    def _reset(cls):    ##Maybe change this for __del__
        "Resets the inkBoard core for a new run"
        del(cls._config)
        del(cls._screen)
        del(cls._device)
        del(cls._integrationLoader)
        del(cls._integrationObjects)
        del(cls._customFunctions)

    #region
    @cached_property
    def DESIGNER_RUN() -> bool:
        from inkBoard import arguments
        return arguments.command == arguments.COMMAND_DESIGNER
    
    @classproperty
    def START_TIME(cls) -> str:
        """The time the CORE object was setup

        Timestring in isoformat.
        """
        return cls._START_TIME

    @classproperty
    def screen(cls) -> "PSSMScreen":
        "The screen instance managing the screen stack"
        return cls._screen
    
    @classproperty
    def device(cls) -> "BaseDevice":
        "The device object managing bindings to the device"
        return cls._device
    
    @classproperty
    def config(cls) -> "configuration":
        "The config object from the currently loaded configuration"
        return cls._config
    
    @classproperty
    def integrationLoader(cls) -> "IntegrationLoader":
        "Object responsible for loading integrations"
        return cls._integrationLoader
    
    @classproperty
    def integrationObjects(cls) -> MappingProxyType[Literal["integration_entry"],Any]:
        "Objects returned by integrations, like client instances."
        return cls._integrationObjects

    @classproperty
    def customElements(cls) -> MappingProxyType[str,"Element"]:
        return cls._customElements

    @classproperty
    def customFunction(cls) -> MappingProxyType[str,Callable]:
        return cls._customFunctions
    #endregion
    
