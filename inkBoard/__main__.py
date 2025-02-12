
from multiprocessing import freeze_support

import inkBoard.logging

freeze_support()

import logging
from typing import Union, TYPE_CHECKING
from pathlib import Path
import asyncio
import sys
import concurrent.futures

from PythonScreenStackManager.exceptions import ReloadWarning, FullReloadWarning

import inkBoard
from inkBoard import constants as const, bootstrap, loaders
from inkBoard.helpers import QuitInkboard
from inkBoard.arguments import parse_args, PRE_CORE_ACTIONS, POST_CORE_ACTIONS

if TYPE_CHECKING:
    from inkBoard import CORE as CORE
    import PythonScreenStackManager
    from inkBoard.configuration.configure import config

_LOGGER = inkBoard.getLogger(__name__)
importer_thread = concurrent.futures.ThreadPoolExecutor(None,const.IMPORTER_THREADPOOL)

async def run_inkBoard(configuration: Union[str,Path],
                    command: str = "run"):
    """Runs inkBoard from the passed config file

    Parameters
    ----------
    configuration : Union[str,Path]
        The configuration file to run from
    command : str, optional
        The command inkBoard is being run with, by default "run"
        This is only used if the command is an action to be run after setting up a core object

    Returns
    -------
    _type_
        _description_
    """    

    "Runs inkBoard from the passed config file"

    while True:
        CORE = await bootstrap.setup_core(configuration, loaders.IntegrationLoader)
        
        if command in POST_CORE_ACTIONS:
            return POST_CORE_ACTIONS[command](parse_args())
        
        await bootstrap.start_core(CORE)
        
        try:
            await bootstrap.run_core(CORE)
        except FullReloadWarning:
            await asyncio.sleep(0)
            await bootstrap.reload_core(CORE, full_reload=True)
        except ReloadWarning:
            await asyncio.sleep(0)
            await bootstrap.reload_core(CORE)
        except (SystemExit, KeyboardInterrupt, QuitInkboard):
            await asyncio.sleep(0)
            _LOGGER.info("Closing down inkBoard")
            ##Check if it is needed to close
            return await bootstrap.stop_core(CORE)
        except Exception as exce:
            _LOGGER.error(f"Something unexpected went wrong running inkBoard: {exce}")
            _LOGGER.warning("Attempting graceful shutdown")
            return await bootstrap.stop_core(CORE)
        
        await asyncio.sleep(0)

def run(args):
    """Starts the main eventloop and runs inkBoard.
    This function is blocking"""

    debug = const.DEBUG
    
    res = asyncio.run(run_inkBoard(args.configuration, args.command),
            debug = debug)
    return res

def run_config(config_file: Union[Path,str]):
    """Starts the main eventloop and runs inkBoard, using the given config file.
    This function is blocking"""
    return asyncio.run(run_inkBoard(config_file),
                        debug=_LOGGER.getEffectiveLevel() <= logging.DEBUG)

def main():
    args = parse_args()
    inkBoard.logging.init_logging(args.logs, args.quiet, args.verbose)

    if args.command in PRE_CORE_ACTIONS:
        return PRE_CORE_ACTIONS[args.command](args)
    
    ##Maybe make a core folder similar to ESPhome, to hold things like the config file, screen instance etc.
    return run(args)

if __name__ == "__main__":
    sys.exit(main())
