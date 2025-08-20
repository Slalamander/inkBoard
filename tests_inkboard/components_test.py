from typing import cast, get_args
import json
from pathlib import Path
import sys
import importlib
from contextlib import suppress

import pytest

import inkBoard
from inkBoard import CORE, util

from inkBoard.components import (
    BaseComponent,
    Platform,
    Integration,
)
from inkBoard.types import componentypes, manifestjson, inkboardrequirements
from inkBoard.constants import COMPONENT_PLURAL_MAP, COMPONENT_SINGULAR_MAP



#For testing:
#Use dummy integration; move it into the configs folder of the tests though

TEST_INTEGRATIONS_PATH = Path(__file__).parent / "configs" / "custom" / "integrations"

def test_component_type_map():
    #Verify that the type hint and map for plurals are consistent with each other
    types = get_args(componentypes)
    assert len(types) == len(COMPONENT_PLURAL_MAP), "types or component map are mismatched"

    if bad_vals := [v for v in COMPONENT_PLURAL_MAP.values() if v not in types]:
        raise ValueError(f"Component map has bad values {bad_vals}")

#TODO use pytest tempdirs to test downloader

class TestPlatformComponent:
    pass

class TestBaseComponent:
    #Tests for the basic component functioning
    #Tests are done with an integration instance, since the BaseComponent itself is an abstract baseclass

    def test_raw_config(self, raw_config : manifestjson, base_component : BaseComponent):
        #Test if the base component functions as expected
        #Also test if simply passing a config causes an error

        with pytest.raises(TypeError):
            testint = Integration(raw_config)
        
        assert base_component.abstract_component, "Passing a raw config dict means the component should be abstract"
        assert not base_component.core_component, "Abstract components cannot be a real type"
        assert not base_component.designer_component, "Abstract components cannot be a real type"
        assert not base_component.custom_component, "Abstract components cannot be a real type"

        assert base_component.module_name == f"ABSTRACT.integrations.{raw_config['name']}"
        return

    def test_bad_version(self, base_component : BaseComponent):
        #test if a version returns false
        raw_config = base_component.config
        raw_config["inkboard_requirements"]["inkboard_version"] = "<0.0.1"
        assert not base_component.validate_requirements()
        return
    
    def test_versions(self, base_component : BaseComponent):
        #test if all versions indeed pass

        raw_config = base_component.config

        raw_config["inkboard_requirements"]["pssm_version"] = "0.0.1"
        raw_config["inkboard_requirements"]["designer"] = "0.0.1"
        assert base_component.validate_requirements(validate_designer=True)
        return
    
    def test_loading_abstract(self, base_component : BaseComponent):
        #Test if calling load on an abstract component raises an exception
        
        with pytest.raises(ImportError):
            base_component.load_module()
        return

class IntegrationTestBase:
    foldername = "dummy_integration"

class TestDummyIntegration(IntegrationTestBase):

    def test_basic_properties(self, dummy_integration: Integration):

        assert dummy_integration.config == json.loads((TEST_INTEGRATIONS_PATH / self.foldername / Integration.CONFIG_FILE_NAME).read_text())
        assert dummy_integration.name == self.foldername
        assert dummy_integration.location == TEST_INTEGRATIONS_PATH / self.foldername
        
        assert dummy_integration.component_type == "integration"
        assert dummy_integration.module_name == f"custom.integrations.{self.foldername}"
        
        assert not dummy_integration.is_loaded

        with pytest.raises(AttributeError):
            dummy_integration.requires_start
        return

    def test_integration_installtype(self, dummy_integration: Integration):
        #Assert if the 

        assert not dummy_integration.designer_component
        assert not dummy_integration.core_component
        assert not dummy_integration.abstract_component
        assert dummy_integration.custom_component

    @pytest.fixture(scope="class")
    def dummy_integration(self):
        f = TEST_INTEGRATIONS_PATH / self.foldername
        dummy = Integration(f)
        yield dummy
        mod = dummy.module
        return

class TestIntegrationImporting(IntegrationTestBase):
    
    
    def test_load_before_custom(self, import_dummy: Integration):

        with pytest.raises(ImportWarning):
            import_dummy.load_module()
        return
    
    def test_load_before_custom_with_file_location(self, import_dummy: Integration):

        #For now, this does not work, as custom is not imported
        #Want to see what happens when it is loaded itself, perhaps?
        #Or simply not use custom as a name I guess but check what the fromfilename does
        # n = inspect.getmodulename(import_dummy.location / "__init__.py") #Does not work, simply returns __init__
        # Idk see what I'm doing for importing platforms or something

        ##Per above comment: try with package name like inkBoard.integrations.custom.{dummy}
        import_dummy.load_module(load_from_file_location=True)
        return
    

    def test_load(self, import_dummy : Integration):
        #When testing this, also think about cleanup probably?

        #Probably need to append the name to Path here?
        #I am 100% sure I have done that somewhere -> see init of the config
        #Test how safe this is when run after each other?
        #Also, may want to add a from_location key to the function
        add_custom_to_path()
        import_dummy.load_module()
        assert import_dummy.module is not None, "dummy was not imported correctly"
        return
    
    def test_cleanup(self, import_dummy: Integration):
        
        add_custom_to_path()
        import_dummy.load_module()
        newmod = importlib.import_module(".dummy", import_dummy.module_name)

        mod = import_dummy.module
        modname = mod.__name__
        cleanup_imported_component(import_dummy, clean_custom=True)

        assert modname not in sys.modules, "import_dummy was not cleaned up correctly"
        assert newmod.__name__ not in sys.modules, "submodule of import_dummy was not cleaned up"
        
        submods = [m.__name__ in sys.modules for m in util.get_all_submodules(mod)]
        assert not any(submods), f"Modules from the import dummy were left over {[m.__name__ for m in submods]}"

        assert "custom" not in sys.modules, "custom was not cleaned up correctly"
        return

    @pytest.fixture()
    def import_dummy(self):
        #Use this one to test importing; Should clean up after itself
        f = TEST_INTEGRATIONS_PATH / self.foldername
        dummy = Integration(f)
        yield dummy

        cleanup_imported_component(dummy)
        return

@pytest.fixture
def raw_config() -> manifestjson:
    
    return manifestjson(
        name = "test_integration",
        version="0.0.1b1",
        inkboard_requirements=inkboardrequirements(
            inkboard_version="0.0.1"
        )
    )

@pytest.fixture
def base_component(raw_config) -> Integration:

    return Integration(None, raw_config)

def add_custom_to_path():
    folder = Path(__file__).parent / "configs"
    folder = str(folder)
    sys.path.insert(0, folder)
    import custom
    sys.path.remove(folder)
    sys.path_importer_cache.pop(folder, None)
    return

def cleanup_imported_component(component : BaseComponent, clean_custom : bool = True):
    """Cleans up an imported component by removing it from sys.modules

    This also removed the `custom` module from the modules

    Parameters
    ----------
    component : BaseComponent
        The component to clean up
    """    

    if component.module:
        mods = util.get_all_submodules(component.module_name)
        mod_list = [*mods, component.module]
        for mod in mod_list:
            # importlib.reload(mod)
            sys.modules.pop(mod.__name__, None)
    
    if clean_custom:
        sys.modules.pop("custom", None)
    return