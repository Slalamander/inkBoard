"Base component models"
from typing import (
    cast,
    TYPE_CHECKING,
    TypedDict,
    Union,
    )
from abc import abstractmethod
from pathlib import Path
from functools import cached_property
import json

from inkBoard import getLogger
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

from .packaging.version import parse_version, Version

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
        return

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

    def load_module(self):
        

        return
    
    # def reload(self):


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



