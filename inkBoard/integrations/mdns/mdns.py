"Bindings for mdns services to inkBoard devices"

from typing import *
import asyncio
import logging
import socket

from .slimDNS import SlimDNSServer, select

if TYPE_CHECKING:
    from inkBoard.platforms import Device

##Giving mdns up for now. From what I've found, zeroconf is the only reliable/well explained library
##But registering a device/api token to the HA websocket through it is not something I could find in the dev docs for now.

_LOGGER = logging.getLogger(__name__)

class MDNSServer:
    def __init__(self, device: "Device"):
        
        self._device = device
        # local_addr = device.network.IP
        local_addr = '127.0.0.1'
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        print(s.getsockname()[0])
        s.close()
        self._server = SlimDNSServer(local_addr, "inkBoard")

    async def run_server(self):
        server = self._server
        _LOGGER.info("Starting mdns server")
        host_address_bytes = server.resolve_mdns_address("ridberry.local")
        print(f"Got HA adress {host_address_bytes}")
        while True:
            read_sockets = [server.sock]
            _LOGGER.info("Reading out server")
            (r, _, _) = await asyncio.to_thread(select,
                                    read_sockets, [], [])
            if server.sock in r:
                server.process_waiting_packets()
                _LOGGER.info("Read out")
                print(server.adverts)
            
            await asyncio.sleep(20)