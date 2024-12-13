import logging
import asyncio

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PythonScreenStackManager import elements
    from PythonScreenStackManager.pssm import PSSMScreen

    
##inkBoard adds these two (alongside with elements and pssm) to the sys, so they can directly be imported as a module.
import PythonScreenStackManager as pssm
# from configure import config
from inkBoard import config

# from . import PythonScreenStackManager

##This way, the init script is ran through only once
from PythonScreenStackManager.elements import baseelements

logger = logging.getLogger(__name__)


##The screen object can only have one instance, calling this function will return it.
##This is also why it is important to not import any pssm libraries in the __init__ of an integration
##Also why inkBoard sets a global module to the screen instance.

from inkBoard import screen

# from inkBoard import screen

# from ...configure import config
##At this point the config is fully read, so the object can be used.

class DummyClient:
    def __init__(self, screen = None) -> None:
        # logger.info("Fry, you fool, you've imported the dummy integration!")

        self.dummy_config = config.configuration["dummy_integration"]
        logger.info(f"Dummy integration has config {self.dummy_config}")

        if screen != None:
            msg = f"And this is where I keep my assorted sizes of screens. See, this one was imported and is {self.screen_dummy.width} by {self.screen_dummy.height}. And this one was passed when initialising, and is {screen.width} by {screen.height}. Hmhm yes..."
            logger.info(msg)

        ##This allows users to set the various actions (i.e. on_count and tap_action) with the string dummy-function
        self.screen_dummy.add_shorthand_function("dummy-function", self.dummy_action)

        ##Whenever a new element is registered (which happens be default before printing starts), this function will be called now.
        self.screen_dummy.add_register_callback(self.dummy_registered)

    @property
    def screen_dummy(self) -> "PSSMScreen":        
        """
        Shorthand to get the screen object. Not necessary per say, but can be useful as a shorthand

        Returns
        -------
        pssm.pssm.PSSMScreen
            The inkBoard screen instance
        """        
        
        return screen
    
    async def start_dummy(self):
        logger.info("If anyone needs me, I'll be in the angry dome!")
        await asyncio.sleep(5)
        logger.info("*Muffled angry noises*")

    async def run_dummy(self):
        # while self.screen_dummy.printing:
        for _ in range(3):
            logger.info("*More muffled angry noises*")
            await asyncio.sleep(5)
        raise RuntimeError("Dummy ran too long") #@IgnoreExceptions

    def dummy_registered(self, element : "elements.Element"):

        if hasattr(element,"dummy"):
            eltcls = element.__class__
            # logger.info(f"I'm 40% {eltcls}!")
            msg = f"This is no ordinary element! It's a dummy {eltcls}" 
            logger.info(msg)
    
    def dummy_action(self, *args):
        logger.info("Fry, you fool, you've integrated the dummy integration!")

