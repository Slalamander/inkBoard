
import pytest
import asyncio
from pathlib import Path

from inkBoard import core as CORE, bootstrap, async_

@pytest.mark.asyncio
async def test_reload_safe_tasks():

    conf = Path(__file__).parent / "configs" / "testconfig.yaml"
    await bootstrap.setup_core(conf)
    shield_task = async_.create_reload_safe_task(_shield_test())

    await bootstrap.reload_core(CORE)

    assert not shield_task.cancelled(), "reload safe task has been incorrectly cancelled"
    
    shield_task.cancel("Testing cancellation")

    assert shield_task.cancelled(), "reload safe task was not cancelled when it should have been (manually)"

async def _shield_test():
    while True:
        await asyncio.sleep(5)