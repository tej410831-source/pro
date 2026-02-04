# Test Lab: Verification Project for Phases 1-4

This project contains intentional errors and structures to test the analysis pipeline.

## 1. Syntax Error (Phase 2 Test)
`bad_syntax.py` has a missing colon and parenthesis.

## 2. Cross-File Call Graph (Phase 3 & 4 Test)
`main.py` calls `utils.helper()`.

## 3. Circular Dependency (Phase 4 Test)
`cycle_a.py` imports `cycle_b` and vice-versa.

## 4. Dead Code (Phase 4 Test)
`dead_code.py` defines `zombie_function()` which is never called.

## 5. Multi-Language (Phase 3 Test)
`Greeter.java` and `calc.c` are provided to test tree-sitter indexing.
