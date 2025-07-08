"Handles inkBoard packages, both creating and installing them."

import asyncio
from typing import TYPE_CHECKING, Union
from pathlib import Path

import inkBoard
# from inkBoard.types  import *
from inkBoard import constants as bootstrap
from .types import internalinstalltypes


if TYPE_CHECKING:
    from inkBoard import CORE as CORE

_LOGGER = inkBoard.getLogger(__name__)
_LOGGER.warning("Dont forget to write tests fro this")

def confirm_input(msg: str):
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
    from .package import Packager

    if pack_all:
        Packager(core).create_package(name)
    else:
        pack = []
        if config: pack.append("configuration")
        if platform: pack.append("platform")
        if integrations: pack.append('integration')

        Packager(core).create_package(name, pack)
    return 0


def run_install_command(file: str, name: str, no_input: bool):
    ##Add functionality to installer for internal installs (platforms and integrations)
    ##Usage: install [platform/integration] [name]

    if file in internalinstalltypes.__args__:
        return install_internal(file, name, no_input)
    else:
        return install_packages(file, no_input)

def install_internal(install_type: str, name:str, no_input: bool = False):
    from .install import InternalInstaller
    return InternalInstaller(install_type, name, no_input, confirm_input).install()

def install_packages(file: Union[str, Path] = None, no_input: bool = False):
    
    ##https://gist.github.com/oculushut/193a7c2b6002d808a791
    ##Found this gist, that may allow downloading files from github
    ##Would make installing integrations and platforms A LOT more user friendly
    ##Especially when simply needing to update
    ##Better yet, see this code: https://github.com/fbunaren/GitHubFolderDownloader
    ##Only relies on requests. That is a library I am a-okay with implementing
    from .install import PackageInstaller
    if file:
        return PackageInstaller(file, skip_confirmations=no_input, confirmation_function=confirm_input).install()
    else:
        packages = PackageInstaller.gather_inkboard_packages()

        print(f"Found {len(packages)} {'package' if len(packages) == 1 else 'packages'} that can be installed")
        for package in packages:
            ##Add a confirmation message for each file.
            PackageInstaller(package, skip_confirmations=no_input, confirmation_function=confirm_input).install()
        return 0



