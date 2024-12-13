"Constants for HA client designer"

from typing import Literal
from mdi_pil import mdiType

__entity_icons : dict[Literal["domain"],mdiType] = {
    "default": "mdi:puzzle",
    
    ##All entities found in https://developers.home-assistant.io/docs/core/entity
    "alarm_control_panel": "mdi:shield-lock",
    "binary_sensor": "mdi:radiobox-indeterminate-variant",
    "button": "mdi:button-pointer",
    "calendar": "mdi:calendar-blank",
    "camera": "mdi:camera",
    "climate": "mdi:radiator-disabled",
    "conversation": "mdi:chat",
    "cover": "mdi:blinds",
    "date": "mdi:calendar",
    "datetime": "mdi:calendar-clock",
    "device_tracker": "mdi:map-marker-account",
    "event": "mdi:star-four-points-circle",
    "fan": "mdi:fan",
    "humidifier": "mdi:air-humidifier",
    "image": "mdi:image",
    "lawn_mower": "mdi:robot-mower",
    "light": "mdi:lightbulb",
    "lock": "mdi:lock",
    "media_player": "mdi:multimedia",
    "notify": "mdi:message",
    "number": "mdi:numeric",
    "remote": "mdi:remote",
    "scene": "mdi:palette",
    "select": "mdi:form-select",
    "sensor": "mdi:speedometer",
    "siren": "mdi:alarm-light",
    "stt": "mdi:account-voice",
    "switch": "mdi:toggle-switch",
    "text": "mdi:form-textbox",
    "time": "mdi:clock",
    "todo": "mdi:format-list-checks",
    "tts": "mdi:microphone-message",
    "update": "mdi:update",
    "vacuum": "mdi:robot-vacuum",
    "valve": "mdi:valve",
    "wake_word": "mdi:microphone-question",
    "water_heater": "mdi:kettle",
    "weather": "mdi:cloud",
    "zone": "mdi:map-marker",

    ##Some domains provided by core that are not in the developer list (may be inconclusive)
    "automation": "mdi:robot",
    "person": "mdi:account",
    "sun": "mdi:weather-sunny",
    "plant": "mdi:flower",
    "script": "mdi:script",

    ##Unique Helper domains
    "counter": "mdi:counter",
    "timer": "mdi:timer",
    "schedule": "mdi:calendar-star"

}

__helper_map = {"input_button": "button", "input_boolean": "switch", "input_number": "number",
                "input_select": "select", "input_text": "text", "input_datetime": "datetime"}

for helper, dom in __helper_map.items():
    __entity_icons[helper] = __entity_icons[dom]

ENTITY_ICONS = __entity_icons
"Icons for entity domains in the treeview"