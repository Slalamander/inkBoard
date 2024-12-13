"""
Provides base update functions (functions called when the entity associated with an element is updated) for some of the pssm elements.
"""
from typing import Callable, Union, TYPE_CHECKING, TypedDict, Optional, Any
import logging
import asyncio
from inspect import getcoroutinestate, getcoroutinelocals
from ast import literal_eval

from PIL import Image

from PythonScreenStackManager import elements as elts, tools
import mdi_pil as mdi
from inkBoard import core as CORE

from .constants import DEFAULT_DOMAIN_ACTIONS, UNKNOWN_ICON, UNAVAILABLE_ICON, UNAVAILABLE_COLOR, UNKNOWN_COLOR, all_entities
from .helpers import triggerDictType, request_image_threadsafe

if TYPE_CHECKING:    
    from .HAelements import HAelement
    from .client import HAclient
    from PIL import Image
    import requests
    from PythonScreenStackManager import elements as elts
    from PythonScreenStackManager import tools

logger = logging.getLogger(__name__)

attribute_styles_stateType = TypedDict('attribute_style_states', {"state": Any, 'properties': dict})
attribute_stylesType = TypedDict('attribute_stylesDict', {'attribute': str, 'states': attribute_styles_stateType, 'else': dict})

state_color_dict = CORE.config.styles.get("state_colors",{})

def get_condition_key(state : str,conditions : list[str]):
    """
    Tests if any of the conditional strings in conditions return true. 
    Conditions can be defined as e.g. 'state < 5', the first one to evaluate as true is returned, otherwise None.
    state is the element state, i.e. if an attribute is set, it will set state to that attribute.
    """
    if isinstance(state,str):
        str_state = state
        try:
            ##First check if state can be converted into a different type
            state = literal_eval(str_state) #@IgnoreException
        except (SyntaxError, ValueError):
            ##state cannot be evaluated as something else than a string
            pass
    for cond in conditions:
        if "state" not in cond: continue
        try:
            if eval(cond): return cond #@IgnoreException
        except (SyntaxError, NameError, TypeError, ZeroDivisionError):
            continue
    
    # if not isinstance(state,str):
    #     state = str(state)
    #     for cond in conditions:
    #         try:
    #             if state == cond: return cond
    #         except TypeError:
    #             continue
    ##Return default if no matches were found
    return None

def get_new_state(element : "HAelement", trigger_dict : "triggerDictType", skip_conditions : bool=False):
    """
    Returns the current state of the entity associated with this element.
    Mainly just present to prevent repetition in other trigger functions.
    args:
        element: the element to determine the state form
        trigger_dict: dict with the entity triggers
        skip_conditions (bool): If state_conditionals is true, setting this to true will mean the conditional test is not performed.
    """
    ##Handle eval states hiero
    ##First test if any of the expressions can be evaluated to true, else check for the state, else return default

    # if trigger_dict["to_state"]["state"] in ["unknown", "unavailable"]:
    #     new_state = trigger_dict["to_state"]["state"]

    if attr := getattr(element,"entity_attribute", None):
        if attr in trigger_dict["to_state"]["attributes"]:
            new_state = trigger_dict["to_state"]["attributes"][attr]
            if not element.state_conditionals:
                new_state = str(new_state)
        else:
            if trigger_dict["to_state"]["state"] in ["unknown", "unavailable"]:
                new_state = trigger_dict["to_state"]["state"]
            else:
                new_state = None #"default"
    else:
        new_state = trigger_dict["to_state"]["state"]
    
    if element.state_conditionals and not skip_conditions: # and not new_state in element.state_styles:
        conditions = element.state_styles.keys()
        key = get_condition_key(new_state,conditions)
        new_state = key if key != None else new_state

    return new_state

def get_attribute_styles(element : "HAelement", trigger_dict : "triggerDictType") -> dict:
    """
    Function to check for each attribute in an elements attribute_styles if conditions matches.

    Parameters
    ----------
    element : HAelement
        The element to check
    trigger_dict : triggerDictType
        Entity's trigger

    Returns
    -------
    dict
        Dict with element properties to update
    """

    ##Maybe make a list for each attribute?
    ##i.e. - attribute: app
    ##       states:
    ##            - state: Netflix
    #               properties: blahblahblah
    ##       else:
    ##          color: blahblahblah
    attr_list = getattr(element, 'attribute_styles',[])
    if not attr_list: 
        return {}

    attr_states = trigger_dict["to_state"]["attributes"].copy()
    attr_states["state"] = trigger_dict["to_state"]["state"]

    upd_dict = {}
    for attr_conf in attr_list:
        prop_dict = {}
        attr = attr_conf.get("attribute", None)
        if attr == None:
            logger.warning(f"{element.id} attribute_styles is missing an attribute key at index {attr_list.index(attr_conf)}")
            continue

        # if attr not in attr_states or "states" not in attr_conf:
        if "states" not in attr_conf:
            if "else" in attr_conf:
                upd_dict.update(attr_conf["else"])
            continue

        state = attr_states.get(attr,None)
        if state == None:
            state = 'None'

        if attr == "state":
            str_state = state
            try:
                ##First check if state can be converted into a different type
                state = literal_eval(str_state) #@IgnoreException
            except (SyntaxError, ValueError):
                ##state cannot be evaluated as something else than a string
                pass

        for conf_state in attr_conf["states"]:
            if state == conf_state["state"]:
                prop_dict.update(conf_state.get("properties", {}))
                continue

            str_state = conf_state["state"]
            try:
                if eval(str_state): #@IgnoreException
                    prop_dict.update(conf_state.get("properties", {}))
            except (SyntaxError, NameError, TypeError, ZeroDivisionError):
                pass

        if not prop_dict and "else" in attr_conf:
            upd_dict.update(attr_conf["else"])
        elif prop_dict:
            upd_dict.update(prop_dict)
    
    return upd_dict

async def get_entity_picture(entity_picture : str, client : "HAclient") -> tuple[Union["Image.Image", "requests.Response"],int]:
    """
    Gets the entity_picture from an entity's entity_picture attribute.
    Appends the client's url if needed.   

    Parameters
    ----------
    entity_picture : str
        The entity_picture attribute, as gotten from a trigger_dict
    client : HAclient
        The Home Assistant client to get the picture from

    Returns
    -------
    Returns
    -------
    tuple[Image.Image | requests.response, status_code] | 
        If the status code is 200 (i.e. the request was succesfull) a tuple is returned with the gotten Image and the status code. 
        Otherwise a tuple with the full response and the status code is returned.
    """

    # url = entity_picture
    if "http" not in entity_picture:
        hass_url = client.hass_data["url"]
        ##I assume this should take care of getting a correct url?
        ##The SSL protocol should be present anyways if using an external url
        if not "http" in hass_url:
            hass_url = "http://" + hass_url

        url = hass_url + entity_picture
    else:
        url = entity_picture

    # try:
    #     img = await request_image_threadsafe(url)
    # except Exception as exce:
    #     logger.error(exce)

    return await request_image_threadsafe(url)

async def button_trigger(element: Union["elts.Button", "HAelement"],trigger_dict : "triggerDictType"):
    """
    Default trigger function for button (text) elements
    
    Parameters
    ----------
    element : Union[&quot;elts.Button&quot;, &quot;HAelement&quot;]
        the element this trigger originated from
    trigger_dict : triggerDictType
        the dict with trigger information
    """
    ##For buttons, element states are not required, if not it simply sets the state as new text
    
    newAttributes = {}
    new_state = get_new_state(element,trigger_dict)
    # element.font_color
    if new_state not in element.state_styles:
        if new_state == "unknown":
            newAttributes["font_color"] = UNKNOWN_COLOR #"gray4"
        elif new_state == "unavailable":
            newAttributes["font_color"] = UNAVAILABLE_COLOR #"gray4"
        
        elif "else" in element.state_styles:
            new_state = "else"
    
    statedict = element.state_styles.get(new_state,False)

    if statedict:
        if isinstance(statedict,str):
            newAttributes["text"] = statedict
        else:
            newAttributes.update(statedict)
    else:
        newAttributes["text"] = new_state
        
    if new_state in state_color_dict and getattr(element,"state_colors",False):
        newAttributes.setdefault("font_color", state_color_dict[new_state])

    if hasattr(element,"attribute_styles"):
        attr_props = get_attribute_styles(element, trigger_dict)
        newAttributes.update(attr_props)

    if newAttributes:
        # if element.parentPSSMScreen.isBatch:
        skipPrint = getattr(element.parentPSSMScreen,"isBatch",False)
        # element.update(newAttributes, skipPrint=skipPrint)
        await element.async_update(newAttributes, skipPrint=skipPrint)
    return

async def icon_trigger(element: Union["elts.Icon", "HAelement"],trigger_dict : "triggerDictType"):
    """
    Default trigger function for icon elements
    
    Parameters
    ----------
    element : Union[&quot;elts.Icon&quot;, &quot;HAelement&quot;]
        the element this trigger originated from
    trigger_dict : triggerDictType
        the dict with trigger information
    """

    newAttributes = {}
    new_state = get_new_state(element,trigger_dict)

    if new_state not in element.state_styles:
        if new_state == "unknown" or new_state == None:
            newAttributes["badge_icon"] = UNKNOWN_ICON
        elif new_state == "unavailable":
            newAttributes["badge_icon"] = UNAVAILABLE_ICON
        # elif "default" not in element.state_styles:
        #     return
        # else:
        #     new_state = "default"
        if new_state == None:
            new_state = "else"

    statedict = element.state_styles.get(new_state,False)

    if statedict:
        if isinstance(statedict,str):
            newAttributes["icon"] = statedict
        else:
            newAttributes.update(statedict)

    if hasattr(element,"attribute_styles"):
        attr_props = get_attribute_styles(element, trigger_dict)
        newAttributes.update(attr_props)
        ##Check if this state is defined in the default state colors. If so, and state_colors is true and icon_color has not been set yet, set it.

    if "icon_attribute" in newAttributes: 
        icon_attr = newAttributes["icon_attribute"] 
    else:
        icon_attr = getattr(element, "icon_attribute", None)
    
    if icon_attr != None and "icon" not in newAttributes:
        ##Defining an icon in a state overwrites the attribute.
        logger.debug(f"{element}: Getting entity {element.entity} picture")
        if icon_attr == "entity_picture":
            if element.iconData[0] != trigger_dict["to_state"]["attributes"]["entity_picture"] or element.iconData[1] != 200:

                picture_link =  trigger_dict["to_state"]["attributes"]["entity_picture"]
                (resp, status) = await get_entity_picture(picture_link, client=element.HAclient)

                if status == 200:
                    newAttributes.update({'icon': resp})
                    element._iconData = (picture_link, status)
                else:
                    element._iconData = (picture_link, status)

        else:
            new_icon = trigger_dict["to_state"]["attributes"].get(icon_attr,None)
            if new_icon != None and element.icon != new_icon:
                newAttributes["icon"] = new_icon

    if new_state in state_color_dict and getattr(element,"state_colors",False):
        newAttributes.setdefault("icon_color", state_color_dict[new_state])

    # else:
    if newAttributes:
        # element.update(newAttributes, skipPrint=skipPrint)
        await element.async_update(newAttributes)
            # if element.imgData: element.imgData.show()

        if element.fileError:
            logger.warning(f"Icon {element.icon} for state {new_state} could not be found.")
    return

async def picture_trigger(element: Union["elts.Picture", "HAelement"],trigger_dict : "triggerDictType"):
    
    newAttributes = {}
    new_state = get_new_state(element,trigger_dict)
    ##Also allow for default picture; so add picture setter?
    ##Nope can be done in default state maybe

    if new_state not in element.state_styles:
        pass
        # if new_state == "unknown" or new_state == None:
        #     newAttributes["badge_icon"] = UNKNOWN_ICON
        # elif new_state == "unavailable":
        #     newAttributes["badge_icon"] = UNAVAILABLE_ICON
        # # elif "default" not in element.state_styles:
        # #     return
        # # else:
        # #     new_state = "default"
        # if new_state == None:
        #     new_state = "default"

    statedict = element.state_styles.get(new_state,False)
    if statedict:
        if isinstance(statedict,str):
            newAttributes["picture"] = statedict
        else:
            newAttributes.update(statedict)

    if hasattr(element,"attribute_styles"):
        attr_props = get_attribute_styles(element, trigger_dict)
        newAttributes.update(attr_props)

    if "picture_attribute" in newAttributes: 
        pic_attr = newAttributes["picture_attribute"] 
    else:
        pic_attr = getattr(element, "picture_attribute", None)

    status = 0
    if pic_attr != None and "picture" not in newAttributes:
        ##Defining an icon in a state overwrites the attribute.
        logger.debug("Getting picture")
        # if pic_attr == "entity_picture":

        ##For pictures, I think it makes more sense to assume you're getting an image from the HA server.
        ##So we always try and get it.
        ##Don't know if the link works like this for other entities/attributes but eh we'll see.
        if pic_attr not in trigger_dict["to_state"]["attributes"]:
            icon = trigger_dict["to_state"]["attributes"].get("icon", None)
            if icon == None:
                if hasattr(element,"fallback_icon"):
                    icon = element.fallback_icon
                else:
                    icon = elts.MISSING_PICTURE_ICON

            if element.area != None:
                [_, size] = element.area
            else:
                size = (100,100)
            
            if mdi.is_mdi(icon):
                img = Image.new("RGBA", size, element.background_color)
                img = mdi.draw_mdi_icon(img, icon, icon_size=int(size[1]*0.3))
            else:
                img = icon

            newAttributes.update({'picture': img})
            element.pictureData = (None, -1)
        elif (element.pictureData == None or
            element.pictureData[0] != trigger_dict["to_state"]["attributes"][pic_attr] or 
            element.pictureData[1] != 200):

            picture_link =  trigger_dict["to_state"]["attributes"][pic_attr]
            (resp, status) = await get_entity_picture(picture_link, client=element.HAclient)

            if status == 200:
                newAttributes.update({'picture': resp})
                element.pictureData = (picture_link, status)
            else:
                element.pictureData = (picture_link, status)

    if newAttributes:
        # if element.parentPSSMScreen.isBatch:
        skipPrint = getattr(element.parentPSSMScreen,"isBatch",False)
        # element.update(newAttributes, skipPrint=skipPrint)
        await element.async_update(newAttributes, skipPrint=skipPrint)
        if element.fileError:
            logger.warning(f"Picture {element.picture} for state {new_state} could not be found.")
    if status == 200:
        return

        # else:
        #     new_pic = trigger_dict["to_state"]["attributes"].get(pic_attr,None)
        #     if new_icon != None and element.icon != new_icon:
        #         newAttributes["icon"] = new_icon

async def slider_trigger(element: Union["elts.Slider", "HAelement"],trigger_dict : "triggerDictType"):
    """
    Default trigger functions for sliders
    
    Parameters
    ----------
    element : Union[&quot;elts.Counter&quot;, &quot;HAelement&quot;]
        the element this trigger originated from
    trigger_dict : triggerDictType
        the dict with trigger information
    """
    ##Use min_attribute and max_attribute for the min/max values
    if element.minAttribute != None:
        if isinstance(element.minAttribute,str):
            minVal = trigger_dict["to_state"]["attributes"].get(element.minAttribute,None)
        else:
            minVal = element.minAttribute
        if minVal != None and element.minimum != minVal:
            element.minimum = minVal
            # newAttributes["minimum"] = minVal

    if element.maxAttribute != None:
        if isinstance(element.maxAttribute,str):
            maxVal = trigger_dict["to_state"]["attributes"].get(element.maxAttribute,None)
        else:
            maxVal = element.maxAttribute
        if maxVal != None and element.maximum != maxVal:
            element.maximum = maxVal
            # newAttributes["maximum"] = maxVal
    
    # entity_range = element.valueRange
    new_state = get_new_state(element,trigger_dict)

    newAttributes = {}

    if new_state  in ["off", "unknown", "unavailable", None, 'None']:
        # cur_state_perc = entity_range[0]
        
        ##What to do here for unavailable etc?
        position = element.minimum
        if new_state in ["unavailable", "unknown"]:
            icon = UNAVAILABLE_ICON if new_state == "unavailable" else UNKNOWN_ICON
            if isinstance(e := element.endPoints,str):
                ep = e
            else:
                ep = e[1]
            newAttributes["endPoints"] = (icon, ep)
            
    else:
        try:
            position = float(new_state) #@IgnoreException
            # cur_state_perc = float(new_state) #int(((new_state - entity_range[0])/(entity_range[1] - entity_range[0]))*100)
            ##Rewrite sliders to allow setting position within range.
        except TypeError:
            position = element.minimum
            logger.exception(f"New state {new_state} for slider {element.id} could not be converted into a number.")
            # if inkBoard.RAISE: raise TypeError(f"New state {new_state} for slider {element.id} could not be converted into a number.")

    newAttributes.update({'position': position})

    statedict = element.state_styles.get(new_state,False)

    if statedict:
        newAttributes.update(statedict)    

    if hasattr(element,"attribute_styles"):
        attr_props = get_attribute_styles(element, trigger_dict)
        newAttributes.update(attr_props)

    if newAttributes:
        skipPrint = getattr(element.parentPSSMScreen,"isBatch",False)
        # element.update(newAttributes, skipPrint=skipPrint)
        await element.async_update(newAttributes, skipPrint=skipPrint)

async def counter_trigger(element: Union["elts.Counter", "HAelement"],trigger_dict : "triggerDictType"):
    """
    Default trigger function for counter elements

    Parameters
    ----------
    element : Union[&quot;elts.Counter&quot;, &quot;HAelement&quot;]
        the element this trigger originated from
    trigger_dict : triggerDictType
        the dict with trigger information
    """

    newAttributes = {}
    
    if element.minAttribute != None:
        if isinstance(element.minAttribute,str):
            minVal = trigger_dict["to_state"]["attributes"].get(element.minAttribute,None)
        else:
            minVal = element.minAttribute
        if minVal != None and element.minimum != minVal:
            element.minimum = minVal
            # newAttributes["minimum"] = minVal

    if element.maxAttribute != None:
        if isinstance(element.maxAttribute,str):
            maxVal = trigger_dict["to_state"]["attributes"].get(element.maxAttribute,None)
        else:
            maxVal = element.maxAttribute
        if maxVal != None and element.maximum != maxVal:
            element.maximum = maxVal

    if element.stepAttribute != None:
        if isinstance(element.stepAttribute,str):
            stepVal = trigger_dict["to_state"]["attributes"].get(element.stepAttribute,None)
        else:
            stepVal = element.stepAttribute
        # stepVal = trigger_dict["to_state"]["attributes"].get(element.stepAttribute,None)
        if stepVal != None and element.step != stepVal:
            element.step = stepVal
            # newAttributes["step"] = stepVal

    new_state = get_new_state(element, trigger_dict)
    newAttributes["value"] = float(new_state)
    
    statedict = element.state_styles.get(new_state,False)
    if statedict:
        newAttributes.update(statedict)
    
    if hasattr(element,"attribute_styles"):
        attr_props = get_attribute_styles(element, trigger_dict)
        newAttributes.update(attr_props)

    if newAttributes:
        skipPrint = getattr(element.parentPSSMScreen,"isBatch",False)
        # element.update(newAttributes, skipPrint=skipPrint)
        await element.async_update(newAttributes, skipPrint=skipPrint)


    ##element states?
    ##Yes.

    return

async def select_trigger(element: Union["elts.DropDown", "HAelement"], trigger_dict : "triggerDictType"):
    """
    Default trigger function for (menu)select elements

    Parameters
    ----------
    element : Union[&quot;elts.DropDown&quot;, &quot;HAelement&quot;]
        the element this trigger originated from
    trigger_dict : triggerDictType
        the dict with trigger information
    """
    
    if element.optionsAttribute != None:
        if isinstance(element.optionsAttribute,str):
            options = trigger_dict["to_state"]["attributes"].get(element.optionsAttribute,None)
        else:
            options = element.optionsAttribute
        if options != None and element.options != options:
            element.options = options

    newAttributes = {}
    new_state = get_new_state(element,trigger_dict)
    
    if new_state  in ["unknown", "unavailable"]:
        # cur_state_perc = entity_range[0]

        icon = UNAVAILABLE_ICON if new_state == "unavailable" else UNKNOWN_ICON
        newAttributes["closedIcon"] = icon
    
    if new_state in element.options:
        idx = element.options.index(new_state)
        newAttributes["_selected"] = idx

    statedict = element.state_styles.get(new_state,False)
    if statedict:
        newAttributes.update(statedict)

    if hasattr(element,"attribute_styles"):
        attr_props = get_attribute_styles(element, trigger_dict)
        newAttributes.update(attr_props)

    if newAttributes:
        skipPrint = getattr(element.parentPSSMScreen,"isBatch",False)
        # element.update(newAttributes, skipPrint=skipPrint)
        await element.async_update(newAttributes, skipPrint=skipPrint)

    
    return

element_triggers = {
    elts.Icon: icon_trigger,
    elts.Picture: picture_trigger,
    elts.Button: button_trigger,
    elts.Counter: counter_trigger,
    elts.Slider: slider_trigger,
    elts.BoxSlider: slider_trigger,
    elts.DropDown: select_trigger,
}
"Links baseelements to default trigger functions"
#endregion

#region Setter functions
tosetCounter = TypedDict("toset",{"entity_attribute" : Optional[str], "minAttribute" : Union[str,int,float] ,"maxAttribute" : Union[str,int,float], "stepAttribute" : Union[str,int,float], 
                            "action" : str, "action_data_map": dict[str,str]}, total=False)
tosetCounter.__required_keys__ = frozenset({'entity_attribute','minAttribute','maxAttribute'})
def min_max_setter(element : Union["HAelement",elts.Slider, elts.BoxSlider, elts.Counter], savedattributes : dict = {}):
    """
    Default setter for Counter and Slider elements with entities attached

    Parameters
    ----------
    element : Union[elts.Slider, elts.BoxSlider, elts.Counter]
        the element that will be set
    savedattributes : dict, optional
        attributes that were saved during the wrapping of this element into a home assistant element, by default {}
    """
    
    # toset = {"minAttribute" : "minimum","maxAttribute" : "maximum","entity_attribute" : None}
    # toset = {"entity_attribute", "minAttribute" ,"maxAttribute"}

    toset = tosetCounter
    defaultDomains = {"counter" :  toset(entity_attribute=None,minAttribute="minimum",maxAttribute="maximum", stepAttribute="step", action="counter.set_value", action_data_map={"value":"value"}), 
                    "number":  toset(entity_attribute=None,minAttribute="min",maxAttribute="max", stepAttribute="step", action="number.set_value", action_data_map={"value":"value"}),
                    "input_number":  toset(entity_attribute=None,minAttribute="min",maxAttribute="max", stepAttribute="step", action="input_number.set_value", action_data_map={"value":"value"}),
                    "light":  toset(entity_attribute="brightness",minAttribute=0,maxAttribute=254, stepAttribute=1, action="light.turn_on", action_data_map={"brightness": "value"}), ##no min/max brightness so how to set that -> I think just set an optional number value
                    "climate":  toset(entity_attribute="temperature",minAttribute="min_temp",maxAttribute="max_temp", stepAttribute="target_temp_step", action="climate.set_temperature", action_data_map={"temperature": "value"}),
                    "fan":  toset(entity_attribute="percentage",minAttribute=0,maxAttribute=100, stepAttribute=1, action="fan.set_percentage", action_data_map={"percentage": "value"}),
                    "cover" :  toset(entity_attribute="current_cover_position",minAttribute=0,maxAttribute=100, stepAttribute=1, action="cover.set_cover_position", action_data_map={"position": "value"}),
                    "media_player" :  toset(entity_attribute="volume_level",minAttribute=0,maxAttribute=1, stepAttribute=0.1, action="media_player.volume_set", action_data_map={"volume_level": "value"}),
                    "water_heater" :  toset(entity_attribute="target_temperature",minAttribute="min_temp",maxAttribute="max_temp", action="water_heater.set_temperature", action_data_map={"temperature": "value"}),
                    "valve":  toset(entity_attribute="current_valve_position",minAttribute=0,maxAttribute=100,step=1,action="valve.set_position", action_data_map={"position":"value"})
                    }
    ##Most unknown domains use percentages. media_player is here for volume support
    domain = element.entity.split(".")[0]
    if domain not in defaultDomains:
        return
    
    if isinstance(element, elts.Counter):
        toset.__required_keys__ = toset.__required_keys__.union(frozenset({"stepAttribute"}))
        if element.on_count == None:
            # element.on_count = element.HAclient.call_service_action
            v = defaultDomains[domain]["action"]
            d = {"action": "service-action", 
                "data": {"action": defaultDomains[domain]["action"]}, "map": defaultDomains[domain]["action_data_map"]}
            element.on_count = d
            ##So set on_count_map and on_count_data
            ##service_action_data should be made from the kwargs
            # toset.__required_keys__ = toset.__required_keys__.union(frozenset({"action", "action_data_map"}))
    elif isinstance(element, (elts.Slider, elts.BoxSlider)):
        if element._tap_action == None:
            # element.tap_action = element.HAclient.call_service_action
            d = {"action": "service-action", 
                "data": {"action": defaultDomains[domain]["action"]}, "map": defaultDomains[domain]["action_data_map"]}
            element.tap_action = d
            # toset.__required_keys__ = toset.__required_keys__.union(frozenset({"action", "action_data_map"}))

    # if "action" in savedattributes and "action_data_map" not in savedattributes: savedattributes["action_data_map"] = {}
    for attr in toset.__required_keys__:
        # if attr == "action_data_map":
        #     print(type(defaultDomains[domain][attr]))
        #     print("hi")
        #     pass
        if attr in savedattributes:
            ##Declare an attribute when building the element as None to not set a default.
            continue
        
        v = defaultDomains[domain][attr]
        setattr(element,attr,v)

    return

def options_setter(element : Union["HAelement",elts.DropDown], savedattributes : dict = {}):
    toset = TypedDict("toset",{"entity_attribute" : Optional[str], "optionsAttribute" : Union[str,int,float] ,
                            "action" : str, "action_data_map": dict[str,str]}, total=False)
    toset.__required_keys__ = frozenset({'entity_attribute','optionsAttribute'})
    defaultDomains = {"select" :  toset(entity_attribute=None,optionsAttribute="options", action="select.select_option", action_data_map={"option":"selected_option"}), 
                    "input_select":  toset(entity_attribute=None,optionsAttribute="options", action="input_select.select_option", action_data_map={"option":"selected_option"})
    }

    domain = element.entity.split(".")[0]
    if domain not in defaultDomains:
        return

    if element.on_menu_select == None:
        element.on_menu_select = element.HAclient.call_service_action
        toset.__required_keys__ = toset.__required_keys__.union(frozenset({"action", "action_data_map"}))

    if "action" in savedattributes and "action_data_map" not in savedattributes: savedattributes["action_data_map"] = {}
    for attr in toset.__required_keys__:
        if attr in savedattributes:
            ##Declare an attribute when building the element as None to not set a default.
            continue
        
        v = defaultDomains[domain][attr]
        setattr(element,attr,v)

    return

def default_action_setter(element : "HAelement"):
    """
    Sets the default tap_action for some base elements according to their entity.

    Parameters
    ----------
    element : HAelement
        the element to set the tap_action of.
    """

    if not isinstance(element.entity,str) or getattr(element, "HAclient", None) == None:
        return

    domain = element.entity.split(".")[0]
    if domain in DEFAULT_DOMAIN_ACTIONS and element.tap_action == None:
        d = {"action": "service-action"}
        # element.tap_action = element.HAclient.call_service_action
        # element.action = DEFAULT_DOMAIN_ACTIONS[domain] ##Entity is automatically gotten from the element itself

        if domain in ["input_select", "select"]:
            d["data"] = {"action": DEFAULT_DOMAIN_ACTIONS[domain],"cycle": True}
        else:
            d["data"] = {"action": DEFAULT_DOMAIN_ACTIONS[domain]}
        
        element.tap_action = d

compound_setters = {
    elts.Counter: min_max_setter,
    elts.Slider: min_max_setter,
    elts.BoxSlider: min_max_setter,
    elts.DropDown: options_setter,
}
##Should I include a setter here for the bool select?

default_tap_action_setters = {
    elts.Button: default_action_setter, 
    elts.Icon: default_action_setter,
    elts.Picture: default_action_setter
    }

def set_trigger_function(element : "HAelement", savedattributes : dict = {}) -> Callable:
    """
    Applies the appropriate default trigger function to an element if none have been set.

    Parameters
    ----------
    element : HAelement
        element to apply the function to
    savedattributes : dict, optional
        attributes that were already applied to the element before wrapping, by default {}

    Returns
    -------
    Callable
        _description_
    """
    
    "Sets the base trigger function for the provided element type if it was not yet set."
    # if hasattr(element,"trigger_function"):
    eCls =  element.__class__.__base__
    if "trigger_function" in savedattributes:
        ##Perform the check here for possible custom functions
        if isinstance(element.trigger_function,str):
            if "custom:" in element.trigger_function.lower():
                ##Will not do this here, but do it via the parser.
                pass
        ##Probably not return here yet
        # return
    elif eCls in element_triggers:
        element.trigger_function = element_triggers[eCls] #element_triggers[element.__class__.__base__]
    else:
        logger.info(f"Got pssm element without base trigger function: {element.__class__.__name__}")
    
    if eCls in compound_setters:
        setter = compound_setters[eCls]
        setter(element, savedattributes)

    if eCls in default_tap_action_setters and element.tap_action == None:
        func = default_tap_action_setters[eCls]
        func(element)

    # if isinstance(element,elts.Counter):
    #     print(element.minAttribute)
    #     element.minAttribute = 3
    #     print("That's it")
    return None 

#endregion