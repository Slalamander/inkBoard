"""
Small library with helper functions for inkBoard, that could not be included in the pssm tools.
Does not import anything from pssm or integration yet, and is mainly meant to supplement some small useful functions.
"""
import typing   ##Need to import typing to evaluate union strings (those are converted to typing.Union[...])
from typing import TYPE_CHECKING
from typing import TypedDict, Generic, TypeVar, Callable, Union, Literal
from types import ModuleType
import functools
import logging 
import sys
import importlib
from contextlib import suppress

if TYPE_CHECKING:
    from PythonScreenStackManager.elements import Element

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
def reload_full_module(module: Union[str,ModuleType], exclude: list[str] = []):    
    """Reloads the module and all it's submodules presently imported

    Keep in mind reloading imports the module, so things can behave unexpectedly, especially if order matters.
    Generally be careful using this, reloading does not mean imports in none reloaded modules are refreshed, which can cause issuess when i.e. calling `isinstance`
    
    Parameters
    ----------
    module : Union[str,ModuleType]
        The base module to reload.
    exclude : list[str]
        List with module names that do not get excluded. Names need to match in full.
    """    
    if isinstance(module, ModuleType):
        module = module.__package__
    
    if isinstance(exclude,str):
        exclude = [exclude]

    mod_list = [x for x in sys.modules.copy() if x.startswith(module) and not x in exclude]
    for mod_name in mod_list:
        mod = sys.modules[mod_name]
        try:
            importlib.reload(mod)
        except ModuleNotFoundError:
            _LOGGER.error(f"Could not reload module {mod_name}")
    
    for mod_name in mod_list:
        sys.modules.pop(mod_name)
    
    return

def function_parameter_dict(func: Callable, types_as_str: bool = False, is_method: bool = False) -> dict[Literal["required", "optional"], dict[str, dict[Literal["type_hint","default"],str]]]:
    """_summary_

    Parameters
    ----------
    func : Callable
        The function to create the parameter dict of
    types_as_str : bool
        If True, Any type hints will be converted into a string representation. This means either using the types __name__ if present, otherwise just casting it to a string.
    is_method : bool
        If True, the function is considered a method, and the first argument (generally self or cls) will be omitted

    Returns
    ----------
    dict:
        A dict with the keys required and optional, for required parameters and optional parameters.
        If a parameter has a type hint, it is included as a string in the dict for said parameter under 'type_hint'. For optional parameters, their default values are included as well.
    """
    if func.__defaults__:
        num_defaults = len(func.__defaults__)
        default_values = func.__defaults__
    else:
        num_defaults = 0
        default_values = []

    f_code = func.__code__
    num_required = f_code.co_argcount - num_defaults

    func_vars = f_code.co_varnames[:f_code.co_argcount]

    if is_method:
        req_args = func_vars[1:num_required]
    else:
        req_args = func_vars[:num_required]

    opt_args = func_vars[num_required:]

    type_hints = func.__annotations__


    required = {}
    for var_name in req_args:
        if var_name in type_hints:
            hint = type_hints[var_name]
            if types_as_str:
                hint = getattr(hint,"__name__") if hasattr(hint, "__name__") else str(hint)
            required[var_name] = {"type_hint": hint}
        else:
            required[var_name] = {}

    optional = {}
    for i, var_name in enumerate(opt_args):
        optional[var_name] = {"default": default_values[i]}

        if var_name in type_hints:
            hint = type_hints[var_name]
            if types_as_str:
                if types_as_str:
                    hint = getattr(hint,"__name__") if hasattr(hint, "__name__") else str(hint)
            optional[var_name].update({"type_hint": hint})

    return {"required": required, "optional": optional}


T = TypeVar('T')

class classproperty(Generic[T]):
    "Used to avoid the deprecation warning (and the extra writing) needed to set class properties"
    
    def __init__(self, method: Callable[..., T]):
        self.method = method
        functools.update_wrapper(self, wrapped=method) # type: ignore

    def __get__(self, obj, cls=None) -> T:
        if cls is None:
            cls = type(obj)
        return self.method(cls)