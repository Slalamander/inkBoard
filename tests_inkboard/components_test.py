from typing import cast, get_args
import json
from pathlib import Path

import pytest

import inkBoard
from inkBoard import CORE

from inkBoard.components import (
    BaseComponent,
    Platform,
    Integration,
)
from inkBoard.types import componentypes, manifestjson
from inkBoard.constants import COMPONENT_PLURAL_MAP



#For testing:
#Use dummy integration; move it into the configs folder of the tests though

DUMMY_INTEGRATION_PATH = Path(__file__).parent / "configs" / "custom" / "integrations" / "dummy_integration"

def test_component_type_map():
    #Verify that the type hint and map for plurals are consistent with each other
    types = get_args(componentypes)
    assert len(types) == len(COMPONENT_PLURAL_MAP), "types or component map are mismatched"

    if bad_vals := [v for v in COMPONENT_PLURAL_MAP.values() if v not in types]:
        raise ValueError(f"Component map has bad values {bad_vals}")

#TODO use pytest tempdirs to test downloader

class TestPlatformComponent:
    pass

class TestIntegrationComponent:
    raw_conf = {
            "name": "test_integration",
            "version": "0.0.1b1"
        }

    def test_raw_config(self):

        conf = self.raw_conf.copy()
        with pytest.raises(TypeError):
            #Ensure location has to be specified as None
            testint = Integration(conf)
        
        testint = Integration(None, conf)
        assert testint.abstract_component, "Passing a raw config dict means the component should be abstract"
        assert not testint.core_component, "Abstract components cannot be a real type"
        assert not testint.designer_component, "Abstract components cannot be a real type"
        assert not testint.custom_component, "Abstract components cannot be a real type"
        return 

def test_dummy_manifest():
    f = DUMMY_INTEGRATION_PATH / Integration.CONFIG_FILE_NAME
    t = f.read_text()
    return