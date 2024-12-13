
from typing import TYPE_CHECKING
import tracemalloc
from pathlib import Path

from mdi_pil import MDI_WEATHER_ICONS

from . import __version__

if TYPE_CHECKING:
    from PythonScreenStackManager.elements import Element

# ---------------------------------------------------------------------------- #
#                               General constants                              #
# ---------------------------------------------------------------------------- #



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


