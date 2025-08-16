
from typing import *
import tkinter as tk
import random as rnd

import ttkbootstrap as ttk

from inkBoard import CORE as CORE

from inkBoarddesigner.tkinter import window, functions as tk_functions
from inkBoarddesigner.tkinter.widgets import Treeview

from . import _LOGGER, setup as super_setup

if TYPE_CHECKING:
    from PythonScreenStackManager.pssm import PSSMScreen
    from inkBoard import config
    from dummy import DummyClient

##The designer has hooks to register treeviews, which can be useful to convey information to the user.
##For the general usage, look at how to configure trees in tkinter and ttk
dummytree= ttk.Treeview(columns=("Dummy"),
                                    name="my-tree")

##To provide some default functions and shorthands, the designer comes with a wrapper Treeview class. (It could not be a direct treeview subclass since that caused issuess with the widget)
##The treeview sets up the base bindings and styling for designer treeviews, and has functions that are more representative of pssm.
dummytree = Treeview(dummytree)
dummytree.heading("#0", text="Dummy", anchor="w")

##To add mdi icons in the correct styling and sizing, simply call this function. It returns a PhotoImage which can be used in treeview items as the image argument.
dummy_icon = tk_functions.build_tree_icon("mdi:space-invaders")

def setup(screen : "PSSMScreen", config : "config"):
    print("setting up a dummy")
    dummy: DummyClient = super_setup(screen, config)
    dummy.run_callback = dummy_callback

    ##We register the tree with the treeview frame. This register will be emptied upon reloading the config.
    window.treeFrame.register_tree("Dummy Tree", dummytree)
    return dummy


def dummy_callback(dummy, num):

    ##This function is called from the dummy, and is (most likely) not called in the main thread of the designer window.
    ##the designer uses tkthread to provide thread safety, so interacting with the window and other widgets should be fine without having to worry about threading.

    _LOGGER.info(f"In dummy run {num}")

    ##Each time the callback is called, it adds a new item to the treeview, and determines a random number of elements to add as children (subitems) to that item.
    all_elts = tuple(CORE.screen.elementRegister.values())
    
    if num > 1:
        loop_range = rnd.randint(1,num)
    else:
        loop_range = num


    parent_iid = dummytree.insert(
        parent="",
        index=tk.END,
        iid = str(num),
        text=f"Dummy run {num}",
        values=loop_range,
        image=dummy_icon,
        open=True
    )

    ##Pick a random element from the register to add as a subitem
    ##Since the dummytree is wrapped into a designer Treeview, the base function upon selecting an item in the treeview is the highlight function
    ##This means that if a user selects an item in the treeview, if said item is linked to an element on screen, said element is highlighted (if the highlight setting is on)
    for _ in range(loop_range):
        elt_num = rnd.randint(0, len(all_elts)-1)
        rand_elt = all_elts[elt_num]

        dummytree.insert_element_item(
            rand_elt, f"Random element {rand_elt}", parent_iid=parent_iid
        )