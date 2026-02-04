import asyncio
import contextvars

# Create a context variable (like a request ID in a web framework)
request_id = contextvars.ContextVar('request_id')

async def process_data():
    # This function reads the context variable
    rid = request_id.get()
    print(f"Processing with request_id: {rid}")
    await asyncio.sleep(0.1)
    return f"Result for {rid}"

async def log_something():
    rid = request_id.get()
    print(f"Logging for request_id: {rid}")

# ❌ WITHOUT Runner - context is LOST between calls
print("WITHOUT Runner:")
request_id.set("REQ-001")
result1 = asyncio.run(process_data())  # New loop = new context, ContextVar is gone!
# This would raise LookupError because context was lost:
# result2 = asyncio.run(log_something())

# ✅ WITH Runner - context is PRESERVED
print("\nWITH Runner:")
request_id.set("REQ-002")
with asyncio.Runner() as runner:
    result1 = runner.run(process_data())    # Sets up context
    result2 = runner.run(log_something())   # SAME context, can access request_id!

print(f"Results: {result1}, {result2}")

# 🎯 BETTER: Normal async pattern - context preserved naturally
print("\nNormal async pattern:")
async def main():
    request_id.set("REQ-003")
    result1 = await process_data()
    result2 = await log_something()  # Context preserved naturally
    return result1, result2

results = asyncio.run(main())
print(f"Results: {results}")