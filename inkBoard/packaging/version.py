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
    _VersionClass = Version
else:
    try:
        from packaging.version import Version as _VersionClass
    except (ImportError, ModuleNotFoundError):
        from packaging.version import LegacyVersion as _VersionClass
    
    class Version(_VersionClass):
        "Dummy Version class to prevent errors when importing outside of type checking"

        @classmethod
        def __instancecheck__(cls, instance):
            #For some reason this is not called when isinstance is called on the class. Not sure why
            return

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
    tuple[Union[str,None], str, str]
        _description_
    """    

    if cmp := get_comparitor_string(input_str):
        name, version = input_str.split(cmp)
        if input_str.strip().startswith(cmp):
            return None, cmp, version.strip()
        else:
            return name.strip(), cmp, version.strip()
        
    raise ValueError(f"{input_str} does not contain a version comparison")

# def compare_versions(requirement: Union[str,"Version"], compare_version: Union[str,"Version"]) -> bool:
def compare_versions(version_left: Union[str,"Version"], version_right: Union[str,"Version"], comparitor : comparisonstrings = ">=") -> bool:
    """Does simple version comparisons.

    For requirements, accepts both a general requirement string (i.e. '1.0.0'), or a comparison string (i.e. package < 1.0.0))

    Parameters
    ----------
    requirement : Union[str,&quot;Version&quot;]
        The requirement to test
    compare_version : Union[str,Version]
        The version to compare the requirement to.
        If None, it will be treated as '>='

    Returns
    -------
    bool
        True if the requirement is satisfied, false if not
    """

    if isinstance(version_left,str):
        version_left = parse_version(version_left)

    if isinstance(version_right, str):
        ##To be sure that the pkg_resources Version is also fine
        version_right = parse_version(version_right)
    
    if comparitor is None:
        comparitor = ">="
    if comparitor not in VERSION_COMPARITORS:
        raise ValueError(f"{comparitor} is not a valid symbol for making comparisons")
    
    comp_str = f"version_left {comparitor} version_right"
    return eval(comp_str, {}, {"version_left": version_left, "version_right": version_right})

def string_compare_version(input_str : str, **versions) -> bool:
    """Handles comparisons from a string

    Use vals to substitute variables in the input string. The function splits and substitutes.
    i.e. `string_compare_version(input_str = "my_package >= 0.0.1", my_package = "0.1.0")` will lead to a string of "0.1.0 >= 0.0.1".

    Parameters
    ----------
    input_str : str
        The string to compare

    Returns
    -------
    bool
        Result of the comparison

    Raises
    ------
    ValueError
        Raised if input_str cannot be used as a comparison
    """

    comparitor = get_comparitor_string(input_str)
    if not comparitor:
        raise ValueError(f"Cannot make version comparison of {input_str}, no comparitor found")
    
    vl, comp, vr = split_comparison_string(input_str)
    vl = vl.strip()
    vr = vr.strip()

    if vl in versions:
        vl = versions[vl]
        if not isinstance(vl, (str, _VersionClass)):
            vl = vl.__version__

    if vr in versions:
        vr = versions[vr]
        if not isinstance(vr, (str, _VersionClass)):
            vr = vr.__version__
    return compare_versions(vl, vr, comp)

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
    
