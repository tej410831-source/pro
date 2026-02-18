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
    ) -> tuple[List[SemanticBug], str]:
        """
        Analyze a specific symbol (function/method) with focused context.
        Returns: (List[SemanticBug], corrected_code)
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
            
            if not result or not result.get("issues"):
                return [], ""
            
            bugs = []
            for issue in result.get("issues", []):
                bugs.append(SemanticBug(
                    bug_type=issue.get("type", "bug"),
                    severity=issue.get("severity", "medium"),
                    line=issue.get("line", 0),
                    description=issue.get("description", ""),
                    suggestion=issue.get("suggestion", "")
                ))
            
            corrected_code = result.get("corrected_code", "")
            return bugs, corrected_code
        except Exception as e:
            print(f"Focused analysis failed for {symbol_name}: {e}")
            return [], ""

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

        return f"""You are a professional {lang} code auditor.
Your goal is to find real, logical bugs and provide a concrete code patch for each. 

**CRITICAL: BE EXTREMELY PEDANTIC.** If you see something that looks even slightly incorrect, like an unreachable loop, a potential stack overflow, or a "race condition" (even if unlikely), YOU MUST REPORT IT.

**Target File:** {file}
**Target Symbol:** {name}
{ctx_section}
{code_block}
{dep_section}

**Focus on:**
1. DEFINITE crashes or runtime errors.
2. LOGIC ERRORS that break core functionality (including unreachable code).
3. SECURITY vulnerabilities.
4. DATA CORRUPTION symptoms.
5. RACE CONDITIONS or concurrency issues (even if theoretical).

**Strict Rules:**
1. List ALL detected issues in the "issues" array.
2. Provide a SINGLE "corrected_code" block that fixes ALL listed issues simultaneously.
3. The "corrected_code" MUST be the COMPLETE replacement for the target symbol (function/class).
4. DO NOT provide "code_patch" inside individual issue objects.
5. DO NOT report style, naming, or minor best practice violations.
6. Respond ONLY with the JSON object.

Respond with a JSON object:
{{
  "issues": [
    {{
      "type": "logic_error|security|performance|error_handling|race_condition",
      "severity": "critical|high|medium|low",
      "line": <line_number>,
      "description": "<extremely detailed plain-text description of why it is a bug, be pedantic>",
      "suggestion": "<plain-text description of how to resolve>"
    }}
  ],
  "corrected_code": "<complete fixed code for the entire symbol, resolving ALL issues>"
}}"""

    async def analyze_code(self, file_path: Path, code: str, language: str, verbose: bool = False) -> tuple[List[SemanticBug], str]:
        """
        Analyze the entire file content.
        Returns: (List[SemanticBug], corrected_code)
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
            
            if not result or not result.get("issues"):
                return [], ""
            
            bugs = []
            for issue in result.get("issues", []):
                bugs.append(SemanticBug(
                    bug_type=issue.get("type", "bug"),
                    severity=issue.get("severity", "medium"),
                    line=issue.get("line", 0),
                    description=issue.get("description", ""),
                    suggestion=issue.get("suggestion", "")
                ))
            
            corrected_code = result.get("corrected_code", "")
            return bugs, corrected_code
        except Exception as e:
            print(f"Whole-file analysis failed for {file_path}: {e}")
            return [], ""
    
    def _build_detection_prompt(self, file_path: Path, code: str, language: str) -> str:
        return f"""You are a senior {language} code auditor. 
Identify ONLY concrete, actionable logical bugs and provide a code patch for each.
BE EXTREMELY PEDANTIC. Report anything that breaks logic or creates risks.

**Focus on:**
1. Potential crashes or runtime errors.
2. Serious logic flaws (including unreachable code blocks).
3. Security vulnerabilities.
4. Concurrency or race conditions.

**Rules:**
1. Provide a "corrected_code" field that contains the COMPLETE file content with all fixes applied.
2. List ALL detected issues in the "issues" array.
3. No style/formatting issues.

File: {file_path.name}
```{language}
{code}
```

Respond with a JSON object:
{{
  "issues": [
    {{
      "type": "logic_error|security|performance|error_handling|race_condition",
      "severity": "critical|high|medium|low",
      "line": <line_number>,
      "description": "<plain-text description>",
      "suggestion": "<plain-text resolution steps>"
    }}
  ],
  "corrected_code": "<complete fixed code for the entire file>"
}}"""
