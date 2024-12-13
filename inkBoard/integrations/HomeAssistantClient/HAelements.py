"""
PSSM elements that integrate  with Home Assistant entities
""" 

from __future__ import annotations

import asyncio
from time import sleep
from yaml.loader import SafeLoader
from pathlib import Path

# import datetime as dt_lib
from datetime import timezone, datetime, timedelta
#from read_config import dashboardConfig
from io import BytesIO
import logging
import math
from itertools import cycle
from typing import TYPE_CHECKING, Optional, TypeVar, Any, Union
from functools import partialmethod, partial
from types import MappingProxyType
from abc import ABC, abstractmethod

from PIL import Image

from PythonScreenStackManager import elements
from PythonScreenStackManager.elements import baseelements as base, colorproperty
from PythonScreenStackManager.elements.baseelements import DEFAULT_FONT_BOLD, Style
from PythonScreenStackManager.elements.constants import DEFAULT_BACKGROUND_COLOR, DEFAULT_FOREGROUND_COLOR,\
                                                    DEFAULT_FONT, DEFAULT_FONT_HEADER, DEFAULT_ACCENT_COLOR
from PythonScreenStackManager import tools
from PythonScreenStackManager.tools import DummyTask, parse_weather_icon
from PythonScreenStackManager.pssm_types import *

import mdi_pil as mdi

from inkBoard.constants import FuncExceptions

from .constants import UNAVAILABLE_COLOR, UNAVAILABLE_ICON, UNKNOWN_ICON, UNKNOWN_COLOR, DEFAULT_HA_DT_FORMAT,\
                    entity_tags, ENTITY_TAG_KEY, ERROR_STATES, all_entities
            

from .helpers import DomainError, EntityType, WeatherData, stateDictType, triggerDictType

from . import trigger_functions as triggers
from .trigger_functions import set_trigger_function

from . import icon_sets

if TYPE_CHECKING:
    from inkBoard.integrations.HomeAssistantClient.client import HAclient, triggerDictType
    # from typing import Union
else:
    ##Union is causing some weird bug in VSCode, the first line is marked as an error when it is imported. 
    ##Importing it like this solves that, typehinting isn't present tho but alas
    ##Leaving this comment here in case I start wondering again
    from typing import Union



logger = logging.getLogger(__name__)
# 

##Set default client here? For service calls?
##Tho maybe not necessary since these can work with properties, later on.

# entity_tag_key = "!entity "

def validate_entity(elt : HAelement, entity : str):
    "Check if this entity is allowed for the element. Returns False if not. Also parses entities set using the !entity tag."
    if not isinstance(entity, str):
        msg = f"{elt}: Entities must of type str. {type(entity)}: {entity} is not valid."
        logger.exception(TypeError(msg))
        return False
        # raise TypeError("Entities must of type str")
    
    if entity.startswith(ENTITY_TAG_KEY):
        tag = entity.removeprefix(ENTITY_TAG_KEY)
        if tag not in entity_tags:
            msg = f"{elt}: {tag} could not be found as a key in the entities.yaml file. "
            logger.exception(KeyError(msg))
            return False
        else:
            entity = entity_tags[tag]

    if elt.ALLOWED_DOMAINS:
        domain = entity.split(".")[0]
        if not domain in elt.ALLOWED_DOMAINS:
            msg = f"Entity domains for {type(elt).__name__} must be one of {elt.ALLOWED_DOMAINS}. {entity} is an invalid entity."
            logger.exception(DomainError(msg))
            return False
    
    return entity
            # raise DomainError(f"Entity domains for {type(elt).__name__} must be one of {elt.ALLOWED_DOMAINS}. {entity} is an invalid entity.")

def _attribute_getter(attr : str, self):
    """
    Helper function for generic attribute getter. 
    Use as partial function: x = partial(_attribute_getter, "attribute_name"), and set x as the getter

    Parameters
    ----------
    attr : str
        the attribute to get

    Returns
    -------
    _type_
        the objects attribute
    """
    ##Use partials for these
    v = getattr(self,attr)
    if isinstance(v, dict):
        if attr[0] == "_":
            return v
        else:
            return MappingProxyType(v)
    else:
        return v
    # return getattr(self,attr)

def _attribute_setter(attr : str, self, value : Optional[str]):
    """
    Helper function for generic attribute setter. 
    Use as partial function: x = partial(_attribute_setter, "attribute_name"), and set x as the setter

    Parameters
    ----------
    attr : str
        the attribute to set

    Returns
    -------
    _type_
        the objects attribute
    """
    if value == None:
        pass
    elif not isinstance(value,str):
        allowed = compoundProps[attr.lstrip("_")][1]
        if isinstance(value, allowed):
            pass
        else:
            msg = f"Element {self.id}: Entity Attribute {attr} must be a string or None. {value} is not valid"
            logger.exception(msg, exc_info= TypeError(msg))
            return
        # raise TypeError(msg)
    setattr(self,attr,value)
    # self._entity_attribute1 = value

compoundProps = {
    "minAttribute": (("minAttribute","_minAttribute", None, "entity attribute to get the minimum allowed value from"),(int,float)),
    "maxAttribute" : (("maxAttribute","_maxAttribute", None, "entity attribute to get the maximum allowed value from"),(int,float)),
    "stepAttribute": (("stepAttribute","_stepAttribute", None, "entity attribute to get the increment/decrement step value from"),(int,float)),
    "optionsAttribute": (("optionsAttribute","_optionsAttribute", None, "entity attribute listing possible value options"),())
}
"Properties for some compound elements, mapped in compoundAttribute. Each key returns a tuple with 2 entries: the tuple with property settings (property, attribute, default, doc string), and the allowed types along with string"

compoundAttributes : MappingProxyType[elements.Element, 
                                    list[tuple[str,str,Any]]] = MappingProxyType({
        elements.Counter: [compoundProps["minAttribute"][0],compoundProps["maxAttribute"][0],compoundProps["stepAttribute"][0]],
        elements.Slider: [compoundProps["minAttribute"][0],compoundProps["maxAttribute"][0]],
        elements.BoxSlider: [compoundProps["minAttribute"][0],compoundProps["maxAttribute"][0]],
        elements.DropDown: [("optionsAttribute","_optionsAttribute", None)]
        })
"Additional attributes for some compound elements. Usage: [element]: ('attribute Name','return Attribute','default Value', [optional doc string])"


class HAmetaElement(type(elements.Element)):    
    def __instancecheck__(self, instance):
        wrapper = hasattr(instance,"__HAwrapper")
        return wrapper

##Each element that relies on layout should simply call the layout init themselves I think (So base them on multiple classes)
class HAelement(elements.Element, metaclass=HAmetaElement): #, ABC):
    """
    Class that provides base properties and functions for elements connected to Home Assistant entities.
    Nonfunctional if not used as a parent class, but usefull for typechecking.
    When making new element classes, use this as the first parentclass, as otherwise it seems to cause issues.
    """
    ALLOWED_DOMAINS = []
    "Allowed entity domains for this element. Empty if any domain is allowed."

    @property
    def _emulator_icon(cls): return "mdi:home-assistant"

    ##Not sure how it's possible to use this class from an already defined element instance.
    ##So I'm not going to, I tried quite a bit.
    def __init__(self, baseElement : Optional[elements.Element] = None):
        # self = element
        # self.__class__ = baseElement.__class__
        # self._HAclient = None
        if baseElement != None:
            self.wrap_element(baseElement)       
        else:

            ##Do this in a similar for loop as the wrapper function
            # self.__HAwrapper = HAelement.__HAwrapper
            if not hasattr(self,"_HAclient"):
                self._HAclient = None
            if not hasattr(self,"_entity_attribute"):
                self._entity_attribute = False
            if not hasattr(self,"_serviceCallTime"):
                self._serviceCallTime = None
            if getattr(self,"link_element", False):
                self.__link_element_to_config(self)
            else:
                if not hasattr(self,"_state_styles"):
                    self._state_styles = {}
                if not hasattr(self,"_attribute_styles"):
                    self._attribute_styles = []
                if not hasattr(self,"_state_conditionals"):
                    self.state_conditionals = False
                if not hasattr(self,"_state_colors"):
                    self.state_colors = False

            if not hasattr(self, "__HAwrapper"):
                self.__setattr__("__HAwrapper",HAelement.__HAwrapper)
            # print(self.__HAwrapper)
            

    #region
    @property
    def HAclient(self) -> "HAclient":
        "The Home Assistant websocket client connected to the element"
        return self._HAclient

    @property
    def entity(self) -> str:
        "The entity_id of the entity associated with this element. Can be changed, but that will also mean the old entity is not linked anymore."
        return self._entity
    
    @entity.setter
    def entity(self, value):

        entity_id = validate_entity(self,value)
        if not entity_id or entity_id == getattr(self,"_entity",None):
            return
        ##Also make this automatically reregister in the client.
        # if self._HAclient != None:
        old_entity = getattr(self,"_entity",None)
        self._entity = entity_id

        if getattr(self,"_HAclient",None) != None:
            self.HAclient.update_element_entity(element=self, new_entity=entity_id, old_entity=old_entity, update_now=True)


    @property
    def entity_attribute(self) -> Union[str,bool]:
        "Optional entity attribute to use as state. Set to None to use entity state."
        return self._entity_attribute
    
    @entity_attribute.setter
    def entity_attribute(self, value:str):
        # if isinstance(value,bool):
        #     if value: raise ValueError("Entity Attribute can only have boolean value False.")
        if value == None:
            pass
        elif not isinstance(value,str):
            raise TypeError("Entity Attribute must be a string or boolean False.")
        self._entity_attribute = value

    @property
    def state_styles(self) -> MappingProxyType[Literal["state"],dict[Literal["property"],Any]]:
        """
        Dict mapping entity states (or attribute if set) to element attributes to update when that state is received.
        You can also add a default key to use for undefined states. Some default trigger functions deal with the Unavailable and Unknown states, but these can be overwritten.
        If a key returns a string instead of a dict, the value is used to update the base attribute (i.e. set a new icon for Icon elements.)
        """
        return MappingProxyType(self._state_styles.copy())
    
    @state_styles.setter
    def state_styles(self, value):
        # raise Exception
        if not isinstance(value, dict):
            raise TypeError(f"{self}: Element state must be a dict, not {type(value)}: {value}.")
        self._state_styles = value.copy()

    @property
    def attribute_styles(self) -> triggers.attribute_stylesType:
        """
        Element styling as determined by the values of attributes. 
        Advanced property, has not been tested to its full extend, so it may lead to issues.

        Usage
        ----------
        Each entry in the list needs an `attribute` key, which maps it to the connectes entities attribute. `'state'` can also be used here, which maps to the entities state.
        The `states` key is a list which is looped through. 
            Each item needs a `state` key. The value is first tested to see if it matches the value of the attribute. 
            If it does not, it is tested as a condition. In here, the value of the attribute can be provided as `state`. So for example `state < 25'.
            All items in the list are tested. Any that is `True` will update the dict with element properties to update. So, order matters, as each condition that evaluates to true can overwrite previous conditions.
        The `else`, if present, is used when the attribute is not present in the entity's state, or if none of the conditions evaluated to True. This key is not required.

        Bad YAML Example
        ----------
        ```
        - attribute: brightness
          states:
            - state: 'state<100'
              properties:
                color: gray3
            - state: '200<state<254'
              properties:
                 color: white
            - state: 'state<215'
              properties:
                color: gray10
          'else':
            color: black
        ```
        This generally maps a color to the brightness of a light. However there are a few problemns:
            - If the brightness value is between 201 and 214, the second state evaluates `True`, however the third one also evaluated `True`. This causes the color of the element to be set to gray10.
            - If the brightness value is 254 or higher, none of the states evaluate to True, which means the else case is used and the element's color becomes black, even if the light is at maximum brightness.
        A working version of this would be:

        Good YAML Example
        ----------
        ```
        - attribute: brightness
          states:
            - state: '10<state<100'
              properties:
                color: gray3
            - state: 'state>=200'
              properties:
                 color: white
            - state: 'state<200'
              properties:
                color: gray10
            - state: 'None'
              properties:
                color: None
          'else':
            color: black
        ```
        Now, when the light is off, the color becomes None (None can be used to map to the attribute not being present). If the brightness is smaller than 10, the element's color is black since no condition evaluates as `True`. When the brightness is larger than or equal to 200, it will be white (so also at maximum brightness), and the third state does not interfere with it anymore.
        """
        return self._attribute_styles

    @attribute_styles.setter
    def attribute_styles(self, value):
        if not value:
            value = []
        if not isinstance(value, (list, tuple)):
            logger.exception(ValueError(f"{self}: attribute_styles must be a list, not {type(value)}: {value}"))
        
        self._attribute_styles = value

    @property
    def state_colors(self) -> bool:
        "True if the elements color may be set by the configured state colors, if the main color property is not defined in the dict for the state."
        return self._state_colors
    
    @state_colors.setter
    def state_colors(self, value:bool):
        if isinstance(value,bool):
            self._state_colors = value
        else:
            raise TypeError("state_colors must be True or False")

    @property
    def state_conditionals(self) -> bool:
        """
        If true, the element will first treat the keys in the state_styles dict as possible conditions.
        The first condition to return true will be used to configure the element's attributes. If none return True, it will check if the state is present as a key, and only then will use the default element_state if provided.
        """
        return self._state_conditionals

    @state_conditionals.setter
    def state_conditionals(self, value:bool):
        if isinstance(value,bool):
            self._state_conditionals = value
        else:
            raise TypeError("state_conditionals must be a boolean")

    @property
    def __HAwrapper(self):
        """
        Attribute to indicate this element was wrapped into a Home Assistant element. 
        Don't reference it directly, use hasattr(element,'__HAwrapper'). 
        The attribute is always true, but only set if the element is either a subclass of HAelement (Which is true for all elements in the HAelements module), or has been wrapped using HAelement.wrap_element(element). 
        """
        return True
    
    @property
    def serviceCallTime(self):
        "The last time a service was called via this element."
        return self._serviceCallTime
    #endregion

    @abstractmethod
    async def trigger_function(self,element : "HAelement", trigger_dict : "triggers.triggerDictType"): #trigger_dict : dict["entity_id", "to_state", "from_state"]):
        """
        This function is called when the entity associated with the element is updated. 
        Passed are the element itself, and a trigger dict with ['new_state'] and ['old_state'] (and some other keys for clarity).
        When initially setting up, old_state will be false, so be mindfull of this when coding.
        Can be a blocking function, but the typing will show a coroutine.
        args:
            element (element): the element whose attribute has this function. Is passed to deal with non-class trigger_functions
            trigger (dict): dict with the trigger parameters. When processing, be mindful of the scenerio where 'from_state' is False (i.e. when initially setting up) if relevant.
        """
        logger.warning("This HAelement has no update function set")
        return

    @classmethod
    def wrap_element(cls,element : Union[elements.Element, "HAelement"], client : "HAclient") -> "HAelement":
        # setattr(element,"HAclient",cls.HAclient.fget())
        # cls()
        # element._HAclient = None
        # element._HAclient = None
        """
        Wraps a base PSSM element in a Home Assistant element, to add protections, checks etc. for some important attributes by wrapping them into a property.
        This function is automatically called when adding elements with an entity attribute to a Home Assistant client instance.
        Reference: 
        * https://stackoverflow.com/a/1355444/509706
        * https://stackoverflow.com/questions/48448074
        
        Parameters
        ----------
        element : Element
            element to wrap into a Home Assistant element
        client : HAclient
            The client to attach this element to
        """
        ##List of properties and their associated attribute name and default value
        properties = {
            "HAclient": ("_HAclient",client),
            "entity": ("_entity",None),
            "entity_attribute": ("_entity_attribute",False),
            "state_styles": ("_state_styles",{}),
            "attribute_styles" : ("_attribute_styles", []),
            "state_colors": ("_state_colors",False),
            "state_conditionals": ("_state_conditionals", False),
            "serviceCallTime": ("_serviceCallTime", None)
            # "trigger_function": "trigger_function"
        }
        ##Dict to link each property to the actual attribute
        # element.__init_subclass__
        # class_name = "Wrapped" + element.__class__.__name__ #+ 'Child'
        class_name = element.__class__.__name__
        typeDict = {}
        saved = {}

        for prop in properties:
            if hasattr(element,prop):
                saved[prop] = getattr(element,prop)
            typeDict[prop] = getattr(cls,prop)

        if element.__class__ in compoundAttributes:
            moreProps = cls.wrap_compound(element, properties)
            for prop in moreProps:
                if hasattr(element,prop):
                    saved[prop] = getattr(element,prop)
            # properties.update(moreProps)
            typeDict.update(moreProps)

        typeDict["__HAwrapper"] = cls.__HAwrapper
        typeDict["ALLOWED_DOMAINS"] = cls.ALLOWED_DOMAINS
        child_class = type(class_name, (element.__class__,), typeDict)#{"HAclient": cls.HAclient, "entity": cls.entity})

        element.__class__ = child_class
        for prop in properties:
            (attr,val) = properties[prop]
            val = saved.get(prop,val)
            setattr(element,attr,val)

        if element.entity != None and ENTITY_TAG_KEY in element.entity:
            element.entity = element.entity
        # element._entity
        # element.__instancecheck__ = cls.__instancecheck__
        # setattr(element,"__instancecheck__",cls.__instancecheck__)
        if v := getattr(element,"trigger_function",False):
            saved["trigger_function"] = v

        ##Check if the entity is defined in the entities key, and the element has link_element
        if (ent := all_entities.get(element.entity, False)) and getattr(element,"link_element", True):
            ent : dict

            ##defaults to true for now, do I want that?
            if ent.get("link_elements",True):
                ##Also link possible attribute?

                ##Making changes here: don't forget to also change it in wrap_element
                if not "state_styles" in saved:
                    element.state_styles = ent.get("state_styles",{})

                if not "attribute_styles" in saved:
                    element.attribute_styles = ent.get("attribute_styles",{})

                if not "state_colors" in saved:
                    element.state_colors = ent.get("state_colors", False)

                if not "state_conditionals" in saved:
                    element.state_conditionals = ent.get("state_conditionals",False)

        set_trigger_function(element, saved)
        return element 

    @classmethod
    def wrap_compound(cls, element : "HAelement", properties : dict) -> dict:
        """
        Applies some additional attributes to the compound element for better HA connectivity 
        Also performs domain checks

        Parameters
        ----------
        element : HAelement
            Element to wrap
        properties : dict
            the dict with properties to update

        Returns
        -------
        dict
            Additional properties to apply to this element
        """
        ##See how this one works. Make some properties that deal with this?
        ##Idk if checks area really necessary on these though tbf. Mainly just need the attributes to set + HA attributes
        # typeDict[prop] = getattr(cls,prop)

        ##For sliders/counters: add min/maxAttribute
        ##For DropDown: add optionsAttribute
        eltcls = element.__class__
        newprops = compoundAttributes[eltcls]
        typeDictupdt = {}
        for prop in newprops:
            # print(prop)
            protectedAttr = prop[1]
            properties[prop[0]] = (protectedAttr, prop[2])
            g = partial(_attribute_getter, protectedAttr)
            s = partial(_attribute_setter, protectedAttr)
            doc = None if len(prop) < 4 else prop[3]
            typeDictupdt[prop[0]] = property(fget=g,fset=s, doc=doc)
            # print("hi")
        
        return typeDictupdt

    def __link_element_to_config(self, element : "HAelement"):
        "Links an element to settings in the entity config. Does not overwrite settings if they are already applied, and only called during init (hence a private method)"
            
        # if (ent := all_entities.get(self.entity, False)) and getattr(self,"link_element", True):
        ent : dict = all_entities.get(self.entity, {})

        ##Like this: the element should still have all the needed properties/attributes set.
        if not ent.get("link_elements",False):
            ent = {}

        ##defaults to true for now, do I want that?
        # if ent.get("link_elements",True):
            ##Also link possible attribute?

        ##Making changes here: don't forget to also change it in wrap_element
        if not hasattr(self,"_state_styles"):
            element.state_styles = ent.get("state_styles",{})

        if not hasattr(self,"_attribute_styles"):
            element.attribute_styles = ent.get("attribute_styles",{})

        if not hasattr(self,"_state_colors"):
            element.state_colors = ent.get("state_colors", False)

        if not hasattr(self,"_state_conditionals"):
            element.state_conditionals = ent.get("state_conditionals",False)

##Maybe use the entityElement as a base class to ensure all stuff is set at init?

class StateButton(HAelement, elements.Button):
    """
    Button displaying the state of an entity as text.

    Parameters
    ----------
    entity : str
        entity_id of the entity to show
    entity_attribute : Optional[str], optional
        Optional attribute to show as state. Set to None to use the state, by default None
    prefix : Optional[str], optional
        Prefix to show before the state, by default None (No prefix)
    suffix : Optional[str], optional
        Suffix to show after the state, by default None (No suffix)
    prefix_attribute : Optional[str], optional
        Entity attribute to use as prefix. Overwrites prefix, by default None
    suffix_attribute : Optional[str], optional
        Entity attribute to use as suffix. Overwrites suffix,, by default "default", which at initialising sets it to unit_of_measurement if entity_attribute is None, and otherwise None.
    text_mode : bool
        Overwrites the text property and allows setting the text directly.
    """

    @property
    def _emulator_icon(cls): return "mdi:text-box-search"

    def __init__(self, entity : str, entity_attribute : Optional[str] = None, 
                prefix : Optional[str] = None, suffix : Optional[str] = None, 
                prefix_attribute : Optional[str] = None, suffix_attribute : Optional[str] = "default", 
                prefix_separator : Optional[str] = None, suffix_separator : Optional[str] = None,
                text_mode : bool = False, **kwargs):
        ##Give this (or every element? a state_expression or smth option which means states will be evalled to allow for conditions)
        ##Also, give a pre/sufficAttribute that gets the prefix/suffic (i.e. unit) from HA
        ## -> Will default to unit_of_measurement

        self.entity = entity
        self.entity_attribute = entity_attribute

        self._state = None
        self.prefix = prefix
        self.suffix = suffix

        if suffix_attribute == "default":
            if entity_attribute == None:
                suffix_attribute = "unit_of_measurement"
            else:
                suffix_attribute = None

        self.prefix_attribute = prefix_attribute
        self.suffix_attribute = suffix_attribute
        self.prefix_separator = prefix_separator
        self.suffix_separator = suffix_separator

        self.text_mode = text_mode

        text = kwargs.pop("text",None)

        elements.Button.__init__(self, text=text, **kwargs)

        HAelement.__init__(self)

        ##For the entityTile, use these as both title and text elements
        pass

    #region
    @property
    def text(self) -> str:
        if self.text_mode and hasattr(self, "_text"):
            return self._text

        if self.state in ["unknown", "unavailable"]:
            return self.state
        
        if self.prefix != None:
            pf = f"{self.prefix} "
            if self.prefix_separator != None:
                pf = f"{pf}{self.prefix_separator} "
        else:
            pf = ""
        
        if self.suffix != None:
            sf = "%" if self.suffix == "%" else f" {self.suffix}"
            if self.suffix_separator != None:
                sf = f" {self.suffix_separator}"
        else:
            sf = ""            

        return f"{pf}{self.state}{sf}"            
        # return f"{self.prefix}{self.state}{self.suffix}"
    
    @text.setter
    def text(self, value):
        if not self.text_mode:
            logger.warning(f"{self}: text_mode is not enabled, so the button (may) not show the set text.")
        self._text = str(value)

    @property
    def text_mode(self) -> bool:
        "If True, the element will display the set text, instead of the state. Use with care."
        return self._text_mode

    @text_mode.setter
    def text_mode(self, value):
        self._text_mode = bool(value)

    @property
    def state(self) -> str:
        "The value of the entity's state or attribute that is displayed as the state"
        return self._state
    
    @property
    def entity_attribute(self) -> Optional[str] :#Optional[str]:
        """
        The entity's attribute being shown as the element's state. Set to None to use the state (default)
        If the attribute is not present the button will display no text.
        """
        return self.__entity_attribute

    @entity_attribute.setter
    def entity_attribute(self, value):
        if not isinstance(value,str) and value != None: # or value != False:
            msg = f"entity_attribute must be a string or None. {value} is invalid."
            logger.exception(TypeError(msg))
            return
        self.__entity_attribute = value

    @property
    def suffix(self) -> str:
        return self._suffix

    @suffix.setter
    def suffix(self, value):
        if value != None:
            value = str(value)
        self._suffix = value

    @property
    def suffix_attribute(self) -> Optional[str]:
        "Entity attribute to get the suffix from. Overwrites the value of suffix if not None."
        return self._suffix_attribute
    
    @suffix_attribute.setter
    def suffix_attribute(self, value):
        self._suffix_attribute = str(value)

    @property
    def suffix_separator(self) -> str:
        "Character(s) to separate the state text and the suffix. Set to None for no separator"
        return self._suffix_separator
    
    @suffix_separator.setter
    def suffix_separator(self, value):
        if value != None:
            value = str(value)
        self._suffix_separator = value

    @property
    def prefix(self) -> str:
        return self._prefix

    @prefix.setter
    def prefix(self, value):
        if value != None:
            value = str(value)
        self._prefix = value

    @property
    def prefix_attribute(self) -> Optional[str]:
        "Entity attribute to get the prefix from. Overwrites the value of prefix if not None."
        return self._prefix_attribute
    
    @prefix_attribute.setter
    def prefix_attribute(self, value):
        self._prefix_attribute = str(value)

    @property
    def prefix_separator(self) -> str:
        "Character(s) to separate the state text and the prefix. Set to None for no separator"
        return self._prefix_separator
    
    @prefix_separator.setter
    def prefix_separator(self, value):
        if value != None:
            value = str(value)
        self._prefix_separator = value
    #endregion

    async def trigger_function(self, element: Union["elements.Button", "HAelement"], trigger_dict : "triggers.triggerDictType"):
        
        newAttributes = {}
        new_state = triggers.get_new_state(self,trigger_dict)

        if new_state not in self.state_styles:
            if new_state == "unknown":
                newAttributes["font_color"] = UNKNOWN_COLOR #"gray4"
            elif new_state == "unavailable":
                newAttributes["font_color"] = UNAVAILABLE_COLOR #"gray4"
            
            if "else" in self.state_styles:
                new_state = "else"

        statedict = self.state_styles.get(new_state,{})
        attr_props = triggers.get_attribute_styles(self, trigger_dict)
        statedict.update(attr_props)
        # attribute_styles = self.attribute_styles.get()
        
        if self.entity_attribute != None and self.entity_attribute not in trigger_dict["to_state"]["attributes"] and "entity_attribute" not in statedict:
            newAttributes["_state"] = " "

        if statedict:
            if isinstance(statedict,str):
                newAttributes["_state"] = statedict
            else:
                statedict :  dict
                if "state" in statedict:
                    s = statedict.pop("state")
                    statedict["_state"] = s
                newAttributes.update(statedict)
        else:
            # if self.entity_attribute != None and self.entity_attribute in trigger_dict["to_state"]["attributes"]:
            #     newAttributes["_state"] = " "
            # else:
            if "_state" not in newAttributes:
                newAttributes["_state"] = new_state

        if "entity_attribute" in newAttributes: #and self.entity_attribute != newAttributes["entity_attribute"]:
            # and self.entity_attribute not in trigger_dict["to_state"]["attributes"]:
            new_attr = newAttributes["entity_attribute"]
            if new_attr == None:
                newAttributes.setdefault("_state", trigger_dict["to_state"]["state"])
            else:
                new_state = trigger_dict["to_state"]["attributes"].get(new_attr," ")
            # new_state = trigger_dict["to_state"]["attributes"]
                newAttributes["_state"] = new_state

        prefixAttr = newAttributes["prefix_attribute"] if "prefix_attribute" in newAttributes else self.prefix_attribute
        if prefixAttr != None:
            if prefixAttr == "state":
                prefix_val = trigger_dict["to_state"]["state"]
            else:
                prefix_val = trigger_dict["to_state"]["attributes"].get(prefixAttr,None)
            if prefix_val != None and self.prefix != prefix_val:
                newAttributes["prefix"] = prefix_val

        suffixAttr = newAttributes["suffix_attribute"] if "suffix_attribute" in newAttributes else self.suffix_attribute
        if suffixAttr != None:
            if suffixAttr == "state":
                suffix_val = trigger_dict["to_state"]["state"]
            else:
                suffix_val = trigger_dict["to_state"]["attributes"].get(suffixAttr,None)
            if suffix_val != None and self.suffix != suffix_val:
                newAttributes["suffix"] = suffix_val

        if newAttributes:
            await self.async_update(newAttributes) #, skipPrint=False, reprintOnTop=False)

        return

##This can be deprecated, does not really have use like this since build_layout has no real automations attached to it it seems.
class _EntityLayout(HAelement, elements.Layout):
    """
    Base layout element that can be used as a parentclass. Ensures typechecking and makes sure updating the element rebuilds the entire layout. The Home Assistant client can interact with.
    """
    def __init__(self, entity:str, layout, trigger_function = False, link_element = False, **kwargs):
        
        # super().__init__( layout=layout,  **kwargs)
        # HAelement
        self.link_element = link_element

        HAelement.__init__(self)
        
        ##If layout is None, assume the layout element is called elsewhere

        # if layout != None:
        elements.Layout.__init__(self, layout=layout,  **kwargs)
        # self.pssm_update = self.update
        # self.update = self.update_element
        
        self.entity : str = entity
        "The entity_id of the entity associated with this element"

        if not trigger_function:
            self.trigger_function = self.trigger_function

    @abstractmethod
    def build_layout(self):
        "Builds the layout for this element."

class EntityTile(_EntityLayout, elements.Tile):
    """
    Version of the Tile Element linked to an entity. For most options/configuration, see the Tile Element.
    The text and title Button are replaced with StateButtons, and hence the textProperties and titleProperties are set via here as well.
    state_styles can be defined via the appropriate property variable, or via the state_styles of the Tile itself.

    Parameters
    ----------
    entity : str
        entity_id to link this element to
    icon : Optional[str], optional
        Icon to use, by default None, which makes it take the icon set in Home Assistant
    tile_layout : Union[Literal[&quot;vertical&quot;, &quot;horizontal&quot;], str], optional
        Layout of the tile. Defaults to horizontal. See documentation of the Tile element for advanced usage.
    element_properties : dict, optional
        Properties for the elements within. By default, the icon is set to mirror the frontend icon, and the title is given the friendly_name attribute
    link_element : bool, optional
        links the subelements to the global entity settings set in the inkBoard config, by default False
        Cannot be changed later.
    """

    _restricted_element_properties : dict[str,set[str]] = {
        "icon": elements.Tile._restricted_element_properties["icon"] | {"entity"}, 
        "text": elements.Tile._restricted_element_properties["text"] | {"entity"}, 
        "title": elements.Tile._restricted_element_properties["title"] | {"entity"}, }
    "Properties of the elements that are not allowed to be set."

    @property
    def _emulator_icon(cls): return "mdi:layers-search"

    def __init__(self, entity : str, icon : Optional[str] = None, tile_layout : Union[Literal["vertical", "horizontal"], PSSMLayoutString] = "horizontal",
                element_properties : dict[str,dict[str,str]] = {"icon": {"icon_attribute": "icon"}, "text":{}, "title": {"entity_attribute": "friendly_name"}},
                link_element : bool = False,
                **kwargs):

        ##Due to updating, set it like this first
        self._entity = entity

        HAelement.__init__(self)

        iconElt = elements.Icon(icon=icon, entity=entity, icon_attribute=None, link_element=link_element)
        textState = StateButton(entity=entity, _register = False, link_element=link_element)
        titleState = StateButton(entity=entity, _register = False, link_element=link_element)
        # titleState._state = "friendly_name"

        if icon == None:
            # iconProperties.setdefault("icon_attribute", "icon")
            icon_defaults = {"icon_attribute": "icon"}
            iconElt._icon = None
            tile_icon = None
        else:
            icon_defaults = {}
            tile_icon = icon

        default_properties = {"icon": icon_defaults, "text":{}, "title": {"entity_attribute": "friendly_name", "suffix_attribute": None}}

        for elt in default_properties:
            set_props = element_properties.get(elt, {})
            default_properties[elt].update(set_props)

        element_properties = default_properties

        ##For properties: use setdefault in here as well (to set the attributes right away)
        elements.Tile.__init__(self, icon=tile_icon, text=None, tile_layout=tile_layout,
                                # iconProperties=iconProperties, textProperties=textProperties, titleProperties=titleProperties,
                        element_properties=element_properties,
                        _IconElement = iconElt, _TextElement = textState, _TitleElement = titleState, 
                        
                        ##Added these as kwargs to not directly set the properties
                        setIcon = True, setText = False, setTitle=False, 
                        **kwargs)
        

        self.entity = entity

        self._reparse_element_colors()
        self.vertical_sizes
        return

    ##For icons: use iconStateAttribute (for the attribute to follow) and icon_attribute --> set the latter in iconProperties

    #region
    @property
    def entity(self) -> str:
        "The entity_id of the entity associated with this element. Can be changed, but that will also mean the old entity is not linked anymore."
        return self._entity
    
    @entity.setter
    def entity(self, value):
        
        old_entity = getattr(self,"_entity",None)

        HAelement.entity.fset(self, value)

        if old_entity == getattr(self,"_entity",None):
            return

        nd = {"entity": self.entity}

        ##Be mindful there may be some delay in updating here
        self._IconElement.update(nd)
        self._TextElement.update(nd)
        self._TitleElement.update(nd)
        # self._Tile__IconElement.update(nd)
        # self._Tile__TextElement.update(nd)
        # self._Tile__TitleElement.update(nd)
        
    @property
    def icon(self):
        if (icon := self._IconElement.icon) != None:
            return icon
        
        elif icon := getattr(self._IconElement,"icon_attribute",None):
            return icon

        # return self._IconElement.icon

    @icon.setter
    def icon(self, value):
        if value == True:
            raise ValueError("Why is this true?")
        # elements.Tile.icon.fset(self, value)
        self._IconElement.update({"icon": value}, skipGen=self.isGenerating, skipPrint=self.isUpdating)
        i = self.icon
        return

    @property
    def text(self):
        # self._TextElement : StateButton
        return self._TextElement.state

    @text.setter
    def text(self, value):
        if value == None:
            pass
        elif not isinstance(value, str):
            value = str(value)

        ##I think it's good to allow for setting these directly? But it'll set the state of the element
        self._TextElement.update({"_state": value})

    @property
    def title(self):
        # self._TextElement : StateButton
        
        return self._TitleElement.state

    @title.setter
    def title(self, value):
        if value == None:
            pass
        elif not isinstance(value, str):
            value = str(value)

        ##I think it's good to allow for setting these directly? But it'll set the state of the element
        self._TitleElement.update({"_state": value})

    @property
    def _IconElement(self) -> Union[HAelement,elements.Icon]:
        return elements.Tile._IconElement.fget(self)

    @property
    def _TextElement(self) -> StateButton:
        return elements.Tile._TextElement.fget(self)
    
    @property
    def _TitleElement(self) -> StateButton:
        return elements.Tile._TitleElement.fget(self)
    #endregion

    def build_layout(self):
        ##This ensures _layoutstr is build again
        self.tile_layout = self.tile_layout
        # self.layout = self._parse_tile_layout(self._IconElement,self._TextElement, self._TitleElement)
        # self.layout = self._parse_tile_layout(None, icon=self.IconElement, text=self.TextElement, title=self.TitleElement)
        # return super().build_layout()

    async def trigger_function(self, element: triggers.HAelement, trigger_dict: "triggers.triggerDictType"):

        # self.build_layout()

        ##Don't forget to set the badge for unknown etc.
        # self.parentPSSMScreen.start_batch_writing()

        if trigger_dict["from_state"] == None:
            for elt  in [self._IconElement, self._TextElement, self._TitleElement]:
                if elt.HAclient == None: elt._HAclient = self._HAclient
            # self.build_layout()

        newAttributes = {}
        new_state = triggers.get_new_state(self,trigger_dict)

        if new_state not in self.state_styles:
            if new_state == "unknown":
                newAttributes["badge_icon"] = UNKNOWN_ICON #"gray4"
            elif new_state == "unavailable":
                newAttributes["badge_icon"] = UNAVAILABLE_ICON #"gray4"

            elif "else" in element.state_styles:
                new_state = "else"

        ##Should ensure the icon is removed once the unknown is resolved?
        ##Otherwise, add the icon the default maybe?

        newAttributes.setdefault("badge_icon",None)
        statedict = element.state_styles.get(new_state,False)

        if statedict:
            newAttributes.update(statedict)
        
        if newAttributes:
            # async with self._updateLock:
            await self.async_update(newAttributes, skipGen=True, skipPrint=True)

        async with self._updateLock:
            L = asyncio.gather(
                self._IconElement.trigger_function(self._IconElement, trigger_dict),
                self._TitleElement.trigger_function(self._TitleElement, trigger_dict),
                self._TextElement.trigger_function(self._TextElement, trigger_dict), 
                return_exceptions=True
            )
            await L
            for res in L:
                if isinstance(res,Exception):
                    logger.exception(res)
            
            # upd_elt = {}
            # for elt_name, elt in self.elements.items():
            #     upd_elt[elt_name] = elt.isUpdating
        # await self._IconElement.trigger_function(self._IconElement, trigger_dict)
        # await self._TitleElement.trigger_function(self._TitleElement, trigger_dict)
        # await self._TextElement.trigger_function(self._TextElement, trigger_dict)

        if trigger_dict["from_state"] == None:
            self.build_layout()
        
        # i = self.icon
        await self.async_update(updated=True)

        # self.parentPSSMScreen.stop_batch_writing()
        return
        # return super().trigger_function(element, trigger)

class PersonElement(EntityTile):
    """
    Element displaying where a person is (i.e. the state of a person entity). Takes all options except badge from the EntityTile.

    Parameters
    ----------
    entity : str
        entity_id of the person. Must be in the person domain.
    placeholder_icon : _type_, optional
        Icon to use as a placeholder, in case the entity_picture cannot be retrieved at the start, by default "mdi:account"
    element_properties : dict, optional
        properties for the sub elements, by default {"icon_attribute": "entity_picture", "icon_color": False}, which means the profile picture of this person is used.
    tile_layout : Union[Literal[&quot;vertical&quot;, &quot;horizontal&quot;], str], optional
        tile_layout, by default "vertical". See Tile documentation for advanced usage
    hide : list, optional
        specific tile parts to hide, by default {"text": True}, which means no text part (state) is shown.
        The idea of this element is to use the zone icons to display the state/location.
    zone_badges : Optional[dict], optional
        The badge icons used to depict which zones a person is in. By default {"default": None,"home": "mdi:home", "not_home": "mdi:home-off", "unavailable": UNAVAILABLE_ICON, "unknown": UNAVAILABLE_COLOR}. Any missing values at element init will be set to the default, if not explicitly set.
    """

    ALLOWED_DOMAINS = ["person"]
    
    defaultBadges = {"default": None,"home": "mdi:home", "not_home": "mdi:home-off", "unavailable": UNAVAILABLE_ICON, "unknown": UNAVAILABLE_ICON}
    
    @property
    def _emulator_icon(cls): return "mdi:card-account-details"

    def __init__(self, entity : str, placeholder_icon : mdiType = "mdi:account", element_properties : dict = {"icon": {"icon_attribute": "entity_picture", "icon_color": False, "backgroundShape": None, "background_color": None}},
                tile_layout : Union[Literal["vertical", "horizontal"], str] = "vertical", hide : elements.Tile._HideDict = {"text"},
                zone_badges: Optional[dict] = defaultBadges ,#{"default": None,"home": "mdi:home", "not_home": "mdi:home-off", "unavailable": UNAVAILABLE_ICON, "unknown": UNAVAILABLE_COLOR}, 
                 **kwargs):
        
        self._HAclient = None

        self.placeholder_icon = placeholder_icon

        self._entity_picture = placeholder_icon
        "link to the entity_picture. Initially set to the placeholder icon"

        defaultBadges = self.__class__.defaultBadges
        for state, badge in defaultBadges.items():
            zone_badges.setdefault(state,badge)
        
        self._zone_badges = zone_badges

        deficonProperties = {"icon_attribute": "entity_picture", "icon_color": False, "background_shape": None, "background_color": None}
        iconProperties = element_properties.get("icon", {})

        for prop, val in deficonProperties.items():
            iconProperties.setdefault(prop, val)
        element_properties["icon"] = iconProperties

        element_properties.setdefault("title",{})
        element_properties["title"].setdefault("entity_attribute","friendly_name")

        super().__init__(entity=entity, icon=placeholder_icon, tile_layout=tile_layout,
                        element_properties=element_properties, hide = hide, **kwargs)
                        #  tap_action=tap_action, show_feedback=show_feedback, **kwargs) #, trigger_function=self.trigger_function, entity=self.entity, tap_action=self.tap_action, show_feedback=self.show_feedback, isInverted=self.isInverted, background_color=self.background_color)

    @property
    def zone_badges(self) -> MappingProxyType:
        "Icons used to represent which zone the person is in (i.e. the state of the entity). Shown as a badge"
        return MappingProxyType(self._zone_badges)
    
    @zone_badges.setter
    def zone_badges(self, value : dict):
        value = value.copy()
        if not isinstance(value, dict):
            msg = f"zone_badges must be a dict with 'zone': 'icon'"
            logger.exception(TypeError(msg))
            return

        self._zone_badges.update(value)
        
    async def trigger_function(self, element, trigger_dict: triggers.triggerDictType):

        if trigger_dict["from_state"] == None:
            for elt  in [self._IconElement, self._TextElement, self._TitleElement]:
                if elt.HAclient == None: elt._HAclient = self._HAclient

        newAttributes = {}
        new_state = triggers.get_new_state(self,trigger_dict)

        badge_state = trigger_dict["to_state"]["state"]
        if new_state not in self.state_styles:
            if new_state == "unknown":
                pass
            elif new_state == "unavailable":
                pass

            elif "else" in element.state_styles:
                new_state = "else"

        ##Should ensure the icon is removed once the unknown is resolved?
        ##Otherwise, add the icon the default maybe?

        statedict = element.state_styles.get(new_state,False)

        if statedict:
            newAttributes.update(statedict)

        if badge_state in self.zone_badges:
            new_badge = self.zone_badges[badge_state]
        else:
            new_badge = self.zone_badges.get("default", None)
            if new_badge == None:
                if badge_state == "unknown": new_badge = UNKNOWN_ICON
                if badge_state == "unavailable": new_badge = UNAVAILABLE_ICON

        if "badge_icon" in newAttributes:
            logger.warning(f"zone_badges Overwrite badge_icons set in the state_styles. Set them via the zoneicons.")

        newAttributes["badge_icon"] = new_badge
        
        if newAttributes:
            await self.async_update(newAttributes, skipGen=True, skipPrint=True)

        L = asyncio.gather(
            self._IconElement.trigger_function(self._IconElement, trigger_dict),
            self._TitleElement.trigger_function(self._TitleElement, trigger_dict),
            self._TextElement.trigger_function(self._TextElement, trigger_dict),
        )
        await L
        return

class MediaPlayer(_EntityLayout):
    """
    A element to show the state of a media player. Highly configurable and stylable (In my opinion), but the default values should make it similar to the media player cards in the HA frontend.
    Any element properties passed (e.g. `info_title_properties` or `duration_slider_properties`) will only overwrite the keys passed, otherwise the default value is used. These also accepts the values `background` and `foreground` for color properties, which parses the appropriate color of the MediaPlayer to that property.
    Due to complexity,does not use the `_TileBase` class, so it may be rewritten in the future.
    
    Parameters
    ----------
    entity : str
        The entity to use with this element. Must be in domain media_player
    player_layout : Union[Literal[&quot;default&quot;],PSSMLayoutString], optional
        Layout of the media player. By default "default", which has seperate layout based on whether there is media playing or not.
        Otherwise, accepts tile layouts with elements `{"media_info", "controls", "duration", "artwork", "volume"}`
    show : Union[Literal[&quot;all&quot;],list[Literal[&quot;media_info&quot;, &quot;controls&quot;, &quot;duration&quot;, &quot;artwork&quot;,&quot;turn_off&quot;,&quot;volume&quot;]]], optional
        List with the elements to show in the layout, by default ["media_info", "controls", "duration", "artwork"]
        Elements not present here will be hidden. Set to 'all' to show all elements (if present in `player_layout`)
    foreground_color : Optional[ColorType], optional
        Color to use as foreground, which can be parsed in element colors using the `"foreground"` value. by default DEFAULT_FOREGROUND_COLOR
    accent_color : Optional[ColorType], optional
        Color to use as accent, which can be parsed in element colors using the `"accent"` value. by default DEFAULT_ACCENT_COLOR
    background_color : Optional[ColorType], optional
        Color to use as outline, which can be parsed in element colors using the `"background"` value. by default None
    outline_color : Optional[ColorType], optional
        Color to use as outline, which can be parsed in element colors using the `"outline"` value. by default None
    controls : Union[Literal[&quot;all&quot;],list[__control_options],dict], optional
        Either a list or a dict. When passing a list, default icons will be used.
        When using a dict, each control can be mapped to an icon, with some accepting the `state` value, which will change their icon based on the appropriate attribute.
        Defaults are `{"play-pause": "state", #"mdi:play-pause", "shuffle": "state", "repeat": "state", "mute": "state", "previous": "mdi:skip-previous", "next": "mdi:skip-next", "fast-forward": "mdi:fast-forward", "rewind": "mdi:rewind", "volume-up": "mdi:volume-high", "volume-down": "mdi:volume-medium"}`
        By default "all", which shows all icons (if present in `controls_layout`) with default icons.
    controls_layout : Union[Literal[&quot;default&quot;],PSSMLayoutString], optional
        Tile Layout string for the controls section, elements are build up using the values in `controls` above. 
        By default "default", which changes the shown buttons based on the media type that is playing.
    ff_time : Union[float,DurationType], optional
        Time to forward the media by when pressing the control button, by default 30 (seconds)
    rewind_time : Union[float,DurationType], optional
        Time to rewind the media by when pressing the control button, by default 30 (seconds)
    link_element : bool, optional
        Link the element to the entity config, by default False
        
    control_icon_properties : dict, optional
        Default settings to style the control icons. 
        By default  `{"icon_color": "foreground"}`. 
        Does not allow setting `{"tap_action"}`
    idle_picture : str | mdiType, optional
        mdi Icon or picture to use when no media is playing, by default "mdi:multimedia"
    artwork_properties : dict, optional
        properties for the artwork picture, by default `{}`. 
        Does not allow setting `{"picture", "picture_attribute", "entity", "fallback_icon", "link_element"}`
    duration_type : Literal[&quot;slider&quot;, &quot;text&quot;], optional
        How to show the duration, by default "slider", which shows a slider that progresses with the media. "Text" shows a button with the passed time and the maximum duration.
    duration_slider_properties : dict, optional
        Properties for the duration slider, by default `{"style":"box", "activeColor": "foreground"}`
        Does not allow setting `{"minimum", "maximum", "position", "tap_action", "count"}`
    duration_buttons_properties : dict, optional
        Properties for the duration buttons, by default `{}`.
        Does not allow setting `{"text"}`
    volume_icon : Union[Literal[&quot;state&quot;], mdiType], optional
        Icon to use for the icon next to the volume slider,
        By default 'state' (Depends on the media volume and whether it is muted.)

    volume_icon_properties : dict, optional
        Properties for the volume icon element, by default `{"icon_color": "foreground"}`
        Does not allow setting `{"icon", "tap_action"}`
    volume_slider_properties : dict, optional
        Properties for the volume slider, by default `{"style" : "box", "activeColor": "foreground", "outline_color": "foreground"}`
        Does not allow setting `{"entity","minimum", "maximum", "position", "tap_action"}`
    info_title_properties : dict, optional
        properties for the title StateButton, by default `{"font_color": "foreground", "attribute_styles": 'default_attribute_styles', "entity_attribute": "media_artist", "font": DEFAULT_FONT_HEADER,"fitText": True, "fontSize": 0}`
        default_attribute_styles sets the title to the entity's friendly name if the media_player is not playing.
        Does not allow setting `{"entity"}`
    info_text_properties : dict, optional
        properties for the text StateButton, by default `{"font_color": "foreground", "entity_attribute": "media_artist", "fitText": True, "fontSize": 0}`
        Does not allow setting `{"entity"}`
    """
    
    ALLOWED_DOMAINS = {"media_player"}
    TILES = {"media_info", "controls", "duration", "artwork", "volume"}

    @property
    def _emulator_icon(cls): return "mdi:video-image"

    #region
    class __Elements(TypedDict):
        "Elements that can be shown in the mediaplayer"
        
        artwork : bool
        "Artwork of the currently playing media. A placeholder can be set in case the media player is idle."

        media_info : bool
        "Two text elements with info about the currently playing media."

        duration : bool
        "A slider and optionally text displaying the (left over) time of the playing media"

        controls : bool
        "Various control buttons for the media player"

        volume : bool
        "A slider to control the volume of the media player"

        turn_off : bool
        "A button to turn off the media player"

    __control_options = Literal["play-pause", "shuffle", "mute", "repeat",
                                "previous", "next", "fast-forward", "rewind",
                                "volume-up", "volume-down"]
    "Available options for the controls"

    __DefaultControlIcons = MappingProxyType({
        ##Generally: Allow people to change this via settings. I think play-pause will be given a value of default, which will change depending on the state
        "play-pause": "state", #"mdi:play-pause",
        "shuffle": "state",
        "repeat": "state",
        "mute": "state",
        "previous": "mdi:skip-previous",
        "next": "mdi:skip-next",
        "fast-forward": "mdi:fast-forward",
        "rewind": "mdi:rewind",
        "volume-up": "mdi:volume-high",
        "volume-down": "mdi:volume-medium"
        })
    "Default icons for the controls"    

    @property
    def _emulator_icon(cls): return "mdi:motion-play"
    #endregion

    def __init__(self, entity : EntityType, player_layout : Union[Literal["default"],PSSMLayoutString] = "default", show : Union[Literal["all"],list[Literal["media_info", "controls", "duration", "artwork","turn_off","volume"]]] = ["media_info", "controls", "duration", "artwork"],
                foreground_color : Optional[ColorType]=DEFAULT_FOREGROUND_COLOR, accent_color : Optional[ColorType]=DEFAULT_ACCENT_COLOR, background_color : Optional[ColorType] =None, outline_color : Optional[ColorType] = None, #DEFAULT_BACKGROUND_COLOR, 
                controls : Union[Literal["all"],list[__control_options],dict] = "all", controls_layout : Union[Literal["default"],PSSMLayoutString] = "default", control_icon_properties : dict = {"icon_color": "foreground"},  ff_time : Union[float,DurationType] = 30, rewind_time : Union[float,DurationType] = 30, 
                idle_picture : Union[str,mdiType] = "mdi:multimedia", artwork_properties : dict = {},
                duration_type : Literal["slider", "text"] = "slider", duration_slider_properties : dict = {"style":"box", "activeColor": "foreground"}, duration_buttons_properties : dict = {"fitText": True, "fontSize": 0}, 
                volume_icon : Union[Literal["state"], mdiType] = 'state', volume_icon_properties : dict = {"icon_color": "foreground"}, volume_slider_properties : dict = {"style" : "box", "activeColor": "foreground", "outline_color": "foreground"}, 
                info_title_properties : dict = {"font_color": "foreground", "attribute_styles": 'default_attribute_styles', "entity_attribute": "media_artist", "font": DEFAULT_FONT_HEADER,"fitText": True, "fontSize": 0}, info_text_properties : dict = {"font_color": "foreground", "entity_attribute": "media_artist", "fitText": True, "fontSize": 0}, 
                off_icon_properties : dict = {"icon": "mdi:power","backgroundShape": "circle", "background_color": "foreground", "icon_color": "background"},
                link_element = False, **kwargs):            

        # validate_domain(self,entity)
        if "entity_attribute" in kwargs:
            logger.warning(f"Setting entity_attribute is not allowed for {self.__class__}")
            kwargs.pop("entity_attribute")

        # self.foreground_color = foreground_color

        self._color_setter("__foreground_color",foreground_color,False)
        self._color_setter("__background_color",background_color,True)
        self._color_setter("__outline_color",outline_color,True)
        self._color_setter("__accent_color",accent_color,True)
        # self.entity = entity
        self.entity = entity

        self._optimistic_trigger : dict = {}
        """
        If values are added in this dict, the next state update received will update the state and present attributes.
        Formed as `{'state': new_state, 'attributes': {'example_attribute': example}}`
        """

        self._HAclient = None
        
        self._layout = []

        ##Maybe add duration time?
        # show = ("media_info", "controls", "duration", "artwork", "volume")
        # show = ("media_info", "controls", "duration", "artwork","turn_off","volume")
        self.show = show

        self._mediaPosition = 0
        self._mediaDuration = -1
        self._updateTime = None
        self._media_updateTime = None

        self.__state = "idle"
        self.__mediaType = None

        ##I will require default values to be actively overwritten.
        ##So these can be called just after the init.
        self._idleIcon = None
        self.__artwork_properties = {}
        self.__artwork_properties.update(artwork_properties)
        
        self.__ArtworkElement = elements.Picture(picture=None,entity=self.entity, picture_attribute="entity_picture", link_element=False, fallback_icon=None)

        self.__off_icon_properties = {"icon": "mdi:power","backgroundShape": "circle", "background_color": "foreground", "icon_color": "background"}
        self.__off_icon_properties.update(off_icon_properties)
        self.__off_Icon = elements.Icon("mdi:power", tap_action = self._turn_off)

        self.__volume_slider_properties = {"style" : "box", "activeColor": "foreground", "outline_color": "foreground"}
        self.__volume_slider_properties.update(volume_slider_properties)
        self.__volume_icon_properties = {"icon_color": "foreground"}
        self.__volume_icon_properties.update(volume_icon_properties)

        self.volume_icon = volume_icon
        if volume_icon == 'state':
            volume_icon = "mdi:volume-high"
        self.__VolumeIcon = elements.Icon(icon=volume_icon, tap_action=self._mute)
        self.__VolumeSlider = elements.Slider(style=self.__volume_slider_properties["style"], minimum=0, maximum=1, position=0, width="h*0.5", tap_action=self._set_volume)

        
        self.__info_text_properties = {"font_color": "foreground", "entity_attribute": "media_artist", "fitText": True, "fontSize": 0}
        self.__info_text_properties.update(info_text_properties)

        # self.__info_title_properties = {"font_color": "foreground", "state_styles": state_styles, "state_conditionals": True}
        attribute_styles = [{"attribute": "media_title", 
                            "states": [{"state": "None", "properties": {"entity_attribute": "friendly_name"}}],
                            "else": {"entity_attribute": "media_title"}}]
        self.__info_title_properties = {"font_color": "foreground", "attribute_styles": attribute_styles, "entity_attribute": "media_artist", "font": DEFAULT_FONT_HEADER,"fitText": True, "fontSize": 0}
        self.__info_title_properties.update(info_title_properties)
        if self.__info_title_properties["attribute_styles"] == "default_attribute_styles":
            self.__info_title_properties["attribute_styles"] = attribute_styles


        self.__InfoText = StateButton(entity, link_element=False, entity_attribute="media_artist", fitText=True, fontSize=0)
        self.__InfoTitle = StateButton(entity, link_element=False, entity_attribute="media_title", font=DEFAULT_FONT_HEADER, fitText=True, fontSize=0)
        

        self.__duration_slider_properties = {"style" : "box", "activeColor": "foreground"}
        self.__duration_slider_properties.update(duration_slider_properties)

        self.__duration_buttons_properties = {"fitText": True, "fontSize": 0}
        self.__duration_buttons_properties.update(duration_buttons_properties)

        self.duration_type =  duration_type

        ##When implementing properties, don't forget to include some defaults like the colours
        self.__DurationSlider = elements.TimerSlider("up", self.__duration_slider_properties["style"], outline_color = None,
                                                    tap_action=self._seek_time, show_feedback=False, background=None, orientation="hor", width="h/4")
        self.__durationFuture : asyncio.Future = DummyTask()
        "Gather object for the duration runner"

        self.__durationTask : asyncio.Task = DummyTask()

        self.__TimeButton = elements.Button("--/--")
        self.__DurationButton = elements.Button("--/--")
        self.__DurationLock = asyncio.Lock()


        self.player_layout = player_layout

        # self.duration_type = duration_type if duration_type == "slider" else "timer"

        ##Or make this a stateTile?

        ##Also, give a default value for info attributes, which makes it change depending on music/other media type

        self.controls = controls
        self.controls_layout = controls_layout

        self.ff_time = ff_time
        self.rewind_time = rewind_time


        self.__control_icon_properties = {"icon_color": "foreground"}
        self.__control_icon_properties.update(control_icon_properties)
        self.__ControlIcons = {}
        control_actions = {
        ##Generally: Allow people to change this via settings. I think play-pause will be given a value of default, which will change depending on the state
        "play-pause": self._play_pause,
        "shuffle": self._shuffle,
        "repeat": self._repeat,
        "mute": self._mute,
        "previous": self._previous,
        "next": self._next,
        "fast-forward": self._fast_forward,
        "rewind": self._rewind,
        "volume-up": self._volume_up,
        "volume-down": self._volume_down
        }

        icons = {}
        for contr, icon in self.__class__.__DefaultControlIcons.items():
            ##Don't forget to apply the right controls and icon properties
            ##Eventually
            icons[contr] = elements.Icon(icon, tap_action = control_actions[contr])

        self.__ControlIcons : dict["MediaPlayer.__control_options", elements.Icon] = MappingProxyType(icons)
        self.__ControlLayoutElement = elements.Layout(layout=[["?"]],_updateTime=None)

        self.build_layout()

        #This should call the layout
        #Update it: call the layout update function after calling build layout again
        super().__init__(entity=entity, link_element=link_element, background_color=background_color, outline_color=outline_color, layout=self.layout, **kwargs)
        
        self.idle_picture = idle_picture
        self.__ArtworkElement.picture = self.idle_picture
        self.artwork_url = self.idle_picture
        ##Should be able to just call this if i'm not mistaken, since it shouldn't lead to errors before printing has started
        self.__reparse_element_colors()

        return
        # self.pssm_update = self.update
        # self.update = self.update_element

    #region [Media Player Properties]
    #region [General]
    @property
    def entity_attribute(self):
        "Attribute cannot be set for media players."
        return None

    @property
    def state(self) -> str:
        "The state of the media player element (Copied from the last received update of the media player entity)"
        return self.__state

    @property
    def mediaType(self) -> Literal[None, "music", "tvshow", "movie", "video", "episode", "channel", "playlist", "image", "url", "game", "app","podcast"]:
        "The type of media playing, as reported by Home Assistant"
        return self.__mediaType

    @property
    def mediaPosition(self):
        "Last media position as reported by Home Assistant"
        return self._mediaPosition
    
    @property
    def updateTime(self):
        "Last time the entiy was updated in Home Assistant"
        return  self._updateTime

    @property
    def media_updateTime(self):
        "Last time the media position was updated, as reported by Home Assistant"
        return self._media_updateTime

    @property
    def mediaDuration(self) -> float:
        "Duration of the media, in seconds. Returns -1 if no duration was present in the attributes."
        return self._mediaDuration

    @property
    def mediaActive(self) -> bool:
        "True if the media player is considered to be in an active state, i.e. playing, paused or buffering"
        return self.state in {"playing", "buffering","paused"}
    #endregion

    #region [Styling]
    @colorproperty
    def foreground_color(self) -> ColorType:
        "The main color to use for the icon and text. Can be overwritten by iconSettings and buttonSettings respectively."
        return self._foreground_color
    
    # @foreground_color.setter
    # def foreground_color(self, value):
    #     self._foreground_color : ColorType

    #     if value == self._foreground_color:
    #         return

    #     self._color_setter("_foreground_color",value,False)
    #     self.__reparse_element_colors()

    #     if self._idleIcon != None:
    #         self.idle_picture = self._idleIcon

        ##From here: Call the setters for the properties etc. such that the new values are parsed like
        ##self.setteryaya(self, self.buttonproperties) WHICH SHOULD still have the background/foreground values in there.

    @colorproperty
    def accent_color(self) -> ColorType:
        "The accent color to use. Can be used for the element colors by setting it's value to 'accent'."
        return self._accent_color
    
    # @accent_color.setter
    # def accent_color(self, value):
    #     self._accent_color : ColorType

    #     if value == self._accent_color:
    #         return

    #     self._color_setter("_accent_color",value,False)
    #     self.__reparse_element_colors()

    @colorproperty
    def background_color(self) ->  Union[ColorType,None]:
        return self._background_color

    # @background_color.setter
    # def background_color(self, value:  Union[ColorType,None]):
    #     if value == self._background_color:
    #         return
        
    #     self._color_setter("_background_color",value,True)
        
    #     self.__reparse_element_colors()

    @colorproperty
    def outline_color(self) ->  Union[ColorType,None]:
        return self._outline_color

    # @outline_color.setter
    # def outline_color(self, value:  Union[ColorType,None]):
    #     if value == self._outline_color:
    #         return
        
    #     self._color_setter("_outline_color",value,True)
        
    #     self.__reparse_element_colors()

    def _style_update(self, attribute: str, value):
        "Called when a style property is updated"
        if attribute in self.color_properties:
            self.__reparse_element_colors()

        if attribute == "foreground_color" and self._idleIcon != None:
            self.idle_picture = self._idleIcon

    def __reparse_element_colors(self):
        "Calls the setters for all property setters, use when setting e.g. foreground_color or background_color"

        cls = self.__class__
        cls.artwork_properties.fset(self,self.artwork_properties)
        cls.control_icon_properties.fset(self,self.control_icon_properties)
        cls.info_text_properties.fset(self,self.info_text_properties)
        cls.info_title_properties.fset(self,self.info_title_properties)
        cls.volume_slider_properties.fset(self,self.volume_slider_properties)
        cls.volume_icon_properties.fset(self,self.volume_icon_properties)
        cls.duration_buttons_properties.fset(self,self.duration_buttons_properties)
        cls.duration_slider_properties.fset(self,self.duration_slider_properties)
        cls.off_icon_properties.fset(self, self.off_icon_properties)

    @property
    def player_layout(self) -> Union[Literal["default"],PSSMLayoutString]:
        """
        Layout string to define the layout of the element.
        Default is `'[artwork,[[media_info,turn_off];controls;volume]];duration'` when media is playing, else `'[artwork,[media_info,turn_off]];None'` 
        """
        if self.__player_layout == "default":
            if self.state not in {"playing", "paused", "buffering"}:
                return "[artwork,[media_info,turn_off]];None"
            else:
                return "[artwork,[[media_info,turn_off];controls;volume]];duration"
        return self.__player_layout
    
    @player_layout.setter
    def player_layout(self, value : str):
        self.__player_layout = value

    @property
    def show(self) -> tuple[Literal["media_info", "controls", "duration", "artwork", "volume", "turn_off"]]:
        """
        Media player elements to show. 
        Can be set to all to show all elements, if present in the player_layout (So useful when working with custom layouts.)
        """
        return self._show
    
    @show.setter
    def show(self, value : Union[list, tuple]):
        if value == "all":
            value = list(self.__class__.__Elements.__required_keys__)
        else:
            value = list(value)
            for v in value:
                if v not in self.__class__.__Elements.__required_keys__:
                    value.remove(v)
        self._show = tuple(value)

    @property
    def hide(self) -> tuple[Literal["media_info", "controls", "duration", "artwork", "volume"]]:
        "Elements that will be hidden from the layout. Determined by the show parameter"
        return tuple(self.__class__.__Elements.__required_keys__ - set(self.show))
    #endregion

    #region [Controls]
    @property
    def controls(self) -> tuple[Literal["__control_options"]]:
        return self.__controls
    
    @controls.setter
    def controls(self, value):
        if value == "all":
            self.__controls = value
            self.__control_icon_map = dict(self.__class__.__DefaultControlIcons)
            return
        
        icons = {}

        ##I assume turning this into a dict will not alter the actual thing right?
        icon_vals = dict(self.__class__.__DefaultControlIcons)
        if isinstance(value, (list,tuple)):
            value = list(value)
        elif isinstance(value, dict):
            icon_vals.update(value.copy())
            value = list(value.keys())
        else:
            msg = f"controls must be either a list with options, or a dict with [options: icons]"
            logger.exception(TypeError(msg))
            return
        
        for cont in value:
            if cont in icon_vals and cont in self.__class__.__DefaultControlIcons:
                icons[cont] = icon_vals[cont]
            else:
                msg = f"{cont} is not a valid options for media player controls"
                logger.warning(msg)
                value.remove(cont)
        self.__controls = value
        self.__control_icon_map = icons

    @property
    def _control_icon_map(self) -> dict["__control_options",mdiType]:
        "Icons for various controls. Can be set by passing a dict to controls"
        return MappingProxyType(self.__control_icon_map)

    @property
    def ControlIcons(self) -> dict[str, elements.Icon]:
        "All the icons used for the control buttons"
        return MappingProxyType(self.__ControlIcons)

    @property
    def controls_layout(self) -> Union[Literal["default"],PSSMLayoutString]:
        """
        Layout string for the control buttons.
        default value is a row with control buttons, where the type of media playing determines which are shown.
        """
        if self.__controls_layout == "default":
            if self.state not in {"playing", "paused", "buffering"}:
                # return "play-pause"
                return "None"
            else:
                ##Default value. Layout updater automatically takes care of hiding.
                value = "mute,volume-down,volume-up,shuffle,previous,play-pause,next,repeat,rewind,fast-forward"
                if self.mediaType in {"music", "playlist"}:
                    value = "shuffle,repeat,None,previous,play-pause,next"
                elif self.mediaType in {"tvshow", "movie", "video","episode","podcast"}:
                    value = "rewind,fast-forward,None,previous,play-pause,next"
                return value

        return self.__controls_layout
    
    @controls_layout.setter
    def controls_layout(self, value):
        self.__controls_layout = value

    @property
    def control_icon_properties(self) -> dict:
        "Proprerties for _all_ the control icons. Setting this does _not_ remove previously set properties."
        return self.__control_icon_properties
    
    @control_icon_properties.setter
    def control_icon_properties(self, value : dict):
        # self.ArtworkElement.outline_color
        not_allow = {"icon", "tap_action"}

        for sett in filter(lambda sett: sett in value, not_allow):
            logger.warning(f"Mediaplayers do not allow setting {sett} in control icons")
            value.pop(sett)

        set_props = value.copy()
        # color_props = {"background_color", "outline_color", "icon_color"}
        color_props = elements.Icon.color_properties
        newprops = set(set_props.keys())
        for prop in color_props.intersection(newprops):
            if set_props[prop] == "foreground":
                set_props[prop] = self.foreground_color
            elif set_props[prop] == "background":
                set_props[prop] = self.background_color
            elif set_props[prop] == "outline":
                set_props[prop] = self.outline_color
            elif set_props[prop] == "accent":
                set_props[prop] = self.accent_color
        
        self.__control_icon_properties.update(value)

        for elt in self.ControlIcons.values():
            ##Maybe generating should not be skipped?
            # elt.update(set_props, skipGen=self.isUpdating, skipPrint=self.isUpdating)
            elt.update(set_props, skipPrint=self.isUpdating)

        # self.ArtworkElement.update(set_props, skipGen=self.isUpdating, skipPrint=self.isUpdating)

    @property
    def ff_time(self) -> float:
        "The time media is fast forwarded with when pressing the fast forward button"
        return self.__ff_time
    
    @ff_time.setter
    def ff_time(self, value : Union[int,float]):
        if isinstance(value,str):
            value = tools.parse_duration_string(value)
        self.__ff_time = float(value)

    @property
    def rewind_time(self) -> float:
        "The time media is fast forwarded with when pressing the fast forward button"
        return self.__rewind_time
    
    @rewind_time.setter
    def rewind_time(self, value : Union[int,float]):
        if isinstance(value,str):
            value = tools.parse_duration_string(value)
        self.__rewind_time = float(value)
    #endregion

    #region [Artwork]
    @property
    def idle_picture(self) -> Union[str,Image.Image]:
        return self._idle_picture
    
    @idle_picture.setter
    def idle_picture(self, value):
        if mdi.is_mdi(value):
            self._idleIcon = value
            img = Image.new("RGBA", (100,100),None)
            value = mdi.draw_mdi_icon(img, value, icon_size=60, icon_color=self.foreground_color)
        else:
            self._idleIcon = None

        self._idle_picture = value
        
        self.__ArtworkElement.update({"fallback_icon": value}, skipGen=self.mediaActive, skipPrint=self.isUpdating)

    @property
    def artwork_properties(self) -> dict:
        "Proprerties for the artwork. Setting this does _not_ remove previously set properties. Color properties can be set to `foreground` or `background` to use the respective media player's color"
        return self.__artwork_properties
    
    @artwork_properties.setter
    def artwork_properties(self, value : dict):
        # self.ArtworkElement.outline_color

        not_allow = {"picture", "picture_attribute", "entity", "fallback_icon", "link_element"}
        # self.ArtworkElement.

        for sett in filter(lambda sett: sett in value, not_allow):
            logger.warning(f"Mediaplayers do not allow setting {sett} in the artwork picture")
            value.pop(sett)

        set_props = value.copy()
        # color_props = {"background_color", "outline_color"}
        color_props = self.ArtworkElement.color_properties
        newprops = set(set_props.keys())
        for prop in color_props.intersection(newprops):
            if set_props[prop] == "foreground":
                set_props[prop] = self.foreground_color
            elif set_props[prop] == "background":
                set_props[prop] = self.background_color
            elif set_props[prop] == "outline":
                set_props[prop] = self.outline_color
            elif set_props[prop] == "accent":
                set_props[prop] = self.accent_color
        
        self.__artwork_properties.update(value)

        # self.ArtworkElement.update(set_props, skipGen=self.isUpdating, skipPrint=self.isUpdating)
        # for prop in color_props

    @property
    def ArtworkElement(self) -> elements.Picture:
        "Artwork of the currently playing media"
        return self.__ArtworkElement
    #endregion

    #region [Duration]
    @property
    def duration_type(self) -> Literal["slider", "text"]:
        "The way to display the duration. Use slider to show a slider progression and text, or text for just text."
        return self.__duration_type
    
    @duration_type.setter
    def duration_type(self, value: Literal["slider", "text"]):
        if value not in {"slider", "text"}:
            logger.exception(ValueError(f"duration_type must be one of 'slider' or 'text', {value} is not valid"))
            return
        self.__duration_type = value

    @property
    def duration_slider_properties(self) -> dict:
        "Properties to style the slider in the duration section"
        return self.__duration_slider_properties
    
    @duration_slider_properties.setter
    def duration_slider_properties(self, value):
        not_allow = {"minimum", "maximum", "position", "tap_action", "count"}

        for sett in filter(lambda sett: sett in value, not_allow):
            logger.warning(f"Mediaplayers do not allow setting {sett} in the duration slider")
            value.pop(sett)

        set_props = value.copy()
        # color_props = {"background_color", "outline_color", "activeColor", "color", "thumbColor", "thumbicon_color"}
        color_props = self.DurationSlider.color_properties
        newprops = set(set_props.keys())
        for prop in color_props.intersection(newprops):
            if set_props[prop] == "foreground":
                set_props[prop] = self.foreground_color
            elif set_props[prop] == "background":
                set_props[prop] = self.background_color
            elif set_props[prop] == "outline":
                set_props[prop] = self.outline_color
            elif set_props[prop] == "accent":
                set_props[prop] = self.accent_color
        
        self.__duration_slider_properties.update(value)
        self.DurationSlider.update(set_props, skipPrint=self.isUpdating)

    @property
    def duration_buttons_properties(self) -> dict:
        "Properties of the duration text (both total duration and passed play time). Allows parsing of color values"
        return self.__duration_buttons_properties
    
    @duration_buttons_properties.setter
    def duration_buttons_properties(self, value : dict):
        
        if "text" in value:
            logger.warning("Mediaplayers do not allow setting the duration text")
            value.pop("text")

        set_props = value.copy()
        # color_props = {"background_color", "outline_color", "font_color"}
        color_props = self.InfoTextElement.color_properties
        newprops = set(set_props.keys())
        for prop in color_props.intersection(newprops):
            if set_props[prop] == "foreground":
                set_props[prop] = self.foreground_color
            elif set_props[prop] == "background":
                set_props[prop] = self.background_color
            elif set_props[prop] == "outline":
                set_props[prop] = self.outline_color
            elif set_props[prop] == "accent":
                set_props[prop] = self.accent_color
        
        self.__duration_buttons_properties.update(value)

        self.TimeButton.update(set_props, skipPrint=self.isUpdating)
        self.DurationButton.update(set_props, skipPrint=self.isUpdating)

    @property
    def DurationSlider(self) -> elements.TimerSlider:
        "Slider used to display the elapsed time of the media"
        return self.__DurationSlider
    
    @property
    def TimeButton(self) -> elements.Button:
        "The button showing the elapsed media time."
        return self.__TimeButton
    
    @property
    def DurationButton(self) -> elements.Button:
        "The button showing the duration of the media"
        return self.__DurationButton
    
    def get_assumed_position(self) -> Optional[float]:
        "Returns the assumed current media position in seconds, or `None` if nothing is playing."
        if self.state not in {"playing", "paused", "buffering"}:
            return None
        
        if self.state in {"paused", "buffering"}:
            return self.mediaPosition

        cur_seconds = datetime.now(timezone.utc).timestamp() - self.media_updateTime.timestamp() + self.mediaPosition

        if cur_seconds > self.__DurationSlider.maximum:
            return self.__DurationSlider.maximum
        elif cur_seconds < 1/3:
            return 0
        else:
            return cur_seconds
    #endregion

    #region [Volume]
    @property
    def volume_icon(self) -> Union[Literal["state"],str,mdiType]:
        "Icon to use for the volume icon in the volume section. Use `'state'` to use the default icons set by the volume level."
        return self.__volume_icon

    @volume_icon.setter
    def volume_icon(self, value):
        if value == "state":
            self.__volume_icon = value
        else:
            elements.Icon._icon_setter(self,"__volume_icon", value, allow_none=True)
    
    @property
    def volume_icon_properties(self) -> dict:
        "Properties to style the icon in the volume section"
        return self.__volume_icon_properties
    
    @volume_icon_properties.setter
    def volume_icon_properties(self, value):
        not_allow = {"icon", "tap_action"}

        for sett in filter(lambda sett: sett in value, not_allow):
            logger.warning(f"Mediaplayers do not allow setting {sett} in the volume icon")
            value.pop(sett)

        set_props = value.copy()
        # color_props = {"background_color", "outline_color", "icon_color"}
        color_props = self.VolumeIconElement.color_properties
        newprops = set(set_props.keys())
        for prop in color_props.intersection(newprops):
            if set_props[prop] == "foreground":
                set_props[prop] = self.foreground_color
            elif set_props[prop] == "background":
                set_props[prop] = self.background_color
            elif set_props[prop] == "outline":
                set_props[prop] = self.outline_color
            elif set_props[prop] == "accent":
                set_props[prop] = self.accent_color
        
        self.__volume_icon_properties.update(value)
        self.VolumeIconElement.update(set_props, skipPrint=self.isUpdating)

    @property
    def volume_slider_properties(self) -> dict:
        "Properties to style the slider in the volume section"
        return self.__volume_slider_properties
    
    @volume_slider_properties.setter
    def volume_slider_properties(self, value):
        not_allow = {"entity", "minimum", "maximum", "position", "tap_action"}

        for sett in filter(lambda sett: sett in value, not_allow):
            logger.warning(f"Mediaplayers do not allow setting {sett} in the volume slider")
            value.pop(sett)

        set_props = value.copy()
        # color_props = {"background_color", "outline_color", "activeColor", "color", "thumbColor", "thumbicon_color"}
        color_props = self.VolumeSlider.color_properties
        newprops = set(set_props.keys())
        for prop in color_props.intersection(newprops):
            if set_props[prop] == "foreground":
                set_props[prop] = self.foreground_color
            elif set_props[prop] == "background":
                set_props[prop] = self.background_color
            elif set_props[prop] == "outline":
                set_props[prop] = self.outline_color
            elif set_props[prop] == "accent":
                set_props[prop] = self.accent_color
                
        self.__volume_slider_properties.update(value)
        self.VolumeSlider.update(set_props, skipPrint=self.isUpdating)

    @property
    def VolumeIconElement(self) -> elements.Icon:
        "The icon element in the volume section"
        return self.__VolumeIcon
    
    @property
    def VolumeSlider(self) -> elements.Slider:
        "The slider used to control the volume"
        return self.__VolumeSlider
    #endregion

    #region [Media Info]
    @property
    def info_text_properties(self) -> dict:
        "Properties of the text button. Allows parsing of color values"
        return self.__info_text_properties
    
    @info_text_properties.setter
    def info_text_properties(self, value : dict):
        
        if "entity" in value:
            logger.warning("Mediaplayers do not allow setting the media info entity")
            value.pop("entity")

        set_props = value.copy()
        # color_props = {"background_color", "outline_color", "font_color"}
        color_props = self.InfoTextElement.color_properties
        newprops = set(set_props.keys())
        for prop in color_props.intersection(newprops):
            if set_props[prop] == "foreground":
                set_props[prop] = self.foreground_color
            elif set_props[prop] == "background":
                set_props[prop] = self.background_color
            elif set_props[prop] == "outline":
                set_props[prop] = self.outline_color
            elif set_props[prop] == "accent":
                set_props[prop] = self.accent_color
        
        self.__info_text_properties.update(value)
        self.InfoTextElement.update(set_props, skipPrint=self.isUpdating)

    @property
    def info_title_properties(self) -> dict:
        "Properties of the text button. Allows parsing of color values"
        return self.__info_title_properties
    
    @info_title_properties.setter
    def info_title_properties(self, value : dict):
        
        if "entity" in value:
            logger.warning("Mediaplayers do not allow setting the media info entity")
            value.pop("entity")

        set_props = value.copy()
        # color_props = {"background_color", "outline_color", "font_color"}
        color_props = self.InfoTitleElement.color_properties
        newprops = set(set_props.keys())
        for prop in color_props.intersection(newprops):
            if set_props[prop] == "foreground":
                set_props[prop] = self.foreground_color
            elif set_props[prop] == "background":
                set_props[prop] = self.background_color
            elif set_props[prop] == "outline":
                set_props[prop] = self.outline_color
            elif set_props[prop] == "accent":
                set_props[prop] = self.accent_color
        
        self.__info_title_properties.update(value)
        self.InfoTitleElement.update(set_props, skipPrint=self.isUpdating)

    @property
    def InfoTextElement(self) -> StateButton:
        "The element in the text part of media info"
        return self.__InfoText
    
    @property
    def InfoTitleElement(self) -> StateButton:
        "The element in the title part of the media info"
        return self.__InfoTitle

    #endregion
    
    #region [Turn Off]
    @property
    def off_icon_properties(self) -> dict:
        "Properties to style the turn off icon "
        return self.__off_icon_properties
    
    @off_icon_properties.setter
    def off_icon_properties(self, value):
        not_allow = {"tap_action"}

        for sett in filter(lambda sett: sett in value, not_allow):
            logger.warning(f"Mediaplayers do not allow setting {sett} in the off Icon")
            value.pop(sett)

        set_props = value.copy()
        # color_props = {"background_color", "outline_color", "icon_color"}
        color_props = self.__off_Icon.color_properties
        newprops = set(set_props.keys())
        for prop in color_props.intersection(newprops):
            if set_props[prop] == "foreground":
                set_props[prop] = self.foreground_color
            elif set_props[prop] == "background":
                set_props[prop] = self.background_color
            elif set_props[prop] == "outline":
                set_props[prop] = self.outline_color
            elif set_props[prop] == "accent":
                set_props[prop] = self.accent_color
        
        self.__off_icon_properties.update(value)
        self.__off_Icon.update(set_props, skipPrint=self.isUpdating)

    #endregion
    
    #endregion

    #region [Layout getters]
    def get_MediaInfoElement(self) -> elements.Layout:
        layout  = [["?", (self.__InfoTitle, "?")],
                    ["?", (self.__InfoText, "?")]]
        return elements.Layout(layout, _register=False)

    def get_Artwork(self) -> elements.Picture:
        return self.__ArtworkElement

    def get_Volume(self) -> elements.Layout:
        layout = [["?", (self.__VolumeIcon, "r"), (self.__VolumeSlider,"?")]]
        return elements.Layout(layout, _register=False)

    def get_ControlButtons(self) -> elements.Layout:
        return self.__ControlLayoutElement
    
    def get_turn_off(self):
        "Returns the icon to turn the media player off"
        return self.__off_Icon

    def get_DurationElement(self) -> elements.Layout:
        "Layout Element that contains the duration elements (Slider and the text element(s))"
        ##Maybe allow this to be done using show/hide calls? not fully sure
        
        ##Allow this one to be made using it's own layout string

        if self.mediaDuration >= 3600:
            text_w = "w*0.2"
        else:
            text_w = "w*0.15"
        layout = [["?", (self.TimeButton, text_w),(self.DurationSlider, "?"), (self.DurationButton, text_w)]]
        return elements.Layout(layout, _register=False)
        # return self.__durationLayout
    #endregion

    def build_layout(self):

        builders = {"media_info" : self.get_MediaInfoElement,
                    "controls": self.get_ControlButtons,
                    "duration" : self.get_DurationElement,
                    "artwork" : self.get_Artwork,
                    "volume": self.get_Volume,
                    "turn_off": self.get_turn_off}
        media_elements = {}
        for elt in self.show:
            media_elements[elt] = builders[elt]()
        
        layout = elements.parse_layout_string(self.player_layout, 
                                vertical_sizes={"duration": "h*0.2", "controls": "h*0.3"}, 
                                horizontal_sizes={"artwork": "r","turn_off": "w*0.15"}, hide=self.hide,
                                **media_elements)

        self.layout = layout
        return
    
    async def trigger_function(self, element: triggers.HAelement, trigger_dict: triggers.triggerDictType):
        if trigger_dict["from_state"] == None:
            # self._updateTime = datetime.fromisoformat(trigger_dict['to_state']["last_updated"])
            for elt  in {self.__ArtworkElement, self.__InfoText, self.__InfoTitle}:
                if not isinstance(elt,HAelement):
                    HAelement.wrap_element(elt, self.HAclient)
                # if elt.HAclient == None: elt._HAclient = self._HAclient
        # else:
        #     ##Update time seems to be a bit more accurate like this.
        #     ##But doesn't work when starting since the media time is not correct then (misses the offset)
        #     # self._updateTime = datetime.now(timezone.utc)
        #     self._updateTime = datetime.fromisoformat(trigger_dict['to_state']["last_updated"])

        # datetime.strptime
        if self._optimistic_trigger:
            ##When interacting with i.e. the volume, a trigger is thrown but it may not be up to date entirely. So that update is skipped. Mainly determined by the call functions.
            trigger_dict = dict(trigger_dict)
            new_state = trigger_dict['to_state']
            if "state" in self._optimistic_trigger:
                new_state["state"] = self._optimistic_trigger["state"]

            if "attributes" in self._optimistic_trigger:
                new_state["attributes"].update(self._optimistic_trigger["attributes"])

            trigger_dict["to_state"] = new_state
            self._optimistic_trigger = {}

        new_state = trigger_dict['to_state'].copy()

        # new_media = False
        # if trigger_dict["from_state"] == None:
        #     new_media = True
        # elif trigger_dict["to_state"]["attributes"].get("media_title", None) != trigger_dict["from_state"]["attributes"].get("media_title", None):
        #     new_media = True

        hidden = self.hide

        element_state = triggers.get_new_state(self,trigger_dict)
        update_props = self.state_styles.get(element_state,{})
        attr_props = triggers.get_attribute_styles(self, trigger_dict)
        update_props.update(attr_props)

        cur_layout = self.player_layout
        
        self.__state = new_state["state"]
        self._mediaPosition = new_state["attributes"].get("mediaPosition", 0.0)
        self._mediaDuration = new_state["attributes"].get("mediaDuration", -1)
        self.__mediaType = new_state["attributes"].get("media_content_type", None)
        self._updateTime = datetime.fromisoformat(trigger_dict['to_state']["last_updated"])

        if update_props:
            # start_batch = True
            await self.async_update(update_props, skipGen=True, skipPrint=True)

        ##If playLayout is in update_props, the new layout should automatically be taken care off I believe
        if cur_layout != self.player_layout or self.hide != hidden:
            self.build_layout()

        update_coros = []
        
        if "mediaPosition_updated_at" in new_state["attributes"]:
            self._media_updateTime = datetime.fromisoformat(new_state['attributes']["mediaPosition_updated_at"])
        else:
            self._media_updateTime = self._updateTime

        if trigger_dict["from_state"] == None:
            start_batch = not self.parentPSSMScreen.isBatch
        elif trigger_dict["to_state"]["attributes"].get("media_title", None) != trigger_dict["from_state"]["attributes"].get("media_title", None):
            start_batch = True

        if "artwork" in self.show:
            # if new_state["state"] in {"playing","paused"}:
            if self.mediaActive:
                update_coros.append(triggers.picture_trigger(self.__ArtworkElement,trigger_dict))
            else:
                update_coros.append(self.ArtworkElement.async_update({"picture": self.idle_picture}))
                # new_pic = self.idle_picture

        if "media_info" in self.show:
            # pass
            update_coros.extend([
                self.__InfoText.trigger_function(None,trigger_dict),
                self.__InfoTitle.trigger_function(None,trigger_dict)])

        if "controls" in self.show:
            # pass
            update_coros.append(self.__update_controls(trigger_dict))

        if "duration" in self.show:
            asyncio.create_task(self.__duration_runner(trigger_dict))
            # if self.__durationTask.done() or new_state["state"] != "playing" or new_media:
            #     ##Something goes wrong when going from idle to not idle
            #     ##What I found is that the timebutton did not report being onScreen
            #     ##So gotta check how that is determined and why it was false. Maybe the layout was not updated?
            #     self.__durationTask = asyncio.create_task(self.__duration_runner(trigger_dict))

        if "volume" in self.show:
            update_coros.append(self.__update_volume(trigger_dict))


        ##Turn off button can be styled using the off_properties
        # if "turn_off" in self.show:
        #     pass

        ##Don't forget to test for layout to change, when going from idle to something else e.g.!
        ##And update accordingly.
        ##Also keep this in mind when starting the timer, as it may be required to start when it is added.

        L = await asyncio.gather(*update_coros, return_exceptions=True)
        for i, res in enumerate(L):
        # L = asyncio.as_completed(update_coros)
        # for coro in L:
        #     res = await coro
        
            if isinstance(res,Exception): 
                logger.error(f"{update_coros[i]} returned an exception: {res} ")

        if self.onScreen:
            if bool(update_coros) or update_props:
                updated = True
            else: updated = False

                ##I think the update slow done is in the artwork. -> Turns out it was running a batch update causing the issues.
                ##Also for some reason it seems to now update the entire thing in one go so well ¯\_(ツ)_/¯
                ##Probably a good moment to implement the generator lock when changing pictures :)
                ##Maybe also check if the buttons correctly updated
            await self.async_update(updated=updated)
            # self.parentPSSMScreen.stop_batch_writing()

        return
            ##I think it's best to set the text directly if it's not present?

    #region [Additional trigger functions]
    async def __duration_runner(self, trigger_dict : triggers.triggerDictType):
        """
        Handles state updates specifically for the duration elements.

        Parameters
        ----------
        trigger_dict : triggers.triggerDictType
            _description_
        """
        
        new_state = trigger_dict["to_state"]

        previous_ent_state = None
        
        # new_position = True
        if trigger_dict["from_state"] != None:
            previous_ent_state = trigger_dict["from_state"]["state"]

        if "mediaPosition_updated_at" in new_state["attributes"]:
            if previous_ent_state != None and new_state["attributes"]["mediaPosition_updated_at"] == trigger_dict["from_state"]["attributes"].get("mediaPosition_updated_at", None):
                new_position_update = False
            else:
                new_position_update = True
        else:
            new_position_update = False

        update_coros = []

        new_buffer = new_state["state"] in {"playing", "buffering"} and previous_ent_state == "playing"
        # if (not self.__durationFuture.done() and not (new_state["state"] == previous_ent_state == "playing")):
        #     self.__durationFuture.cancel()
        #     await asyncio.sleep(0)

        gather_cancel = False
        if (not self.__durationFuture.done() or new_position_update):
            self.__durationFuture.cancel()
            await asyncio.sleep(0)
            gather_cancel = True

        ##There seem to be some issues with the timer restarting even when paused?
        ##Well, no, it seems to go through a loop, and get cancelled and start again at the older position
        ##So maybe the paused doesn't work indeed.
        if new_state["state"] in {"playing","paused","buffering"} or new_position_update:
            if "mediaDuration" in new_state["attributes"]:
                duration_stamp = new_state["attributes"]["mediaDuration"]
                if duration_stamp != self.__DurationSlider.maximum :
                    self.__DurationSlider.maximum = duration_stamp
            else:
                duration_stamp = self.__DurationSlider.maximum
                # duration = datetime.utcfromtimestamp(duration_stamp)
            duration = datetime.fromtimestamp(duration_stamp,timezone.utc)
            timeformat = "%H:%M:%S" if duration_stamp >= 3600 else "%M:%S"
            durstr = duration.strftime(timeformat)

            # cur_seconds = datetime.now(timezone.utc).timestamp() - self.media_updateTime.timestamp() + self.mediaPosition
            cur_seconds = self.get_assumed_position()

            if durstr != self.DurationButton.text:
                update_coros.append(self.DurationButton.async_update({"text": durstr}))

            buffer_new_media = False
            if new_state["state"] == "buffering":
                # await asyncio.gather(*update_coros)
                if trigger_dict["from_state"] != None:
                    old_media_title = trigger_dict["from_state"]["attributes"].get("media_title",None)
                    new_media_title = trigger_dict["from_state"]["attributes"].get("media_title",None)
                    if new_media_title != None and new_media_title != old_media_title:
                        buffer_new_media = True
                # return

            if new_state["state"] == "playing" or new_buffer or buffer_new_media:
                # pass
                
                self.__DurationSlider.position = cur_seconds
                if self.onScreen: # and not self.__DurationSlider.running:
                    ##I believe it's cancelled by cancelling the future (which is ok), so the running check should not be necessary
                    # pass
                    self.__DurationSlider.pause_timer()
                    await asyncio.sleep(0)
                    update_coros.append(
                        self.__DurationSlider.await_timer(reset=False))
                
                if not self.__DurationLock.locked():
                    update_coros.append(
                            self.__durationtext_loop(duration_stamp,timeformat))
                
                # self.__DurationSlider.start_timer(reset=False)
                # update_coros.append(self.__DurationSlider._timerTask)
            # elif new_state["state"] in {"paused","buffering"}:
            else:
                logger.debug(f"{self}: pausing timer")
                if new_state["state"] == "paused":
                    self.__DurationSlider.pause_timer()

                # if self.__DurationSlider.position != self.mediaPosition:
                ##Don't need the if case since async_set_position returns anyways if the position already matches.
                update_coros.append(
                    self.__DurationSlider.async_set_position(cur_seconds))
                ##First acquire the lock here.
                posstr = datetime.fromtimestamp(cur_seconds, timezone.utc).strftime(timeformat)
                update_coros.append(
                        self.TimeButton.async_update({"text": posstr}, reprintOnTop=True))
        else:
            ##I don't think it's necessary to filter these out? Since the element's shouldn't update anyways if nothing changes.
            # if new_state["state"] == previous_ent_state:
            update_coros.append(self.DurationButton.async_update({"text": ""}))
            update_coros.append(self.TimeButton.async_update({"text": ""}))
            self.__DurationSlider.cancel_timer()
            

        try:
            logger.trace(f"Got media trigger, new state is {new_state['state']}. Elt is updating: {self.isUpdating}")
            if self.isUpdating:
                async with self._updateLock:
                    await asyncio.sleep(0)
            group = asyncio.gather(*update_coros, return_exceptions=True, loop=self.parentPSSMScreen.mainLoop) #@IgnoreException
            # group = asyncio.gather(*update_coros, return_exceptions=True, loop=self.parentPSSMScreen._printLoop) #@IgnoreException
            await asyncio.sleep(0)
            if not (new_state["state"] == previous_ent_state == "playing") or gather_cancel:
                self.__durationFuture = group
            
            await self.__durationFuture #@IgnoreExceptions
        except (asyncio.exceptions.CancelledError, asyncio.CancelledError):
            pass

    async def __durationtext_loop(self, total_seconds, timeformat):
        """
        loop that updates the duration text every second.

        Parameters
        ----------
        total_seconds : _type_
            Total amount of seconds of the media
        timeformat : _type_
            Timeformat of the text
        """
        async with self.__DurationLock:
            cur_seconds = self.mediaPosition
            while cur_seconds < total_seconds:      
                #cur_pos = datetime.utcnow().timestamp() - updateTime.timestamp() + position
                try:
                    cur_seconds = datetime.now(timezone.utc).timestamp() - self.media_updateTime.timestamp() + self.mediaPosition
                    #posstr = datetime.utcfromtimestamp(math.floor(cur_pos)).strftime(timeformat)
                    #new_text = f"{posstr}/{durstr}"
                    #sleep_time = update_func(cur_pos)
                    # update_func(cur_pos)

                    if cur_seconds > total_seconds:
                        continue

                    if cur_seconds < 1:
                        cur_seconds = 0

                    posstr = datetime.fromtimestamp(cur_seconds, timezone.utc).strftime(timeformat)

                    if self.duration_type == "text":
                        durstr = self.__DurationButton.text
                        posstr = f"{posstr}/{durstr}"

                    ##Why not on screen?
                    if  self.TimeButton.onScreen:
                        await self.TimeButton.async_update({"text": posstr}, reprintOnTop=True)
                        if not self.__DurationSlider.running:
                            self.__DurationSlider.position = cur_seconds
                            self.__DurationSlider.start_timer()
                        # self.TimeButton.update({"text": posstr}, reprintOnTop=True)
                    else:
                        self.TimeButton.text = posstr

                    # if not self.DurationSlider.running and self.DurationSlider.onScreen:
                    #     self.DurationSlider.set_position(cur_seconds)

                    sleep_time = math.ceil(cur_seconds) - cur_seconds
                    #logger.info(new_text)
                    # if cur_pos < duration_stamp:
                    #     self.durationElt.update({"text": new_text}, reprintOnTop=True)

                    await asyncio.sleep(sleep_time) #@IgnoreExceptions
                except asyncio.CancelledError:
                    logger.debug(f"{self}: Duration runner was cancelled") #@IgnoreExceptions
                    return
                
            cur_seconds = total_seconds
            posstr = datetime.fromtimestamp(cur_seconds, timezone.utc).strftime(timeformat)
            if  self.TimeButton.onScreen:
                self.TimeButton.update({"text": posstr}, reprintOnTop=True)
            else:
                self.TimeButton.text = posstr
        

        ##Using a lock to ensure only one lock is running at a time.
        # async with self.__DurationLock:
        #     asyncio.sleep(1)

    async def __update_controls(self, trigger_dict : triggers.triggerDictType):
        new_state = trigger_dict["to_state"]
        update_coros = []
        hide = []

        for contr, elt in self.__ControlIcons.items():
            elt : elements.Icon
            new_icon = self._control_icon_map.get(contr,None)
            if new_icon == "state":
                if contr == "play-pause":
                    if new_state["state"] == "playing": new_icon = "mdi:pause"
                    elif new_state["state"] == "paused": new_icon = "mdi:play"
                    elif new_state["state"] == "buffering": new_icon = elt.icon if elt.icon != 'state' else "mdi:play-pause"
                    else: new_icon = "mdi:play-pause"
                
                if contr == "mute":
                    s = new_state["attributes"].get("is_volume_muted", None)
                    if s == True: new_icon = "mdi:volume-off"
                    elif s == False: new_icon = "mdi:volume-source"
                    else: new_icon = None
                    

                if contr == "shuffle":
                    s = new_state["attributes"].get("shuffle", None)
                    # if s == None:
                    #     new_icon = None
                    if s == True: new_icon = "mdi:shuffle"
                    elif s == False: new_icon = "mdi:shuffle-disabled"
                    else: new_icon = None
                
                if contr == "repeat":
                    s = new_state["attributes"].get("repeat", None)

                    if s == "all": new_icon = "mdi:repeat"
                    elif s == "off": new_icon = "mdi:repeat-off"
                    elif s == "one": new_icon = "mdi:repeat-once"
                    else: new_icon = None

            if new_icon != None:
                update_coros.append(elt.async_update({"icon": new_icon}, skipPrint=True))
            else:
                hide.append(contr)

        # self.__ControlIcons
        # self.controls_layout = "default"

        # elts = bool(update_coros)

        await asyncio.gather(*update_coros)

        new_layout = elements.parse_layout_string(self.controls_layout,hide=hide,**self.__ControlIcons)
        # await self.__ControlLayout.Async_update({"layout": new_layout}, forceGen=bool(update_coros))
        
        if self.onScreen:
            await self.__ControlLayoutElement.async_update({"layout": new_layout}, updated=bool(update_coros))
            # b = self.parentPSSMScreen.isBatch
            # await self.__ControlLayout.Async_update({"layout": new_layout, "_updateTime": self._updateTime}, forceGen=True, skipPrint=False)
            # layout_img = self.__ControlLayout.imgData
        else:
            await self.__ControlLayoutElement.async_update({"layout": new_layout})
        return

    async def __update_volume(self, trigger_dict : triggers.triggerDictType):
        
        update_coros = []

        new_state = trigger_dict["to_state"]

        if new_state["state"] in {"playing","paused", "buffering"}:
            level = new_state["attributes"]["volume_level"]

            new_icon = self.__VolumeIcon.icon
            if self.volume_icon != "state":
                new_icon = self.volume_icon
            elif new_state["attributes"].get("is_volume_muted",False): # and new_state["attributes"]["is_volume_muted"]:
                    new_icon = "mdi:volume-mute"
            else:
                # if level == 0: new_icon = "mdi:volume-variant-off" 
                if level < 0.35: new_icon = "mdi:volume-low"
                elif level < 0.65: new_icon = "mdi:volume-medium"
                else: new_icon = "mdi:volume-high"
        else:
            level = 0
            # new_icon = self.__VolumeIcon.icon 
            # if self.volume_icon != "state":
            #     new_icon = self.volume_icon
            new_icon = "mdi:volume-variant-off" if self.volume_icon == "state" else self.volume_icon

        if new_icon != self.__VolumeIcon.icon:
            update_coros.append(self.__VolumeIcon.async_update({"icon": new_icon}))
        
        update_coros.append(self.__VolumeSlider.async_set_position(level))

        await asyncio.gather(*update_coros)

        return
    #endregion

    def on_add(self):
        super().on_add()

        if self.HAclient != None and self.HAclient.connection:
            entity_state = self.HAclient.stateDict[self.entity]
            if entity_state["state"] in {"playing", "paused"}:
                self.parentPSSMScreen.mainLoop.create_task(self.__duration_runner({"to_state" : entity_state, "from_state": None}))

    #region [service action functions]
    def _set_optimistic_trigger(self, state=None, attributes = {}):
        "Quick hand function to set the optimistic trigger"

        if state != None:
            self._optimistic_trigger["state"] = state

        if attributes:
            if "attributes" in self._optimistic_trigger:
                self._optimistic_trigger["attributes"].update(attributes)
            else:
                self._optimistic_trigger["attributes"] = attributes

    def _seek_time(self, *args, new_position : float = None):
        "Seeks to the provided time set by the interaction with the slider. Uses the position of the duration slider if new_position is None."
        if new_position == None:
            new_position = self.__DurationSlider.position

        isotime = datetime.now(timezone.utc).isoformat()
        optmdict = {"mediaPosition": new_position, "mediaPosition_updated_at": isotime}
        if "attributes" in self._optimistic_trigger:
            self._optimistic_trigger["attributes"].update(optmdict)
        else:
            self._optimistic_trigger["attributes"] = optmdict

        self.HAclient.call_service(service="media_player.media_seek", target=self.entity, service_data={"seek_position": new_position})
    
    def _set_volume(self, *args, new_volume : float = None):
        "Sets the volume of the media player. Uses the volume of the slider if new_volume is None."
        if new_volume == None:
            new_volume = self.__VolumeSlider.position

        # if self.__VolumeSlider in args:
        if "attributes" in self._optimistic_trigger:
            self._optimistic_trigger["attributes"].update({"volume_level": new_volume})
        else:
            self._optimistic_trigger["attributes"] = {"volume_level": new_volume}

        self.HAclient.call_service(service="media_player.volume_set", target=self.entity, service_data={"volume_level": new_volume})
    
    def _play_pause(self, *args, action : Literal["play","pause"] = None):
        "Toggles the state of the media player if action is not set. Otherwise does action"
        if self.state not in {"playing","buffering","paused"}:
            return
        
        if action == "play": 
            service_action = "media_play"
            self._optimistic_trigger["state"] = "playing"
        elif action == "pause":
            service_action = "media_pause"
            self._optimistic_trigger["state"] = "paused"
            self.DurationSlider.pause_timer()
        else:
            service_action = "media_play_pause"
            if self.state in {"playing","buffering"}:
                self._optimistic_trigger["state"] = "paused"
                self.DurationSlider.pause_timer()
            else:
                self._optimistic_trigger["state"] = "playing"
        
        self.HAclient.call_service(service=f"media_player.{service_action}", target=self.entity)
        
    def _shuffle(self, *args, shuffle : bool = None):
        """
        Changes the shuffle setting of the media player.

        Parameters
        ----------
        shuffle : bool, optional
            The shuffle setting to set, by default None, which means it'll pick the opposite from the currently known shuffle state of the entity.
        """
        ent_state = self.HAclient.stateDict[self.entity]

        if "shuffle" not in ent_state["attributes"]:
            return

        if shuffle == None:
            shuffle = not ent_state["attributes"].get("shuffle")
        
        service_data = {"shuffle": shuffle}
        self._set_optimistic_trigger(attributes=service_data)
        self.HAclient.call_service(service=f"media_player.shuffle_set", target=self.entity, service_data=service_data)

    def _repeat(self, *args, repeat : Literal['off','all', 'one'] = None):
        """
        Changes the repeat setting of the media player.

        Parameters
        ----------
        repeat : Literal[&#39;off&#39;,&#39;all&#39;, &#39;one&#39;], optional
            The repeat setting to set, by default None, which means it'll cycle from the currently known state of the entity.
        """
        ent_state = self.HAclient.stateDict[self.entity]

        if "repeat" not in ent_state["attributes"]:
            return
        
        if repeat == None:
            cur_rep = ent_state["attributes"]["repeat"]
            ops = ['off','all', 'one']

            idx = ops.index(cur_rep) + 1
            if idx >= len(ops): idx = 0

            repeat = ops[idx]

        service_data = {"repeat": repeat}
        self._set_optimistic_trigger(attributes=service_data)
        self.HAclient.call_service(service=f"media_player.repeat_set", target=self.entity, service_data=service_data)

    def _mute(self, *args):
        "Mutes the media player's volume. Sets it to 0 if it is not supported."
        if self.state not in {"playing","buffering","paused"}:
            return
        
        ent_state = self.HAclient.stateDict[self.entity]

        if "is_volume_muted" not in ent_state["attributes"]:
            service_action = "set_volume"
            service_data = {"volume_level": 0}
        else:
            service_action = "volume_mute"
            service_data = {"is_volume_muted": not ent_state["attributes"]["is_volume_muted"]}

        self._set_optimistic_trigger(attributes=service_data)
        self.HAclient.call_service(service=f"media_player.{service_action}", target=self.entity, service_data=service_data)

    def _previous(self, *args):
        "Requests to play the previous media track"
        self.HAclient.call_service(service=f"media_player.media_previous_track", target=self.entity)

    def _next(self, *args):
        "Requests to play the next media track"
        self.HAclient.call_service(service=f"media_player.media_next_track", target=self.entity)
    
    def _fast_forward(self, *args):
        """
        Forwards the playing media by `time` seconds. Uses the set ff_time if time is None.

        Parameters
        ----------
        time : float, optional
            Time to forward by, by default None
        """        
        if cur_pos := self.get_assumed_position():
            new_pos = cur_pos + self.ff_time
            if new_pos > self.mediaDuration:
                new_pos = self.mediaDuration
            self._seek_time(new_position=new_pos)
    
    def _rewind(self, *args, time : float = None):
        """
        Rewinds the playing media by `time` seconds. Uses the set rewind_time if time is None.

        Parameters
        ----------
        time : float, optional
            Time to rewind by, by default None
        """
        if cur_pos := self.get_assumed_position():
            if time == None:
                time = self.rewind_time
            new_pos = cur_pos - time
            if new_pos < 0:
                new_pos = 0
            self._seek_time(new_position=new_pos)
    
    def _volume_up(self, *args):
        "Turns up the media player volume"
        self.HAclient.call_service(service=f"media_player.volume_up", target=self.entity)

    def _volume_down(self, *args):
        "Turns down the media player volume"
        self.HAclient.call_service(service=f"media_player.volume_down", target=self.entity)

    def _turn_off(self, *args):
        "Turns off the media player, or (tries to) turn it on if it's state reports off."
        # if self.state == "off":
        #     service_action = "turn_on"
        # else:
        #     service_action = "turn_off"
        service_action = "toggle"

        self.HAclient.call_service(service=f"media_player.{service_action}", target=self.entity)
    #endregion


### Weather Elements ###

##Maybe also add a special weather tile? Which simply shows the icon and two attributes

class WeatherElement(_EntityLayout, base._TileBase):# (elements.Layout):
    """
    A Weather Element. Opens a forecast popup on click (if tap_action is not specified) with a forecast from the entity. \n
    Elements are 'condition' (The condition icon), 'title' (A statebutton which by default shows the friendly name, but is also hidden by default) and 'weather-data', which is the tile_layout holding all the weather_data
    Otherwise accepts all TileLayout arguments.

    Elements
    ----------
    condition : `base.Icon`
        Icon element, that shows the condition icon. the icon cannot be set directly
    title : `StateButton`
        StateButton element, can show any data of the entity. Defaults the the friendly_name, but is also hidden by default
    weather-data : `base.TileLayout`
        A TileLayout that holds more TileLayouts for each attribute in weather_data. Element_properties can be set, however that requires setting one for each weather_data entry. Use this element's weather_data_properties to give each tile the same styling. By default, the icon and text button in here will be given this element's foreground_color.
    forecast : `ForecastElement`
        The element with the forecast data. Typically, this is used as a popup (when the `tap_action` is `"show-forecast"`), but it can be used as an element in the tile layout
        Putting it in the tile_layout and also using it in the popup could lead to weird behaviour, though it didn't seem to when I was testing (which was not what I expected)
        Styling is done via `element_properties['forecast']` regardless of whether it is used as a popup or an element in the tile_layout.
        
    Parameters
    ----------
    entity : str
        The Weather entity to connect to this element
    condition_icons : Union[Literal[&quot;mdi&quot;,&quot;meteocons&quot;,&quot;meteocons, optional
        Dict with icons to match the conditions. Icons can be mapped to conditions using the keys 'day' and 'night' with a dict corresponding to conditions. A default icon can be set using 'default', and a standard prefix and suffix for each icon can be set using the keys 'prefix' and 'suffix' respectively. 
        Shorthand values for already defined icon packs are "mdi" (for mdi icons), "meteocons" and "meteocons-outline" (which uses the meteocons pack found here: https://github.com/basmilius/weather-icons)
    weather_data : list[WeatherData,Literal[&#39;friendly_name&#39;],str], optional
        List of weather data to show. Maps to the entities attributes, and automatically tries to find the correct unit, by default ['temperature']
    weather_data_icons : Union[Literal[&quot;mdi&quot;,&quot;meteocons&quot;,&quot;meteocons, optional
        Icons to corresponds to the items in `weather_data`, a defaults key will use one of the default icon packs (mdi, meteocons or meteocons-outline), with values in the dict overwriting them.
        A 'prefix' and 'suffix' key can be set too, for a standard prefix/suffix for each icon value.
        Same as `condition_icons`, accepts string values 'mdi', 'meteocons' and 'meteocons-outline' for default icon packs. 
        By default "mdi"
    time_format : str
        datetime format string to convert datetimes to human readable strings. Only for forecasts as the entity itself lacks the appropriate attribute.
    element_properties : dict, optional
        Properties of the tile elements, 
        defaults set icon_color for the condition element, 
        font_color, fitText and fontSize for the title element, 
        and weather-data has all color properties set accordingly as well as the vertical sizes of the outer margins (to center the data rows no matter how many are set)
        for forecasts, the entity and time_format are copied by default as well as the foreground, accent and background colors
    weather_data_properties : dict, optional
        Properties for _all_ tile elements in the weather-data tile., by default {}
    tile_layout : Union[Literal[&quot;vertical&quot;,&quot;horizontal&quot;],PSSMLayoutString], optional
        Layout string for the WeatherElement. Shorthands are 'vertical' and 'horizontal', by default "vertical"
    weather_data_layout : Union[Literal[&quot;default&quot;],PSSMLayoutString], optional
        Layout string for the weather-data tile, by default "default", which stacks all values in `weather_data` vertically. 
        Otherwise, a custom layout is possible, but you will need to define each value from `weather_data` yourself (any value missing in the layout string will not be shown).
    hide : list[Literal[&quot;condition&quot;,&quot;title&quot;,&quot;weather, optional
        List of elements to hide from the main Tile, by default ["title"]
    """

    ALLOWED_DOMAINS = ["weather"]
    
    _default_layouts : dict = {"vertical": "[condition,title];weather-data", "horizontal": "[condition;title],weather-data"}

    _resricted_properties = {"icon": {"icon"},"title": {"entity"}, "forecast": {"updateInterval", "updateEvery"}} ##Technically, element_properties can be used here to set stuff but is not quite supposed to.    "Properties not allowed to be set in element_properties. Not in use, preferably use `_restricted_element_properties`"

    @classmethod
    @property
    def action_shorthands(cls) -> dict[str,Callable[["base.Element", CoordType],Any]]:
        "Shorthand values mapping to element specific functions. Use by setting the function string as element:{function}"
        # return {"show-forecast": "async_show_forecast"}.update(_EntityLayout.action_shorthands)
        return _EntityLayout.action_shorthands | {"show-forecast": "async_show_forecast"}
        ##Add show-forecast later on as function

    @property
    def _emulator_icon(cls): return "mdi:cloud-circle"

    def __init__(self, entity : str, condition_icons : Union[Literal["mdi","meteocons","meteocons-outline"],dict] = "mdi",
                weather_data : list[WeatherData,Literal['friendly_name'],str] = ['temperature'], weather_data_icons : Union[Literal["mdi","meteocons","meteocons-outline"],dict[WeatherData,Union[mdiType,str]]] = "mdi", 
                time_format : str = "%A",
                element_properties : dict = {"condition": {}, "title": {}, "weather-data": {}}, weather_data_properties : dict = {},
                tile_layout : Union[Literal["vertical","horizontal"],PSSMLayoutString] = "vertical", weather_data_layout : Union[Literal["default"],PSSMLayoutString] = "default",
                hide : list[Literal["condition","title","weather-data"]] = ["title"],
                ##HAclient : HAclient = None, cannot import HAclient as it leads to circular imports :( -> maybe possible to import the class tho?
                tap_action : InteractionFunctionType = "show-forecast",
                forecast_update : Union[Literal["on-trigger", "on-open", "hour"], DurationType] = "on-open",
                popup_properties : dict = {}, _isForecast : bool = False, **kwargs):
        """
        tap_action : InteractionFunctionType, optional
            _description_, by default "show-forecast"
        forecast_update : Union[Literal[&quot;on, optional
            _description_, by default "on-open"
        popup_properties : dict, optional
            _description_, by default {}
        _isForecast : bool, optional
            _description_, by default False
        """        

        

        # validate_domain(self,entity)
        # if entity.split(".")[0] not in self.ALLOWED_DOMAINS:
        #     logger.error(f"Please supply an entity in the weather domain. {entity} is not a valid entity for a weather element")
        #     return Exception("Entity Domain Error")

        ##Build the icons and buttons for this when fetching data, and add them to attribute elements or something.
        ##Also, for the layout: have icon;title;weather-data
        # allow for a title?/titleattribute
        # Coloring: somehow apply a data-icon-color?
        # Cause I want the attributes for the forecast buttons to be able to be set via a single attribute, not one for each button
        # And same for icons, butttt that means it's probably gotta loop?
        # Maybe in the layout maker, make a list with the icons/buttons
        # condition_icons = "meteocons-outline"

        self.entity = entity
        self.__isForecast = _isForecast
        
        self.__weather_data_layout = "default"
        
        self.__condition = None
        self.__weather_data = []
        self.__weather_data_icons = {}
        self.__weather_data_properties = {}
        self.__weather_data_Tile = base.TileLayout("None", {})

        self.time_format = time_format

        ##This button should become a state button
        # weatherButton = elements.Button("Temp", fontSize = "0.8*h", text_xPosition = 'center' ,text_yPosition = "bottom", outline_color="white", attribute="temperature", show_unit = " °C", fitText=False )
        # weatherButton = elements.Button("Temp")
        weatherButton = StateButton(self.entity, "friendly_name", _register = False)
        weatherIcon = elements.Icon("mdi:weather-fog")

        if isinstance(weather_data_icons,dict):
            weather_data_icons.setdefault("defaults","mdi")



        self.weather_data_layout = weather_data_layout

        ##Give conditionIcon it's own setter or something
        ##And for the forecasts -> icons and buttons.
        ##Attributes automatically try and look for the correct unit (give auto temperature unit if temperature in attribute name)
        ##Also check how I build it in  the function above

        # self.color = color
        # self.background_color = background_color


        if "tap_action" not in kwargs:
            logger.debug("Weather element has get_forecast")
            tap_action = self.async_show_forecast
            
            s = WeatherElement.tap_action.fset


            #self.response_function = self.build_forecast_popup
        else:
            tap_action = kwargs.pop("tap_action")
            # self.response_function = None if "response_function" not in kwargs else kwargs["response_function"]

        self.__elements = {"condition": weatherIcon, "title": weatherButton, "weather-data": self.__weather_data_Tile}

        self._condition_prefix = None
        self._condition_suffix = None
        self.condition_icons = condition_icons

        self.weather_data = weather_data
        self.weather_data_icons = weather_data_icons

        # tile_layout = "horizontal"
        t = tap_action
        data_vSize = {}
        if tile_layout == "vertical":
            # vertical_sizes = kwargs.pop("vertical_sizes",{"condition": "?", "title": "?", "weather-data": "?*2"})
            vertical_sizes = {"condition": "?", "title": "?", "weather-data": "?*2"}
            horizontal_sizes = {"condition": "r", "outer": "?", "weather-data": "w*0.8"}
            # horizontal_sizes = kwargs.pop("horizontal_sizes",{"condition": "r", "outer": "?", "weather-data": "w"})
            data_vSize = {"outer": "?"}
        elif tile_layout == "horizontal":
            vertical_sizes = kwargs.pop("vertical_sizes",{"condition": "?", "title": "?*2", "weather-data": "?"})
            horizontal_sizes = kwargs.pop("horizontal_sizes",{"weather-data": "?*2"})
            data_vSize = {"outer": "?"}
        else:
            vertical_sizes = kwargs.pop("vertical_sizes",{})
            horizontal_sizes = kwargs.pop("horizontal_sizes",{})

        default_condition_properties = {"icon_color": "foreground"} if condition_icons in {"mdi","meteocons-outline"} else {"icon_color": False}
        default_title_properties = {"font_color": "foreground", "fitText": True, "fontSize": 0}
        default_data_properties = {"foreground_color": "foreground", "accent_color": "accent",
                                "vertical_sizes": data_vSize}

        # if vertical_sizes in kwargs:
        vertical_sizes.update(kwargs.pop("vertical_sizes",{}))
        horizontal_sizes.update(kwargs.pop("horizontal_sizes",{}))

        set_element_properties = {"condition": default_condition_properties, "title": default_title_properties, "weather-data": default_data_properties}

        for elt, props in set_element_properties.items():
            if elt in element_properties:
                props.update(element_properties[elt])

        if not self._isForecast:
            forecast_properties = element_properties.get("forecast",{})
            forecast_properties.setdefault("entity",self.entity)
            forecast_properties.setdefault("time_format",self.time_format)
            forecast_properties.setdefault("foreground_color",'foreground')
            forecast_properties.setdefault("accent_color",'accent')
            forecast_properties.setdefault("background_color",None)
            # forecast_properties.setdefault("outline_color",'outline')
            

            w_props : dict = forecast_properties.get("element_properties",{})
            w_props.setdefault("condition_icons", condition_icons)
            w_props.setdefault("weather_data_icons", weather_data_icons)
            forecast_properties["element_properties"] = w_props

            self.__ForecastElement = WeatherForecast(forecast_properties["entity"])
            self.__ForecastPopup = base.Popup([["?", (self.__ForecastElement,"?")]])
            self.__elements["forecast"] = self.__ForecastElement
            set_element_properties["forecast"] = forecast_properties

            self.forecast_update = forecast_update
            self.popup_properties = popup_properties

        elif "forecast" in element_properties:
            logger.warning(f"{self}: the forecast element is unavailable for WeatherElements used in a ForecastElement")
            set_element_properties.pop("forecast",None)
            element_properties.pop("forecast")
            
        
        HAelement.__init__(self)
        t = tap_action
        base._TileBase.__init__(self, tile_layout, hide=hide,
                                vertical_sizes=vertical_sizes,  horizontal_sizes=horizontal_sizes,
                                element_properties=set_element_properties, tap_action=tap_action, **kwargs)

        if not self._isForecast:
            self.element_properties
        ##Data properties should work ok like this?
        ##I.e. element_properties are already set in the tilebase init.
        ##Which should take care of the properties of the main data tile
        
        if weather_data_icons in {"mdi", "meteocons-outline"}:
            icon_data_color = "foreground"
        else:
            icon_data_color = False
        default_data_properties = {"foreground_color": "foreground", "accent_color": "accent", "background_color": None, "outline_color": None,
                                "element_properties": {"icon": {"icon_color": icon_data_color}, "data": {"font_color": "foreground"}}}
        ##This one should allow having foreground etc. set
        
        if "element_properties" in weather_data_properties:
            icon_settings = weather_data_properties[element_properties].get("icon", {})
            data_settings = weather_data_properties[element_properties].get("data", {})
            weather_data_properties.pop("element_properties")
            default_data_properties["element_properties"]["icon"].update(icon_settings)
            default_data_properties["element_properties"]["data"].update(data_settings)
        
        default_data_properties.update(weather_data_properties)
        self.weather_data_properties = default_data_properties

        self._rebuild_layout = True
        "Set this to rebuild the layout the next time the generator is called."

        # self.tap_action = self.show_forecast_popup
        


        return

    #region
    # @base.Element.tap_action.getter

    @property
    def _isForecast(self) -> bool:
        "True if this WeatherElement is part of a forecast element (To prevent recursion issues)"
        return self.__isForecast

    @property
    def elements(self)-> MappingProxyType[Literal["condition","title","weather-data"],base.Element]:
        return MappingProxyType(self.__elements)

    @property
    def condition_icons(self) -> dict:
        """
        Icons that are used for weather conditions. Shorthand values for predefined sets are "mdi","meteocons","meteocons-outline".
        A custom dict is made up of the following keys:
            "default": specifies the default icon to use, if it cannot be found in the set of day time icons
            "day": icons to use during daytime (i.e. when the state of the sun.sun entity is not 'below_horizon')
            "night": icons to use during nighttime (when sun.sun state is 'below_horizon'). If the condition is not present in the night time icons, the daytime icon is used as a fallback, or default if it is not in there either.
            "suffix": optional suffix to append to all the icon values
            "prefix": optional prefix to append to all the icon values
        """        
        return self._condition_icons
    
    @condition_icons.setter
    def condition_icons(self, value : Union[dict,Literal["mdi","meteocons","meteocons-outline"]]):
        if isinstance(value,str) and value in {"mdi","meteocons","meteocons-outline"}:
            if value == "mdi":
                self._condition_prefix = "mdi:weather-"
                self._condition_suffix = None
                self._condition_icons = icon_sets.MDI_WEATHER_CONDITION_ICONS
            else:
                self._condition_icons = icon_sets.METEOCONS_WEATHER_CONDITIONS_ICONS
                self._condition_suffix = ".png"
                self._condition_prefix = icon_sets.METEOCONS_PATH if value == "meteocons" else icon_sets.METEOCONS_PATH_OUTLINE
        elif isinstance(value, dict):
            d = value.copy()
            self._condition_suffix = d.pop("suffix",None)
            self._condition_prefix = d.pop("prefix",None)
            self._condition_icons = d
        else:
            msg = f"{self}: condition_icons must be a preset pack (mdi, meteocons or meteocons-outline), or a dict."
            logger.exception(TypeError(msg))
            return
        
        nighttime = False
        if not self._isForecast and getattr(self,"HAclient",None) != None:
            sunstate = self.HAclient.stateDict.get("sun.sun", {"state": None})
            nighttime = True if sunstate["state"] == "below_horizon" else False

        # if self.__condition == None:


        weather_icon = parse_weather_icon(self.__condition, night=nighttime, conditionDict=self.condition_icons, prefix=self._condition_prefix, suffix=self._condition_suffix)
        weatherIcon = self.elements["condition"]
        weatherIcon.update({"icon": weather_icon}, skipGen=self.isGenerating, skipPrint=self.isUpdating)
        return
        ##Update the current condition icon accordingly.

    @property
    def weather_data_layout(self) -> PSSMLayoutString:
        "Layout of the weather-data TileLayout. Set to default to automatically make a vertical stack of the elements in weather_data, otherwise a layout needs to be set with each element mapping to a value in weather_data."
        if self.__weather_data_layout != "default":
            return self.__weather_data_layout
        
        data = self.__weather_data
        layout = data[0]

        for data_key in data[1:]:
            layout = f"{layout};{data_key}"
        
        return layout
    
    @weather_data_layout.setter
    def weather_data_layout(self, value : str):
        if value == self.__weather_data_layout:
            return
        
        self.__weather_data_layout = value
        self._rebuild_layout = True

    @property
    def weather_data(self) -> list: #dict[WeatherData,Union[mdiType,str,None]]:
        "The weather data to show along with the forecast icon"
        return self.__weather_data
    
    @weather_data.setter
    def weather_data(self, value : list[WeatherData]):
        if value == getattr(self,"__weather_data", []):
            return
        
        if isinstance(value, str):
            self.__weather_data = [value]
        elif not isinstance(value, (list,set,tuple)):
            msg = f"{self}: weather_data must be an iterable type. Type {type(value)} is not valid"
            logger.exception(msg)
            return

        self.__weather_data = list(value)
        self._rebuild_layout = True

    @property
    def weather_data_icons(self) -> dict[WeatherData,str]:
        """
        Dict with values for the weather_data entries and their corresponding icons.
        Can be set using a default string value for a default dict ("mdi", "meteocons", "meteocons-outline").
        Otherwise, a dict can be used mapping the data names to icons.
        This dict can hold a value for 'defaults' (which is one of the string defaults), which will be used as a default set of icons to use. Initially, mdi will be used if not present. Set this key to `None` to use no default icons.
        If present, the keys prefix and suffix will respectively be used for each value in the dict as a prefix and suffix (to i.e. easily set image extensions).
        Set a data names value to None to use no icon (Default for any values not present in the data dict)
        """        
        return self.__weather_data_icons

    @weather_data_icons.setter
    def weather_data_icons(self, value : Union[Literal["mdi","meteocons","meteocons-outline"],dict[WeatherData,Union[mdiType,str]]]):
        
        defaults = False
        if isinstance(value, dict) and "defaults" in value:
            ##Defaults does not need to be present, as at init the defaults key is automatically set to mdi
            defaults = value.pop("defaults")
            if defaults not in {"mdi","meteocons","meteocons-outline"}:
                msg = f"{self}: Default data icons must be either 'mdi', 'meteocons', 'meteocons-outline', {defaults} is not valid."
                logger.exception(msg)
                return

        if isinstance(value,str):
            if value not in {"mdi","meteocons","meteocons-outline"}:
                msg = f"{self}: Default data icons must be either 'mdi', 'meteocons', 'meteocons-outline'"
                logger.exception(msg)
                return
            defaults = value

        if defaults and defaults in {"mdi","meteocons","meteocons-outline"}:
            if defaults == "mdi": 
                icon_dict  = icon_sets.MDI_WEATHER_DATA_ICONS.copy()
                weather_data_suffix = None 
                weather_data_prefix = None
                ##The ones already have mdi: in front
            else: 
                icon_dict = icon_sets.METEOCONS_WEATHER_DATA_ICONS.copy()
                weather_data_suffix = ".png"
                weather_data_prefix = icon_sets.METEOCONS_PATH if defaults == "meteocons" else icon_sets.METEOCONS_PATH_OUTLINE
                
                for key, icon in icon_dict.items():
                    if icon == None:
                        continue
                    
                    ##Maybe check if this works with the Path instances. Should work like this?
                    icon_dict[key] = weather_data_prefix / f"{icon}{weather_data_suffix}"
        else:
            icon_dict = {}

        if not isinstance(value,dict):
            if icon_dict != self.__weather_data_icons:
                self._rebuild_layout = True
            self.__weather_data_icons = icon_dict
            return
        
        if not defaults: icon_dict = self.__weather_data_icons.copy()

        weather_data_prefix = value.pop("prefix", None)
        weather_data_suffix = value.pop("suffix", None)

        if weather_data_prefix or weather_data_suffix:
            for key, icon in value.items():
                if icon == None:
                    icon_dict[key] = icon
                    continue

                ##Should be able to safely do this even if prefix is a Path instance, since that automatically sets the seperator correctly when printing -> but not the trailing slash...
                if weather_data_prefix != None: 
                    if isinstance(weather_data_prefix,Path):
                        icon = weather_data_prefix / icon
                    else:
                        icon = f"{weather_data_prefix}{icon}"
                if weather_data_suffix != None: icon = f"{icon}{weather_data_suffix}"
                icon_dict[key] = icon

        # self.__weather_data_icons = icon_dict.update(value)
        self.__weather_data_icons = icon_dict
        self._rebuild_layout = True

    @property
    def weather_data_properties(self) -> dict[Literal["icon","data"],dict]:
        "properties for _ALL_ tiles with weather data. Available elements (for element_properties) are `icon` and `data`"
        return self.__weather_data_properties
    
    @weather_data_properties.setter
    def weather_data_properties(self, value : dict):
        if value == self.__weather_data_properties:
            return

        # for elt_str, props in prop_loop:

        ##Need to do this for a single Tile element, and then propagate to each tile
        ##Don't need to call this when setting the foreground color etc. since the  data Tile should take care of that as it updates all elements accordingly
        self.__weather_data_properties = value
        
        # set_props = value.copy()
        
        # color_props = elements.TileLayout.color_properties
        # color_setters = self.__class__._color_shorthands()
        # for prop in color_props.intersection(set_props):
        #     if set_props[prop] in color_setters:
        #         # set_props[prop] = color_setters[set_props[prop]](self)
        #         color_attr = color_setters[set_props[prop]]
        #         set_props[prop] = getattr(self,color_attr)

        # new_props = self._parse_weather_data_properties()
        self._reparse_colors = True

        # for tile in self.weather_data_Tile.elements.values():
        #     tile.update(updateAttributes=new_props, skipGen=self.isUpdating, skipPrint=self.isUpdating)
        

            # tile.elements["icon"].update()

    def _reparse_element_colors(self, elt_name: str = None):
        base._TileBase._reparse_element_colors(self,elt_name)
        new_props = self._parse_weather_data_properties()
        for tile in self.weather_data_Tile.elements.values():
            tile.update(updateAttributes=new_props, skipGen=self.isGenerating, skipPrint=self.isUpdating)

    def _parse_weather_data_properties(self) -> dict:
        """
        Helper function to parse the properties for the weather data tiles.
        Should return the correct colors for foreground etc.
        """        

        set_props = self.__weather_data_properties.copy()
        color_props = elements.TileLayout.color_properties
        color_setters = self.__class__._color_shorthands
        for prop in color_props.intersection(set_props):
            if set_props[prop] in color_setters:
                # set_props[prop] = color_setters[set_props[prop]](self)
                color_attr = color_setters[set_props[prop]]
                set_props[prop] = getattr(self,color_attr)
        return set_props

    @property
    def weather_data_dict(self) -> dict[WeatherData,Union[mdiType,str,None]]:
        "Dict for the weather data. Returns a dict with the data attributes to show along with their set icons."
        s = {}
        for data_name in self.weather_data:
            s[data_name] = self.weather_data_icons.get(data_name,None)
        return s

    # @property
    # def weather_data_Elements(self) -> dict[WeatherData,dict[Literal["icon","button"], Union[base.Icon,base.Button]]]:
    #     return self.__weather_data_Elements

    @property
    def weather_data_Tile(self) -> base.TileLayout: #dict[WeatherData,dict[Literal["icon","button"], Union[base.Icon,base.Button]]]:
        return self.__weather_data_Tile
    #endregion

    #region [Forecast popup properties]
    @property
    def forecast_update(self) -> Union[Literal["on-trigger", "on-open", "hour"], DurationType]:
        if self._isForecast:
            return None
        return self._forecast_update
    
    @forecast_update.setter
    def forecast_update(self, value):
        if self._isForecast:
            return
        
        fc_elt = self.__ForecastElement
        if value in {"on-trigger", "on-open"}:
            new_attr = {"updateEvery": None, "updateInterval": None}
            fc_elt.stop_wait_loop() 
        elif value == "hour":
            new_attr = {"updateEvery": value, "updateInterval": None}
            fc_elt.start_wait_loop()    
        else:
            new_attr = {"updateEvery": None, "updateInterval": value}
            ##Should you restart it upon changing this value?
            ##More something for updateintervals in general tho
            fc_elt.start_wait_loop()
            ##Shouldn't need to cancel this.
            # self.__ForecastElement.updateTask.cancel()

        fc_elt.update(new_attr)
        self._forecast_update = value
    
    @property
    def popup_properties(self) -> dict:
        if self._isForecast:
            return {}
        return self.__popup_properties
    
    @popup_properties.setter
    def popup_properties(self, value : dict):
        if self._isForecast:
            return 
        ##Not allowed to set: layout (is simply the forecast element)
        ##PopupId -> but only for updates, so need to check if that's present in the initial settings.
        if "layout" in value:
            logger.warning(f"{self}: setting the layout of the forecast popup is not allowed")
            value.pop("layout")
        
        self.__popup_properties = value

        set_props = value.copy()
        color_props = elements.TileLayout.color_properties
        color_setters = self.__class__._color_shorthands
        for prop in color_props.intersection(set_props):
            if set_props[prop] in color_setters:
                # set_props[prop] = color_setters[set_props[prop]](self)
                color_attr = color_setters[set_props[prop]]
                set_props[prop] = getattr(self,color_attr)
        self.__ForecastPopup.update(updateAttributes=set_props, skipGen=self.isGenerating, skipPrint=self.isUpdating)

    @property
    def time_format(self) -> str:
        "The time format string to use when formatting the datetime of forecasts"
        return self._time_format
    
    @time_format.setter
    def time_format(self, value :str):
        # if not isinstance(value, str):
        #     msg = f"{self}: time_format value must be a string!"
        #     logger.exception(msg)
        #     return
        
        try:
            datetime.now().strftime(value)
        except (ValueError, TypeError) as e:
            msg = f"{self}: invalid value {value} for time_format: {e}"
            logger.exception(msg)
            return

        self._time_format = value
    #endregion

    # def on_add(self):
    #     super().on_add()
    #     for i,color in enumerate(self.forecastBackground):
    #         if color == "device":
    #             self.forecastBackground[i] = self.parentPSSMScreen.device.defaultColor

    def generator(self, area, skipNonLayoutGen):
        
        if self._rebuild_layout:
            self.build_layout()


        img = base._TileBase.generator(self,area,skipNonLayoutGen)
        return img

    async def Async_generate(self, area=None, skipNonLayoutGen=False):
        async with self._generatorLock:
            if self._rebuild_layout:
                self.build_layout()

        return await super().Async_generate(area, skipNonLayoutGen)

    # async def Async_update(self, updateAttributes, skipGen=False, forceGen: bool = False, skipPrint=False, reprintOnTop=False, updated: bool = False) -> asyncio.Coroutine[Any, Any, bool]:
    #     await super().Async_update(updateAttributes, skipGen, forceGen, skipPrint, reprintOnTop, updated)
    #     return

    def build_layout(self):

        #[ ]: add option for unit, or check if it can be gotten from entity
        #, shapeSettings={"drawArgs":{"start": 30, "end": 210}})
        # self.layout = [["?*0.75", (self.weatherIcon, "?")],["?*0.25", (self.weatherTMP, "?")]]

        data_elts = self.weather_data_Tile.elements
        # weather_data_layout = "icon,data"
        #Don't need to define this, any new element's will have it parsed from the properties.
        rebuild_data_tile = False
        for data_key, icon in self.weather_data_dict.items():
            if data_key not in data_elts:
                rebuild_data_tile = True
                if icon == None:
                    # icon = "mdi:weather-cloudy-clock"
                    iconElt = base.Icon("mdi:weather-cloudy-clock")
                else:
                    iconElt = base.Icon(icon)
                dataElt = base.Button(data_key, fitText=True)
                tile = base.TileLayout("icon,data",{"icon": iconElt, "data": dataElt}, horizontal_sizes={"icon": "r"})
                
                ##Allows for immediately setting the stuff
                if self.weather_data_properties:
                    tile.update(self._parse_weather_data_properties(), skipGen=self.isGenerating, skipPrint=self.isUpdating)

                # self.__weather_data_Elements[data_key] = tile
                self.weather_data_Tile.add_element(data_key, tile)
        ##Will use a tileLayout for each data_element, such that the layouts etc. can be set via that.
            else:
                tile = data_elts[data_key]
            
            if icon == None and "icon" not in tile.hide:
                tile.hide = ["icon"]
            elif icon != None:# and "icon" in tile.hide:
                if "icon" in tile.hide:
                    tile.hide = []
                tile.elements["icon"].update({"icon": icon}, skipGen=self.isGenerating, skipPrint=self.isUpdating)

        if rebuild_data_tile and self.__weather_data_layout == "default":
            self.weather_data_Tile.tile_layout = self.weather_data_layout
            self._rebuild_layout = False

        if not self._isForecast and getattr(self, "HAclient",None) != None and self.entity in self.HAclient.stateDict:
            to_state = self.HAclient.stateDict[self.entity]
            # trigger = {"entity_id": self.entity}
            trigger = triggers.triggerDictType(entity_id=self.entity, to_state=to_state, from_state=None, context=None)
            # if asyncio._get_running_loop() != None:
            if self.parentPSSMScreen.mainLoop.is_running():
                self.parentPSSMScreen.mainLoop.create_task(self.trigger_function(None, trigger))

        self._rebuild_layout = False
        return
        ##TileLayout for the full thing too? yeah sure. With a default, which automatically returns a vertical layout
        ##Should also make parsing them easier.
        ##Should maybe then call add_element for it? Instead of putting it in a dict
        ##Keep in mind the layout should be rebuild if at default.

    async def trigger_function(self, element, trigger_dict):
	#screen.start_batch_writing()
        # try:

        async with self._updateLock:
            if self._rebuild_layout:
                self.build_layout()

        new_state = trigger_dict['to_state']

        element_state = triggers.get_new_state(self,trigger_dict)
        update_props = self.state_styles.get(element_state,{})
        attr_props = triggers.get_attribute_styles(self, trigger_dict)
        update_props.update(attr_props)

        if update_props:
            # start_batch = True
            await self.async_update(update_props, skipGen=True, skipPrint=True)

        logger.debug("Weather: " + str(new_state["state"]))

        
        ##This is for support for forecasts.
        ##is_daytime will be put in by the forecast element.
        async with self._updateLock:
            nighttime = False
            if "is_daytime" in new_state["attributes"]:
                nighttime = not new_state["attributes"]["is_daytime"]
            elif self.HAclient != None:
                sunstate = self.HAclient.stateDict.get("sun.sun", {"state": None})
                nighttime = True if sunstate["state"] == "below_horizon" else False
            
            # weather_icon = parse_weather_icon(new_state["state"],night=nighttime)
            
            # weather_icon = parse_weather_icon(new_state["state"], night=nighttime, conditionDict=self.weather_data_icons, prefix=METEOCONS_PATH, suffix=".png")
            
            self.__condition = new_state["state"]
            weather_icon = parse_weather_icon(new_state["state"], night=nighttime, conditionDict=self.condition_icons, prefix=self._condition_prefix, suffix=self._condition_suffix)
            
            coro_list = set()

            logger.trace(f"Parsing weather icon {weather_icon}")
            # self.elements["condition"].update(updateAttributes={'icon': weather_icon },
            #                 skipPrint = True)
            elts = self.elements
            conditionElt = elts["condition"]

            coro_list.add(conditionElt.async_update(updateAttributes={'icon': weather_icon },
                            skipPrint = True, skipGen=True))
            
            titleElt : StateButton = elts["title"]
            coro_list.add(titleElt.trigger_function(titleElt, trigger_dict))
            # await titleElt.trigger_function(titleElt, trigger_dict)

            data_attr = new_state["attributes"]
            for data_key in self.weather_data:
                if data_key not in data_attr or data_key not in self.weather_data_Tile.elements:
                    continue

                # if data_key not in self.weather_data_Tile.elements:
                #     continue

                data_tile = self.weather_data_Tile.elements[data_key]
                data_button : elements.Button = data_tile.elements["data"]
                data_val = data_attr[data_key]

                data_unit = None
                if "temperature" in data_key or data_key in {"templow", "dew_point"}:
                    if "temperature_unit" in data_attr:
                        data_unit = f' {data_attr["temperature_unit"]}'
                        # data_unit = f" {data_unit}"
                elif data_key in {"humidity", "cloud_coverage", "precipitation_probability"}:
                    data_unit = "%"
                elif data_key == "wind_bearing":
                    if isinstance(data_val, (int,float)):
                        data_unit = "°"
                elif data_key == "datetime":
                    if self.time_format != None:
                        try:
                            data_dt = datetime.fromisoformat(data_val).astimezone()
                            #astimezone seems to automatically convert to the local timezone yay
                            data_val = data_dt.strftime(self.time_format)
                        except FuncExceptions as e:
                            logger.error(f"{self}: error converting datetime into readable string: {e}")
                else:
                    unit_key = f"{data_key}_unit"
                    if unit_key in data_attr:
                        data_unit = f' {data_attr[unit_key]}'

                if data_unit: data_val = f"{data_val}{data_unit}"
                coro_list.add(data_button.async_update({"text": data_val}, skipPrint=True, skipGen=True))
                # data_button.update({"text": data_val})
            
            if not self._isForecast and self.forecast_update == "on-trigger":
                if self.screen.printing:
                    coro_list.add(self.__ForecastElement.get_forecasts())
                else:
                    asyncio.create_task(self.__ForecastElement.get_forecasts())
                # asyncio.create_task(self.__ForecastElement.get_forecasts())

            L = await asyncio.gather(*coro_list,return_exceptions=False)
            for i, res in enumerate(L):
                if isinstance(res,Exception): 
                    logger.error(f"{coro_list[i]} returned an exception: {res} ")

            # done, pending = await asyncio.wait(coro_list,loop=self.parentPSSMScreen.mainLoop, timeout= 10)
            # for coro in pending:
            #     await coro

        if self.onScreen:
            if bool(coro_list) or update_props:
                updated = True
            else: updated = False
            await self.async_update(updated=updated)
            # await self.Async_update(updated=updated, skipGen=True, skipPrint=True)
        
        return

    def show_forecast(self, *args):
        asyncio.create_task(self.async_show_forecast())

    async def async_show_forecast(self, element, coords):
        "Opens the forecast popup and, if forecast_update is 'on_open', will get new forecast data."
        
        ##Seems to work fine even if the forecast is on screen?
        ##Then don't log the warning. Just put it in the docstring.

        if self.forecast_update == "on-open":
            await self.__ForecastElement.get_forecasts()
        await self.__ForecastPopup.async_show()

class WeatherForecast(HAelement, base._TileBase, base._IntervalUpdate):
    """
    An element that shows the weather forecast of the connected entity using a stack of `WeatherElements`.
    Does _NOT_ accept Tile like layout strings, but does accept the same color properties.
    ForecastElements also accept a list of values for its color properties (foreground_color, accent_color, background_color, outline_color).
    Using a list will have the element cycle through the values, i.e. the first `WeatherElement` will parse the first value if it has a color property matching the shorthand. Then the next `WeatherElement` will parse the next value in the list, etc.
    Values are still cycled even if they're not used in an element.
    So, for example, using `background_color = ["black","white"]` and `foreground_color = ["white","black"]`, and `element_properties = {"background_color": "background", "foreground_color": "foreground"}` will mean the first `WeatherElement` has a white foreground_color and black background_color. The second one will have a black foreground_color and a white background_color, etc.
    Parsing color strings is should work without putting them in a list, but in case of using i.e. RGB values, it may be a bit finnicky. The best way to use these values is to already pass them as a nested list (i.e. pass `[[100,100,50]]` instead of `[100,100,50]`). Checks are in place to prevent this but better safe than sorry.
    
    Due to the way the client is setup, the first forecast data cannot be retrieved before printing has started, so the element will initially show the default texts and icons. However the elements should update within the first few seconds, provided a connection to Home Assistant was successfully made.

    Parameters
    ----------
    entity : str
        An entity in the weather domain
    orientation : Literal[&quot;horizontal&quot;,&quot;vertical&quot;], optional
        Orientation of the element, i.e. stack direction, by default "horizontal"
    num_forecasts : int, optional
        The number of forecast entries to show, by default 5
        If not enough forecasts are received, the remainder of space is left empty
    skip_forecasts : Union[int,Literal[&quot;now&quot;]], optional
        Skip the first number of forecast, by default 0
        Used as a python list expression, so negative values can be used too (i.e. -3 means you only use the last 3 received forecasts)
    forecast_type : Literal[&quot;daily&quot;, &quot;hourly&quot;, &quot;twice_daily&quot;], optional
        The type of forecast to request from Home Assistant, by default "daily"
        Keep in mind weather entities don't always support all 3 types, you need to check for yourself which ones the weather entity accepts.
        The logs will show if the requested type is not available.
    forecast_data : Union[Literal[&quot;datetime&quot;], WeatherData], optional
        The data entries to show, by default ["datetime", "temperature", "precipitation", "precipitation_probability"], works the same as `weather_data` in the `WeatherElement`
        Entries do not fully match attributes from the weather entity, you can see the available data by calling the `get_forecasts` service action in Home Assistant, and looking at the response.
    time_format : str, optional
        The time_format to use for the datetime forecast_data, by default "%A" (the full name of the weekday). 
        To show i.e. the time, use %H:%M. Use i.e. https://www.dateformatgenerator.com/?lang=Python to see the format string needed for a desired way to display the datetime
    updateInterval : Union[float,str,DurationType], optional
        The interval with which to request new forecast data, by default "1h"
    element_properties : _type_, optional
        Properties for all of the `WeatherElements`, by default {"background_color": "background", "foreground_color": "foreground", "accent_color": "accent"}
        Setting properties for individual elements is not possible via this property, so you don't need to specify which element gets which properties. You just define them globally, like the default value does.
    foreground_color : Union[ColorType,list[ColorType]], optional
        The foreground color, by default DEFAULT_FOREGROUND_COLOR
        Accepts lists of colors too
    accent_color : Union[ColorType,list[ColorType]], optional
        The accent color, by default DEFAULT_ACCENT_COLOR
        Accepts lists of colors too
    background_color : Union[ColorType,list[ColorType]], optional
        the background color, by default DEFAULT_BACKGROUND_COLOR
        Accepts lists of colors too
    outline_color : Union[ColorType,list[ColorType]], optional
        the outline color, by default None
        Accepts lists of colors too
    """

    ALLOWED_DOMAINS = ["weather"]
    
    _restricted_element_properties = {"time_format", "weather_data", "entity"}

    @property
    def _emulator_icon(cls): return "mdi:cloud-download"

    def __init__(self, entity, orientation : Literal["horizontal","vertical"] = "horizontal", num_forecasts : int = 5, skip_forecasts : Union[int,Literal["now"]] = 0,
                forecast_type : Literal["daily", "hourly", "twice_daily"] = "daily", forecast_data : Union[Literal["datetime"], WeatherData] = ["datetime", "temperature", "precipitation", "precipitation_probability"], 
                time_format : str = "%A", updateInterval : Union[float,str,DurationType] = "1h",
                element_properties : dict = {"background_color": "background", "foreground_color": "foreground", "accent_color": "accent"},
                foreground_color : Union[ColorType,list[ColorType]] = DEFAULT_FOREGROUND_COLOR, accent_color : Union[ColorType,list[ColorType]] = DEFAULT_ACCENT_COLOR,
                background_color : Union[ColorType,list[ColorType]] = DEFAULT_BACKGROUND_COLOR, outline_color : Union[ColorType,list[ColorType]] = None,
                **kwargs):
     

        # logger.warning("The forecast element has not been implemented yet!")
        
        ##Todo:
        ##[x] implement other orientation + orientation switch -> seems to work
        ##[x] update_interval -> mainly just pass it to the intervalupdate init -> works
        ##[x] Overflow when not enough forecasts are returned
        ##[x] Unsuccesfull response -> nvm already did that lol
        ##[ ] Implement as pop-up tap-action for weather-element
            # [x] Kijk ook of je de achtergrond van popups kan blurren
            # [x] Updaten van properties
            # [ ] icon packs -> gekopieerd?
            # [x] forecastelement als tile_layout optie toevoegen
                # Also a check if this is the case cause if so, the forecast element cannot be used as popup
            # [x] Update intervals
            # [x] Uitzoeken waarom de printstack soms whack doet i.e. indices van areaMatrix en ImgMatrix komen niet overeen
                ##Dit lijkt gefixt? Door m te laten loopen over de areaMatrix ipv. de layout zelf

        ##[x] For certain updates: Somehow build in that get_forecasts is called? -> works (use __force_get_forecasts = True1````)
            ##I.e. when changing the forecast type, the updated data would be preferred to be seen immediatly
            ##I think by overwriting the async update, first update all attributes, then if a variable is set, you get the new data after finishing the update?
            ##Would maybe cause some issues? I'd prefer updating and getting the data before that.

        self.entity = entity
        self.__lastForecastUpdate = None
        self._rebuild_layout = True

        self.__forecastLock = asyncio.Lock()
        self.__force_get_forecasts = False
        "Indicates the element should get the forecast data during the current or next update cycle"

        self._element_properties = {}
        self._background_colorList = [None]
        self._foreground_colorList = [None]
        self._outline_colorList = [None]
        self._accent_colorList = [None]
        self.orientation = orientation

        self._entity_units = {}
        "Dict with the units for the entities. Automatically gotten from the entity after connecting."

        self.forecast_type = forecast_type
        self.num_forecasts = num_forecasts
        self.skip_forecasts = skip_forecasts

        self.time_format = time_format
        self.forecast_data = forecast_data

        self.__elements : dict[int, WeatherElement] = {}

        HAelement.__init__(self)

        # updateInterval = "30s"
        base._IntervalUpdate.__init__(self,False,False,False, updateEvery=None, updateInterval=updateInterval)

        # base.Layout.__init__(self,[["?"]],**kwargs)

        ##Test if this can be moved further down?
        base._TileBase.__init__(self,[["?"]],**kwargs)
        
        self.background_color = background_color
        self.foreground_color = foreground_color
        self.accent_color = accent_color
        self.outline_color = outline_color
        # self.outlineWidth = 5

        default_properties = {
            "background_color": "background", "foreground_color": "foreground", "accent_color": "accent",
            "element_properties": 
            {"condition": {"icon_color": "foreground"}},
            "weather_data_properties": {"foreground_color": "foreground", 
                        "element_properties": {"data": {"fitText": True, "fontSize": 0, "font_color": "foreground"}, "icon": {"icon_color": "foreground"}}},
            "vertical_sizes": {"outer": 10}
            }
        
        default_weather_props : dict = default_properties.pop("element_properties")
        set_weather_props : dict = element_properties.pop("element_properties", {})
        # default_weather_props.update(set_weather_props)
        for k, v in default_weather_props.items():
            set_weather_props.setdefault(k,v)
        
        default_properties.update(element_properties)
        default_properties["element_properties"] = set_weather_props

        self.element_properties = default_properties

        self.build_layout()
        return
        ##This will be a regular layout. Two options for 'tile_layout': horizontal and vertical
        ##Each forecast column though will be a weather element, i.e. you can set the layouts of those however you like.

    #region
    @HAelement.entity.setter
    def entity(self, value):
        entity_id = validate_entity(self,value)
        if not entity_id or entity_id == getattr(self,"_entity",None):
            return
        
        HAelement.entity.fset(self, entity_id)
        self.__force_get_forecasts = True
    
    @property
    def elements(self) -> dict[int,WeatherElement]:
        return self.__elements

    @base._TileBase.foreground_color.setter
    def foreground_color(self, value):
        
        color_list = self.__make_color_list(value, "foreground_color")

        set_value = color_list[0]

        self._reparse_colors = True
        self._foreground_colorList = color_list
        base._TileBase.foreground_color.fset(self, set_value)
    
    @base._TileBase.accent_color.setter
    def accent_color(self, value):
        # if isinstance(value, (tuple,list)):
        #     set_value = None
        # else:
        #     set_value = value
        
        color_list = self.__make_color_list(value, "accent_color")

        if not color_list:
            return

        set_value = color_list[0]
        self._reparse_colors = True
        self._accent_colorList = color_list
        base._TileBase.accent_color.fset(self, set_value)

    @base._TileBase.background_color.setter
    def background_color(self, value: Union[str,list]):
        
        # if isinstance(value, (tuple,list)):
        #     set_value = None
        # else:
        #     set_value = value
        
        color_list = self.__make_color_list(value, "background_color")

        if not color_list:
            return

        if None in color_list:
            set_value = None
        else:
            set_value = color_list[0]

        self._reparse_colors = True
        self._background_colorList = color_list
        base._TileBase.background_color.fset(self, set_value)

    @base._TileBase.outline_color.setter
    def outline_color(self, value):
        # if isinstance(value, (tuple,list)):
        #     set_value = None
        # else:
        #     set_value = value
        
        color_list = self.__make_color_list(value, "outline_color")

        if not color_list:
            return

        if None in color_list:
            set_value = None
        else:
            set_value = color_list[0]

        set_value = color_list[0]
        self._reparse_colors = True
        self._outline_colorList = color_list
        base._TileBase.outline_color.fset(self, set_value)

    @property
    def element_properties(self) -> dict[str,dict]:
        """
        Dict with properties for each element. Accepts parsing colors. Needs to be set using the `set_element_properties` method.
        Works a bit different that the normal behaviour, as element keys do not need to be specified (The properties are set the same for each WeatherElement)
        """
        return self._element_properties
    
    @element_properties.setter
    def element_properties(self, value : dict[str, dict]):
        self._element_properties.update(value)
        self._reparse_colors = True

    def __make_color_list(self, value, color_property):
        """
        Checks if the colors in value are valid colors. If value is a single color, checks for that color
        May not work properly when using RGBA colors since it identifies those as multiple colours too.

        Parameters
        ----------
        value : _type_
            _description_
        color_property : _type_
            _description_

        Returns
        -------
        _type_
            _description_
        """        
        if isinstance(value, list):
            if value[0] == None or isinstance(value[0], (str,list,tuple)):
                value = list(value)
            else:
                ##This should prevent RGB color values etc from messing up stuff
                ##Not sure though
                value = [value]
        else:
            value = [value]

        for col in value:
            if not Style.is_valid_color(col):
                logger.warning(f"{self}: {col} is not a valid color. Removing it from the {color_property} list.")
                value.remove(col)
        if not value:
            logger.warning(f"{self}: no valid colors were supplied in the {color_property} list. Not updating.")
        
        if not value:
            return [None]
        return value

    def _reparse_element_colors(self, elt_name: str = None):
        
        # if isinstance(self.background_color, list):
            ##Will just use the shorthands.
            ##Put cycles in a dict -> call next when parsing
            # next(bg_cols)
        color_cycles = {
            "background": cycle(self._background_colorList),
            "foreground": cycle(self._foreground_colorList),
            "outline": cycle(self._outline_colorList),
            "accent": cycle(self._accent_colorList)
            }
        
        set_props_init = self.element_properties.copy()

        set_props_init["time_format"] = self.time_format
        set_props_init["weather_data"] = self.forecast_data
        color_props = WeatherElement.color_properties
        
        ##Don't need to parse these since they are done automatically
        ##maybe easy to do tho? Since it's an easy way to make the dict correctly
        # color_setters = self.__class__._color_shorthands()

        for elt in self.elements.values():
            set_props = set_props_init.copy()
            ##Perform a check for elements not in there to cycle those too
            cycled_cols = set()
            for prop in color_props.intersection(set_props):
                if set_props[prop] in color_cycles:
                    key = set_props[prop]
                    # col_cycl = color_cycles[key]
                    # col = next(col_cycl)
                    set_props[prop] =  next(color_cycles[key])
                    cycled_cols.add(key)
                    
            ##Ensure all values are cycled
            for prop in color_cycles.keys() - cycled_cols:
                next(color_cycles[prop])
            
            elt.update(set_props, skipPrint=self.isUpdating, skipGen=self.isGenerating)
            # elt.update(set_props)
                # else:
        self._reparse_colors = False
        return

    @property
    def lastForecastUpdate(self) -> Optional[datetime]:
        "The last time the forecast was updated succesfully"
        return self.__lastForecastUpdate

    @property
    def forecast_type(self) -> Literal["daily", "hourly", "twice_daily"]:
        "The forecast type to show. Keep in mind Weather entities do not support all types."
        return self.__forecast_type
    
    @forecast_type.setter
    def forecast_type(self, value):
        if value == getattr(self, "__forecast_type", None):
            return

        if value not in {"daily", "hourly", "twice_daily"}:
            msg = f'{self}: forecast_type must be one of ("daily", "hourly", "twice_daily"), {value} is not valid'
            logger.exception(ValueError(msg))
            return
        
        self.__forecast_type = value
        self.__force_get_forecasts = True

    @property
    def num_forecasts(self) -> int:
        "The number of forecasts to show"
        return self.__num_forecasts
    
    @num_forecasts.setter
    def num_forecasts(self, value : int):
        if not isinstance(value, int) or value < 1:
            logger.exception(f"{self}: num_forecasts must be an integer or 1 or higher.")
            return
        
        self.__num_forecasts = value
        self._rebuild_layout = True
        self.__force_get_forecasts = True

    @property
    def skip_forecasts(self) -> Union[int,Literal["now"]]:
        """
        How many forecast entries to skip before using them to populate the elements. None is shorthand(ish) value for not skipping any.
        If set to now, any forecast whos datetime value is smaller than the datetime value of the current time will be omitted.
        Can be a negative integer, which means you'll get the last x forecasts (i.e. setting it to -3 will mean only the last 3 of the returned forecasts are processsed).
        Does not perform checks when setting, to see if enough forecasts are left in combination with the value of `num_forecasts`
        """
        return self.__skip_forecasts
    
    @skip_forecasts.setter
    def skip_forecasts(self, value):
        if value == "now":
            pass
        elif value == None:
            value = 0
        elif not isinstance(value, int):
            logger.exception(f"{self}: skip_forecasts must be an integer or 'now'.")
            return
        
        self.__skip_forecasts = value
        self.__force_get_forecasts = True

    @property
    def time_format(self) -> str:
        "The time format string to use when formatting the datetime of forecasts"
        return self._time_format
    
    @time_format.setter
    def time_format(self, value :str):
        # if not isinstance(value, str):
        #     msg = f"{self}: time_format value must be a string!"
        #     logger.exception(msg)
        #     return
        
        try:
            datetime.now().strftime(value)
        except (ValueError, TypeError) as e:
            msg = f"{self}: invalid value {value} for time_format: {e}"
            logger.exception(msg)
            return

        self._time_format = value
        self._reparse_colors = True
        self.__force_get_forecasts = True

    @property
    def forecast_data(self) -> Union[Literal["datetime"], WeatherData]:
        """
        The forecast data to show. Works similarly to the `WeatherElement` `weather_data`. 
        Available options for the entity can be determined by calling the get_forecasts action in Home Assistant for the element's entity.
        Units for the forecast data are gathered from the entity's attributes.
        """
        return self.__forecast_data

    @forecast_data.setter
    def forecast_data(self, value : list):
        if value == getattr(self,"__forecast_data", []):
            return
        
        if isinstance(value, str):
            value = [value]
        elif not isinstance(value, (list,set,tuple)):
            msg = f"{self}: weather_data must be an iterable type. Type {type(value)} is not valid"
            logger.exception(msg)
            return
        
        self.__forecast_data = value
        self.__force_get_forecasts = True
        self._reparse_colors = True

    @property
    def orientation(self) -> Literal["horizontal", "vertical"]:
        "Direction to stack the forecasts in. Either left to right (horizontal) or top to bottom (vertical)"
        return self.__orientation
    
    @orientation.setter
    def orientation(self, value):
        if value not in {"horizontal", "vertical", "ver", "hor"}:
            logger.error(f"{self}: {value} is not a valid setting for orientation")
        
        if value in "horizontal":
            value = "horizontal"
        else:
            value = "vertical"

        self.__orientation = value
        # self.build_layout()
        self._rebuild_layout = True
    #endregion

    async def async_update(self, updateAttributes={}, skipGen=False, forceGen: bool = False, skipPrint=False, reprintOnTop=False, updated: bool = False) -> bool:
        attr_updated = await super().async_update(updateAttributes, skipGen=True, skipPrint=True)
        if self.HAclient.connection and self.__force_get_forecasts:
            await asyncio.wait([self.get_forecasts()],timeout=0.25)
        return await super().async_update({}, skipGen, forceGen, skipPrint, reprintOnTop, updated= (updated or attr_updated))

    def generator(self, area=None, skipNonLayoutGen=False):
        # e = self.elements[0]
        if self._rebuild_layout:
            self.build_layout()
        img = super().generator(area, skipNonLayoutGen)

        ##Idea  to have a unify_text_size is fun and all, but tbh let users just set the fontSize in weather-data[data] properties if they want a single fontsize I think

        return img

    async def Async_generate(self, area=None, skipNonLayoutGen=False):
        async with self._generatorLock:
            if self._rebuild_layout:
                self.build_layout()

        return await super().Async_generate(area, skipNonLayoutGen)

    def build_layout(self):
        
        if self.orientation == "horizontal":
            layout_row = [None] * (self.num_forecasts + 1)
            layout_row[0] = "?"
            layout = [layout_row]
        else:
            # layout = [["?", None]] * self.num_forecasts
            layout = [["?", None] for _ in range(self.num_forecasts)]

        reparse_colors = self._reparse_colors
        for i in range(self.num_forecasts):
            if i in self.__elements:
                elt = self.__elements[i]
            else:
                ##Can't automatically parse the colours here due to the alternating options
                reparse_colors = True
                elt = WeatherElement(self.entity, weather_data=self.forecast_data, time_format=self.time_format, tap_action=None, _isForecast=True, _register=False)
                ##In here: See what happens when directly parsing?
                if self.HAclient != None:
                    elt._HAclient = self.HAclient
                self.__elements[i] = elt
            
            row, col = self.get_forecast_element_coords(i)
            layout[row][col] = (elt,"?")
            ##Maybe make the tuples, put them in a list, and put those into a layout matrix according to orientation.
            ##Yes, and just use the get_coords function to put them in the correct spot.

        self.layout = layout
        if reparse_colors: self._reparse_element_colors()
        self._rebuild_layout = False
        return

    def get_forecast_element_coords(self, idx : int) -> tuple[int,int]:
        """
        Gets the (assumed) location of the forecast element with index idx. Returns a tuple with indices to use in the layout matrix.

        Parameters
        ----------
        idx : int
            index of which forecast to get (starting from 0)

        Returns
        -------
        tuple[int,int]
            the location of the element within the layout matrix as (row, column)
        """        
        if idx > self.num_forecasts - 1:
            logger.error(f"{self}: can't get a forecast that is outside the range of gotten forecasts. Requested index {idx}, but the maximum is {self.num_forecasts - 1} (i.e., {self.num_forecasts} are requested)")

        if self.orientation == "horizontal":
            idx_1 = 0
            ##This should work I believe? idx 0 should return idx_2 = 1, since [0] is the row_height 
            idx_2 = idx + 1
        else:
            idx_1 = idx
            idx_2 = 1
        
        return (idx_1, idx_2)

    async def trigger_function(self, element: triggers.HAelement, trigger_dict: "triggerDictType"):
        
        new_state = trigger_dict["to_state"]
        if trigger_dict["from_state"] != None:
            ##I don't suspect these will change during runtime tbh
            ##Can also get them from the statedict whenever an update is called?
            ##Eh. But maybe do compare like, 2?
            return

        units = {}

        for key, value in new_state["attributes"].items():
            if "_unit" in key:
                units[key] = value

        self._entity_units = MappingProxyType(units)

        if trigger_dict["from_state"] == None:
            if self._updateTask.done():
                self.__lastForecastUpdate = None
                # await self.HAclient.await_commander()
                # await self.get_forecasts()
                self.start_wait_loop()
        return

    async def _wait(self):
        # while True:
        await self.HAclient.await_commander()
        logger.debug(f"{self}: starting interval loop to get the forecast")
        while self.HAclient.connection and self._waitTime > 0:
            asyncio.create_task(
                self.callback())
            logger.trace(f"{self} waiting for {self._waitTime} seconds to call get_forecasts again.")
            await asyncio.sleep(self._waitTime)

    async def callback(self):
        ##Here to prevent the abstractmethod in _IntervalUpdate from causing an error
        await self.get_forecasts()

    async def get_forecasts(self):

        if self.__forecastLock.locked():
            logger.debug(f"{self}: already getting forecasts, not adding a new call.")
            return

        async with self.__forecastLock:
            service_action = "weather.get_forecasts"
            action_data = {"type": self.forecast_type}
            response_task = self.HAclient.call_service_action(
                elt=None, action=service_action, action_data=action_data, response=True, target=self.entity)
            res = await response_task
            await self.trigger_elements(res)
        return

    async def trigger_elements(self, result : dict):

        if "success" in result and not result["success"]:
            return
        else:
            self.__force_get_forecasts = False

        response = result["result"]["response"]

        if self._rebuild_layout:
            self.build_layout()

        self.__lastForecastUpdate = datetime.now()
        forecasts : list[dict] = response[self.entity]["forecast"]

        dt_now = datetime.now(tz=timezone.utc)
        if isinstance(self.skip_forecasts, int):
            forecasts = forecasts[self.skip_forecasts:]
        else:
            i = 0
            for fc in forecasts:
                # forecast_dt = 
                if dt_now <= datetime.fromisoformat(fc["datetime"]):
                    break
                i += 1
            forecasts = forecasts[i:]

        units = self._entity_units
        dt_isos = dt_now.isoformat()
        if self.num_forecasts > len(forecasts):
            logger.warning(f"{self}: Returned {len(forecasts)} forecasts (With any skipped forecasts already removed), but {self.num_forecasts} were requested. Area for missing forecast entries will be left empty.")
            l = self.layout
            ##I think generally check if any points are None/not None?
            ##Build in functionality to deal with this
            ##Can probably be done in the loop to make the dicts correctly
            for i in range(len(forecasts), self.num_forecasts):
                row, col = self.get_forecast_element_coords(i)
                (elt, width) = self.layout[row][col]
                if elt != None:
                    self.layout[row][col] = (None, width)

        loop_range = min(self.num_forecasts, len(forecasts))

        update_coros = set()

        ##In here/the weatherElement: figure out how to set the nighttime parameter -> simply add to the attributes a is_nighttime, with the weatherelement falling back to the sunstate if it's not there
        ##Use the next_dusk/next_dawn parameter -> figure out which one is first to get current state (or use current sun state)
        ##For daily: I think just use the current state? -> nope, does not necessarily match the current time
        ##Maybe just set is_daytime as True automatically for that
        ##Maybe check the datetime value to see if that (roughly) matches the current time

        #For twice-daily: should be present
        #For daily: auto set to true
        #Hourly: use sunstate.

        if "is_daytime" not in forecasts[0]:
            if self.forecast_type == "daily":
                # for forecast in forecasts: forecast["is_daytime"] = True
                pass
            elif self.forecast_type == "hourly":
                sunstate = self.HAclient.stateDict.get("sun.sun")

                change_dts = {
                            "next_dusk": datetime.fromisoformat(sunstate["attributes"]["next_dusk"]),
                            "next_dawn": datetime.fromisoformat(sunstate["attributes"]["next_dawn"])
                            }
                dt_cycle = cycle(change_dts)

                cur_state = sunstate["state"] != "below_horizon"
                dt_state = cur_state

                key = next(dt_cycle) ##next_dusk
                if not cur_state:
                    key = next(dt_cycle) ##next_dawn
                
                for forecast in forecasts:
                    forecast["is_daytime"] = True
                    # continue

                    forecast_dt = datetime.fromisoformat(forecast["datetime"])
                    if forecast_dt > change_dts[key]:
                        dt_state = not dt_state
                        change_dts[key] = change_dts[key] + timedelta(days=1)
                        key = next(dt_cycle)


                    forecast["is_daytime"] = dt_state
                    
        for i in range(loop_range):
            forecast = forecasts[i]
            state = forecast["condition"]
            attr = forecast
            attr.update(units)
            fct_state = stateDictType(entity_id=self.entity, context={},
                        state=state, attributes=attr,
                        last_changed=dt_isos, last_reported=dt_isos, last_updated=dt_isos)
            trigger = triggerDictType(entity_id=self.entity, to_state=fct_state, from_state=None, context=None)

            if i in self.__elements:
                elt = self.__elements[i]
                row, col = self.get_forecast_element_coords(i)
                (layout_elt, width) = self.layout[row][col]
                if layout_elt != elt:
                    self.layout[row][col] = (elt, width)
                    self._rebuild_area_matrix = True
                update_coros.add(elt.trigger_function(elt,trigger))
            
        async with self._updateLock:
            L = await asyncio.gather(*update_coros, return_exceptions=True)
            for res in L:
                if isinstance(res, Exception):
                    logger.error(f"WeatherElement errored in updating from forecast: {res}")
            # for coro in update_coros:
            #     await coro
        await self.async_update(updated=True)
        return
            

        # return super()._reparse_element_colors(elt_name)

##Apparently seting HAelement as the second parentclass caused issues lol
##So it needs to be in front
class EntityTimer(HAelement, base._TileBase):
    """
    A tile based element for timer entities.
    Provided tiles are 'icon', 'title', 'timer', 'timer-slider', 'timer-countdown' and 'duration'. (See tile_layout below for more info)

    Parameters
    ----------
    entity : EntityType
        The timer entity to attach to
    tile_layout : Union[Literal[&quot;horizontal&quot;,&quot;vertical&quot;],str], optional
        tile layout for this element, by default "horizontal" (`"icon,[title;timer]"`).
        Also allows "vertical" (`"icon;title;timer"`) and custom layout strings.
        Available elements are icon, title, timer-slider, timer-countdown and duration. 
        slider can also be used as an option, and maps either to timer-slider or timer-countdown, depending on the timer_type.
    horizontal_sizes : dict, optional
        horizontal element sizes, by default {"icon": "r", "outer": "?"}
    timer_type : Literal[&quot;slider&quot;,&quot;countdown_total&quot;,&quot;countdown&quot;], optional
        The type of element to show the timer with, by default "slider", which shows a decreasing bar.
        'countdown' shows a text button with the remaining time (that counts down)
        'countdown_total' shows a similar text button, along with the total duration of the timer
    timeformat : Union[Literal[&quot;duration&quot;,&quot;dynamic&quot;],str], optional
        How to format the time strings, by default "duration"
        duration uses the length of duration to set the format. Depending on if the timer takes longer than an hour, it shows/hides the hour part. Same for minutes.
        dynamic uses the same principle, but alters the format based on the remaining time. Does not affect the format of the duration string.
        Any other valid python time format string can be used too.
    element_properties : dict, optional
        Properties for the different elements, 
            applied defaults are {"icon": {"icon_attribute": "icon","icon_color": "foreground", "background_color": "accent", "backgroundShape": "circle", "tap_action": 'toggle_timer'}, "timer-slider": {"style": "box", "inactiveColor": 'accent', "activeColor": "foreground", "outline_color": None}, "title": {"entity_attribute": "friendly_name", "text_xPosition": "left","font": DEFAULT_FONT_HEADER}, "timer-countdown": {"text_xPosition": "left"}}
    """ 
    
    @property
    def _emulator_icon(cls): return "mdi:clock-star-four-points"

    ALLOWED_DOMAINS = ["timer"]

    _default_layouts = {"horizontal": "icon,[title;timer]", "vertical": "icon;title;timer"}

    _restricted_element_properties = {"icon":{"entity"},
                                    "title": {"entity"},
                                    "timer-slider": {"interactive","count","entity","position","minimum","maximum"},
                                    "timer-countdown": {"text"}, "duration": {"text"}}

    def __init__(self, entity : EntityType, tile_layout : Union[Literal["horizontal","vertical"],str] = "horizontal", horizontal_sizes : dict = {"icon": "r", "outer": "?"},
                timer_type : Literal["slider","countdown_total","countdown"] = "slider", 
                timeformat : Union[Literal["duration","dynamic"],str] = "duration", 
                element_properties : dict[str,dict[str,str]] = {"icon": {"icon_attribute": "icon","icon_color": "foreground", "background_color": "accent", "backgroundShape": "circle", "tap_action": 'toggle_timer'},
                            "timer-slider": {"style": "box", "inactiveColor": 'accent', "activeColor": "foreground", "outline_color": None},
                            "title": {"entity_attribute": "friendly_name", "text_xPosition": "left","font": DEFAULT_FONT_HEADER},
                            "timer-countdown": {"text_xPosition": "left"}},
                **kwargs):

        ##How to descern between text just showing the time left/progressed and time/total_time
        self.entity = entity
        self._state = "unknown"
        self._durationString = None
        self._duration = -1
        self._timer_type = None

        self.__timerLock = asyncio.Lock()
        self._timerTask : asyncio.Task = DummyTask()

        ##Configure the defaults/icon still. Otherwise it should be finished I think.
        if "icon" in element_properties.get("icon",{}):
            icon = element_properties["icon"]["icon"]
        else:
            icon = "mdi:timer"

        ##Maybe later on add a way to count upwards?
        slider = elements.TimerSlider("down", position=0)

        icon = elements.Icon(icon, tap_action=self.toggle_timer, icon_attribute=None)
        
        HAelement.wrap_element(icon,None)
        
        timer = elements.Button("--:--")
        total = elements.Button("--/--", )
        stateButton = StateButton(self.entity,"friendly_name", font=DEFAULT_FONT_HEADER)

        elts = {"icon": icon, "timer-slider": slider, "timer-countdown": timer, "duration": total, "title": stateButton}

        self.__elements = elts

        self.timer_type = timer_type #"countdown_total"
        self.timeformat = timeformat

        # layout = "icon,slider"
        # layout = tile_layout #"icon,[title;timer]" 
        ##is horizontal
        ##vertical: icon;title;timer

        default_horizontals = {"icon": "r", "outer": "?"}
        for elt, val in default_horizontals.items():
            horizontal_sizes.setdefault(elt, val)

        ##Don't forget to set the tap_action from the string
        default_properties = {"icon": {"icon_attribute": "icon","icon_color": "foreground", "background_color": "accent", "backgroundShape": "circle", "tap_action": self.toggle_timer},
                            "timer-slider": {"style": "box", "inactiveColor": 'accent', "activeColor": "foreground", "outline_color": None},
                            "title": {"entity_attribute": "friendly_name", "text_xPosition": "left","font": DEFAULT_FONT_HEADER},
                            "timer-countdown": {"text_xPosition": "left"}}
        
        if "icon" in element_properties.get("icon",{}):
            default_properties["icon"].pop("icon_attribute")

        for elt in default_properties:
            set_props = element_properties.get(elt, {})
            default_properties[elt].update(set_props)

        element_properties = default_properties
        
        # k = kwargs
        base._TileBase.__init__(self, tile_layout = tile_layout, horizontal_sizes=horizontal_sizes, 
                                element_properties=element_properties,
                                **kwargs)
        # base.Layout.__init__(self, None, show_feedback=False, **kwargs)

        HAelement.__init__(self)

        return

    #region
    @property
    def elements(self) -> MappingProxyType[Literal["icon","timer","timer-slider", "timer-countdown", "duration", "title"],Union[elements.TimerSlider,elements.Icon, elements.Button, StateButton]]:
        return MappingProxyType(self.__elements)
    
    @property
    def state(self) -> Literal["active", "paused", "idle", "unknown", "unavailable"]:
        return self._state

    @property
    def timer_type(self) -> Literal["slider","countdown","countdown_total"]:
        """
        The type of timer to show. 
        Slider will show a slider type element that decreases. 
        countdown shows the remaining time (and counts down). 
        countdown_total shows the remaining time and the total time.
        """
        return self._timer_type
    
    @timer_type.setter
    def timer_type(self, value : Literal["slider","countdown","countdown_total"]):
        value = value.lower()
        if value == self._timer_type:
            return
        
        if value == "slider":
            self.__elements["timer"] = self.__elements["timer-slider"]
        else:
            self.__elements["timer"] = self.__elements["timer-countdown"]
        
        self._reparse_layout = True
        self._timer_type = value

    @base._TileBase.element_properties.setter
    def element_properties(self, value : dict):
        if "slider" in value:
            logger.warning(f"{self}: slider element cannot be altered directly. Please change the appropriate element: 'timer-slider' or 'timer-countdown'.")
            value.pop("slider")
        base._TileBase.element_properties.fset(self, value)

    @property
    def durationString(self) -> str:
        "The duration of the timer, as gotten from home assistant."
        return self._durationString
    
    @property
    def duration(self) -> float:
        "The duration of the timer, as gotten from home assistant, in seconds"
        return self._duration
    
    def get_asumed_position(self) -> float:
        if  self._finish_time == None:
            return 0
        
        time_diff = self._finish_time - datetime.now(tz=timezone.utc)
        s = time_diff.total_seconds()
        if s >= 0:
            return s
        else:
            return 0
        
    @property
    def timeformat(self) -> Union[Literal["default","dynamic"],str]:
        return self._timeformat
    
    @timeformat.setter
    def timeformat(self, value):
        if value in {"duration", "dynamic"}:
            self._timeformat = value
        else:
            ##Maybe perform a check here to see if it's valid
            self._timeformat = value

    @property
    def timerformatStr(self) -> str:
        "The string gotten from the timeformat. Can be used directly in a `datetime..strftime()` call"
        
        if self.timeformat in {"dynamic","duration"}:
            if self.timeformat == "dynamic" and self.state == "active":
                secs = self.get_asumed_position()
            else:
                secs = self.duration

            if secs >= 60*60:
                timeformat = "%H:%M:%S"
            elif secs >= 60:
                timeformat = "%M:%S"
            else:
                timeformat = "%S"
        else:
            # timeformat = "%H:%M:%S"
            timeformat = self.timeformat
        return timeformat

    @property
    def durationformatStr(self) -> str:
        "The string to format the total duration with"
        if self.timeformat in {"dynamic","duration"}:
            secs = self.duration
            if secs >= 60*60:
                timeformat = "%H:%M:%S"
            elif secs >= 60:
                timeformat = "%M:%S"
            else:
                timeformat = "%S"
        else:
            timeformat = self.timeformat
        return timeformat
    #endregion

    async def trigger_function(self, element: triggers.HAelement, trigger_dict: "triggerDictType"):
        # slider : elements.TimerSlider = self.elements["slider"]
        # return
        new_state = trigger_dict["to_state"]
        
        self._state = new_state["state"]

        if trigger_dict["from_state"] == None:
            # HAelement.wrap_element(self.elements["icon"], self.HAclient)
            self.elements["icon"]._HAclient = self.HAclient
            self.elements["title"]._HAclient = self.HAclient
        
        element_state = triggers.get_new_state(self,trigger_dict)
        update_props = self.state_styles.get(element_state,{})
        attr_props = triggers.get_attribute_styles(self, trigger_dict)
        update_props.update(attr_props)

        attr_updated = False
        if update_props:
            # start_batch = True
            attr_updated = await self.async_update(update_props, skipGen=True, skipPrint=True)


        ##From docs: timers have duration either in "00:00:00" format, or in seconds.
        ##Also I guess try two timeformats? Also the one without leading zeros.
        duration = trigger_dict["to_state"]["attributes"].get("duration", None)
        slider : elements.TimerSlider = self.elements["timer-slider"]

        update_coros = []

        if duration != None and duration != self.durationString:
            self._durationString = duration
            dur_secs = -1
            if isinstance(duration, (int,float)):
                dur_secs = duration
            elif isinstance(duration, str):
                fmt_ops = {"%-H:%M:%S", "%H:%M:%S"}
                for fmt in fmt_ops:
                    try:
                        duration = duration.replace(" ", "")
                        dur_dt = datetime.strptime(duration, fmt) #@IgnoreExceptions
                        break
                    finally:
                        continue
                ##Running into weird problems with .timestamp() not working so I suppose this'll do too.
                dur_secs = dur_dt.second + 60*dur_dt.minute + 60*60*dur_dt.hour + 24*60*60*(dur_dt.day - 1)
            if dur_secs >= 0:
                self._duration = dur_secs
                if slider.maximum != dur_secs:
                    slider.maximum = dur_secs

                total_str = datetime.fromtimestamp(self.duration, timezone.utc).strftime(self.durationformatStr)
                self.elements["duration"].update({"text": total_str})

        if new_state["state"] == "active":
            final_time = new_state["attributes"]["finishes_at"]
            final_dt = datetime.fromisoformat(final_time)

            self._finish_time = final_dt

            # time_diff = final_dt - datetime.now(tz=timezone.utc)

            # cur_seconds = time_diff.total_seconds()

            cur_seconds = self.get_asumed_position()

            ##Gotta check what happens when the timer continues from being paused
            ##Seems to cause a jump.

            # slider.set_position(cur_seconds)
            # if self.timer_type == "slider":
            if slider.onScreen:
                await slider.async_set_position(cur_seconds)
                slider.start_timer()
            else:
                self._timerTask = asyncio.create_task(self._text_timer())
        elif new_state["state"] == "paused":
            self._timerTask.cancel()
            slider.pause_timer()
        else:
            slider.cancel_timer()   
            self._timerTask.cancel()

            timer_str = datetime.fromtimestamp(self.duration, timezone.utc).strftime(self.timerformatStr)
            if self.timer_type == "countdown_total":
                timer_str = f"{timer_str}/{self.durationString}"

            # elt = self.elements["countdown"]
            self.elements["timer-countdown"].update({"text": timer_str})

        title = self.elements["title"]
        icon = self.elements["icon"]

        # update_coros.append(title.trigger_function(title, trigger_dict))

        update_coros.extend([title.trigger_function(title, trigger_dict),icon.trigger_function(icon, trigger_dict)])

        # await asyncio.gather(*update_coros)

        async with self._updateLock:
            L = await asyncio.gather(*update_coros,return_exceptions=True)
            for i, res in enumerate(L):
                if isinstance(res,Exception): 
                    logger.error(f"{update_coros[i]} returned an exception: {res} ")

        if update_coros or attr_updated:
            if bool(update_coros) or attr_updated:
                updated = True
            else: updated = False
            await self.async_update(updated=updated)

        return
        # return await super().trigger_function(element, trigger_dict)

    async def _text_timer(self):
        """
        Runs a loop to update the timer text every second. Stops automatically once the timer reports a different state from active.
        """
        async with self.__timerLock:
            elt = self.elements["timer-countdown"]
            
            while self.state == "active":
                try:
                    cur_seconds = self.get_asumed_position()
                    if cur_seconds < 0:
                        return

                    posstr = datetime.fromtimestamp(cur_seconds, timezone.utc).strftime(self.timerformatStr)
                    if self.timer_type == "countdown_total":
                        total_str = datetime.fromtimestamp(self.duration, timezone.utc).strftime(self.durationformatStr)
                        posstr = f"{posstr}/{total_str}"

                    if elt.onScreen:
                        elt.update({"text": posstr}, reprintOnTop=True)
                        # await elt.Async_update({"text": posstr}, reprintOnTop=True)
                    else:
                        elt.text = posstr
                    
                    ##A constant delay simply looks better.
                    ##Considering how cur_seconds is determined it should not lead to issues anyways.
                    # sleep_time = math.ceil(cur_seconds) - cur_seconds
                    await asyncio.sleep(1) #@IgnoreExceptions
                except asyncio.CancelledError:
                    return

    def toggle_timer(self, *args):
        if self.state != "active":
            self.start_timer()
        else:
            self.pause_timer()

    def start_timer(self, *args):
        "Pauses the connected timer entity"
        # self.elements["timer-slider"].start_timer()

        if self.state != "active":
            self.HAclient.call_service(service="timer.start", target=self.entity)

    def pause_timer(self, *args):
        # self.elements["timer-slider"].pause_timer()

        if self.state == "active":
            self.HAclient.call_service(service="timer.pause", target=self.entity)

    def cancel_timer(self, *args):
        "Cancels the timer"
        # self.elements["timer-slider"].cancel_timer()
        self.HAclient.call_service(service="timer.cancel", target=self.entity)

class ClimateElement(HAelement, base._TileBase):
    """
    A tile element that controls a climate entity. For now, the features are limited to setting the target temperature and selecting the HVAC mode.
    Three tiles are provided: 
        'state-tile': a state tile showing (by default at least) the name of the entity and the current temperature
        'thermostat': a counter element that shows the current target temperature, as well as allows setting it via the counter buttons
        'hvac-modes': a row with icons that can be used to set the HVAC modes. Currently, no custom icons are provided yet but may come later.
            Can be styled via active and inactive colors as well. Currently the only ElementSelector in use, so documentation may not be fully clear.

    Parameters
    ----------
    entity : EntityType
        The climate entity for this element
    tile_layout : Union[PSSMLayoutString,Literal[&quot;horizontal&quot;,&quot;vertical&quot;,&quot;compact&quot;]], optional
        The layout of the element, by default 'compact' ("[state-tile,hvac-modes];thermostat"), also has default values 'horizontal' and 'vertical'
    foreground_color : ColorType, optional
        The element's foreground color, by default DEFAULT_FOREGROUND_COLOR
    accent_color : ColorType, optional
        The element's accent color, by default DEFAULT_ACCENT_COLOR
    element_properties : dict, optional
        Properties for the tile elements, by default colors are parsed to what is deemed appropriate, and hvac-modes has active_properties and inactive_properties set to change the icon_color.
    """  

    ALLOWED_DOMAINS = ["climate"]

    # mode_attributes = {"hvac_modes","preset_modes","swing_modes", "fan_modes"}

    @classmethod
    @property
    def color_properties(cls):
        "Set containing all possible color properties for an element type"
        return base._TileBase.color_properties | {"activeColor"}

    @classproperty
    def _color_shorthands(cls) -> dict[str,str]:
        "Class method to get shorthands for color setters, to allow for parsing their values in element properties. Returns a dict with the [key] being the shorthand to use for element properties and [value] being the tile attribute it links to."
        return {"active": "activeColor"} | base._TileBase._color_shorthands

    _default_layouts = {
                "horizontal": "[state-tile,thermostat];hvac-modes",
                "vertical": "state-tile;thermostat;modes",
                "compact": "[state-tile,hvac-modes];thermostat"}

    @property
    def _emulator_icon(cls): return "mdi:thermostat-box"

    def __init__(self, entity : EntityType, tile_layout : Union[PSSMLayoutString,Literal["horizontal","vertical","compact"]] = "compact",
                foreground_color : ColorType = DEFAULT_FOREGROUND_COLOR, accent_color : ColorType = DEFAULT_ACCENT_COLOR,
                element_properties : dict = {},
                **kwargs):

        self.entity = entity
        
        ##toggle is not necessary since the icon takes care of that - fine by me
        ##Give each preset option its own element?
        ##eh? idk -> a selector would be ok too I think
        ##It's just hard to test since I don't have them
        ##Add color attribute for active -> parsed to the active mode icon
        ##Can't parse it to the active one using 'active' as color but is done automatically for those
        ##simply to use it elsewhere if desired

        # styles = { "heat": {"icon": "mdi:thermostat"},"else":{"icon": "mdi:fire-off"}}
        styles = {}

        tile = EntityTile(self.entity, icon="mdi:thermostat", element_properties={"text":{"entity_attribute": "current_temperature", "prefix_attribute": "state", "prefix_separator": "•"}, "icon": {"icon_attribute": None}}, 
                        state_styles = styles, background_color=None, vertical_sizes = {"outer": 0}, _register = False)
        
        ##Possible modes to set: HVAC, preset, swing and fan
        ##I think just include HVAC modes tbh, it's hard to test if you don't have the features
        ##Don't even know if all hvac modes will work since I only have two

        temp_count = elements.Counter("horizontal", entity=self.entity)

        mode_layout = base.Layout([["?"]])
        base._ElementSelect(mode_layout,{}, allow_deselect=False,
                                        active_properties={}, inactive_properties= {"icon_color": "inactive"}, on_select=self.select_hvac_mode)

        self.__HVACModeLayout = mode_layout

        self.__elements = {"state-tile": tile, "thermostat": temp_count, "hvac-modes": mode_layout}

        HAelement.__init__(self)

        default_properties = {
            "hvac-modes": {"accent_color": "accent", "foreground_color": "foreground", "activeColor": "foreground", "inactiveColor": "accent", "active_properties": {"icon_color": "active"}, "inactive_properties": {"icon_color": "inactive"}},
            "state-tile": {"accent_color": "accent", "foreground_color": "foreground", "background_color": None},
            "thermostat": {"accent_color": "accent", "foreground_color": "foreground"}
            }
        
        for elt, props in default_properties.items():
            if elt not in element_properties:
                element_properties[elt] = props
            else:
                elt_props : dict = element_properties[elt]
                for prop, val in props.items():
                    elt_props.setdefault(prop, val)

        base._TileBase.__init__(self, tile_layout=tile_layout, element_properties=element_properties, foreground_color=foreground_color, accent_color=accent_color,  **kwargs)
        return

    #region
    @property
    def elements(self) -> dict[str,Union[base.Element,HAelement]]:
        return self.__elements

    @property
    def unit(self) -> str:
        "The unit to use for temperatures, as received from the Home Assistant config"
        return self.__unit

    @property
    def HVACModeLayout(self) -> Union[base.Layout, base._ElementSelect]:
        "The layout with icons to set the hvac mode"
        return self.__HVACModeLayout
    #endregion

    # def generator(self, area: CoordType[CoordType, CoordType] = None, skipNonLayoutGen: bool = False):
    #     img= super().generator(area, skipNonLayoutGen)
    #     return img

    async def trigger_function(self, element: triggers.HAelement, trigger_dict: triggerDictType):
        
        new_state = trigger_dict["to_state"]

        state_attr = new_state["attributes"]

        state_elt : EntityTile = self.elements["state-tile"]
        therm : elements.Counter = self.elements["thermostat"]
        if trigger_dict["from_state"] == None:
            state_elt._HAclient = self.HAclient
            self.__unit = self.HAclient.get_unit("temperature")
            t_elt = self.elements["state-tile"].elements["text"]
            await t_elt.async_update({"suffix": " " + self.unit, "suffix_attribute": None})
            await therm.async_update({"unit": " " + self.unit})
            self.make_mode_selectors(state_attr.get("hvac_modes", []))
            # await self.elements["state-tile"].Async_update({"element_properties": {"text": {"suffix": " " + temp_unit, "suffix_attribute": None}}})



        element_state = triggers.get_new_state(self,trigger_dict)
        update_props = self.state_styles.get(element_state,{})
        attr_props = triggers.get_attribute_styles(self, trigger_dict)
        update_props.update(attr_props)

        attr_updated = False
        if update_props:
            # start_batch = True
            attr_updated = await self.async_update(update_props, skipGen=True, skipPrint=True)


        # hvac_mode = state_attr.get("hvac_mode", None)
        update_coros =  set()
        async with self._updateLock:

            if new_state["state"] not in ERROR_STATES and self.HVACModeLayout.selected !=  new_state["state"]:
                # await self.HVACModeLayout.async_select(new_state["state"],call_on_select=False)
                update_coros.add(self.HVACModeLayout.async_select(new_state["state"], call_on_select=False))


            # await self.elements["state-tile"].trigger_function(self.elements["state-tile"], trigger_dict)
            update_coros.add(therm.trigger_function(therm, trigger_dict))
            update_coros.add(state_elt.trigger_function(state_elt, trigger_dict))
            # await therm.trigger_function(therm, trigger_dict)

            L = await asyncio.gather(*update_coros,return_exceptions=True)
            for i, res in enumerate(L):
                if isinstance(res,Exception): 
                    logger.error(f"{update_coros[i]} returned an exception: {res} ")
            
            # i = state_elt.imgData
            # if i != None:
            #     state_elt.imgData.show()
        
        if update_coros or attr_updated:
            await self.async_update(updated=True)
        return
    
    def make_mode_selectors(self, modes):
        mode_elts = {}
        row = ["?"]
        for mode in modes:
            if mode in self.HVACModeLayout.option_elements:
                elt = self.HVACModeLayout.option_elements[mode]
            else:
                icon = icon_sets.HVAC_MODES_ICONS.get(mode,"mdi:thermostat")
                elt = base.Icon(icon)
                mode_elts[mode] = elt
                self.HVACModeLayout.add_option(mode, elt)
            row.append((elt,"?"))
        
        self.HVACModeLayout.update({"layout": [row]})
        if self._tile_layout == "compact":
            self.horizontal_sizes = {"hvac-modes": f"r*{len(modes)}"}

    async def select_hvac_mode(self, element, selected):
        ##Don't forget to update the set mode in the trigger
        ##Will be called again but that should be ok
        ##Do add a check to prevent it from selecting again

        logger.debug(f"{self}: New mode is {selected}")
        
        action = "climate.set_hvac_mode"
        data = {"hvac_mode": selected}
        self.HAclient.call_service_action(action=action, target=self.entity, action_data=data)
        
        return

