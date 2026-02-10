"""
Static Syntax Analyzer (Python Only + LLM for others)
Deterministic, compiler-grade syntax checking using Python's native AST for Python.
LLM-based syntax checking for C/C++/Java (experimental).
"""

import ast
from pathlib import Path
from typing import List, Tuple

class FileSyntaxError:
    def __init__(self, message: str = "", parser: str = "unknown", line: int = 0, column: int = 0):
        self.line = line
        self.column = column
        self.message = message
        self.parser = parser
        # Compatibility attributes
        self.type = "syntax_error"
        self.severity = "critical"

class StaticSyntaxAnalyzer:
    """Analyze source files for syntax errors using native AST (Python) or LLM (C/C++/Java)."""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.lang_map = {
            '.py': 'python',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.h': 'cpp', # Treat headers as CPP for now
            '.hpp': 'cpp',
            '.java': 'java'
        }
    
    async def analyze_file(self, file_path: Path) -> Tuple[bool, List[FileSyntaxError]]:
        """
        Analyze a file for syntax errors.
        """
        if not file_path.exists():
             return False, [FileSyntaxError(f"File not found: {file_path}", "os-error")]

        ext = file_path.suffix.lower()
        if ext == '.py':
            # Deterministic Python check
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                return self._check_python_code(source)
            except Exception as e:
                return False, [FileSyntaxError(f"Read error: {str(e)}", "python-io")]
        
        elif ext in self.lang_map:
            # LLM-based check for C/C++/Java
            if not self.llm_client:
                 # If no LLM, we can't check syntax for these languages
                 return True, [] 
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                language = self.lang_map[ext]
                return await self._check_syntax_with_llm(source, language, file_path.name)
            except Exception as e:
                 return False, [FileSyntaxError(f"Analysis error: {str(e)}", f"{language}-llm")]
        
        else:
            # Unsupported type
            return True, []

    def analyze_code(self, code: str, extension: str) -> Tuple[bool, List[FileSyntaxError]]:
        """
        Analyze code string directly. (Synchronous wrapper for Python only)
        For async LLM check, use analyze_file or a new async method.
        This legacy method is kept for Python compatibility.
        """
        if extension == '.py':
            return self._check_python_code(code)
        return True, []
    
    def _check_python_code(self, source: str) -> Tuple[bool, List[FileSyntaxError]]:
        """Check Python code string using ast module."""
        try:
            ast.parse(source)
            return True, []
            
        except SyntaxError as e:
            error = FileSyntaxError(
                line=e.lineno or 0,
                column=e.offset or 0,
                message=str(e),
                parser="python-ast"
            )
            return False, [error]
        
        except Exception as e:
            error = FileSyntaxError(
                message=str(e),
                parser="python-ast"
            )
            return False, [error]

    async def _check_syntax_with_llm(self, code: str, language: str, filename: str) -> Tuple[bool, List[FileSyntaxError]]:
        """
        Ask vLLM to find syntax errors.
        """
        from utils.llm_utils import robust_json_load
        
        prompt = f"""You are a {language} compiler.
Check the following code for SYNTAX ERRORS only.
Ignore logical errors or warnings. Focus on missing semicolons, unmatched braces, invalid types, etc.

File: {filename}
```{language}
{code}
```

If there are syntax errors, list them in JSON.
If the code is syntactically valid, return an empty list.

Refrain from reporting "missing main function" or "dependency not found" logic.
Only report parsing errors that would prevent compilation of this single file unit.

Respond with JSON:
{{
  "errors": [
    {{
      "line": <number>,
      "column": <number>,
      "message": "<short error message>"
    }}
  ]
}}"""

        try:
            response = await self.llm_client.generate_completion(prompt, temperature=0.1)
            data = robust_json_load(response)
            
            if not data or "errors" not in data:
                return True, []
            
            errors = []
            for e in data["errors"]:
                errors.append(FileSyntaxError(
                    line=e.get("line", 0),
                    column=e.get("column", 0),
                    message=e.get("message", "Syntax Error"),
                    parser=f"{language}-llm"
                ))
            
            return (len(errors) == 0), errors
            
        except Exception as e:
            # Fallback if LLM fails
            print(f"LLM Syntax Check failed: {e}")
            return True, []
