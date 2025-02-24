"Tests for template elements"

##Tests to include:
##Validation of the template itself (throw error for mismatched variables i.e. maps can only be maps etc)
##Validation of missing required variables
##Validation of wrong variable type for both map and sequence extenders

import pytest
import yaml
from inkBoard.exceptions import inkBoardTemplateError, TemplateLoadError, TemplateElementError

from inkBoard.dashboard.templates import TemplateLoader, TemplateElement
from inkBoard.platforms.dummy import DummyDevice
from inkBoard.elements import Button, Tile, GridLayout

from PythonScreenStackManager.pssm import PSSMScreen

d = DummyDevice()
PSSMScreen(d)

def _get_yaml_nodes(template_str):
    return yaml.SafeLoader(template_str).get_single_node()

class TestTemplateLoader:

    def _load_template(self, template : str):
        
        n = _get_yaml_nodes(template)
        key_node, value_node = n.value[0]
        return TemplateLoader(key_node.value, value_node).construct_template()

    def test_missing_element_key(self):
        "Test if an error is thrown if the element key is left out of the template"
        template_name = "test_template"
        template_str = f"""
        {template_name}:
            defaults:
                a_var: 5
                ext_variable:
                    my_val: tonk
                var: 
                    - a list
        """
        
        
        with pytest.raises(TemplateLoadError):
            self._load_template(template_str)

        return

    def test_invalid_template_entry(self):
        "Test if an error is thrown if a key other than element or default is present"
        template_name = "test_template"
        template_str = f"""
        {template_name}:
            defaults:
                a_var: 5
                ext_variable:
                    my_val: tonk
                var: 
                    - a list
            element:
                - type: Button
            some_key: I shouldn't be here!
        """

        with pytest.raises(TemplateLoadError):
            self._load_template(template_str)


    def test_duplicate_map_and_sequence_var(self):
        "Tests if an error is thrown if a variable is used for both a mapping and sequence node"

        template_name = "variable_place_test"
        template_str = f"""
        {template_name}:
            element:
                type: GridLayout
                elements:
                    - type: Tile
                      element_properties:
                        text:
                            text: some test
                            !template_extend : extend_var
                    - !template_extend extend_var
        """
        with pytest.raises(TemplateLoadError):
            self._load_template(template_str)

    def test_invalid_default_type(self):
        "Tests if the values specified in the defaults have the correct typing"
        template_name = "variable_place_test"
        template_str = f"""
        {template_name}:
            defaults:
                extend_var:
                    value: wrong
            element:
                type: GridLayout
                elements:
                    - !template_extend extend_var
        """
        with pytest.raises(TemplateLoadError):
            self._load_template(template_str)

        template_str = f"""
        {template_name}:
            defaults:
                extend_var:
                    - wrong
            element:
                type: Tile
                element_properties:
                text:
                    text: some test
                    !template_extend : extend_var
        """
        with pytest.raises(TemplateLoadError):
            self._load_template(template_str)

    def test_valid_template(self):
        template_name = "a_correct_template"
        template_str = f"""
        {template_name}:
            element:
                type: GridLayout
                defaults:
                    my_text: Hello World!
                elements:
                    - type: Tile
                      element_properties:
                        text:
                            text: !template_var my_text
                            !template_extend : extend_map
                    - !template_extend extend_list
        """

        assert isinstance(self._load_template(template_str),TemplateElement)

class TestTemplateParser(TestTemplateLoader):
    "Tests parsing templates"

    ##Tests to create:
    ##Check if all sequence variables are lists, and similar for maps [x]
    ##Check if it runs when not passing all required variables [x]
    ##Check if the parsed element has the correct properties applied
        ##So that also means checking if the extend tags result in the expected element attribute
        ##Also test if double keys in an extend variable overwrites present keys
    ##Check if it errors when the element config is invalid -> no that's not a template thing tbh

    def test_missing_required_variable(self):
        template_name = "missing_variable_template"
        template_str = f"""
        {template_name}:
            defaults:
                bar: baz
            element:
                type: GridLayout
                elements:
                    - type: Text
                      text: !template_var my_text
                      foo: !template_variable bar
        """
        template = self._load_template(template_str)
        with pytest.raises(TemplateElementError):
            template.construct_element({"some_variable": "hi"})

        template.construct_element({"my_text": "Hello Tests!"})

    def test_invalid_mapping_variable(self):
        template_name = "invalid_mapping_template"
        template_str = f"""
        {template_name}:
            defaults:
                elt_text: Hello World!
            element:
                type: GridLayout
                elements:
                    - type: Tile
                      icon: mdi:test-tube
                      text: !tmp_var elt_text
                      element_properties:
                        text:
                            font: default 
                            !tmp_extend : text_properties
        """
        template = self._load_template(template_str)
        
        with pytest.raises(TemplateElementError):
            template.construct_element({"text_properties": "hi"})

        with pytest.raises(TemplateElementError):
            template.construct_element({"text_properties": ["hi"]})

        template.construct_element()  ##This should not throw errors
        template.construct_element({"text_properties": {"font_color": "green"}})

    def test_invalid_sequence_variable(self):
        template_name = "invalid_sequence_template"
        template_str = f"""
        {template_name}:
            defaults:
                elt_text: Hello World!
            element:
                type: GridLayout
                column_sizes:
                    - "?"
                    - !tmp_extend col_sizing
                elements:
                    - type: Tile
                      icon: mdi:test-tube
                      text: !tmp_var elt_text
                      element_properties:
                        text:
                            font: default 
                            !tmp_extend : text_properties
        """
        template = self._load_template(template_str)
        
        with pytest.raises(TemplateElementError):
            template.construct_element({"col_sizing": "hi"})

        with pytest.raises(TemplateElementError):
            template.construct_element({"col_sizing": {"hi": "World!"}})

        template.construct_element()  ##This should not throw errors
        template.construct_element({"col_sizing": ["r"]})

    def test_regular_variable(self):
        "Test if a regular variable takes on the correct value in a simple template"

        template_name = "regular_variable_test"
        default_text = "Hello World!"

        template_str = f"""
        {template_name}:
            defaults:
                elt_text: {default_text}
            element:
                type: Button
                text: !tmp_var elt_text
        """

        template = self._load_template(template_str)
        
        default_elt = template.construct_element()
        assert default_elt.text == default_text

        var_text = "Foo Bar"
        var_elt = template.construct_element({"elt_text": var_text})
        assert var_elt.text == var_text

    def test_simple_mapping_variable(self):
        
        template_name = "invalid_type_template_1"
        default_text = "Hello World!"
        default_icon = "mdi:earth"

        default_font_color = "maroon"

        template_str = f"""
        {template_name}:
            defaults:
                elt_text: {default_text}
                elt_icon: {default_icon}
            element:
                type: Tile
                text: !tmp_var elt_text
                icon: !tmp_var elt_icon
                element_properties:
                    text:
                        font_color: {default_font_color}
                        !tmp_extend : text_props
        """

        template = self._load_template(template_str)
        
        default_elt : Tile = template.construct_element()
        text_props = default_elt.element_properties["text"]
        assert text_props["font_color"] == default_font_color

        new_props = {"font_size": 50}
        new_elt : Tile = template.construct_element({"text_props" : new_props})
        text_props = new_elt.element_properties["text"]
        assert text_props["font_color"] == default_font_color
        assert text_props["font_size"] == new_props["font_size"]

        new_props = {"font_size": 50, "font_color": "green"}
        new_elt : Tile = template.construct_element({"text_props" : new_props})
        text_props = new_elt.element_properties["text"]
        assert text_props["font_color"] == new_props["font_color"]
        assert text_props["font_size"] == new_props["font_size"]

    def test_complex_mapping_variable(self):
        "Test if map extenders nested between maps will update values as expected"

        template_name = "invalid_type_template_1"
        default_text = "Hello World!"
        default_icon = "mdi:earth"

        default_font_color = "maroon"
        default_font_size = 10

        template_str = f"""
        {template_name}:
            defaults:
                elt_text: {default_text}
                elt_icon: {default_icon}
            element:
                type: Tile
                text: !tmp_var elt_text
                icon: !tmp_var elt_icon
                element_properties:
                    text:
                        font_size : {default_font_size}
                        !tmp_extend : text_props
                        font_color: {default_font_color}
        """

        template = self._load_template(template_str)
        
        default_elt : Tile = template.construct_element()
        text_props = default_elt.element_properties["text"]
        assert text_props["font_color"] == default_font_color
        assert text_props["font_size"] == default_font_size

        new_props = {"font_size": 50}
        new_elt : Tile = template.construct_element({"text_props" : new_props})
        text_props = new_elt.element_properties["text"]
        assert text_props["font_color"] == default_font_color
        assert text_props["font_size"] == new_props["font_size"]

        new_props = {"font_size": 50, "font_color": "green"}
        new_elt : Tile = template.construct_element({"text_props" : new_props})
        text_props = new_elt.element_properties["text"]
        assert text_props["font_color"] == default_font_color
        assert text_props["font_size"] == new_props["font_size"]

    def test_simple_sequence_variable(self):
        
        template_name = "simple_list_test_1"
        default_text = "Hello World!"
        default_icon = "mdi:earth"

        default_col_size = "r"

        template_str = f"""
        {template_name}:
            defaults:
                elt_text: {default_text}
                elt_icon: {default_icon}
            element:
                type: GridLayout
                column_sizes:
                    - {default_col_size}
                    - !tmp_extend col_sizes
                elements:
                  - type: Tile
                    text: !tmp_var elt_text
                    icon: !tmp_var elt_icon
        """

        template = self._load_template(template_str)
        
        default_elt : GridLayout = template.construct_element()
        assert default_elt.column_sizes == [default_col_size]

        new_sizes = ["?", "r"]
        new_elt : GridLayout = template.construct_element({"col_sizes" : new_sizes})
        assert new_elt.column_sizes == [default_col_size, *new_sizes]

    def test_complex_sequence_variable(self):
        "Test if list extenders also allow for appending set values to the end of the list"

        template_name = "complex_list_test_1"
        default_text = "Hello World!"
        default_icon = "mdi:earth"

        size_1 = "r"
        size_2 = 10

        template_str = f"""
        {template_name}:
            defaults:
                elt_text: {default_text}
                elt_icon: {default_icon}
            element:
                type: GridLayout
                column_sizes:
                    - {size_1}
                    - !tmp_extend col_sizes
                    - {size_2}
                elements:
                  - type: Tile
                    text: !tmp_var elt_text
                    icon: !tmp_var elt_icon
        """

        template = self._load_template(template_str)

        default_elt : GridLayout = template.construct_element()
        assert default_elt.column_sizes == [size_1, size_2]

        new_sizes = ["?", "r"]
        new_elt : GridLayout = template.construct_element({"col_sizes" : new_sizes})
        assert new_elt.column_sizes == [size_1, *new_sizes, size_2]