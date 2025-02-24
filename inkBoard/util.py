"""Utilities for inkBoard

This module (should) not contain functions etc. that are mainly useful when writing integrations or devices, but are otherwise not often needed.
"""

##Difference-ish between util and a helper, see the table here:
##https://github.com/erikras/react-redux-universal-hot-example/issues/808#issuecomment-1528847708

import inspect
import sys
import importlib
from types import ModuleType
from pathlib import Path
from typing import Union, Callable, Literal

import inkBoard

from PythonScreenStackManager.elements import Element
from PythonScreenStackManager.tools import DummyTask, update_nested_dict
from PythonScreenStackManager.util import classproperty, isclassproperty


_LOGGER = inkBoard.getLogger(__name__)

##Move this to helpers
def get_module_elements(module: ModuleType) -> dict[str,"Element"]:
    """
    Creates a dict with all the valid elements in a module to use in element parsers, for example

    Parameters
    ----------
    module : ModuleType
        The module to inspect. It is asserted to be a python module

    Returns
    -------
    dict[str,`Element`]
        A dict with the names users can use as type in the yaml config, and the actual class is represents
    """    

    assert inspect.ismodule(module), "Module must be a module type"

    element_dict = {}
    for name, cls in inspect.getmembers(module, inspect.isclass):
        if (module.__name__ in cls.__module__
            and issubclass(cls,Element) 
            and not inspect.isabstract(cls) 
            and name[0] != "_"):
            element_dict[name] = cls

    return element_dict

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


##Improve this one with the one created for the documentation?
def function_parameter_dict(func: Callable, types_as_str: bool = False, is_method: bool = False) -> dict[Literal["required", "optional"], dict[str, dict[Literal["type_hint","default"],str]]]:
    """Returns a dict with function params etc.

    Code here is currently based on low level api. It will be replaced later with inspect. functions
    Similar to what is used in the docs

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

