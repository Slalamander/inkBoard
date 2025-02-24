"""Custom exceptions for PythonScreenStackManager and inkBoard
"""

from PythonScreenStackManager.exceptions import *

class InkBoardError(Exception):
    "Base Exception for inkBoard"

class DeviceError(InkBoardError):
    "Something went wrong setting up the device"

class ScreenError(InkBoardError):
    "Something went wrong setting up the screen instance"

class ConfigError(InkBoardError):
    "Something is wrong with the configuration"

class DashboardError(ConfigError):
    "Unable to setup the dashboard"

class QuitInkboard(InkBoardError):
    "Exception to set as eStop to quit the current inkBoard session"

class inkBoardParseError(InkBoardError, ValueError):
    "Something could not be parsed correctly"

class inkBoardTemplateError(DashboardError):
    "Base error for anything to do with template Elements"

class TemplateLoadError(inkBoardTemplateError):
    "Something went wrong loading and/or creating a template"

class TemplateElementError(inkBoardTemplateError):
    "Something went wrong parsing a template element"

class TemplateTypeError(inkBoardTemplateError):
    "The type from the parsed template is invalid"