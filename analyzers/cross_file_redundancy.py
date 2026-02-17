import ast
import re
from typing import List, Dict, Tuple, Any
from core.symbol_table import Symbol, SymbolType
import difflib
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

class DuplicateFunction:
    def __init__(self, functions: List[Symbol], similarity: float, reason: str):
        self.functions = functions
        self.similarity = similarity
        self.reason = reason

class CrossFileRedundancyDetector:
    """
    Detects semantic duplicates: Functions with same LOGIC but different VARIABLES.
    Approach:
    1. Structural Filter: Compare control flow skeletons to find candidates.
       - Python: AST node types
       - C/C++/Java: Regex-based keyword sequences
    2. Semantic Verify (LLM): Ask AI if logic is truly identical.
    """
    
    # Dunder methods to skip — these are boilerplate and naturally similar across classes
    SKIP_METHODS = {
        '__init__', '__str__', '__repr__', '__eq__', '__ne__', '__lt__', '__gt__',
        '__le__', '__ge__', '__hash__', '__len__', '__bool__', '__del__',
        '__enter__', '__exit__', '__iter__', '__next__', '__getitem__', '__setitem__',
        '__contains__', '__call__', '__new__', '__setattr__', '__getattr__',
    }
    
    MIN_BODY_LINES = 4  # Minimum function body lines to consider
    AST_SIMILARITY_THRESHOLD = 0.85  # Minimum AST fingerprint similarity
    
    def __init__(self, symbol_table, llm_client=None):
        self.symbol_table = symbol_table
        self.llm_client = llm_client
        from rich.console import Console
        self.console = Console()
    
    async def detect_duplicates(self, console=None) -> List[DuplicateFunction]:
        duplicates = []
        
        # PRE-CHECK: Detect exact duplicate definitions (same name, same file)
        # The symbol table deduplicates by name, so we scan the raw AST
        seen_files = set()
        for sym in self.symbol_table.symbols.values():
            if sym.file not in seen_files:
                seen_files.add(sym.file)
        
        for file_path in seen_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                tree = ast.parse(source)
                exact_dups = self._find_duplicate_defs(tree, file_path, source)
                if exact_dups:
                    duplicates.extend(exact_dups)
                    if console:
                        for dup in exact_dups:
                            f1, f2 = dup.functions
                            console.print(f"  [red]⚠ Exact duplicate definition: {f1.name}() defined at lines {f1.line} AND {f2.line} in {file_path.name}[/red]")
            except:
                pass
        
        # Filter: only real logic functions (no dunders, no trivially small)
        functions = [
            s for s in self.symbol_table.symbols.values() 
            if s.type == SymbolType.FUNCTION 
            and s.body_code
            and len(s.body_code.strip().splitlines()) >= self.MIN_BODY_LINES
            and s.name not in self.SKIP_METHODS
        ]
        
        if console:
            console.print(f"  [dim]Comparing {len(functions)} functions for similarity (skipped dunder methods)...[/dim]")
        
        # 1. Structural Fingerprinting (The Filter)
        fingerprints = {}
        for func in functions:
            try:
                fingerprints[func.qualified_name] = self._get_structural_fingerprint(func.body_code)
            except:
                fingerprints[func.qualified_name] = ""

        # 2. Compare All Candidate Pairs (same-file AND cross-file)
        for i, func1 in enumerate(functions):
            for func2 in functions[i+1:]:
                
                # Skip comparing methods of the same class (e.g. get vs set)
                if (func1.parent_name and func2.parent_name 
                    and func1.parent_name == func2.parent_name):
                    continue
                
                # Check a window of neighbors with similar complexity
                # (Simplification: check all for now, N is likely < 100 in tests. 
                # In prod, use LSH or similar.)
                for name2 in sorted_keys[i+1:]:
                    if name1 == name2: continue
                    sym2 = self.symbol_table.symbols[name2]
                    
                # Structural Similarity (Sequence Match on Node Types)
                struct_sim = difflib.SequenceMatcher(None, fp1, fp2).ratio()
                
                if struct_sim > self.AST_SIMILARITY_THRESHOLD:
                    # 3. AI Verification (The Judge)
                    if console:
                        same_or_cross = "same-file" if func1.file == func2.file else "cross-file"
                        console.print(f"  [cyan]🔍 Candidate ({same_or_cross}): {func1.name} ↔ {func2.name} (AST: {struct_sim:.0%})[/cyan]")
                    
                    is_semantic_duplicate = False
                    reason = f"Structurally similar (AST match: {struct_sim:.2f})"
                    suggestion = ""
                    
                    if self.llm_client:
                        llm_result = await self.validate_with_llm(func1, func2)
                        is_semantic_duplicate = llm_result.get("are_duplicates", False)
                        if is_semantic_duplicate:
                            reason = llm_result.get("shared_logic_summary", "Same logic")
                            suggestion = llm_result.get("optimization_suggestion", "")
                    else:
                        is_semantic_duplicate = True
                        
                    if is_semantic_duplicate:
                        dup = DuplicateFunction(
                            functions=[func1, func2],
                            similarity=struct_sim,
                            reason=reason
                        )
                        dup.suggestion = suggestion
                        duplicates.append(dup)
                        if console:
                            console.print(f"    [red]⚠ Confirmed duplicate![/red]")
                    else:
                        if console:
                            console.print(f"    [green]✓ Not a duplicate[/green]")
        
        return duplicates

    def _get_universal_fingerprint(self, code: str, extension: str) -> str:
        """
        Returns a simplified structural string of the code.
        """
        code = code.strip()
        if not code: return ""

        if extension == '.py':
            return self._get_python_fingerprint(code)
        elif extension in ['.c', '.cpp', '.h', '.hpp', '.java']:
            return self._get_c_java_fingerprint(code)
        
        return code # Fallback: raw code

    def _get_python_fingerprint(self, code: str) -> str:
        try:
            tree = ast.parse(code)
            node_types = []
            for node in ast.walk(tree):
                # Include binops to differentiate math
                if isinstance(node, ast.BinOp):
                    node_types.append(f"BinOp_{type(node.op).__name__}")
                else:
                    node_types.append(type(node).__name__)
            return " ".join(node_types)
        except:
            return ""

    def _find_duplicate_defs(self, tree, file_path, source: str) -> List[DuplicateFunction]:
        """
        Scan a file's AST to find functions defined multiple times with the same name
        at the same scope (top-level or within the same class).
        This catches cases the symbol table misses due to key deduplication.
        """
        from pathlib import Path
        duplicates = []
        source_lines = source.splitlines()
        
        # Collect all function defs at each scope
        # scope_key -> list of (name, lineno, end_lineno)
        scopes = {}
        
        # Top-level functions
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                key = ("top", node.name)
                if key not in scopes:
                    scopes[key] = []
                scopes[key].append(node)
            
            # Functions inside classes
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        key = (node.name, item.name)
                        if key not in scopes:
                            scopes[key] = []
                        scopes[key].append(item)
        
        # Find names defined more than once at same scope
        for (scope, name), nodes in scopes.items():
            if len(nodes) < 2:
                continue
            
            # Create pairs for each duplicate
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    n1, n2 = nodes[i], nodes[j]
                    
                    # Extract body code for each definition
                    end1 = getattr(n1, 'end_lineno', n1.lineno + 5)
                    end2 = getattr(n2, 'end_lineno', n2.lineno + 5)
                    body1 = "\n".join(source_lines[n1.lineno - 1:end1])
                    body2 = "\n".join(source_lines[n2.lineno - 1:end2])
                    
                    # Create lightweight Symbol-like objects
                    parent = scope if scope != "top" else None
                    sym1 = Symbol(name=name, symbol_type=SymbolType.FUNCTION, file_path=file_path, 
                                 line=n1.lineno, signature=f"def {name}(...)", body_code=body1,
                                 parent_name=parent or "")
                    sym2 = Symbol(name=name, symbol_type=SymbolType.FUNCTION, file_path=file_path,
                                 line=n2.lineno, signature=f"def {name}(...)", body_code=body2,
                                 parent_name=parent or "")
                    
                    dup = DuplicateFunction(
                        functions=[sym1, sym2],
                        similarity=1.0,
                        reason=f"Exact duplicate: {name}() defined twice in {file_path.name}"
                    )
                    dup.suggestion = f"Remove the duplicate definition at line {n2.lineno}"
                    duplicates.append(dup)
        
        return duplicates

    async def validate_with_llm(self, func1: Symbol, func2: Symbol) -> Dict:
        """
        The "AI Judge": Confirms if logic is truly identical.
        Uses a strict prompt to minimize hallucination.
        """
        if not self.llm_client:
            return {"are_duplicates": False}
        
        prompt = f"""Compare these two Python functions and determine if they do the EXACT SAME THING.

Function A — "{func1.name}":
```
{func1.body_code}
```

Function B — "{func2.name}":
```
{func2.body_code}
```

IMPORTANT: Two functions are duplicates ONLY if they perform the same computation/algorithm.
- Same control flow (same loops, same conditions)
- Same data transformations (same operations on inputs)
- Different variable names or function names do NOT matter

They are NOT duplicates if:
- They operate on different data types
- They have different logic (even slightly)
- One has extra steps the other doesn't

Answer with ONLY valid JSON, nothing else:
{{"are_duplicates": true, "shared_logic_summary": "one line description", "optimization_suggestion": "how to merge them"}}
or
{{"are_duplicates": false, "shared_logic_summary": "N/A", "optimization_suggestion": "N/A"}}"""
        
        try:
            import json
            import re
            response = await self.llm_client.generate_completion(prompt)
            
            # Try multiple extraction strategies
            cleaned = response.strip()
            
            # Strategy 1: Extract JSON from markdown code block
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            
            # Strategy 2: Find JSON object with regex
            json_match = re.search(r'\{[^{}]*"are_duplicates"[^{}]*\}', cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)
            
            # Normalize boolean values (LLM might output True/False instead of true/false)
            cleaned = cleaned.replace(': True', ': true').replace(': False', ': false')
            cleaned = cleaned.replace(':True', ':true').replace(':False', ':false')
            
            try:
                result = json.loads(cleaned)
                return result
            except json.JSONDecodeError:
                # Strategy 3: Look for are_duplicates keyword with any format
                dup_match = re.search(r'"are_duplicates"\s*:\s*(true|false)', cleaned, re.IGNORECASE)
                if dup_match:
                    is_dup = dup_match.group(1).lower() == 'true'
                    summary_match = re.search(r'"shared_logic_summary"\s*:\s*"([^"]*)"', cleaned)
                    suggestion_match = re.search(r'"optimization_suggestion"\s*:\s*"([^"]*)"', cleaned)
                    return {
                        "are_duplicates": is_dup,
                        "shared_logic_summary": summary_match.group(1) if summary_match else "Same logic detected",
                        "optimization_suggestion": suggestion_match.group(1) if suggestion_match else "Consolidate into one function"
                    }
                
                return {"are_duplicates": False}
                
        except Exception as e:
            print(f"LLM Validation Error ({func1.name} vs {func2.name}): {e}")
            return {"are_duplicates": False}
