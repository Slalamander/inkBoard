"""asyncio utilities for inkBoard
"""
import asyncio
from asyncio import Task, coroutines
from asyncio import create_task, shield, iscoroutine, iscoroutinefunction
from types import CoroutineType

from collections import abc

from PythonScreenStackManager.tools import DummyTask


_reload_shield = object()

def create_reload_safe_task(coro, *, name : str = None) -> Task:
    """Creates an asyncio Task and indicates it should not be cancelled when reloading inkBoard

    Parameters
    ----------
    coro :
        The coroutine to pass to the task
    name : str, optional
        The name of the task, by default None

    Returns
    -------
    Task
        The task object
    """

    task = create_task(coro = coro, name=name)
    task._reload_shield = _reload_shield
    return task


def is_reload_shielded_task(task):
    return getattr(task, "_reload_shield", None) == _reload_shield