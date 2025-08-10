"""Functions to download stuff from the package index
Trying to implement this without using requests
"""
from typing import (
    Union,
    Literal,
    TYPE_CHECKING,
    Final,
    overload,
    ClassVar,
)
from types import MappingProxyType
import urllib.request
from pathlib import Path
import os
from datetime import datetime as dt
from datetime import timedelta
import json
import tempfile

from inkBoard import logging
from inkBoard.constants import INKBOARD_FOLDER

from .types import (
    PackageIndex,
    branchtypes,
)
from .constants import (
    PACKAGE_INDEX_URL,
    INTERNAL_PACKAGE_INDEX_FILE,
    INDEX_FILE_PATH,
    REPO_INDEX_FILE,
)

if TYPE_CHECKING:
    from .version import Version

_LOGGER = logging.getLogger(__name__)
##For the logger here, maybe use a seperate format?
##Or at least for the info logs

##See this repo: https://github.com/fbunaren/GitHubFolderDownloader
##And this gist: https://gist.github.com/oculushut/193a7c2b6002d808a791

packagebranchtypes = ("main", "dev")

#FIXME clean up this class. Remove unused type hints, methods etc. Move required methods to the installer.
class Downloader:
    """Helper class for downloading inkBoard packages.
    
    Instantiating this class IMMEDIATELY starts the download.
    Use the `download` or `repo_download` classmethods instead.
    `PackageIndexInstaller().download` provides a user friendly wrapper to interface with this class too (i.e. for validation of packages etc).
    """


    destination_folder : Path
    "Folder where downloaded files are put. Usually a temporary folder"

    package_index : PackageIndex = {}
    "inkBoard package index with information on package versions"

    index_file : ClassVar[Path] = INKBOARD_FOLDER / "files" / INTERNAL_PACKAGE_INDEX_FILE

    file_location : Path
    "Location (with file name) of the downloaded file. `None` until the download has been succesfull."

    file_name : str
    "Name of the downloaded file. `None` until the download has been succesfull."

    _last_index_change : ClassVar[str] = None

    @property
    def destination(self) -> Path:
        return self.destination_folder / self.destination_file

    # _index_downloaded : bool = False
    #Indicate whether the index has been updated for this instance of the downloader
    #Means it can be updated i.e. when asking to download a package of which the version is supposedly already up to date
    #Currently commented out to test classmethod downloading (which simply checks if the index is outdated)

    ##Some stuff to test:
    ##Invalid url (i.e. invalid name thing)
    ##No internet
    ##Mainly just to know what the errors are
    def __init__(self):

        return
    
    def verify_destination(self, destination : Union[str, Path] = None, *, destination_folder : Union[str, Path] = None, destination_file : Union[str, Path] = None):
        if destination is None and (destination_folder is None or destination_file is None):
            raise ValueError("Pass both a destination folder and destination file when not specifying destination")
        elif destination is not None:
            if (destination_folder is not None or destination_file is not None):
                raise ValueError("Specifying a destination folder or destination file is not allowed when passing destination")
            destination = Path(destination)
            destination_folder = destination.parents
            destination_file = destination.name

        self.destination_folder = Path(destination_folder)
        
        if not self.destination_folder.is_dir():
            if self.destination_folder.exists():
                raise FileNotFoundError(f"Destination {self.destination_folder} is not a folder")
            else:
                raise FileNotFoundError(f"Destination folder {self.destination_folder} does not exist")
        
        self.destination_file = Path(destination_file)
        if len(self.destination_file.parts) != 1:
            raise ValueError(f"Destination file cannot have more than 1 part, {self.destination_file} is invalid")

        if (self.destination_folder / self.destination_file).exists():
            raise FileExistsError(f"File {(self.destination_folder / self.destination_file)} exists")
        return
    
    def safe_instance_download(self, url : str, destination : Union[str, Path] = None, *, destination_folder : Union[str, Path] = None, destination_file : Union[str, Path] = None):
        """Verifies the destination and downloads the url's contents if it is available.

        Parameters
        ----------
        url : str
            The url to retrieve
        destination : Union[str, Path], optional
            Full destination path, by default None
        destination_folder : Union[str, Path], optional
            Destination folder, ignored if destination is specified, by default None
        destination_file : Union[str, Path], optional
            File name within the destination_folder, ignored if destination is specified, by default None

        Returns
        -------
        None
        """        
        self.verify_destination(destination, destination_folder, destination_file)
        return self._unsafe_instance_download(url)

    def _unsafe_instance_download(self, url : str):
        self.file_location = self._download_url_request(url, self.destination)
        self.file_name = self.file_location.name

    @overload
    @classmethod
    def download(cls, url : str, destination : Union[str,Path]) -> Path:
        """Downloads contents from the provided url to the given destination

        Parameters
        ----------
        url : str
            The url to retrieve the contents from
        destination : Union[str,Path]
            Destination the contents, including filename

        Returns
        -------
        Path
            The location of the retrieved contents
        """   

    @overload
    @classmethod
    def download(cls, url : str, destination_folder : Union[str,Path], destination_file : Union[str, Path]) -> Path:
        """Downloads contents from the provided url to the given destination

        Parameters
        ----------
        url : str
            The url to retrieve the contents from
        destination_folder : Union[str,Path]
            Destination folder of the contents
        destination_file : Union[str, Path]
            Filename of the retrieved contents

        Returns
        -------
        Path
            The location of the retrieved contents
        """        

    @classmethod
    def download(cls, url : str, **destination_kwargs) -> Path:
        ins = cls()
        ins.safe_instance_download(url, **destination_kwargs)
        return ins.file_location
    
    @overload
    @classmethod
    def repo_download(cls, repo_url : str, branch : str, repo_file : str, destination): ...
        
    @overload
    @classmethod
    def repo_download(cls, repo_url : str, branch : str, repo_file : str, destination): ...

    @classmethod
    def repo_download(cls, repo_url : str, branch : str, repo_file : str, **destination_kwargs):
        """Download a file from a repository to the given destination

        Parameters
        ----------
        repo_url : str
            The url linke to the github repository
        branch : str
            The branch of the repo to download from
        repo_file : str
            The path to the file within the repo

        Returns
        -------
        Path
            Path to the downloaded file
        """
        url = cls.repo_raw_file_url(repo_file, branch, repo_url)
        destination_kwargs.setdefault("destination_file", Path(repo_file).name)
        return cls.download(url, **destination_kwargs)

    #[ ] See if all these functions can be turned into classmethods so they can be called independently
    def _download_integration_package(self, name : str, package_branch : branchtypes = "main", version : str = "") -> Path:
        filename, package_url = self._make_download_url(name, "integrations", package_branch, version)
        return self._download_url_request(package_url, filename)

    def _download_platform_package(self, name : str, package_branch : branchtypes = "main", version : str = ""):
        #[ ] for platforms, ask to copy files like readme etc. into the current working directory?
        filename, package_url = self._make_download_url(name, "platforms", package_branch, version)
        return self._download_url_request(package_url, filename)

    def _make_download_url(self, package_name : str, package_type : Literal["integrations", "platforms"], package_branch: branchtypes, version : str = ''):
        """Creates the raw url for a platform or integration package

        Parameters
        ----------
        package_name : str
            The name of the package
        package_type : Literal[&quot;integrations&quot;, &quot;platforms&quot;]
            Type of package, either integration or platform
        package_branch : branchtypes
            The inkBoard branch to download from. Not relevant when version is specified
        version : str
            Specific version to get

        Returns
        -------
        tuple[str, str]
            The filename and corresponding url of the package

        Raises
        ------
        ValueError
            _description_
        KeyError
            _description_
        ValueError
            _description_
        ValueError
            _description_
        """        
        
        #create the raw_url for a package
        
        #"https://github.com/Slalamander/inkBoard-package-index/raw/refs/heads/main/platforms/desktop0.0.2.zip"
        if package_branch not in ("main","dev"):
            raise ValueError(f"branch must be one of {packagebranchtypes}, you passed {package_branch}")

        if not self.package_index:
            self.get_package_index()

        if package_name not in self.package_index[package_type]:
            raise KeyError(f"Integration {package_name} is not known in the package index")

        if version:
            _LOGGER.warning(f"Downloading archived versions is not available (yet). Download of {package_name} will fail if the version is not the newest one in the <main> or <dev> branch.")
            if version == self.package_index[package_type][package_name]["main"]["version"]:
                fileversion = version
            elif version == self.package_index[package_type][package_name]["dev"]["version"]:
                fileversion = f"{version}_dev"
            else:
                # _LOGGER.warning(f"Downloading archived versions is not available (yet). Download of {name} will fail if the version is not the newest one in the <main> or <dev> branch.")
                _LOGGER.error("Downloading archived components is not available yet.")
                raise ValueError("Downloading archived components is not available yet.")
                if package_branch == "dev" or version.count(".") >= 3:
                    ##main versions should be 0.2.5 etc. For dev, it may be 0.2.5.dev1 etc.
                    ##If it's more something went wrong tbf lol
                    ##Minor versions **should** end up in the main index too.
                    _LOGGER.debug(f"appending _dev suffix to {package_name} version {version} for package handling")
                    fileversion = f"{version}_dev"
                    raise ValueError("I don't think it should be handled like this for specific versions")
                    ##Basically: for versions if specified, check if it is the main version -> prefer
                    ##If dev version -> well you know it's the dev version
                    ##Otherwise, there will be a dev/main folder in the repo that handles those and which should be set via the package_type honestly?
                    ##Or should there be a check in the indexer whether a dev version is elligeble?

        else:
            fileversion = self.package_index[package_type][package_name][package_branch]
            if package_branch == "dev":
            # version =
                fileversion = f"{fileversion}_dev"
        
        filename = f"{package_name}-{fileversion}.zip"
        filepath = f"/{package_type}/{package_name}/{filename}"

        raw_url = self.repo_raw_file_url(filepath, package_branch)
        return filename, raw_url

    @staticmethod
    def _download_url_request(url : str, dest : Union[Path,str]) -> Path:
        """Downloads what is retrieved from url to the destination of the Downloader instance

        Silently overwrites anything if the file already exists!

        Parameters
        ----------
        url : str
            The url to retrieve

        Returns
        -------
        Path
            _description_
        """

        # dest = self.destination_folder / self.destination_file
        loc, _ = urllib.request.urlretrieve(url, filename=dest)
        download_path = Path(loc)
        _LOGGER.debug(f"Successfully downloaded {url} to {download_path}")
        return download_path
            ##From here an installer instance can be created I think? Since that one reidentifies the package anyways

    @classmethod
    def _download_package_index(cls, *, _destination_file : Union[Path, str] = None):
        if _destination_file == None:
            _destination_file = INDEX_FILE_PATH
        _LOGGER.info("Getting inkBoard package index from github")
        raw_url = cls.repo_raw_file_url(REPO_INDEX_FILE)
        cls._download_url_request(raw_url, _destination_file)
        _LOGGER.info("Updated inkBoard package index")

    @staticmethod
    def repo_raw_file_url(file : str, branch = "main", repo_url : str = PACKAGE_INDEX_URL) -> str:
        """Returns the link to the raw version of the file on github

        Parameters
        ----------
        file : str
            The path to the file to download
        branch : str, optional
            The branch of the repo to get the file from, by default "main"
        repo_url : str
            url to the repo. Defaults to the inkBoard package index

        Returns
        -------
        str
            url to the raw version (raw.githubusercontent) of the file
        """
        assert repo_url.startswith("https://github.com"), "repo_url must start with `https://github.com`"
        repo_url = repo_url.removesuffix("/")
        raw_base_url = repo_url.replace("github.com", "raw.githubusercontent.com")
        return raw_base_url + "/refs/heads/" + branch + "/" + file
