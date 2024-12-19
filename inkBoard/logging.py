"Logging classes for inkBoard."

import logging
import logging.handlers
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
from functools import partial, partialmethod
from contextlib import suppress
from dataclasses import asdict
from types import MappingProxyType

try:
    # Python 3.7 and newer, fast reentrant implementation
    # without task tracking (not needed for that when logging)
    from queue import SimpleQueue as Queue
except ImportError:
    from queue import Queue

if TYPE_CHECKING:
    from inkBoard import core as CORE
    from inkBoard.configuration.types import LoggerEntry


NOTSET = logging.NOTSET
VERBOSE = int(logging.DEBUG/2)
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
WARN = WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL
FATAL = logging.FATAL

LOG_LEVELS = ("NOTEST", "VERBOSE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")



log_format = '%(asctime)s [%(levelname)s %(name)s %(funcName)s, line %(lineno)s]: %(message)s'
log_dateformat = '%d-%m-%Y %H:%M:%S'


class ANSICOLORS:
    GRAY = "\x1b[38;5;247m"
    GREEN = "\x1b[32;20m"
    BLUE =  "\x1b[34;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET =  "\x1b[0m"

ANSI_FORMATS = {
        logging.NOTSET: ANSICOLORS.GRAY,
        logging.DEBUG: ANSICOLORS.GREEN,
        logging.INFO: ANSICOLORS.BLUE,
        logging.WARNING: ANSICOLORS.YELLOW,
        logging.ERROR: ANSICOLORS.RED,
        logging.CRITICAL: ANSICOLORS.BOLD_RED
    }


class LogFormats:
    fmt = log_format
    datefmt = log_dateformat


_LOGGER = logging.getLogger(__name__)


class BaseLogger(logging.Logger):
    "Logger class with the verbose function defined for type hinting purposes"

    def __init__(self, name, level = 0):
        super().__init__(name, level)

    def verbose(self, msg, *args, exc_info = None, stack_info = False, stacklevel = 1, extra = None):
        "Logs a message at VERBOSE level (below DEBUG)"
        return self.log(VERBOSE, msg, *args, exc_info = None, stack_info = False, stacklevel = 1, extra = None)



class BaseFormatter(logging.Formatter):
    
    formatter = logging.Formatter(log_format, log_dateformat)

    @classmethod
    def format(cls, record):
        return cls.formatter.format(record)


class ColorFormatter(logging.Formatter):
    
    def __init__(self, fmt = log_format, datefmt = log_dateformat, style = "%", validate = True):
        super().__init__(fmt, datefmt, style, validate)

    def format(self, record):
        formatted = BaseFormatter.format(record)
        if record.levelno < DEBUG:
            format_level = 0
        elif record.levelno in ANSI_FORMATS:
            format_level = record.levelno
        else:
            for level in ANSI_FORMATS:
                format_level = level
                if level >= record.levelno:
                    break

        prefix = ANSI_FORMATS.get(format_level,"default")
        return f"{prefix}{formatted}{ANSICOLORS.RESET}" 

class InkBoardQueueHandler(logging.handlers.QueueHandler):
    ##Altered from HA logger

    listener: Optional[logging.handlers.QueueListener] = None

    def handle(self, record: logging.LogRecord) -> Any:
        """Conditionally emit the specified logging record.

        Depending on which filters have been added to the handler, push the new
        records onto the backing Queue.

        The default python logger Handler acquires a lock
        in the parent class which we do not need as
        SimpleQueue is already thread safe.

        See https://bugs.python.org/issue24645
        """
        return_value = self.filter(record)
        if return_value:
            self.emit(record)
        return return_value

    def close(self) -> None:
        """Tidy up any resources used by the handler.

        This adds shutdown of the QueueListener
        """
        super().close()
        if not self.listener:
            return
        self.listener.stop()
        self.listener = None

streamhandler = logging.StreamHandler()
streamhandler.setFormatter(ColorFormatter(log_format, log_dateformat))

def init_logging(log_level: str = None, quiet: bool = False, verbose: bool = False) -> None:
    """Initialises the logger, such that the messages printed to stdout are color coded.
    
    Done before setting up queue handler, such that messages printed before reading the config are also logged.
    """

    logging.setLoggerClass(BaseLogger)

    logging.addLevelName(VERBOSE, "VERBOSE")
    logging.Logger.verbose = partialmethod(logging.Logger.log, VERBOSE)
    logging.verbose = partial(logging.log, VERBOSE)

    logging.basicConfig(format=log_format, 
                    datefmt=log_dateformat,
                    handlers=[streamhandler])
    base_logger = logging.getLogger()
    if log_level:
        base_logger.setLevel(log_level)
    elif verbose:
        base_logger.setLevel(VERBOSE)
    elif quiet:
        base_logger.setLevel(CRITICAL)
    else:
        base_logger.setLevel(WARNING)

    ##Would it be better to set up the stream handler already? I'm not quite sure

def overwrite_basicConfig(core: "CORE", config: "LoggerEntry"):
    "Overwrites the basicConfig of logging"

    base_args = asdict(config.basic_config)
    
    logging.basicConfig(**base_args, 
                        handlers=[streamhandler],
                        force=True
                        )
    
    new_format = base_args.get("format", log_format)
    new_datefmt = base_args.get("datefmt", log_dateformat)
    new_style = base_args.get("style", "%")
    new_formatter = logging.Formatter(new_format, new_datefmt, new_style)
    BaseFormatter.formatter = new_formatter


def setup_filehandler(core: "CORE", config: "LoggerEntry"):
    "Sets up the rotating filderhandler logs"

    if isinstance(config.log_to_file, (dict,MappingProxyType)):
        fileconf = config.log_to_file
    else:
        fileconf = {}
    
    fileconf.setdefault("backupCount", 5)
    fileconf.setdefault("filename", "inkboard.log") ##Default filename: logs -> but resolve to config folder.
    if isinstance(fileconf["filename"], str):
        name = fileconf["filename"]
        if "/" in name or "\\" in name:
            filename = Path(name)
        else:
            name = Path(name)
            filename = core.config.baseFolder / "logs" / name
            with suppress(FileExistsError):
                filename.resolve().parent.mkdir()
                _LOGGER.debug(f"Made folder for logs at {filename.parent}")

    else:
        filename = fileconf["filename"]
        assert isinstance(filename,Path),  "logging to file filename must be a string or Path"

    ##Check is performed for non custom too, but those folder will have just been made if not already there
    assert filename.parent.absolute().exists(), "Logging to custom locations requires the folder to exist"

    do_rollover = False
    if filename.exists():
        do_rollover = True

    fileconf["filename"] = filename
    file_handler = logging.handlers.RotatingFileHandler(**fileconf)
    file_handler.setFormatter(BaseFormatter())
    if do_rollover:
        file_handler.doRollover()

    logging.root.addHandler(file_handler)

    return

def setup_logging(core: "CORE"):
    "Sets up logging via the config definitions"
    
    config = core.config.logger

    if config.basic_config != False:
        overwrite_basicConfig(core, config)

    if config.log_to_file != False:
        setup_filehandler(core, config)
    
    ##Remote logging: setup later
    ##Need more knowledge on best practices, as well as knowing what is the best way to set up server/client for general connections

    logging.root.setLevel(config.level)
    for log_name, level in config.logs:
        logging.getLogger(log_name).setLevel(level)

    queue = Queue()
    queue_handler = InkBoardQueueHandler(queue)
    logging.root.addHandler(queue_handler)

    migrated_handlers: list[logging.Handler] = []
    for handler in logging.root.handlers[:]:
        if handler is queue_handler:
            continue
        logging.root.removeHandler(handler)
        migrated_handlers.append(handler)

    listener = logging.handlers.QueueListener(
        queue, *migrated_handlers, respect_handler_level=True)
    queue_handler.listener = listener
    
    listener.handlers

    listener.start()
