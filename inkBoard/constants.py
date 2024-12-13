
from typing import TYPE_CHECKING
import tracemalloc
from pathlib import Path

from mdi_pil import MDI_WEATHER_ICONS

# from .arguments import args
# __raise = args.raise_errors

if TYPE_CHECKING:
    from PythonScreenStackManager.elements import Element

# ---------------------------------------------------------------------------- #
#                               General constants                              #
# ---------------------------------------------------------------------------- #

__version__ = "0.1.0" ##0.1.0: Integrations framework implemented
"inkBoard version"

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

##These should be moved to the config folder. They're not constants
# CONFIG_FILE: str = args.config_file.lstrip()

# DEFAULT_CONFIG = str(Path("./testconfig/second_config/second_config.yaml"))
DEFAULT_CONFIG = str(Path("./testconfig/config.yaml"))
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

# MDI_WEATHER_ICONS : dict = {"default": "cloudy",
#         "day": {
#             "clear-night": "night",
#             'cloudy':"cloudy",
#             "exceptional": "cloudy-alert",
#             'fog': "fog",
#             'hail': "hail",
#             'lightning': 'lightning',
#             "lightning-rainy": "lightning-rainy",
#             "partlycloudy": "partly-cloudy",
#             "pouring": "pouring",
#             'rainy': "rainy",
#             "snowy": "snowy",
#             "snowy-rainy": "snowy-rainy",
#             "sunny": "sunny",
#             "windy": "windy",
#             "windy-variant": "windy-variant",

#             ##Icons not in the recommended conditions, but present as mdi icons. See https://pictogrammers.com/library/mdi/category/weather/
#             'hazy': "hazy",
#             "hurricane": "hurricane",
#             'dust': "dust",
#             "partly-lightning": "partly-lightning",
#             "partly-rainy": "partly-rainy",
#             "partly-snowy": "partly-snowy",
#             "partly-snowy-rainy": "partly-snowy-rainy",             
#             "snowy-heavy": "snowy-heavy",
#             "tornado": "tornado"
#             },
#         "night": {
#             'cloudy': "night-partly-cloudy",
#             "partlycloudy": "night-partly-cloudy",
#             "sunny": "night",
#             "clear-night": "night"
#             }}
# "Dict linking forecast conditions to mdi icons"

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

METEOCONS_PATH_OUTLINE = INKBOARD_FOLDER / "files/icons/meteocons/outline"
METEOCONS_PATH = INKBOARD_FOLDER / "files/icons/meteocons/filled"

METEOCONS_WEATHER_ICONS : dict = {"default": "cloudy",
        "day": {
            "clear-night": "clear-night",
            'cloudy':"overcast",
            "exceptional": "rainbow",
            'fog': "fog",
            'hail': "hail",
            'lightning': 'thunderstorms-extreme',
            "lightning-rainy": "thunderstorms-extreme-rain",
            "partlycloudy": "partly-cloudy-day",
            "pouring": "extreme-rain",
            'rainy': "overcast-drizzle",
            "snowy": "overcast-snow",
            "snowy-rainy": "overcast-sleet",
            "sunny": "clear-day",
            "windy": "umbrella-wind",
            "windy-variant": "umbrella-wind-alt",

            "hazy": "haze",
            "hurricane": "hurricane",
            "dust": "dust",
            "partly-lightning": "thunderstorms-day-overcast",
            "partly-rainy": "overcast-day-drizzle",
            "partly-snowy": "overcast-day-snow",
            "partly-snowy-rainy": "overcast-day-sleet",             
            "snowy-heavy": "extreme-snow",
            "tornado": "tornado"
            },
        "night": {
            "clear-night": "falling-stars",
            'cloudy':"overcast-night",
            "exceptional": "rainbow",
            'fog': "fog-night",
            'hail': "partly-cloudy-night-hail",
            'lightning': 'thunderstorms-night-extreme',
            "lightning-rainy": "thunderstorms-night-extreme-rain",
            "partlycloudy": "overcast-night",
            "pouring": "extreme-night-rain",
            'rainy': "overcast-night-drizzle",
            "snowy": "overcast-night-snow",
            "snowy-rainy": "overcast-night-sleet",
            "sunny": "falling-stars",

            "hazy": "overcast-night-haze",
            "dust": "dust-night",
            "partly-lightning": "thunderstorms-night-overcast",
            "partly-rainy": "partly-cloudy-night-drizzle",
            "partly-snowy": "partly-cloudy-night-snow",
            "partly-snowy-rainy": "partly-cloudy-night-sleet",             
            "snowy-heavy": "extreme-night-snow",
            }}
"Dict linking meteocon images to conditions. Suitable for both filled and outlined. Does not yet have the .png extension."

METEOCONS_FORECAST_ICONS : dict = {
                        "datetime" : None,
                        "cloud_coverage": "cloud-up",
                        "humidity": "humidity",
                        "apparent_temperature": "thermometer-sunny",
                        "dew_point": "thermometer-raindrop",
                        "precipitation": "raindrop-measurement",
                        "pressure": "barometer",
                        "temperature": "thermometer",
                        "templow": "thermometer-colder",
                        "wind_gust_speed": "wind-alert",
                        "wind_speed": "wind",
                        "precipitation_probability": "raindrop",
                        "uv_index": "uv-index",
                        "wind_bearing": "windsock"
                            }
"Meteocon icons for forecast entries."

__base_mod = __package__

# _no_reload_mods = [
#     "__main__",
#     "constants",
#     "arguments",
#     "helpers",
#     "integrations",
#     "dashboard",
#     ]

# NO_RELOAD = [
#     # __package__,
#     # f"{__base_mod}.__main__",
#     # f"{__base_mod}.arguments",
#     # f"{__base_mod}"
# ]
"List of modules that do not need to removed from sys.modules upon reloading"

# for mod in _no_reload_mods:
#     NO_RELOAD.append(f"{__base_mod}.{mod}")

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

# FULL_RELOAD_MODULES = ("PythonScreenStackManager.elements", "PythonScreenStackManager.pssm",
#                        *FULL_RELOAD_MODULES, "custom")

##Generally: don't reload pssm, should not change when designing elements or platforms which is what the full reload is mainly meant for.
##Full reload should reload all custom elements, platforms outside basedevice, and reset the screen.
##It's mainly for that, or when making platforms; those may not have a decent ide to work with (like for the kobo)
FULL_RELOAD_MODULES = (*FULL_RELOAD_MODULES, "custom")


