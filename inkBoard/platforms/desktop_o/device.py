"""
This device can be used in desktop environments.
It is an extension of the base device that comes with PythonScreenStackManager, since it (will) provide functionality for somewhat easy extension of the functionality using integrations.
"""

import __main__
import asyncio
import tkinter as tk
from typing import TYPE_CHECKING, Union
from pathlib import Path
import platform

from PIL import Image, ImageTk

from inkBoard.platforms.basedevice import BaseDevice, InkboardDeviceFeatures, \
                                    BaseBacklight, BaseBattery, BaseNetwork
from inkBoard.constants import INKBOARD_FOLDER

from PythonScreenStackManager.devices import windowed
from PythonScreenStackManager.tools import DummyTask

try:
    #plyer module is optional, provides additional device features
    import plyer #@IgnoreExceptions
except ModuleNotFoundError:
    plyer = False

if TYPE_CHECKING:
    from PythonScreenStackManager.pssm_types import *

class Device(BaseDevice, windowed.Device):
    "inkBoard device for desktop environments"

    def __init__(self, name : str = None,
                frame_rate : int = 20, screenWidth = 1280, screenHeight = 720, fullscreen : bool = False, resizeable : bool = False, cursor : str = "target",
                screenMode : str = "RGB", imgMode : str = "RGBA", defaultColor: "ColorType"  = "white",
                interactive : bool = True, network : bool = True, backlight : bool = False, backlight_alpha : int = 175,
                window_icon: Union[str,Path] = "inkboard"
                ):

        self._model = None

        feature_dict = {"interactive": interactive, "backlight": backlight, "network": network}
        if plyer:
            bat_state = plyer.battery.get_state()
            if not all(v is None for v in bat_state.values()):
                feature_dict["battery"] = True

        features = InkboardDeviceFeatures(**feature_dict)

        ##Gotta see what needs to be overwritten after this
        windowed.Device.__init__(self, name, frame_rate,  
                        screenWidth, screenHeight, fullscreen, resizeable,
                        cursor, screenMode, imgMode, defaultColor, features=features)
        
        if window_icon in {None, "inkboard"}:
            window_icon = Path(INKBOARD_FOLDER) / "files" /"icons" / "inkboard.ico"
        self.window.wm_iconbitmap(window_icon)

class Battery(BaseBattery):
        "Device battery. Not used if unsupported by plyer."

        def __init__(self, device):
            
            charge, state = self.update_battery_state()

            super().__init__(device, charge, state)

        async def async_update_battery_state(self)-> tuple[int,str]:
            """
            Update the battery state. Returns the result.

            Returns
            -------
            tuple[int,str]
                Tuple with [charge percentage, state]
            """
            ##idk if this is blocking, if so, needs to go to a thread
            self.update_battery_state()
        
        def update_battery_state(self):
            state = plyer.battery.get_state()
            charge_perc = state.get("percentage", 0)

            if state["isCharging"]:
                charge_state = "charging"
            else:
                charge_state = "discharging" if charge_perc < 100 else "full"

            t = (charge_perc, charge_state)
            self._update_properties(t)
            return t
    #endregion

    