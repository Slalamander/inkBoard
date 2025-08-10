"Functions for installing inkBoard packages"

from typing import (
    TYPE_CHECKING,
    Callable,
    Union,
    ClassVar,
    Optional,
    Literal,
    Final,
    get_args,
)
from types import MappingProxyType
from abc import abstractmethod
from contextlib import suppress
import json
import subprocess
import sys
import zipfile
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime as dt

from inkBoard import logging
from inkBoard.types import (
    platformjson,
    manifestjson,
    inkboardrequirements,
)
from inkBoard.constants import (
    INKBOARD_FOLDER,
    CONFIG_FILE_TYPES,
    DESIGNER_INSTALLED,
    DESIGNER_FOLDER
)

from .types import (
    packagetypes,
    PackageDict,
    PackageIndex,
    NegativeConfirmation,
    internalinstalltypes,
)
from .constants import (
    PACKAGE_ID_FILES,
    INKBOARD_PACKAGE_INTERNAL_FOLDER,
    REQUIREMENTS_FILE,
    INDEX_PACKAGE_KEYS,
    PACKAGETYPE_TO_INDEX_KEY,
    INDEX_KEY_TO_PACKAGETYPE,
    INTERNAL_PACKAGE_INDEX_FILE,
)
from .version import (
    InkboardVersion,
    PSSMVersion,
    parse_version,
    compare_versions,
    get_comparitor_string,
    split_comparison_string
    )
from .download import Downloader

_LOGGER = logging.getLogger(__name__)

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
                with open(INKBOARD_FOLDER / "platforms" / platform / PACKAGE_ID_FILES["platform"]) as f:
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
                with open(INKBOARD_FOLDER / "integrations" / integration / PACKAGE_ID_FILES["integration"]) as f:
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
class InternalInstaller(BaseInstaller):
    """Handles installing requirements of already installed platforms and integrations.
    
    I.e. used to call the appropriate `pip install ...` commands
    """
    def __init__(self, install_type: internalinstalltypes, name: str, skip_confirmations = False, confirmation_function = None):
        ##May remove the subclassing, but just reuse the usable functions (i.e. seperate out a few funcs.)
        ##Also, use the constant designer mod in case something is not found internally.
        ##Do give a warning for platforms though, or integrations without a designer module.
        if install_type == "integration":
            file = Path("integrations") / name
        elif install_type == "platform":
            file = Path("platforms") / name

        full_path = INKBOARD_FOLDER / file
        if not DESIGNER_INSTALLED:
            assert full_path.exists(), f"{install_type} {name} is not installed or does not exist"
        else:
            if not full_path.exists():
                assert (DESIGNER_FOLDER / file).exists(),  f"{install_type} {name} is not installed or does not exist"
                full_path = DESIGNER_FOLDER / file

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

        with open(self._full_path / PACKAGE_ID_FILES["platform"]) as f:
            conf: platformjson = json.load(f)
            
        with suppress(NegativeConfirmation):
            msg = f"Install platform {self._name}?"
            self.ask_confirm(msg)
            return self.install_platform_requirements(self._name, conf)
        return 1

    def install_integration(self):
        with open(self._full_path / PACKAGE_ID_FILES["integration"]) as f:
            conf: platformjson = json.load(f)
        
        with suppress(NegativeConfirmation):
            msg = f"Install integration {self._name}?"
            self.ask_confirm(msg)
            return self.install_integration_requirements(self._name, conf)
        return 1

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

    def __init__(self,
                file: Union[Path,str], 
                package_type : Literal[None, "integration", "platform", "package", "configuration"] = None,
                skip_confirmations: bool = False, confirmation_function: Callable[[str, 'BaseInstaller'],bool] = None,
                ):
        self._file = Path(file)
        assert self._file.exists(), f"{file} does not exist"
        self._confirmation_function = confirmation_function
        self._skip_confirmations = skip_confirmations

        if package_type is not None:
            self._package_type = package_type
        elif self._file.suffix in CONFIG_FILE_TYPES:
            self._package_type = "configuration"
        else:
            self._package_type: packagetypes = self.identify_package_type(self._file)
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
        else:
            raise ValueError(f"Unknown package_type given: {self._package_type}")

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
            f = zip_file.open(PACKAGE_ID_FILES["package"])
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
                    with open(integration_folder / PACKAGE_ID_FILES["integration"]) as f:
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

        f = self.__zip_file.open(f"{platform_info.filename}{PACKAGE_ID_FILES['platform']}")
        platform_conf: platformjson = json.load(f)
        platform_version = parse_version(platform_conf['version'])

        install = True
        ib_requirements = platform_conf["inkboard_requirements"]

        if not self.check_inkboard_requirements(ib_requirements, f"Platform {platform}"):
            msg = f"inkBoard requirements for platform {platform} are not met (see logs). Continue installing?"
            self.ask_confirm(msg)

        if (INKBOARD_FOLDER / "platforms" / platform).exists():
            #[ ]: Implement the self._path_to_platform function here
            with open(INKBOARD_FOLDER / "platforms" / platform / PACKAGE_ID_FILES["platform"]) as f:
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

        manifestpath = integration_zippath / PACKAGE_ID_FILES['integration']
        f = manifestpath.open()
        integration_conf: manifestjson = json.load(f)
        integration_version = parse_version(integration_conf['version'])

        install = True
        ib_requirements = integration_conf.get("inkboard_requirements",{})

        if ib_requirements and not self.check_inkboard_requirements(ib_requirements, f"Integration {integration}"):
            msg = f"inkBoard requirements for integration {integration} are not met (see logs). Continue installing?"
            self.ask_confirm(msg)

        # if (INKBOARD_FOLDER / "integrations" / integration).exists():
        if p := self._path_to_integration(integration):
            
            # with open(INKBOARD_FOLDER / "integrations" / integration / PACKAGE_ID_FILES["integration"]) as f:
            with open(p / PACKAGE_ID_FILES["integration"]) as f:
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

            if p := cls.identify_package_type(file):
                packs[file] = p
        
        _LOGGER.info(f"Found {len(packs)} inkBoard installable zip packages.")
        return packs
    
    @classmethod
    def identify_package_type(cls, file: Union[str, Path, zipfile.ZipFile]) -> Optional[packagetypes]:
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
            if (root_files[0] / PACKAGE_ID_FILES["integration"]).exists():
                return 'integration'
            elif (root_files[0] / PACKAGE_ID_FILES["platform"]).exists():
                return 'platform'
        elif (p / PACKAGE_ID_FILES["package"]).exists() and (len(root_files) in {2,3}):  ##2 or 3: at least contains package.json, and has .inkBoard and/or configuration folder
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

    @staticmethod
    def _path_to_platform(platform : str, check_designer : bool = False) -> Union[Path, None]:
        """Get the path to the given platform, or None if it is not installed.
        
        If `check_designer` is true, the designer folder will be checked if it cannot be found in the base inkBoard folder.
        """
        f = INKBOARD_FOLDER / "platforms" / platform
        if f.exists():
            return f
        elif check_designer and DESIGNER_FOLDER:
            f = DESIGNER_FOLDER / "platforms" / platform
            if f.exists():
                return f
        return None
    
    @staticmethod
    def _path_to_integration(integration : str, check_designer : bool = False) -> Union[Path, None]:
        f = INKBOARD_FOLDER / "integrations" / integration
        if f.exists():
            return f
        elif check_designer and DESIGNER_FOLDER:
            f = DESIGNER_FOLDER / "integrations" / integration
            if f.exists():
                return f
        return None
    #FIXME add function that gets the current version of a platform/integration (perhaps in the base installer)

class PackageIndexInstaller(PackageInstaller):
    "Handles installing packages from the package index"

    index_file : ClassVar[Path] = INKBOARD_FOLDER / "files" / INTERNAL_PACKAGE_INDEX_FILE


    def __init__(self, 
                name : str,
                package_type : packagetypes = None,
                skip_confirmations : bool = False,
                confirmation_function = None):
        self.downloaded = False

        if get_comparitor_string(name):
            name, cmp, version = split_comparison_string(name)
            self.package_name = name
            self._comparison_string = cmp
            self.version = version
        else:
            self.package_name = name
            self._comparison_string = None
            self.version = None

        if package_type is None:
            package_type = self.identify_package_type(name)
        else:
            self.verify_package(self.package_name, package_type)
        # super().__init__(name, package_type, skip_confirmations, confirmation_function)

    def install(self, download_folder : Union[Path, str, None] = None):
        ##Ensure first that download has taken place succesfully
        ##Then run super().install after setting the file

        #So structure:
        #   - Get the index
        #   - Check if the wanted package is already installed, if so, compare the version to the index version
        #   - set up a tempdir, pass as destination folder (Optionally enable using a common tempdir)
        #   - download package, set file location to file
        #   - run super().install()

        if not self.downloaded:
            self.download()
        return super().install()
    
    def download(self, destination_folder : Union[Path, str]):
        dest = Path(destination_folder)
        self._downloader = Downloader(
            dest, 
        )
        self.downloaded = True
        return
    
    def _install_with_tempdir(self):
        
        with tempfile.TemporaryDirectory() as tempdir:
            tempdir_path = Path(tempdir)
            self.install(tempdir_path)
        
        return

    @classmethod
    def get_package_index(cls, force_get = False) -> PackageIndex:
        """Gets the package index

        If the index file does not exist or is outdated, it will be downloaded.
        Only opens the index file if required.
        The index file is located internally in the `files` directory of inkBoard.

        Parameters
        ----------
        force_get : bool, optional
            Forces downloading and updating the index, by default False

        Returns
        -------
        PackageIndex
            The package index
        """        

        if force_get or cls.is_index_outdated():
            get_index = True
        else:
            get_index = False

        if get_index:
            Downloader._download_package_index()
            cls._last_index_change = os.path.getmtime(cls.index_file)

        if get_index or not cls.package_index:
            with open(cls.index_file) as f:
                package_index = MappingProxyType(PackageIndex(json.load(f)))
            
            cls.package_index : PackageIndex = package_index
        
        return cls.package_index

    @classmethod
    def is_index_outdated(cls) -> bool:
        """Determines if the index file is outdated depending on the time since it was last changed
        """

        if not cls.index_file.exists():
            return True
        else:
            last_change = cls._last_index_change
            if last_change is None:
                last_change = os.path.getmtime(cls.index_file)
            d = dt.now() - dt.fromtimestamp(last_change)
            if d.days != 0:
                return True
        return False

    @classmethod
    def verify_package(cls, name : str, package_type : str):
        p_index = cls.get_package_index()

        index_type = PACKAGETYPE_TO_INDEX_KEY.get(package_type, package_type)
        if index_type not in INDEX_PACKAGE_KEYS:
            raise KeyError(f"Unknown package type {package_type}, cannot be found in the package index")
        
        if name not in p_index[index_type]:
            raise FileNotFoundError(f"Package with name {name} does not exist in the {package_type} package index")
        
        return True

    @classmethod
    def identify_package_type(cls, name : str):
        
        p_index = cls.get_package_index()        
        if cmp := get_comparitor_string(name):
            package_name, _ = name.split(cmp)
        else:
            package_name = name

        index_type = None
        for k in INDEX_PACKAGE_KEYS:
            if package_name in p_index[k]:
                index_type = k
                break
        
        if index_type is None:
            raise FileNotFoundError(f"Cannot find anything matching the name {package_name} in the package index")
        
        package_type = INDEX_KEY_TO_PACKAGETYPE[index_type]
        return package_type