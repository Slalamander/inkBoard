"""
Platforms for pssm devices.
"""
from pathlib import Path
import logging
import importlib
from typing import TYPE_CHECKING

from ..arguments import args, DESIGNER_MOD

from .basedevice import BaseDevice, Device, FEATURES
from .validate import validate_device

if DESIGNER_MOD:
    import inkBoard_designer

if TYPE_CHECKING:
    from inkBoard import config as configuration

logger = logging.getLogger(__name__)

def get_device(config : "configuration") -> Device:
    "Initialises the correct device based on the config."

    ##Don't forget to include a way to import the designer
    if args.command == "designer":
        from inkBoard_designer.emulator.device import Device, window
        return Device(config)

    conf_platform = config.device["platform"]
    if DESIGNER_MOD:
        platform_path = Path(inkBoard_designer.__file__).parent / "platforms" / conf_platform
        platform_package = f"{inkBoard_designer.__package__}.platforms"
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