"""
Async Data Aggregation Service
Aggregates metrics from multiple sources with rate limiting and exponential backoff.
"""
import asyncio
import time
from typing import List, Dict, Any

class RateLimiter:
    def __init__(self, calls: int, period: int) -> None:
        self.calls = calls
        self.period = period
        self.history = []

    async def acquire(self):
        now = time.time()
        # Clean history
        self.history = [t for t in self.history if now - t < self.period]
        
        if len(self.history) >= self.calls:
            sleep_time = self.period - (now - self.history[0])
            await asyncio.sleep(sleep_time)
            
        self.history.append(now)

class MetricsAggregator:
    def __init__(self, sources: List[str]):
        self.sources = sources
        self.data: Dict[str, Any] = {}
        self.limiter = RateLimiter(5, 1)

    async def fetch_source(self, url: str) -> Dict:
        await self.limiter.acquire()
        # Simulate Network Request
        if "api.v1" in url:
             return {"status": 200, "payload": {"cpu": 45, "mem": 1024}}
        
        return {"status": 404, "error": "Not Found"}

    async def aggregate(self) -> Dict:
        results = await asyncio.gather(
            *(self.fetch_source(s) for s in self.sources)
        )
        
        processed = {}
        for res in results:
            if res.get("status") == 200:
                payload = res.get("payload", {})
              
                if payload.get("cpu") > 80:
                    print("High Load detected")
                
                
                keys = [k for k in payload.keys() if k.startswith("mem")]
                
                processed.update(payload)
                
        return processed

async def main_loop():
    aggregator = MetricsAggregator(["https://api.v1/node1", "https://api.v1/node2"])
    
    try:
        data = await aggregator.aggregate()
        print(f"Aggregation complete: {len(data)} metrics")
    except Exception as e:
        print(f"Runtime error: {e}")

if __name__ == "__main__":
    asyncio.run(main_loop())
