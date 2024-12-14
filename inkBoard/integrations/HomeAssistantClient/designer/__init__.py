import asyncio
from typing import *
import tkinter as tk

import ttkbootstrap as ttk

from inkBoard import core as CORE

from inkBoarddesigner.tkinter import window, functions as tk_functions
from inkBoarddesigner.tkinter.widgets import Treeview
from inkBoarddesigner import const as des_const

from .const import ENTITY_ICONS
from .. import async_setup as super_setup, async_start as super_start, logger as _LOGGER

if TYPE_CHECKING:
    from inkBoard import config
    from PythonScreenStackManager import PSSMScreen
    from .. import client

entity_tree= ttk.Treeview(columns=("entity"),
                                    name="entity-tree")

entity_tree = Treeview(entity_tree)
entity_tree.heading("#0", text="Entity", anchor="w")
entity_tree.heading("#1", text="State", anchor="w")

entity_tree.column("#0", minwidth=100, width=int(des_const.INTERFACE_WIDTH*0.6))
entity_tree.column("#1", minwidth=50, width=int(des_const.INTERFACE_WIDTH*0.4))

def get_client() -> "client.HAclient":
    return CORE.integration_objects[__package__.split(".")[-2]]


async def async_setup(core: "CORE", config : "config"):

    window.treeFrame.register_tree("Entities",entity_tree)
    return await super_setup(core, config)

async def async_start(core: "CORE", client : "client.HAclient"):
    client._subcribe_callbacks.append(_new_subscription)
    await super_start(core.screen, client)
    build_entity_tree(client)

    for entity in client.stateDict:    
        client.add_entity_function(
            entity, ((update_tree_row, False),)
        )
    # client._subcribe_callbacks.append(_new_subscription)
    return


def build_entity_tree(client:  "client.HAclient"):

    # elts = client.elementDict
    # states = client.stateDict

    # treeview = entity_tree
    # open_init = True


    for id in client.stateDict:
        add_entity_to_tree(client, id)
    return


def select_tree(tree, event, iids):

    client: "client.HAclient" = CORE.integration_objects[__package__.split(".")[-2]]

    iid = iids[0]

    if iid in client.elementDict:
        elts = client.elementDict[iid]
        tk_functions.highlight_elements(*elts)
        return

    entity_tree.highlight_element(tree,event,iids)

def _new_subscription(client: "client.HAclient", header: dict):
        
    entity = header["trigger"].get("entity_id", None)
    if not entity: return

    add_entity_to_tree(client, entity)
    return


def add_entity_to_tree(client: "client.HAclient", entity: str):
    id = entity
    state = client.stateDict.get(id, None)
    
    if not (entity or state): 
        return

    open_init = False

    if not entity_tree.exists(id):
        if id in client.elementDict:
            idx = 0
        else:
            idx = tk.END

        dom = id.split(".")[0]
        icon_mdi = ENTITY_ICONS.get(dom,ENTITY_ICONS["default"])
        icon = tk_functions.get_tree_icon(icon_mdi)
        name = state["attributes"].get("friendly_name", id)
        entity_tree.insert(
            "",
            idx,
            iid = id,
            text=name,
            values=(state["state"]),
            image=icon,
            open=open_init
        )
    else:
        if id in client.elementDict:
            if not entity_tree.get_children(id):
                entity_tree.move(id,"",0)

    for elt in client.elementDict.get(id,{}):
        for child in entity_tree.get_children(id):
            if elt.id in child:
                break
        
        if [x for x in entity_tree.get_children(id) if elt.id in x]:
            _LOGGER.debug(f"Duplicate element to be added {elt.id}")
            break
        

        elttype = str(elt.__class__.__name__)
        entity_tree.insert_element_item(
            elt, elttype, id
            )   
    return

def update_tree_row(trigger_dict, state_dict):
    iid = trigger_dict["entity_id"]
    state = trigger_dict["to_state"]["state"]
    entity_tree.item(iid, values=(state))
    return

def show_entity_tip(tree: Treeview, event, _iid):

    client = get_client()
    state = client.stateDict.get(_iid, None)

    if not state: 
        tree.tooltip.hide_tip()
        return

    tipText = (f"entity id: {state['entity_id']}\n"
            f"state: {state['state']}")
    if "attributes" in state:
        tipText = tipText + "\nattributes:"
        attributes = state['attributes']
        for attr,val in sorted(attributes.items()):
            tipText = tipText + "\n" + "   " + f"{attr}: {val}"
    tree.tooltip.text = tipText
    tree.tooltip.show_tip()
    return

entity_tree.on_select = select_tree
entity_tree.on_hover = show_entity_tip