
from types import MappingProxyType
import zipfile

from .types import (
    packagetypes,
)

INKBOARD_PACKAGE_INTERNAL_FOLDER = ".inkBoard"
#Folder name where files from a package are put which are gotten from or destined to the site-packages inkBoard folder.

PACKAGE_INDEX_URL = "https://github.com/Slalamander/inkBoard-package-index"
"url to the package index"

ZIP_COMPRESSION = zipfile.ZIP_BZIP2
ZIP_COMPRESSION_LEVEL = 9

PACKAGE_ID_FILES : dict[packagetypes,str] = MappingProxyType({
    'package': 'package.json',
    'integration': 'manifest.json',
    'platform': 'platform.json'
})

VERSION_COMPARITORS = ('==', '!=', '>=', '<=', '>', '<')    ##The order of this is important!
"Comparison operators allowed for versioning, so they can be evaluated internally"

DESIGNER_FILES = {"designer", "designer.py"}
#Files in integrations etc. meant for the designer. Currently these are not included in files in the package index

REQUIREMENTS_FILE = 'requirements.txt'

