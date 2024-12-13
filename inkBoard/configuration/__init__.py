"""
Handles reading and setting up the yaml config for inkBoard
"""
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from . import const

from .configure import config

if TYPE_CHECKING:
    from yaml import Node

##Will probably set up a new logger class for this that can just be passed the node
_LOGGER = logging.getLogger(__name__)

def log_yaml_line(level: int, msg: str, node: "Node", *args, **kwargs):
    yaml_line = node.start_mark.line
    yaml_file = node.start_mark.name
    msg = f"[yaml file {yaml_file} line {yaml_line}]: {msg}"
    _LOGGER.log(level, msg, *args, **kwargs)
