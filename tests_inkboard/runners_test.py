
import pytest
import asyncio
from pathlib import Path

from inkBoard import core as CORE, bootstrap, async_

CORE._DESIGNER_RUN = False

@pytest.mark.asyncio
async def test_reload_safe_tasks():
    # print("Testing reload")
    conf = Path(__file__).parent / "configs" / "testconfig.yaml"
    await bootstrap.setup_core(conf)
    # await bootstrap.start_core(CORE)
    # await bootstrap.run_core(CORE)
    shield_task = async_.create_reload_safe_task(_shield_coro(), name="shielded test task")
    assert async_.is_reload_shielded_task(shield_task), "task is not shielded"

    await bootstrap.reload_core(CORE)
    assert not shield_task.cancelled(), "reload safe task has been incorrectly cancelled"
    
    await bootstrap.setup_core(conf)
    await bootstrap.stop_core(CORE)
    await asyncio.sleep(0.1)
    assert shield_task.cancelled(), "reload safe task was not cancelled when it should have been (quitting inkBoard)"

    shield_task = async_.create_reload_safe_task(_shield_coro(), name="shielded test task")
    shield_task.cancel("Cancelling manually")
    await asyncio.sleep(0.1)
    assert shield_task.cancelled(), "reload safe task was not cancelled when it should have been (manually)"


async def _shield_coro():
    while True:
        await asyncio.sleep(5)

