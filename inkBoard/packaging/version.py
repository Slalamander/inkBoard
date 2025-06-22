"Helps with comparing versions"

from typing import TYPE_CHECKING, Union, Literal

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

InkboardVersion = parse_version(inkBoard.__version__)
PSSMVersion = parse_version(PSSM.__version__)

def get_comparitor_string(input_str: str) -> Literal[comparisonstrings]:
    "Returns the comparitor (==, >= etc.) in a string, or None if there is None."
    if c := (x for x in VERSION_COMPARITORS if x in input_str):
        return c[0]
    return

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
