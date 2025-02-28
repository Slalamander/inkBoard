"Constants"

import __main__
from typing import Callable, Literal
from pathlib import Path
import yaml

yaml

from ..constants import INKBOARD_FOLDER, CONFIG_FILE_TYPES

DEFAULT_CONFIG_FILE = "configuration.yaml"
BASE_FOLDER = Path.cwd()

SECRETS_YAML = 'secrets.yaml'
ENTITIES_YAML  = 'entities.yaml'

REQUIRED_KEYS = (
    "inkBoard",
    "device",
)

TEMPLATES_KEY = "templates"
DASHBOARD_KEYS = (
    TEMPLATES_KEY,
    "elements",
    "layouts",
    "popups",
    "main_tabs",
    "statusbar"
    )
"Config keys that indicate they are used to parse the dashboard, which means they will not be processed passed the first node when reading out the config initially."

TEMPLATE_VARIABLE_TAGS = (
    "!tmp_var",
    "!tmp_variable",
    "!template_var",
    "!template_variable"
)

TEMPLATE_EXTEND_TAGS = (
    "!tmp_extend",
    "!template_extend",
)

TEMPLATE_TAGS = (
    *TEMPLATE_VARIABLE_TAGS,
    *TEMPLATE_EXTEND_TAGS
)

YAML_STR_TAG = 'tag:yaml.org,2002:str'

validatortype = Callable[[Literal["Element_class"],Literal["Requested_type"]],None]