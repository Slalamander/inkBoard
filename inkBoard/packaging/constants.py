
from types import MappingProxyType
import zipfile

from inkBoard.constants import INKBOARD_FOLDER

from .types import (
    packagetypes,
)

INKBOARD_PACKAGE_INTERNAL_FOLDER = ".inkBoard"
#Folder name where files from a package are put which are gotten from or destined to the site-packages inkBoard folder.

PACKAGE_INDEX_URL = "https://github.com/Slalamander/inkBoard-package-index"
"url to the package index"

REPO_INDEX_FILE = "index.json"
INTERNAL_PACKAGE_INDEX_FILE = "package_index.json"
INDEX_FILE_PATH = INKBOARD_FOLDER / "files" / INTERNAL_PACKAGE_INDEX_FILE

ZIP_COMPRESSION = zipfile.ZIP_BZIP2
ZIP_COMPRESSION_LEVEL = 9

PACKAGE_ID_FILES : dict[packagetypes,str] = MappingProxyType({
    'package': 'package.json',
    'integration': 'manifest.json',
    'platform': 'platform.json'
})

VERSION_COMPARITORS = ('==', '!=', '>=', '<=', '>', '<')    ##The order of this is important!
"Comparison operators allowed for versioning, so they can be evaluated internally"

INDEX_PACKAGE_KEYS = (
    "platforms",
    "integrations",
)
#The actual keys that hold all the packages. The other keys in the index are additional information.

PACKAGETYPE_TO_INDEX_KEY = {
    "platform": "platforms",
    "integration": "integrations"
}
INDEX_KEY_TO_PACKAGETYPE = {v: k for k,v in PACKAGETYPE_TO_INDEX_KEY.items()}

DESIGNER_FILES = {"designer", "designer.py"}
#Files in integrations etc. meant for the designer. Currently these are not included in files in the package index

REQUIREMENTS_FILE = 'requirements.txt'

