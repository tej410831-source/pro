"""
Fix Code Generator
Generates executable code patches for bugs using LLM.
"""

from typing import Dict, Optional, List
from pathlib import Path
import json
import difflib
from utils.llm_utils import extract_json, robust_json_load

class CodeFix:
    def __init__(self, fix_type: str, fixed_code: str, explanation: str, line: int):
        self.fix_type = fix_type  # "inline_replacement" or "diff"
        self.fixed_code = fixed_code
        self.explanation = explanation
        self.line = line

class FixGenerator:
    """
    Generates code fixes using LLM with AST constraints.
    """
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    async def generate_fix(
        self, 
        bug_type: str,
        severity: str,
        file_path: Path,
        line: int,
        code_snippet: str,
        language: str,
        description: str,
        suggestion: str,
        global_context: str = ""
    ) -> Optional[CodeFix]:
        """
        Generate a fix for a detected bug.
        """
        
        prompt = self._build_fix_prompt(
            bug_type, severity, str(file_path), line, code_snippet, language, description, suggestion, global_context
        )
        
        try:
            response = await self.llm_client.generate_completion(prompt)
            
            # Parse response (expected JSON)
            fix_data = robust_json_load(response)
            
            if not fix_data:
                print(f"\n  [red]✗ FAILED TO PARSE AI RESPONSE FOR {file_path.name}[/red]")
                print(f"  [dim]Check the vLLM logs or try again with a different model.[/dim]\n")
                return None
            
            if "fixed_code" not in fix_data:
                print(f"  [red]✗ Missing 'fixed_code' in LLM response for {file_path.name}[/red]")
                return None

            return CodeFix(
                fix_type=fix_data.get("fix_type", "inline_replacement"),
                fixed_code=fix_data["fixed_code"],
                explanation=fix_data.get("explanation", "Applied semantic fix."),
                line=line
            )
        except Exception as e:
            print(f"  [red]✗ Fix Generation Exception: {e}[/red]")
            return None
    
    # _extract_json replaced by utils.llm_utils.extract_json

    def _build_fix_prompt(
        self, bug_type: str, severity: str, file: str, 
        line: int, code: str, language: str,
        description: str, suggestion: str, global_context: str
    ) -> str:
        context_section = ""
        if global_context:
            context_section = f"\n**Global Context (Imports & Constants):**\n```{language}\n{global_context}\n```\n"

        return f"""You are an expert senior {language} engineer.
{context_section}
**Target Bug:**
- Type: {bug_type}
- Line: {line}
- Issue: {description}
- Recommendation: {suggestion}

**Source Code:**
```{language}
{code}
```

**Task:**
1. Fix the bug in the provided source code.
2. IMPORTANT: Return the **full and complete** source code in the `fixed_code` field.
3. Keep all other logic intact.
4. Ensure the JSON is valid. If your `fixed_code` contains double quotes, escape them as `\"`.

Respond with ONLY valid JSON:
{{
  "fixed_code": "<full source code with fix applied>",
  "explanation": "<brief summary of change>"
}}"""
    
    def generate_unified_diff(
        self, 
        original_lines: List[str], 
        fixed_lines: List[str],
        file_path: str
    ) -> str:
        """
        Generate unified diff format.
        """
        diff = difflib.unified_diff(
            original_lines,
            fixed_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=''
        )
        return '\n'.join(diff)
