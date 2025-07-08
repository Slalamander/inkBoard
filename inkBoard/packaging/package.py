from typing import (
    TYPE_CHECKING, 
    Union,
    Literal,
    Callable,
)
from pathlib import Path
from datetime import datetime as dt
import tempfile
import json
import zipfile
import os
from functools import partial
import shutil
import inspect


from inkBoard import logging
from inkBoard.constants import CONFIG_FILE_TYPES

from .constants import (
    ZIP_COMPRESSION,
    ZIP_COMPRESSION_LEVEL,
    DESIGNER_FILES,
    INKBOARD_PACKAGE_INTERNAL_FOLDER,
)
from .types import (
    PackageDict
)

if TYPE_CHECKING:
    from inkBoard import CORE

_LOGGER = logging.getLogger(__name__)

class Packager:
    """Takes care of creating inkBoard packages from configs
    """

    def __init__(self, core: "CORE", folder: Union[str,Path] = None, progress_func: Callable[[str,str, float],None] = None):
        self.CORE = core
        self.config = core.config
        if folder:
            if isinstance(folder,str): folder = Path(folder)
            assert folder.is_dir(), "Folder must be a directory"
            self.base_folder = folder
        else:
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
            with zipfile.ZipFile(zipname, 'w', ZIP_COMPRESSION, compresslevel=ZIP_COMPRESSION_LEVEL) as zip_file:
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

        _LOGGER.info("Succesfully copied contents of config folder.")
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

        manual_files = {"readme.md", "install.md", "installation.md", "package_files"}
        manual_dir = (tempdir / "configuration") if (tempdir / "configuration").exists() else tempdir

        for file in platform_folder.iterdir():
            if file.name.lower() not in manual_files:
                continue

            _LOGGER.debug(f"Copying platform manual file {file}")
            if file.is_dir():
                shutil.copytree(
                    src = file,
                    dst = manual_dir / "files",
                    dirs_exist_ok=True
                )
            else:
                manual_files.add(file.name)
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
        all_integrations : dict[str,Path] = self.CORE.integrationLoader.imported_integrations
        ##E

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
        import inkBoard
        import PythonScreenStackManager as PSSM

        package_dict = {"created": dt.now().isoformat()}

        package_dict["versions"] = {"inkBoard": inkBoard.__version__,
                    "PythonScreenStackManager": PSSM.__version__}
        

        if self.CORE.DESIGNER_RUN:
            import inkBoarddesigner

            package_dict["created_with"] = "inkBoarddesigner"
            package_dict["versions"]["inkBoarddesigner"] = inkBoarddesigner.__version__
            package_dict["platform"] = self.CORE.device.emulated_platform
        else:
            package_dict["created_with"] = "inkBoard"
            package_dict["versions"]["inkBoarddesigner"] = None
            package_dict["platform"] = self.CORE.device.platform

        return PackageDict(**package_dict)
