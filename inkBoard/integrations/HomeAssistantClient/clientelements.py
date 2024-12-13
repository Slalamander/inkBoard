"""
Elements that show info regarding the client, and not to any entities per say
"""

import asyncio
from typing import TYPE_CHECKING

from PythonScreenStackManager import tools
from PythonScreenStackManager.elements import baseelements as base, menuelements as menu
from PythonScreenStackManager.tools import DummyTask

if TYPE_CHECKING:
    from .client import HAclient


class ClientElement(base.Icon):
    def __init__(self, icon = "home-assistant", tap_action = "show_client_popup", **kwargs):
        self._HAclient = None
        self._monitorTask : asyncio.Task = DummyTask()

        if tap_action == "show_client_popup":
            tap_action = {"action": "element:show-popup", "element_id": "home-assistant-menu"}#"data": {"popupId": "home-assistant-menu"}}

        super().__init__(icon=icon, tap_action=tap_action, badge_icon="mdi:close-thick", **kwargs)

    @property
    def HAclient(self) -> "HAclient":
        "The Home Assistant websocket client connected to the element"
        return self._HAclient   

    def on_add(self):
        # asyncio.create_task(self._update_status_icon())
        loop = self.parentPSSMScreen.mainLoop
        self._monitorTask = loop.create_task(self._monitor_client_state())

    async def _monitor_client_state(self):
        "Async function that awaits the device conditions notifications and updates the element when needed"
        
        self.HAclient ##Is this still None? -> should not be the case
        condition : asyncio.Condition = self.HAclient.websocketCondition
        testVal = getattr(self.HAclient,"clientState")
        asyncio.create_task(self.update_icon())

        while self.onScreen:
            try:
                async with condition:
                    await condition.wait_for(lambda : testVal != self.HAclient.clientState)
                    testVal = self.HAclient.clientState

                    asyncio.create_task(self.update_icon())
            except asyncio.CancelledError:
                break

    async def update_icon(self):
        testVal = self.HAclient.clientState
        if testVal == "connected":
            badge = None #"mdi:check-bold" ##Will change this, to show a checkmark for a second or so before dissapearing
            ##Keep in mind, that task should also be cancelled if still running
        elif testVal == "connecting":
            badge = "mdi:autorenew"
        else:
            badge = "mdi:close-thick"

        if testVal == "connected" and self.badge_icon != None:
            await self.async_update({"badge_icon": "mdi:check-bold"})
            await asyncio.sleep(3)
            # await self.Async_update({"badge_icon": None})

        await self.async_update({"badge_icon": badge})
        # self.imgData.show()
        return

class HomeAssistantMenu(menu.UniquePopupMenu):

    def __init__(self,  **kwargs):

        fSize = "0.4*h"
        buttonSettings = {"text_x_position": "left", "font_size":fSize}
        titleTxt = f"Not connected to Home Assistant"
        self.__titleButton = base.Button(titleTxt, **buttonSettings)
        self.__integrationButton = base.Button("inkBoard integration not found", **buttonSettings)

        # button_col = menu.DEFAULT_MENU_BUTTON_COLOR
        
        buttonSettings["background_color"] = menu.DEFAULT_MENU_BUTTON_COLOR
        buttonSettings["text_x_position"] = "center"

        self.__connectButton = base.Button("Connect", **buttonSettings)
        self.__reconnectButton = base.Button("Reconnect", **buttonSettings)
        self.__disconnectButton = base.Button("Disconnect", **buttonSettings)

        ##No background means badge doesn't show --> fix that
        iconCol = "home-assistant"
        self.__clientElt = ClientElement(tap_action=None, icon_color = iconCol) #, backgroundShape = "circle")
        self.__integrationIcon = base.Icon("mdi:devices", icon_color=iconCol)

        self.__HAclient = None

        popupid = "home-assistant-menu"
        height = 225 #3*50 + 2*10

        super().__init__(popupid, "Home Assistant", height=height, id=popupid, **kwargs)

    #region
    @property
    def HAclient(self) -> "HAclient":
        "The Home Assistant websocket client connected to the element"
        return self._HAclient
    
    @property
    def _HAclient(self)-> "HAclient":
        return self.__HAclient
    
    @_HAclient.setter
    def _HAclient(self, value):
        self.__HAclient = value
        self._client_set()
    #endregion

    def _client_set(self):
        "Called after the element's Client has been set"
        self.__connectButton.tap_action = tools.wrap_to_tap_action(self.HAclient.connect_client)
        self.__reconnectButton.tap_action = tools.wrap_to_tap_action(self.HAclient.reconnect_client)
        self.__disconnectButton.tap_action = tools.wrap_to_tap_action(self.HAclient.disconnect_client)
        
        s = self.screen
        # self.mainLoop.create_task(self.__clientElt.update_icon())
        asyncio.create_task(self.__clientElt.update_icon())

    def build_menu(self):
        
        m = "w*0.02"
        h = 50
        h_margin = 5
        # [[h, (None,m), (networkIcon, "r"), (None,m) , (wifiButton,"?")]
        layout = [
            [h, (None,m), (self.__clientElt, "r"), (None,m), (self.__titleButton,"?")],
            [h_margin],
            [h, (None,m), (self.__integrationIcon, "r"), (None,m), (self.__integrationButton,"?")],
            [h_margin],
            ["?", (self.__reconnectButton,"?"), (self.__connectButton,"?"), (self.__disconnectButton,"?")]
        ]
        
        self.menuLayout = base.Layout(layout)
        return self.menuLayout

    async def async_show(self, *args, **kwargs):
        asyncio.create_task(self._monitor_client_state())
        return await super().async_show(*args, **kwargs)

    async def _monitor_client_state(self):
        "Async function that awaits the device conditions notifications and updates the element when needed"
        
        self.HAclient ##Is this still None? -> should not be the case
        condition : asyncio.Condition = self.HAclient.websocketCondition
        testVal = getattr(self.HAclient,"clientState")
        asyncio.create_task(self._update_buttons())

        while self.onScreen:
            async with condition:
                await condition.wait_for(lambda : testVal != self.HAclient.clientState)
                testVal = self.HAclient.clientState

                asyncio.create_task(self._update_buttons())
        
    async def _update_buttons(self):
        
        update_coros = set()
        testVal = self.HAclient.clientState
        if testVal == "connected":
            text = "Connected to" ##Will change this, to show a checkmark for a second or so before dissapearing
            ##Keep in mind, that task should also be cancelled if still running
        elif testVal == "connecting":
            text = "Connecting to"
        else:
            text = "Disconnected from"

        server_name = self.HAclient.server_config["name"]
        if server_name == None: server_name = "Home Assistant"
        button_text = f"{text} {server_name}"
        update_coros.add(self.__titleButton.async_update({"text": button_text}))

        if self.HAclient.server_config["integration"]:
            ib_int_text = "inkBoard integration detected"
            badge = None
        else:
            ib_int_text = "inkBoard integration not found"
            badge = "mdi:close-thick"

        update_coros.add(self.__integrationButton.async_update({"text": ib_int_text}))
        update_coros.add(self.__integrationIcon.async_update({"badge_icon": badge}))

        await asyncio.gather(*update_coros)
        return