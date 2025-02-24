"A dummy device that can be used for i.e. testing"

from .basedevice import BaseDevice, InkboardDeviceFeatures
from inkBoard.types import ColorType

class DummyDevice(BaseDevice):

    def __init__(self, features = [], width : int = 1000, height : int = 1000, mode : str = "RGBA", color : ColorType = None, 
                print_screen : bool = True,
                **kwargs):
        features = InkboardDeviceFeatures(*features)
        super().__init__(features=features, screenWidth=width, screenHeight=height,
                        viewWidth=width, viewHeight=height,
                        screenMode=mode, imgMode=mode,
                        defaultColor=color,
                        model="Dummy Device", name="Dummy")
        self.print_screen = print_screen
    
    def print_pil(self, imgData, x, y, isInverted=False):
        if self.print_screen:
            return imgData
        return imgData
        
    def event_bindings(self, touch_queue = None):
        return