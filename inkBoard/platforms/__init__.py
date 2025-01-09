"""
Platforms for pssm devices.
"""
from pathlib import Path
import logging
import importlib
import importlib.util
from typing import TYPE_CHECKING
import sys

from .. import constants as const

from .basedevice import BaseDevice, Device, FEATURES, InkboardDeviceFeatures
from .validate import validate_device

if const.DESIGNER_INSTALLED:
    import inkBoarddesigner

if TYPE_CHECKING:
    from inkBoard import config as configuration, core as CORE

_LOGGER = logging.getLogger(__name__)

def get_device(config : "configuration", core: "CORE") -> Device:
    "Initialises the correct device based on the config."

    ##Don't forget to include a way to import the designer
    if core.DESIGNER_RUN:
        from inkBoarddesigner.emulator.device import Device, window
        return Device(config)

    platform_package = __package__
    conf_platform = config.device["platform"]
    platform_name = conf_platform
    if const.DESIGNER_INSTALLED:
        platform_path = Path(inkBoarddesigner.__file__).parent / "platforms" / conf_platform
        platform_package = f"{inkBoarddesigner.__package__}.platforms"
        if not platform_path.exists() or not platform_path.is_dir():
            platform_path = Path(__file__).parent / conf_platform
            platform_package = __package__
    elif not "/" in conf_platform:
        platform_path = Path(__file__).parent / conf_platform
    else:
        platform_path = Path(conf_platform)
        if conf_platform.startswith("./"):
            platform_path = config.baseFolder / platform_path
        _LOGGER.info(f"Looking for custom device at {platform_path}")
        platform_name = platform_path.name
    
    platform_package = f"{platform_package}.{platform_name}"
    

    if not platform_path.exists() or not platform_path.is_dir():
        _LOGGER.error(f"Device platform {conf_platform} does not exist.")
        raise ModuleNotFoundError(f"Device platform {conf_platform} does not exist.")
    else:
        ##Test this again once the platform is installed
        dev_spec = importlib.util.spec_from_file_location(platform_package, str(platform_path / "__init__.py"), submodule_search_locations=[])
        device_platform: basedevice = importlib.util.module_from_spec(dev_spec)
        sys.modules[platform_package] = device_platform
        dev_spec.loader.exec_module(device_platform)
        device_platform = importlib.import_module(".device",platform_package)

    device_args = dict(config.device)
    device_args.pop("platform")
    device = device_platform.Device(**device_args) #-> pass the config to this right -> no but the device mappingproxy
    validate_device(device)
    return device