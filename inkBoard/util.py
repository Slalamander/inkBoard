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