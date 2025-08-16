"""
A dummy integration for inkBoard. Mainly meant to show how to build one (And so I can remember how to myself)

A minimal integration requires a manifest.json file, as well as an __init__.py file with the `setup` or `async_setup` functions.
Optional are `start`/`async_start` and `async_run`.
"""

# ---------------------------------------------------------------------------- #
#                             Integration Importing                            #
# ---------------------------------------------------------------------------- #
##Integrations are imported after the config has been read out.
##The recommended way to access the config object, however, is to import core from inkBoard. This module gets all the important objects assigned.

##If the integration should be runnable on the designer, ensure that any platform specific imports are not done in the init.
##These can optionally be imported in any of the functions defined in here, provided the module has a designer hook and overwrites any functions that would pose problems.


from typing import TYPE_CHECKING, Optional, Any, Union, TypedDict, Literal
from types import MappingProxyType
from inkBoard.helpers import *
import logging
from time import sleep
import asyncio

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel("INFO")

from inkBoard import CORE as CORE

if TYPE_CHECKING:
    ##During type checking it is fine to import these, 
    ##however importing anything from pssm will break things since the config is not yet loaded.
    ##Same goes for importing config.
    from .dummy import DummyClient
    from inkBoard import CORE as CORE
    from inkBoard.configuration.types import MainEntry as ConfigMap
    from mdi_pil import mdiType
    from PythonScreenStackManager import pssm_types as pssm
    from PythonScreenStackManager.pssm.screen import PSSMScreen

#This if the full dict as read out from the config file.
#The integration is imported, which means the config entry dummy_integration is guaranteed to be present
#however, if the user i.e. reloads, the object may change, so be mindful when using it here. The setup functions are always passed the correct, up to date core object.
conf = CORE.config.configuration.get("dummy_integration")
if conf:
    msg = f"Good news, everyone! I've integrated a dummy integration with settings {conf} into inkBoard!"
else:
    msg = "Good news, everyone! I've integrated a dummy integration into inkBoard!"

def setup(core : "CORE", config : "CORE.config") -> Union[Literal[False],Any]:
    """
    These are similar to the setup functions for home assistant integrations and are required for an integration to be loaded.
    They're called after the screen and device have been set up. As parameters, it is passed the current inkBoard core and the configuration.
    Accessing the screen, device etc. can be done by accessing the appropriate attribute of `core`. Keep in mind, not everything is set yet, so that may raise errors.
    async_setup takes precedent over setup.
    Returning a literal value of False indicates something went wrong in the setup function, for example an error in the config.
    """    

    dummy_conf = config.configuration["dummy_integration"]
    screen = core.screen

    from .dummy import Dummy


    def dummy_parser(elt_type : str):
        ##An element parser is relatively simple. It gets passed a string, and has to return an element type (provided it is all fine and dandy)
        if elt_type != "Dummy":
            _LOGGER.error("I am user-friendly, my good chum.")
        
        return Dummy
    
    core.add_element_parser("DUMMY",dummy_parser)

    ##For integrations with more custom elements, the core.util function can get all Element classes and put them in a dict (the keys being the string names of the Element class)
    ##The function only returns classes which do not have any abstract functions left, and also omits any classes starting with an _
    ##See usage in the second elif statement, though it is obviously not very useful for the dummy.

    if dummy_conf == "I'm 40% config!":
        ##If this is the value of the config, the integration deems the config, or anything else in the setup, to have failed.
        ##So, like the Home Assistant setup functions, return False to indicate something went wrong.
        _LOGGER.error("Bender, you cannot setup the dummy integration!")
        return False
    elif dummy_conf == "Good News Everyone!":
        #Returning a boolean True indicates to the integration loader that the setup result does not need to be available otherwise.
        #This means that, in the latter two functions, the setup_result will be None.
        _LOGGER.info("Good news everyone! It seems I already setup the dummy integration last year.")
        from . import dummy
        all_elements = core.util.get_module_element(dummy)
        _LOGGER.info(f"All dummies aboard the planet express ship! {all_elements}")
        return True
    else:
        ##Returning the dummyobj will lead to inkBoard making the object available under inkBoard.integration_objects["dummy_integration"]
        ##Use this when you want people making custom dashboards to be able to access the object
        msg = f"A size of {screen.width} by {screen.height}? Let me put on my reading glasses."
        _LOGGER.info(msg)
        from .dummy import DummyClient
        dummyobj = DummyClient(screen, core)
        return dummyobj

async def async_setup(core : "CORE", config : "CORE.config"):
    """
    `async_setup` takes precedent over `setup`, so the integration loader calls this function, and not `setup`
    """
    return setup(core, config)


    ##Starting up happens here, do whatever needs doing before printing starts
    ##Keep in mind, a timeout may be set for setting up, which will not cancel this coroutine, but will mean printing starts
    ##So depending on how vital that is, an integration should keep this in mind.
    
def start(core: "CORE", dummy : Optional["DummyClient"]):
    """
    As with setup, `async_start` takes precedent over `start`
    """

    ##If the config of the integration is "Good News Everyone!", the setup function simply returned True.
    ##In that case, the value passed to the second argument is None, since there is no integration object loaded.
    if dummy == None:
        _LOGGER.warning("Fry! You forgot to deliver the dummy!")
        # sleep(5)

    ##This function is blocking, mainly to show off what happens in such a case.
    ##It is more or less worst practice.
    _LOGGER.info("I'm sciencing as fast as I can!")
    # sleep(5)
    _LOGGER.info("Eh wha?!")

async def async_start(core: "CORE", dummy : Optional["DummyClient"]):
    """
    Start is called after the dashboard has been generated, and hence all elements should be registered.
    Use this function to ensure the properties of attributes are set correctly when the screen is printed for the first time, for example.
    A good use is establishing a connection to a websocket, for example.
    When writing the function, take into account that the time given before printing starts may be limited by the user in the config.
    On the other hand, it may also be unlimited, which could cause issues if the function never returns.
    `async_run` will not be called before the start function finishes, nor will the start function be cancelled, but keep both things in mind when writing the function.
    """
    screen = core.screen
    start(screen, dummy)

    if dummy != None:
        await dummy.start_dummy()

async def async_run(core: "CORE", dummy : "DummyClient"):
    """
    A long running task (or set of, i.e. using `asyncio.gather`) that will be started alongside the screen's printloop.
    Must be a coroutine. An example could be a websocket client.
    Not required.
    inkBoard wraps it into a gather call, so awaitables can take as long as needed.
    inkBoard will wait for setup to finish before starting this function.
    """

    if dummy != None:
        await dummy.run_dummy()
    else:
        _LOGGER.warning("Fry! You forgot to deliver the dummy again!")

_LOGGER.info(msg)
