"""
Static Syntax Analyzer
Deterministic, compiler-grade syntax checking.
LLMs are NEVER used for syntax errors.
"""

import ast
from pathlib import Path
from typing import List, Optional

class SyntaxError:
    def __init__(self, line: int, column: int, message: str, parser: str):
        self.line = line
        self.column = column
        self.message = message
        self.parser = parser
        self.severity = "critical"
        self.type = "syntax_error"

class StaticSyntaxAnalyzer:
    """
    Uses language-native parsers for 100% accurate syntax checking.
    Currently supports Python with ast module.
    """
    
    def __init__(self):
        pass
    
    def analyze_file(self, file_path: Path) -> tuple[bool, List[SyntaxError]]:
        """
        Returns: (is_valid, errors)
        If is_valid is False, DO NOT proceed to LLM analysis.
        """
        ext = file_path.suffix
        
        if ext == '.py':
            return self._check_python(file_path)
        else:
            # For non-Python files, skip syntax check for now
            # User can add tree-sitter later or use Python 3.12
            return True, []
    
    def _check_python(self, file_path: Path) -> tuple[bool, List[SyntaxError]]:
        """Use Python's ast module for absolute accuracy."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            ast.parse(source, filename=str(file_path))
            return True, []
            
        except SyntaxError as e:
            error = SyntaxError(
                line=e.lineno or 0,
                column=e.offset or 0,
                message=e.msg,
                parser="python-ast"
            )
            return False, [error]
        except Exception as e:
            error = SyntaxError(
                line=0,
                column=0,
                message=f"Parse error: {str(e)}",
                parser="python-ast"
            )
            return False, [error]

