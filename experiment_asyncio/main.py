import asyncio

def normal_function():
    return 'Hello from normal_function'

async def async_function():
    return 'Hello from async_function'

async def await_function():
    message = await async_function()
    #message = asyncio.run(async_function()) # Error: asyncio.run() cannot be called inside an async function
    return message

print(normal_function())             # normal function call
print(async_function())              # coroutine object
print(asyncio.run(async_function())) # unwrapping a coroutine object
print(await_function())              # coroutine object
print(asyncio.run(await_function())) # unwrap the coroutine object