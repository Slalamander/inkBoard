##HomeAssistantClient file
"""
This library manages elements from PSSM and linked entities from Home Assistant, and provides additional comound elements in the HAelements library.
Import it first, or at least before importing the element library to allow it to add to the PSSM default colors and fonts.
"""
from __future__ import annotations
from typing import Literal, TypedDict, TypeVar, Optional, Union
from pathlib import Path
import asyncio
from io import BytesIO
import logging

import requests
from PIL import Image

logger = logging.getLogger(__name__)

##Use this file to declare some more constants and extend a couple
class DomainError(ValueError):
    "The supplied entity is not of a valid domain."
    pass

##Mind the docstring when dealing with errors here (i.e. use from fromisoformat)

HAtimestrFormat = Literal["%Y-%m-%-dT%H:%M:%S.%Y+%H:%M"] #Literal[DEFAULT_HA_DT_FORMAT]
"Default Home Assistant datetime string typing"

EntityType = TypeVar("entity_id", bound=str)

stateDictType = TypedDict('stateDict', {"entity_id":str, "state": str, "attributes": dict, "last_changed": HAtimestrFormat,"last_reported": HAtimestrFormat, "last_updated": HAtimestrFormat, "context": dict})
"Typed dict for an entities state as passed from a trigger"

triggerDictType = TypedDict('triggerDictType',{"entity_id":str,"to_state": stateDictType, "from_state": Optional[stateDictType], "context":Optional[dict]})
"Typed dict for how triggers are passed"


actionCallDict = TypedDict('actionCallDict', {"id": int, "type": str, "domain": str, "service":str, "service_data": dict, "target": dict, "return_response": bool}, total=True)
"Typed dict for the message format of a HA action call via the websocket"

actionCallDict.__optional_keys__ = frozenset({"service_data", "target"})
actionCallDict.__required_keys__ = actionCallDict.__required_keys__.difference(actionCallDict.__optional_keys__)

serviceCallDict = actionCallDict

WeatherData = Literal["datetime", "cloud_coverage", "condition", "humidity", "temperature", "apparent_temperature", "dew_point", "pressure", "visibility", "wind_gust_speed", "wind_speed", "ozone", "uv_index", "wind_bearing"]
"Type hint with (most likely) all possible weather data in a weather entity's attributes."

async def request_image_threadsafe(image_url : str) -> tuple[Union[Image.Image, requests.Response],int]: #Union[tuple[Image.Image,Literal["status_code"]],tuple[requests.Response, Literal["status_code"]]]:    
    """
    Gets an image from a request.get response in a non-blocking manner.
    Method from: https://superfastpython.com/python-async-requests/

    Parameters
    ----------
    image_url : str
        url to get the image from

    Returns
    -------
    tuple[Image.Image | requests.response, status_code] | 
        If the status code is 200 (i.e. the request was succesfull) a tuple is returned with the gotten Image and the status code. 
        Otherwise a tuple with the full response and the status code is returned.
    """

    response = await asyncio.to_thread(requests.get, image_url)

    if response.status_code == 200:

        ##Is this one threadsafe? Since it's not technically reading a file I'm not sure 
        ##Replaced it with a to_thread call to be sure
        # img = Image.open(BytesIO(response.content))
        respIO = BytesIO(response.content)
        img = await asyncio.to_thread(Image.open,respIO)
        return (img.copy(), response.status_code)
    else:
        logger.warning(f"Unable to get requested image")
        return (response, response.status_code)