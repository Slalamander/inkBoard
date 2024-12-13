"""
This folder can hold integrations for inkBoard.
"""

from types import ModuleType

imported_modules : dict[str,ModuleType] = {}
"""
Holds the modules for the imported integrations. Can be used to access client objects, for example.
The value is set by intergration_loader.py, when import_integrations is called.
"""