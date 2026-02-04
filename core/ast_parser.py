"""
Structural Parser
Extracts symbols (functions, classes) and call sites from source code.
"""

import ast
from pathlib import Path
from typing import List, Dict, Any

class StructuralParser:
    """Extracts structural information from source files using AST and tree-sitter."""

    def __init__(self):
        self.tree_sitter_available = False
        self.parsers = {}
        self._init_tree_sitter()

    def _init_tree_sitter(self):
        """Initialize tree-sitter parsers for Java, C, and C++."""
        try:
            from tree_sitter_languages import get_parser
            for ext, lang_name in [('.java', 'java'), ('.cpp', 'cpp'), ('.c', 'c'), ('.h', 'cpp')]:
                try:
                    self.parsers[ext] = get_parser(lang_name)
                except:
                    pass
            if self.parsers:
                self.tree_sitter_available = True
        except ImportError:
            self.tree_sitter_available = False

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

    def parse_tree_sitter(self, code: str, file_path: Path) -> Dict[str, Any]:
        """Parse Java/C/C++ using tree-sitter."""
        ext = file_path.suffix
        parser = self.parsers.get(ext)
        if not parser or not self.tree_sitter_available:
            return {"functions": [], "classes": [], "imports": [], "calls": []}

        tree = parser.parse(bytes(code, "utf8"))
        root = tree.root_node

        functions = []
        classes = []
        calls = []
        
        # Track current function for call mapping
        self._current_calls = []

        def traverse(node):
            node_type = node.type
            
            # Identify Functions/Methods
            if node_type in ("method_declaration", "function_definition"):
                name_node = node.child_by_field_name("name") or node.child_by_field_name("declarator")
                if name_node:
                    # Deep extraction for C declarators
                    while name_node.child_by_field_name("declarator"):
                        name_node = name_node.child_by_field_name("declarator")
                    
                    name = code[name_node.start_byte:name_node.end_byte]
                    
                    prev_calls = self._current_calls
                    self._current_calls = []
                    
                    for child in node.children:
                        traverse(child)
                    
                    functions.append({
                        "name": name,
                        "line": node.start_point[0] + 1,
                        "signature": f"{name}(...)",
                        "calls": self._current_calls
                    })
                    self._current_calls = prev_calls
                    return # Already recursed

            # Identify Classes
            elif node_type in ("class_declaration", "class_specifier", "struct_specifier"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte]
                    classes.append({
                        "name": name,
                        "line": node.start_point[0] + 1
                    })

            # Identify Calls
            elif node_type in ("method_invocation", "call_expression"):
                name_node = node.child_by_field_name("name") or node.child_by_field_name("function")
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte]
                    # Handle method calls obj.func()
                    if "." in name:
                        name = name.split(".")[-1]
                    if "->" in name:
                        name = name.split("->")[-1]
                        
                    self._current_calls.append(name)
                    calls.append(name)

            for child in node.children:
                traverse(child)

        traverse(root)
        return {
            "functions": functions,
            "classes": classes,
            "imports": [], # Import extraction is more complex in C/Java
            "calls": calls
        }
