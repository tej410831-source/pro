from core.ast_parser import StructuralParser
from pathlib import Path
import json

parser = StructuralParser()
# Test C file if SemanticBugs.java is tedious? Or check SemanticBugs.java again.
file_path = Path("multilang_test/SemanticBugs.java")

with open(file_path, 'r', encoding='utf-8') as f:
    code = f.read()

data = parser.parse(code, file_path)

print("Functions found:")
for func in data["functions"]:
    print(f"Name: {func['name']}")
    print(f"Calls: {func.get('calls')}")

print("\nVariables (Fields/Globals):")
for var in data.get("variables", []):
    print(f"Name: {var['name']} (Line {var['line']}) Type: {var['type']}")

print("\nIdentifiers (Count):", len(data.get("identifiers", [])))
print("Sample Identifiers:", data.get("identifiers", [])[:20])
