import networkx as nx
from pathlib import Path
from typing import List, Dict, Any, Set
from core.symbol_table import SymbolTableBuilder, Symbol as STSymbol, SymbolType as STSymbolType
from core.ast_parser import StructuralParser

class StructuralAnalyzer:
    """
    Main analyzer that coordinates parsing and structural analysis:
    - Cross-file Symbol Table (Definitions)
    - Global Usage Tracking (References)
    - Call Graph (Function cycles)
    - Dependency Graph (Import cycles)
    """
    
    def __init__(self):
        self.parser = StructuralParser()
        self.symbol_table = SymbolTableBuilder()
        self.call_graph = nx.DiGraph()
        self.dependency_graph = nx.DiGraph()
        self.file_data_map = {} # path -> parser output

    def analyze_codebase(self, files: List[Path]) -> Dict[str, Any]:
        """Run full structural analysis on a list of files."""
        print(f"Analysing {len(files)} files structurally...")
        
        all_identifiers_global = [] 
        
        # 1. Parse all files and collect definitions
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                ext = file_path.suffix.lower()
                lang = "python" if ext == ".py" else ("java" if ext == ".java" else "c/cpp")
                
                data = self.parser.parse(code, file_path)
                self.file_data_map[str(file_path)] = data
                module_name = file_path.stem
                
                # Extract symbols and populate SymbolTableBuilder
                for func in data.get("functions", []):
                    sym = STSymbol(
                        name=func["name"],
                        symbol_type=STSymbolType.FUNCTION,
                        file_path=file_path,
                        line=func["line"],
                        signature=func.get("signature", ""),
                        body_code=func.get("body_code", ""),
                        parent_name=func.get("parent_class", "")
                    )
                    self.symbol_table.add_symbol(sym, module_name)
                    # Register nodes in call graph
                    self.call_graph.add_node(sym.qualified_name)
                    
                for cls in data.get("classes", []):
                    sym = STSymbol(
                        name=cls["name"],
                        symbol_type=STSymbolType.CLASS,
                        file_path=file_path,
                        line=cls["line"],
                        signature=f"class {cls['name']}"
                    )
                    self.symbol_table.add_symbol(sym, module_name)
                
                for var in data.get("variables", []):
                    # We don't have a special type for globals in STSymbolType, use VARIABLE
                    sym = STSymbol(
                        name=var["name"],
                        symbol_type=STSymbolType.VARIABLE, # Assuming it exists in core.symbol_table
                        file_path=file_path,
                        line=var["line"],
                        signature=var["name"]
                    )
                    self.symbol_table.add_symbol(sym, module_name)

                # Track usage identifiers for cross-file variable analysis
                for id_name in data.get("identifiers", []):
                    all_identifiers_global.append(id_name)
                
                # Track imports for dependency graph
                for imp in data.get("imports", []):
                    module_name_imp = imp.get("module") or (imp["names"][0] if imp.get("names") else "")
                    if module_name_imp:
                        self.dependency_graph.add_edge(file_path.name, module_name_imp)

            except Exception as e:
                print(f"Error parsing {file_path}: {e}")

    def _build_import_graph(self) -> Dict[str, Set[str]]:
        """Map file paths to the modules/files they import."""
        graph = {} # {str(file_path): set(imported_names)}
        
        for file_path, data in self.raw_data.items():
            imports = set()
            for imp in data.get("imports", []):
                # Handle 'from x import y' and 'import x'
                if imp["module"]:
                    imports.add(imp["module"])
                for name in imp["names"]:
                    if not imp["module"]:
                        imports.add(name)
            graph[file_path] = imports
            
        return graph

    def _collect_definitions(self) -> Dict[str, Dict]:
        """Aggregate all function/class definitions."""
        defs = {} 
        for file_path, data in self.raw_data.items():
            fname = Path(file_path).name
            defs[file_path] = {
                "functions": [f["name"] for f in data["functions"]],
                "classes": [c["name"] for c in data["classes"]]
            }
        return defs

    def _detect_cycles(self, graph: Dict[str, Set[str]]) -> List[List[str]]:
        """Find circular import dependencies."""
        cycles = []
        # Simplified DFS for cycles
        def find_path(current, visited, path):
            visited.add(current)
            path.append(current)
            
            # Approximate mapping: imports are module names, keys are file paths
            # We need to map module names back to file paths or check strictly by name
            # This is hard without full module resolution. 
            # For now, we cycle check simplistic "names" if plausible?
            # actually, let's skip complex mapping:
            # If we see import 'utils', and we scanned 'utils.py', we assume link.
            
            imps = graph.get(current, set())
            
            # Simple heuristic mapping for this project structure
            # If imported name appears in a scanned file path
            targets = []
            for imp in imps:
                # Find matching file in graph keys
                for fpath in graph.keys():
                    if imp in fpath or (imp + ".py") in fpath:
                         targets.append(fpath)
            
            for neighbor in targets:
                if neighbor in path:
                    # Found cycle
                    cycle_slice = path[path.index(neighbor):] + [neighbor]
                    # Format nicely
                    clean_cycle = [Path(p).name for p in cycle_slice]
                    if clean_cycle not in cycles:
                        cycles.append(clean_cycle)
                elif neighbor not in visited:
                    find_path(neighbor, visited, path)
            
            path.pop()
            visited.remove(current)

        # check all nodes
        # Optimization: only check if unvisited? Cycle detection usually needs full DFS
        # But for limited set ok.
        
        # Only run on subset to avoid massive recursion in huge repos
        # We limit to finding first few cycles
        try:
            for node in list(graph.keys()):
                find_path(node, set(), [])
                if len(cycles) > 5: break
        except RecursionError:
            pass
            
        return cycles

    def _detect_function_cycles(self, symbol_builder: SymbolTableBuilder) -> List[List[Symbol]]:
        """
        Find circular function dependencies (recursion/mutual recursion).
        Uses dependency-based call resolution instead of name-based matching.
        """
        # Build class hierarchy: class_name -> [base_class_names]
        class_bases = {}  # class_name -> list of base class names
        class_methods = {}  # class_name -> {method_name: Symbol}
        
        for data in self.raw_data.values():
            for cls in data.get("classes", []):
                class_bases[cls["name"]] = cls.get("bases", [])
                class_methods[cls["name"]] = {}
        
        # Populate class_methods from symbols
        for qname, sym in symbol_builder.symbols.items():
            if sym.type == SymbolType.FUNCTION and sym.parent_name:
                if sym.parent_name not in class_methods:
                    class_methods[sym.parent_name] = {}
                class_methods[sym.parent_name][sym.name] = sym
        
        # Build standalone functions map: (file, name) -> Symbol
        standalone_map = {}
        for qname, sym in symbol_builder.symbols.items():
            if sym.type == SymbolType.FUNCTION and not sym.parent_name:
                key = (str(sym.file), sym.name)
                standalone_map[key] = sym
        
        def resolve_call(call_info, caller_sym):
            """Resolve a call to its target Symbol(s) based on receiver context."""
            call_name = call_info["name"]
            receiver = call_info.get("receiver")
            
            if receiver == "self":
                # self.method() -> method in the same class
                if caller_sym.parent_name and caller_sym.parent_name in class_methods:
                    target = class_methods[caller_sym.parent_name].get(call_name)
                    return [target] if target else []
            
            elif receiver == "super":
                # super().method() -> method in parent class
                if caller_sym.parent_name and caller_sym.parent_name in class_bases:
                    for base_name in class_bases[caller_sym.parent_name]:
                        if base_name in class_methods:
                            target = class_methods[base_name].get(call_name)
                            if target:
                                return [target]
                return []
            
            elif receiver is not None:
                # ClassName.method() -> method in that specific class
                if receiver in class_methods:
                    target = class_methods[receiver].get(call_name)
                    return [target] if target else []
                return []
            
            else:
                # Bare call: foo() -> same-file standalone function first
                key = (str(caller_sym.file), call_name)
                target = standalone_map.get(key)
                if target:
                    return [target]
                # Fallback: any standalone function with that name (cross-file)
                results = []
                for (fpath, name), sym in standalone_map.items():
                    if name == call_name:
                        results.append(sym)
                return results
        
        # Build graph: Symbol -> [Symbol]
        graph = {}
        for qname, sym in symbol_builder.symbols.items():
            if sym.type != SymbolType.FUNCTION:
                continue
            
            graph[sym] = []
            
            file_data = self.raw_data.get(str(sym.file))
            if not file_data:
                continue
            
            func_data = next(
                (f for f in file_data["functions"]
                 if f["name"] == sym.name and f["line"] == sym.line),
                None
            )
            if not func_data:
                continue
            
            for call_info in func_data.get("calls_detailed", []):
                targets = resolve_call(call_info, sym)
                for target in targets:
                    if target and target != sym or (target == sym and call_info.get("receiver") != "super"):
                        graph[sym].append(target)
        
        # Find Cycles (DFS)
        cycles = []
        visited = set()
        recursion_stack = []
        
        def dfs(current: Symbol):
            visited.add(current)
            recursion_stack.append(current)
            
            for neighbor in graph.get(current, []):
                if neighbor in recursion_stack:
                    cycle_start = recursion_stack.index(neighbor)
                    cycle = recursion_stack[cycle_start:]
                    cycles.append(list(cycle))
                elif neighbor not in visited:
                    dfs(neighbor)
            
            recursion_stack.pop()
        
        for sym in graph.keys():
            if sym not in visited:
                dfs(sym)
        
        # Dedup cycles
        unique_cycles = []
        seen_str = set()
        
        for cyc in cycles:
            sig = "->".join(sorted([s.qualified_name for s in cyc]))
            if sig not in seen_str:
                seen_str.add(sig)
                unique_cycles.append(cyc)
        
        return unique_cycles

    def _detect_dead_code(self, symbol_builder: SymbolTableBuilder) -> List[Dict]:
        """Find functions that are never called anywhere across all files."""
        # Collect ALL calls from ALL files
        all_calls = set()
        for data in self.raw_data.values():
            for call in data.get("calls", []):
                all_calls.add(call)
        
        # Collect decorated function names — these are called by frameworks implicitly
        decorated_funcs = set()
        for data in self.raw_data.values():
            for func in data.get("functions", []):
                if func.get("decorators"):
                    decorated_funcs.add(func["name"])
        
        dead = []
        for qname, symbol in symbol_builder.symbols.items():
            # Only check functions and methods
            if symbol.type != SymbolType.FUNCTION:
                continue
            
            # Skip ALL dunder methods (__init__, __del__, __str__, __repr__, etc.)
            if symbol.name.startswith("__") and symbol.name.endswith("__"):
                continue
            
            # Skip main/test functions
            if "test" in symbol.name.lower() or "main" in symbol.name.lower():
                continue
            
            # Skip decorated functions (called by frameworks: @property, @route, etc.)
            if symbol.name in decorated_funcs:
                continue
            
            # Check if this function name appears in ANY call across ALL files
            if symbol.name not in all_calls:
                dead.append(symbol)
        
        return dead

    def _detect_unused_variables(self, symbol_builder: SymbolTableBuilder) -> List[Dict]:
        """
        Identify variables that are assigned but never used.
        Checks same-file and cross-file usage via imports.
        Tracks actual line numbers.
        """
        import ast
        
        unused = []
        
        # First pass: collect all names imported by any file (cross-file usage)
        cross_file_used = set()
        for file_path_str, data in self.raw_data.items():
            for imp in data.get("imports", []):
                for name in imp.get("names", []):
                    cross_file_used.add(name)
        
        for file_path_str, data in self.raw_data.items():
            fpath = Path(file_path_str)
            mod_name = fpath.stem
            
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    code = f.read()
                tree = ast.parse(code)
            except:
                continue
            
            # Track assignments with line numbers and all usages per scope
            class UsageVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.scope_stack = ["global"]
                    # scope -> {name: line_number}
                    self.assigns = {"global": {}}
                    # scope -> set of used names
                    self.usages = {"global": set()}
                    # Track function parameter names to exclude them
                    self.params = {"global": set()}
                
                @property
                def scope(self):
                    return self.scope_stack[-1]
                
                def visit_FunctionDef(self, node):
                    scope_name = node.name
                    self.scope_stack.append(scope_name)
                    self.assigns[scope_name] = {}
                    self.usages[scope_name] = set()
                    self.params[scope_name] = set()
                    
                    # Mark function parameters as params (not unused variables)
                    for arg in node.args.args:
                        self.params[scope_name].add(arg.arg)
                    if node.args.vararg:
                        self.params[scope_name].add(node.args.vararg.arg)
                    if node.args.kwarg:
                        self.params[scope_name].add(node.args.kwarg.arg)
                    
                    self.generic_visit(node)
                    self.scope_stack.pop()
                
                visit_AsyncFunctionDef = visit_FunctionDef
                
                def visit_Name(self, node):
                    if isinstance(node.ctx, ast.Store):
                        self.assigns[self.scope][node.id] = node.lineno
                    elif isinstance(node.ctx, (ast.Load, ast.Del)):
                        self.usages[self.scope].add(node.id)
                    self.generic_visit(node)
            
            visitor = UsageVisitor()
            visitor.visit(tree)
            
            # Check globals: unused if not used in same file AND not imported by other files
            for name, line in visitor.assigns["global"].items():
                # Skip dunder names
                if name.startswith("__") and name.endswith("__"):
                    continue
                # Skip _ prefix (deliberately unused)
                if name.startswith("_"):
                    continue
                # Check usage in global scope
                if name in visitor.usages["global"]:
                    continue
                # Check usage in any local scope within same file
                used_locally = False
                for scope, usage_set in visitor.usages.items():
                    if scope != "global" and name in usage_set:
                        used_locally = True
                        break
                if used_locally:
                    continue
                # Check cross-file usage (imported by other files)
                if name in cross_file_used:
                    continue
                
                unused.append({
                    "file": fpath.name,
                    "line": line,
                    "name": name,
                    "type": "global_variable"
                })
            
            # Check locals: unused if assigned but never loaded in same scope
            for scope, assigns in visitor.assigns.items():
                if scope == "global":
                    continue
                usages = visitor.usages.get(scope, set())
                params = visitor.params.get(scope, set())
                for name, line in assigns.items():
                    # Skip parameters
                    if name in params:
                        continue
                    # Skip _ prefix
                    if name.startswith("_"):
                        continue
                    # Skip dunder
                    if name.startswith("__") and name.endswith("__"):
                        continue
                    if name not in usages:
                        unused.append({
                            "file": fpath.name,
                            "line": line,
                            "name": f"{scope}.{name}",
                            "type": "local_variable"
                        })
        
        return unused

