"""
This module takes care of building a dashboard from a config layout.
Its functions can also be called for custom dashboards.
"""

import logging
from typing import TYPE_CHECKING

from ..configuration.loaders import const as yaml_const
from ..helpers import DashboardError

from .loader import DashboardLoader
from .validate import validator_dict

from PythonScreenStackManager.elements import Layout, TabPages, StatusBar

if TYPE_CHECKING:
    from inkBoard import config, core as CORE

logger = logging.getLogger(__name__)

def build_config_elements(config : "config", core: "CORE"):
    """
    Builds all the elements defined in the configuration.
    Order of parsing: elements, layouts, popups, tabs.
    """
    ##Statusbar can simply be parsed from the dict (though should be done here ofc)
    ##main_element or smth needs to be defined somewhere. I think under inkBoard. -> either use a main_tabs key, or simply tabs and take that as default
    ##Default should be None.

    conf = dict(config.configuration)

    DashboardLoader._CORE = core

    if "home_assistant" in conf:
        _add_ha_defaults()

    dash_conf = {}
    for conf_key in yaml_const.DASHBOARD_KEYS:
        if conf_key in conf:
            ##Determine how to deal with the validators, i.e. they should only validate the top_level elements
            validator = validator_dict.get(conf_key,validate.validate_general)
            DashboardLoader._validator = validator

            conf_res = DashboardLoader().construct_dashboard_node(conf[conf_key],True)

            if conf_key  == "statusbar":
                if conf_res == None:
                    conf_res = {}
                else:
                    conf_res = dict(conf_res)
                status_conf = {"size": conf_res.pop("size","?*0.05"),
                                                "location": conf_res.pop("location","top")}
                if "orientation" not in conf_res:
                    if status_conf["location"] in {"top","bottom"}:
                        conf_res["orientation"] = "horizontal"
                    else:
                        conf_res["orientation"] = "vertical"
                try:
                    statusbar = StatusBar(**conf_res)
                    status_conf["element"] = statusbar
                    conf_res = status_conf
                except TypeError as e:
                    logger.error(f"Error in the config for {conf_key}: {e}. Check if the initial arguments were defined correctly.")
                    DashboardLoader._config_error = True
                    continue
            elif conf_key == "main_tabs":
                try:
                    conf_res = TabPages(**conf_res)
                except TypeError as e:
                    logger.error(f"Error in the config for {conf_key}: {e}. Check if the initial arguments were defined correctly.")
                    DashboardLoader._config_error = True
                    continue
                
            dash_conf[conf_key] = conf_res

    if DashboardLoader._config_error:
        raise DashboardError("Error parsing configuration for the dashboard. See the logs for more information.") #@IgnoreExceptions
    return dash_conf

def get_main_layout(dash_config: "config.configuration"):
    """
    Builds the main layout element based on the settings in the configuration.
    Returns the main layout element. Unless otherwise specified in the config, this will return the tab element made from the tabs key, and the statusbar, if specified
    """

    layout = []

    if dash_config.get("main_tabs",None):
        main_elt = dash_config["main_tabs"]

    if "statusbar" in dash_config:
        statusbar_conf = dash_config["statusbar"]
        statusbar = statusbar_conf["element"]
        loc = statusbar_conf["location"]
        if loc in {"left","right"}:
            status_tuple = (statusbar,statusbar_conf["size"])
            if loc == "left":
                statusbar_row = ["?", status_tuple, (main_elt,"?")]
            else:
                statusbar_row = ["?", (main_elt,"?"), status_tuple]
            layout.append(statusbar_row)
        elif loc in {"top", "bottom"}:
            statusbar_row = [statusbar_conf["size"], (statusbar,"?")]
            main_row = ["?", (main_elt,"?")]
            if loc == "top":
                layout.extend([statusbar_row,main_row])
            else:
                layout.extend([main_row,statusbar_row])
    else:
        layout.append(["?", (main_elt,"?")])

    return Layout(layout)

def _add_ha_defaults():
    from inkBoard.core import integration_loader
    imported_modules = integration_loader.imported_integrations
    ha_integration = "homeassistant_client"
    if ha_integration  not in imported_modules:
        return
    
    import importlib

    ha_module = integration_loader._imported_modules[ha_integration]    
    ha_parser = importlib.import_module(".parser",ha_module.__package__)

    ha_elements = getattr(ha_parser,"element_dict",{})
    from . import loader
    loader.default_elements.update(ha_elements)

    