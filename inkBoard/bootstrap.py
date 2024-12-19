"Functions to get an inkBoard config set up."

from typing import *
import asyncio
import importlib
from pathlib import Path

import inkBoard
from inkBoard import constants as const, loaders, arguments
from inkBoard.helpers import DeviceError, ScreenError, ConfigError, reload_full_module
import inkBoard.loaders
from inkBoard.logging import setup_logging
import PythonScreenStackManager as PSSM
import inkBoard.platforms

_LOGGER = inkBoard.getLogger(__name__)

if arguments.DESIGNER_MOD:
    import inkBoarddesigner.integrations

if TYPE_CHECKING:
    import inkBoard
    from PythonScreenStackManager import pssm, elements
    from inkBoard import config, core as CORE, platforms


def import_custom_functions(core: "CORE") -> dict[str,Callable]:
    "Imports the modules from custom functions and constructs the dict holding them."

    ##Move this to loader (where integrationloader will be put too.)
    ##Also check what happens when reloading, without reloading the module
    ##I.e. to test what popping from path_importer_cache does -> nothing I can figure out at least

    return inkBoard.loaders.load_custom_functions(core)

def import_custom_elements(core: "CORE") -> dict[str, "elements.Element"]:

    elts = inkBoard.loaders.load_custom_elements(core)

    def parser(elt_str):
        return elts[elt_str]

    core.add_element_parser("custom", parser)
    return

def setup_base_config(config_file) -> "config":
    "Read out the config and Setup the object holding the inkBoard config"

    from inkBoard.configuration import config

    if isinstance(config_file, config):
        return config_file
    
    try:
        config_obj = config(config_file)
    except Exception as exce:
        raise ConfigError(f"Invalid base configuration: {exce}") from exce

    return config_obj

async def setup_device(core: "CORE") -> "platforms.Device":
    "Import the correct platform module and set up its Device instance. Also validate if the device functions correctly."

    from inkBoard import platforms
    ##Gotta check how this deals with being reloaded, same with config
    config = core.config
    try:
        device = platforms.get_device(config, core)
        await asyncio.sleep(0)  ##Allow startup tasks from devices to optionally run
    except Exception as exce:
        if isinstance(exce, DeviceError):
            raise exce
        raise DeviceError(f"Could not set up device: {exce}") from exce
    
    return device

async def setup_screen(core: "CORE") -> "pssm.PSSMScreen":
    "Setup the screen instance that will be handling the printing"

    config = core.config

    from PythonScreenStackManager import pssm

    try:
        screen = pssm.PSSMScreen(core.device, **vars(config.screen))
        await asyncio.sleep(0)
    except Exception as exce:
        raise ScreenError(f"Could not set up pssm screen: {exce}") from exce
    return screen

def setup_styles(core: "CORE"):
    "Applies styles from the config to the style handler"

    ##Will attach style to screen later
    config = core.config

    import PythonScreenStackManager as pssm
    pssm.pssm.styles.Style.add_color_shorthand(**const.INKBOARD_COLORS)

    pssm.constants.SHORTHAND_ICONS["inkboard"] = const.INKBOARD_ICON

    if config.styles:
        pssm.pssm.styles.Style.add_color_shorthand(**config.styles.get("shorthand_colors",{}))
    
    new_folders = {
                "font_folder": config.folders.font_folder,
                "icon_folder": config.folders.icon_folder,
                "picture_folder": config.folders.picture_folder
                }
    pssm.constants.CUSTOM_FOLDERS.update(new_folders)

def setup_dashboard_config(core: "CORE") -> "elements.Layout":
    "Reads out validates the dashboard nodes from the config, as well as optionally importing the custom dashboard file."

    from inkBoard import dashboard

    config = core.config
    dash_conf = dashboard.build_config_elements(config, core)
    main_layout = dashboard.get_main_layout(dash_conf)

    return main_layout

async def setup_integration_loader(core: "CORE"):
    "Sets up the integration loader attached to the core object."

    loader = core.integration_loader

    obj = await loader.async_setup_integrations(core)
    return obj

async def setup_core(config_file, integration_loader: "loaders.IntegrationLoader" = None) -> "CORE":
    "Sets up the core module for running inkBoard, everything up to starting."
    
    from inkBoard import core as CORE

    assert Path(config_file).exists(), f"{config_file} does not exist"
    p = Path(config_file)
    assert Path(config_file).suffix[1:] in const.CONFIG_FILE_TYPES, f"{config_file} must be a yaml file"

    config_folder = Path(config_file).parent

    if integration_loader != None:
        assert not hasattr(CORE,"integration_loader"), "inkBoard core already has an integration loader defined"
        CORE.integration_loader = integration_loader
    
    if CORE.integration_loader:
        folders = {
            "custom.integrations" : config_folder / "custom" / "integrations",
            inkBoard.integrations.__package__: Path(inkBoard.integrations.__path__[0]) 
            }
        if arguments.DESIGNER_MOD:
            folders[inkBoarddesigner.integrations.__package__] = Path(inkBoarddesigner.integrations.__path__[0])
        CORE.integration_loader.get_integrations(folders)
    
    CORE.config = setup_base_config(config_file)

    setup_logging(CORE)

    if CORE.integration_loader:
        CORE.integration_loader.import_integrations(CORE)

    CORE.custom_functions = import_custom_functions(CORE)
    import_custom_elements(CORE)

    CORE.device = await setup_device(CORE)

    CORE.screen = await setup_screen(CORE)
    CORE.screen.add_shorthand_function_group("custom", CORE.parse_custom_function)

    setup_styles(CORE)

    if CORE.integration_loader:
        CORE.integration_objects = await CORE.integration_loader.async_setup_integrations(CORE)

    main_layout = setup_dashboard_config(CORE)

    await CORE.screen.async_add_element(main_layout, skipPrint=True)

    return CORE

async def start_core(core: "CORE"):
    "Starts the inkBoard core, but does not run the print loop yet"

    core.screen.start_batch_writing()

    if core.integration_loader:
        await core.integration_loader.async_start_integrations(core)

async def run_core(core: "CORE"):
    "Runs the inkBoard core. Generally call after `setup_core` and `start_core`"

    coros = [core.screen.async_start_screen_printing(), core.screen._eStop]

    if core.integration_loader:
        coros.append(core.integration_loader.run_integrations(core))
    
    L = asyncio.gather(
                    *coros,
                    return_exceptions=False)
    return await L  #@IgnoreExceptions

def _shutdown_core(core: "CORE", reload_ = False):
    "Shuts down the core object and optionally reloads the necessary modules"
    
    _LOGGER.info("Shutting down inkBoard core")

    for task in asyncio.all_tasks(core.screen.mainLoop):
        if task == asyncio.current_task(core.screen.mainLoop):
            continue
        task.cancel()

def reload_core(core: "CORE", full_reload: bool = False):
    """Reloads the core object and required modules so it can be set up fresh again.

    Parameters
    ----------
    core : CORE
        The inkBoard core
    full_reload : bool, optional
        A full reload reloads all modules that affect printing, i.e. PSSM, non custom integrations, platforms, etc. by default False
    """    

    _shutdown_core(core,full_reload)

    if not full_reload:
        PSSM.pssm._reset()
        for mod in const.BASE_RELOAD_MODULES:
            _LOGGER.debug(f"Reloading module {mod}")
            reload_full_module(mod)
        
        ##This should also take into account modules coming from designer
        ##i.e. insert the specific platform module too if not in inkBoard

    else:
        PSSM.pssm._reset()
        reload_mods = list(const.FULL_RELOAD_MODULES)

        if inkBoard.platforms.__name__ not in core.device.__module__:
            idx = reload_mods.index(inkBoard.platforms.__name__)
            reload_mods.insert(idx+1, core.device.__module__)

            ##Reload integrations here? ##Yeah, can be done via the loader list.

        for mod in reload_mods:
            _LOGGER.debug(f"Reloading module {mod}")
            reload_full_module(mod)

        core.integration_loader._reload_imports = True

    del inkBoard.core
    return


def stop_core(core: "CORE"):
    try:
        _shutdown_core(core,False)
    except Exception as exce:
        print(f"inkBoard did not shutdown gracefully: {exce}")
        return 1
    
    return 0