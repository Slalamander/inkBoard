"Base component models"
from typing import cast, TYPE_CHECKING, TypedDict
from abc import abstractmethod
from pathlib import Path
from functools import cached_property
import json

from inkBoard import getLogger
from inkBoard.constants import (
    INKBOARD_FOLDER,
)
from inkBoard.types import platformjson, manifestjson

from .version import parse_version, Version

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
        return self.location / self.CONFIG_FILE_NAME

    @cached_property
    def location(self) -> Path:
        return self._location

    @cached_property
    def name(self) -> str:
        return self.location.name

    @cached_property
    def version(self) -> "Version":
        return parse_version(self.config["version"])

    @property
    @abstractmethod
    def config(self) -> baseconfig:
        return

    def __init__(self, location):
        
        location = Path(location)
        assert location.is_dir(), "Location must be a folder"
        self._location = location
        assert self.config_file.exists(), f"Config file {self.config_file} does not exist"
        self.config
        self._is_loaded = False

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
        assert None not in (cls.COMPONENT_FOLDER, cls.CONFIG_FILE_NAME), "Component folder and config file name must be defined in a class"
        f : Path = cls.COMPONENT_FOLDER / name / cls.CONFIG_FILE_NAME
        return f.is_file()

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



