"Helps with comparing versions"

from typing import TYPE_CHECKING, Union, Literal
import itertools

import inkBoard
import PythonScreenStackManager as PSSM

from .constants import (
    VERSION_COMPARITORS,
)

from .types import (
    comparisonstrings
)

try:
    from packaging.version import parse as parse_version
except ModuleNotFoundError:
    from pkg_resources import parse_version

if TYPE_CHECKING:
    from packaging.version import Version
else:
    class Version:
        "Dummy Version class to prevent errors when importing outside of type checking"

        def __new__(cls, *args, **kwargs):
            return parse_version(*args, **kwargs)

        def __init__(self, *args, **kwargs):
            raise NotImplementedError("Cannot instantiate, use parse_version. This class is only for typehinting")

InkboardVersion = parse_version(inkBoard.__version__)
PSSMVersion = parse_version(PSSM.__version__)

def get_comparitor_string(input_str: str) -> Union[Literal[comparisonstrings],None]:
    "Returns the comparitor (==, >= etc.) in a string, or None if there is None."
    for c in itertools.dropwhile(lambda x: x not in input_str, VERSION_COMPARITORS):
        return c
    else:
        return None
    if c := (x for x in VERSION_COMPARITORS if x in input_str):
        return c[0]
    return

def split_comparison_string(input_str : str) -> tuple[str, Union[str,None], Union[str,None]]:
    """Splits the string into the name, comparison string and version string

    If it is not 

    Parameters
    ----------
    input_str : str
        The string to split

    Returns
    -------
    tuple[str, Union[str,None], Union[str,None]]
        _description_
    """    

    if cmp := get_comparitor_string(input_str):
        name, version = input_str.split(cmp)
        return name, cmp, version
    else:
        raise ValueError(f"{input_str} does not contain a version comparison")

def compare_versions(requirement: Union[str,"Version"], compare_version: Union[str,"Version"]) -> bool:
    """Does simple version comparisons.

    For requirements, accepts both a general requirement string (i.e. '1.0.0'), or a comparison string (i.e. package < 1.0.0))

    Parameters
    ----------
    requirement : Union[str,&quot;Version&quot;]
        The requirement to test
    compare_version : Union[str,Version]
        The version to compare the requirement to

    Returns
    -------
    bool
        True if the requirement is satisfied, false if not
    """

    if isinstance(compare_version,str):
        compare_version = parse_version(compare_version)

    if not isinstance(requirement, str):
        ##To be sure that the pkg_resources Version is also fine
        return compare_version >= requirement

    if c := [x for x in VERSION_COMPARITORS if x in requirement]:
        req_version = requirement.split(c[0])[-1]   ##With how the comparitors are set up, 0 should always be the correct one
        comp_str = f"compare_version {c[0]} required_version"
    else:
        req_version = requirement
        comp_str = "compare_version >= required_version"
    
    return eval(comp_str, {}, {"compare_version": compare_version, "required_version": parse_version(req_version)})

def write_version_filename(package_name : str, version : Union[str,"Version"], suffix : str = ".zip") -> str:
    """Creates the appropriate filename for an inkBoard index package

    The returned string will have the form of "{package_name}-{version}{suffix}".
    If suffix evaluates to a boolean `True`, it will be included, otherwise not.

    Parameters
    ----------
    package_name : str
        The name of the package
    version : str, Version
        The version of the package
    suffix : str, optional
        Suffix for after the strin, by default ".zip"

    Returns
    -------
    str
        The formatted package name
    """    
    
    if suffix:
        return f"{package_name}-{version}{suffix}"
    else:
        return f"{package_name}-{version}"