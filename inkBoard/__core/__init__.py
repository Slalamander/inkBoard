"Core modules and objects for running inkBoard instances"

raise DeprecationWarning("The core module is deprecated. Please import CORE from the base inkBoard.")

from typing import TYPE_CHECKING, Literal, Final, Optional, Any, Callable, get_args
from types import MappingProxyType, MemberDescriptorType
import logging
from datetime import datetime as dt
from contextlib import suppress

from inkBoard import constants as const
from inkBoard.constants import CORESTAGES

from PythonScreenStackManager.pssm.util import classproperty, ClassPropertyMetaClass
from PythonScreenStackManager.exceptions import ShorthandNotFound

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

_INTEGRATION_KEYS = {}
_INTEGRATION_OBJECTS = {}
_ELEMENT_PARSERS = {}


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

_corestagestype = Literal["RELOAD", "QUIT", "NONE", "SETUP", "START", "RUN", "STOP"]
# _corestages = list(val for val in CORESTAGES.__dict__.keys() if not val.startswith("_"))
_corestageslevels = {val: key for key, val in CORESTAGES.__dict__.items() if not key.startswith("_")}

class _CoreStage:
    def __init__(self, stage : Literal[_corestagestype]):
        # assert isinstance(stage,str) and hasattr(CORESTAGES,stage.upper()), f"Invalid stage {stage}"
        
        try:
            if isinstance(stage,int):
                self._stage = _corestageslevels[stage]
                self._stageno = stage
            else:
                self._stageno = self._stage_to_no(stage)
                self._stage = stage.upper()
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"{stage} cannot be set as a corestage") from e
    
    def __repr__(self):
        return self._stage

    def __eq__(self, value):
        if isinstance(value, str):
            value = self._stage_to_no(value)
        
        if isinstance(value,(int)):
            return value == self._stageno
        elif isinstance(value,_CoreStage):
            return value._stageno == self._stageno
        else:
            self.__invalid_type(value)
    
    def __lt__(self, value):
        if isinstance(value,str):
            value = self._stage_to_no(value)

        if isinstance(value, (int)):
            return self._stageno < value
        elif isinstance(value, _CoreStage):
            return self._stageno < value._stageno
        else:
            self.__invalid_type(value)
    
    def __le__(self, value):

        if isinstance(value,str):
            value = self._stage_to_no(value)

        if isinstance(value, (int)):
            return self._stageno <= value
        elif isinstance(value, _CoreStage):
            return self._stageno <= value._stageno
        else:
            self.__invalid_type(value)
    
    def __gt__(self, value):
        if isinstance(value,str):
            value = self._stage_to_no(value)

        if isinstance(value, (int)):
            return self._stageno > value
        elif isinstance(value, _CoreStage):
            return self._stageno > value._stageno
        else:
            self.__invalid_type(value)
    
    def __ge__(self, value):
        if isinstance(value,str):
            value = self._stage_to_no(value)

        if isinstance(value, (int)):
            return self._stageno >= value
        elif isinstance(value, _CoreStage):
            return self._stageno >= value._stageno
        else:
            self.__invalid_type(value)

    def __invalid_type(self, value):
        TypeError(f"Cannot compare core stage with value of type {type(value)}")

    @staticmethod
    def _stage_to_no(stage : str) -> int:
        try:
            return getattr(CORESTAGES,stage.upper())
            # return _corestages.index(stage.upper())
        except AttributeError as e:
            raise ValueError(f"{stage} is not a valid core stage") from e


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
        "_stage", "_config", "_screen", "_device",
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
            import sys
            if len(sys.argv) > 1 and sys.argv[1] == const.COMMAND_DESIGNER:
                cls._DESIGNER_RUN = True
            else:
                cls._DESIGNER_RUN = False
        
        ##As is, the current classproperty I have written actually does allow overwriting (setting) the property
        ##may have two options: implement core as a singleton, or fix classmethod
        ##thing is, if not fixing it, the problem may arise later on too in, i.e. element classes
        ##I see one way of perhaps doing it: overwriting __setattr__ for the class to intercept it
        ##At the __set_owner__ stage I believe -> would give issues for classes since that is called on instance level
        ##So I think a metaclass would somehow need to be put on it...

        ##check if it is possible to just do that with elements tbh
        ##And check if classes that are not elements implement that

        ##So: add the metaclass thingy, but for elements the __setattr__ will be overwritten
        self._set_stage(CORESTAGES.NONE)
        return
    
    @classmethod
    def _reset(cls):
        "Resets the inkBoard core for a new run"
        for attr in cls.__slots__:
            if attr == "_DESIGNER_RUN": continue
            with suppress(AttributeError):
                delattr(cls, attr)
        
        cls._set_stage(CORESTAGES.NONE)
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
    def stage(cls) -> _CoreStage:
        "The current stage of the inkBoard run"
        return cls._stage

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
    def customFunctions(cls) -> MappingProxyType[str,Callable]:
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
    def parse_element(cls, element_str : str) -> type["Element"]:
        """Parses elements registered by integrations or present in the custom elements folder

        Does not parse elements from the default pssm library

        Parameters
        ----------
        element_str : str
            The string to parse, must be setup as {identifier}:{element_type}

        Returns
        -------
        type[Element]
            The element class parsed from the string

        Raises
        ------
        KeyError
            Raised if the string is invalid or something else went wrong
        """
        if not ":" in element_str:
            msg = f"A custom element string must be structured as {{identifier}}:{{element_type}}"
            _LOGGER.error(msg)
            raise KeyError(msg)
        
        identifier, elt_type = element_str.split(":",1)
        if identifier not in cls._elementParsers:
            msg = f"No identifier {identifier} found"
            _LOGGER.error(msg)
            raise KeyError(msg)
        
        try:
            parser = cls._elementParsers[elt_type]
            return parser(elt_type)
        except Exception as exce:
            raise KeyError from exce

    @classmethod
    def parse_custom_function(cls, name: str, attr: str, options = {}) -> Optional[Callable]:
        """Parses a string to a function from the custom functions package. 
        """

        parse_string = name.lower()
        if parse_string not in cls._customFunctions:
            msg = f"No custom function called {parse_string}"
            raise ShorthandNotFound(msg=msg)
        return cls._customFunctions[parse_string]


    @classmethod
    def _set_stage(cls, stage : str):
        cls._stage = _CoreStage(stage)

_CORE._stage = CORESTAGES.NONE