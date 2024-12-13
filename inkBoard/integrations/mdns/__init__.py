"""Integration to support mdns. 
Currently uses slimDNS: https://github.com/nickovs/slimDNS
"""

from typing import *
import logging
import asyncio

from inkBoard.platforms import FEATURES

if TYPE_CHECKING:
    from inkBoard import screen, config
    from .mdns import MDNSServer

_LOGGER = logging.getLogger(__name__)

async def async_setup(screen: "screen", config: "config"):
    device = screen.device
    
    if not device.has_feature(FEATURES.FEATURE_NETWORK):
        _LOGGER.error("Using mdns requires the device to have network capabilities")
        return False

    from .mdns import MDNSServer

    server = MDNSServer(device)
    return server

async def async_start(screen, server : "MDNSServer"):
    asyncio.create_task(server.run_server())
    return