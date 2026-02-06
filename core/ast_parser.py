"""
Structural Parser
Extracts symbols (functions, classes) and call sites from source code.
"""

import ast
from pathlib import Path
from typing import List, Dict, Any

class StructuralParser:
    """Extracts structural information from source files using AST."""

    def __init__(self):
        # Pure Python parser - no initialization needed
        pass

    def parse_python(self, code: str, file_path: Path) -> Dict[str, Any]:
        """
        Parse Python code and extract functions, classes, and calls.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"functions": [], "classes": [], "imports": [], "calls": []}

        all_calls = []

        class Analyzer(ast.NodeVisitor):
            def __init__(self, source_code):
                self.source_code = source_code
                self.current_function = None
                self.current_class = None
                self.functions = []
                self.classes = []
                self.imports = []
                self.calls_in_current = []

            def visit_Import(self, node):
                names = [alias.name for alias in node.names]
                self.imports.append({"module": None, "names": names})
                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                names = [alias.name for alias in node.names]
                self.imports.append({"module": node.module, "names": names})
                self.generic_visit(node)

            def visit_ClassDef(self, node):
                prev_class = self.current_class
                self.current_class = node.name
                
                class_data = {
                    "name": node.name,
                    "line": node.lineno,
                    "methods": [],
                    "attributes": []
                }
                
                # Simple attribute detection (assignments in class body)
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                class_data["attributes"].append(target.id)
                
                self.classes.append(class_data)
                self.generic_visit(node)
                self.current_class = prev_class

            def visit_FunctionDef(self, node):
                prev_func = self.current_function
                prev_calls = self.calls_in_current
                
                self.current_function = node.name
                self.calls_in_current = []
                
                args = [arg.arg for arg in node.args.args]
                signature = f"{node.name}({', '.join(args)})"
                
                # Capture function body code
                try:
                    import ast as ast_mod # Use module level ast
                    body_code = ast_mod.get_source_segment(self.source_code, node)
                except:
                    body_code = ""

                self.generic_visit(node)
                
                func_data = {
                    "name": node.name,
                    "line": node.lineno,
                    "signature": signature,
                    "body_code": body_code,
                    "calls": self.calls_in_current,
                    "parent_class": self.current_class
                }
                self.functions.append(func_data)
                
                # Also add to class if within one
                if self.current_class:
                    for c in self.classes:
                        if c["name"] == self.current_class:
                            c["methods"].append(node.name)
                            break
                
                self.current_function = prev_func
                self.calls_in_current = prev_calls

            # Alias for async definitions
            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node):
                call_name = None
                if isinstance(node.func, ast.Name):
                    call_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    call_name = node.func.attr
                
                if call_name:
                    self.calls_in_current.append(call_name)
                    all_calls.append(call_name)
                
                self.generic_visit(node)

        analyzer = Analyzer(code)
        analyzer.visit(tree)
        
        return {
            "functions": analyzer.functions,
            "classes": analyzer.classes,
            "imports": analyzer.imports,
            "calls": all_calls
        }
