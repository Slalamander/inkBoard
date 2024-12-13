#!/usr/bin/env pythonall_entities

import asyncio
import json
from datetime import datetime
import logging
from typing import Union, Callable, TYPE_CHECKING, TypedDict, Optional, Literal, TypeVar, Any, Coroutine, Sequence
from types import MappingProxyType

import websockets
from websockets import protocol as ws_protocol
from websockets.asyncio import client as ws_client

from PythonScreenStackManager.pssm import screen

import inkBoard
from inkBoard.constants import FuncExceptions
from inkBoard.platforms import FEATURES

from PythonScreenStackManager import tools, elements
from PythonScreenStackManager.tools import DummyTask

from inkBoard import core as CORE

from .helpers import triggerDictType, stateDictType, actionCallDict, EntityType
from .constants import all_entities, all_service_actions, entity_tags, ENTITY_TAG_KEY, parse_entity_tag, \
                        DEFAULT_PING_INTERVAL, MAX_PONGS_MISSED, DEFAULT_HA_DT_FORMAT



from .HAelements import HAelement
from .clientelements import ClientElement

if TYPE_CHECKING:
    from PythonScreenStackManager.devices import PSSMdevice as pssm_device
    from PythonScreenStackManager import elements, tools #import pssm as screenFile, elements as pssm
    from PythonScreenStackManager.tools import DummyTask

logger = logging.getLogger(__name__)
logger.debug(f"{logger.name} has loglevel {logging.getLevelName(logger.getEffectiveLevel())}")

class ServerConfigDict(TypedDict):
    "The entries saved from the servers config response"

    name : str
    "The name of the instance"
    
    time_zone : str
    "The server's time zone"

    version : str
    "The version of Home Assistant that the server is running"

    integration : bool
    "Boolean value indicating if the inkBoard integration is running on the server"

    unit_system : dict
    "The default units this server uses"

#Builds the headers to send to subscribe to triggers
def trigger_headers(entities : Union[list,tuple],last_id : int):
    """
    Builds a list of headers to send to a client to subscribe to state changes of the entities in entities
        Parameters:
            entities: iterable with strings containing the entity_id's to subscribe to
            last_id: the last message id send to the websocket API
    """
    headers = []
    entity_list = []
    if type(entities) is str:
        #Simple rewite to keep the code below functioning in case of inputting a single entity
        entities = [entities]

    for index, entity in enumerate(entities):
        subscribe_header = {
            "id": last_id + index+1,
            "type": "subscribe_trigger",
            "trigger": {
                "platform": "state",
                "entity_id": entity #entity["entity_id"]
            }, }
        headers.append(subscribe_header)
        entity_list.append((entity))
    return headers

class HAclient:
    '''
    Client class that manages the connection with Home Assistant. Subscribes to triggers and updates elements.
        screen: instance of PSSMScreen that handles the printing of layouts and elements etc
    '''
    
    def __init__(self, screen: screen.PSSMScreen, ping_interval:int = DEFAULT_PING_INTERVAL):

        self._websocket: ws_client.ClientConnection
        self._pssmScreen = screen
        self.pssmScreen.client = self

        self._subcribe_callbacks = [] 
        #Callbacks to call when subscribing to a new entity. None async functions only -> eh no make tasks of them and then continue.

        screen.add_shorthand_function("service-action",self.call_service_action)
        screen.add_register_callback(self.register_new_element)
        
        self.hass_data = CORE.config.configuration["home_assistant"]
        self.__last_id = 0
        self.loglist = []
        self._HAconfig = ServerConfigDict(name=None, time_zone=None, version=None, integration=False, unit_system={})
        self._elementDict : dict[str,set[EntityType]] = {}
        self._functionDict : dict[str,list] = {}
        self._stateDict : dict = {}
        self.updatingAll : bool = False

        self.__websocketCondition = asyncio.Condition()

        self.ping_interval = ping_interval
        self.listenerTask : asyncio.Task = DummyTask()
        self.commanderTask : asyncio.Task = DummyTask()
        self.pingpongTask : asyncio.Task = DummyTask()
        self.longrunningTasks: asyncio.Task = DummyTask()
        self.reconnect_task : asyncio.Task = DummyTask()

        self._callback_queues : dict["id", asyncio.Queue]= {} ##Dict with keys corresponding to message id's, values being asyncio events
        self.__message_queue = asyncio.Queue()
        self._commanderLock = asyncio.Lock()
        self._listenerLock = asyncio.Lock()

    #region client properties
    @property
    def websocket(self) -> ws_client.ClientConnection:
        "The websocket client object managing the connection."
        if hasattr(self,"_websocket"):
            return self._websocket
        else:
            return None
    
    @property
    def HAconfig(self) -> dict:
        "The configuration from the Home Assistant server (only keys needed for inkboard)"
        return self._HAconfig
    
    @property
    def next_id(self) -> int:
        "Returns the next message id and increments last_id"
        self.__last_id += 1
        return self.__last_id

    @property
    def connection(self) -> bool:
        "True if the client websocket is open."
        if self.websocket == None:
            return False
        else:
            return self.websocket.state is ws_protocol.State.OPEN
    
    @property
    def clientState(self) -> Literal["disconnected", "connecting", "connected"]:
        "Returns the state the client is currently in"
        if self.websocket == None or self.connectionTask.done():
            return "disconnected"
        else:
            # if self.connectionTask.done() and self.reconnect_task.done():
            if self.connection:
                return "connected"
            else:
                return "connecting"

    @property
    def websocketCondition(self) -> asyncio.Condition:
        "Condition that is notified when something happends to the websocket connection, generally in case of loss of connect, or start of a reconnect."
        return self.__websocketCondition

    @property
    def pssmScreen(self) -> screen.PSSMScreen:
        "The PSSM screen object the client is managing"
        return self._pssmScreen

    @property
    def device(self) -> "pssm_device":
        "The device object connected to the PSSM screen object"
        return self._pssmScreen.device
    
    @property
    def elementDict(self) -> dict[EntityType, HAelement]:
        "Dict that links entities to pssm elements that need to be updated with the entity"
        return MappingProxyType(self._elementDict)
    
    @property
    def functionDict(self) -> MappingProxyType[EntityType, Callable[[triggerDictType,"HAclient"],Any]]:
        "Dict that links entity id's to functions that have to be called when its state update"
        return MappingProxyType(self._functionDict)
    
    @property
    def stateDict(self)-> MappingProxyType[EntityType, stateDictType]:
        "dict with the current states of all subscribed to entities"
        return MappingProxyType(self._stateDict)
    
    @property
    def messageQueue(self) -> asyncio.Queue:
        "Queue with messages to send to the server"
        return self.__message_queue
    
    @property
    def commanding(self) -> bool:
        "True if the client is currently able to send commands to the Home Assistant Server (e.g. call service actions etc.)."
        return self._commanderLock.locked()
    
    @property
    def listening(self) -> bool:
        "True if the client is currently listening to the Home Assistant Server"
        return self._listenerLock.locked()
    
    @property
    def server_config(self) -> ServerConfigDict:
        "The important parts of the configuration of the Home Assistant server"
        return MappingProxyType(self._HAconfig)

    async def await_commander(self) -> None:
        """
        This can be used to await for the client to start accepting commands, i.e. know when it's possible to call services or call other stuff on the websocket.
        """
        async with self._commanderLock:
            await asyncio.sleep(0)
    #endregion

    #region [websocket stuff]
    def reconnect_client(self, initWait=5, *args, **kwargs):
        """Starts the task to reconnect to the client, and periodically retry doing so."""
        self.reconnect_task = self.loop.create_task(self.__async__reconnect(initWait))
    
    async def connect_client(self):
        """Starts the function that connects to Home Assistant""" 
        self.loop = asyncio.get_event_loop()
        self.connectionTask = asyncio.create_task(self.__async__connect())
        async with self.websocketCondition:
            await self.websocketCondition.wait()
        
        return

    async def disconnect_client(self):
        "Disconnects from the Home Assistant client."
        await self.websocket.close()
        async with self.websocketCondition:
            self.websocketCondition.notify_all()

    async def start_client(self):
        """Starts the infinite loops to manage the Home Assistant connection (listener, commander and ping-pong)"""
        raise NotImplementedError("Don't call me anymore")
        if not self.connection:
            logger.warning("Not connected to client, cannot start.")
            return
        
        # if self.listenerTask.done():
        #         self.listenerTask = self.loop.create_task(self.__async_listen())
        # if self.commanderTask.done():
        #         self.commanderTask = self.loop.create_task(self.__async_command())
        # if self.pingpongTask.done():
        #         self.pingpongTask = self.loop.create_task(self.__async_ping_pong())
        

        
        async with self.websocketCondition:
            self.websocketCondition.notify_all()

    async def __async__connect(self):
        """Sets up a websocket connection to Home Assistant"""

        ##A rewrite of this could work by using a context manager to connect, and notify the condition when it is connected (which would then return the integration start function)
        ##And then use a gather call for the listener and commander
        ##Pros of this is that the context manager can automatically reconnect, and closes the connection when it exits too.
        ##Only thing that's kinda iffy: how would it signal when it is reconnecting?
        if not self.device.has_feature(FEATURES.FEATURE_NETWORK):
            logger.error("A device needs to have a network to use the Home Assistant integration")
            return

        uri = f"ws://{self.hass_data['url']}/api/websocket"
        token = self.hass_data["token"]
        auth_header =    {
            "type": "auth",
            "access_token": token     }
        logger.debug("Attempting connection to {}".format(uri))        

        async for websocket in ws_client.connect(uri, additional_headers=auth_header):
            logger.debug("Setting up websocket connection to Home Assistant")  
            try:                
                self._websocket = websocket
                await self.websocket.recv() #The first message send by the server requests authentication. Needs to be received to start it.
                await self.websocket.send(json.dumps(auth_header))
                auth_res = json.loads(await self.websocket.recv())
                if auth_res["type"] == "auth_ok":
                    self.authenthicated = True
                    logger.info(f"Connected to Home Assistant {auth_res}")
                else:
                    logger.error(f"Authentication failed {auth_res}")
                    return
                
                HAconf_header = {"id": self.next_id, "type": "get_config" }
                await self.websocket.send(json.dumps(HAconf_header))
                HAconf_res = json.loads(await self.websocket.recv())
                if HAconf_res["success"]:
                    HAconf_res = HAconf_res["result"]
                    self._HAconfig = {
                                    "name": HAconf_res["location_name"],
                                    "time_zone": HAconf_res["time_zone"],
                                    "version": HAconf_res["version"],
                                    "integration": "inkboard" in HAconf_res["components"], 
                                    "unit_system": HAconf_res["unit_system"]
                                    }

                states_header = {"id": self.next_id, "type": "get_states" } 
                await self.websocket.send(json.dumps(states_header))
                all_states = json.loads(await self.websocket.recv())
                if not all_states.get("success",False):
                    logger.error(f"Failed to get states, Home Assistant returned response: {all_states}")
                    continue
                else:
                    logger.debug("Received all states from Home Assistant")
                    initial_states = list(filter(lambda entity: entity["entity_id"] in all_entities, all_states["result"])) 
                    initial_dict = {}
                    for entity in initial_states:
                        initial_dict[entity["entity_id"]] = entity
                    self._stateDict = initial_dict
                    
                    timeout = CORE.config.inkBoard.integration_start_time
                    if isinstance(timeout, str):
                        timeout = tools.parse_duration_string(timeout)
                    if timeout < 0:
                        timeout = 5
                    
                    logger.debug("Updating all elements after connecting")
                    coro_list = []
                    coro_list.append(self.client_update_elements(update_all=True, timeout=timeout))
                    called_functions = [self.client_update_elements]
                    
                    logger.debug(f"Updating functions in function dict") #{self.functionDict}")
                    for func_entity in self.functionDict:
                        trigger_dict = triggerDictType(entity_id=func_entity, to_state=self.stateDict[func_entity], from_state=None, context=None)
                        for func_tuple in self.functionDict[func_entity]:
                            (func, call_func) = func_tuple
                            if func not in called_functions and call_func:
                                try:
                                    if asyncio.iscoroutine(func):
                                        coro_list.append(func(trigger_dict, self))
                                    else:
                                        coro_list.append(asyncio.to_thread(
                                            func, trigger_dict, self))
                                    called_functions.append(func)
                                except (TypeError, KeyError, IndexError, OSError) as exce:
                                    logger.warning(f"Error calling function {func} for entity {func_entity}: {exce}, removed from function dict")
                                    self._functionDict[func_entity].remove(func_tuple)
                    if coro_list:
                        done, pending = await asyncio.wait(coro_list,timeout=timeout)

                        for task in pending:
                            task : asyncio.Task
                            coro = task.get_coro()
                            logger.warning(f"{coro.__qualname__} is taking longer than the specified {timeout} while connecting, continuing in background and progressing connect script.")
                        
                        for task in done:
                            task : asyncio.Task
                            if task.exception() != None:
                                coro = task.get_coro()
                                logger.warning(f"{coro.__qualname__} raised an error while connecting: {task.exception()}")

                subscribe_headers = trigger_headers(all_entities,self.__last_id)
                subscribe_fails = 0

                for header in subscribe_headers:
                    res = await self.subscribe_to_trigger(None,header)
                    
                    if res == header:
                        continue
                    else:
                        subscribe_fails += 1
                if subscribe_fails == 0:
                    logger.info("Succesfully subscribed to all entities")
                
                self.__last_id = header["id"]
                async with self.websocketCondition:
                    self.websocketCondition.notify_all()

                if not self.longrunningTasks.done():
                    self.longrunningTasks.cancel()

                self.listenerTask = self.loop.create_task(self.__async_listen())
                self.commanderTask = self.loop.create_task(self.__async_command())
                # self.pingpongTask = self.loop.create_task(self.__async_ping_pong())

                runners = [self.listenerTask, self.commanderTask]

                self._longrunningTasks = asyncio.gather(*runners, return_exceptions=True)

                await self._longrunningTasks

                logger.debug("Listener and Commander task have returned")

            except websockets.exceptions.ConnectionClosed:
                if not self.longrunningTasks.done(): 
                    self.longrunningTasks.cancel("Client connection closed")
                logger.warning("Websocket connection has closed")
                continue
            except ConnectionRefusedError as exce:
                if not self.longrunningTasks.done(): self.longrunningTasks.cancel("Client connection closed")
                logger.error("Hme Assistant refused connection", exc_info=True)
            except asyncio.CancelledError:
                logger.debug("Connect task has been cancelled")
                if not self.longrunningTasks.done(): 
                    self.longrunningTasks.cancel("Client connection closed")
                return
            except Exception as e:
                logger.error(f"Something went wrong in the client: {e}")
                raise
        return

    async def __async__reconnect(self, init_Wait: float = 15, max_Attempts=0, wait_Increase: int =2, wait_Max: float = 300):
        """
        Reconnect function
        Args:
            init_wait: initial wait time (seconds) before reconnecting
            max_attempts: maximum attempts to try reconnecting before stopping the function
            wait_increase: how much the previous wait time is multiplied with for the next time; if init_wait = 0, next wait time will be 30 seconds
            wait_max: maximum waiting time (seconds) before attempting a new reconnection
        """
        wait = init_Wait
        att = 0
        logger.info("Reconnecting to Home Assistant")

        if self.connection:
            logger.info("Home Assistant is still connected, closing connection.")
            await self.disconnect_client()

        if not self.connectionTask.done():
            self.connectionTask.cancel("Attempting reconnect script")

        async with self.websocketCondition:
            self.websocketCondition.notify_all()

        while not self.connection:
            logger.debug("Trying to get IP")
            ip = await self.device.network.get_ip_async()
            if ip == None:
                logger.info("Got no IP adress, Trying to get SSID")
                ssid = await self.device.network.get_SSID_async()
                if ssid == "Wifi off":
                    logger.info("Wifi is still off. calling wifi up")
                    await self.device.network.wifi_up_async()
                else:
                    logger.info(f"Got network {ssid}")

                ip = await self.device.network.get_ip_async()
                if ip == None:
                    logger.error("Still got no IP adress, stopping reconnect")
                    return
            else:
                logger.debug(f"Got IP adress {ip}")

            await asyncio.sleep(wait)

            logger.info("Attempting reconnect")
            await self.connect_client()

            if not self.connection:
                if init_Wait == 0: init_Wait=30/2 #Otherwise it would stay at 30
                wait = init_Wait*(wait_Increase**(att + 1)) if init_Wait*(wait_Increase**(att + 1)) < 300 else 300
                att += 1
                logger.warning("Failed to reconnect, trying again in {} seconds".format(wait))

            if max_Attempts > 0 and att >= max_Attempts:
                logger.warning(f"Failed to reconnect within maximum attempts set: {max_Attempts}, stopping reconnect.")
                break

        async with self.websocketCondition:
            self.websocketCondition.notify_all()

        if self.connection:
            logger.info("Reconnected to Home Assistant")
        else:
            logger.warning("Failed to reconnect to Home Assistant")

    async def __async_listen(self):
        '''
        Listens to messages from the Home Assistant server
        '''
        logger.debug("Starting Listener")
        async with self._listenerLock:
            try:
                async for message in self.websocket: #@IgnoreException
                    message = json.loads(message)
                    id = message["id"]
                    logger.debug(f"Received message {id}")
                    logger.trace(message)
                    if id in self._callback_queues:
                        queue = self._callback_queues[id]
                        logger.debug(f"Putting response from message id {id} in queue")
                        try:
                            queue.put_nowait(message)
                        except asyncio.QueueFull:
                            logger.error(f"Message id {id} has already queued a response")
                    
                    if message.get("type") == "event":
                        try:
                            asyncio.create_task(self.update_states(message))
                        except (TypeError, KeyError, IndexError, OSError) as exce:
                            logger.error(f"Error in update states for {message}: {exce}")
                    elif message.get("type") == "result":
                        if not message.get("success", False):
                            err = message.get("error",{})
                            logger.warning(f"Unsuccesful request {err.get('code','unknown code')}: {err.get('message','No message')}")
            except websockets.exceptions.ConnectionClosedError as exce:
                logger.error(f"Listener stopped due to connection closing")
                logger.debug(exce)
            except asyncio.CancelledError:
                pass
                        
        logger.warning("Listener stopped")
        if not self.commanderTask.done():
            self.commanderTask.cancel()
        async with self.websocketCondition:
            self.websocketCondition.notify_all()

    async def __async_command(self):
        '''
        Sends messages put into HAclient.messageQueue to the Home Assistant server
        '''
        logger.info("Starting Commander")
        async with self._commanderLock:
            if not self.messageQueue.empty():
                await self._empty_message_queue()

            while self.connection:
                try:
                    logger.trace(f"Waiting for message from commander queue")
                    cmd = await self.messageQueue.get()

                    if "id" not in cmd:
                        cmd["id"] = self.next_id
                    else:
                        msg_id = cmd["id"]
                        if msg_id < self.__last_id:
                            logger.debug(f"{msg_id} was already used for a websocket message. Increasing id of command {cmd}")
                            # self.last_id += 1
                            new_id = self.next_id
                            cmd["id"] = new_id
                            if msg_id in self._callback_queues:
                                # queue = self._callback_queues.pop(msg_id)
                                logger.debug(f"Message {msg_id} has a callback. Removing object from key {msg_id} and putting it in {new_id}.")
                                self._callback_queues[new_id] = self._callback_queues.pop(msg_id)

                    send = await asyncio.wait_for(self.websocket.send(json.dumps(cmd)), timeout=10) #@IgnoreException
                    logger.debug(f"Command send")
                    logger.trace(cmd)
                except TimeoutError:
                    if cmd["type"] == "call_service":
                        logger.warning(f"Calling service action {cmd['domain']}.{cmd['service']} timed out")
                    else:
                        logger.warning(f"Sending message {cmd['type']} timed out")
                except (TypeError, KeyError, IndexError, OSError) as exce:
                    logger.error(f"Exception occured in commander while sending command {cmd}: {exce}")
                except websockets.exceptions.ConnectionClosedError as exce:
                    logger.error(f"Commander stopped due to connection closing")
                    logger.debug(exce)
                    break
                except (asyncio.CancelledError, asyncio.exceptions.CancelledError):
                    break

        logger.error("Commander stopped")

    async def __async_ping_pong(self):
        '''
        Sends pings and receives the pongs from the Home Assistant Server
        '''
        logger.info("Starting ping-pong script")
        #await asyncio.sleep(3)
        pong_timeout = 10
        pongs_missed = 0
        missed_max = MAX_PONGS_MISSED
        while self.connection:
        #for i in range(10):  
            await asyncio.sleep(self.ping_interval)  
            # self.last_id += 1
            ping_id = self.next_id
            ping_dict = {"id": ping_id, "type": "ping"}
            # queue = asyncio.Queue(1)
            # self._callback_queues[ping_id] = queue
            pong_task = self.add_callback(ping_id)

            logger.debug(f"Sending Ping id {ping_id}")
            try:
                #await asyncio.wait_for(self.websocket.send(json.dumps(ping_dict)), timeout=pong_timeout)
                await self.messageQueue.put(ping_dict)
                # res = await asyncio.wait_for(queue.get(), timeout=pong_timeout) #@IgnoreException
                res = await asyncio.wait_for(pong_task, timeout=pong_timeout) #@IgnoreException
                ping_id = res["id"] ##Update the ping_id in case the commander increased it
                pongs_missed = 0
            except asyncio.exceptions.TimeoutError:
                pongs_missed += 1
                logger.error(f"Did not receive pong back from Home Assistant within {pong_timeout} seconds, missed {pongs_missed} pongs in a row")
                if pongs_missed >= missed_max: 
                    self.__connection = False
                    break
            except websockets.exceptions.ConnectionClosedError as exce:
                logger.error(f"Ping Pong errored due to connection closing: {exce}")
                self.__connection = False
                break

            logger.debug(f"Received pong from ping id {ping_id}")

        logger.warning("Ping pong function has stopped, Closing websocket to start reconnect")
        await self.websocket.close()
        async with self.websocketCondition:
            self.websocketCondition.notify_all()
        self.reconnect_client()

    async def _empty_message_queue(self):
        """
        Empties the queue with messages to be send to the commander, to prevent any service-actions from being performed on reconnect
        """
        while not self.messageQueue.empty():
            await self.messageQueue.get()
            self.messageQueue.task_done()

    async def _new_entities_subscribe(self, *entities):

        for ent in entities:
            if ent not in all_entities:
                ##all_entities should not have to perform a check for this.
                all_entities[ent] = {'entity_id': ent}

        if not self.stateDict or not self.commanding:
            return

        logger.debug(f"Subscribing to new entities {entities}.")

        states_msg = {
        "id": self.next_id,
        "type": "get_states"
        }

        result = await self._async_get_message_result(states_msg)
        states = result["result"]

        for ent_state in filter(lambda ent_state: ent_state["entity_id"] in entities, states):
            self._stateDict[ent_state["entity_id"]] = ent_state

        for entity in filter(lambda entity: entity not in self._stateDict, entities):
            logger.error(f"entity {entity} could not be found on the Home Assistant server. Setting it's state to unknown.")
            state = stateDictType(entity_id=entity,state="unknown", attributes={}, last_changed=None, last_reported=None,last_updated=None, context=None)
            self._stateDict[entity] = state

        ##Will remove the last_id later and have it set by the commander
        for subscr in trigger_headers(entities, last_id=self.__last_id):
            await self.messageQueue.put(subscr)
        
        last_id = subscr["id"]
        if last_id > self.__last_id:
            self.__last_id = last_id
        
        logger.info(f"Succesfully subscribed to new entities {entities}.")

    def add_callback(self, message_id : int) -> asyncio.Task:
        """
        Indicates the response of the server from the message with the specified id is needed somewhere, and puts it in an asyncio queue when received.
        The queue object is discarded from the callbacks afterwards (Since message_id's cannot be reused), and the task object returns the response.

        Parameters
        ----------
        message_id : int
            The id of the message to expect the response from

        Returns
        -------
        asyncio.Task
            A task that can be awaited on, that will return the response from the server.
        """        
        if message_id in self._callback_queues:
            logger.warning(f"A message with id {message_id} already has a callback assigned. Returning that queue")
            return self._callback_queues[message_id]
        
        def remove_queue(future : asyncio.Future):
            try:
                id = future.result()["id"]
                pop_id = id
            except (asyncio.CancelledError, asyncio.exceptions.InvalidStateError):
                pop_id = message_id
            self._callback_queues.pop(pop_id, None)

        resp_queue = asyncio.Queue(1)
        self._callback_queues[message_id] = resp_queue
        task = asyncio.create_task(resp_queue.get())
        task.add_done_callback(remove_queue)
        return task
    #endregion

    def register_new_element(self, element : elements.Element):
        
        if hasattr(element,"_HAclient"):
            element._HAclient = self

        if not hasattr(element,"entity") and not isinstance(element,HAelement):
            return
        

        if not isinstance(element,HAelement):
            HAelement.wrap_element(element,self)

        if element.HAclient == None:
            element._HAclient = self

        if not hasattr(element,"entity"):
            return
        
        entity_id = element.entity

        if entity_id not in all_entities:
            logger.info(f"{entity_id} is not defined in config, adding it.")
            
            if self.websocket is not None:      
                self.messageQueue.put_nowait(trigger_headers(entity_id,self.__last_id))

            all_entities[entity_id] = {'entity_id': entity_id}

        if entity_id in self.elementDict:                       
            self._elementDict[entity_id].add(element)
        else:
            self._elementDict[entity_id] = set([element])

    def _add_element(self, *element_list, update_elements=True, layout_element=None, internalbatch=True):
        '''
        Adds an element that is called when it's asociated entity is updated
            Parameters:
                element_list: The elements that are to be watched by the client. 
                            Can be any pssm or HAelement. If a pssm layout, will add all elements individually. The entity_id linked to a layout is copied to their sub elements, unless said element has its own entity_id
                update_elements (bool): update_element after adding (not implemented)
                layout_element: For internal purposed mainly. The first layout element an element is associated with
                internalbatch: Mainly internal and not implemented
        '''
        for element in element_list:
            if hasattr(element, "entity"):
                
                if not isinstance(element, HAelement):
                    ##This should take care of parsing
                    HAelement.wrap_element(element,self)
                
                element._HAclient = self
                entity_id = element.entity
                
                if entity_id not in all_entities:
                    logger.info(f"{entity_id} is not defined in config, adding it.")
                    if self.websocket is not None:      
                        self.messageQueue.put_nowait(trigger_headers(entity_id,self.__last_id))

                    all_entities[entity_id] = {'entity_id': entity_id}

                if entity_id in self.elementDict:                       
                    self._elementDict[entity_id].add(element)
                else:
                    self._elementDict[entity_id] = set([element])

            if isinstance(element,elements.Layout):
                for subElement in element.createEltList():
                    self.add_element(subElement, layout_element=element, update_elements=False, internalbatch=internalbatch)
                    
    def update_element_entity(self, element : HAelement, new_entity : str, old_entity = None, update_now=True):
        """
        Updated the entity associated with the element to new_entity
        args:
            element: the element to change the entity off
            new_entity (str, list): entity_id (or list of) to associate with the element (lists may not be implemented yet-ish)
            update_now(bool): immediately update the element by calling its trigger_function, using the state currently in the state dict.
        """
        if not self.pssmScreen.printing and old_entity == None:
            self.register_new_element(element)
            return

        if old_entity:
            logger.debug(f"Updating {element} entity from {old_entity} to {new_entity}")
            if old_entity in self.elementDict:
                if element in self.elementDict[old_entity]:
                    logger.debug(f"Removing {element} from {old_entity}")
                    self._elementDict[old_entity].remove(element)

        if new_entity in self.elementDict:                       
            self._elementDict[new_entity].add(element)
        else:
            self._elementDict[new_entity] = set([element])
        if update_now:
            if new_entity not in self.stateDict:
                asyncio.create_task(self._new_entities_subscribe(new_entity))
            elif callable( func := getattr(element,"trigger_function",False)):
                to_state = self.stateDict.get(new_entity,{})
                ent_dict = {"entity_id": new_entity, "to_state": to_state, 'from_state': None, 'context': None}
                ent_dict = triggerDictType(**ent_dict)
                if asyncio.iscoroutine(func):
                    asyncio.create_task(func(element, self.stateDict[new_entity]))
                elif func:
                    asyncio.create_task(tools.wrap_to_coroutine(func,element,self.stateDict[new_entity]))
            
    def setup_entity_functions(self):
        for ent, ent_config in all_entities.items():
            if "trigger_functions" in ent_config:
                funcs = ent_config["trigger_functions"]
                if not isinstance(funcs, Sequence):
                    funcs = [funcs]
                self.add_entity_function(ent, call_functions=funcs)
        return

    def add_entity_function(self, entity_id: str, call_functions: list[tuple[Union[str,Callable]], bool]):
        '''
        Adds a function that is called when entity_id is updated. Can accept multiple trigger entities for the function

                Parameters:
                        entities (str): The entity that is associated with the function. If a list is provided, the function will be associated with all entities in it
                        call_function (function): The function to be called. Needs to accept a trigger_dict (called on entity update) and current stateDict (dict, with all current entity states, called after adding and reconnect). 
                                If called after adding, needs to accept a current state dict as well, which is none if the state is not defined yet. Set up can be call_function(power_funcs_test(trigger_dict=None,stateDict=None)
                        call_after_add (bool): after adding the function to the dict, run the function (true) or not (false). If starting up the dashboard, this will decide if the function is called after all states have been processed. 
        '''

        # if not isinstance(call_function, Callable):
        #     logger.error(f"{call_function} is not a function, has type {type(call_function)}")
        #     return
        

        # for entity_id in entities: 
        for func_tuple in call_functions:
            if isinstance(func_tuple, (tuple,list)):
                func, call_after_add = func_tuple
            else:
                call_after_add = True
                func = func_tuple
            
            if isinstance(func,str):
                func = self.pssmScreen.parse_shorthand_function(func)
            # func_tuple = (func, call_after_add)

            if isinstance(entity_id,str):
                if entity_id not in all_entities:
                    logger.warning(f"{entity_id} is not defined in the configuration entities")
                if entity_id in self.functionDict:
                    self._functionDict[entity_id].append((func, call_after_add))
                else:
                    self._functionDict[entity_id] = [(func, call_after_add)]
                
                #Only calls if the function is added while connected. Otherwise it's handled in the connect script.
                if call_after_add and self.connection:
                    trigger_dict = triggerDictType(entity_id=entity_id, to_state=self.stateDict[entity_id], from_state=None, context=None)
                    func(trigger_dict, self)


    async def update_states(self,trigger):
        "Updates the clients state dict from the trigger. Calls any update functions (elements and general functions) associated with the entity as well."
        updated_entity = trigger["event"]["variables"]["trigger"]["entity_id"]
        to_state = trigger["event"]["variables"]["trigger"]["to_state"]
        from_state = trigger["event"]["variables"]["trigger"]["to_state"]

        trigger_dict = trigger["event"]["variables"]["trigger"]
        trigger_dict["context"] = trigger["event"]["context"]
        self._stateDict[updated_entity] = to_state
        
        trigger_dict = MappingProxyType(trigger_dict)

        coro_list = []
        func_list = []
        if updated_entity in self.functionDict:
            logger.debug(f"Updating {updated_entity} functions: {self.functionDict[updated_entity]}")
            for (func, __) in self.functionDict[updated_entity]:
                func_list.append(func)
                coro_list.append(tools.wrap_to_coroutine(func, trigger_dict, self))
                    # func(trigger_dict=trigger, state_dict=self.stateDict)

        if self.connection and self.authenthicated:
            #self.client_update_elements(updated_entity, internalbatch=False)
            if not self.updatingAll:
                ent_elts = self.elementDict.get(updated_entity,[])
                logger.debug(f"Updating {updated_entity} elements: {ent_elts}")
                for element in ent_elts:
                    element : HAelement
                    if not hasattr(element,"trigger_function"):
                        continue
                    func = element.trigger_function
                    coro_list.append(tools.wrap_to_coroutine(func,element,trigger_dict))
                    func_list.append(func)
            else:
                logger.warning("Wanted to update {} but update all in progress".format(updated_entity))
        
        if coro_list:
            L = await asyncio.gather(*coro_list, return_exceptions=True) #, return_exceptions=True)
            #self.add_running_task(L)
            for i, res in enumerate(L):
                if isinstance(res,Exception): 
                    logger.error(f"{func_list[i]} returned an exception: {res} ")
                    if inkBoard.RAISE: raise res

    async def subscribe_to_trigger(self, entity: Union[str,list[str]] = None, trigger: dict = None):
        if entity == None and trigger == None:
            return

        if entity:
            header = trigger_headers(entity, self.__last_id)
        else:
            header = trigger
        
        if self.commanding:
            t = self.add_callback(header["id"])
            await self.messageQueue.put(header)
            subscr_resp = await t
        else:
            await self.websocket.send(json.dumps(header))
            subscr_resp = await self.websocket.recv()
            subscr_resp = json.loads(subscr_resp)

        logger.debug(subscr_resp)
        if not "success" in subscr_resp:
            logger.error(f"Error with a subscribe header {subscr_resp}")
        elif not subscr_resp["success"]:
            logger.error(f'Failed to subscribe to {header["trigger"]["entity_id"]}, server responded with {subscr_resp}')
        else:
            for func in self._subcribe_callbacks:
                func(self, header)
            return header

        return subscr_resp

    def call_service(self, elt : Union[HAelement,elements.Element]=None, coords=None, service = None, service_data = None, target = None, response = False, *args, **kwargs):
        """
        Placeholder for the old terminology of service (which was renamed to service_action in HA)

        Parameters
        ----------
        elt : Union[HAelement,elements.Element], optional
            element to optionally provide data. Will be deprecated as call_service should obtain this data from the element, by default None
        coords : _type_, optional
            the coordinates where the click was registered (not used but required to make it work as a tap_action), by default None
        service : _type_, optional
            service to call. Overwrites data from element if one has been passed, by default None
        service_data : _type_, optional
            optional data to send along with the service. Overwrites service data from element if one has been passed, by default None
        target : _type_, optional
            target to call the service on. Overwrites element target is one has been passed., by default None
        response_function : _type_, optional
            function to return the response from the service call too. This will also tell Home Assistant to return a response from this service call. Must accept a response argument. If called from an element click, this function should also accept an elt and coords parameter., by default None
        """
        return self.call_service_action(elt,coords,service,service_data,target, response, **kwargs)

    def call_service_action(self, elt : Union[HAelement,elements.Element]=None, coords : screen.CoordType = None, 
                            action : str = None, action_data : Union[dict,str] = None, target : Union[dict,str,None] = None, response : bool = False, service_id : Optional[str] = None,
                            *args, **action_data_kwargs) -> Union[asyncio.Task[Any,dict],None]:
        '''
        Builds a message for the commander to call a service action on the Home Assistant server. Mainly made to work as the tap_action function of PSSM elements, but can also be called separately
        Calls a home assistant service action
        Parameters:
                elt: element to optionally provide data. Will be deprecated as call_service should obtain this data from the element
                coords: the coordinates where the click was registered (not used but required to make tap_action work)
                action: service action to call. Overwrites data from element if one has been passed
                action_data: optional data to send along with the action. Overwrites action data from element if one has been passed
                target: target (entity id, area etc.) to call the action on. Overwrites element target is one has been passed.
                response_function (bool): If true, the response of the action call will be caught and forwarded via the task
                response (bool): If true, the function tell the client to catch the result of the action call. In this case, the `call_service_action` function will return an asyncio Task that can be awaited, which will return the result of the response (or the entire response if the call was unsuccesfull)
        '''
        logger.debug("Calling a service action")
        service_header = {}
        if service_id != None and action == None:
            logger.warning("Got a service id but this is not yet implemented from the config script")
            action = service_id

        if elt != None and hasattr(elt,"_serviceCallTime"):
            elt.update(updateAttributes={"_serviceCallTime": datetime.now()}, skipPrint=True, skipGen=True)

        return_response = response
            
        if action is not None:
            if action_data == None and action_data_kwargs:
                action_data = action_data_kwargs
            if target == None: target = getattr(elt,"entity",None)
            
            service_header = self.build_service_header(action_id = action, action_data = action_data, target = target, return_response=return_response)
        if return_response and service_header:
            response_task = self.loop.create_task(self._async_get_message_result( service_header, elt, coords))
            logger.debug("Made task for service callback and added to queue")
            return response_task
        else:
            asyncio.run_coroutine_threadsafe(
                self.messageQueue.put(service_header),
                self.pssmScreen.mainLoop
            )
        return

    def build_service_header(self, action_id : str, action_data : Optional[dict], target : Optional[Union[dict,str]] = None, return_response : bool=False) -> actionCallDict:
        '''
        Builds the header to send to Home Assistant to call the asked for service with the service data and target ID
            Parameters:
                action_id: the service to call, as you would call it in home assistant (i.e. light.turn_on)
                action_data: optional data to send along with the service
                target: target to call the service on
                return_response: tell Home Assistant to return a response from this service call
        '''
        if action_id in all_service_actions:
            service_config = all_service_actions[action_id]
            full_service = service_config["action"]
        else:
            full_service = action_id
            service_config = {}
        
        full_service = full_service.split(".")
        try:
            serv_domain = full_service[0]
            serv_service = full_service[1]
        except (TypeError, IndexError):
            logger.warning(f"Error in service action call {full_service}", exc_info=True)
            return

        msg_id = self.next_id
        service_header = { 
            "id": msg_id,
            "type": "call_service",
            "domain": serv_domain,
            "service": serv_service,
            }
        if action_data == None:
            if "data" in service_config:
                service_header.update({"service_data" : service_config["service_data"]})
        else:
            service_header.update({"service_data" : action_data})

        if target == None:
            if "target" in service_config:
                service_header.update({"target": service_config["target"]})
        else:
            if isinstance(target,(str,list,tuple)):
                target = {"entity_id": target}
            service_header.update({"target": target})
        
        if "entity_id" in service_header.get("target",{}):
            ent_target = service_header["target"]["entity_id"]
            if isinstance(ent_target,str) and ENTITY_TAG_KEY in ent_target:
                service_header["target"]["entity_id"] = parse_entity_tag(ent_target)
            elif isinstance(ent_target,(tuple,list)):
                targets = list(ent_target)
                for i, ent in enumerate(targets):
                    if ENTITY_TAG_KEY in ent:
                        targets[i] = parse_entity_tag(ent)
                service_header["target"]["entity_id"] = targets

        service_header.update({"return_response": bool(return_response)})
        return service_header

    def build_element_service_header(self, elt : Union[elements.Element, HAelement]) -> actionCallDict:
        """
        Builds a service header from a PSSM element; 

        Parameters
        ----------
        elt : Union[elements.Element, HAelement]
            the element to build from

        Returns
        -------
        actionCallDict
            The dict to put in the message queue to send to Home Assistant
        """

        if not hasattr(elt,"service_action"):
            msg = f"Calling a service from an element requires a service_action attribute to be set. {elt.id} does not have one."
            logger.exception(AttributeError(msg), stack_info=True)
            return

        service_id = elt.service
        
        service_data = {}
        if hasattr(elt,"service_data"):
            service_data = elt.service_data
        
        if hasattr(elt,"service_data_map"):
            elt.service_data_map
            for k,v in elt.service_data_map.items():
                if hasattr(elt,v): service_data[k] = getattr(elt,v)

        if not service_data: service_data = None

        target = None
        if service_data != None and "target" in service_data:
            target = service_data["target"]
            service_data.pop("target")
        elif hasattr(elt,"entity"):
            target = {"entity_id": elt.entity}

        service_message = self.build_service_header(service_id, service_data, target)
        return service_message

    async def _async_get_message_result(self, message, *args) -> Union[Any,Literal[False]]:
        """
        Quick hand to easily get the response of a message send to the command.
        Simply 

        Parameters
        ----------
        message : dict
            The message to put in the message queue. If it does not have an id yet, the id will be set automatically

        Returns
        -------
        dict
            The response. If the reponse was successful, it just returns the ["result"]["response"] part of the response (Like you would see in the developer_tools perform action part of the frontend). Returns False if the response was not succesful.
        """        

        if "id" not in message:
            message_id = self.next_id
            message["id"] = message_id
        else:
            message_id = message["id"]

        task = self.add_callback(message_id)

        #self.next_message = service_header
        await self.messageQueue.put(message)
        logger.debug(f"Waiting for service response from id {message_id}")
        # response = await resp_queue.get()
        response = await task
        # await task
        logger.debug(f"Message {message_id} returned service response.")
        if not response.get("success",False):
            logger.error(f"Error getting a service action response. Received {response}")
        return response

    async def client_update_elements(self,entity_id=None,internalbatch=False,update_all=False, timeout : int = None) -> Optional[list[Coroutine]]:
        """
        Updates the elements associated with entity_id to the last received state. Does not handle triggers, so trigger_function is called with 'old_state': False

        Parameters
        ----------
        entity_id : _type_, optional
            The entity_id to update all connected elements of, by default None
        internalbatch : bool, optional
            Start a _batch_writing process, by default False
        update_all : bool, optional
            Update all elements connected to entity, by default False
        timeout : int, optional
            If updating all elements, set an optional timeout, by default None
            The update tasks will continue in the background, but it prevents the function from blocking, i.e. when connecting

        Returns
        -------
        Optional[list[Coroutine]]
            If update_all is False, a list of all element's trigger functions is returned.
            Can be used in i.e. an asyncio.gather call.
        """        
        
        "Updates the elements associated with entity_id to the last received state. Does not handle triggers, so trigger_function is called with 'old_state': False"
        #InternalBatch: defaults to true. If true, will start a batch writing in the function. Otherwise, will asume it is defined outside of it.
        #If state_dict is still empty/does not exist: make it sleep for a bit

        ##This has to be rewritten a bit to accept async functions
        if internalbatch: self.pssmScreen.start_batch_writing()
        if update_all:
            logger.debug("[HAClient]: Updating all elements")
            coro_list = []
            self.updatingAll = True
            self.pssmScreen.start_batch_writing()
            for entity in all_entities:
                coro_list.extend(
                    await self.client_update_elements(entity_id=entity,internalbatch=False))
            if coro_list:
                # L = await asyncio.gather(*coro_list, return_exceptions=True) #, return_exceptions=True)
                try:
                    done, pending = await asyncio.wait(coro_list,loop=self.pssmScreen.mainLoop,timeout=timeout)
                except Exception as exce:
                    logger.error(exce)
                    pass
                
                if pending:
                    msgs = set()
                    for task in pending:
                        task : asyncio.Task
                        coro = task.get_coro()
                        vars = coro.cr_frame.f_locals
                        if "self" in vars:
                            elt = vars["self"]
                            func = getattr(elt,"trigger_function",None)
                        elif "element" in vars:
                            elt = vars["element"]
                            func = getattr(elt,"trigger_function",None)
                        else:
                            elt = getattr(vars,"args", [None])[0]
                            func = getattr(vars,"func",None)
                        
                        if callable(func):
                            if "HomeAssistantClient" in func.__module__:
                                func = func.__name__
                            else:
                                func = f"{func.__module__}.{func.__name__}"
                        
                        if elt == None:
                            msg = func
                        else:
                            msg = f"{elt}: {func}"
                        
                        if msg != None:
                            msgs.add(msg)

                    logger.warning(f"Element updates are taking a long time: {msgs}. Continuing in background.")
                
                    for task in done:
                        task : asyncio.Task
                        if task.exception() != None:
                            coro = task.get_coro()
                            vars = getattr(coro.cr_frame,"f_locals", {})
                            # vars = coro.cr_frame.f_locals
                            if "self" in vars:
                                elt = vars["self"]
                                # func = getattr(elt,"trigger_function",None)
                            elif "element" in vars:
                                elt = vars["element"]
                                # func = getattr(elt,"trigger_function",None)
                            else:
                                elt = getattr(vars,"args", [None])[0]
                                # func = getattr(vars,"func",None)

                            logger.warning(f"Element {elt} raised an error in it's trigger_function {getattr(coro,'__qualname__','unknown_function_name')}")
                    

            self.updatingAll = False
            self.pssmScreen.stop_batch_writing()
            return
        else:
            try:
                coro_list = []
                if entity_id in self.elementDict:
                    for element in self.elementDict[entity_id]:
                        element : HAelement
                        func = False
                        to_state = self.stateDict[entity_id]
                        # from_state = False

                        ent_dict = {"entity_id": entity_id, "to_state": to_state, 'from_state': None, 'context': None}
                        ent_dict = triggerDictType(**ent_dict)
                        
                        #el_type = str(type(element))
                        if isinstance(element,elements.Slider) and hasattr(element,"trigger_function"):
                        #if "Slider" in el_type:
                            #The slider update would jump around a bit since the lights fade. It updates on touch, and then has a delayed callback to update the indicator precisely
                            #The delay is thus not called if the service was not called recently (so when fading it from your phone eg)
                            
                            ##This should be moved to the slider  trigger_function itself
                            if element.serviceCallTime != None and (datetime.now() - element.serviceCallTime).total_seconds() < 5:
                                self.loop.create_task(self.__async_update_later(entity_id=entity_id, element=element))
                            else:
                                # element.trigger_function(element,new_state)
                                func = element.trigger_function
                                # element.trigger_function(element,ent_dict)
                        elif hasattr(element,"trigger_function"): #isinstance(element,elements.Button) or isinstance(element,elements.Icon) or isinstance(element,HAelements.MediaPlayer):
                        #elif "Icon" or "Button"in el_type:
                            # print(f"Element {element} has trigger_function {element.trigger_function}")
                            # element.trigger_function(element,new_state)
                            # element.trigger_function(element,ent_dict)
                            func = element.trigger_function
                            if isinstance(element,elements.Icon):
                                if element.fileError:
                                    msg = " Error updating {} icon for state {}: image {} does not exist".format(entity_id,to_state,element.icon)
                                    logger.warning(msg)
                                    # self.addtoLog(msg)
                        # elif isinstance(element,function):
                        #     logger.debug(f"{entity_id} has seperate update function")

                        else:
                            logger.warning("{}: Wanted to update unknown element type: {}".format(entity_id, element))
                    
                        if func:
                            # if asyncio.iscoroutine(func):
                            if asyncio.iscoroutinefunction(func): # or asyncio.iscoroutine(func):
                                coro_list.append(func(element,ent_dict))
                            else:
                                coro_list.append(asyncio.to_thread(
                                        func, element, ent_dict))
                    if internalbatch and not self.updatingAll: self.pssmScreen.stop_batch_writing()
                return coro_list
            except FuncExceptions as exce:
                msg = exce
                logger.error(f"Caught error updating elements: {exce}")
                logger.debug(msg)
                return []
                # if RAISE: raise exce
                        # except (TypeError, KeyError, IndexError, OSError, RuntimeError) as exce:
                        #     if not self.updatingAll:
                        #         logger.warning("{} {}: {}".format(entity_id, element, exce))
                        #     else:
                        #         raise exce
                            
            # except (TypeError, KeyError, IndexError, OSError, RuntimeError) as exce:
            #     logger.error("{} Caught Exception".format(entity_id), exc_info=True)
            #     if RAISE: raise exce
                # raise exce  ##Maybe place a not keyerror in the genereic update dict; pass a trigger dict with new and old state. Than catch out keyerrors
            # else:
            #     return [func]
        
    async def __async_update_later(self, entity_id, element, wait_time=5):
        await asyncio.sleep(wait_time)
        entity_range = element.range
        if hasattr(element,"attribute"):
            try:
                cur_state = self.stateDict[entity_id]["attributes"]["brightness"]
            except KeyError:
                cur_state =  self.stateDict[entity_id]
        else:
            cur_state =  self.stateDict[entity_id]
        if cur_state == "off":
            #print("State is off")
            cur_state_perc = 0
        else:
            try:
                cur_state_perc = int(((cur_state - entity_range[0])/(entity_range[1] - entity_range[0]))*100)
            except (TypeError,IndexError):
                cur_state_perc = 0
        if abs(element.position - cur_state_perc) > 5:
            element.trigger_function(element,self.stateDict[entity_id])

    def get_unit(self, unit_type : Literal["length","accumulated_precipitation","mass","pressure","temperature", "volume", "wind_speed"]) -> Optional[str]:
        """
        Returns the unit that should be the main one used for this Home Assistant instance connected to the provided unit_type.
        If the unit_type cannot be found, returns None
        Generally, if an entity has its own unit_of_measurement attribute e.g. (a weather entity has multiple unit attributes for example), it is best to use said attribute.

        Parameters
        ----------
        unit_type : Literal[&quot;length&quot;,&quot;accumulated_precipitation&quot;,&quot;mass&quot;,&quot;pressure&quot;,&quot;temperature&quot;, &quot;volume&quot;, &quot;wind_speed&quot;]
            Which type of unit to get the unit of. I.e. for a distance travelled state, use `unit_type` = length
            (So, the physical quantity type)

        Returns
        -------
        str
            The unit of the requested unit_type. None if it does not exist.
        """

        units = self._HAconfig["unit_system"]
        return units.get(unit_type,None)


class dummyClient:
    '''
    Dummy client for testing. Does not interact with pssm and likely misses functions.
    Does have some additional functions to easily get and read out responses.
    Main usage is by using the function dict to get entity triggers
    '''
    def __init__(self):
        logger.info("Starting dummy client")
        self._websocket = None
        self.hass_data = CORE.config.configuration["home_assistant"]
        self.__last_id = 0
        self.stateDict = {}

        self.__connection = False
        self.listenerTask = DummyTask()
        self.commanderTask = DummyTask()
        self.pingpongTask = DummyTask()
        self.message_queue : asyncio.Queue = False
        "queue with messages to send to the server"

        self._callback_queues : dict[int, asyncio.Queue] = {}
        """
        Dict with [message_id]: asyncio.Queue; When a message is returned with the corresponding id, the message is put in the queue. Used to get e.g. service responses
        In general, use this only to signify a callback. The Queue
        """

        self.entity_queues = {} #asyncio.Queue()
        "Dict with [entity_id]: asyncio.Queue; when the entity is updated, the trigger dict is put in the queue"

        self.functionDict = {}
        "Dict with [entity_id]: function; calls the function when the entity updates, and on connecting"

    # @property
    # def _callback_queues(self):

    @property
    def next_id(self) -> int:
        "Returns the next_id that can be used for a message (presumably)"
        self.__last_id += 1
        return self.__last_id

    async def connect_client(self, url, auth_token):
        """Starts the function that connects to Home Assistant""" 
        self.loop = asyncio.get_event_loop()
        await self.__async__connect(url, auth_token)

    async def start_client(self):
        """Starts the infinite loops to manage the Home Assistant connection (listener, commander and ping-pong)"""
        logger.debug("Starting Dummy HA Client")
        # raise Exception
        if self.listenerTask.done():
                self.listenerTask = self.loop.create_task(self.__async_listen())
        if self.commanderTask.done():
                self.commanderTask = self.loop.create_task(self.__async_command())
        #self.loop.create_task(self.__async_ping_pong())

    async def __async__connect(self, url: str, auth_token: str):
        """Sets up a websocket connection to Home Assistant"""
        
        hass_data = self.hass_data
        uri = "ws://{}/api/websocket".format(url)
        token = auth_token #hass_data["token"]
        auth_header =    {
            "type": "auth",
            "access_token": token     }
        logger.info("Attempting connection to {}".format(uri))

        # perform async connect, and store the connected WebSocketClientProtocol
        # object, for later reuse for send & recv
        try:
            self._websocket = await websockets.connect(uri)           
            await self.websocket.recv()
            self.__connection = True
            await self.websocket.send(json.dumps(auth_header))
            auth_res = json.loads(await self.websocket.recv())
            if auth_res["type"] == "auth_ok":
                self.authenthicated = True
                logger.info(f"Connected to Home Assistant {auth_res}")
            else:
                logger.error(f"Authentication failed {auth_res}")
                #self.loglist.append("{} Authentication failed: {}".format(datetime.now().strftime("%H:%M"), auth_res))
                pass

            #This gets literally ALL states, but it seems to handle fine. May however cause problems in large setups.
            # self.last_id += 1
            states_header = {"id": self.next_id, "type": "get_states" } 

            await self.websocket.send(json.dumps(states_header))
            all_states = json.loads(await self.websocket.recv())
            if all_states["success"]:
                #Finding the corresponding entitiy's entry in the list of all states
                logger.debug("Received all states from Home Assistant")
                initial_states = list(filter(lambda entity: entity["entity_id"] in all_entities, all_states["result"])) 
                all_states = None
                initial_dict = {}
                for entity in initial_states:
                    initial_dict[entity["entity_id"]] = entity

                self.stateDict = initial_dict
                
                logger.debug(f"Updating functions in function dict") #{self.functionDict}")
                called_functions = []
                for func_entity in self.functionDict:
                    for func_tuple in self.functionDict[func_entity]:
                        (func, call_func) = func_tuple
                        if func not in called_functions and call_func:
                            try:
                                func(state_dict=self.stateDict)
                                called_functions.append(func)
                            except FuncExceptions as exce:
                                logger.warning(f"Error calling function {func} for entity {func_entity}: {exce}, removed from function dict")
                                self.functionDict[func_entity].remove(func_tuple)
                #init_elements(initial_dict,self.pssm_screen,self.elementDict)
            else:
                logger.error(f"Failed to get states {all_states}")
                #self.loglist.append("{} Failed to get the initial states: {}".format(datetime.now().strftime("%H:%M"), all_states["error"]["message"]))

            #subscribe_headers = trigger_headers(config["entities"],self.last_id)
            subscribe_headers = trigger_headers(all_entities,self.__last_id)
            subscribe_fails = 0
            for header in subscribe_headers:
                await self.websocket.send(json.dumps(header))
                subscr_resp = await self.websocket.recv()
                subscr_resp = json.loads(subscr_resp)
                logger.debug(subscr_resp)
                if not "success" in subscr_resp and subscr_resp["type"] != "event":
                    logger.error(f"Error with a subscribe header {subscr_resp}")
                elif subscr_resp["type"] != "event":
                    if not subscr_resp["success"]:
                        logger.error(f'Failed to subscribe to {header["trigger"]["entity_id"]}, server responded with {subscr_resp}')
                        #self.loglist.append("{} failed to subscribe to {}: {}".format(datetime.now().strftime("%H:%M"), header["trigger"]["entity_id"],subscr_resp["error"]["message"]))
                        subscribe_fails += 1
            if subscribe_fails == 0:
                logger.info("Succesfully subscribed to all entities")

            self.__last_id = header["id"]
        except TimeoutError:
            logger.error(f'Failed to establish connection to {self.hass_data["url"]}')
            #self.loglist = ["[HAClient]: Failed to establish connection to {}".format(self.hass_data["url"])]
        except FuncExceptions as exce:
            logger.error(f"Couldn't connect {exce}")
        return        
    
    async def __async_listen(self):
        '''
        Listens to messages from the Home Assistant server
        '''
        logger.info("Starting Listener")
        #while self.connection:
        self.listening = True
        try:
            async for message in self.websocket:
                message = json.loads(message)
                id = message["id"]
                logger.debug(f"Received message {id}")
                logger.trace(message)
                if id in self._callback_queues:
                    ##Maybe have a seperate queue for service responses and one for pings/pongs.
                    queue = self._callback_queues[id]
                    logger.debug(f"Putting response from message id {id} in queue")
                    try:
                    # attempt to add an item
                        queue.put_nowait(message)
                    except asyncio.QueueFull:
                        logger.debug(f"Message id {id} has already queued a response")
                
                if message.get("type") == "event":
                    # [ ]: remove this try once the illegal instruction error is fixed
                    logger.debug(message)
                    # if "trigger" in message["event"]["variables"]:
                    ent = message["event"]["variables"]["trigger"].get("entity_id", False)
                    if ent and ent in self.entity_queues:
                        await self.entity_queues[ent].put(message)
                elif message.get("type") == "result":
                    if not message.get("succes", True):
                        logger.warning("Unsuccesful request: {}".format(message))
                        #self.loglist.append("{} Unsuccesful request: {}".format(datetime.now().strftime("%H:%M"), message["error"]["message"]))
                        self.update_Icon()
                ##Catch all other message types that are not pongs
                elif message.get("type") != "pong":
                    #print("Message seems unfamiliar: {}".format(message))
                    logger.warning("Message seems unfamiliar: {}".format(message))
        
        except websockets.exceptions.ConnectionClosedError as exce:
            logger.error(f"Websocket connection closed, calling reconnect {exce}")
            self.__connection = False
            self.reconnect_client()
                        
        logger.warning("Listener stopped")

    async def __async_command(self):
        #Pick the first entry every iteration and remove it from the list after the send --> maybe but hasn't lead to problems yet though
        '''
        Sends messages put into HAclient.message_queue to the Home Assistant server
        '''
        logger.info("Starting Commander")
        self.message_queue = asyncio.Queue()
        while self.connection:
            try:
                logger.trace(f"Waiting for message from commander queue")
                cmd = await self.message_queue.get()

                if "id" not in cmd:
                    cmd["id"] = self.next_id
                else:
                    msg_id = cmd["id"]
                    if msg_id < self.__last_id:
                        logger.debug(f"{msg_id} was already used for a websocket message. Increasing id of command {cmd}")
                        # self.last_id += 1
                        new_id = self.next_id
                        cmd["id"] = new_id
                        if msg_id in self._callback_queues:
                            # queue = self._callback_queues.pop(msg_id)
                            logger.debug(f"Message {msg_id} has a callback. Removing object from key {msg_id} and putting it in {new_id}.")
                            self._callback_queues[new_id] = self._callback_queues.pop(msg_id)

                send = await asyncio.wait_for(self.websocket.send(json.dumps(cmd)), timeout=10)
                logger.debug(f"Command send")
                logger.trace(cmd)
            except TimeoutError:
                logger.warning("Calling {}.{} timed out".format(cmd["domain"],cmd["service"]))
                #self.loglist.append("{}: Calling {}.{} timed out".format(datetime.now().strftime("%H:%M"), self.cmd["domain"],self.cmd["service"]))
            except FuncExceptions as exce:
                logger.error(f"Exception occured in commander:{exce}")
            
            #await asyncio.sleep(0)

        logger.error("Commander stopped")

    def add_callback(self, message_id : int) -> asyncio.Task:
        """
        Indicates the response of the server from the message with the specified id is needed somewhere, and puts it in an asyncio queue when received.
        The queue object is discarded from the callbacks afterwards (Since message_id's cannot be reused), and the task object returns the response.

        Parameters
        ----------
        message_id : int
            The id of the message to expect the response from

        Returns
        -------
        asyncio.Task
            A task that can be awaited on, that will return the response from the server.
        """        
        if message_id in self._callback_queues:
            logger.warning(f"A message with id {message_id} already has a callback assigned. Returning that queue")
            return self._callback_queues[message_id]
        
        resp_queue = asyncio.Queue(1)
        self._callback_queues[message_id] = resp_queue
        task = asyncio.create_task(resp_queue.get())
        return task

    async def get_response(self,message_dict : dict) -> dict:
        """
        Send a command to the server and return the response.
        see https://developers.home-assistant.io/docs/api/websocket for possible commands
        args:
            message_dict: dict with the message. Optionally add id, or let the client automatically set a correct one.
        """
        if "id" in message_dict:
            logger.debug("Using preset id")
            id = message_dict["id"]
        else:
            # self.last_id += 1
            id = self.next_id
            message_dict["id"] = id
        
        queue = asyncio.Queue(1)
        self._callback_queues[id] = queue
        await self.message_queue.put(message_dict)
        resp = await queue.get()
        return resp
    
    async def get_trigger_dict(self, entity : str) -> dict:
        """
        Returns the trigger dict upon the first state change of entity
        args:
            entity (str): entity_id to get the trigger from
        """
        if entity not in self.stateDict:
            logger.error(f"Client is not subscribed to {entity}")
            raise ValueError("Invalid entity")
        
        queue = asyncio.Queue(1)
        self.entity_queues[entity] = queue
        trigger = await queue.get()
        # raise Exception("Got value")
        self.entity_queues.pop(entity)
        return trigger