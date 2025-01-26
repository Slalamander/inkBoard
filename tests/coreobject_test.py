"""Tests for the CORE object

CORE object has some protections applied to ensure it runs 
"""

from inkBoard import core as CORE

import pytest

CORE._DESIGNER_RUN = False

@pytest.fixture(autouse=True)
def setup_core():
    CORE()

    yield

    CORE._reset()

def test_property_setting():
    #Tests if properties cannot be set directly

    with pytest.raises(AttributeError):
        CORE.config = "A config"

    CORE._config = "A config"
    assert CORE.config == "A config", "Changing private attribute did not change the public attribute"

    ##cleanup
    # CORE._reset()

def test_core_setup():
    ##Tests if CORE() raises an error when calling __init__ again
    with pytest.raises(AssertionError):
        # CORE()
        CORE()

    CORE._reset()
    CORE()

    # CORE._reset()
