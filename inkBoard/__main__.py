
from multiprocessing import freeze_support

import inkBoard.logging

freeze_support()

import logging
from typing import Union, TYPE_CHECKING
from pathlib import Path
import asyncio
import sys
import concurrent.futures

import inkBoard
from inkBoard import constants as const, bootstrap, loaders
from PythonScreenStackManager.exceptions import ReloadWarning, FullReloadWarning
from inkBoard.arguments import args, PRE_CORE_ACTIONS, POST_CORE_ACTIONS

if TYPE_CHECKING:
    from inkBoard import core as CORE
    import PythonScreenStackManager
    from inkBoard.configuration.configure import config

_LOGGER = inkBoard.getLogger(__name__)
importer_thread = concurrent.futures.ThreadPoolExecutor(None,const.IMPORTER_THREADPOOL)

async def run_inkBoard(config_file):
    "Runs inkBoard from the passed config file"

    while True:
        CORE = await bootstrap.setup_core(config_file, loaders.IntegrationLoader)
        
        if args.command in POST_CORE_ACTIONS:
            return POST_CORE_ACTIONS[args.command](args)
        
        await bootstrap.start_core(CORE)
        
        try:
            await bootstrap.run_core(CORE)
        except FullReloadWarning:
            await asyncio.sleep(0)
            bootstrap.reload_core(CORE, full_reload=True)
        except ReloadWarning:
            await asyncio.sleep(0)
            bootstrap.reload_core(CORE)
        except (SystemExit, KeyboardInterrupt):
            await asyncio.sleep(0)
            _LOGGER.info("Closing down inkBoard")
            ##Check if it is needed to close
            return bootstrap.stop_core(CORE)
        except Exception as exce:
            _LOGGER.error(f"Something unexpected went wrong running inkBoard: {exce}")
            _LOGGER.warning("Attempting graceful shutdown")
            return bootstrap.stop_core(CORE)
        
        await asyncio.sleep(0)

def run():
    "Starts the main eventloop and runs inkBoard. This function is blocking"
    res = asyncio.run(run_inkBoard(args.configuration),
            debug=_LOGGER.getEffectiveLevel() <= logging.DEBUG)
    return res

def run_config(config_file: Union[Path,str]):
    "Starts the main eventloop and runs inkBoard, using the given config file. This function is blocking"
    return asyncio.run(run_inkBoard(config_file),
                        debug=_LOGGER.getEffectiveLevel() <= logging.DEBUG)

def main():
    inkBoard.logging.init_logging(args.logs, args.quiet, args.verbose)

    if args.command in PRE_CORE_ACTIONS:
        return PRE_CORE_ACTIONS[args.command](args)
    
    ##Maybe make a core folder similar to ESPhome, to hold things like the config file, screen instance etc.
    return run()

if __name__ == "__main__":
    sys.exit(main())
