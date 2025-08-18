
import itertools
import logging

import pytest

import inkBoard
from inkBoard.packaging.version import Version, VERSION_COMPARITORS
from inkBoard.packaging import version

_LOGGER = logging.getLogger(__name__)

class TestVersions:

    @staticmethod
    def test_version_parse():
        #Test if the output class of parse_version is ok
        v = "1.0.0"
        v = version.parse_version(v)
        assert not isinstance(v, Version), "parse_version did returned an instance of the version class"
        assert issubclass(Version, v.__class__), "The version class should be a subclass of the return type of parse_version"

    @staticmethod
    def test_version_class():
        #Test if the non TYPE_CHCKING version class is fenced off as expected

        v = "1.0.0"
        assert version.parse_version(v) == Version(v), "Version instantiating should simply return parse_version"
        with pytest.raises(NotImplementedError):
            Version.__init__(v)
        return
    
    @staticmethod
    def test_comparitor_splitter():
        #Check if the get_comparitor_string function works

        fmt = "1.0.0{comp}1.0.0"

        errs = {}
        for c in VERSION_COMPARITORS:
            s = fmt.format(comp=c)
            cget = version.get_comparitor_string(s)
            if cget != c:
                errs[s] = cget
        
        if errs:
            msg = f"Comparitor function returned bad values for comparisons {errs}"
            raise ValueError(msg)
    
    def test_split_version_string(self):
        #Tests for the split_comparison_string function

        s = "1.0.0 >= 1.2.1"
        vals = version.split_comparison_string(s)
        assert vals[0] == "1.0.0" and vals[1] == ">=" and vals[2] == "1.2.1"

        s = "inkboard >    2.0.5      "
        vals = version.split_comparison_string(s)
        assert vals[0] == "inkboard" and vals[1] == ">" and vals[2] == "2.0.5"
        #Also test this when the left hand is a name

        s = "  ==    3.5.1b1      "
        vals = version.split_comparison_string(s)
        assert vals[0] is None and vals[1] == "==" and vals[2] == "3.5.1b1"

        with pytest.raises(ValueError):
            s = "2025.8.1"
            version.split_comparison_string(s)

    @staticmethod
    def test_compare_version():
        #Test the compare_versions function
        #Tests for all comparisons both at least 1 true and 1 false case
        #Also tests the default argument for the comparitor (which is None), which is parsed to ">="

        errs = {}
        comps = {
            ">=": [("1.2.3", "1.5.7", False), ("2025.5", "2021.10.5", True), ("10.8.2b1", "10.8.2b1", True)],
            "<=": [("1.2.3", "1.5.7", True), ("15.2.8", "10.8.2b1", False), ("10.8.2b1", "10.8.2b1", True)],
            "==":[("2025.5.1", "2023.1.2", False), ("12.0.1", "12.0.1", True)],
            "!=": [("2025.5.1", "2023.1.2", True), ("12.0.1", "12.0.1", False)],
            ">": [("0.5.0b1", "0.5.0", False), ("0.5.1b1", "0.5.0", True)],
            "<": [("2024.12.1", "2024.10.8", False), ("5.1.2", "6.3.4a1", True)],
            None: [("2025.5.8","2025.5.8", True), ("52.9", "60.7.8", False)]    #Also test the default option
        }
        assert set(comps.keys()) == set([*VERSION_COMPARITORS, None]), "Not using all comparitors!"
        for c, tests in comps.items():
            # results = [version.compare_versions(v[0], v[1], c) for v in tests]
            badtests = list(itertools.filterfalse(lambda v: version.compare_versions(v[0], v[1], c) == v[2], tests))
            # s = fmt.format(comp=c)
            # cget = version.get_comparitor_string(c)
            if badtests:
                errs[c] = [f"For {v[0]} {c} {v[1]} expected {v[2]}, got {version.compare_versions(v[0], v[1], c)}" for v in badtests]
        
        if errs:
            full_msg = ""
            for k, msgs in errs.items():
                msgs_str = "\n    ".join(msgs)
                full_msg = full_msg + f"Comparitor {k}:\n    {msgs_str}\n\n"
            _LOGGER.error(full_msg)
            raise ValueError(f"Compare versions failed for {list(errs.keys())}")
        
    @staticmethod
    def test_bad_compare_version():
        comp = "~~"
        vleft = "20.6.5"
        vright = "25.4.6"
        with pytest.raises(ValueError):
            version.compare_versions(vleft, vright, comp)
        return
    
    @staticmethod
    def test_string_compare_version_basics():

        #Test here:
        #The base function, for both a Version object and a string?
        #Test if it also works when passing it inkBoard (i.e., it should get the __version__ attribute)
        #And test if that also raises an attribute error
        s = "2024.6.1 >= 2023.4.5"
        assert version.string_compare_version(s), "Raw string comparison did not return expected result"

        s = "1.2.5 != 1.2.5"
        assert not version.string_compare_version(s), "Raw string comparison did not return expected result"
        return
    
    @staticmethod
    def test_string_compare_version_complex():

        s = "test >= 1.5.3"
        assert version.string_compare_version(s, test = "1.5.4"), "Error in string comparison when substituting variable for string"

        s = "test < 2025.4.3"
        assert version.string_compare_version(s, test = version.parse_version("1.5.4")), "Error in string comparison when substituting variable for Version object"

        s = "inkBoard > 0.1.0"
        assert version.string_compare_version(s, inkBoard = inkBoard), "Error in string comparison when substituting variable for object with __version__ attribute"

    @staticmethod
    def test_string_compare_version_bad():
        
        with pytest.raises(ValueError):
            s = "test !! 1.5.3"
            version.string_compare_version(s, test = "2.5.4")
        
        with pytest.raises(AttributeError):
            obj = object()
            s = "test > 1.5.3"
            version.string_compare_version(s, test = obj)