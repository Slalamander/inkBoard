import logging
import asyncio

import random as rnd

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from PythonScreenStackManager import elements
    from PythonScreenStackManager.pssm import PSSMScreen
    from inkBoard import CORE

##The core object holds e.g. the config object, the screen and device instance.
##It is reloaded when the running instance gets reloaded, and the various attributes are set by inkBoard at the appropriate time.
##So generally, importing core is best practice, instead of importing objects from core directly.

from PythonScreenStackManager.elements import baseelements

_LOGGER = logging.getLogger(__name__)


##The screen object can only have one instance, calling this function will return it.
##This is also why it is important to not import any pssm libraries in the __init__ of an integration
##Also why inkBoard sets a global module to the screen instance.

class DummyClient:
    def __init__(self, screen = None, CORE: "CORE" = None) -> None:
        # logger.info("Fry, you fool, you've imported the dummy integration!")

        self.CORE = CORE
        self.dummy_config = CORE.config.configuration["dummy_integration"]
        _LOGGER.info(f"Your custom dummy integration has config {self.dummy_config}")

        if screen != None:
            msg = f"And this is where I keep my assorted sizes of screens. See, this one was imported and is {self.screen_dummy.width} by {self.screen_dummy.height}. And this one was passed when initialising, and is {screen.width} by {screen.height}. Hmhm yes..."
            _LOGGER.info(msg)

        ##This allows users to set the various actions (i.e. on_count and tap_action) with the string dummy-function
        self.screen_dummy.add_shorthand_function("dummy-function", self.dummy_action)

        ##Whenever a new element is registered (which happens be default before printing starts), this function will be called now.
        ##The function itself keeps any registered Dummy elements in the list.
        self.screen_dummy.add_register_callback(self.dummy_registered)
        self.dummies: list[elements.Element] = []
        
        self._running = True
        self.run_callback: Callable[[DummyClient, int],None] = None
        

    @property
    def screen_dummy(self) -> "PSSMScreen":        
        """
        Shorthand to get the screen object. Not necessary per say, but can be useful as a shorthand

        Returns
        -------
        pssm.pssm.PSSMScreen
            The inkBoard screen instance
        """        
        
        return self.CORE.screen

    async def start_dummy(self):
        _LOGGER.info("If anyone needs me, I'll be in the angry dome!")
        # await asyncio.sleep(5)
        _LOGGER.info("*Muffled angry noises*")

    async def run_dummy(self):
        
        run_range = rnd.randint(3,10)
        for i in range(run_range):
            await asyncio.sleep(5)
            _LOGGER.info(msg="*More muffled angry noises*")
            if self.run_callback != None: self.run_callback(self, i)
            self.update_dummies()


        self._running = False
        self.update_dummies()
        raise RuntimeError("Dummy ran too long") #@IgnoreExceptions

    def dummy_registered(self, element : "elements.Element"):

        if isinstance(element, Dummy):
            eltcls = element.__class__
            # logger.info(f"I'm 40% {eltcls}!")
            msg = f"This is no ordinary element! It's a {eltcls} Element!" 
            _LOGGER.info(msg)
            element._dummyclient = self
            self.dummies.append(element)

    def update_dummies(self):
        ##Update all dummy elements with a random rotation

        for elt in self.dummies:
            upd_dict = {"rotation": rnd.randint(0,360)}
            if not self._running:
                upd_dict["badge_icon"] = "mdi:wizard-hat"
            elt.update(upd_dict)


    def dummy_action(self, *args):
        _LOGGER.info("Fry, you fool, you've integrated the dummy integration!")

class Dummy(baseelements.Icon):
    """A dummy element to show how to include custom elements in integrations.

    This element is a simply 

    Parameters
    ----------
    icon : str, optional
        Icon to use for this dummy, by default "mdi:duck"
    icon_color : str, optional
        Color to give this icon, by default "green"
    """

    def __init__(self, icon = "mdi:duck", icon_color = "green", **kwargs):  
        super().__init__(icon, icon_color, **kwargs)
        
    
    @property
    def dummyclient(self) -> DummyClient:
        "The running dummy client"
        return self._dummyclient
    
    def generator(self, area=None, skipNonLayoutGen=False):
        if not self.dummyclient._running:
            _LOGGER.info(" I'll ruin you like I ruined this Dummy Client!")
        return super().generator(area, skipNonLayoutGen)