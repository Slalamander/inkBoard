"""
Some functions that validate whether the parsed element type is of the correct type for the section it is being defined in.
These functions raise type errors if they are not, otherwise they simply return.
"""

import logging
from inspect import isabstract

from PythonScreenStackManager import elements

logger = logging.getLogger(__package__)

def validate_general(elt_class, requested_type: str):
    """
    Validates if the provided class is a subclass of the PSSM Element class. `requested_type` is a string for the log messages.
    Also tests whether the class still has abstractmethods, or its name starts with an '_', in which case it is also deemed invalid.
    """
    
    if not issubclass(elt_class,elements.Element):
        msg = f"Requested element type: {requested_type} did not return an Element type, returned {elt_class}"
        logger.error(msg)
        raise TypeError(msg)
    elif isabstract(elt_class) or elt_class.__name__.startswith("_"):
        msg = f"Requested element type: {requested_type} returned {elt_class}, which is a building block element and cannot be used."
        logger.error(msg)
        raise TypeError(msg)

def validate_layout(elt_class, requested_type: str):
    """
    Validates if the provided class is a subclass of the PSSM Layout class
    Keep in mind that, due to way elements have been set up, various elements like Tiles and Counters also evaluate to a layout.
    However, layouts can also simply be defined under element's, and the distinction is moreso to reduce clutter.
    """
    
    validate_general(elt_class,requested_type)

    if not issubclass(elt_class,elements.Layout):
        msg = f"Requested element type: {requested_type} did not return a Layout type Element, returned {elt_class}"
        logger.error(msg)
        raise TypeError(msg)
    
def validate_popup(elt_class, requested_type: str):
    "Validates if the provided class is a subclass of the PSSM Popup class"
    
    validate_general(elt_class, requested_type)
    
    if not issubclass(elt_class,elements.Popup):
        msg = f"Requested element type: {requested_type} did not return a Layout type Element, returned {elt_class}"
        logger.error(msg)
        raise TypeError(msg)
    
validator_dict = {
    "elements": validate_general,
    "layouts": validate_layout,
    "popups": validate_popup,
}
"Dict mapping config entries to possible validator functions"