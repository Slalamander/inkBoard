###Inkboard

import sys
from types import TracebackType, MappingProxyType
from typing import Callable, TYPE_CHECKING, Literal, Any, Union
import __main__
from functools import partialmethod, partial
from . import logging as ib_logging

from yaml import SafeLoader

from . import helpers, constants
from .constants import RAISE, __version__

#Location is correct (i.e. points to the package location)

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

configLoader = SafeLoader
"configLoader object"

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
        # else:
        #     raise Exception("Double instance")
        return cls._instances[cls]

# class RaiseHandler(logging.Handler):
#     """
#     Custom logging handler class that can raise errors on calls to logger.exception (or error with exc_info) if RAISE has been set.  
#     Could be logging does have a setting or something for this, but I was unable to find it.
#     """

#     ##Colors for different log levels
#     gray = "\x1b[38;5;247m" #"\x1b[2;37;41m" #"\x1b[247;20m"
#     green = "\x1b[32;20m"
#     blue = "\x1b[34;20m"
#     yellow = "\x1b[33;20m"
#     red = "\x1b[31;20m"
#     bold_red = "\x1b[31;1m"
#     reset = "\x1b[0m"
#     # format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
#     format_str = '%(asctime)s [%(levelname)s; %(name)s %(filename)s %(funcName)s; line %(lineno)s]: %(message)s'

#     FORMATS = {
#         "default": gray + format_str + reset,
#         logging.DEBUG: green + format_str + reset,
#         logging.INFO: blue + format_str + reset,
#         logging.WARNING: yellow + format_str + reset,
#         logging.ERROR: red + format_str + reset,
#         logging.CRITICAL: bold_red + format_str + reset
#     }

#     def __init__(self )-> None:
#         # self.sender = LogSender()
#         logging.Handler.__init__(self=self)

#     def handleError(self, record):
#         return

#     def format(self,record):
#         log_fmt = self.FORMATS.get(record.levelno, self.FORMATS["default"])
#         formatter = logging.Formatter(log_fmt)
#         return formatter.format(record)

#     def emit(self, record) -> None:
#         f = self.format(record)
#         print(f)

#         if record.levelno >= 40 and record.exc_info != None and RAISE:
#             if not isinstance(record.exc_info, (list,tuple)) or record.exc_info[0] == None:
#                 exce = record.msg
#             else:
#                 exc = record.exc_info[0]
#                 msg = record.exc_info[1]
#                 exce = exc(msg)

#             if "inkboard" in record.name.lower():
#                 ##This worked in the element attribute getter. Hopefully here too.
#                 ##See: https://stackoverflow.com/questions/1603940/how-can-i-modify-a-python-traceback-object-when-raising-an-exception

#                 traceback = sys.exc_info()[2]
                
#                 if traceback == None:
#                     try:
#                         raise exce
#                     except:
#                         traceback = sys.exc_info()[2]
#                         back_frame = traceback.tb_frame.f_back.f_back
#                 else:
#                     back_frame = traceback.tb_frame.f_back
#                         # back_frame = traceback.tb_frame.f_back
#                         # raise exce

                
#                 back_tb = TracebackType(tb_next=None,
#                                     tb_frame=back_frame,
#                                     tb_lasti=back_frame.f_lasti,
#                                     tb_lineno=back_frame.f_lineno)
#                 raise exce.with_traceback(back_tb) #@IgnoreExceptions

# logging.TRACE = 5
# logging.addLevelName(logging.TRACE, "TRACE")
# logging.Logger.trace = partialmethod(logging.Logger.log, logging.TRACE)
# logging.trace = partial(logging.log, logging.TRACE)

# logging.VERBOSE = logging.TRACE
# logging.Logger.verbose = partialmethod(logging.Logger.log, logging.VERBOSE)
# logging.verbose = partial(logging.log, logging.VERBOSE)


# if __main__.__package__ == "inkBoard":
#     ##Use this later on to add the stream handler for streaming logs
#     ##Also check if running as emulator?
#     ##Yes cause if inkBoard  is the package, args can be imported
#     pass

# log_format = '%(asctime)s [%(levelname)s %(filename)s %(funcName)s, line %(lineno)s]: %(message)s'
# log_dateformat = '%d-%m-%Y %H:%M:%S'
