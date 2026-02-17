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
    
    def __init__(self, symbol_table, llm_client=None):
        self.symbol_table = symbol_table
        self.llm_client = llm_client
        from rich.console import Console
        self.console = Console()
    
    async def detect_duplicates(self) -> List[DuplicateFunction]:
        duplicates = []
        # Filter for functions and classes that have bodies
        candidates = [s for s in self.symbol_table.symbols.values() 
                     if s.type in (SymbolType.FUNCTION, SymbolType.CLASS) and s.body_code]
        
        # 1. Structural Fingerprinting (The Filter)
        fingerprints: Dict[str, str] = {}
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeRemainingColumn()
        ) as progress:
            task1 = progress.add_task("[cyan]Fingerprinting functions...", total=len(candidates))
            
            for symbol in candidates:
                progress.update(task1, advance=1, description=f"[cyan]Fingerprinting {symbol.name} ({symbol.file.name})")
                fp = self._get_universal_fingerprint(symbol.body_code, symbol.file.suffix.lower())
                if len(fp) > 5: # Ignore trivial bodies
                    fingerprints[symbol.qualified_name] = fp

        # 2. Optimized Comparison (Bucket by length or hash to avoid O(N^2))
        # For now, we'll sort by length and only compare neighbors, or plain O(N^2) if N is small.
        # Let's simple O(N^2) but with a quick hash check.
        
        sorted_keys = sorted(fingerprints.keys(), key=lambda k: len(fingerprints[k]))
        
        checked: set = set()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeRemainingColumn()
        ) as progress:
            task2 = progress.add_task("[cyan]Comparing functions...", total=len(sorted_keys))
            
            for i, name1 in enumerate(sorted_keys):
                progress.update(task2, advance=1, description=f"[cyan]Comparing {name1}")
                fp1 = fingerprints[name1]
                sym1 = self.symbol_table.symbols[name1]
                
                # Check a window of neighbors with similar complexity
                # (Simplification: check all for now, N is likely < 100 in tests. 
                # In prod, use LSH or similar.)
                for name2 in sorted_keys[i+1:]:
                    if name1 == name2: continue
                    sym2 = self.symbol_table.symbols[name2]
                    
                    # Check 1: Must be same Symbol Type (Function vs Function)
                    if sym1.type != sym2.type:
                        continue
    
                    fp2 = fingerprints[name2]
                    
                    # Optimization: Length diff check
                    if abs(len(fp1) - len(fp2)) / max(len(fp1), len(fp2)) > 0.3:
                        continue # Too different in size
                    
                    # Check 2: Structural Similarity
                    struct_sim = difflib.SequenceMatcher(None, fp1, fp2).ratio()
                    
                    # print(f"DEBUG SIMILARITY {name1} vs {name2}: {struct_sim:.2f}") # Debug
                    
                    if struct_sim > 0.75: # Slightly relaxed for better recall
                        # Found a candidate! It has the same "shape" of logic.
                        
                        # Show user we are checking this pair using progress console to avoid UI break
                        progress.console.print(f"  [yellow]?[/yellow] Candidate: [cyan]{sym1.name}[/cyan] vs [cyan]{sym2.name}[/cyan] (Sim: {struct_sim:.2f}) -> Asking AI...")
                        
                        if self.llm_client:
                            llm_result = await self.validate_with_llm(sym1, sym2)
                            
                            # print(f"DEBUG LLM: {llm_result}") # Debug
                            
                            if llm_result.get("are_duplicates", False):
                                # Immediate feedback to user
                                progress.console.print(f"[bold green]✓ DUPLICATE CONFIRMED![/bold green]")
                                progress.console.print(f"  • Reason: {llm_result.get('shared_logic_summary', 'Same logic')}\n")

                                duplicates.append(DuplicateFunction(
                                    functions=[sym1, sym2],
                                    similarity=struct_sim,
                                    reason=f"AI Confirmed: {llm_result.get('shared_logic_summary', 'Same logic')}"
                                ))
                            else:
                                progress.console.print(f"  [dim]x AI rejected (Different logic)[/dim]")
                        else:
                            duplicates.append(DuplicateFunction(
                                functions=[sym1, sym2],
                                similarity=struct_sim,
                                reason=f"Structurally identical ({struct_sim:.2f})"
                            ))

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

    def _get_c_java_fingerprint(self, code: str) -> str:
        # Regex to capture control flow keywords, braces, and operators
        # Keywords: if, else, for, while, do, switch, case, return, break, continue, try, catch, throw
        # Operators: +, -, *, /, %, <, >, =, !, &, |, ^
        token_pattern = re.compile(
            r'\b(if|else|for|while|do|switch|case|return|break|continue|try|catch|throw)\b'
            r'|[{}]'
            r'|([+\-*/%<>!=&|^]=?)'
        )
        
        # findall returns tuples if there are multiple groups, we want to flatten
        raw_tokens = token_pattern.findall(code)
        tokens = []
        for t in raw_tokens:
            if isinstance(t, tuple):
                tokens.extend([x for x in t if x])
            else:
                tokens.append(t)
        return " ".join(tokens)

    async def validate_with_llm(self, sym1: Symbol, sym2: Symbol) -> Dict[str, Any]:
        """
        The "AI Judge": Confirms if logic is identical.
        """
        if not self.llm_client:
            return {"are_duplicates": False}
        
        prompt = f"""You are a Senior Code Reviewer.
Compare these two code snippets provided below.

GOAL: Determine if they implement the SAME LOGIC/ALGORITHM.
Ignore:
- Variable names
- Function/Class names
- Comments/Docstrings
- Whitespace formatting
- Syntax differences (if different languages)

Snippet 1 ({sym1.name} in {sym1.file.name}):
```{sym1.language if hasattr(sym1, 'language') else ''}
{sym1.body_code}
```

Snippet 2 ({sym2.name} in {sym2.file.name}):
```{sym2.language if hasattr(sym2, 'language') else ''}
{sym2.body_code}
```

Are they semantic duplicates?
Respond ONLY with valid JSON:
{{
  "are_duplicates": boolean,
  "confidence": float (0.0-1.0),
  "shared_logic_summary": "Short 1-line description",
  "optimization_suggestion": "How to consolidate"
}}"""
        
        try:
            import json
            response = await self.llm_client.generate_completion(prompt)
            # Clean possible markdown wrapping
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
                
            return json.loads(response)
        except Exception as e:
            print(f"LLM Validation Error: {e}")
            return {"are_duplicates": False, "confidence": 0.0}
