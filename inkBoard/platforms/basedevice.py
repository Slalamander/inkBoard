"""
A basedevice needed to run inkBoard. Mainly an extension from the pssm basedevice.
"""

from abc import abstractmethod
from typing import Optional
import asyncio

from functools import cached_property
from collections import namedtuple

import inkBoard
from PythonScreenStackManager.pssm_types import *
from PythonScreenStackManager import tools
from PythonScreenStackManager.devices import PSSMdevice, DeviceFeatures, \
                                    Battery as BaseBattery, Backlight as BaseBacklight, Network as BaseNetwork
from PythonScreenStackManager.devices.const import FEATURES, _attr_list, DeviceFeatures

from ..helpers import function_parameter_dict

_LOGGER = inkBoard.getLogger(__name__)

class FEATURES(FEATURES):

    FEATURE_CONNECTION = "FEATURE_CONNECTION"
    "Subfeature of network, indicates the device is able to manage the network connection (i.e. disconnect, connect, etc.)"

_attr_list = _attr_list.copy()   ##Copying so the original is not altered
_attr_list.extend([y for x, y in FEATURES.__dict__.items() if not x.startswith("_")])
_DeviceTuple = namedtuple("_DeviceTuple", _attr_list, defaults=(False,)* len(_attr_list))


class InkboardDeviceFeatures(_DeviceTuple, DeviceFeatures, FEATURES):
    """Class for indicating which features the device has. 
    
    Pass all the features using the constants from the `FEATURES` class.
    Do not interface with this class directly, but use `device.has_feature(FEATURES.FEATURE_{})` instead.
    """

    def __new__(cls, *features: str, **kwargs):
        for a in features:
            kwargs[a] = True
        return _DeviceTuple.__new__(cls, **kwargs)

featurehint = Literal[tuple(_attr_list)]

class BaseDevice(PSSMdevice):
    "Base device class for inkBoard"

    ##Need some properties in here, as well as abstractmethods
    ##At least: platform and model
    ##And rewrite the name property?
    
    def __init__(self, features: DeviceFeatures, screenWidth: int, screenHeight: int, viewWidth: int, viewHeight: int, screenMode: str, imgMode: str, defaultColor: ColorType, model: str = None, name: str = None, **kwargs):
        
        self._model = None
        super().__init__(features, screenWidth, screenHeight, viewWidth, viewHeight, screenMode, imgMode, defaultColor, name, **kwargs)

    #region
    @classproperty
    def platform(cls) -> str:
        "The device platform"
        mod = cls.__module__.split('.')
        if mod[-1] == "device":
            return mod[-2]
        return mod[-1]

    
    @cached_property
    def model(self) -> Optional[str]:
        "The model of the device"
        return self._model
    #endregion

    def has_feature(self, feature: Union[str,featurehint]):
        return super().has_feature(feature)

    async def async_pol_features(self):
        """Pols the necessary features of the device to see if their state has changed.

        The screen calls this automatically at preset intervals.
        """

        if self.has_feature(FEATURES.FEATURE_NETWORK):
            await self.network.async_update_network_properties()

        if self.has_feature(FEATURES.FEATURE_BATTERY):
            await self.battery.async_update_battery_state()

        return

    def _set_screen(self, ScreenInstance):

        super()._set_screen(ScreenInstance)

        if self.has_feature(FEATURES.FEATURE_POWER):
            self.Screen.add_shorthand_function("power-off", tools.wrap_to_tap_action(self.power_off))
            self.Screen.add_shorthand_function("reboot", tools.wrap_to_tap_action(self.reboot))


class BaseConnectionNetwork(BaseNetwork):
    "Abstract base class to manage a device's network connection."

    @abstractmethod
    async def async_connect(self, ssid: str = None, password: str = None):
        """Base async method to connect to a network."""
        return

    def connect(self, ssid: str = None, password: str = None):
        "Connects to a wifi network"
        asyncio.create_task(self.async_connect(ssid,password))

    @abstractmethod
    async def async_disconnect(self):
        """Base async method to disconnect from the network."""

    def disconnect(self):
        "Disconnects to a wifi network"
        asyncio.create_task(self.async_disconnect())


class Device(BaseDevice):
    """An inkBoard device

    This class is meant as a most basic implementation. Reference the documentation for platforms for the full API of its device.    
    """

    @property
    def network(self) -> Union[BaseNetwork,BaseConnectionNetwork]: return

    @property
    def backlight(self) -> BaseBacklight: return

    @property
    def battery(self) -> BaseBattery: return

def create_emulatorjson_init(device: type[Device]):
    """Updates the platform's emulator.json file with the parameters from the device's __init__ function.

    This is meant as a dev function, and imports a couple of modules too. Generally don't use it aside from when developing platforms.

    Parameters
    ----------
    device : type[Device]
        The _class_ to process. The platform is automatically gathered from this.
    """    

    ##Since this is meant as a developer function that is not ran often, these imports are done in function
    import json
    import inspect
    from pathlib import Path

    if isinstance(device,BaseDevice):
        device = device.__class__

    assert issubclass(device, BaseDevice), "device must a class which is a subclass of the BaseDevice"

    _LOGGER.info(f"Gathering init parameters for device platform {device.platform}")

    parameter_dict = function_parameter_dict(device.__init__, True, True)


    device_folder = Path(inspect.getfile(device)).parent
    platform_file = device_folder / "emulator.json"

    if platform_file.exists():
        _LOGGER.info("Opening emulator.json")
        with open(platform_file) as f:
            cur_conf = json.load(f)
    else:
        cur_conf = {}

    _LOGGER.info("Writing to emulator.json")
    with open(platform_file, "w") as f:
        cur_conf.update({"__init__": parameter_dict})
        json.dump(cur_conf, f, indent=4)

    _LOGGER.info("Succesfully updated emulator.json")
    return

def create_emulatorjson_features(device: Device):
    """Uses an _instance_ of a device to add/update features to the emulator.json file

    Parameters
    ----------
    device : Device
        _description_
    """    

    import json
    import inspect
    from pathlib import Path

    assert isinstance(device._features, InkboardDeviceFeatures), "Use the InkboardDeviceFeatures class for the features attribute"

    _LOGGER.info("Updating device features in emulator.json")

    device_folder = Path(inspect.getfile(device)).parent
    platform_file = device_folder / "emulator.json"

    if platform_file.exists():
        _LOGGER.info("Opening emulator.json")
        with open(platform_file) as f:
            cur_conf = json.load(f)
    else:
        cur_conf = {}

    _LOGGER.info("Writing to emulator.json")
    with open(platform_file, "w") as f:
        cur_conf.update({"features", device._features._asdict()})
        json.dump(cur_conf, f, indent=4)

    return