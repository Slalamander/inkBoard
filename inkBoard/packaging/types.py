from typing import Literal, TypedDict, TYPE_CHECKING, NewType

from inkBoard.types import manifestjson, platformjson, inkboardrequirements  # noqa: F401

if TYPE_CHECKING:
    from .version import Version

internalinstalltypes = Literal["platform", "integration"]
downloadinstalltypes = Literal["platform", "integration"]
packagetypes = Literal['package', 'integration', 'platform']
branchtypes = Literal["main", "dev"]

class PackageDict(TypedDict):
    "Dict holding info for a packaged inkBoard configuration"

    created: str
    "The date and time the package was created, in isoformat"

    created_with: Literal["inkBoard", "inkBoarddesigner"]
    "Whether this package was created via inkBoard itself, or via the designer"

    versions: dict[Literal["inkBoard", "PythonScreenStackManager", "inkBoarddesigner"],"Version"]
    "The versions of the core packages installed when creating it. Designer version is None if not installed"

    platform: str
    "The platform the package was created for"

    requirements : inkboardrequirements
    "Requirements for this package"

class indexpackagedict(TypedDict):
    "Holds information pertaining to a package in the index"

    version : "Version"
    "The package's version"

class PackageIndex(TypedDict):
    "Structure of the index.json file in the package index"

    inkBoard : dict[branchtypes,"Version"]
    "inkBoard version the index was made on"

    inkBoarddesigner : dict[branchtypes,"Version"]
    "Version of inkBoard designer the index was made on"

    PythonScreenStackManager : dict[branchtypes,"Version"]
    "Version of PSSM the index was made on"

    timestamp : dict[branchtypes, str]
    "ISO format timestamp of when the index file was last updated"

    platforms : dict[str,dict[branchtypes,indexpackagedict]]
    "List of platforms and their versions in the main and dev branch"

    integrations : dict[str,dict[branchtypes,indexpackagedict]]
    "List of integrations and their versions in the main and dev branch"

comparisonstrings = Literal[
    '==', '!=', '>=', '<=', '>', '<'
]

class NegativeConfirmation(UserWarning):
    "Raised by ask confirm if the confirmation was negative"