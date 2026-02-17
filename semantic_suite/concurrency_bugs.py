"""
Concurrency Bug Test Suite
Syntactically valid Python with intentional async/threading bugs for Phase 3 detection.
"""

import asyncio
import threading


# ==================== ASYNC BUGS ====================

# BUG 1: Missing await on coroutine — coroutine object never executed
async def fetch_user(user_id: int) -> dict:
    await asyncio.sleep(0.1)  # Simulate network call
    return {"id": user_id, "name": f"User_{user_id}"}
async def fetch_user(user_id: int) -> dict:
    await asyncio.sleep(0.1)  # Simulate network call
    return {"id": user_id, "name": f"User_{user_id}"}

async def get_all_users(user_ids: list) -> list:
    results = []
    for uid in user_ids:
        user = fetch_user(uid)  # BUG: missing 'await', gets coroutine object not dict
        results.append(user)
    return results


# BUG 2: Async function called as sync — never actually runs
async def send_notification(message: str):
    await asyncio.sleep(0.01)
    print(f"Notification sent: {message}")

def handle_order(order_id: int):
    """Process an order."""
    print(f"Processing order {order_id}")
    send_notification(f"Order {order_id} confirmed")  # BUG: coroutine created but never awaited
    print("Order done")


# BUG 3: Shared mutable state without lock in async context
class AsyncCounter:
    def __init__(self):
        self.count = 0  # BUG: no lock protecting this

    async def increment(self):
        current = self.count  # BUG: race condition — read
        await asyncio.sleep(0)  # Yield control
        self.count = current + 1  # BUG: write could be stale

    async def run_concurrent(self, n: int):
        tasks = [self.increment() for _ in range(n)]
        await asyncio.gather(*tasks)
        return self.count  # May not equal n due to race condition


# ==================== THREADING BUGS ====================

# BUG 4: Race condition on shared list
shared_results = []

def worker_append(value: int):
    """Worker that appends to shared list."""
    global shared_results
    temp = shared_results.copy()  # BUG: TOCTOU — list could change between copy and append
    temp.append(value)
    shared_results = temp  # BUG: overwrites concurrent modifications


# BUG 5: Deadlock potential — inconsistent lock ordering
lock_a = threading.Lock()
lock_b = threading.Lock()

def transfer_funds(from_account: dict, to_account: dict, amount: float):
    """Transfer money between accounts."""
    with lock_a:  # Acquires lock_a first
        with lock_b:  # Then lock_b
            from_account["balance"] -= amount
            to_account["balance"] += amount

def reverse_transfer(from_account: dict, to_account: dict, amount: float):
    """Reverse a transfer."""
    with lock_b:  # BUG: Acquires lock_b first (opposite order) — DEADLOCK potential
        with lock_a:
            from_account["balance"] += amount
            to_account["balance"] -= amount


# BUG 6: Thread-unsafe singleton pattern
class DatabasePool:
    _instance = None

    def __init__(self):
        self.connections = []

    @classmethod
    def get_instance(cls):
        if cls._instance is None:  # BUG: race condition — two threads could both see None
            cls._instance = cls()
        return cls._instance


# BUG 7: Fire-and-forget thread without join — may not complete
def background_save(data: dict):
    """Save data in background."""
    def _save():
        import time
        time.sleep(1)
        print(f"Saved: {data}")

    t = threading.Thread(target=_save)
    t.start()
    # BUG: no t.join() — function returns immediately, program may exit before save completes


# BUG 8: Async generator consumed incorrectly
async def generate_batches(items: list, batch_size: int):
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]

async def process_all_batches(items: list):
    batches = generate_batches(items, 10)  # Returns async generator
    for batch in batches:  # BUG: should be 'async for batch in batches'
        print(f"Processing batch: {batch}")


async def fetch_user_details(user_id: int) -> dict:
    await asyncio.sleep(0.1)
    return {'id': user_id, 'name': f'User_{user_id}'}
