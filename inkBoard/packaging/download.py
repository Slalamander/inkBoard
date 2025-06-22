"""Functions to download stuff from the package index
Trying to implement this without using requests
"""
from typing import (
    Union,
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

##See this repo: https://github.com/fbunaren/GitHubFolderDownloader
##And this gist: https://gist.github.com/oculushut/193a7c2b6002d808a791

class Downloader:

    destination_folder : Path
    "Folder where downloaded files are put. Usually a temporary folder"

    index : PackageIndex
    "inkBoard package index with information on package versions"

    def __init__(self, destination_folder : Path):
        self.destination_folder = destination_folder
    
    def get_package_index(self, force_get = False) -> dict:

        ##Internal file is NOT going to be put into the destination folder
        internal_file = self.destination_folder / INTERNAL_PACKAGE_INDEX_FILE

        get_index = False
        if force_get:
            get_index = True
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

        with open(internal_file) as f:
            package_index = PackageIndex(json.load(f))
        
        self.index : PackageIndex = package_index
        return package_index

    @classmethod
    def _download_package_index(cls, *, _destination_file : Union[Path, str] = None):
        if _destination_file == None:
            _destination_file = Path(__file__).parent / INTERNAL_PACKAGE_INDEX_FILE
        raw_url = cls._make_raw_file_link(PACKAGE_INDEX_URL, "index.json")
        cls._download_raw_file(raw_url, _destination_file)

    @staticmethod
    def _download_raw_file(raw_file_url : str, destination_file : str):

        filename, headers = urllib.request.urlretrieve(raw_file_url, filename=destination_file)
        _LOGGER.debug(f"Successfully downloaded {filename}")
        return filename, headers

    @staticmethod
    def _make_raw_file_link(repo_url : str, file : str, branch = "main"):
        """Returns the link to the raw file on github

        Parameters
        ----------
        repo_url : str
            url to the repo
        file : str
            _description_
        branch : str, optional
            _description_, by default "main"

        Returns
        -------
        _type_
            _description_
        """
        assert repo_url.startswith("https://github.com"), "repo_url must start with `https://github.com`"
        repo_url = repo_url.removesuffix("/")
        raw_base_url = repo_url.replace("github.com", "raw.githubusercontent.com")
        return raw_base_url + "/refs/heads/" + branch + "/" + file
