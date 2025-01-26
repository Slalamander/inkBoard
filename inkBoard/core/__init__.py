"Core modules and objects for running inkBoard instances"

from typing import TYPE_CHECKING, Literal, Final, Optional, Any, Callable
from types import MappingProxyType, MemberDescriptorType
from functools import cached_property
import logging
from pathlib import Path
from datetime import datetime as dt
from contextlib import suppress

import inkBoard
from inkBoard import constants as const
from inkBoard.arguments import parse_args

from PythonScreenStackManager.pssm.util import classproperty, ClassPropertyMetaClass

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


# DESIGNER_RUN : bool = parse_args().command == const.COMMAND_DESIGNER
False

_INTEGRATION_KEYS = {}
_INTEGRATION_OBJECTS = {}
_ELEMENT_PARSERS = {}

# def add_integration_config_key(key : str, folder : Path):
#     """
#     Adds the key that is connected to an integration and the import function. Will call the import_func if the key is present in the config.

#     Parameters
#     ----------
#     key : str
#         The key that users can use in their config file to load in the integration
#     folder : Callable
#         The function that handles the processing of data under said key.
#     """    
#     if key in _INTEGRATION_KEYS:
#         int_mod = _INTEGRATION_KEYS[key].__module__
#         _LOGGER.error(f"{key} is already used for a the config of a different integration: {int_mod}")
#     else:
#         _INTEGRATION_KEYS[key] = folder

# def get_integration_config_keys() -> MappingProxyType[str,Callable]:
#     return MappingProxyType(_INTEGRATION_KEYS)

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

class COREMETA(ClassPropertyMetaClass):

    def __setattr__(self, attr, value):
        if attr not in self.__slots__:
            raise AttributeError(f"Setting CORE attribute {attr} is not allowed")   #@IgnoreExceptions
        return super(ClassPropertyMetaClass, self).__setattr__(attr, value)
    
    def __getattribute__(self, name):
        val = super().__getattribute__(name)
        if isinstance(val,MemberDescriptorType):
            raise AttributeError
        return val
    

class _CORE(metaclass=COREMETA):

    __slots__ = (
        "_START_TIME", "_DESIGNER_RUN",
        "_config", "_screen", "_device",
        "_integrationLoader", "_integrationObjects",
        "_customFunctions", "_customElements", "_elementParsers"
    )

    # _START_TIME: str
    _elementParsers: dict[str,Callable]

    def __init__(self):
        

        cls = type(self)
        assert not hasattr(cls, "_START_TIME") or isinstance(cls._START_TIME, MemberDescriptorType),  "CORE has already been set up"

        cls._START_TIME = dt.now().isoformat()

        cls._elementParsers = {}
        if not hasattr(cls,"_DESIGNER_RUN"):
            cls._DESIGNER_RUN = parse_args().command == const.COMMAND_DESIGNER
        
        ##As is, the current classproperty I have written actually does allow overwriting (setting) the property
        ##may have two options: implement core as a singleton, or fix classmethod
        ##thing is, if not fixing it, the problem may arise later on too in, i.e. element classes
        ##I see one way of perhaps doing it: overwriting __setattr__ for the class to intercept it
        ##At the __set_owner__ stage I believe -> would give issues for classes since that is called on instance level
        ##So I think a metaclass would somehow need to be put on it...

        ##check if it is possible to just do that with elements tbh
        ##And check if classes that are not elements implement that

        ##So: add the metaclass thingy, but for elements the __setattr__ will be overwritten
        return
    
    @classmethod
    def _reset(cls):
        "Resets the inkBoard core for a new run"
        for attr in cls.__slots__:
            if attr == "_DESIGNER_RUN": continue
            with suppress(AttributeError):
                delattr(cls, attr)
        
        _LOGGER.error("Cleaned all attributes")

    #region
    @classproperty
    def DESIGNER_RUN(cls) -> bool:
        return cls._DESIGNER_RUN
    
    @classproperty
    def START_TIME(cls) -> str:
        """The time the CORE object was setup

        Timestring in isoformat.
        """
        return cls._START_TIME
    START_TIME : str
    
    @classproperty
    def IMPORT_TIME(cls): return cls.START_TIME

    @classproperty
    def screen(cls) -> "PSSMScreen":
        "The screen instance managing the screen stack"
        return cls._screen
    screen : "PSSMScreen"
    
    @classproperty
    def device(cls) -> "BaseDevice":
        "The device object managing bindings to the device"
        return cls._device
    device : "BaseDevice"
    
    @classproperty
    def config(cls) -> "configuration":
        "The config object from the currently loaded configuration"
        return cls._config
    config : "configuration"
    
    @classproperty
    def integrationLoader(cls) -> "IntegrationLoader":
        "Object responsible for loading integrations"
        return cls._integrationLoader
    integrationLoader : "IntegrationLoader"
    
    @classproperty
    def integrationObjects(cls) -> MappingProxyType[Literal["integration_entry"],Any]:
        "Objects returned by integrations, like client instances."
        return cls._integrationObjects
    integrationObjects : MappingProxyType[Literal["integration_entry"],Any]

    @classproperty
    def customElements(cls) -> MappingProxyType[str,"Element"]:
        return cls._customElements
    customElements : MappingProxyType[str,"Element"]

    @classproperty
    def customFunction(cls) -> MappingProxyType[str,Callable]:
        return cls._customFunctions
    customFunctions : MappingProxyType[str,Callable]
    
    @classproperty
    def elementParsers(cls) -> MappingProxyType[str,Callable]:
        "Returns the registered element parsers"
        return MappingProxyType(cls._elementParsers)
    elementParsers : MappingProxyType[str,Callable]
    #endregion

    @classmethod
    def add_element_parser(cls, identifier : str, parser : Callable[[str],"Element"]):
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
        if identifier in cls._elementParsers:
            _LOGGER.error(f"Element identifier {identifier} is already registered")
            return
        
        cls._elementParsers[identifier] = parser

    @classmethod
    def parse_custom_function(cls, name: str, attr: str, options = {}) -> Optional[Callable]:
        """Parses a string to a function from the custom functions package. 
        """

        parse_string = name.lower()
        if parse_string not in cls._custom_functions:
            _LOGGER.error(f"No custom function called {parse_string}")
            return
        return cls._custom_functions[parse_string]



