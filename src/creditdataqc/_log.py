import sys
import logging.config
import logging
from pathlib import Path

from creditdataqc.config._config import AppConfig

_LOG_APPNAME = AppConfig.general.app_name
_LOG_LEVEL = AppConfig.logging.log_level
_LOG_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
_LOG_FILE_NAME = f"{_LOG_APPNAME}.log"
_LOG_FILEPATH = Path(AppConfig.logging.log_filepath) / _LOG_FILE_NAME
_LOG_FILEPATH.parent.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "formatter": {
            "format": "%(asctime)s - %(levelname)s - %(name)s - (%(filename)s:%(lineno)s) - %(message)s",
            "datefmt": _LOG_DATETIME_FORMAT,
        },
        "file_formatter": {
            "format": "%(asctime)s - %(levelname)s - %(name)s - (%(filename)s:%(lineno)s) - %(message)s",
            "datefmt": _LOG_DATETIME_FORMAT,
        },
    },
    "handlers": {
        "stream_handler": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "formatter",
            "stream": "ext://sys.stdout",
        },
        "file_handler": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "file_formatter",
            "filename": _LOG_FILEPATH,
            "mode": "a",
            "encoding": "utf-8",
        },
        "root_file_handler": {
            "class": "logging.FileHandler",
            "level": "WARNING", # External packages and other root loggers are only allowed WARNING and above to file
            "formatter": "file_formatter",
            "filename": _LOG_FILEPATH,
            "mode": "a",
            "encoding": "utf-8",
        },
    },
    "root": {
        "handlers": ["stream_handler", "root_file_handler"],
        "level": _LOG_LEVEL,
    },
    "loggers": {
        _LOG_APPNAME: { # Writes to the same file as the root logger, but handler allows for different level
            "handlers": ["stream_handler", "file_handler"],
            "level": _LOG_LEVEL,
            "propagate": False, # Our loggers won't propagate to root logger to avoid duplicate messages
        },
    },
}

logging.config.dictConfig(LOGGING) # Ensure all loggers write to the same file _LOG_FILEPATH
logging.captureWarnings(True) # Redirects warnings issued by the 'warnings' module to the logging system

def get_logger(name: str = None) -> logging.Logger:
    """Handle logger object.

    Return a logger with the specified name or, if no name is specified, return a
    logger which is the root logger of the hierarchy. If specified, the name is
    typically a dot-separated hierarchical name like “a”, “a.b” or “a.b.c.d”.
    All calls to this function with a given name return the same logger instance.
    This means that logger instances never need to be passed between different parts
    of an application.
    """
    if name:
        return logging.getLogger(f"{_LOG_APPNAME}.{name}") # Ensure all applcation loggers are under the _LOG_APPNAME logger hierarchy
    return logging.getLogger(_LOG_APPNAME)


def custom_excepthook(exc_type, exc_value, exc_traceback):
    '''
    Custom function aimed to replace de default behaviour of sys.excepthook, which is the interpreter default function
    called when an exception is raised and uncaught, right before exiting the program.

    By default, it simply prints out a given traceback and exception to sys.stderr (console),
     we modify it so that it also logs the error via the logger named 'Uncaught_Exception'.
    '''
    logger = get_logger(__name__)
    if issubclass(exc_type, KeyboardInterrupt):#If KeyboardInterrupt raised, simply handle exception using default behaviour
        sys.__excepthook__(exc_type, exc_value, exc_traceback) # sys.__excepthook__ objects contain the original values of sys.excepthook
    else: #Otherwise log an error message specifying unchaught exception and then proceed with default behaviour
        logger.critical("Uncaught Exception", exc_info=(exc_type, exc_value, exc_traceback))
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

# Override the default excepthook
sys.excepthook = custom_excepthook
