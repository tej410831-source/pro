from typing import List, Dict, Set, Any
from pathlib import Path
from rich.console import Console
import tree_sitter_languages
from tree_sitter import Language, Parser

console = Console()

class DeadCodeDetector:
    def __init__(self):
        self.parsers = {}
        self.languages = {}
        
        # Consistent with ast_parser.py
        for lang_id in ['python', 'c', 'cpp', 'java']:
            try:
                lang = tree_sitter_languages.get_language(lang_id)
                parser = tree_sitter_languages.get_parser(lang_id)
                self.languages[lang_id] = lang
                self.parsers[lang_id] = parser
            except Exception as e:
                # console.print(f"[yellow]Warning: Could not load parser for {lang_id}: {e}[/yellow]")
                pass

    def analyze_unused_functions(self, symbol_table: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        Identify functions that are defined but never called across the codebase.
        Returns a dict grouped by file: {file_path: [{name, line, type}, ...]}
        """
        defined_funcs = {} # name -> {file, line, ...}
        called_funcs = set()
        
        # 1. Collect definitions and calls
        for file_path, file_data in symbol_table.items():
            for func in file_data.get("functions", []):
                name = func["name"]
                # Store definition (handle duplicates by keeping list?)
                defined_funcs[name] = {
                    "file": file_path,
                    "line": func["line"],
                    "name": name
                }
                
                # Collect calls made BY this function
                for call in func.get("calls", []):
                    called_funcs.add(call)

        # 2. Find difference
        unused_report = {}
        
        # Common entry points to ignore
        ignored_names = {'main', '__init__', 'setup', 'loop', 'run', 'test', 'setUp', 'tearDown'}
        
        for name, info in defined_funcs.items():
            if name not in called_funcs and name not in ignored_names and not name.startswith("test_"):
                fpath = info["file"]
                if fpath not in unused_report:
                    unused_report[fpath] = []
                unused_report[fpath].append({
                    "name": name,
                    "line": info["line"],
                    "type": "Unused Function"
                })
        
        return unused_report

    def analyze_unused_variables(self, symbol_table: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        Analyze function bodies to find identifiers that are declared but not used.
        Returns dict grouped by file.
        """
        unused_vars_report = {}
        
        # We need language mappings
        lang_map = {'.py': 'python', '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.hpp': 'cpp', '.java': 'java'}
        
        for file_path, file_data in symbol_table.items():
            ext = Path(file_path).suffix
            lang_id = lang_map.get(ext)
            
            if not lang_id or lang_id not in self.parsers:
                continue
                
            parser = self.parsers[lang_id]
            language = self.languages[lang_id]
            
            # Iterate functions to check local scope
            for func in file_data.get("functions", []):
                body = func.get("body_code", "")
                if not body: continue
                
                try:
                    tree = parser.parse(bytes(body, "utf8"))
                    root = tree.root_node
                    
                    # 1. Collect Valid Identifiers (exclude comments/strings)
                    identifiers = []
                    
                    def walk(node):
                        if node.type == 'identifier':
                            identifiers.append(node.text.decode('utf8'))
                        for child in node.children:
                            walk(child)
                    
                    walk(root)
                    
                    from collections import Counter
                    counts = Counter(identifiers)
                    
                    # Finding declarations:
                    declarations = set()
                    
                    def find_decls(node):
                        # Python: assignment left side
                        if lang_id == 'python':
                            if node.type == 'assignment':
                                left = node.child_by_field_name('left')
                                if left and left.type == 'identifier':
                                    declarations.add(left.text.decode('utf8'))
                        for child in node.children:
                            find_decls(child)
                            
                    # Better Approach for C/Java: 
                    # Use queries for precise declaration extraction
                    if lang_id in ['c', 'cpp', 'java']:
                        query = None
                        if lang_id == 'c':
                            query_str = "(declaration declarator: (identifier) @decl)"
                            try: query = language.query(query_str)
                            except: pass
                        elif lang_id == 'cpp':
                             query_str = "(declaration declarator: (identifier) @decl)"
                             try: query = language.query(query_str)
                             except: pass
                        elif lang_id == 'java':
                             # Java simpler query
                             query_str = "(variable_declarator name: (identifier) @decl)"
                             try: query = language.query(query_str)
                             except: pass
                        
                        if query:
                            captures = query.captures(root)
                            for node, _ in captures:
                                declarations.add(node.text.decode('utf8'))

                    elif lang_id == 'python':
                        # Simple tree walk for assignments as fallback 
                        # Or use query:
                        try:
                            q = language.query("(assignment left: (identifier) @decl)")
                            captures = q.captures(root)
                            for node, _ in captures:
                                declarations.add(node.text.decode('utf8'))
                        except:
                            find_decls(root)
                    
                    # 3. Check Counts
                    for decl in declarations:
                        # Ignore common ignored vars
                        if decl == '_' or decl.startswith("unused"): continue
                        
                        if counts[decl] == 1:
                            if file_path not in unused_vars_report:
                                unused_vars_report[file_path] = []
                            
                            unused_vars_report[file_path].append({
                                "name": decl,
                                "line": func["line"], 
                                "scope": func["name"],
                                "type": "Unused Local Variable"
                            })

                except Exception as e:
                    # console.print(f"Error parsing {func['name']}: {e}")
                    pass
        
        return unused_vars_report
