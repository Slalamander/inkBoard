"Logging classes for inkBoard."

import logging
import logging.handlers
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING, Union, TypedDict
from functools import partial, partialmethod
from contextlib import suppress
from dataclasses import asdict
from types import MappingProxyType
import struct

import yaml

from inkBoard.helpers import YAMLNodeDict
from inkBoard.constants import LOG_LEVELS, DEBUGGING

try:
    # Python 3.7 and newer, fast reentrant implementation
    # without task tracking (not needed for that when logging)
    from queue import SimpleQueue as Queue
except ImportError:
    from queue import Queue

if TYPE_CHECKING:
    from inkBoard import CORE as CORE
    from inkBoard.configuration.types import LoggerEntry

import inkBoard
import PythonScreenStackManager

try:
    import inkBoarddesigner
except ImportError:
    _baselog_modules = (inkBoard, PythonScreenStackManager)
else:
    _baselog_modules = (inkBoard, PythonScreenStackManager, inkBoarddesigner)


NOTSET = logging.NOTSET
VERBOSE = int(logging.DEBUG/2)
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
WARN = WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL
FATAL = logging.FATAL

# log_format = '%(asctime)s [%(levelname)s %(name)s %(funcName)s, line %(lineno)s %(YAML)s] %(message)s'

log_format = '${asctime} [${levelname} ${name} ${funcName}, line ${lineno}${YAML}] ${message}'
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

def get_handlers() -> list[logging.Handler]:
    if logging.root.handlers and isinstance(logging.root.handlers[0], InkBoardQueueHandler):
        queue_hdlr = logging.root.handlers[0]
        return queue_hdlr.listener.handlers
    else:
        return logging.root.handlers
    
def add_handler(handler: logging.Handler):
    ##in the root addHandler, some stuff happens regarding locks etc.
    ##So stuff may act up? will see
    if logging.root.handlers and isinstance(logging.root.handlers[0], InkBoardQueueHandler):
        queue_hdlr = logging.root.handlers[0]
        queue_hdlr.listener.handlers = (*queue_hdlr.listener.handlers, handler) ##Euh where/how to add these?
    else:
        logging.root.addHandler(handler)

def remove_handler(handler: logging.Handler):
    if logging.root.handlers and isinstance(logging.root.handlers[0], InkBoardQueueHandler):
        handlers = list(get_handlers())
        if handler in handlers:
            handlers.remove(handler)
            listener = logging.root.handlers[0].listener
            listener.handlers = tuple(handlers)
    else:
        logging.root.removeHandler(handler)

class BaseLogger(logging.Logger):
    "Logger class with the verbose function defined for type hinting purposes"

    def __init__(self, name, level = 0):
        super().__init__(name, level)

    def verbose(self, msg, *args, exc_info = None, stack_info = False, stacklevel = 1, extra = None):
        "Logs a message at VERBOSE level (below DEBUG)"
        return self.log(VERBOSE, msg, *args, exc_info = exc_info, stack_info = stack_info, stacklevel = stacklevel, extra = extra)

class BaseFormatter(logging.Formatter):
    
    formatter = logging.Formatter(log_format, log_dateformat, style="$")

    @classmethod
    def format(cls, record):
        if not "YAML" in record.__dict__:
            record.__dict__["YAML"] = ""
        else:
            record.__dict__["YAML"] = cls._format_yaml(record.__dict__["YAML"])
        return cls.formatter.format(record)

    @staticmethod
    def _format_yaml(yamlinfo):
        new_yaml = ""
        start_mark = None
        if isinstance(yamlinfo, yaml.Node):
            start_mark = yamlinfo.start_mark
            end_mark = yamlinfo.end_mark
        elif isinstance(yamlinfo,tuple):
            start_mark, end_mark = yamlinfo
        elif isinstance(yamlinfo,yaml.Node):
            start_mark = yamlinfo
            end_mark = None
        elif isinstance(yamlinfo,YAMLNodeDict):
            new_yaml = " " + str(yamlinfo)
        elif isinstance(yamlinfo,str):
            new_yaml = " " + yamlinfo

        if start_mark:
            f = Path(start_mark.name).name
            
            if end_mark and end_mark.line != start_mark.line:
                new_yaml = f" {f} lines {start_mark.line}-{end_mark.line}"
            else:
                new_yaml = f" {f} line {start_mark.line}"        
        return new_yaml


class ColorFormatter(logging.Formatter):
    
    def __init__(self, fmt = log_format, datefmt = log_dateformat, style = "$", validate = True):
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

class LogFileHandler(logging.handlers.RotatingFileHandler):
    """Class that handles logging to log files for inkBoard
    """    

    _current_handler : "LogFileHandler" = None

    def __init__(self, filename, mode = "a", maxBytes = 0, backupCount = 0, encoding = None, errors = None, level: Union[int,str] = None):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, True, errors)

        if self.__class__._current_handler:
            _LOGGER.debug("Removing previous instance of LogFileHandler and log_to_file settings")
            hdlr = self._current_handler
            remove_handler(hdlr)
            if hdlr.stream:
                hdlr.stream.close()
                assert hdlr.stream.closed, "Stream should be closed before setting up a new filehandler"
                hdlr.stream = None
            hdlr.close()

        self.__class__._current_handler = self

        if level is None:
            level = logging.root.level
        elif isinstance(level,str):
            level = level.upper()
        self.setLevel(level)

        if not isinstance(filename,Path): filename = Path(filename)
        if filename.exists():
            self.doRollover()
        _LOGGER.debug("LogFileHandler has been set up")


    def filter(self, record):
        if record.levelno < self.level:
            return False
        return super().filter(record)

class LocalhostSocketHandler(logging.handlers.SocketHandler):
    
    def __init__(self, port, level : Union[int,str] = None):
        super().__init__('localhost', port)
        self.added = False

        if level == None:
            level = streamhandler.level
        elif type(level) == str:
            level = level.upper()
        self.setLevel(level)
        
    def addToHandlers(self):
        add_handler(self)
        self.added = True

    def close(self):
        super().close()
        remove_handler(self)
    
    def format(self, record):
        if self.formatter:
            fmt = self.formatter
        else:
            fmt = streamhandler.formatter
        return fmt.format(record)

    def makePickle(self, record):
        s = self.format(record).encode()
        slen = struct.pack(">L", len(s))
        return slen + s

    def send(self, s):
        if not self.added:
            if self in get_handlers():
                self.added = True
            else:
                _LOGGER.warning("Cannot send logs before being added to handlers")
                return
        return super().send(s)    

streamhandler = logging.StreamHandler()
streamhandler.setFormatter(ColorFormatter(log_format, log_dateformat))


def _set_baselogger_levels(log_level):
    ##Sets the log level for the base packages

    for log_mod in _baselog_modules:
        logging.getLogger(log_mod.__name__).setLevel(log_level)

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
                    style="$",
                    handlers=[streamhandler])
    
    if log_level or log_level == 0:
        pass
    elif verbose:
        log_level = VERBOSE
    elif quiet:
        log_level = CRITICAL
    else:
        log_level = WARNING
    

    _set_baselogger_levels(log_level)

    # base_logger = logging.getLogger()
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

    if isinstance(logging.root.handlers[0], InkBoardQueueHandler):
        queue_hdlr = logging.root.handlers[0]
        for hdlr in queue_hdlr.listener.handlers:
            ##Remove any rotating file handlers if present
            ##For decent workings, also with reloading, I think it's best to create a childclass to handle file logging
            ##As a singleton, so it can basically persist across reloads -> no, removing it and instantiating is better also to change the config.

            ##Also, make that class have a custom logging level, and also give an option to not log error tracebacks
            if isinstance(hdlr, LogFileHandler):
                hdlr.close()
                logging.root.removeHandler(hdlr)
    
    if isinstance(config.log_to_file, (dict,MappingProxyType)):
        fileconf = dict(config.log_to_file)
    else:
        fileconf = {}

    if DEBUGGING and not fileconf.get("enable_in_debug", False):
        _LOGGER.debug("Not setting up filelogger, debug in progress")
        return

    fileconf.setdefault("backup_count", 5)
    fileconf["backupCount"] = fileconf.pop("backup_count")
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

    fileconf["filename"] = filename
    file_handler = LogFileHandler(**fileconf)
    file_handler.setFormatter(BaseFormatter())

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

    # logging.root.setLevel(NOTSET)
    streamhandler.setLevel(config.level)
    _set_baselogger_levels(config.level)

    for log_name, level in config.logs:
        logging.getLogger(log_name).setLevel(level)

    queue = Queue()
    queue_handler = InkBoardQueueHandler(queue)

    if len(logging.root.handlers) == 1 and isinstance(logging.root.handlers[0], InkBoardQueueHandler):
        return
    else:
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
        
        ##Determine how to deal with this inbetween reloads since it will likekly set up multiple queues like this
        listener.start()

def getLogger(name: Union[str,None] = None) -> "BaseLogger":
    """Convenience method to get a logger with type hinting for additional levels like verbose.
    
    Return a logger with the specified name, creating it if necessary.
    If no name is specified, return the root logger.
    """
    return logging.getLogger(name)

class FileLogEntry(TypedDict):
    "Entries that can be used for the ``log_to_file`` logging entry"

    backup_count : int = 5
    "Maximum number of logs to retain"

    filename : str = "inkBoard.log"
    """Base name of the logs.
    If a path, this will also determine the folder the logs will be put in.
    Otherwise, they're put in a logs folder within the config directory
    """

    level : Union[str,int] = None
    """The minimum level of logs to log to the file

    If left at None, it will be set to the same level as the base logger.
    """

    enable_in_debug : bool = False
    "Enables the file logger even if a debugger is currently attached"

##Todos for logging:
##Setup socketlogger within the api extension -> no, not socketlogger, use httphandler probably?
##I'm still not fully sure what the best way to set up network logging is tbh
##Add setting to handle std out logging (via a terminal key)
##Handle log queue being set up every time a reload is called

