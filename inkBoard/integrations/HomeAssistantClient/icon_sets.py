"""
Holds data for default icon packs for various elements.
"""

from pathlib import Path

from PythonScreenStackManager.constants import MDI_WEATHER_DATA_ICONS, PATH_TO_PSSM
from mdi_pil import MDI_WEATHER_ICONS as MDI_WEATHER_CONDITION_ICONS

METEOCONS_PATH_OUTLINE = PATH_TO_PSSM / "icons/meteocons/outline"
METEOCONS_PATH = PATH_TO_PSSM / "icons/meteocons/filled"

METEOCONS_WEATHER_CONDITIONS_ICONS : dict = {"default": "cloudy",
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
"""
Dict linking meteocon images to conditions. Suitable for both filled and outlined. Does not yet have the .png extension.
Usage: call `pssm.tools.parse_weather_icon(conditionDict=METEOCONS_WEATHER_CONDITIONS_ICONS, prefix=METEOCONS_PATH, suffix=".png")`. `METEOCONS_PATH` can be substituted for `METEOCONS_PATH_OUTLINE` to use the outline pack. The full path to the correct image is returned.
"""

METEOCONS_WEATHER_DATA_ICONS : dict = {
                        "datetime" : None,
                        "cloud_coverage": "cloud-up",
                        "humidity": "humidity",
                        "apparent_temperature": "thermometer-sunny",
                        "dew_point": "thermometer-raindrop",
                        "precipitation": "raindrop-measure",
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

HVAC_MODES_ICONS : dict = {
    "off" : "mdi:power",
    "heat": "mdi:fire",
    "cool": "mdi:snowflake" ,
    "heat_cool": "mdi:sun-snowflake-variant" ,
    "dry": "mdi:heat-wave" ,
    "fan_only": "mdi:fan" ,
    "auto": "mdi:thermostat-auto"
}
"Default icons for the possible HVAC modes"