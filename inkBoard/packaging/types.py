from typing import Literal, TypedDict

internalinstalltypes = Literal["platform", "integration"]
packagetypes = Literal['package', 'integration', 'platform']

class PackageDict(TypedDict):

    created: str
    "The date and time the package was created, in isoformat"

    created_with: Literal["inkBoard", "inkBoarddesigner"]
    "Whether this package was created via inkBoard itself, or via the designer"

    versions: dict[Literal["inkBoard", "PythonScreenStackManager", "inkBoarddesigner"],str]
    "The versions of the core packages installed when creating it. Designer version is None if not installed"

    platform: str
    "The platform the package was created for"

class PackageIndex(TypedDict):
    "Structure of the index.json file in the package index"

    inkBoard : str
    "inkBoard version the index was made on"

    inkBoarddesigner : str
    "Version of inkBoard designer the index was made on"

    PythonScreenStackManager : str
    "Version of PSSM the index was made on"

    timestamp : str
    "ISO format timestamp of when the index file was run"

    platforms : dict[str,dict[Literal["main","dev"],str]]
    "List of platforms and their versions in the main and dev branch"

    integrations : dict[str,dict[Literal["main","dev"],str]]
    "List of integrations and their versions in the main and dev branch"

comparisonstrings = Literal[
    '==', '!=', '>=', '<=', '>', '<'
]

class NegativeConfirmation(UserWarning):
    "Raised by ask confirm if the confirmation was negative"