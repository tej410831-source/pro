"""
LLM-Powered Bug Detector
Uses vLLM (Qwen2.5-Coder) for semantic bug detection.
"""

from pathlib import Path
from typing import List, Dict
import json

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
    
    async def analyze_code(self, file_path: Path, code: str, language: str) -> List[SemanticBug]:
        """
        Analyze code for semantic bugs using vLLM.
        """
        prompt = self._build_detection_prompt(file_path, code, language)
        
        try:
            response = await self.llm_client.generate_completion(prompt, temperature=0.1)
            
            # Parse JSON response
            result = json.loads(self._extract_json(response))
            
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
        return f"""You are an expert code reviewer specializing in {language}.

Analyze this code for bugs and issues:

File: {file_path.name}
```{language}
{code}
```

Find:
1. Logic errors (null checks, off-by-one, incorrect algorithms)
2. Security vulnerabilities (SQL injection, XSS, hardcoded secrets)
3. Performance issues
4. Error handling problems
5. Edge case issues

Respond ONLY with valid JSON in this exact format:
{{
  "issues": [
    {{
      "type": "logic_error|security|performance|error_handling",
      "severity": "critical|high|medium|low",
      "line": <line_number>,
      "description": "<what's wrong>",
      "suggestion": "<how to fix>"
    }}
  ]
}}"""
    
    def _extract_json(self, response: str) -> str:
        """Extract JSON from markdown code blocks if present."""
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            return response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            return response[start:end].strip()
        else:
            return response.strip()
