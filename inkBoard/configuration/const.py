"Constants"

import __main__
from pathlib import Path

from ..constants import INKBOARD_FOLDER, CONFIG_FILE_TYPES

DEFAULT_CONFIG_FILE = "configuration.yaml"
BASE_FOLDER = Path.cwd()

SECRETS_YAML = 'secrets.yaml'
ENTITIES_YAML  = 'entities.yaml'

REQUIRED_KEYS = (
    "inkBoard",
    "device",
)

DASHBOARD_KEYS = (
    "elements",
    "layouts",
    "popups",
    "main_tabs",
    "statusbar"
    )
"Config keys that indicate they are used to parse the dashboard, which means they will not be processed passed the first node when reading out the config initially."