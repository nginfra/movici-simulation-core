import functools
import logging
import sys
import typing as t
import warnings

from movici_simulation_core.settings import Settings


def get_logger(settings: Settings, name=None, capture_warnings=True):
    logger = logging.getLogger(name or settings.name)
    level = logging.getLevelName(settings.log_level.upper())
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(settings.log_format, style="{"))
    logger.addHandler(handler)
    if capture_warnings:
        captureWarnings(logger)
    return logger


# Warnings integration
# Reimplementation of warning integration from `logging` module with the difference that you can
# specify which logger to use as an output

_warnings_showwarning: t.Optional[callable] = None


def captureWarnings(logger):
    """
    If `logger` is an instance of `logging.Logger`, redirect all warnings to that logger.
    If `logger` is `None`, ensure that warnings are not redirected to logging but to their original
    destinations.
    """
    global _warnings_showwarning
    if logger is None and _warnings_showwarning is not None:
        warnings.showwarning = _warnings_showwarning
        _warnings_showwarning = None
        return
    if _warnings_showwarning is None:
        _warnings_showwarning = warnings.showwarning

    warnings.showwarning = functools.partial(_showwarning, logger)


def _showwarning(logger, message, category, filename, lineno, file=None, line=None):
    """
    Implementation of showwarning which redirects to logging, which will first
    check to see if the file parameter is None. If a file is specified, it will
    delegate to the original warnings implementation of showwarning. Otherwise,
    it will call warnings.formatwarning and will log the resulting string to a
    warnings logger named "py.warnings" with level logging.WARNING.
    """
    if file is not None:
        if _warnings_showwarning is not None:
            _warnings_showwarning(message, category, filename, lineno, file, line)
    else:
        s = warnings.formatwarning(message, category, filename, lineno, line)
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
        logger.warning("%s", s)
