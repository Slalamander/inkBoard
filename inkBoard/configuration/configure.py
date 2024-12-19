

from datetime import datetime
import sys
from types import MappingProxyType
from typing import Union, TYPE_CHECKING, overload
from pathlib import Path
from datetime import datetime as dt
from contextlib import suppress
import logging

import yaml

from .types import MainEntry

from ..helpers import ConfigError

from . import const
from .types import *
from .loaders import MainConfigLoader, BaseSafeLoader


if TYPE_CHECKING:
    from PythonScreenStackManager import pssm_types as pssm
    from PythonScreenStackManager.elements import constants as elt
    from mdi_pil import mdiType

dashboard_nodes = {}

_LOGGER = logging.getLogger(__name__)

def mount_config_dir(folder: Path):
    
    if not isinstance(folder, str):
        folder = str(folder)

    sys.path.insert(0, folder)
    with suppress(ImportError):
        import custom  # pylint: disable=import-outside-toplevel  # noqa: F401
        _LOGGER.debug("imported custom folder")

    sys.path.remove(folder)
    sys.path_importer_cache.pop(folder, None)

def read_config(filepath: Path) -> MainEntry:
    with open(filepath) as f:
        _config = yaml.load(f, Loader=MainConfigLoader)
    return MappingProxyType(_config)

def set_folders(full_config : MainEntry, base_folder: Path) -> FolderEntry:
    folderDict = {}

    folder_config = full_config.get("folder", {})

    folderDict["base_folder"] = base_folder

    folders = [k for k in FolderEntry.__dataclass_fields__ if "folder" in k and k != "base_folder"]

    ##If folders key is defined, not existing folders should NOT be made (if they are defined)
    for folder in folders:
            if folder in folder_config:
                p = Path(folder_config[folder])
                if not p.is_absolute():
                    p = base_folder / p
            else:

                f = folder.split('_')[0]
                if f != "custom": f = f + 's' 
                p = base_folder / f
                ##Probably do something here to make the folder if it does not exist? Or at least perform a check
                if not Path(p).exists():
                    _LOGGER.warning(f"folder {folder} does not yet exist, making it")
                    pa = Path(p)
                    pa.mkdir()

            folderDict[folder] = p
    

    return FolderEntry(**folderDict)

class configMeta(type):
    """
    Metaclass for inkBoard configuration. Ensures class attributes cannot be overwritten.
    """

    def __setattr__(cls, name, value):
        raise AttributeError("Cannot modify config attributes")

    def __delattr__(cls, name):
        raise AttributeError("Cannot delete config attributes")


##Turn this into a singleton.
##And make it all instance based not class based.
class config(metaclass=configMeta):
    """
    the inkBoard configuration. Automatically build upon important from the configuration file supplied as command line argument.'
    """
    __configFile = const.DEFAULT_CONFIG_FILE
    "The yaml file where the config is read from"

    
    "The full configuration dict as defined in the yaml file."

    __integrations = {}

    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            return object.__new__(cls)
        else:
            raise AttributeError("Can only define one config class. Access it via `inkBoard.core.config`")

    def __init__(self, file: Union[str,Path]):
        if isinstance(file,str):
            file_path = Path(file).resolve()
        else:
            file_path = file.resolve()
        
        
        if not file_path.exists(): raise ConfigError(f"Cannot find file {file}")
        if not file_path.suffix.endswith(const.CONFIG_FILE_TYPES): raise ConfigError(f"Config file must be of type {const.CONFIG_FILE_TYPES}")

        self.__configFile = file
        self.__filePath = file_path
        self.__baseFolder = file_path.parent

        mount_config_dir(self.__baseFolder)
        

        self._readout_time = datetime.now()
        self._readout_time_string = self._readout_time.strftime("%X")

        BaseSafeLoader._base_folder = self.__baseFolder
        BaseSafeLoader.read_secrets()
        BaseSafeLoader.read_entities()

        __full_config : MainEntry = read_config(file_path)

        missing = []
        for entry in const.REQUIRED_KEYS:
            if entry not in __full_config:
                missing.append(entry)
        
        if missing:
            raise ConfigError(f"Missing required keys {missing}")

        self.__full_config = __full_config

        ##Maybe do a few more assertions or some validation to check if the required keys are present?

        self.__folders = set_folders(__full_config, self.__baseFolder)

        ##Apply test in config to see if required keys are present.

        exces = []

        try:
            self.__inkBoard = InkboardEntry(**__full_config["inkBoard"])
        except TypeError as exce:
            exces.append("inkBoard")

        ##Would probably want to somehow validate the device and screen entries beforehand?
        self.__device = MappingProxyType(DeviceEntry(**__full_config["device"]))
        self.__screen = ScreenEntry(**__full_config.get("screen",{}))
        self.__styles = StylesEntry(**__full_config.get("styles",{}))
        self.__logger = LoggerEntry(**__full_config.get("logger",{}))



        try:
            designer : DesignerEntry = DesignerEntry(**__full_config.get("designer",{}))
        except TypeError as exce:
            _LOGGER.error(f"Error in entry designer: {exce}")
            exces.append("designer")

        self.__designer = designer

        if exces:
            raise ConfigError(f"Errors under entries {exces}")

        return

    def __getitem__(self, item: str):
        return self.configuration[item]
    
    @overload
    def get(self, key, /):
        ...
    
    @overload
    def get(self, key, default, /):
        ...

    def get(self, *args):
        "Gets a key from the full config, similar to calling `.get` on a dict"
        if len(args) == 1:
            return self.__full_config[args[0]]
        else:
            return self.__full_config.get(*args)

    @property
    def file(self) -> str:
        "The file used for the configuration. Either a string or the Path instance to it"
        return self.__configFile

    @property
    def included_yamls(self) -> set[str]:
        "All yaml files included in the config, i.e. secrets.yaml and other include constructors."
        return BaseSafeLoader._opened_files

    @property
    def filePath(self) -> Path:
        "Path to the config file. Resolved be absolute."
        return self.__filePath
    
    @property
    def baseFolder(self) -> Path:
        "The folder the configuration file is in"
        return self.__baseFolder

    @property
    def configuration(self) -> MainEntry:
        "The mappingproxy dict that was build by reading out the configuration file."
        return self.__full_config

    @property
    def folders(self) -> FolderEntry:
        "Folder paths for some of the custom folders, useful when running configs from other folders (like the examples)"
        return self.__folders

    @property
    def logger(self) -> LoggerEntry:
        "Settings for the logger"
        return self.__logger

    @property
    def inkBoard(self) -> InkboardEntry:
        "Configuration under the inkboard: entry. Holds settings for the screen instance mainly."
        return self.__inkBoard
    
    @property
    def device(self) -> DeviceEntry: 
        "Settings for the device. Device type/platform and other settings pertaining to hardware not (directly) related to the screen."
        return self.__device

    @property
    def screen(self) -> ScreenEntry:
        "Settings for the screen instance, like refresh time and rotation."
        return self.__screen

    @property
    def styles(self) -> StylesEntry:
        "Styling for inkBoard, For example to overwrite the default font, or define custom color shorthands."
        return self.__styles

    @property
    def designer(self) -> DesignerEntry:
        "Settings for the designer. Empty if not defined"
        return self.__designer
    ##Replace this by using the command line argument


    ##Full config is read out anyways. So add a function for clients to add stuff, which is passed the full config.
    ##Maybe at print start check if every key is read?
    ##Or redo this, such that it has a function to read out everything at a later point, after the init, which can only be called once.
