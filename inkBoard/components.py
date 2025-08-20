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

import PythonScreenStackManager as PSSM

import inkBoard.integrations
from inkBoard import getLogger, CORE
from inkBoard.constants import (
    INKBOARD_FOLDER,
    DESIGNER_FOLDER,
    DESIGNER_INSTALLED,
    COMPONENT_PLURAL_MAP,
    COMPONENT_SINGULAR_MAP,
)
from inkBoard.types import (
    componentypes,
    basecomponentjson,
    platformjson,
    manifestjson,
    inkboardrequirements,
    )
from inkBoard.util import reload_full_module, wrap_to_coroutine
from inkBoard.packaging import version

if DESIGNER_INSTALLED or TYPE_CHECKING:
    import inkBoarddesigner.integrations

if TYPE_CHECKING:
    from _inspiration.homeassistant.loader import Integration as hassintegration
    from inkBoard.packaging.version import Version

_LOGGER = getLogger(__name__)


def validate_component_requirements(requirements : inkboardrequirements,
                                validate_designer : bool = False,
                                validate_deps : bool = False) -> bool:
    """Validates the requirements as set in a config file

    Parameters
    ----------
    requirements : inkboardrequirements
        Dict with requirements for the package
    validate_designer : bool, optional
        Whether to validate the designer version, by default False
    validate_deps : bool, optional
        Whether to validate if all the dependencies of the package are installed, by default False

    Returns
    -------
    bool
        _description_
    """

    inv_msg = []
    if "inkboard_version" in requirements:
        vright = requirements["inkboard_version"]
        if comp := version.get_comparitor_string(vright):
            vright = vright.lstrip(comp)
        vleft = version.parse_version(inkBoard.__version__)
        res = version.compare_versions(vleft, vright, comp)
        if not res:
            inv_msg.append(f'Requirement for inkBoard version {requirements["inkboard_version"]} not met (installed version is {vleft})')

    if "pssm_version" in requirements:
        vright = requirements["pssm_version"]
        if comp := version.get_comparitor_string(vright):
            vright = vright.lstrip(comp)
        vleft = version.parse_version(PSSM.__version__)
        res = version.compare_versions(vleft, vright, comp)
        if not res:
            inv_msg.append(f'Requirement for PSSM version {requirements["pssm_version"]} not met (installed version is {vleft})')
    
    if ("designer_version" in requirements and validate_designer):
        if DESIGNER_INSTALLED:
            vright = requirements["designer_version"]
            if comp := version.get_comparitor_string(vright):
                vright = vright.lstrip(comp)
            vleft = version.parse_version(inkBoarddesigner.__version__)
            res = version.compare_versions(vleft, vright, comp)
        else:
            vleft = "NOT INSTALLED"
            res = False
        
        if not res:
            inv_msg.append(f'Requirement for inkBoard designer version {requirements["designer_version"]} not met (installed version is {vleft})')
    
    if "python_version" in requirements:
        vright = requirements["python_version"]
        if comp := version.get_comparitor_string(vright):
            vright = vright.lstrip(comp)
        vleft = sys.version
        res = version.compare_versions(vleft, vright, comp)
        if not res:
            inv_msg.append(f'Requirement for python version {requirements["python_version"]} not met (installed version is {vleft})')

    return not bool(inv_msg)

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
        self.component_type
        moduletype = COMPONENT_SINGULAR_MAP[self.component_type]
        if self.abstract_component:
            basemod = f"ABSTRACT.{moduletype}"
        elif self.core_component:
            basemod = getattr(inkBoard, moduletype)
            basemod = basemod.__package__
        elif self.designer_component:
            basemod = getattr(inkBoarddesigner, moduletype)
            basemod = basemod.__package__
        elif self.custom_component:
            basemod = f"custom.{moduletype}"

        return f"{basemod}.{self.name}"

    @property
    def module(self) -> Union[ModuleType,None]:
        if self.is_loaded:
            return sys.modules[self.module_name]
        return None

    @cached_property
    def version(self) -> "Version":
        return version.parse_version(self.config["version"])

    @cached_property
    def dependencies(self):
        return self.config.get("dependencies", [])

    @cached_property
    def requirements(self):
        return self.config.get("requirements", [])

    @cached_property
    def inkBoard_requirements(self) -> inkboardrequirements:
        return self.config.get("inkboard_requirements", {})

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

    @cached_property
    @abstractmethod
    def config(self) -> basecomponentjson:
        """The components configuration
        Overwrite this component for typehinting.
        If a raw  config is passed to the base __init__, the attribute is overwritten to that
        """
        try:
            config = cast(basecomponentjson, json.loads(self.config_file.read_text()))
        except json.JSONDecodeError as err:
            msg = f"Error parsing {self.CONFIG_FILE_NAME} file at {self.config_file}: {err}"
            raise json.JSONDecodeError(msg) from err
        return config

    def __init__(self, location, config = {}, *, is_abstract : bool = False):
        
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

    def validate_requirements(self, validate_designer : bool = False, validate_deps : bool = False) -> bool:
        req = self.inkBoard_requirements
        # if getattr(CORE, "DESIGNER_RUN", False):
        if CORE.DESIGNER_RUN:
            validate_designer = True
        
        #This is currently in install, which most likely means it will cause a circular import eventually
        #Tbf, for the installer that can be taken care of by importing i.e. in the relevant function

        #Gonna move this back to component from CORE, it is not a thing for CORE tbh
        #Should be fine since install is not imported, only version
        #Will probably use is as a general function mainly though, so it can be called without requiring class instances
        return validate_component_requirements(req, validate_designer, validate_deps)
    
    @classmethod
    @abstractmethod
    def to_index_entry(self) -> dict:
        "Returns a dict with summarised information for the package index"
        return

    def load_module(self, reload : bool = False, *, load_from_file_location : bool = False):
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

        spec_from_location = False
        if self.abstract_component:
            raise ImportError(f"Cannot load/import abstract component {self.name}")
        elif self.custom_component:
            if load_from_file_location:
                spec_from_location = True
            elif "custom" not in sys.modules:
                raise ImportWarning("Cannot import custom integration if the 'custom' module is not imported")
            else:
                try:
                    basefolder = CORE.config.baseFolder
                except AttributeError:
                    basefolder = Path().cwd()
                if not self.location.is_relative_to(basefolder):
                    raise ImportWarning("Cannot import custom integration ")

        module = None        
        if self.module_name in sys.modules and reload:
            self.reload()

        if self.module_name in sys.modules and not reload:
            module = sys.modules.get(self.module_name,None)
        else:
            if spec_from_location:
                spec = importlib.util.spec_from_file_location(self.module_name, str(self.location / "__init__.py"), submodule_search_locations=[])
            else:
                spec = importlib.util.find_spec(self.module_name)

            ##Got this code from: https://docs.python.org/3/library/importlib.html#checking-if-a-module-can-be-imported
            if spec is None:
                msg = f"Unable to import {self.component_type} {self.name} from {self.module_name}"
                raise ImportError(msg)
            
            try:
                module = importlib.util.module_from_spec(spec)
                # if spec_from_location:
                #     sys.modules[self.module_name] = module
                    # spec.loader.exec_module(module)   #Check with testing if this one is necessary, may be done in get_device in order to load the device module
                module = importlib.import_module(self.module_name)
            except Exception as exce:
                msg = f"Error importing {self.module_name} {self.name}: {type(exce)}({exce})"
                # _LOGGER.exception(msg, stack_info=True)
                raise ImportError(msg) from exce

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
        if not self.module:
            raise AttributeError("Cannot determine attribute before loading module")
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
        
