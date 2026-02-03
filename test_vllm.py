"""
Demo script to verify vLLM integration.
Tests basic connection and semantic analysis.
"""

import asyncio
from llm.vllm_client import VLLMClient

async def test_vllm():
    print("🔍 Testing vLLM Connection...")
    
    client = VLLMClient(base_url="http://localhost:8000/v1")
    
    test_prompt = """Analyze this Python code for bugs:

```python
def divide(a, b):
    return a / b
```

Respond with JSON:
{
  "issues": [
    {
      "type": "logic_error",
      "severity": "high",
      "line": 2,
      "description": "Division by zero not checked",
      "suggestion": "Add: if b == 0: raise ValueError('Cannot divide by zero')"
    }
  ]
}"""
    
    try:
        response = await client.generate_completion(test_prompt, temperature=0.1)
        print("\n✅ vLLM Response:")
        print(response)
        print("\n✅ vLLM is working correctly!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure vLLM server is running:")
        print("  python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-Coder-7B-Instruct --port 8000")

if __name__ == "__main__":
    asyncio.run(test_vllm())
