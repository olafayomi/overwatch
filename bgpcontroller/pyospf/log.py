# !/usr/bin/env python
# -*- coding:utf-8 -*-


"""
logging handler.
"""

from __future__ import print_function
import inspect
import logging
import logging.config
import logging.handlers
import os
import sys

CONF = dict()
CONF["verbose"] = False
CONF["use-stderr"] = True
CONF["log-dir"] = None
CONF["log-file"] = None
CONF["log-file-mode"] = "0644"

DEBUG_LOG_FORMAT = '%(asctime)s.%(msecs)03d %(process)d %(levelname)s %(name)s ' \
                   '%(funcName)s %(lineno)d [-] %(message)s'
INFOR_LOG_FORMAT = '%(asctime)s.%(msecs)03d %(process)d %(levelname)s %(name)s [-] %(message)s'
_EARLY_LOG_HANDLER = None


def early_init_log(level=None):
    global _EARLY_LOG_HANDLER
    _EARLY_LOG_HANDLER = logging.StreamHandler(sys.stderr)

    log = logging.getLogger()
    log.addHandler(_EARLY_LOG_HANDLER)
    if level is not None:
        log.setLevel(level)


def _get_log_file():
    if CONF["log-file"]:
        return CONF.log_file
    if CONF["log-dir"]:
        return os.path.join(CONF.log_dir,
                            os.path.basename(inspect.stack()[-1][1])) + '.log'
    return None


def _set_log_format(handlers, _format):
    for handler in handlers:
        handler.setFormatter(logging.Formatter(_format))


def init_log():
    global _EARLY_LOG_HANDLER

    log = logging.getLogger()

    if CONF["use-stderr"]:
        log.addHandler(logging.StreamHandler(sys.stderr))

    if _EARLY_LOG_HANDLER is not None:
        log.removeHandler(_EARLY_LOG_HANDLER)
        _EARLY_LOG_HANDLER = None

    log_file = _get_log_file()
    if log_file is not None:
        log.addHandler(logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=5))
        mode = int(CONF["log-file-mode"], 8)
        os.chmod(log_file, mode)
        for handler in log.handlers:
                    handler.setFormatter(logging.Formatter(INFOR_LOG_FORMAT))

    if CONF["verbose"]:
        log.setLevel(logging.DEBUG)
        for handler in log.handlers:
                    handler.setFormatter(logging.Formatter(DEBUG_LOG_FORMAT))
    else:
        log.setLevel(logging.INFO)
        _set_log_format(log.handlers, INFOR_LOG_FORMAT)
