"""
Fix Code Generator
Generates executable code patches for bugs using LLM.
"""

from typing import Dict, Optional
from pathlib import Path
import difflib

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
        language: str
    ) -> Optional[CodeFix]:
        """
        Generate a fix for a detected bug.
        """
        
        prompt = self._build_fix_prompt(
            bug_type, severity, str(file_path), line, code_snippet, language
        )
        
        try:
            response = await self.llm_client.generate_completion(prompt)
            
            # Parse response (expected JSON)
            import json
            fix_data = json.loads(response)
            
            return CodeFix(
                fix_type=fix_data.get("fix_type", "inline_replacement"),
                fixed_code=fix_data["fixed_code"],
                explanation=fix_data["explanation"],
                line=line
            )
        except Exception as e:
            # Fix generation failed, return None
            return None
    
    def _build_fix_prompt(
        self, bug_type: str, severity: str, file: str, 
        line: int, code: str, language: str
    ) -> str:
        return f"""You are an expert software engineer specializing in bug fixes.

Bug detected:
- Type: {bug_type}
- Severity: {severity}
- File: {file}
- Line: {line}

Original Code:
```{language}
{code}
```

Task:
1. Fix the bug
2. Keep behavior unchanged except for the fix
3. Follow {language} best practices
4. Output ONLY valid, executable code

Respond in JSON format:
{{
  "fix_type": "inline_replacement",
  "fixed_code": "<complete fixed code>",
  "explanation": "<what was changed and why>"
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
