###Inkboard

from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Any, Union
from . import logging as ib_logging

__version__ = "0.2.6"
"inkBoard version"


if TYPE_CHECKING:
    ##These are set in the main() function, so they can actually be imported during runtime too.
    CONFIG_FILE: str
    
    from PythonScreenStackManager.pssm.screen import PSSMScreen as screen
    from PythonScreenStackManager.devices import PSSMdevice as device
    from PythonScreenStackManager.elements import Element
    from inkBoard.configuration.configure import config

    integration_objects: MappingProxyType[Literal["integration_entry"],Any]


def getLogger(name: Union[str,None] = None) -> ib_logging.BaseLogger:
    """Convenience method to get a logger with type hinting for additional levels like verbose.
    
    logging docstr:
    Return a logger with the specified name, creating it if necessary.
    If no name is specified, return the root logger.
    """
    return ib_logging.logging.getLogger(name)


class DomainError(ValueError):
    "The supplied entity is not of a valid domain."
    pass

class Singleton(type):
    """
    Use as metaclass (class Classtype(metaclass=Singleton)).
    Ensures only a single instance of this class can exist, without throwing actual errors. Instead, it simply returns the first define instance.
    """
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

