"""
A dummy integration for inkBoard. Mainly meant to show how to build one (And so I can remember how to myself)

A minimal integration requires the __integration__ string (must be usuable as a variable too, so e.g. '-' are not possible), as well as the `read_config_entry` and `import_integration` functions.
Optional are `setup`/`async_setup` and `async_run`.
"""

# ---------------------------------------------------------------------------- #
#                             Integration Importing                            #
# ---------------------------------------------------------------------------- #
#Integrations are imported after the config has been read out.
#At this point, the inkBoard config can be imported via `from inkBoard import config`
#When importing, keep in mind the main package is inkBoard (capital B). The package with utilities is inkboard (lower b), which generally is not needed.

from typing import TYPE_CHECKING, Optional, Any, Union, TypedDict, Literal
from types import MappingProxyType
from inkBoard.helpers import *
import logging
from time import sleep
import asyncio

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

from inkBoard import core as CORE

if TYPE_CHECKING:
    ##During type checking it is fine to import these, 
    ##however importing anything from pssm will break things since the config is not yet loaded.
    ##Same goes for importing config.
    from .dummy import DummyClient
    from inkBoard.configuration.types import MainEntry as ConfigMap
    from mdi_pil import mdiType
    from PythonScreenStackManager import pssm_types as pssm
    from PythonScreenStackManager.pssm.screen import PSSMScreen

##Once figured out, don't forget to add a dummy element and explain how/when to import it

#This if the full dict as read out from the config file.
#The integration is imported, which means the config entry dummy_integration is guaranteed to be present
conf = CORE.config.configuration.get("dummy_integration",None)
if conf:
    msg = f"Good news, everyone! I've integrated a dummy integration with settings {conf} into inkBoard!"
else:
    msg = "Good news, everyone! I've integrated a dummy integration into inkBoard!"

def setup(screen : "PSSMScreen", config : "config") -> Union[Literal[False],Any]:
    """
    These are similar to the setup functions for home assistant integrations and are required for an integration to be loaded.
    They're called after the screen has been set up and the device has been imported.
    async_setup takes precedent over setup.
    Returning a literal value of False indicates something went wrong in the setup function, for example an error in the config.
    """    

    dummy_conf = config.configuration["dummy_integration"]

    if dummy_conf == "I'm 40% config!":
        ##If this is the value of the config, the integration deems the config, or anything else in the setup, to have failed.
        ##So, like the Home Assistant setup functions, return False to indicate something went wrong.
        logger.error("Bender, you cannot setup the dummy integration!")
        return False
    elif dummy_conf == "Good News Everyone!":
        #Returning a boolean True indicates to the integration loader that the setup result does not need to be available otherwise.
        #This means that, in the latter two functions, the setup_result will be None.
        logger.info("Good news everyone! I have already setup the dummy integration")
        return True
    else:
        ##Returning the dummyobj will lead to inkBoard making the object available under inkBoard.integration_objects["dummy_integration"]
        ##Use this when you want people making custom dashboards to be able to access the object
        msg = f"A size of {screen.width} by {screen.height}? Let me put on my reading glasses."
        logger.info(msg)
        from .dummy import DummyClient
        dummyobj = DummyClient(screen)
        return dummyobj

async def async_setup(screen : "PSSMScreen", config : "config"):
    """
    `async_setup` takes precedent over `setup`, so the integration loader calls this function, and not `setup`
    """

    return setup(screen, config)


    ##Starting up happens here, do whatever needs doing before printing starts
    ##Keep in mind, a timeout may be set for setting up, which will not cancel this coroutine, but will mean printing starts
    ##So depending on how vital that is, an integration should keep this in mind.
    
def start(screen, dummy : Optional["DummyClient"]):
    """
    As with setup, `async_start` takes precedent over `start`
    """

    ##If the config of the integration is "Good News Everyone!", the setup function simply returned True.
    ##In that case, the value passed to the second argument is None, since there is no integration object loaded.
    if dummy == None:
        logger.warning("Fry! You forgot to deliver the dummy!")
        sleep(5)

    logger.info("I'm sciencing as fast as I can!")
    sleep(5)
    logger.info("Eh wha?!")

async def async_start(screen, dummy : Optional["DummyClient"]):
    """
    Start is called after the dashboard has been generated, and hence all elements should be registered.
    Use this function to ensure the properties of attributes are set correctly when the screen is printed for the first time, for example.
    A good use is establishing a connection to a websocket, for example.
    When writing the function, take into account that the time given before printing starts may be limited by the user in the config.
    On the other hand, it may also be unlimited, which could cause issues if the function never returns.
    `async_run` will not be called before the start function finishes, nor will the start function be cancelled, but keep both things in mind when writing the function.
    """
    start(screen, dummy)

    if dummy != None:
        await dummy.start_dummy()

async def async_run(screen, dummy : "DummyClient"):
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
        logger.warning("Fry! You forgot to deliver the dummy again!")

logger.info(msg)
