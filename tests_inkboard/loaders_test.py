
import pytest

from inkBoard.loaders import IntegrationLoader

class TestIntegrationLoader:

    def test_duplicate_integrations(self):

        #See if somewhere else the dummy_integration is installed by default
        #And ensure the custom one is used
        #Not the case for the dummy integration at least; how to then?
        #Maybe just overwrite api or whatever, maybe dns
        #Testing of integrations should happen in the designer repo anyways
        return