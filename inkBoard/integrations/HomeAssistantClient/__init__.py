"""
This library manages elements from PSSM and linked entities from Home Assistant, and provides additional comound elements in the HAelements library.
Import it first, or at least before importing the element library to allow it to add to the PSSM default colors and fonts.
"""

from typing import TYPE_CHECKING, Optional
from types import MappingProxyType
import logging

from inkBoard.helpers import *

if TYPE_CHECKING:
    from inkBoard import config, core as CORE
    from mdi_pil import mdiType
    from PythonScreenStackManager import pssm_types as pssm
    from PythonScreenStackManager.pssm.screen import PSSMScreen
    from . import client

logger = logging.getLogger(__name__)


##This one is required
async def async_setup(core: "CORE", config : "config") -> None:
    ##Screen can be gotten by importing at this point

    ha_config = config.configuration["home_assistant"]

    if "url" not in ha_config or "token" not in ha_config:
        logger.error("Home Assistant integration requires url and token to be set in the config. At least one is missing.")
        return False

    from . import client
    client.CORE = core
    HAclient = client.HAclient(core.screen)
    from . import parser
    parser.setup_elements()

    core.add_element_parser("HA", parser.parse_ha_element)
    return HAclient

async def async_start(core: "CORE", client : "client.HAclient"):
    client.setup_entity_functions()
    await client.connect_client()
    return

class home_assistantMap(TypedDict):
    "Dict with settings required for the home assistant client"

    url : str
    "Url to the home assistant server."

    token: str
    "Long lived access token to authenticate with the server."

    state_colors: dict
    """
    This way you can map the default foreground colors of connected elements to take on the same color when their state matches.
    Also accepts a default entry for unknown states.
    Will be used for elements where state_colors: True is set.
    """

    ping_pong_interval : 'pssm.DurationType'
    "Interval inbetween checking the connection to the server. Generally you can keep this undefined."

    unknown_icon : Optional['mdiType']
    "Default icon to indicate that an entity's state is unknown"

    unavailable_icon : Optional['mdiType']
    "Default icon to indicate that an entity is unavailable"

home_assistantMap.__required_keys__ = frozenset({'url','token'})
home_assistantMapDefaults = MappingProxyType({"state_colors": {}, "ping_pong_interval": 50, 'unknown_icon': "mdi:help", 'unavailable_icon': "mdi:exclamation-thick"})
