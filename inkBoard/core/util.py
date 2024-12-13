
import inspect
from types import ModuleType
from pathlib import Path

from PythonScreenStackManager.elements import Element

##In core since it needs to be reloaded when pssm reloads
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

    ##See if this can be rewritten to ensure it does not need to be imported everytime.
    ##Probably just add an import for Element in there.
    # from PythonScreenStackManager.elements import Element #Just to prevent any preliminary imports, don't import it globally
    assert inspect.ismodule(module), "Module must be a module type"

    element_dict = {}
    for name, cls in inspect.getmembers(module, inspect.isclass):
        if (module.__name__ in cls.__module__
            and issubclass(cls,Element) 
            and not inspect.isabstract(cls) 
            and name[0] != "_"):
            element_dict[name] = cls

    return element_dict

