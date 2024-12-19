
import sys
import importlib
import importlib.util
import pkgutil
import inspect
import asyncio
import json

from typing import *
from types import MappingProxyType
from pathlib import Path

import inkBoard
from inkBoard.helpers import classproperty, reload_full_module
import inkBoard.integrations

if TYPE_CHECKING:
    from inkBoard import core as CORE

_LOGGER = inkBoard.getLogger(__name__)

def load_custom_functions(core: "CORE"):
    "Imports the modules from custom functions and constructs the dict holding them."

    ##Move this to loader (where integrationloader will be put too.)
    ##Also check what happens when reloading, without reloading the module
    ##I.e. to test what popping from path_importer_cache does -> nothing I can figure out at least

    try:
        from custom import functions as custom_funcs
    except (ImportError, ModuleNotFoundError):
        _LOGGER.debug("No directory for custom functions found")
        return {}

    _LOGGER.debug("Gathering custom functions")

    funcs = {}

    def log_error(mod_name):
        _LOGGER.error(f"Unable to import custom functions module {mod_name}")

    ##Using walk_packages as it can import any function from a file within a module since those are found too.
    pks_w = pkgutil.walk_packages(custom_funcs.__path__, f"{custom_funcs.__package__}.", onerror=log_error)

    for m in pks_w:
        _LOGGER.verbose(f"Importing custom functions from {m.name}")
        ##HA checks module versions in the manifest with cached values to determine reloads
        if m.name in sys.modules:
            mod = sys.modules[m.name]
            mod = importlib.reload(mod)
        else:
            mod = importlib.import_module(m.name,)

        for name, func in inspect.getmembers(mod, lambda x: 
                                                                    inspect.isfunction(x) 
                                                                    and mod.__name__ in x.__module__
                                                                    and not x.__name__.startswith("_")):
            if name in funcs:
                _LOGGER.warning(f"A custom function with the name {name} is already registered.")
                _LOGGER.debug(f"Duplicate function from {func.__module__}, first function is from {funcs[name].__module__}")
                continue
            funcs[name] = func  
    
    ##When to import: Maybe rewalk config dict after importing this and rebuild?
    ##Maybe nah, just let integrations and stuff handle parsing those themselves.
    ##Seems like this works?

    ##So, for screen: just add every function as shorthand with the custom: prefix
    ##For trigger functions etc., have the integration handle in it

    ##Import after importing modules but before calling setup I think
    ##yeah. Do indeed add imported modules to the core, but directly importing from other things is fine too.

    ##Generally for updating integrations etc: need to stop the problem anyways to install them so eh.
    return funcs

def load_custom_elements(core: "CORE"):
    "Loads elements present in the custom/elements folder, and constructs a dict with them."

    try:
        from custom import elements as custom_elts
    except (ImportError, ModuleNotFoundError):
        _LOGGER.debug("No directory for custom functions found")
        return {}

    _LOGGER.debug("Gathering custom functions")

    elts = {}

    def log_error(mod_name):
        _LOGGER.error(f"Unable to import custom functions module {mod_name}")
    
    ##Using walk_packages as it can import any function from a file within a module since those are found too.
    pks_w = pkgutil.walk_packages(custom_elts.__path__, f"{custom_elts.__package__}.", onerror=log_error)

    for m in pks_w:
        _LOGGER.verbose(f"Importing custom functions from {m.name}")
        ##HA checks module versions in the manifest with cached values to determine reloads
        if m.name in sys.modules:
            mod = sys.modules[m.name]
            mod = importlib.reload(mod)
        else:
            mod = importlib.import_module(m.name,)

        elt_dict = core.util.get_module_elements(mod)
        for name, elt in elt_dict.items():
            if name in elts:
                _LOGGER.warning(f"A custom function with the name {name} is already registered.")
                _LOGGER.debug(f"Duplicate function from {elts.__module__}, first function is from {elts[name].__module__}")
                continue
            elts[name] = elt  

    return elts


class IntegrationLoader:
    "Provides bindings to load inkBoard integrations"

    _integration_keys: dict[str,str] = {}
    _installed_integrations: dict[str,Path] = {}
    _integration_modules: dict[str,str] = {}

    _imported_modules: dict[str,str] = {}
    _loaded_integrations: list[str] = set()

    _reload_imports: bool = False

    @classproperty
    def integration_keys(cls) -> dict[str,str]:
        return cls._integration_keys.copy()

    @classproperty
    def imported_integrations(cls) -> dict[str,Path]:
        "The integrations imported for the loaded config, and the Path pointing to them"
        d = {}
        for integration in cls._imported_modules:
            d[integration] = cls._installed_integrations[integration]
        return d

    @classmethod
    def get_integrations(cls, folders: dict[str,Path]):
        "Retrieves all the available integrations in the config's custom folder and inkBoard itself."
        #folders: dict with base module name mapped to the folder path
        cls._reset()


        for base_module, folder in folders.items():
            if folder.exists():
                cls._read_out_folder(base_module, folder)

        return MappingProxyType(cls._installed_integrations)
    
    @classmethod
    def add_integration_config_key(cls, key: str, module_name: str):
        if key in cls._integration_keys:
            int_mod = cls._integration_keys[key]
            _LOGGER.info(f"{key} is already used for a the config of a different integration: {int_mod}")
        else:
            cls._integration_keys[key] = module_name
        return

    @classmethod
    def _read_out_folder(cls, base_module: str, folder: Path):
        folders = folder.iterdir()
        for int_dir in filter(lambda p: (p.is_dir() and not p.name.startswith("_")), folders):
            if int_dir.name in cls._installed_integrations:
                _LOGGER.info(f"Integration {int_dir.name} has already been found in module {cls._integration_modules[int_dir.name]}. Will not import from {base_module}")
                continue

            manifest = int_dir / "manifest.json"
            if not manifest.exists():
                _LOGGER.error(f"Integration folder {int_dir} is missing the manifest.json file.")
                continue

            with open(manifest) as f:
                manifest = json.load(f)
                ##Support for requirements has not yet been implemented
            
            if c := manifest.get("config_entry",False):
                #Will require config_keys, similar to esphome, which can be left empty if needed.
                name = f"{base_module}.{int_dir.name}"
                ##These should not be checked by config key (i.e., save the key in the dict entry); key should be the folder name.
                cls.add_integration_config_key(c, name)
                cls._installed_integrations[int_dir.name] = int_dir
                cls._integration_modules[int_dir.name] = name
            else:
                _LOGGER.error(f"Integrations are required to have a config_entry key {int_dir.name} does not")
                continue

    @classmethod
    def import_integrations(cls, core: "CORE", progress_func=None, value_range=()):
        config = core.config
        import_set: set[tuple[str, Path]] = set()

        ##Import custom via appending to path.
        ##And I think just import via here, but make the set or something recognise the base package too.
        ##Or save strings to the modules instead of their folders.

        for config_entry in cls._integration_keys:
            if config_entry in config.configuration:
                import_set.add((config_entry, cls._integration_keys[config_entry]))
        
        if not import_set: 
            return

        if progress_func:
            progress_func(value_range[0] + 1, f"Importing {len(import_set)} integrations")
            step = int((value_range[1] - value_range[0] - 1)/len(import_set))
            progress = value_range[0] + 1

        for (config_key, name) in import_set:
            integration = name.split(".")[-1]
            if progress_func:
                progress = progress + step
                progress_func(progress, f"Importing integration {integration}")
            module = cls._import_integration(name)
            if not module:
                _LOGGER.error(f"Unable to successfully import integration {integration} from {name}")
            else:
                cls._imported_modules[integration] = module
        
        cls._reload_imports = False
        return
        ##See code in hass core: https://github.com/home-assistant/core/blob/ab5ddb8edfb72d5f5915574f642eba93afc5abdc/homeassistant/loader.py#L1669

    @classmethod
    def _import_integration(cls, name):
            
        module = None
        integration = name.split(".")[-1]

        ##Simply put: I don't think it'll matter how you set this up, the __init__ will be imported regardless
        ##Messing with the package name and whatever will just cause issues with relative imports and stuff
        ##So: make different file, like integration.py or something, that provided the hooks for the integration_loader
        ##Or simply make writers use the init to provide the correct hooks *shrug*
        
        if name in sys.modules and cls._reload_imports:
            reload_full_module(name)

        if name in sys.modules and not cls._reload_imports:
            module = sys.modules.get(name,None)
        else:
            spec = importlib.util.find_spec(name)

            ##Got this code from: https://docs.python.org/3/library/importlib.html#checking-if-a-module-can-be-imported
            if spec  == None:
                _LOGGER.error(f"Unable to import integration {integration} from {name}")
                return
            try:
                module = importlib.util.module_from_spec(spec)
                module = importlib.import_module(name)
            except Exception as exce:
                msg = f"Error importing integration {integration}: {exce}"
                _LOGGER.exception(msg, stack_info=True)
                raise exce

        if not hasattr(module,"async_setup") and not hasattr(module,"setup"):
            _LOGGER.error(f"Integration {integration} is missing the required setup function")
            return

        return module

    @classmethod
    async def async_setup_integrations(cls, core: "CORE", progress_func=None, value_range=()) -> MappingProxyType[Literal["integration_entry"],Any]:
        integration_objects = {}
        
        config = core.config
        if not cls._imported_modules:
            return {}

        if progress_func:
            progress_func(value_range[0] + 1, f"Importing {len(cls._imported_modules)} integrations")
            step = int((value_range[1] - value_range[0] - 1)/len(cls._imported_modules))
            progress = value_range[0] + 1

        for integration, module in cls._imported_modules.items():
            module : "sys.ModuleType"
            setup_func = None
            if hasattr(module,"async_setup"):
                setup_func = module.async_setup
            elif hasattr(module,"setup"):
                setup_func = module.setup

            if not isinstance(setup_func,Callable):
                _LOGGER.error(f"{integration} does not have a valid setup function, not importing")
                raise TypeError
            
            _LOGGER.info(f"Setting up integration {integration}")
            if progress_func:
                progress = progress + step
                progress_func(progress, f"Setting up integration {integration}")
            try:
                if asyncio.iscoroutinefunction(setup_func):
                    res = await setup_func(core, config)
                else:
                    res = setup_func(core, config)

                if res == None:
                    _LOGGER.error(f"Integration setup functions must return a result (at minimum a boolean `True`), or `False`. {integration} returned `None`")
                    continue

                if res == False:
                    _LOGGER.error(f"Something went wrong setting up {integration}")
                    continue
                
                cls._loaded_integrations.add(Path(module.__file__).parent)
                if res != True:
                    integration_objects[integration] = res

                _LOGGER.debug(f"{integration} succesfully set up")
            except (ModuleNotFoundError, ImportError) as exce:
                msg = f"Error importing integration {integration}: {exce}. The integration may not be able to run in an emulated environment."
                _LOGGER.warning(msg)
            except Exception as exce:
                msg = f"Error importing integration {integration}: {exce}."
                _LOGGER.error(msg, exc_info=True)

        return integration_objects
    
    @classmethod
    async def async_start_integrations(cls, core: "CORE"):
        """
        Calls the setup functions for relevant integrations. If a maximum time was set in the config, will continue setting up in the background while inkBoard starts printing.

        Parameters
        ----------
        core : CORE
            The inkBoard core module
        """   

        cls._done_setups = {}
        cls._pending_setups = {}

        config = core.config

        coro_list = set()
        for integration, module in cls._imported_modules.items():
            pkg = module.__package__
            setup_res = core.integration_objects.get(integration,None)

            if hasattr(module, "async_start"):
                if not asyncio.iscoroutinefunction(module.async_start):
                    _LOGGER.error(f"integration {integration}: async_start must be a coroutine")
                    continue
                t = asyncio.create_task(module.async_start(core, setup_res), name=pkg)

            elif hasattr(module, "start"):
                coro = asyncio.to_thread(module.start, core, setup_res)
                t = asyncio.create_task(coro,name=pkg)
            else:
                continue

            coro_list.add(t)
            cls._pending_setups[pkg] = t

        if not coro_list:
            return
        
        setup_time = config.inkBoard["integration_start_time"]

        if setup_time < 0:
            await cls._wait_for_start(coro_list)
        else:
            setup_task = asyncio.create_task(cls._wait_for_start(coro_list))
            try:
                await asyncio.wait_for(asyncio.shield(setup_task), setup_time)
            except asyncio.TimeoutError:
                _LOGGER.warning(f"Integration setup time of {setup_time} seconds elapsed but not all integrations are setup yet. Integrations {cls._pending_setups.keys()} will continue setup in the background.")

        return
    
    @classmethod
    async def _wait_for_start(cls, coro_list):
        pending = coro_list 
        while pending:
            try:
                done, pending = await asyncio.wait(pending,return_when=asyncio.FIRST_COMPLETED)
            except:
                for t in done:
                    t : asyncio.Future
                    if t.cancelled():
                        continue

                    if t.exception() != None:
                        _LOGGER.error(f"Integrations {t.get_name()} ran into an error while starting up: {t.exception()}")
            else:
                names = set()
                for t in done:
                    names.add(t.get_name())
                _LOGGER.info(f"Integrations {names} were started.")
            finally:
                cls._pending_setups.pop(t.get_name())
                cls._done_setups[t.get_name()] = t

    @classmethod
    async def run_integrations(cls, core: "CORE"):
        """
        Runs any long running tasks defined by integrations.
        Exceptions do not interfere with the print loop.

        Parameters
        ----------
        core : CORE
            The inkBoard core module
        """    
        screen = core.screen

        coro_list = set()

        async def await_setup(pkg, runner : asyncio.Task):
            setup_task = cls._pending_setups.get(pkg,None)
            _LOGGER.warning(f"Waiting to start {pkg} long running task until its setup has finished.")
            if setup_task != None:
                await setup_task
                await asyncio.sleep(0)
            await runner

        for integration, module in cls._imported_modules.items():

            pkg = module.__package__
            setup_res = core.integration_objects.get(integration,None)

            if hasattr(module, "async_run"):
                if not asyncio.iscoroutinefunction(module.async_run):
                    _LOGGER.error(f"integration {pkg}: async_run must be a coroutine")
                    continue

                if pkg in cls._pending_setups:
                    coro = await_setup(pkg, module.async_run(core, setup_res))
                else:
                    coro = module.async_run(core, setup_res)

                t = asyncio.create_task(coro, name=pkg)
                coro_list.add(t)

        if not coro_list:
            return

        pending = coro_list
        ##From what I could find, this is the only way to catch out exceptions when they happen (gather only returns when everything is done, or returns a single result)
        ##While keeping a reference to the original task (which doesn't seem to happen for as_completed I believe) -> that only also just throws an exception

        done = []
        while pending:
            try:
                done, pending = await asyncio.wait(pending,return_when=asyncio.FIRST_COMPLETED)
            except:
                for t in done:
                    t : asyncio.Future
                    if t.cancelled():
                        _LOGGER.warning(f"Integration {t.get_name()} was cancelled while running.")

                    if t.exception() != None:
                        _LOGGER.error(f"Integration {t.get_name()} ran into an error while running: {t.exception()}")

    @classmethod
    def _reset(cls):
        cls._integration_keys: dict[str,str] = {}
        cls._installed_integrations: dict[str,Path] = {}
        cls._integration_modules = {}

        cls._imported_modules: dict[str,str] = {}
        cls._loaded_integrations: list[str] = set()

