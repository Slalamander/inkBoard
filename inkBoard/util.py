"""Utilities for inkBoard

This module (should) not contain functions etc. that are mainly useful when writing integrations or devices, but are otherwise not often needed.
"""

import inspect
from types import ModuleType
from pathlib import Path

from PythonScreenStackManager.elements import Element

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
