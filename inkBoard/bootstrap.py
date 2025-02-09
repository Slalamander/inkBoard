"Functions to get an inkBoard config set up."

from typing import *
import asyncio
import importlib
from pathlib import Path
from contextlib import suppress

import inkBoard
import inkBoard.platforms
import inkBoard.loaders

from inkBoard import constants as const, loaders, CORE
from inkBoard.helpers import DeviceError, ScreenError, ConfigError, QuitInkboard
from inkBoard.helpers import ParsedAction
from inkBoard.util import reload_full_module
from inkBoard.logging import setup_logging
from inkBoard.types import coretype
from inkBoard.async_ import is_reload_shielded_task

import PythonScreenStackManager as PSSM

_LOGGER = inkBoard.getLogger(__name__)

if const.DESIGNER_INSTALLED:
    import inkBoarddesigner.integrations

if TYPE_CHECKING:
    import inkBoard
    from PythonScreenStackManager import pssm, elements
    from inkBoard import config, CORE, platforms

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
    core._customElements = elts
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
    pssm.constants.SHORTHAND_ICONS["inkboard-background"] = const.INKBOARD_BACKGROUND

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
    main_layout = dashboard.get_main_layout(dash_conf, core)

    return main_layout

async def setup_integration_loader(core: "CORE"):
    "Sets up the integration loader attached to the core object."

    loader = core.integrationLoader

    obj = await loader.async_setup_integrations(core)
    return obj

async def setup_core(config_file, integration_loader: "loaders.IntegrationLoader" = None) -> "CORE":
    "Sets up the core module for running inkBoard, everything up to starting."
    
    # from inkBoard import core as CORE
    # from inkBoard import core
    c = CORE()
    print("core is set up")
    # CORE()

    assert Path(config_file).exists(), f"{config_file} does not exist"
    p = Path(config_file)
    assert Path(config_file).suffix[1:] in const.CONFIG_FILE_TYPES, f"{config_file} must be a yaml file"

    config_folder = Path(config_file).parent

    if integration_loader != None:
        assert not hasattr(CORE,"integrationLoader"), "inkBoard core already has an integration loader defined"
        CORE._integrationLoader = integration_loader
    
    if hasattr(CORE,"integrationLoader"):
        folders = {
            "custom.integrations" : config_folder / "custom" / "integrations",
            inkBoard.integrations.__package__: Path(inkBoard.integrations.__path__[0]) 
            }
        if const.DESIGNER_INSTALLED:
            folders[inkBoarddesigner.integrations.__package__] = Path(inkBoarddesigner.integrations.__path__[0])
        CORE.integrationLoader.get_integrations(folders)
    
    CORE._config = setup_base_config(config_file)

    setup_logging(CORE)

    if hasattr(CORE,"integrationLoader"):
    # if CORE.integrationLoader:
        ##This should be throwing an error for now
        ##Since I should figure out how to make hasattr return False if a private attribute is not set yet
        CORE.integrationLoader.import_integrations(CORE)

    CORE._customFunctions = import_custom_functions(CORE)
    import_custom_elements(CORE)

    setup_styles(CORE)

    CORE._device = await setup_device(CORE)

    CORE._screen = await setup_screen(CORE)
    CORE.screen.add_shorthand_function_group("custom", CORE.parse_custom_function)

    if hasattr(CORE,"integrationLoader"):
        CORE._integrationObjects = await CORE.integrationLoader.async_setup_integrations(CORE)

    main_layout = setup_dashboard_config(CORE)

    await CORE.screen.async_add_element(main_layout, skipPrint=True)

    ParsedAction.parse_actions()

    return CORE

async def start_core(core: "CORE"):
    "Starts the inkBoard core, but does not run the print loop yet"

    core.screen.start_batch_writing()

    if hasattr(CORE,"integrationLoader"):
        await core.integrationLoader.async_start_integrations(core)

async def run_core(core: "CORE"):
    "Runs the inkBoard core. Generally call after `setup_core` and `start_core`"

    coros = [core.screen.async_start_screen_printing(), core.screen._eStop]

    if core.integrationLoader:
        coros.append(core.integrationLoader.run_integrations(core))
    
    L = asyncio.gather(
                    *coros,
                    return_exceptions=False)
    return await L  #@IgnoreException

def _shutdown_core(core: "CORE", is_reload: bool = False):
    "Shuts down the core object and optionally reloads the necessary modules"
    
    _LOGGER.info("Shutting down inkBoard core")
    if not hasattr(core,"screen"):
        return

    for task in asyncio.all_tasks(core.screen.mainLoop):
        if (
            task == asyncio.current_task(core.screen.mainLoop)
            or (is_reload and is_reload_shielded_task(task))
            ):
            continue
        task.cancel()

async def reload_core(core: "CORE", full_reload: bool = False):
    """Reloads the core object and required modules so it can be set up fresh again.

    Parameters
    ----------
    core : CORE
        The inkBoard core
    full_reload : bool, optional
        A full reload reloads all modules that affect printing, i.e. PSSM, non custom integrations, platforms, etc. by default False
    """    

    _shutdown_core(core, is_reload=True)
    if hasattr(core,"integrationLoader"):
        await core.integrationLoader.async_stop_integrations(core)

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

        with suppress(AttributeError):
            if inkBoard.platforms.__name__ not in core.device.__module__:
                idx = reload_mods.index(inkBoard.platforms.__name__)
                reload_mods.insert(idx+1, core.device.__module__)

            ##Reload integrations here? ##Yeah, can be done via the loader list.

        for mod in reload_mods:
            _LOGGER.debug(f"Reloading module {mod}")
            reload_full_module(mod)

        core.integrationLoader._reload_imports = True

    core._reset()
    return


async def stop_core(core: "CORE"):
    try:
        _shutdown_core(core)
        if hasattr(core, "integrationLoader"):
            await core.integrationLoader.async_stop_integrations(core)
    except Exception as exce:
        print(f"inkBoard did not shutdown gracefully: {exce}")
        return 1
    
    return 0