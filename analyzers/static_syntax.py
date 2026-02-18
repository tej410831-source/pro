"""
Static Syntax Analyzer
Deterministic syntax checking:
  - Python: native ast.parse()
  - C/C++/Java: Tree-sitter ERROR node detection
"""

import ast
from pathlib import Path
from typing import List, Tuple

try:
    import tree_sitter_languages
    from tree_sitter import Parser
    TREESITTER_AVAILABLE = True
except ImportError:
    TREESITTER_AVAILABLE = False

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
    """Analyze source files for syntax errors using native AST (Python) or Tree-sitter (C/C++/Java)."""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.lang_map = {
            '.py': 'python',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.h': 'cpp',
            '.hpp': 'cpp',
            '.java': 'java'
        }
        
        # Initialize Tree-sitter parsers for C/C++/Java
        self.ts_parsers = {}
        if TREESITTER_AVAILABLE:
            for lang_id in ['c', 'cpp', 'java']:
                try:
                    parser = tree_sitter_languages.get_parser(lang_id)
                    self.ts_parsers[lang_id] = parser
                except Exception as e:
                    print(f"[WARNING] Failed to load tree-sitter parser for {lang_id}: {e}")
                    # Likely incompatibility between tree-sitter and tree-sitter-languages
                    pass
        else:
            print("[DEBUG] Tree-sitter NOT available (ImportError)")
    
    def analyze_file(self, file_path: Path) -> Tuple[bool, List[FileSyntaxError]]:
        """
        Analyze a file for syntax errors.
        Now fully synchronous — no LLM calls needed for detection.
        """
        if not file_path.exists():
             return False, [FileSyntaxError(f"File not found: {file_path}", "os-error")]

        ext = file_path.suffix.lower()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
        except Exception as e:
            return False, [FileSyntaxError(f"Read error: {str(e)}", "io-error")]
        
        if ext == '.py':
            return self._check_python_code(source)
        
        elif ext in self.lang_map:
            language = self.lang_map[ext]
            if language in self.ts_parsers:
                return self._check_treesitter_syntax(source, language)
            else:
                # Tree-sitter not available for this language
                return True, []
        
        else:
            return True, []

    def analyze_code(self, code: str, extension: str) -> Tuple[bool, List[FileSyntaxError]]:
        """
        Analyze code string directly (synchronous).
        """
        if extension == '.py':
            return self._check_python_code(code)
        
        lang = self.lang_map.get(extension)
        if lang and lang in self.ts_parsers:
            return self._check_treesitter_syntax(code, lang)
        
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

    def _check_treesitter_syntax(self, source: str, language: str) -> Tuple[bool, List[FileSyntaxError]]:
        """
        Check C/C++/Java code using Tree-sitter.
        Walks the parse tree for ERROR and MISSING nodes.
        Deduplicates nested errors (if parent is ERROR, skip children).
        """
        parser = self.ts_parsers[language]
        tree = parser.parse(bytes(source, 'utf-8'))
        
        source_lines = source.splitlines()
        errors = []
        
        def walk(node, parent_is_error=False):
            is_error = node.type == 'ERROR'
            is_missing = getattr(node, 'is_missing', False) 
            
            if (is_error or is_missing) and not parent_is_error:
                line = node.start_point[0] + 1
                col = node.start_point[1] + 1
                col = node.start_point[1] + 1
                end_line = node.end_point[0] + 1
                
                # Build a descriptive error message
                if is_missing:
                    msg = f"Missing expected token: '{node.type}'"
                else:
                    # Get the problematic text (truncated)
                    try:
                        text = node.text.decode('utf-8', errors='replace')[:50]
                        if len(text) > 40:
                            text = text[:40] + "..."
                    except:
                        text = ""
                    
                    # Get the source line for context
                    if 0 < line <= len(source_lines):
                        src_line = source_lines[line - 1].strip()
                        msg = f"Syntax error near: '{src_line[:60]}'"
                    elif text:
                        msg = f"Unexpected syntax: '{text}'"
                    else:
                        msg = "Syntax error"
                
                errors.append(FileSyntaxError(
                    message=msg,
                    parser=f"{language}-treesitter",
                    line=line,
                    column=col
                ))
            
            # Walk children — skip children of ERROR nodes to avoid duplicates
            for child in node.children:
                walk(child, parent_is_error=(is_error or parent_is_error))
        
        walk(tree.root_node)
        return (len(errors) == 0), errors

