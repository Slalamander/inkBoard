"""
Platforms for pssm devices.
"""
from pathlib import Path
import logging
import importlib
from typing import TYPE_CHECKING

from .. import constants as const

from .basedevice import BaseDevice, Device, FEATURES
from .validate import validate_device

if const.DESIGNER_INSTALLED:
    import inkBoarddesigner

if TYPE_CHECKING:
    from inkBoard import config as configuration, core as CORE

logger = logging.getLogger(__name__)

def get_device(config : "configuration", core: "CORE") -> Device:
    "Initialises the correct device based on the config."

    ##Don't forget to include a way to import the designer
    if core.DESIGNER_RUN:
        from inkBoarddesigner.emulator.device import Device, window
        return Device(config)

    conf_platform = config.device["platform"]
    if const.DESIGNER_INSTALLED:
        platform_path = Path(inkBoarddesigner.__file__).parent / "platforms" / conf_platform
        platform_package = f"{inkBoarddesigner.__package__}.platforms"
        if not platform_path.exists() or not platform_path.is_dir():
            platform_path = Path(__file__).parent / conf_platform
            platform_package = __package__
    else:
        platform_path = Path(__file__).parent / conf_platform
        platform_package = __package__

    if not platform_path.exists() or not platform_path.is_dir():
        logger.error(f"Device platform {conf_platform} does not exist.")
        raise ModuleNotFoundError(f"Device platform {conf_platform} does not exist.")
    else:
        device_platform: basedevice  = importlib.import_module(f".{conf_platform}.device",platform_package)

    device_args = dict(config.device)
    device_args.pop("platform")
    device = device_platform.Device(**device_args) #-> pass the config to this right -> no but the device mappingproxy
    validate_device(device)
    return device