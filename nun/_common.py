"""Common functions"""
from asyncio.events import get_running_loop
from functools import partial


async def run_async(func, *args, **kwargs):
    """
    Run function asynchronously.

    Args:
        func (function):
        args: Function arguments.
        kwargs: Function keyword arguments.

    Returns:
        function result
    """
    return await get_running_loop().run_in_executor(
        None, partial(func, *args, **kwargs))
