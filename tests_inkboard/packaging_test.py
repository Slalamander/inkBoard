
import pytest

from inkBoard.packaging.version import Version, VERSION_COMPARITORS
from inkBoard.packaging import version

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