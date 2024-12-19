
from typing import TYPE_CHECKING, Union
import tracemalloc
from pathlib import Path
import importlib.util

from . import __version__

if TYPE_CHECKING:
    from PythonScreenStackManager.elements import Element

# ---------------------------------------------------------------------------- #
#                               General constants                              #
# ---------------------------------------------------------------------------- #

DESIGNER_INSTALLED: bool = False
DESIGNER_FOLDER: Union[None,Path] = None

if s := importlib.util.find_spec("inkBoarddesigner"):
    try:
        DESIGNER_FOLDER = Path(s.origin).parent
        DESIGNER_INSTALLED = True
    except:
        pass


FuncExceptions = (TypeError, KeyError, IndexError, OSError, RuntimeError)
"General exceptions to catch when calling functions like update. Usage  in try statements as `except FuncExceptions:`"

RAISE : bool = False
"If true, some errors which are only logged in situations like interaction handling and trigger functions are now raised. Also enables memory allocation tracing."

if RAISE:
    # os.environ["PYTHONTRACEMALLOC"] = "1"
    tracemalloc.start(5)

COMMAND_VERSION = "version"
COMMAND_DESIGNER = "designer"
COMMAND_RUN = "run"
COMMAND_PACK = "pack"
COMMAND_INSTALL = "install"
ARGUMENT_CONFIG = "configuration"
"Argument to use to indicate a config file"

IMPORTER_THREADPOOL = "inkboard-import-threadpool"

INKBOARD_FOLDER = Path(__file__).parent.resolve()
"Absolute path to the folder containing the inkBoard module"

DEFAULT_CONFIG = "./configuration.yaml"
"The default name to use for the config file"

CONFIG_FILE_TYPES = (
                "yaml",
                "yml"
                    )

INKBOARD_COLORS = {
    "inkboard": (19,54,91), #Prussian Blue
    "inkboard-light": (44,107,176), #Lightened version of Prussian Blue
    "inkboard-dark": (35,31,32), #Dark anthracite color
    "inkboard-gray": (63,59,60), #Dark-ish gray color that just looks nice
    "inkboard-grey": (63,59,60), #Synonym color
    "inkboard-white": (255,255,255) #Simply white but putting it in here for completeness
}

INKBOARD_ICON = INKBOARD_FOLDER / "files/icons/inkboard.ico"

##See https://developers.home-assistant.io/docs/core/entity/weather#forecast-data
##Not included: is_daytime, condition
MDI_FORECAST_ICONS : dict = {
                        "datetime" : None,
                        "cloud_coverage": "mdi:cloud-percent",
                        "humidity": "mdi:water-percent",
                        "apparent_temperature": "mdi:thermometer-lines",
                        "dew_point": "mdi:water-thermometer",
                        "precipitation": "mdi:water",
                        "pressure": "mdi:gauge",
                        "temperature": "mdi:thermometer",
                        "templow": "mdi:thermometer-chevron-down",
                        "wind_gust_speed": "mdi:weather-windy",
                        "wind_speed": "mdi:weather-windy",
                        "precipitation_probability": "mdi:water-percent-alert",
                        "uv_index": "mdi:sun-wireless",
                        "wind_bearing": "mdi:windsock"
                            }
"Dict with default icons to use for forecast data lines"


BASE_RELOAD_MODULES = (
    f"{__package__}.core",
    "custom"
)

FULL_RELOAD_MODULES = [
    "core",
    "configuration",
    "dashboard",
    "platforms",
]

for i, mod in enumerate(FULL_RELOAD_MODULES):
    FULL_RELOAD_MODULES[i] = f"{__package__}.{mod}"
    # NO_RELOAD.append(f"{__base_mod}.{mod}")

##Generally: don't reload pssm, should not change when designing elements or platforms which is what the full reload is mainly meant for.
##Full reload should reload all custom elements, platforms outside basedevice, and reset the screen.
##It's mainly for that, or when making platforms; those may not have a decent ide to work with (like for the kobo)
FULL_RELOAD_MODULES = (*FULL_RELOAD_MODULES, "custom")


