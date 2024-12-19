"Handles inkBoard packages, both creating and installing them."

import asyncio
import zipfile
import os
import tempfile
import shutil
import inspect
import json
import subprocess
import sys

from typing import TYPE_CHECKING, TypedDict, Literal, Callable, Union, Optional
from abc import abstractmethod
from functools import partial
from pathlib import Path
from datetime import datetime as dt
from contextlib import suppress

import inkBoard
import inkBoard.platforms
from inkBoard.configuration.const import CONFIG_FILE_TYPES, INKBOARD_FOLDER
from inkBoard.types  import *
from inkBoard import constants as const, bootstrap

import PythonScreenStackManager as PSSM


if TYPE_CHECKING:
    from inkBoard import core as CORE
    from packaging.version import Version

with suppress(ModuleNotFoundError):
    import inkBoarddesigner

try:
    from packaging.version import parse as parse_version
except ModuleNotFoundError:
    from pkg_resources import parse_version



_LOGGER = inkBoard.getLogger(__name__)

packagetypes = Literal['package', 'integration', 'platform']
packageidfiles : dict[packagetypes,str] = {
    'package': 'package.json',
    'integration': 'manifest.json',
    'platform': 'platform.json'
}
internalinstalltypes = Literal["platform", "integration"]

class PackageDict(TypedDict):

    created: str
    "The date and time the package was created, in isoformat"

    created_with: Literal["inkBoard", "inkBoarddesigner"]
    "Whether this package was created via inkBoard itself, or via the designer"

    versions: dict[Literal["inkBoard", "PythonScreenStackManager", "inkBoarddesigner"],str]
    "The versions of the core packages installed when creating it. Designer version is None if not installed"

    platform: str
    "The platform the package was created for"

class NegativeConfirmation(UserWarning):
    "Raised by ask confirm if the confirmation was negative"

INKBOARD_PACKAGE_INTERNAL_FOLDER = ".inkBoard"
#Folder name where files from a package are put which are gotten from or destined to the site-packages inkBoard folder.

VERSION_COMPARITORS = ('==', '!=', '>=', '<=', '>', '<')
"Comparison operators allowed for versioning, so they can be evaluated internally"

DESIGNER_FILES = {"designer", "designer.py"}

REQUIREMENTS_FILE = 'requirements.txt'

required_attributes = {
    "config",
    "device",
    "integration_loader"
    
}

InkboardVersion = parse_version(inkBoard.__version__)
PSSMVersion = parse_version(PSSM.__version__)

def get_comparitor_string(input_str: str) -> Literal[VERSION_COMPARITORS]:
    "Returns the comparitor (==, >= etc.) in a string, or None if there is None."
    if c := [x for x in VERSION_COMPARITORS if x in input_str]:
        return c[0]
    return

def compare_versions(requirement: Union[str,"Version"], compare_version: Union[str,"Version"]) -> bool:
    """Does simple version comparisons.

    For requirements, accepts both a general requirement string (i.e. '1.0.0'), or a comparison string (i.e. package < 1.0.0))

    Parameters
    ----------
    requirement : Union[str,&quot;Version&quot;]
        The requirement to test
    compare_version : Union[str,Version]
        The version to compare the requirement to

    Returns
    -------
    bool
        True if the requirement is satisfied, false if not
    """

    if isinstance(compare_version,str):
        compare_version = parse_version(compare_version)

    if not isinstance(requirement, str):
        ##To be sure that the pkg_resources Version is also fine
        return compare_version >= requirement

    if c := [x for x in VERSION_COMPARITORS if x in requirement]:
        req_version = requirement.split(c[0])[-1]   ##With how the comparitors are set up, 0 should always be the correct one
        comp_str = f"compare_version {c[0]} required_version"
    else:
        req_version = requirement
        comp_str = f"compare_version >= required_version"
    
    return eval(comp_str, {}, {"compare_version": compare_version, "required_version": parse_version(req_version)})

def confirm_input(msg: str, installer: "BaseInstaller"):
    answer = input(f"{msg}\n(Y/N): ")
    if answer.lower() in {"y","yes"}:
        return True
    elif answer.lower() in {"n","no"}:
        return False
    else:
        print("Please answer one of Y(es) or N(o) (Not case sensitive)")
        return confirm_input(msg)

def create_config_package(configuration: str, name: str = None, pack_all: bool = False, config: bool = False, platform: bool = False, integrations: bool = False):
    """Sets up a core instance and creates a package from it

    Parameters
    ----------
    configuration : str
        The YAML file to use
    name : str, optional
        The name of the package, by default None
    pack_all : bool, optional
        Packages all components (config stuff, platform and integrations), by default False
    config : bool, optional
        Packages the config folder, by default False
    platform : bool, optional
        Packages the platform, by default False
    integrations : bool, optional
        Packages the imported integrations, by default False

    Returns
    -------
    int
        Return code
    """    
    core = asyncio.run(bootstrap.setup_core(configuration, bootstrap.loaders.IntegrationLoader))
    return create_core_package(core, name, pack_all, config, platform, integrations)

def create_core_package(core: "CORE", name: str = None, pack_all: bool = False, config: bool = False, platform: bool = False, integrations: bool = False):
    """Creates an inkBoard package from a core instance.

    This bundles all required files and folders from the configuration folder, as well in the required platforms and integrations.

    Parameters
    ----------
    core : CORE
        The core object constructed from the config
    """

    if pack_all:
        Packager(core).create_package(name)
    else:
        pack = []
        if config: pack.append("configuration")
        if platform: pack.append("platform")
        if integrations: pack.append('integration')

        Packager(core).create_package(name, pack)
    return 0


def command_install(file: str, name: str, no_input: bool):
    ##Add functionality to installer for internal installs (platforms and integrations)
    ##Usage: install [platform/integration] [name]

    if file in internalinstalltypes.__args__:
        return install_internal(file, name, no_input)
    else:
        return install_packages(file, no_input)

def install_internal(install_type: str, name:str, no_input: bool = False):
    return InternalInstaller(install_type, name, no_input, confirm_input).install()

def install_packages(file: Union[str, Path] = None, no_input: bool = False):
    
    if file:
        return PackageInstaller(file, skip_confirmations=no_input, confirmation_function=confirm_input).install()
    else:
        packages = PackageInstaller.gather_inkboard_packages()
        if len(packages) == 1:
            print(f"Found 1 package that can be installed")
        else:
            print(f"Found {len(packages)} packages that can be installed")
        for package in packages:
            PackageInstaller(package, skip_confirmations=no_input, confirmation_function=confirm_input).install()
        return 0


class Packager:
    """Takes care of creating inkBoard packages from configs
    """

    def __init__(self, core: "CORE", progress_func: Callable[[str,str, float],None] = None):
        self.CORE = core
        self.config = core.config
        self.base_folder = core.config.baseFolder
        self._copied_yamls = set()
        self.__progress_func = progress_func
    
    def report_progress(self, stage: str, message: str, progress: float):
        "Reports progress to the progress function, if any"
        if self.__progress_func:
            self.__progress_func(stage, message, progress)
        else:
            _LOGGER.info(message)

    def create_package(self, package_name: str = None, pack: list[Literal['configuration', 'platform', 'integration']] = ['configuration', 'platform', 'integration']):

        self.report_progress("Start", f"Creating a package for {self.CORE.config.file}", 0)

        self.report_progress("Gathering", "Creating temporary directory", 5)

        with tempfile.TemporaryDirectory(dir=self.base_folder) as tempdir:

            if 'configuration' in pack:
                self.report_progress("Configuration", "Copying configuration directory", 10)
                self.copy_config_files(tempdir)
            
            if 'platform' in pack:
                self.report_progress("Platform", "Copying platform directory", 30)
                self.copy_platform_folder(tempdir)

            if 'integration' in pack:
                self.report_progress("Integrations", "Copying included integrations", 50)
                self.copy_integrations(tempdir)

            self.report_progress("Package Info", "Creating Package info file", 70)            

            package_info = self.create_package_dict()
            with open(Path(tempdir) / "package.json", 'w') as f:
                json.dump(package_info, f, indent=4)

            if not package_name:
                package_name = f'inkBoard_package_{package_info["platform"]}_{self.CORE.config.filePath.stem}'

            self.report_progress("Zip File", "Creating Package zipfile", 75)
            _LOGGER.info("Creating package zip file")
            zipname = self.base_folder / f'{package_name}.zip'
            with zipfile.ZipFile(zipname, 'w') as zip_file:
                for foldername, subfolders, filenames in os.walk(tempdir):
                    _LOGGER.verbose(f"Zipping contents of folder {foldername}")
                    for filename in filenames:
                        file_path = os.path.join(foldername, filename)
                        zip_file.write(file_path, os.path.relpath(file_path, tempdir))
                    for dir in subfolders:
                        dir_path = os.path.join(foldername, dir)
                        zip_file.write(dir_path, os.path.relpath(dir_path, tempdir))

            self.report_progress("Done", f"Package created: {zipname}", 100)
            _LOGGER.info(f"Package created: {zipname}")

        return

    def copy_config_files(self, tempdir):
        "Copies all files and folders from the config directory in to the temporary folder"

        _LOGGER.info(f"Copying files from config folder {self.base_folder}")
        config_dir = Path(tempdir) / "configuration"
        config_folders_copy = {
        "icon", "picture", "font", "custom", "file"
        }


        for folder_attr in config_folders_copy:
            ignore_func = partial(self.ignore_files, self.config.folders.custom_folder / "integrations", 
                            ignore_in_baseparent_folder = DESIGNER_FILES)
            path: Path = getattr(self.config.folders, f"{folder_attr}_folder")
            if not path.exists():
                continue
            
            _LOGGER.info(f"Copying config folder {path.name}")
            shutil.copytree(
                src= path,
                dst= config_dir / path.name,
                ignore=ignore_func
            )
        
        for yamlfile in self.config.included_yamls:
            if Path(yamlfile) in self._copied_yamls:
                _LOGGER.debug(f"Yaml file {yamlfile} was already copied.")
                continue

            _LOGGER.debug(f"Copying yaml file {yamlfile}")
            shutil.copy2(
                src=yamlfile,
                dst=config_dir
            )

        _LOGGER.info(f"Succesfully copied contents of config folder.")
        return
    
    def copy_platform_folder(self, tempdir):
        
        tempdir = Path(tempdir)

        if self.CORE.DESIGNER_RUN:
            platform = self.CORE.device.emulated_platform
            platform_folder = self.CORE.device.emulated_platform_folder
        else:
            platform = self.CORE.device.platform
            platform_folder = Path(inspect.getfile(self.CORE.device.__class__)).parent
        
        _LOGGER.info(f"Copying platform {platform} from {platform_folder} to package")

        manual_files = {"readme.md", "install.md", "installation.md"}
        manual_dir = (tempdir / "configuration") if (tempdir / "configuration").exists() else tempdir

        for file in platform_folder.iterdir():
            if file.name.lower() not in manual_files:
                continue

            manual_files.add(file.name)
            
            _LOGGER.debug(f"Copying platform manual file {file}")
            shutil.copy2(
                src = file,
                dst = manual_dir
            )

        ignore_func = partial(self.ignore_files, platform_folder.parent, ignore_in_baseparent_folder = manual_files | DESIGNER_FILES )
        _LOGGER.debug("Copying platform folder")
        shutil.copytree(
                src = platform_folder,
                dst = tempdir / INKBOARD_PACKAGE_INTERNAL_FOLDER / "platforms" / platform_folder.name,
                ignore = ignore_func
            )
        
        _LOGGER.info("Succesfully copied platform folder")
        return

    def copy_integrations(self, tempdir):
        
        tempdir = Path(tempdir)

        ##Filter out integrations from the custom folder
        all_integrations = self.CORE.integration_loader.imported_integrations

        _LOGGER.info("Copying all non custom integrations to package")
        for integration, location in all_integrations.items():
            if location.is_relative_to(self.config.folders.custom_folder):
                ##Skip integrations here. Those were already copied during the config folder phase
                continue
            _LOGGER.debug(f"Copying integration {integration}")
            ignore_func = partial(self.ignore_files, location.parent, ignore_in_baseparent_folder=DESIGNER_FILES)
            shutil.copytree(
                src= location,
                dst= tempdir / INKBOARD_PACKAGE_INTERNAL_FOLDER / "integrations" / location.name,
                ignore=ignore_func
            )
            
        _LOGGER.info("Succesfully copied integrations")
        return

    def ignore_files(self, parentbase_folder: Path, src, names, ignore_in_baseparent_folder: set = {}):
        """Returns a list with files to not copy for `shutil.copytree`

        Parameters
        ----------
        parentbase_folder : Path
            The base folder being copied from
        src : str
            source path, passed by `copytree`
        names : list[str]
            list with file and folder names, passed by `copytree`
        ignore_in_baseparent_folder : set, optional
            Set with filenames to ignore (i.e. not copy), _Only if_ the parent folder of `src` is `base_ignore_folder`, by default {}

        Returns
        -------
        _type_
            _description_
        """        

        ignore_set = {"__pycache__"}
        if Path(src).parent == parentbase_folder:
            ignore_set.update(ignore_in_baseparent_folder)

        for name in filter(lambda x: x.endswith(CONFIG_FILE_TYPES), names):
            self._copied_yamls.add(Path(src) / name)

        return ignore_set

    def create_package_dict(self) -> PackageDict:
        
        package_dict = {"created": dt.now().isoformat()}

        package_dict["versions"] = {"inkBoard": inkBoard.__version__,
                    "PythonScreenStackManager": PSSM.__version__}
        

        if self.CORE.DESIGNER_RUN:
            package_dict["created_with"] = "inkBoarddesigner"
            package_dict["versions"]["inkBoarddesigner"] = inkBoarddesigner.__version__
            package_dict["platform"] = self.CORE.device.emulated_platform
        else:
            package_dict["created_with"] = "inkBoard"
            package_dict["versions"]["inkBoarddesigner"] = None
            package_dict["platform"] = self.CORE.device.platform

        return PackageDict(**package_dict)

class BaseInstaller:
    """Base class for installers

    Call `Installer().install()` to run the installer, or use the pip functions to install packages via pip
    """

    _skip_confirmations: bool
    _confirmation_function: Callable[[str, 'BaseInstaller'],bool]

    @property
    def skip_confirmations(self) -> bool:
        "Whether to ask for confirmation for all actions"
        return self._skip_confirmations
    
    @property
    def confirmation_function(self) -> Callable[[str, 'BaseInstaller'],bool]:
        "The function used to prompt the user for confirmation"
        return self._confirmation_function
    

    @abstractmethod
    def install(self):
        "Runs the installer"
        return

    def install_platform_requirements(self, name: str, platform_conf: platformjson) -> bool:
        """Installs requirements based on a platformjson dict

        Parameters
        ----------
        name : str
            Name of the platform. For logging
        platform_conf : platformjson
            The platform.json dict

        Returns
        -------
        bool
            Whether the requirements were installed successfully
        """        

        platform = name
        requirements = platform_conf["requirements"]
        if requirements:
            res = self.pip_install_packages(*requirements, no_input=self._skip_confirmations)

            if res.returncode != 0:
                try:
                    msg = f"Something went wrong installing the requirements using pip. Continue installation of platform {platform}?"
                    self.ask_confirm(msg, force_ask=True)
                except NegativeConfirmation:
                    return False

        for opt_req, reqs in platform_conf.get("optional_requirements", {}).items():
            with suppress(NegativeConfirmation):
                msg = f"Install requirements for optional features {opt_req}?"
                self.ask_confirm(msg)
                self.pip_install_packages(*reqs, no_input=self._skip_confirmations)
        
        return True

    def install_integration_requirements(self, name: str, manifest: manifestjson) -> bool:
        """Installs integration requirements based on a manifestjson dict

        Parameters
        ----------
        name : str
            Name of the integration. For logging
        platform_conf : platformjson
            The manifest.json dict

        Returns
        -------
        bool
            Whether the requirements were installed successfully
        """

        integration_version = parse_version(manifest['version'])
        integration = name

        _LOGGER.info(f"Installing new Integration {integration}, version {integration_version}")
        
        requirements = manifest["requirements"]
        if requirements:
            res = self.pip_install_packages(*requirements, no_input=self._skip_confirmations)

            if res.returncode != 0:
                try:
                    msg = f"Something went wrong installing the requirements using pip. Continue installation of integration {integration}?"
                    self.ask_confirm(msg, force_ask=True)
                except NegativeConfirmation:
                    return False

        for opt_req, reqs in manifest.get("optional_requirements", {}).items():
            with suppress(NegativeConfirmation):
                msg = f"Install requirements for optional features {opt_req}?"
                self.ask_confirm(msg)
                self.pip_install_packages(*reqs, no_input=self._skip_confirmations)
        return True

    def ask_confirm(self, msg: str, force_ask: bool = False):
        """Prompts the user to confirm something.

        Calls the confirmation function passed at initialising if skip_confirmations is `False`
        
        Parameters
        ----------
        msg : str
            The message to pass to the confirmation function
        force_ask : bool
            Force the prompt to appear, regardless of the value passed to `skip_confirmations`

        Raises
        ------
        NegativeConfirmation
            Raised if the confirmation does not evaluate as `True`
        """
        if self._skip_confirmations and not force_ask:
            return
        
        if self._confirmation_function:
            if not self._confirmation_function(msg, self):
                raise NegativeConfirmation
        return

    def check_inkboard_requirements(self, ib_requirements: inkboardrequirements, required_for: str) -> bool:
        """Checks if inkBoard requirements are met for the current install

        Performs version checks for inkBoard and pssm, and checks for installed platforms and their versions. 

        Parameters
        ----------
        ib_requirements : inkboardrequirements
            Dict with inkBoard specific requirements
        required_for : str
            What the requirements are required for. Used in log messages. Best practice is to pass it as [type] [name], e.g. 'Platform desktop'

        Returns
        -------
        bool
            `True` if requirements are met, otherwise `False`.
        """        

        ##Check: required inkboard version, pssm version and required integrations/platforms 
        warn = False
        if v := ib_requirements.get("inkboard_version", None):
            if not compare_versions(v, InkboardVersion):
                warn = True
                _LOGGER.warning(f"{required_for} requirment for inkBoard's version not met: {v}")

        if v := ib_requirements.get("pssm_version", None):  ##I think this should generally be met by having the inkBoard requirement met tho?
            if not compare_versions(v, PSSMVersion):
                warn = True
                _LOGGER.warning(f"{required_for} requirment for PSSM's version not met: {v}")

        for platform in ib_requirements.get('platforms', []):
            req_vers = None
            if c := get_comparitor_string(platform):
                platform, req_vers = platform.split(c)
            
            if not (INKBOARD_FOLDER / "platforms" / platform).exists():
                warn = True
                _LOGGER.warning(f"Platform {platform} required  for {required_for} is not installed")
                ##Should maybe check this in regards with package installing? i.e. if these are otherwise present in the package
                ##But will come later.
            elif req_vers:
                with open(INKBOARD_FOLDER / "platforms" / platform / packageidfiles["platform"]) as f:
                    platform_conf: platformjson = json.load(f)
                    cur_version = platform_conf["version"]

                if not compare_versions(c + req_vers, cur_version):
                    warn = True
                    _LOGGER.warning(f"Platform {platform} does not meet the version requirement: {c + req_vers}")

        ##And do the same for integrations.
        for integration in ib_requirements.get('integrations', []):
            req_vers = None
            if c := get_comparitor_string(integration):
                integration, req_vers = integration.split(c)
            
            if not (INKBOARD_FOLDER / "integrations" / integration).exists():
                warn = True
                _LOGGER.warning(f"Integration {integration} required for {required_for} is not installed")
                ##Should maybe check this in regards with package installing? i.e. if these are otherwise present in the package
                ##But will come later.
            elif req_vers:
                with open(INKBOARD_FOLDER / "integrations" / integration / packageidfiles["integration"]) as f:
                    integration_conf: manifestjson = json.load(f)
                    cur_version = integration_conf["version"]

                if not compare_versions(c + req_vers, cur_version):
                    warn = True
                    _LOGGER.warning(f"Integration {integration} does not meet the version requirement: {c + req_vers}")

        return not warn

    @staticmethod
    def pip_install_packages(*packages: str, no_input: bool = False) -> subprocess.CompletedProcess:
        """Calls the pip command to install the provided packages

        Parameters
        ----------
        packages : str
            The packages to install (as would be passed to pip as arguments)
        no_input: bool
            Disables prompts from pip        

        Returns
        -------
        subprocess.CompletedProcess
            The result of the subprocess.run function
        """

        if not packages:
            return

        if no_input:
            args = [sys.executable, '-m', 'pip', '--no-input', 'install', *packages]
        else:
            args = [sys.executable, '-m', 'pip', 'install', *packages]

        res = subprocess.run(args)
        return res
    
    @staticmethod
    def pip_install_requirements_file(file: Union[str,Path], *, no_input: bool = False) -> subprocess.CompletedProcess:
        """Calls the pip command to install the provided .txt file with requirements

        Parameters
        ----------
        file : Union[str,Path]
            The text file holding the requirements
        no_input: bool
            Disables prompts from pip
        
        Returns
        -------
        subprocess.CompletedProcess
            The result of the subprocess.run function
        """

        if isinstance(file,Path):
            file = str(file.resolve())

        if no_input:
            args = [sys.executable, '-m', 'pip', '--no-input', 'install', '-r', file]
        else:
            args = [sys.executable, '-m', 'pip', 'install', '-r', file]


        res = subprocess.run(args)
        return res

    ##Options to install:
    # - Package
    # - Platform
    # - Integration
    # - requirements; internal and external -> internal eh, should be taken care of when actually installing it.

class PackageInstaller(BaseInstaller):
    """Installs an inkBoard compatible .zip file, or requirements files in a config directory.

    Call `PackageInstaller().install()` to run the installer.
    There are a few classmethods and staticmethods too that can be called without instantiating.

    Parameters
    ----------
    file : Union[Path,str]
        The .zip file to install
    skip_confirmations : bool, optional
        Skips most confirmation messages during installation, except those deemed vital, by default False
    confirmation_function : Callable[[str, Installer],bool], optional
        Function to call when asking for confirmation, gets passed the question to confirm and the Installer instance., by default None
    """

    def __init__(self, file: Union[Path,str], skip_confirmations: bool = False, confirmation_function: Callable[[str, 'BaseInstaller'],bool] = None):
        self._file = Path(file)
        assert self._file.exists(), f"{file} does not exist"
        self._confirmation_function = confirmation_function
        self._skip_confirmations = skip_confirmations

        if self._file.suffix in CONFIG_FILE_TYPES:
            self._package_type = "configuration"
        else:
            self._package_type: packagetypes = self.identify_zip_file(self._file)
        return

    def install(self):
        """Runs the appropriate installer for the package type.
        """

        if self._package_type == "integration":
            self.install_integration()
        elif self._package_type == "platform":
            self.install_platform()
        elif self._package_type == "package":
            self.install_package()
        elif self._package_type == "configuration":
            self.install_config_requirements(self._file, self._skip_confirmations, self._confirmation_function)

    def install_package(self) -> Optional[packagetypes]:
        """Installs a package type .zip file file
        """        

        file = self._file

        if self._package_type != 'package':
            raise TypeError(f"{file} is not a package type .zip file")

        try:
            self.ask_confirm(f"Install package {file}?")
        except NegativeConfirmation:
            _LOGGER.info(f"Not installing package {file}")
            return

        with zipfile.ZipFile(file) as zip_file:
            self.__zip_file = zip_file
            zip_path = zipfile.Path(zip_file)
            # with zip_file.open(packageidfiles["package"]) as f:
                ##This section is used to determine compatibility of the package and the installed modules
            f = zip_file.open(packageidfiles["package"])
            package_info: PackageDict = json.load(f)

            vers_msg = ""
            if (v := parse_version(package_info["versions"]["inkBoard"])) >= InkboardVersion:
                vers_msg = vers_msg + f"Package was made with a newer version of inkBoard ({v}). Installed is {InkboardVersion}."
            
            if (v := parse_version(package_info["versions"]["PythonScreenStackManager"])) >= PSSMVersion:
                vers_msg = vers_msg + f"Package was made on with a newer version of PSSM ({v}). Installed is {PSSMVersion}."
            
            if vers_msg:
                print(vers_msg)
                try:
                    self.ask_confirm(f"Version mismatch, continue installing {self._package_type}?")
                except NegativeConfirmation:
                    return
            
            ##Check if platform is installed or present in the package.
            package_platform = package_info["platform"]

            if ((INKBOARD_FOLDER / "platforms" / package_platform).exists() or 
                (zip_path / INKBOARD_PACKAGE_INTERNAL_FOLDER / "platforms" / package_platform).exists()):
                pass
            else:
                msg = f"Package was made for platform {package_platform}, but it is not installed or present in the package. Continue installing?"
                try:
                    self.ask_confirm(msg)
                except NegativeConfirmation:
                    return

            if (zip_path / INKBOARD_PACKAGE_INTERNAL_FOLDER / "platforms").exists():
                _LOGGER.info("Installing platforms")
                for platform_folder in (zip_path / INKBOARD_PACKAGE_INTERNAL_FOLDER / "platforms").iterdir():
                    
                    with suppress(NegativeConfirmation):
                        self.ask_confirm(f"Install platform {platform_folder.name}?")
                        try:
                            _LOGGER.info(f"Installing platform {platform_folder.name}")
                            self._install_platform_zipinfo(zip_file.getinfo(platform_folder.at))
                        except NegativeConfirmation:
                            pass
                        except Exception as exce:
                            _LOGGER.error(f"Could not install platform {platform_folder.name}", exc_info=exce)
                _LOGGER.info("Platforms installed")


            if (zip_path / INKBOARD_PACKAGE_INTERNAL_FOLDER / "integrations").exists():
                _LOGGER.info("Installing integrations")
                for integration_folder in (zip_path / INKBOARD_PACKAGE_INTERNAL_FOLDER / "integrations").iterdir():
                    
                    with suppress(NegativeConfirmation):
                        self.ask_confirm(f"Install integration {integration_folder.name}?")
                        try:
                            _LOGGER.info(f"Installing integration {integration_folder.name}")
                            self._install_integration_zipinfo(zip_file.getinfo(integration_folder.at))
                        except Exception as exce:
                            _LOGGER.error(f"Could not install integration {integration_folder.name}", exc_info=exce)
                _LOGGER.info("Integrations installed")

            if (zip_path / "configuration").exists():
                _LOGGER.info(f"Extracting configuration folder to current working directory {Path.cwd()}")
                ##First extract, then find requirements.txt file
                
                self.extract_zip_folder(zip_file.getinfo((zip_path / "configuration").at),
                                        allow_overwrite=True, just_contents=True)

                self.install_config_requirements(Path.cwd())

            _LOGGER.info("Package succesfully installed")
            return
        
    def install_platform(self):
        """Installs a platform type .zip file file
        """           
        file = self._file

        if self._package_type != 'platform':
            raise TypeError(f"{file} is not a platform type .zip file")
        
        with zipfile.ZipFile(file) as zip_file:
            self.__zip_file = zip_file
            zip_path = zipfile.Path(zip_file)
            p = list(zip_path.iterdir())[0]
            self._install_platform_zipinfo(zip_file.getinfo(p.at))
        
        return
    
    def install_integration(self):
        """Installs an integration type .zip file file
        """   
        
        file = self._file

        if self._package_type != 'integration':
            raise TypeError(f"{file} is not an integration type .zip file")
        
        with zipfile.ZipFile(file) as zip_file:
            self.__zip_file = zip_file
            zip_path = zipfile.Path(zip_file)
            p = list(zip_path.iterdir())[0]
            self._install_integration_zipinfo(zip_file.getinfo(p.at))
        
        return

    def install_config_requirements(self, config_file: Union[str,Path]):
        """Installs requirements for the passed config_file

        If config_file is a .yaml file it will use the folder the file is in. If is it a folder, that folder be used as a base.
        The function looks for requirements.txt files in the 'config folder' itself, in 'config folder/files' (but only the top folder), and recursively in 'config folder/custom' (i.e. it goes through all files in all folders within there and installs every requirements.txt it finds)
        Afterwards, it will look in 'config folder/custom/integrations' and install all requirements for all integrations, as well as prompt for optional requirements if a function is supplied.

        Parameters
        ----------
        config_file : Union[str,Path]
            The yaml file from which to get the base folder, or the base folder itself
        skip_confirmations : bool, optional
            Instructs pip to not prompt for confirmations when installing, by default False
        confirmation_function : Callable[[str],bool], optional
            Function to call when optional requirements can be installed, by default `confirm_input` (command line prompt). If a boolean `False` is returned, or a `NegativeConfirmation` error is raised, the optional requirements are not installed.
        """        

        skip_confirmations = self._skip_confirmations

        if isinstance(config_file,str):
            config_file = Path(config_file)
        
        if config_file.is_file():
            assert config_file.suffix in CONFIG_FILE_TYPES, "Config file must be a yaml file"
            path = config_file.parent
        else:
            path = config_file
        
        if (path / "custom").exists():
            if (path / REQUIREMENTS_FILE).exists():
                self.pip_install_requirements_file(path / REQUIREMENTS_FILE, skip_confirmations)
            
            if (path / "files" / REQUIREMENTS_FILE).exists():
                self.pip_install_packages(path / "files" / REQUIREMENTS_FILE, skip_confirmations)

            folder = path / "custom"
            for foldername, subfolders, filenames in os.walk(folder):
                if REQUIREMENTS_FILE in filenames:
                    file_path = os.path.join(foldername, REQUIREMENTS_FILE)
                    self.pip_install_requirements_file(file_path, skip_confirmations)
            
            if (folder / "integrations").exists():
                for integration_folder in (folder / "integrations").iterdir():
                    with open(integration_folder / packageidfiles["integration"]) as f:
                        integration_conf: manifestjson = json.load(f)

                    if reqs := integration_conf.get("requirements", []):
                        _LOGGER.info(f"Installing requirements for custom integration {integration_folder.name}")
                        res = self.pip_install_packages(*reqs, no_input=skip_confirmations)

                        if res.returncode != 0: 
                            _LOGGER.error(f"Something went wrong installing requirements for custom integration {integration_folder.name}")
                            continue
                    
                    for opt_req, reqs in integration_conf.get("optional_requirements", {}).items():
                        with suppress(NegativeConfirmation):
                            msg = f"Install requirements for optional features {opt_req} for custom integration {integration_folder.name}?"

                            if self._confirmation_function:
                                if not self._confirmation_function(msg, self):
                                    continue
                            self.pip_install_packages(*reqs, no_input=skip_confirmations)

    def _install_platform_zipinfo(self, platform_info: zipfile.ZipInfo):
        
        assert platform_info.is_dir(),"Platforms must be a directory"

        platform_zippath = zipfile.Path(self.__zip_file, platform_info.filename)
        platform = platform_zippath.name 

        # with self.__zip_file.open(f"{platform_info.filename}{packageidfiles['platform']}") as f:
        f = self.__zip_file.open(f"{platform_info.filename}{packageidfiles['platform']}")
        platform_conf: platformjson = json.load(f)
        platform_version = parse_version(platform_conf['version'])

        install = True
        ib_requirements = platform_conf["inkboard_requirements"]

        if not self.check_inkboard_requirements(ib_requirements, f"Platform {platform}"):
            msg = f"inkBoard requirements for platform {platform} are not met (see logs). Continue installing?"
            self.ask_confirm(msg)

        if (INKBOARD_FOLDER / "platforms" / platform).exists():
            
            with open(INKBOARD_FOLDER / "platforms" / platform / packageidfiles["platform"]) as f:
                cur_conf: platformjson = json.load(f)
                cur_version = parse_version(cur_conf['version'])
            
            if cur_version > platform_version:
                msg = f"Version {cur_version} of platform {platform} is currently installed. Do you want to install earlier version {platform_version}?"
                self.ask_confirm(msg)

            elif platform_version > cur_version:
                _LOGGER.info(f"Updating platform {platform} from version {cur_version} to {platform_version}.")
            else:
                msg = f"Version {platform_version} of platform {platform} is already installed. Do you want to overwrite it?"
                self.ask_confirm(msg)

        if not install:
            _LOGGER.info(f"Not installing platform {platform} {platform_version}")
            return
        
        _LOGGER.info(f"Installing new platform {platform}, version {platform_version}")
        if self.install_platform_requirements(platform,platform_conf):
            self.extract_zip_folder(platform_info, path = INKBOARD_FOLDER / "platforms", allow_overwrite=True)
            _LOGGER.info("Extracted platform file")
        return

    def _install_integration_zipinfo(self, integration_info: zipfile.ZipInfo):
        
        assert integration_info.is_dir(),"Integrations must be a directory"

        integration_zippath = zipfile.Path(self.__zip_file, integration_info.filename)
        integration = integration_zippath.name

        manifestpath = integration_zippath / packageidfiles['integration']
        f = manifestpath.open()
        integration_conf: manifestjson = json.load(f)
        integration_version = parse_version(integration_conf['version'])

        install = True
        ib_requirements = integration_conf.get("inkboard_requirements",{})

        if ib_requirements and not self.check_inkboard_requirements(ib_requirements, f"Integration {integration}"):
            msg = f"inkBoard requirements for integration {integration} are not met (see logs). Continue installing?"
            self.ask_confirm(msg)

        if (INKBOARD_FOLDER / "integrations" / integration).exists():
            
            with open(INKBOARD_FOLDER / "integrations" / integration / packageidfiles["integration"]) as f:
                cur_conf: manifestjson = json.load(f)
                cur_version = parse_version(cur_conf['version'])
            
            if cur_version > integration_version:
                msg = f"Version {cur_version} of Integration {integration} is currently installed. Do you want to install earlier version {integration_version}?"
                self.ask_confirm(msg)

            elif integration_version > cur_version:
                _LOGGER.info(f"Updating Integration {integration} from version {cur_version} to {integration_version}.")
            else:
                msg = f"Version {integration_version} of Integration {integration} is already installed. Do you want to overwrite it?"
                self.ask_confirm(msg)

        if not install:
            _LOGGER.info(f"Not installing Integration {integration} {integration_version}")
            return

        if self.install_integration_requirements(integration, integration_conf):
            self.extract_zip_folder(integration_info, path = INKBOARD_FOLDER / "integrations", allow_overwrite=True)
            _LOGGER.info("Extracted integration files")

    def extract_zip_folder(self, member: Union[str,zipfile.ZipInfo], path: Union[str,Path,None] = None, pwd: str = None, just_contents: bool = False, allow_overwrite: bool = False):
        """Extracts a folder and all it's contents from a ZipFile object to path.

        Parameters
        ----------
        member : zipfile.ZipInfo
            The name or ZipInfo object of the folder to extract
        path : _type_, optional
            The path to extract the folder to, by default None (which extracts to the current working directory)
        just_contents : bool
            Extract the contents of the folder directly to path, instead of extracting the folder itself, defaults to `False`
        pwd : str, optional
            Optional password for the archive, by default None
        allow_overwrite : bool
            Allows overwriting existing files or folders
        """        

        if isinstance(member, str):
            member = self.__zip_file.getinfo(member)

        assert member.is_dir(),"Member must be a directory"

        ##Gotta put it all in a temporary directory to isolate the folder correctly
        with tempfile.TemporaryDirectory() as tempdir:
            self.__zip_file.extract(member, tempdir, pwd)
            for file in self.__zip_file.namelist():
                if file.startswith(member.orig_filename) and file != member.orig_filename:
                    self.__zip_file.extract(file, tempdir, pwd)
            _LOGGER.verbose(f"Extracted folder {member.orig_filename} to temporary directory")

            if path == None:
                path = Path.cwd()
            
            if just_contents:
                src = Path(tempdir) / Path(member.orig_filename)
            else:
                src = Path(tempdir) / Path(member.orig_filename).parent

            shutil.copytree(
                src = src,
                dst = path,
                dirs_exist_ok = allow_overwrite
            )
        _LOGGER.debug("Copied from tempdir")
        ##What happens here with nested stuff? I.e. internal folders -> check with package extraction
        
        return

    @classmethod
    def gather_inkboard_packages(cls) -> dict[Path, packagetypes]:
        """Gathers all inkBoard viable packages availables in the current working directory

        Returns
        -------
        dict[Path, packagetypes]
            Dict with all the path objects of all found packages and their package type
        """

        _LOGGER.info(f"Gathering inkBoard zip packages in {Path.cwd()}")

        packs = {}
        for file in Path.cwd().glob('*.zip'):
            if file.suffix != ".zip":
                continue

            if p := cls.identify_zip_file(file):
                packs[file] = p
        
        _LOGGER.info(f"Found {len(packs)} inkBoard installable zip packages.")
        return packs
    
    @classmethod
    def identify_zip_file(cls, file: Union[str, Path, zipfile.ZipFile]) -> Optional[packagetypes]:
        """Identifies the type of inkBoard package the zip file is

        Parameters
        ----------
        file : Union[str, Path]
            The file to identify. Must be a .zip file.

        Returns
        -------
        Optional[packagetypes]
            The type of package this file is (package, integration or platform), or None if it could not be identified.

        Raises
        ------
        TypeError
            Raised if the provided file is not a zipfile
        """        


        if not isinstance(file, zipfile.ZipFile):
            zip_file = cls._path_to_zipfile(file)
            zip_file.close()
        else:
            zip_file = file
        
        p = zipfile.Path(zip_file)
        root_files = [f for f in p.iterdir()]

        if len(root_files) == 1 and root_files[0].is_dir():
            ##Look in the single folder and whether it contains a manifest or platform json
            if (root_files[0] / packageidfiles["integration"]).exists():
                return 'integration'
            elif (root_files[0] / packageidfiles["platform"]).exists():
                return 'platform'
        elif (p / packageidfiles["package"]).exists() and (len(root_files) in {2,3}):  ##2 or 3: at least contains package.json, and has .inkBoard and/or configuration folder
            return 'package'

        return

    @staticmethod
    def _path_to_zipfile(file: Union[str, Path]) -> zipfile.ZipFile:
        """Converts a path string or Path object to a `zipfile.ZipFile` object

        Parameters
        ----------
        file : Union[str, Path]
            The file to open

        Returns
        -------
        zipfile.ZipFile
            The corresponding ZipFile object

        Raises
        ------
        TypeError
            Raised if the file is not a .zip file
        """        

        if isinstance(file, str):
            file = Path(file)

        if file.suffix != '.zip':
            raise TypeError("File must be a .zip file")
        else:
            return zipfile.ZipFile(file, 'r')



class InternalInstaller(BaseInstaller):
    "Handles installing requirements already installed platforms and integrations."
    def __init__(self, install_type: internalinstalltypes, name: str, skip_confirmations = False, confirmation_function = None):
        ##May remove the subclassing, but just reuse the usable functions (i.e. seperate out a few funcs.)
        ##Also, use the constant designer mod in case something is not found internally.
        ##Do give a warning for platforms though, or integrations without a designer module.
        if install_type == "integration":
            file = Path("integrations") / name
        elif install_type == "platform":
            file = Path("platforms") / name

        full_path = INKBOARD_FOLDER / file
        if not const.DESIGNER_INSTALLED:
            assert full_path.exists(), f"{install_type} {name} is not installed or does not exist"
        else:
            if not full_path.exists():
                assert (const.DESIGNER_FOLDER / file).exists(),  f"{install_type} {name} is not installed or does not exist"
                full_path = const.DESIGNER_FOLDER / file

        self._name = full_path.name
        self._full_path = full_path
        self._confirmation_function = confirmation_function
        self._skip_confirmations = skip_confirmations
        self._install_type = install_type
        return
    
    def install(self):
        if self._install_type == "integration":
            return self.install_integration()
        elif self._install_type == "platform":
            return self.install_platform()

    def install_platform(self):

        with open(self._full_path / packageidfiles["platform"]) as f:
            conf: platformjson = json.load(f)
            
        with suppress(NegativeConfirmation):
            msg = f"Install platform {self._name}?"
            self.ask_confirm(msg)
            return self.install_platform_requirements(self._name, conf)
        return 1

    def install_integration(self):
        with open(self._full_path / packageidfiles["integration"]) as f:
            conf: platformjson = json.load(f)
        
        with suppress(NegativeConfirmation):
            msg = f"Install integration {self._name}?"
            self.ask_confirm(msg)
            return self.install_integration_requirements(self._name, conf)
        return 1
