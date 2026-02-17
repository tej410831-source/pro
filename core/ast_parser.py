"""
Structural Parser
Extracts symbols (functions, classes) and call sites from source code.
Uses native AST for Python and Tree-sitter for C, C++, and Java.
"""

import ast
from pathlib import Path
from typing import List, Dict, Any, Optional
import tree_sitter_languages
from tree_sitter import Parser, Language, Query

class StructuralParser:
    """Extracts structural information from source files using AST or Tree-sitter."""

    def __init__(self):
        self.parsers = {}
        self.languages = {}
        self.queries = {}
        self.queries_usage = {}
        
        # Initialize Tree-sitter for non-Python languages
        for lang_id in ['c', 'cpp', 'java']:
            try:
                lang = tree_sitter_languages.get_language(lang_id)
                parser = tree_sitter_languages.get_parser(lang_id)
                self.languages[lang_id] = lang
                self.parsers[lang_id] = parser
                
                # Pre-compile queries for performance
                if lang_id == 'c':
                    # Simplified C query
                    query_str = """
                    (function_definition) @func
                    (declaration) @var
                    """
                elif lang_id == 'cpp':
                    query_str = """
                    (function_definition) @func
                    
                    (class_specifier
                      name: (type_identifier) @name
                    ) @class
                    
                    (declaration) @var
                    (field_declaration) @var
                    """
                elif lang_id == 'java':
                    query_str = """
                    (method_declaration
                      name: (identifier) @name
                      parameters: (formal_parameters) @params
                    ) @func
                    
                    (class_declaration
                      name: (identifier) @name
                    ) @class
                    
                    (declaration) @var
                    (field_declaration) @var
                    """
                
                self.queries[lang_id] = lang.query(query_str)
                self.queries[lang_id] = lang.query(query_str)
                
                if lang_id == 'java':
                    # Java uses 'identifier' or 'type_identifier'
                    self.queries_usage[lang_id] = lang.query("""
                    (identifier) @id
                    (type_identifier) @id
                    """)
                else:
                    # C/C++ usage
                    self.queries_usage[lang_id] = lang.query("""
                    (identifier) @id
                    (type_identifier) @id
                    (field_identifier) @id
                    """)
            except Exception as e:
                print(f"Warning: Failed to initialize Tree-sitter for {lang_id}: {e}")

    def parse(self, code: str, file_path: Path) -> Dict[str, Any]:
        """Unified entry point for parsing any supported file."""
        ext = file_path.suffix.lower()
        if ext == '.py':
            return self._parse_python_ast(code, file_path)
        
        lang_map = {
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.h': 'c', # Headers can be C or CPP, default to C for simple extract
            '.hpp': 'cpp',
            '.java': 'java'
        }
        
        lang_id = lang_map.get(ext)
        if lang_id and lang_id in self.parsers:
            return self._parse_with_treesitter(code, lang_id)
        
        return {"functions": [], "classes": [], "imports": [], "calls": []}

    def _parse_python_ast(self, code: str, file_path: Path) -> Dict[str, Any]:
        """Parse Python code using native AST module."""
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
                self.calls_in_current = []
                self.identifiers = []
                self.variables = []

            def visit_Name(self, node):
                if isinstance(node, ast.Name):
                    self.identifiers.append(node.id)
                self.generic_visit(node)

            def visit_Assign(self, node):
                # Only capture top-level variables (not inside function/class)
                if self.current_function is None and self.current_class is None:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.variables.append({"name": target.id, "line": node.lineno})
                self.generic_visit(node)

            def visit_AnnAssign(self, node):
                 # Only capture top-level variables
                if self.current_function is None and self.current_class is None:
                    if isinstance(node.target, ast.Name):
                        self.variables.append({"name": node.target.id, "line": node.lineno})
                self.generic_visit(node)

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
                
                try:
                    body_code = ast.get_source_segment(self.source_code, node)
                except:
                    body_code = ""

                self.generic_visit(node)
                
                func_data = {
                    "name": node.name,
                    "line": node.lineno,
                    "signature": signature,
                    "body_code": body_code or "",
                    "calls": self.calls_in_current,
                    "parent_class": self.current_class
                }
                self.functions.append(func_data)
                
                if self.current_class:
                    for c in self.classes:
                        if c["name"] == self.current_class:
                            c["methods"].append(node.name)
                            break
                
                self.current_function = prev_func
                self.calls_in_current = prev_calls

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
            "calls": all_calls,
            "identifiers": analyzer.identifiers,
            "variables": analyzer.variables
        }

    def _parse_with_treesitter(self, code: str, lang_id: str) -> Dict[str, Any]:
        """Extract functions and classes using Tree-sitter queries."""
        parser = self.parsers[lang_id]
        query = self.queries.get(lang_id)
        usage_query = self.queries_usage.get(lang_id)
        
        # Helper to find nodes by field or type
        def find_child_by_type(n, t):
            for c in n.children:
                if c.type == t: return c
            return None

        try:
            tree = parser.parse(bytes(code, "utf8"))
            root = tree.root_node
        except Exception as e:
            print(f"Error parsing with Tree-sitter ({lang_id}): {e}")
            return {"functions": [], "classes": [], "imports": [], "calls": [], "identifiers": [], "global_vars": []}

        results = {
            "functions": [],
            "classes": [],
            "imports": [],
            "calls": [],
            "identifiers": [],
            "global_vars": []
        }

        if not query:
            return results

        captures = query.captures(root)
        
        # We need to track which node belongs to which class
        # (Simplified: functions/methods following a class but before next class)
        current_class = None

        for node, tag in captures:
            if tag == 'class':
                current_class = node.child_by_field_name('name').text.decode('utf8')
                results["classes"].append({
                    "name": current_class,
                    "line": node.start_point[0] + 1,
                    "methods": [],
                    "attributes": []
                })
            
            elif tag == 'func':
                # Helper to recursive find name
                def get_symbol_name(n):
                    if n.type in ['identifier', 'type_identifier', 'field_identifier', 'destructor_name']:
                        return n.text.decode('utf8')
                    # Prefer field_identifier for methods if available
                    field = n.child_by_field_name('name') or n.child_by_field_name('declarator')
                    if field:
                        res = get_symbol_name(field)
                        if res: return res
                        
                    # Scoped identifiers (A::B)
                    if n.type == 'scoped_identifier':
                        return n.text.decode('utf8')
                    for c in n.children:
                        res = get_symbol_name(c)
                        if res: return res
                    return None

                # Favor direct field 'name' if parser provided it
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = name_node.text.decode('utf8')
                else:
                    name = get_symbol_name(node) or "unknown"
                
                
                # Signature extraction — include return type
                return_type = ""
                sig_parts = []
                for child in node.children:
                    # Return type (comes before the function name/declarator)
                    if child.type in ['primitive_type', 'type_identifier', 'sized_type_specifier',
                                      'template_type', 'scoped_type_identifier', 'auto']:
                        return_type = child.text.decode('utf8')
                    elif child.type == 'type':  # Java return type wrapper
                        return_type = child.text.decode('utf8')
                    elif child.type in ['formal_parameters', 'parameter_list', 'function_declarator']:
                        # For function_declarator, we want its params
                        params = find_child_by_type(child, 'parameter_list') or find_child_by_type(child, 'formal_parameters')
                        if params:
                            sig_parts.append(params.text.decode('utf8'))
                            break
                
                params_str = sig_parts[0] if sig_parts else '()'
                signature = f"{return_type + ' ' if return_type else ''}{name}{params_str}"
                
                results["functions"].append({
                    "name": name,
                    "line": node.start_point[0] + 1,
                    "signature": signature,
                    "body_code": code[node.start_byte:node.end_byte],
                    "calls": [],
                    "parent_class": current_class
                })
                
                if current_class:
                    results["classes"][-1]["methods"].append(name)

        # ── Tree-sitter: Extract imports, globals, and call sites ──
        
        # 1. Walk root children for imports and global declarations
        for child in root.children:
            # Imports / includes
            if child.type == 'preproc_include':  # C/C++ #include
                results["imports"].append({
                    "module": child.text.decode('utf8').strip(),
                    "names": []
                })
            elif child.type == 'import_declaration':  # Java import
                results["imports"].append({
                    "module": child.text.decode('utf8').strip(),
                    "names": []
                })
            elif child.type == 'using_declaration':  # C++ using
                results["imports"].append({
                    "module": child.text.decode('utf8').strip(),
                    "names": []
                })
            elif child.type == 'package_declaration':  # Java package
                results["imports"].append({
                    "module": child.text.decode('utf8').strip(),
                    "names": []
                })
            
            # Global declarations (#define, top-level variables)
            elif child.type == 'preproc_def':  # #define
                if "global_vars" not in results:
                    results["global_vars"] = []
                results["global_vars"].append(child.text.decode('utf8').strip())
            elif child.type == 'declaration' and child.parent == root:  # top-level var/const
                if "global_vars" not in results:
                    results["global_vars"] = []
                results["global_vars"].append(child.text.decode('utf8').strip())
        
        # 2. Extract call sites from each function body
        def extract_calls(node):
            """Recursively find call_expression nodes."""
            calls = []
            if node.type == 'call_expression':
                func_node = node.child_by_field_name('function')
                if func_node:
                    call_name = func_node.text.decode('utf8')
                    # Simplify: take last part of dotted names (e.g. System.out.println -> println)
                    if '.' in call_name:
                        call_name = call_name.split('.')[-1]
                    if '::' in call_name:
                        call_name = call_name.split('::')[-1]
                    calls.append(call_name)
            elif node.type == 'method_invocation': # Java specific
                name_node = node.child_by_field_name('name')
                if name_node:
                    calls.append(name_node.text.decode('utf8'))
            for child in node.children:
                calls.extend(extract_calls(child))
            return calls
        
        for func in results["functions"]:
            # Re-parse the function body to find call sites
            func_line = func["line"] - 1  # 0-indexed
            for node, tag in captures:
                if tag == 'func' and node.start_point[0] == func_line:
                    func["calls"] = extract_calls(node)
                    break

        if usage_query:
            captures_usage = usage_query.captures(root)
            for node, tag in captures_usage:
                if tag == 'id':
                    try:
                        name = node.text.decode('utf8')
                        results["identifiers"].append(name)
                    except: pass

        return results
