"""
Cross-File Redundancy Detector
Finds duplicate and similar functions across different files.
"""

from pathlib import Path
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
    Detects similar/duplicate functions across files.
    Uses multi-stage filtering: size -> token similarity -> LLM validation
    """
    
    def __init__(self, symbol_table, llm_client=None):
        self.symbol_table = symbol_table
        self.llm_client = llm_client
    
    def detect_duplicates(self) -> List[DuplicateFunction]:
        """
        Find duplicate functions across files.
        """
        duplicates = []
        
        # Get all functions
        functions = [s for s in self.symbol_table.symbols.values() 
                    if s.type == SymbolType.FUNCTION]
        
        # Compare pairs
        for i, func1 in enumerate(functions):
            for func2 in functions[i+1:]:
                # Skip same file
                if func1.file == func2.file:
                    continue
                
                similarity = self._calculate_similarity(func1, func2)
                
                if similarity > 0.7:  # High similarity threshold
                    duplicates.append(DuplicateFunction(
                        functions=[func1, func2],
                        similarity=similarity,
                        reason=f"Token similarity: {similarity:.2f}"
                    ))
        
        return duplicates
    
    def _calculate_similarity(self, func1: Symbol, func2: Symbol) -> float:
        """
        Calculate token-based similarity using SequenceMatcher.
        """
        # Get code for both functions
        code1 = func1.signature  # Use signature as proxy for now
        code2 = func2.signature
        
        # Tokenize (simple: split by whitespace)
        tokens1 = set(code1.split())
        tokens2 = set(code2.split())
        
        # Jaccard similarity
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    async def validate_with_llm(self, func1: Symbol, func2: Symbol) -> Dict:
        """
        Use LLM to semantically validate if functions are truly similar.
        """
        if not self.llm_client:
            return {"are_similar": False, "confidence": 0.0}
        
        prompt = f"""Compare these two functions from different files:

Function 1 ({func1.file.name}):
{func1.signature}

Function 2 ({func2.file.name}):
{func2.signature}

Are they doing essentially the same thing?

Respond with JSON:
{{
  "are_similar": true/false,
  "confidence": 0.0-1.0,
  "reason": "...",
  "consolidation_suggestion": "..."
}}"""
        
        try:
            import json
            response = await self.llm_client.generate_completion(prompt)
            return json.loads(response)
        except:
            return {"are_similar": False, "confidence": 0.0}
