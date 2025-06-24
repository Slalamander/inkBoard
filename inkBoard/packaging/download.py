"""Functions to download stuff from the package index
Trying to implement this without using requests
"""
from typing import (
    Union,
    Literal,

)
import urllib.request
from pathlib import Path
import os
from datetime import datetime as dt
from datetime import timedelta
import json

from inkBoard import logging

from .types import (
    PackageIndex
)
from .constants import (
    PACKAGE_INDEX_URL,
    INTERNAL_PACKAGE_INDEX_FILE,
)

_LOGGER = logging.getLogger(__name__)
##For the logger here, maybe use a seperate format?
##Or at least for the info logs

##See this repo: https://github.com/fbunaren/GitHubFolderDownloader
##And this gist: https://gist.github.com/oculushut/193a7c2b6002d808a791

packagebranchtypes = ("main", "dev")

class Downloader:

    destination_folder : Path
    "Folder where downloaded files are put. Usually a temporary folder"

    index : PackageIndex
    "inkBoard package index with information on package versions"

    _index_downloaded : bool = False
    #Indicate whether the index has been updated for this instance of the downloader
    #Means it can be updated i.e. when asking to download a package of which the version is supposedly already up to date

    ##Some stuff to test:
    ##Invalid url (i.e. invalid name thing)
    ##No internet
    ##Mainly just to know what the errors are
    def __init__(self, destination_folder : Path):
        print(self._index_downloaded)
        self.destination_folder = destination_folder
    
    def get_package_index(self, force_get = False) -> dict:

        ##Internal file is NOT going to be put into the destination folder
        internal_file = self.destination_folder / INTERNAL_PACKAGE_INDEX_FILE

        get_index = False
        if force_get:
            get_index = True
        elif self._index_downloaded:
            get_index = False
        elif internal_file.exists():
            ##Check last changed (i.e. downloaded) time?
            last_change = os.path.getmtime(internal_file)
            d = dt.now() - dt.fromtimestamp(last_change)
            if d.days != 0:
                get_index = True
        else:
            get_index = True

        if get_index:
            self._download_package_index()
            self._index_downloaded = True

        with open(internal_file) as f:
            package_index = PackageIndex(json.load(f))
        
        self.index : PackageIndex = package_index
        return package_index

    def download_integration_package(self, name : str, package_type : Literal["main","dev"] = "main", version : str = ""):
        #"https://github.com/Slalamander/inkBoard-package-index/raw/refs/heads/main/platforms/desktop0.0.2.zip"
        if package_type not in ("main","dev"):
            raise ValueError(f"branch must be one of {packagebranchtypes}, you passed {package_type}")
        
        if not hasattr(self,"index"):
            self.get_package_index()

        if name not in self.index["integrations"]:
            raise KeyError(f"Integration {name} is not known in the package index")

        if version:
            ##Handle cases where _dev should be appended to it?
            _LOGGER.warning(f"Downloading custom versions is not available (yet). Download of {name} will fail if the version is not the newest one in the <main> or <dev> branch.")
            if package_type == "dev" or version.count(".") >= 3:
                ##main versions should be 0.2.5 etc. For dev, it may be 0.2.5.dev1 etc.
                ##If it's more something went wrong tbf lol
                ##Minor versions **should** end up in the main index too.
                _LOGGER.debug(f"appending _dev suffix to {name} version {version} for package handling")
                fileversion = f"{version}_dev"
                raise ValueError("I don't think it should be handled like this for specific versions")
                ##Basically: for versions if specified, check if it is the main version -> prefer
                ##If dev version -> well you know it's the dev version
                ##Otherwise, there will be a dev/main folder in the repo that handles those and which should be set via the package_type honestly?
                ##Or should there be a check in the indexer whether a dev version is elligeble?

            pass
        else:
            fileversion = self.index["integrations"][name][package_type]
            if package_type == "dev":
            # version =
                fileversion = f"{fileversion}_dev"
                pass

        raw_url = self._make_raw_file_link()
        return

    @classmethod
    def _download_package_index(cls, *, _destination_file : Union[Path, str] = None):
        if _destination_file == None:
            _destination_file = Path(__file__).parent / INTERNAL_PACKAGE_INDEX_FILE
        _LOGGER.info("Getting inkBoard package index from github")
        raw_url = cls._make_raw_file_link("index.json")
        cls._download_raw_file(raw_url, _destination_file)
        _LOGGER.info("Updated inkBoard package index")
        

    @staticmethod
    def _download_raw_file(raw_file_url : str, destination_file : str):

        filename, headers = urllib.request.urlretrieve(raw_file_url, filename=destination_file)
        _LOGGER.debug(f"Successfully downloaded {filename}")
        return filename, headers

    @staticmethod
    def _make_raw_file_link(file : str, branch = "main", repo_url : str = PACKAGE_INDEX_URL) -> str:
        """Returns the link to the raw file on github

        Parameters
        ----------
        file : str
            The path to the file to download
        branch : str, optional
            The brand of the repo to get the file from, by default "main"
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
