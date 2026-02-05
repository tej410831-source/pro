"""
vLLM Client
Interfaces with local Qwen2.5-Coder via OpenAI-compatible API.
"""

from typing import Optional
from openai import AsyncOpenAI
import hashlib
import json

class VLLMClient:
    def __init__(self, base_url: str = "http://localhost:8000/v1", model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="EMPTY"
        )
        self.model = model
        self.cache = {}  # Disabled persistent caching per user request
    
    async def generate_completion(
        self, 
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4096
    ) -> str:
        """Generate completion with caching."""
        
        # Cache key based on prompt hash
        cache_key = hashlib.md5(prompt.encode()).hexdigest()
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            result = response.choices[0].message.content
            self.cache[cache_key] = result
            return result
            
        except Exception as e:
            raise RuntimeError(f"vLLM request failed: {e}")
