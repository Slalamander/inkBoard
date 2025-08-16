"Base component models"
from typing import (
    cast,
    TYPE_CHECKING,
    TypedDict,
    Union,
    )
from types import ModuleType
from collections.abc import Callable
from abc import abstractmethod
from pathlib import Path
from functools import cached_property
import json
import sys
import importlib
import importlib.util

import inkBoard.integrations
from inkBoard import getLogger, CORE
from inkBoard.constants import (
    INKBOARD_FOLDER,
    DESIGNER_FOLDER,
    DESIGNER_INSTALLED,
    COMPONENT_PLURAL_MAP,
)
from inkBoard.types import (
    componentypes,
    platformjson,
    manifestjson,
    )
from inkBoard.util import reload_full_module, wrap_to_coroutine

from .packaging.version import parse_version, Version

if DESIGNER_INSTALLED or TYPE_CHECKING:
    import inkBoarddesigner.integrations

if TYPE_CHECKING:
    from _inspiration.homeassistant.loader import Integration as hassintegration

_LOGGER = getLogger(__name__)

class baseconfig(TypedDict):

    version : Version

#Base this on the Integration class in Home Assistant: https://github.com/home-assistant/core/blob/dev/homeassistant/loader.py#L650

class BaseComponent:
    """_summary_

    Returns
    -------
    _type_
        _description_
    """

    COMPONENT_FOLDER : Path = None
    CONFIG_FILE_NAME = None

    @cached_property
    def config_file(self) -> Path:
        if self.location:
            return self.location / self.CONFIG_FILE_NAME
        return None

    @cached_property
    def location(self) -> Path:
        return self._location

    @cached_property
    def name(self) -> str:
        #Determine from the location, because that determines with which key it can be loaded in the config
        if self.location:
            return self.location.name
        else:
            return self.config["name"]
        
    @cached_property
    def module_name(self) -> str:
        "The name of the component's python module"
        base_name = f"{self.component_type}.{self.name}"
        if self.abstract_component:
            basemod = "ABSTRACT"
        elif self.core_component:
            basemod = inkBoard.integrations.__package__
        elif self.designer_component:
            basemod = inkBoarddesigner.integrations.__package__
        elif self.custom_component:
            basemod = "custom.integrations"

        return f"{basemod}.{base_name}"

    @property
    def module(self) -> Union[ModuleType,None]:
        if self.is_loaded:
            return sys.modules[self.module_name]
        return None

    @cached_property
    def version(self) -> "Version":
        return parse_version(self.config["version"])

    @cached_property
    def dependencies(self):
        return self.config.get("dependencies", [])

    @cached_property
    def requirements(self):
        return self.config.get("requirements", [])

    @cached_property
    def inkBoard_requirements(self):
        return self.config.get("inkboard_requirements", [])

    @cached_property
    def component_type(self) -> componentypes:
        tk = self.COMPONENT_FOLDER.name
        return COMPONENT_PLURAL_MAP[tk]

    @cached_property
    def abstract_component(self) -> bool:
        "Abstract components are components "
        if self.location:
            return False
        else:
            return True

    @property
    def core_component(self):
        if self.abstract_component:
            return False
        return self.location.is_relative_to(INKBOARD_FOLDER)

    @property
    def designer_component(self):
        if self.abstract_component or not DESIGNER_INSTALLED:
            return False
        return self.location.is_relative_to(DESIGNER_FOLDER)

    @property
    def custom_component(self):
        if self.abstract_component:
            return False
        elif not self.core_component and not self.designer_component:
            return True
        else:
            return False
        
    @property
    def is_loaded(self) -> bool:
        return self.module_name in sys.modules

    @property
    @abstractmethod
    def config(self) -> baseconfig:
        return

    def __init__(self, location, config = {}, *, is_abstract : bool = False):
        
        #FIXME how to handle passing a raw config maybe?
        #Mainly considering readout; may be able to be handled via the cached_property?
        if location:
            location = Path(location)
            assert location.is_dir(), "Location must be a folder"
            self._location = location
            if config:
                self.config = config
            elif not self.config_file.exists():
                raise FileNotFoundError(f"Config file {self.config_file} does not exist")
        
        else:
            assert config, "Please specify a config"
            self._location = None
            self.config = config

        self._is_loaded = False

    @abstractmethod
    def read_config(): ...

    @classmethod
    def is_core_installed(cls, name : str) -> bool:
        """Determines if the given component name is installed internally

        Parameters
        ----------
        name : str
            The component name

        Returns
        -------
        bool
        """        
        return cls.is_installed(name)

    @classmethod
    def is_installed(cls, name : str, folder : Union[str,Path] = None):
        """Determines if the given component name is installed in the provided folder

        If folder is None, use the internal folder for this component

        Parameters
        ----------
        name : str
            The component name

        Returns
        -------
        bool
        """        
        assert None not in (cls.COMPONENT_FOLDER, cls.CONFIG_FILE_NAME), "Component folder and config file name must be defined in a class"
        if folder is None:
            folder = cls.COMPONENT_FOLDER / name
            
        f : Path = folder / cls.CONFIG_FILE_NAME
        return f.is_file()

    @abstractmethod
    def validate_requirements(self) -> bool:

        return
    
    @classmethod
    @abstractmethod
    def to_index_entry(self) -> dict:
        "Returns a dict with summarised information for the package index"
        return

    def load_module(self, reload : bool = False):
        """Loads and imports the component. Returns the module

        Parameters
        ----------
        reload : bool, optional
            Whether to reload the module if it is already installed, by default False

        Returns
        -------
        ModuleType
            The components module

        Raises
        ------
        exce
            _description_
        ImportWarning
            _description_
        """        

        module = None        
        if self.module_name in sys.modules and reload:
            self.reload()

        if self.module_name in sys.modules and not reload:
            module = sys.modules.get(self.module_name,None)
        else:
            spec = importlib.util.find_spec(self.module_name)

            ##Got this code from: https://docs.python.org/3/library/importlib.html#checking-if-a-module-can-be-imported
            if spec  is None:
                _LOGGER.error(f"Unable to import {self.component_type} {self.name} from {self.module_name}")
                return
            try:
                module = importlib.util.module_from_spec(spec)
                module = importlib.import_module(self.module_name)
            except Exception as exce:
                msg = f"Error importing {self.module_name} {self.name}: {exce}"
                _LOGGER.exception(msg, stack_info=True)
                raise exce

        if not hasattr(module,"async_setup") and not hasattr(module,"setup"):
            msg = f"{self.component_type} {self.name} is missing the required setup/async_setup function"
            raise ImportWarning(msg)

        return module
    
    def reload(self):
        reload_full_module(self.module_name)
        self._module = None


class Platform(BaseComponent):
    
    COMPONENT_FOLDER = INKBOARD_FOLDER / "platforms"
    CONFIG_FILE_NAME = "platform.json"

    @cached_property
    def config(self) -> platformjson:
        try:
            config = cast(platformjson, json.loads(self.config_file.read_text()))
        except json.JSONDecodeError as err:
            msg = f"Error parsing {self.CONFIG_FILE_NAME} file at {self.config_file}: {err}"
            raise json.JSONDecodeError(msg)
        return config

class Integration(BaseComponent):
    
    COMPONENT_FOLDER = INKBOARD_FOLDER / "integrations"
    CONFIG_FILE_NAME = "manifest.json"

    @cached_property
    def config(self) -> manifestjson:
        try:
            config = cast(manifestjson, json.loads(self.config_file.read_text()))
        except json.JSONDecodeError as err:
            msg = f"Error parsing {self.CONFIG_FILE_NAME} file at {self.config_file}: {err}"
            raise json.JSONDecodeError(msg)
        return config
    
    @property
    def setup_result(self):
        return self._setup_result

    @property
    def requires_start(self):
        return hasattr(self.module, "async_start") or hasattr(self.module, "start")

    async def async_setup(self, core: "CORE"):
        """Verifies and runs the setup function

        Parameters
        ----------
        core : CORE
            inkBoard CORE object

        Returns
        -------
        Any
            Result of the setup function

        Raises
        ------
        TypeError
            Raised if the setup function is not of a valid type
        ValueError
            Raised if the setup function returns None (which is invalid)
        ImportError
            Raised if the setup returned False
        ImportWarning
            Final exception type, raised from other thrown exceptions or if the component is not loaded yet
        """        

        if not self.is_loaded:
            raise ImportWarning(f"Cannot setup {self.component_type} {self.name} before loading it")

        module = self.module
        if hasattr(module,"async_setup"):
            setup_func = module.async_setup
        elif hasattr(module,"setup"):
            setup_func = module.setup
        
        if not isinstance(setup_func,Callable):
            msg = f"{self.name} does not have a valid setup function, cancelling setup"
            raise TypeError(msg)
        try:
            res = await wrap_to_coroutine(setup_func, core, core.config)

            if res in (None, False):
                if res is None:
                    msg = f"Integration setup functions must return a result (at minimum a boolean `True`), or `False`. {self.name} returned `None`"
                    raise ValueError(msg)
                else:
                    msg = f"Something went wrong setting up {self.name}"
                    raise ImportError(msg)
        except Exception as exce:
            res = exce

        if isinstance(res, Exception):
            raise ImportWarning from res

        self._setup_result = res
        return res
    
    async def async_start(self, core: "CORE"):

        if not self.requires_start:
            raise AttributeError(f"{self.component_type} has no start functions")
        
