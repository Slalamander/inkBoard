"Tests for the configuration"

import dataclasses
import inspect
import logging

from PythonScreenStackManager.pssm import PSSMScreen
from inkBoard.configuration.types import ScreenEntry

_LOGGER = logging.getLogger(__name__)

def test_screenentry():
    ##This should test if the screenentry matches the __init__ of the screen
    ##So the current validation that happens in the file already.
    
    warnings = []
    init_args = inspect.signature(PSSMScreen.__init__)
    param_names = [param for param in init_args.parameters]

    fields = dataclasses.fields(ScreenEntry)
    field_names = [field.name for field in fields]

    for param in init_args.parameters.values():
        if param.name in {"self", "device"}:
            continue
        if param.name not in field_names:
            _LOGGER.warning(f"ScreenEntry is missing parameter {param.name}")
            continue
        else:
            for field in fields:
                if field.name == param.name:
                    break
        if param.annotation != field.type:
            msg = f"ScreenEntry field {field.name} does not match the annotation of the parameter"
            _LOGGER.warning(msg)
            warnings.append(msg)
        
        if param.default == param.empty:
            if field.default != dataclasses._MISSING_TYPE:
                msg = f"ScreenEntry {field.name} is not required but it should be"
                _LOGGER.warning(msg)
                warnings.append(msg)

    for field in field_names:
        if field not in param_names:
            msg = f"Illegal field in ScreenEntry: {field}"
            _LOGGER.warning(msg)
            warnings.append(msg)
    
    assert not warnings, "ScreenEntry does not match with parameters for screen"

    return

if __name__ == "__main__":
    test_screenentry()