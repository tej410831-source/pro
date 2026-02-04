"""
Static Syntax Analyzer
Deterministic, compiler-grade syntax checking.
LLMs are NEVER used for syntax errors.
"""

import ast
from pathlib import Path
from typing import List, Optional, Tuple

class FileSyntaxError:
    def __init__(self, message: str = "", parser: str = "unknown", line: int = 0, column: int = 0):
        self.line = line
        self.column = column
        self.message = message
        self.parser = parser
    
    # Class attributes moved inside or ensured they are valid
    type: str = "syntax_error"
    severity: str = "critical"

class StaticSyntaxAnalyzer:
    """Analyze source files for syntax errors using native parsers."""
    
    def __init__(self):
        self.tree_sitter_available = False
        self.parsers = {}
        self._init_tree_sitter()
    
    def _init_tree_sitter(self):
        """Initialize tree-sitter parsers for Java, C, and C++."""
        try:
            from tree_sitter import Language, Parser
            from tree_sitter_languages import get_language, get_parser
            
            # Initialize parsers for Java, C++, C, and header files
            # We do this one by one to catch specific failures
            self.parsers = {}
            for ext, lang_name in [('.java', 'java'), ('.cpp', 'cpp'), ('.c', 'c'), ('.h', 'cpp')]:
                try:
                    self.parsers[ext] = get_parser(lang_name)
                except Exception as e:
                    print(f"Warning: Failed to load tree-sitter parser for {lang_name}: {e}")
            
            if self.parsers:
                self.tree_sitter_available = True
            
        except (ImportError, Exception) as e:
            # tree-sitter not installed or version conflict
            print(f"Warning: tree-sitter initialization failed, falling back to Python only. Error: {e}")
            self.tree_sitter_available = False
            self.parsers = {}
    
    def analyze_file(self, file_path: Path) -> Tuple[bool, List[FileSyntaxError]]:
        """
        Analyze a file for syntax errors.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (is_valid, errors_list)
        """
        ext = file_path.suffix
        
        if ext == '.py':
            return self._check_python(file_path)
        elif ext in self.parsers and self.tree_sitter_available:
            return self._check_tree_sitter(file_path, ext)
        else:
            # Unsupported language, treat as valid
            return True, []
    
    def analyze_code(self, code: str, extension: str) -> Tuple[bool, List[FileSyntaxError]]:
        """
        Analyze code string directly (for validating fixes).
        
        Args:
            code: Source code as string
            extension: File extension (.py, .js, etc.)
            
        Returns:
            Tuple of (is_valid, errors_list)
        """
        if extension == '.py':
            return self._check_python_code(code)
        elif extension in self.parsers and self.tree_sitter_available:
            return self._check_tree_sitter_code(code, extension)
        else:
            return True, []
    
    def _check_python(self, file_path: Path) -> Tuple[bool, List[FileSyntaxError]]:
        """Check Python file using ast module."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            return self._check_python_code(source)
        except Exception as e:
            error = FileSyntaxError(
                message=f"Failed to read file: {str(e)}",
                parser="python-ast"
            )
            return False, [error]
    
    def _check_python_code(self, source: str) -> Tuple[bool, List[FileSyntaxError]]:
        """Check Python code string."""
        try:
            ast.parse(source)
            return True, []
            
        except SyntaxError as e:
            error = FileSyntaxError(
                line=e.lineno or 0,
                column=e.offset or 0,
                message=e.msg,
                parser="python-ast"
            )
            return False, [error]
        
        except Exception as e:
            error = FileSyntaxError(
                message=str(e),
                parser="python-ast"
            )
            return False, [error]
    
    def _check_tree_sitter(self, file_path: Path, extension: str) -> Tuple[bool, List[FileSyntaxError]]:
        """Check file using tree-sitter."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            return self._check_tree_sitter_code(source, extension)
        except Exception as e:
            error = FileSyntaxError(
                message=f"Failed to read file: {str(e)}",
                parser="tree-sitter"
            )
            return False, [error]
    
    def _check_tree_sitter_code(self, source: str, extension: str) -> Tuple[bool, List[FileSyntaxError]]:
        """Check code using tree-sitter parser."""
        try:
            parser = self.parsers.get(extension)
            if not parser:
                return True, []
            
            # Parse the code
            tree = parser.parse(bytes(source, "utf8"))
            
            # Check for syntax errors
            errors = []
            if tree.root_node.has_error:
                # Find error nodes
                errors = self._find_tree_sitter_errors(tree.root_node, source)
            
            return len(errors) == 0, errors
            
        except Exception as e:
            error = FileSyntaxError(
                message=str(e),
                parser=f"tree-sitter-{extension}"
            )
            return False, [error]
    
    def _find_tree_sitter_errors(self, node, source: str) -> List[FileSyntaxError]:
        """Recursively find error nodes in tree-sitter parse tree."""
        errors = []
        
        if node.type == "ERROR":
            line = node.start_point[0] + 1  # 1-indexed
            column = node.start_point[1]
            
            # Get error context
            lines = source.split('\n')
            error_line = lines[line - 1] if line <= len(lines) else ""
            
            errors.append(FileSyntaxError(
                line=line,
                column=column,
                message=f"Syntax error near: {error_line[:50]}",
                parser="tree-sitter"
            ))
        
        # Recurse through children
        for child in node.children:
            errors.extend(self._find_tree_sitter_errors(child, source))
        
        return errors
