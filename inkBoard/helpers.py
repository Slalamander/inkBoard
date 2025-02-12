"""
Small library with helper functions for inkBoard, that could not be included in the pssm tools.
Does not import anything from pssm or integration yet, and is mainly meant to supplement some small useful functions.
"""
import typing   ##Need to import typing to evaluate union strings (those are converted to typing.Union[...])
import asyncio
from typing import TYPE_CHECKING
from typing import TypedDict, TypeVar, Union, Literal, Callable
from types import ModuleType, MethodType, CoroutineType
import logging 
import sys
import importlib
from contextlib import suppress
from pathlib import Path

from inkBoard import CORE as CORE
from inkBoard.constants import CORESTAGES

from PythonScreenStackManager.exceptions import ShorthandNotFound
from PythonScreenStackManager.pssm import util as pssm_util

if TYPE_CHECKING:
    from PythonScreenStackManager.elements import Element
    from PythonScreenStackManager.pssm import PSSMScreen
    import yaml

_LOGGER = logging.getLogger("inkBoard")

_ph = TypedDict("ph")
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

def add_required_keys(td : _ph, keys : frozenset):
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

def add_optional_keys(td : _ph, keys : frozenset):
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

def check_required_keys(typeddict : _ph, checkdict : dict, log_start : str):
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
    This allows for clearer logging, for example.

    Has an overwritten __repr__ method that returns it as the filename + line numbers

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

    def __repr__(self):
        return self.format_marks(self._start_mark, self._end_mark)
    
    @staticmethod
    def format_marks(start_mark : "yaml.Mark", end_mark : "yaml.Mark" = None) -> str:
        """Formats a yaml mark to a string similar as in logging

        Parameters
        ----------
        start_mark : yaml.Mark
            The start mark to use
        end_mark : yaml.Mark, optional
            The end mark to use, by default None

        Returns
        -------
        str
        """        

        f = Path(start_mark.name).name
        if end_mark:
            return f"{f} lines {start_mark.line}-{end_mark.line}"
        else:
            return f"{f} line {start_mark.line}"


class ParsedAction:
    """Helper to aid in parsing actions shorthands and dicts

    Actions can be passed as any of the valid types, and the object and inkBoard take care of parsing.
    The action should not be called before the CORE is starting, since them being parsed by then is not a given.

    Parameters
    ----------
    action : Union[Callable, str, dict]
        The action to parse. The ``map`` key is not used, otherwise the same syntax as element actions apply.
    yamlmarks : tuple[&quot;yaml.Mark&quot;, &quot;yaml.Mark&quot;], optional
        start and optionally end_mark of the yaml entry, by default ()
        used for logging
    """

    _notParsed : set["ParsedAction"] = set()

    def __init__(self, action : Union[Callable, str, dict], awaitable: bool = True, yamlmarks : tuple["yaml.Mark", "yaml.Mark"] = ()):

        self._action = None
        self._parsed = False
        self._awaitable = awaitable
        self.yamlstr = None

        if yamlmarks:
            self.yamlstr = YAMLNodeDict.format_marks(*yamlmarks)

        if isinstance(action, (Callable,str)):
            if isinstance(action,Callable):
                self._action = action
            else:
                self._action_to_parse = action

            self._data = {}
            self._options = {}
        else:
            if isinstance(action,YAMLNodeDict):
                self.yamlstr = str(action)
            action = dict(action)   ##Also allows being passed MappingProxies
            action_val = action.pop("action")
            if callable(action_val):
                self._action = action_val
            else:
                self._action_to_parse = action_val

            self._data = action.pop("data", {})
            self._options = action  ##Simply what is left over of the dict

        if CORE.stage > CORESTAGES.SETUP:
            self._parse_action()
        else:
            self._notParsed.add(self)
        

    def __call__(self, *args, **kwargs):
        if isinstance(self._action, Exception):
            raise self._action
        elif not self._parsed:
            AttributeError("Cannot call functions before its action has been parsed")

        if self._action == None:
            return None
        elif not pssm_util.iscoroutinefunction(self._action):
            ##I don't think this would work right? Since most coroutine checks check before making the call

            return self._action(*args, **kwargs, **self._data)
        else:
            ##If this runs into issuess with awaiting etc.
            ##Check the fix for the trigger interceptor, may be an issue with threadsafety
            ##Fix would be to submit the coroutine to the correct event loop
            loop = asyncio.get_event_loop()
            return loop.create_task(
                self._action(*args, **kwargs, **self._data))
        raise AttributeError("Cannot call functions before its action has been parsed")

    def _parse_action(self):
        
        if not self._action:
            try:
                self._action = CORE.screen.parse_shorthand_function(self._action_to_parse, self._options)
            except ShorthandNotFound as exce:
                msg = f"Unable to parse from {self._action_to_parse}"
                self._action = exce
                if self.yamlstr:
                    _LOGGER.error(msg, extra={"YAML": self.yamlstr})
                else:
                    _LOGGER.error(msg)
                raise
        
        assert self._action == None or callable(self._action), f"Invalid type of action for {self._action}: {type(self._action)}"

        if asyncio.iscoroutinefunction(self._action) and self._awaitable:
            self.__class__ = _AsyncParsedAction

        self._parsed = True
        if self in self._notParsed:
            self._notParsed.remove(self)

    @classmethod
    def parse_actions(cls) -> bool:
        """Parses the actions for all yet unparsed instances

        Returns
        -------
        bool
            If every instance parsed successfully
        """

        errored = False
        for p in cls._notParsed.copy():
            try:
                p._parse_action()
            except ShorthandNotFound:
                errored = True
        return errored


class _AsyncParsedAction(ParsedAction):

    async def __call__(self, *args, **kwargs):
        return await self._action(*args, **kwargs, **self._data)
