"""
Static Syntax Analyzer (Python Only)
Deterministic, compiler-grade syntax checking using Python's native AST.
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
    """Analyze Python source files for syntax errors using native AST."""
    
    def __init__(self):
        # No external parsers needed for Python
        pass
    
    def analyze_file(self, file_path: Path) -> Tuple[bool, List[FileSyntaxError]]:
        """
        Analyze a python file for syntax errors.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (is_valid, errors_list)
        """
        if file_path.suffix != '.py':
            # Skip non-python files silently or return valid
            return True, []
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            return self._check_python_code(source)
        except Exception as e:
            error = FileSyntaxError(
                message=f"Failed to read file: {str(e)}",
                parser="python-io"
            )
            return False, [error]
    
    def analyze_code(self, code: str, extension: str) -> Tuple[bool, List[FileSyntaxError]]:
        """
        Analyze code string directly.
        """
        if extension != '.py':
            return True, []
        return self._check_python_code(code)
    
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
