import ast
from typing import List, Dict, Tuple
from core.symbol_table import Symbol, SymbolType
import difflib

class DuplicateFunction:
    def __init__(self, functions: List[Symbol], similarity: float, reason: str):
        self.functions = functions
        self.similarity = similarity
        self.reason = reason

class CrossFileRedundancyDetector:
    """
    Detects semantic duplicates: Functions with same LOGIC but different VARIABLES.
    Approach:
    1. Structural Filter (AST): Compare code skeletons (node types) to find candidates.
    2. Semantic Verify (LLM): Ask AI if logic is identical despite renaming.
    """
    
    def __init__(self, symbol_table, llm_client=None):
        self.symbol_table = symbol_table
        self.llm_client = llm_client
    
    async def detect_duplicates(self) -> List[DuplicateFunction]:
        duplicates = []
        functions = [s for s in self.symbol_table.symbols.values() 
                    if s.type == SymbolType.FUNCTION and s.body_code]
        
        # 1. Structural Fingerprinting (The Filter)
        # Convert all functions to "skeletons" (AST node sequences)
        fingerprints = {}
        for func in functions:
            try:
                fingerprints[func.qualified_name] = self._get_structural_fingerprint(func.body_code)
            except:
                fingerprints[func.qualified_name] = "" # Parse error fallback

        # 2. Compare Candidates
        checked_pairs = set()
        
        for i, func1 in enumerate(functions):
            for func2 in functions[i+1:]:
                # Skip same file
                if func1.file == func2.file:
                    continue
                
                # Check normalized structure similarity first
                fp1 = fingerprints.get(func1.qualified_name)
                fp2 = fingerprints.get(func2.qualified_name)
                
                if not fp1 or not fp2:
                    continue
                    
                # Structural Similarity (Sequence Match on Node Types)
                # This ignores variable names completely!
                struct_sim = difflib.SequenceMatcher(None, fp1, fp2).ratio()
                
                if struct_sim > 0.85: # High structural overlap
                    # Found a candidate! It has the same "shape" of logic.
                    
                    # 3. AI Verification (The Judge)
                    # Even if structure matches, ask LLM if logic is TRULY same
                    # (e.g. maybe constants differ significantly)
                    
                    is_semantic_duplicate = False
                    reason = f"Structurally identical (AST match: {struct_sim:.2f})"
                    
                    if self.llm_client:
                        llm_result = await self.validate_with_llm(func1, func2)
                        is_semantic_duplicate = llm_result.get("are_duplicates", False)
                        if is_semantic_duplicate:
                            reason = f"AI Confirmed: {llm_result.get('shared_logic_summary', 'Same logic')}"
                    else:
                        # Fallback to structural only if no LLM
                        is_semantic_duplicate = True
                        
                    if is_semantic_duplicate:
                        duplicates.append(DuplicateFunction(
                            functions=[func1, func2],
                            similarity=struct_sim,
                            reason=reason
                        ))
        
        return duplicates

    def _get_structural_fingerprint(self, code: str) -> str:
        """
        Walks the AST and returns a string of node types.
        Example: "FunctionDef If Compare Return"
        This strips away all variable names ('x', 'y') and values.
        """
        try:
            # Normalize indentation just in case
            import textwrap
            code = textwrap.dedent(code)
            tree = ast.parse(code)
            
            node_types = []
            for node in ast.walk(tree):
                # We collect the TYPE of the node, e.g. "For", "If", "Assign"
                node_types.append(type(node).__name__)
            
            return " ".join(node_types)
        except:
            return ""

    async def validate_with_llm(self, func1: Symbol, func2: Symbol) -> Dict:
        """
        The "AI Judge": Confirms if logic is identical.
        """
        if not self.llm_client:
            return {"are_similar": False}
        
        prompt = f"""You are a Senior Code Reviewer.
Compare these two functions provided below.

GOAL: Determine if they implement the SAME LOGIC/ALGORITHM.
Ignore:
- Variable names (e.g. 'calc_tax' vs 'get_vat')
- Function names
- Comments/Docstrings
- Whitespace formatting

Focus on:
- Control flow (loops, ifs)
- Data transformations
- The core algorithm

Function 1 ({func1.name}):
```python
{func1.body_code}
```

Function 2 ({func2.name}):
```python
{func2.body_code}
```

Are they semantic duplicates?
Respond ONLY with valid JSON:
{{
  "are_duplicates": boolean,
  "confidence": float (0.0-1.0),
  "shared_logic_summary": "Short 1-line description of the common logic",
  "optimization_suggestion": "How to consolidate them"
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
