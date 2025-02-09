"""
Small library with helper functions for inkBoard, that could not be included in the pssm tools.
Does not import anything from pssm or integration yet, and is mainly meant to supplement some small useful functions.
"""
import typing   ##Need to import typing to evaluate union strings (those are converted to typing.Union[...])
import asyncio
from typing import TYPE_CHECKING
from typing import TypedDict, TypeVar, Union, Literal, Callable
from types import ModuleType
import logging 
import sys
import importlib
from contextlib import suppress

from inkBoard import core as CORE
from PythonScreenStackManager.exceptions import ShorthandNotFound

if TYPE_CHECKING:
    from PythonScreenStackManager.elements import Element
    from PythonScreenStackManager.pssm import PSSMScreen
    import yaml

_LOGGER = logging.getLogger("inkBoard")

ph = TypedDict("ph")
"Placeholder typedict for typehinting"

class InkBoardError(Exception):
    "Base Exception for inkBoard"

class DeviceError(InkBoardError):
    "Something went wrong setting up the device"

class ScreenError(InkBoardError):
    "Something went wrong setting up the screen instance"

class ConfigError(InkBoardError):
    "Something is wrong with the configuration"

class DashboardError(ConfigError):
    "Unable to setup the dashboard"

class QuitInkboard(InkBoardError):
    "Exception to set as eStop to quit the current inkBoard session"
    pass

class inkBoardParseError(InkBoardError, ValueError):
    "Something could not be parsed correctly"

def add_required_keys(td : ph, keys : frozenset):
    """
    Adds the required keys to the typeddict, and removes them from the optional keys

    Parameters
    ----------
    td : TypedDict
        The typed dict to add the keys to
    keys : frozenset
        the keys to add like {"key1","key2"}
    """
    td.__required_keys__ = td.__required_keys__.union(keys)
    td.__optional_keys__ = td.__optional_keys__.difference(td.__required_keys__)

def add_optional_keys(td : ph, keys : frozenset):
    """
    Adds the optional keys to the typeddict, and removes them from the required keys

    Parameters
    ----------
    td : TypedDict
        The typed dict to add the keys to
    keys : frozenset
        the keys to add like {"key1","key2"}
    """
    td.__optional_keys__ = td.__optional_keys__.union(keys)
    td.__required_keys__ = td.__required_keys__.difference(td.__required_keys__)

def check_required_keys(typeddict : ph, checkdict : dict, log_start : str):
    """
    checks if the keys required by typedict are present in checkdict. Exits inkboard if any are missing.
    Uses name for constructing logs.

    Parameters
    ----------
    typeddict : TypedDict
        The TypedDict to get required keys from
    checkdict : dict
        The dict to check
    log_start : str
        Starting string for log messages; {log_start} is missing ...
    """

    missing = {}
    for k in typeddict.__required_keys__:
        if k not in checkdict:
            missing.add(k)
        if missing:
            _LOGGER.error(f"{log_start} is missing required {'entries' if len(k) > 1 else 'entry'} {k}, exiting inkBoard.")
            sys.exit()
    return missing

##May move some things of these to a util module

def loop_exception_handler(loop, context):

    asyncio.BaseEventLoop.default_exception_handler(loop, context)

    ##Hopefully this comment does not end up lost but:
    ##Create custom event loop policy that always returns the screen's mainloop
    ##That way, asyncio.get_event_loop() will always return the screen loop
    ##however, does maybe provide some issues with functions being called outside of the eventloop
    ##See documentation: https://docs.python.org/3/library/asyncio-policy.html#custom-policies

class YAMLNodeDict(dict):
    """Dict used in yaml parsing

    Should be a drop in replacement for normal dicts, but it also has a reference to where in the YAML documents it came from.
    This allows for clearer logging, for example

    Parameters
    ----------
    dict_ : dict
        The dict gotten from the yaml node
    node : yaml.Node
        The node the dict came from
    """

    def __init__(self, dict_: dict, node : "yaml.Node"):
        super().__init__(dict_)
        self._start_mark = node.start_mark
        self._end_mark = node.end_mark
        return

class ParsedAction:

    def __init__(self, action : Union[Callable, str, dict]):

        self._action = None
        self._parsed = False
        if isinstance(action,Callable):
            self._action = action
        else:
            self._action_to_parse = action

        if isinstance(action, (Callable,str)):
            self._data = {}
            self._options = {}
        else:
            action = dict(action)   ##Also allows being passed MappingProxies
            action_val = action.pop("action")
            if callable(action_val):
                self._action = action_val
            else:
                self._action_to_parse = action_val

            self._data = action.pop("data", {})
            self._options = action  ##Simply what is left over of the dict

        if hasattr(CORE,"screen"):
            self._parse_action()
        

    def __call__(self, *args, **kwargs):
        
        if not self._parsed:
            raise AttributeError("Cannot call functions before an action has been parsed")
        
        if self._action == None:
            return None
        
        return self._action(*args, **kwargs, **self._data)

    def _parse_action(self):
        
        if not self._action:
            try:
                self._action = CORE.screen.parse_shorthand_function(self._action_to_parse, self._options)
            except ShorthandNotFound as exce:
                _LOGGER.error(f"Unable to parse from {self._action}")

        self._parsed = True