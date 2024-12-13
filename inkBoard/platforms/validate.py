"Functions to validate a device at runtime"

import logging
from . import basedevice
from .basedevice import Device, FEATURES, InkboardDeviceFeatures

_LOGGER = logging.getLogger(__name__)

##Validate function: use assertions, or at least raise assertion errors when validation fails

def validate_power(device: basedevice.Device):
    assert device.power_off.__module__ == device.reboot.__module__ != __package__, "Device needs to define their own power off and reboot functions for the power feature"

def validate_backlight(device: Device):
    assert isinstance(device.backlight, basedevice.BaseBacklight), "device's backlight should be based on inkBoard's BaseBacklight"

def validate_battery(device: Device):
    assert isinstance(device.battery, basedevice.BaseBattery), "device's backlight should be based on inkBoard's BaseBattery"

def validate_network(device: Device):
    assert isinstance(device.network,basedevice.BaseNetwork), "device's network should be based on inkBoard's BaseNetwork"
    if device.has_feature(FEATURES.FEATURE_CONNECTION):
        assert isinstance(device.network,basedevice.BaseConnectionNetwork), "device's network should be based on inkBoard's BaseConnectionNetwork to use the connection feature"

def validate_rotation(device: Device):
    ##how to?
    return

##More proof feature strings need to be based on constants.
##Just, how to get them from the feature class or vice versa
feature_validators = {
    FEATURES.FEATURE_POWER: validate_power,
    FEATURES.FEATURE_POWER: validate_battery,
    FEATURES.FEATURE_NETWORK: validate_network,
    FEATURES.FEATURE_BACKLIGHT: validate_backlight
}

def validate_device(device: basedevice.Device):
    assert isinstance(device, basedevice.BaseDevice), f"{device} should be based on inkBoard's BaseDevice"

    assert isinstance(device._features, InkboardDeviceFeatures), f"Device features should be an instance of InkBoardDeviceFeatures"

    err = False

    for feature, validator in feature_validators.items():
        if not device.has_feature(feature):
            continue

        try:
            validator(device)
        except AssertionError as exce:
            _LOGGER.error(exce.args[0], exc_info=None)
            err = True

    assert not err, "Device failed validation. See logs for more info"
