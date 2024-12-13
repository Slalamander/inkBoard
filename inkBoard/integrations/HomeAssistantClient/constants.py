"""
Constants for use with the HA PSSM library
"""
from typing import Literal, Optional, Union
import yaml

from inkBoard import core as CORE

from PythonScreenStackManager.constants import INKBOARD, PSSM_COLORS, SHORTHAND_FONTS, SHORTHAND_ICONS 
from pathlib import Path

import logging

logger = logging.getLogger("inkBoard.HAClient")

__default_domain_actions: dict[Literal["domain"],Optional[Literal["action"]]] = {  
                        "default": None,
                        "switch": "switch.toggle",
                        "light": "light.toggle",
                        "button": "button.press",
                        "climate": "climate.toggle",
                        "fan": "fan.toggle",
                        "media_player": "media_player.toggle",
                        "remote": "remote.toggle",
                        "scene": "scene.turn_on",
                        "select": "select.next", ##For this one, cycle should be set to true automatically...
                        
                        "automation": "automation.trigger",
                        "script": "script.turn_on",
                        
                        "input_button": "input_button.press",
                        "input_boolean": "input_boolean.toggle",
                        "input_select": "input_select.select_next"
                        }

DEFAULT_DOMAIN_ACTIONS = __default_domain_actions
"""
Dict mapping certain HA domains to default actions that can be applied to elements without entity domain restrictions.
Domains without a default action are not present in this dict.
"""

all_entities_config = CORE.config.configuration.get("entities",{}).copy()
"All entitites as defined in the config file"

all_entities = {"sun.sun": {"entity_id": "sun.sun"}}
for entity_config in all_entities_config:
    if "entity_id" not in entity_config:
        logger.error(f"Entries in the entity config require an entity_id. Cannot add {entity_config}")
    else:
        all_entities[entity_config["entity_id"]] = entity_config

entity_tags : dict
"Entities defined in the entities.yaml file. Can be used to parse entities by prefixing the key with !entity (Same as in the yaml config)"

base_folder = CORE.config.folders["base_folder"]

entity_file = base_folder / "entitities.yaml"
if entity_file.exists():
    with open(entity_file) as f:
        #self.config = yaml.load(f, Loader=yaml.SafeLoader)
        entity_tags = yaml.load(f, Loader=yaml.SafeLoader)
    f.close()

    for tag, entity in entity_tags.items():
        if entity not in all_entities:
            all_entities[entity] = {"entity_id": entity}
else:
    entity_tags = {}

ENTITY_TAG_KEY = "!entity "
def parse_entity_tag(entity : str) -> Union[str,Literal[False]]:
    if entity.startswith(ENTITY_TAG_KEY):
        tag = entity.removeprefix(ENTITY_TAG_KEY)
        
        if tag not in entity_tags:
            msg = f"{tag} could not be found as a key in the entities.yaml file. "
            logger.exception(KeyError(msg))
            return False
        else:
            return entity_tags[tag]

_all_services_config = CORE.config.configuration.get("service_actions",{}).copy()

##Generally this should happen during import I think, and return a False maybe for the setup?
all_service_actions = {}
for service_config in _all_services_config:
    if "service_id" not in service_config:
        logger.error(f"Entries in the service_actions config require a service_id. Cannot add {service_config}")
    else:
        all_service_actions[service_config["service_id"]] = service_config

DEFAULT_HA_DT_FORMAT = "%Y-%m-%-dT%H:%M:%S.%Y+%H:%M"
"""
The default format Home Assistant seems to use for datetime strings.
Parsing this using `datetime.strptime()` throws an error, however it does work when using `datetime.fromisoformat()`
That means this constant is likely not necessary anywhere, but leaving it here in case.
"""

DEFAULT_PING_INTERVAL : int = 50 #seconds
"Default time in seconds to send a new ping"

MAX_PONGS_MISSED : int = 5
"Max amount of pongs to be missed before the connection is considered broken."

HOMEASSISTANT_BLUE : tuple = (3, 169, 244, 255)
"The Blue Color used in Home Assistant Branding :)"

PSSM_COLORS['home-assistant'] = HOMEASSISTANT_BLUE

SHORTHAND_FONTS['home-assistant'] = SHORTHAND_FONTS['quicksand-bold']
##The Home Assistant font is included as a default font, but for consistency the shorthand is only declared here

SHORTHAND_ICONS['home-assistant'] = Path(__file__).parent / 'home-assistant.png'

ERROR_STATES = {"unknown", "unavailable"}
"Shorthand for the states that indicate an error in the entity (so unknown or unavailable)"

UNKNOWN_ICON = "mdi:help"
"Default icon for unknown states"

UNAVAILABLE_ICON = "mdi:exclamation-thick"
"Default icon for unavailable states"

UNAVAILABLE_COLOR = "gray4"
"Color to use for text elements when the entity state is unavailable"

UNKNOWN_COLOR = "gray4"
"Color to use for text elements when the entity state is unknown"


cf = CORE.config.configuration["home_assistant"]
if "unavailable_color" in cf:
    UNAVAILABLE_COLOR = cf["unavailable_color"]

if "unknown_color" in cf:
    UNKNOWN_COLOR = cf["unknown_color"]

if "unavailable_icon" in cf:
    UNAVAILABLE_ICON = cf["unavailable_icon"]

if "unknown_icon" in cf:
    UNKNOWN_ICON = cf["unknown_icon"]

if "ping_pong_interval" in cf:
    DEFAULT_PING_INTERVAL = cf["ping_pong_interval"]
