"""
LLM-Powered Bug Detector
Uses vLLM (Qwen2.5-Coder) for semantic bug detection.
"""

from pathlib import Path
from typing import List, Dict
import json
from utils.llm_utils import extract_json, robust_json_load

class SemanticBug:
    def __init__(self, bug_type: str, severity: str, line: int, description: str, suggestion: str):
        self.type = bug_type
        self.severity = severity
        self.line = line
        self.description = description
        self.suggestion = suggestion

class LLMBugDetector:
    """
    Detects semantic bugs using LLM inference.
    """
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    async def analyze_symbol(
        self, 
        symbol_name: str, 
        code: str, 
        language: str, 
        file_path: Path,
        class_context: str = "",
        dependency_hints: str = "",
        global_vars: str = "",
        imports_list: str = "",
        verbose: bool = False
    ) -> List[SemanticBug]:
        """
        Analyze a specific symbol (function/method) with focused context.
        """
        prompt = self._build_focused_prompt(
            symbol_name, code, language, file_path.name, 
            class_context, dependency_hints, global_vars, imports_list
        )
        
        if verbose:
            print(f"\n[bold blue]--- LLM FOCUSED AUDIT PROMPT ({symbol_name} in {file_path.name}) ---[/bold blue]")
            print(prompt)
            print("[bold blue]--------------------------------------------------[/bold blue]\n")
            
        try:
            response = await self.llm_client.generate_completion(prompt, temperature=0.1)
            result = robust_json_load(response)
            
            if not result:
                return []
            
            bugs = []
            for issue in result.get("issues", []):
                bugs.append(SemanticBug(
                    bug_type=issue.get("type", "bug"),
                    severity=issue.get("severity", "medium"),
                    line=issue.get("line", 0),
                    description=issue.get("description", ""),
                    suggestion=issue.get("suggestion", "")
                ))
            return bugs
        except Exception as e:
            print(f"Focused analysis failed for {symbol_name}: {e}")
            return []

    def _build_focused_prompt(
        self, name: str, code: str, lang: str, file: str, 
        class_ctx: str, dep_hints: str, global_vars: str, imports: str
    ) -> str:
        ctx_section = ""
        
        # Module-level context (imports and globals)
        if imports or global_vars:
            ctx_section += "\n**Module Context:**\n"
            if imports:
                ctx_section += f"Imports:\n{imports}\n"
            if global_vars:
                ctx_section += f"Global Variables:\n{global_vars}\n"
        
        # Code Section: Use Class Context if available (it includes the target body), else use raw code
        if class_ctx:
            code_block = f"\n**Class Context (Skeleton):**\n```{lang}\n{class_ctx}\n```\n"
        else:
            code_block = f"\n**Target Code:**\n```{lang}\n{code}\n```\n"
        
        # Call Graph (Dependencies)
        dep_section = ""
        if dep_hints:
            dep_section = f"{dep_hints}\n"

        return f"""You are a senior {lang} code auditor.
Analyze the target code block below and identify ONLY CRITICAL, FUNCTION-BREAKING bugs.

**Target File:** {file}
**Target Symbol:** {name}
{ctx_section}
{code_block}
{dep_section}

**Focus on:**
1. DEFINITE crashes (segfaults, exceptions, null pointers).
2. LOGIC ERRORS that break the core functionality.
3. CRITICAL security vulnerabilities (e.g. buffer overflows, SQL injection).
4. DATA CORRUPTION or invalid state.

**Do NOT Report:**
1. Style, formatting, or consistent naming issues.
2. Minor performance optimizations.
3. Best practices that don't cause bugs.
4. Theoretical issues that are unlikely to occur in practice.
5. Missing documentation.

Respond with a JSON object:
{{
  "issues": [
    {{
      "type": "logic_error|security|performance|error_handling",
      "severity": "critical|high|medium|low",
      "line": <line_number>,
      "description": "<one sentence description>",
      "suggestion": "<brief fix suggestion>"
    }}
  ]
}}"""

    async def analyze_code(self, file_path: Path, code: str, language: str, verbose: bool = False) -> List[SemanticBug]:
        """
        Analyze whole file for semantic bugs using vLLM.
        """
        prompt = self._build_detection_prompt(file_path, code, language)
        
        if verbose:
            print(f"\n[bold blue]--- LLM WHOLE FILE AUDIT PROMPT ({file_path.name}) ---[/bold blue]")
            print(prompt)
            print("[bold blue]--------------------------------------------------[/bold blue]\n")
        
        try:
            response = await self.llm_client.generate_completion(prompt, temperature=0.1)
            # Parse JSON response
            result = robust_json_load(response)
            if not result:
                return []
            
            bugs = []
            for issue in result.get("issues", []):
                bugs.append(SemanticBug(
                    bug_type=issue.get("type", "bug"),
                    severity=issue.get("severity", "medium"),
                    line=issue.get("line", 0),
                    description=issue.get("description", ""),
                    suggestion=issue.get("suggestion", "")
                ))
            return bugs
        except Exception as e:
            print(f"LLM analysis failed for {file_path}: {e}")
            return []
    
    def _build_detection_prompt(self, file_path: Path, code: str, language: str) -> str:
        return f"""You are a senior {language} code auditor. 
Analyze the provided code and identify ONLY concrete, actionable bugs. 

**Focus on:**
1. Potential crashes or runtime errors.
2. Serious logic flaws that would break the intended functionality.
3. Obvious security vulnerabilities.

**Ignore:**
1. Style or formatting issues.
2. Missing docstrings or comments.
3. Minor optimizations unless they are critical.

File: {file_path.name}
```{language}
{code}
```

Respond with a JSON object containing a list of issues.
{{
  "issues": [
    {{
      "type": "logic_error|security|performance|error_handling",
      "severity": "critical|high|medium|low",
      "line": <line_number>,
      "description": "<one sentence description>",
      "suggestion": "<brief fix suggestion>"
    }}
  ]
}}"""
    
    # _extract_json replaced by utils.llm_utils.extract_json
