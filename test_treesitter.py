import asyncio
from pathlib import Path
from core.ast_parser import StructuralParser

async def test():
    parser = StructuralParser()
    
    files = [
        Path("multilang_test/test.cpp"),
        Path("multilang_test/Comp.java"),
        Path("multilang_test/correct.c")
    ]
    
    for f in files:
        print(f"\n--- Testing {f} ---")
        with open(f, 'r') as file:
            code = file.read()
        
        data = parser.parse(code, f)
        print(f"Classes: {[c['name'] for c in data['classes']]}")
        print(f"Functions: {[f['name'] for f in data['functions']]}")
        for func in data['functions']:
            print(f"  - {func['signature']}")

if __name__ == "__main__":
    asyncio.run(test())
