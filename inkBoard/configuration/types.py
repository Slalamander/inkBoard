"Holds the typehints for the inkBoard config, mainly typedicts and dataclasses"

from types import MappingProxyType
from typing import *
from pathlib import Path
import dataclasses
from dataclasses import dataclass
import inspect

import inkBoard
from inkBoard.helpers import add_required_keys
from inkBoard.logging import LOG_LEVELS


from .const import INKBOARD_FOLDER
from PythonScreenStackManager.pssm import PSSMScreen
from PythonScreenStackManager import pssm_types as pssm, constants as pssm_const

if TYPE_CHECKING:
    from PythonScreenStackManager.elements import constants as elt
    from mdi_pil import mdiType

##These need to stay as typeddicts since some, like device, need additional options to be set

_LOGGER = inkBoard.getLogger(__name__)

LogLevels = Union[int, Literal[LOG_LEVELS]]


class _BaseConfigEntry:

    def __getitem__(self, item):
        if isinstance(item,str) and hasattr(self,item): #@IgnoreExceptions
            return getattr(self,item) #@IgnoreExceptions
        else:
            raise KeyError(f"{self.__class__} has no entry {item}") #@IgnoreExceptions

@dataclass(frozen=True)
class InkboardEntry(_BaseConfigEntry):
    """Sets some basic inkBoard functionality. Required, setup using the ``inkBoard`` config entry.

    Map for inkBoard specific settings. 
    """
    
    name : str
    "The name to give the instance. Used for i.e. the name of the Device in Home Assistant"

    main_element : str = None
    """The id of the element to use as a the main element.
    
    If not set, the ``main_tabs`` will be used, which is the default.
    """

    date_format : str = "%-d-%m-%Y"
    """Default format to use when representing dates.
    
    Default may be device/region specific.
    This site can help giving your the correct format string from a date: https://www.dateformatgenerator.com/?lang=Python&q=17-09-2013 
    """

    time_format : str = "%H:%M"
    """Default format to use when representing time.
    
    Default may be device/region specific.
    This site can help giving your the correct format string from a time: https://www.dateformatgenerator.com/?lang=Python&q=11%3A11
    """

    integrations : Union[Literal["all"],tuple] = ()
    "List with integrations to load, if they do not have a config key defined (i.e. for custom elements)"

    integration_start_time : 'pssm.DurationType' = 30
    "Maximum time to allow integrations to run their start tasks before inkBoard continues to printing. Gets parsed to seconds, set to -1 for to wait until everything is set up. Keep in mind that setting this may cause issues with integrations. Default is 30."

class StylesEntry(TypedDict):
    """
    Dataclass for styling options, used to set custom colours, define default fonts and certain icon styles.
    TypedDict, so can hold any entries, to allow integrations to also define styles.
    Since the new Style model is not implemented yet, this entry does nothing at the moment.
    """

    menu_header_color: 'pssm.ColorType'
    "Default color for the header bar of menu popups. Defaults to steelblue"

    menu_button_color: 'pssm.ColorType'
    "Default color for menu buttons. Defaults to gray."

    foreground_color: 'pssm.ColorType'
    "Default color for foreground parts of elements, like text colors or icon colors."

    background_color: 'pssm.ColorType'
    "Default color for element backgrounds, when applicable. Also used for calculating automatic contrasting colors when applicable."

    font: str
    "Default font to use for displaying text."

    font_bold: str
    "Default font to use for bold text"

    font_clock: str
    "Default font to use for digital clocks"

    font_size: 'pssm.PSSMdimension'
    "Default size to use for fonts"

    default_icon: 'mdiType'
    "Default icon to use for icon elements"

    missing_icon: 'mdiType'
    "Icon to use when a specified icon or image file cannot be found."

    battery_style: 'elt.batteryIconMapping'
    """
    Default styling for battery icons. Options for the 3 states + default values. Options should hopefully be somewhere in the docs, otherwise see elements.constants.py
    """

    network_style : Literal["lines","signal"]
    "Default style to use for network icons."

    shorthand_colors : dict[str,tuple[int,int,int,int]]
    """
    Allows you to define additional color shorthands.
    Define them as a set of RGBA values, so 4 integers ranging from 0-255
    """

    blur_popup_background: bool
    "Default setting for blurring the background behind popups. Defaults to True"

@dataclass(frozen=True)
class FolderEntry(_BaseConfigEntry):
    """DEPRECATED, will not be allowed to be set 
    Dataclass with the folders inkBoard will look in for custom files. 
    NOT defined in the config, as all folders should have constant names. However, this is used to set the correct Paths when running configs from different folders.
    Eventually it will be made possible however to define these in a way to use custom folders from elsewhere, such that when developing a new dashboard, old files do not need to be changed immediately. However, this option will only be available for the emulator most likely.
    """
    #No need for custom folders, inkBoard automatically makes the same folders in the config folder.

    base_folder : Path
    "Base path leading to the folder containing the config file."

    icon_folder: Path
    "Path pointing to the folder containing user icons"

    picture_folder: Path
    "Path pointing to the folder containing user pictures"

    font_folder: Path
    "Path pointing to the folder user fonts"
    
    custom_folder: Path
    "Path pointing to the folder where users can define custom elements and functions, to be used with the yaml parser."

    screenshot_folder: Path
    "Path pointing to where inkBoard will save screenshots"

    file_folder: Path
    "Path point to the files folder. This folder can be used to hold any files needed that are not yaml configurations. This entire directory will be copied during packing."

@dataclass(frozen=True)
class DesignerEntry(_BaseConfigEntry):
    """Additional settings for the designer. Setup under the ``designer`` entry.

    Dict with settings for the designer, when developing new dashboards. 
    Can also parse certain settings from the device key, like platform, if the key is present.
    """

    height: int = None
    "Optional height to give the screen. Overwrites device settings."

    width: int = None
    "Optional width to give the screen. Overwrites device settings."

    icons: MappingProxyType = MappingProxyType({})
    "Optionally allows one to redefine the icons used for pssm elements in the element tree view,  or set icons for their custom elements."

    platform_validation: bool = True
    "Validates whether the device configuration is valid for the base platform."


class DeviceEntry(TypedDict):
    """Entry to setup the device, under the ``device`` config entry.

    Dict to configure the device. Mainly important to import the correct device.
    If the emulator key is defined, inkBoard will automatically try and run as emulator using the device settings.
    This config entry accepts any optional arguments to allow for various platforms to be set up via this config.
    """
    
    platform : str
    "The platform (device type) the dashboard will run on, or that will be emulated. A list will be somewhere in the docs."

    model : str
    "Model of the device. May be required for some platforms, others don't need it or can set it automatically."

add_required_keys(DeviceEntry, {"platform"})
deviceMapDefaults = MappingProxyType({"model": None})

# @dataclass(frozen=True)
# class ScreenEntry(_BaseConfigEntry):
#     """
#     Map for values having to do with the screen, like interaction or how it is shown.
#     """
    
#     poll_interval: Union['pssm.DurationType',int, float] = "1min"
#     "The amount of time in between polling different attributes, like the Network status."

#     close_popup_time: Union[float,'pssm.DurationType', int] = "1min"
#     "Default time in which popups will automatically close"

#     background: Union[str, 'pssm.ColorType', None] = INKBOARD_FOLDER / "files" / "images" / "default_background.png"
#     "Main background of the screen. Can be a color, or an image. If None, the default device background is assumed."

#     background_fit: Literal["contain", "cover", "crop", "resize"] = "cover"
#     "Method to use to fit the background onto the screen"

#     background_fit_arguments: MappingProxyType = MappingProxyType({})
#     "Any keyword arguments to pass to the background fit method. Refer to the PIL docs for the arguments for each method"

#     backlight_behaviour: Optional[Literal["Manual", "On Interact", "Always"]] = None
#     "Behaviour of the device's backlight (if applicable)"

#     backlight_time_on: Union['pssm.DurationType',int, float] = "1min"
#     "If backlight_behaviour is 'On Interact', this value determines how long the backlight stays on for after the last interaction, by default None"

#     touch_debounce_time: 'pssm.DurationType' = '1ms'
#     "Time to wait before a touch is considered valid"

#     minimum_hold_time: 'pssm.DurationType' = '0.5s'
#     "Minimum time required to consider a touch as held, instead of tapped"

#     on_interact: Union[Callable[[MappingProxyType, 'pssm.PSSMScreen', 'pssm.CoordType'], None], bool,None] = None
#     "Function called whenever a valid touch is registered"

#     on_interact_data: MappingProxyType = MappingProxyType({})
#     "Any keyword arguments to send along with calls to the on_interact functions"

@dataclass(frozen=True)
class ScreenEntry(_BaseConfigEntry):
    """The entry that sets up the screen. Setup under the ``screen`` entry.
    
    The screen manages the dashboard and handles the connection between it and the device.
    """

    background : Union[str, pssm.ColorType] = "inkboard-background"
    "The background of the dashboard. Can be an image file or a solid color."

    background_fit : Literal["contain", "cover", "crop", "resize"] = "cover"
    """The method used to fit the background image on the screen.
    
     - Contain: makes the entire image fit on the screen, without changing the width/height ratio. Any leftover screen area is either filled up with the default screen color, or a color specified under 'color' in `fit_arguments`. \n
     - Cover: size the image to the smallest size to cover the entire screen without changing the width/height ratio, and crop out anything that is too large. Cropping is generally centered, but can be set using 'centering' in `fit_arguments`\n
     - Crop: Crops out a part of the image and resizes it to fit the screen area, without mainting the width/height ratio. Cropped out area defaults to the center area of the image that fits the screen. Otherwise, can be set using 'box' in `fit_arguments` (see documentation of `tools.fit_Image` for usage)\n
     - Resize: resizes the entire image to fit the screen area, without maintaining width/height ratio.
    """

    background_fit_arguments : dict = MappingProxyType({})
    """Additional arguments to use when fitting the background.

    See the Pillow documentation for what arguments what method accepts.
    """

    close_popup_time : pssm.DurationType = "1min"
    """Default time after which popups will close automatically.
    """

    poll_interval : pssm.DurationType = "1min"
    """Time between polling the device and its features states.
    """

    on_interact: Union[Callable[[dict, 'PSSMScreen', pssm.CoordType], None], bool,None] = None
    """Function to call for *every* interaction with the screen. 
    Does not accept a dict like element actions yet, so shorthands have to be used directly.
    """

    on_interact_data : dict = MappingProxyType({})
    """Any data to pass along to the on_interact function.
    """

    touch_debounce_time: pssm.DurationType = pssm_const.DEFAULT_DEBOUNCE_TIME
    "The minimum time needed for a touch to register as valid. Workings may be dependent on the device's features."

    minimum_hold_time : pssm.DurationType = pssm_const.DEFAULT_HOLD_TIME
    """The minimum time to hold a touch before it is considered as being held.
    """

    backlight_behaviour : Optional[Literal["Manual", "On Interact", "Always"]] = "Manual"
    """Determines how the backlight behaves when interacting with the screen. Requires a device with the backlight feature.

    ``Manual`` and ``Always`` function almost the same, the difference being that the latter turns on the backlight when this setting is applied. Applying manual does not change the state.
    Using one of these values means the backlight has to be toggled manually, via i.e. elements.

    ``On Interact`` means the screen will turn on the backlight when interacting with the screen (provided it is off). 
    It will then keep the backlight on until ``backlight_time_on`` time has elapsed without any interaction.
    """

    backlight_time_on : Union[float, pssm.DurationType] = None
    """Time to keep the backlight on after the last interaction. Requires a device with the backlight feature.

    Requires ``backlight_behaviour`` to be ``On Interact``, otherwise does nothing.
    If ``None``, the value will be left to the device and/or remain unchanged.
    """    


##Add a unittest or something that checks if this corresponds to the __init__
init_args = inspect.signature(PSSMScreen.__init__)
param_names = [param for param in init_args.parameters]

fields = dataclasses.fields(ScreenEntry)
field_names = [field.name for field in fields]

for param in init_args.parameters.values():
    if param.name in {"self", "device"}:
        continue
    if param.name not in field_names:
        _LOGGER.warning(f"ScreenEntry is missing parameter {param.name}")
        continue
    else:
        for field in fields:
            if field.name == param.name:
                break
    if param.annotation != field.type:
        
        _LOGGER.warning(f"ScreenEntry field {field.name} does not match the annotation of the parameter")
    
    if param.default == param.empty:
        if field.default != dataclasses._MISSING_TYPE:
            _LOGGER.warning(f"ScreenEntry {field.name} is not required but it should be")
    # elif param.default != field.default:
    #     _LOGGER.warning(f"ScreenEntry {field.name} has the wrong default value. Should be {param.default}")

for field in field_names:
    if field not in param_names:
        _LOGGER.warning(f"Illegal field in ScreenEntry: {field}")


@dataclass(frozen=True)
class HomeAssistantEntry(TypedDict):
    "Dict with settings required for the home assistant client"

    url : str
    "Url to the home assistant server."

    token: str
    "Long lived access token to authenticate with the server."

    state_colors: MappingProxyType = MappingProxyType({})
    """
    This way you can map the default foreground colors of connected elements to take on the same color when their state matches.
    Also accepts a default entry for unknown states.
    Will be used for elements where state_colors: True is set.
    """

    ping_pong_interval : 'pssm.DurationType' = 30
    "Interval inbetween checking the connection to the server. Generally you can keep this undefined."

    unknown_icon : Optional['mdiType'] = "mdi:help"
    "Default icon to indicate that an entity's state is unknown"

    unavailable_icon : Optional['mdiType'] = "mdi:exclamation-thick"
    "Default icon to indicate that an entity is unavailable"



    ##Also add settings for setting up a socket logger

##Reasons for dict: entries can be omitted
##Namedtuple/dataclass: allows for defaults but requires all entries

@dataclass(frozen=True)
class LoggerEntry(_BaseConfigEntry):
    """This entry sets up the logging facilities of inkBoard, under the ``logger`` entry.
    """    

    level: LogLevels = "INFO"
    "The base level for logging"

    logs: MappingProxyType[str, LogLevels] = MappingProxyType({})
    "Allows setting log levels for individual loggers"

    basic_config: Union[MappingProxyType[str,Any],Literal[False],None] = False
    """Forcibly overwrite the basic logging config (i.e. the way logs are displayed). 
    This is done before parsing the other logging options, so keep in mind you may overwrite settings. 
    """

    log_to_file: Union[MappingProxyType[str,Any],Literal[False],None] = False
    "Settings for logging to a file. This setting is ignored when running in the designer."


class MainEntry(TypedDict):
    "Typehint for the full configuration dict as read out. Not exhaustive"

    inkboard: InkboardEntry
    "Keys for configuring and styling inkBoard"

    device: DeviceEntry
    "Defining what device and platform inkBoard is running on, as well as possible configuring of hardware."

    screen: ScreenEntry
    "Settings that affect how the screen behaves or is interacted with"

    folders: FolderEntry
    "Optionally set paths other than the defaults for folders where custom icons etc. are located"

    styles : StylesEntry
    "Options for styling elements and other things in inkBoard."

    designer : DesignerEntry
    "Settings for the emulator, when designing new dashboards."

    home_assistant : HomeAssistantEntry
    "Settings for the Home Assistant client"

    logger : LoggerEntry
    "Settings to apply for making logs"

__all__ = [
    "InkboardEntry",
    "StylesEntry",
    "FolderEntry",
    "DesignerEntry",
    "DeviceEntry",
    "ScreenEntry",
    "HomeAssistantEntry",
    "LoggerEntry",
    "MainEntry"
]

# rotation : 'pssm.RotationValues' = "UR"
# """
# Screen rotation. Corresponds as follows: \n
# values:\n
#     UR: 'upright' [0°] \n
#     CW: 'clockwise' [90°] \n
#     UD: 'upsidedown' [180°] \n
#     CCW: 'counterclockwise' [270°] \n
# """
##Leaving this in here since it may be useful? But not all devices support it so it should be a device setting.