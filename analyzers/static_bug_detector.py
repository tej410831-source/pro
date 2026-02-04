"""
Static Bug Detector
Deterministic logic checks using AST traversal.
"""

import ast
from pathlib import Path
from typing import List, Dict

class StaticBugDetector:
    """Detects deterministic bugs in Python code without AI."""

    def analyze_file(self, file_path: Path) -> List[Dict]:
        """Analyze a Python file for static bugs."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            return self.analyze_code(code)
        except Exception as e:
            return [{"line": 0, "message": f"Static analysis failed: {e}"}]

    def analyze_code(self, code: str) -> List[Dict]:
        """Analyze Python code string for bugs."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return [] # Handled by Phase 2

        issues = []
        
        # 1. Undefined Variable Detection
        issues.extend(self._find_undefined_variables(tree))
        
        return issues

    def _find_undefined_variables(self, tree: ast.AST) -> List[Dict]:
        """Simple scope analysis for undefined variables."""
        undefined = []
        
        # Build set of defined names (using standard builtins)
        import builtins
        defined = set(dir(builtins))
        # Extra safety for core builtins that might be missed in some envs
        defined.update({'print', 'len', 'range', 'int', 'str', 'round', 'abs', 'min', 'max', 'sum', 'sorted', 'any', 'all'})
        
        class ScopeVisitor(ast.NodeVisitor):
            def __init__(self):
                self.scopes = [defined.copy()]
            
            def visit_FunctionDef(self, node):
                self.scopes[-1].add(node.name)
                # New scope for function
                new_scope = self.scopes[-1].copy()
                for arg in node.args.args:
                    new_scope.add(arg.arg)
                self.scopes.append(new_scope)
                self.generic_visit(node)
                self.scopes.pop()

            def visit_ClassDef(self, node):
                self.scopes[-1].add(node.name)
                # Classes have a scope but it works differently in Python
                # For simplicity, we'll just add the class name to current scope
                self.generic_visit(node)

            def visit_Assign(self, node):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.scopes[-1].add(target.id)
                self.generic_visit(node)

            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load):
                    # Check if name exists in any visible scope
                    is_defined = False
                    for scope in reversed(self.scopes):
                        if node.id in scope:
                            is_defined = True
                            break
                    
                    if not is_defined:
                        undefined.append({
                            "line": node.lineno,
                            "message": f"Undefined variable '{node.id}'"
                        })
                self.generic_visit(node)

            def visit_Import(self, node):
                for alias in node.names:
                    self.scopes[-1].add(alias.name if not alias.asname else alias.asname)
                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                for alias in node.names:
                    self.scopes[-1].add(alias.name if not alias.asname else alias.asname)
                self.generic_visit(node)

        visitor = ScopeVisitor()
        visitor.visit(tree)
        return undefined
