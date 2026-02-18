
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.getcwd())

try:
    import tree_sitter_languages
    print(f"Tree-sitter languages module: {tree_sitter_languages}")
except ImportError:
    print("Failed to import tree_sitter_languages")

from analyzers.static_syntax import StaticSyntaxAnalyzer
import tree_sitter
print(f"tree_sitter: {tree_sitter}")
from tree_sitter import Parser
print(f"Parser class: {Parser}")
try:
    p = Parser()
    print("Parser() init success")
except Exception as e:
    print(f"Parser() init failed: {e}")

try:
    import tree_sitter_languages
    p = tree_sitter_languages.get_parser('c')
    print("get_parser('c') success")
except Exception as e:
    print(f"get_parser('c') failed: {e}")

analyzer = StaticSyntaxAnalyzer()

test_files = [
    "tests/comprehensive_test_suite/01_syntax/syntax_error.c",
    "tests/comprehensive_test_suite/01_syntax/syntax_error.cpp",
    "tests/comprehensive_test_suite/01_syntax/SyntaxError.java"
]

for fpath in test_files:
    path = Path(fpath)
    if not path.exists():
        print(f"File not found: {path}")
        continue
    
    print(f"\nAnalyzing {path}...")
    is_valid, errors = analyzer.analyze_file(path)
    print(f"Result: Valid={is_valid}, Errors={len(errors)}")
    for e in errors:
        print(f"  - {e.message} at line {e.line}")
