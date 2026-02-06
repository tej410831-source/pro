from pathlib import Path
from typing import List, Dict, Set, Any
from core.ast_parser import StructuralParser
from core.symbol_table import SymbolTableBuilder, Symbol, SymbolType
import traceback

class StructuralAnalyzer:
    """
    Performs structural analysis on the codebase:
    - Symbol Table Construction
    - Circular Dependency Detection
    - Dead Code Detection (Global)
    """

    def __init__(self):
        self.parser = StructuralParser()
        self.raw_data = {} # {file_path: parse_result}

    def analyze_codebase(self, files: List[Path]) -> Dict[str, Any]:
        """Run full structural analysis on a list of files."""
        # Initialize Symbol Table
        symbol_builder = SymbolTableBuilder()
        
        results = {
            "symbol_table": {}, # Raw dict for easy JSON
            "symbol_table_object": None, # Object for main.py
            "circular_dependencies": [],
            "dead_code": [],
            "stats": {"functions": 0, "classes": 0}
        }
        
        # 1. Parse all files
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                # Use pure Python parser
                data = self.parser.parse_python(code, file_path)
                self.raw_data[str(file_path)] = data
                
                module_name = file_path.stem
                
                # Populate Symbol Table Object
                for func in data["functions"]:
                    symbol = Symbol(
                        name=func["name"],
                        symbol_type=SymbolType.FUNCTION,
                        file_path=file_path,
                        line=func["line"],
                        signature=func.get("signature", f"{func['name']}(...)"),
                        body_code=func.get("body_code", ""),
                        parent_name=func.get("parent_class", "")
                    )
                    symbol_builder.add_symbol(symbol, module_name)
                    results["stats"]["functions"] += 1
                
                for cls in data["classes"]:
                    symbol = Symbol(
                        name=cls["name"],
                        symbol_type=SymbolType.CLASS,
                        file_path=file_path,
                        line=cls["line"],
                        signature=f"class {cls['name']}",
                        attributes=cls.get("attributes", [])
                    )
                    symbol_builder.add_symbol(symbol, module_name)
                    results["stats"]["classes"] += 1
                
            except Exception as e:
                print(f"Failed to structural parse {file_path}: {e}")
        
        results["symbol_table_object"] = symbol_builder
        
        # 2. Build Global Symbol Table & Import Graph
        import_graph = self._build_import_graph()
        global_defs = self._collect_definitions()
        
        # 3. Detect Cycles (File-level)
        results["circular_dependencies"] = self._detect_cycles(import_graph)
        
        # 3b. Detect Function Cycles (Recursion)
        results["function_cycles"] = self._detect_function_cycles(symbol_builder)
        
        # 4. Detect Dead Code
        results["dead_code"] = self._detect_dead_code(symbol_builder)
        
        # 5. Detect Unused Variables
        results["unused_variables"] = self._detect_unused_variables(symbol_builder)
        
        results["symbol_table"] = global_defs
        results["raw_data"] = self.raw_data
        return results

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
        Returns list of cycles, where each cycle is a list of Symbol objects.
        """
        # 1. Build Call Graph (Qualified Name -> List[Qualified Names])
        # We need to resolve calls to qualified names.
        # This is hard without full resolution.
        # Approximation: Matches "func_name" to ANY function with that name in the codebase.
        # Limitation: Overloading/Shadowing might cause false positives.
        
        # Build map: Name -> [Symbol]
        name_map = {}
        for qname, sym in symbol_builder.symbols.items():
            if sym.type == SymbolType.FUNCTION:
                if sym.name not in name_map:
                    name_map[sym.name] = []
                name_map[sym.name].append(sym)
                
        # Build simple graph: Symbol -> [Symbol]
        graph = {}
        for qname, sym in symbol_builder.symbols.items():
            if sym.type != SymbolType.FUNCTION: continue
            
            graph[sym] = []
            
            # Find possible targets for each call
            # We look up calls in the raw_data for this file?
            # Creating a link requires raw data access or parsing body?
            # Wait, we don't have 'calls' in the Symbol object directly except 'body'.
            # But we have it in raw_data!
            
            # Retrieve calls for this function from raw_data
            file_data = self.raw_data.get(str(sym.file))
            if not file_data: continue
            
            func_data = next((f for f in file_data["functions"] if f["name"] == sym.name and f["line"] == sym.line), None)
            if not func_data: continue
            
            calls = func_data.get("calls", [])
            for call_name in calls:
                # Resolve call_name to Symbols
                targets = name_map.get(call_name, [])
                for target in targets:
                    graph[sym].append(target)
        
        # 2. Find Cycles (DFS)
        cycles = []
        visited = set()
        recursion_stack = [] # Stack of Symbols
        
        def dfs(current: Symbol):
            visited.add(current)
            recursion_stack.append(current)
            
            for neighbor in graph.get(current, []):
                if neighbor in recursion_stack:
                    # Found cycle
                    cycle_start = recursion_stack.index(neighbor)
                    cycle = recursion_stack[cycle_start:]
                    # Sort by qname to verify uniqueness (conceptually) or just append
                    # We store list of symbols
                    cycles.append(list(cycle))
                elif neighbor not in visited:
                    dfs(neighbor)
            
            recursion_stack.pop()
            
        for sym in graph.keys():
            if sym not in visited:
                dfs(sym)
                
        # Dedup cycles (naive string representation check)
        unique_cycles = []
        seen_str = set()
        
        for cyc in cycles:
            # Normalize cycle rotation? 
            # e.g. A->B->A is same as B->A->B
            # For simplicity, we just check exact match first or subset
            # Actually, standard recursion output usually just shows one instance
            sig = "->".join(sorted([s.qualified_name for s in cyc]))
            if sig not in seen_str:
                seen_str.add(sig)
                unique_cycles.append(cyc)
                
        return unique_cycles

    def _detect_dead_code(self, symbol_builder: SymbolTableBuilder) -> List[Dict]:
        """Find functions that are never called globally."""
        all_calls = set()
        for data in self.raw_data.values():
            for call in data.get("calls", []):
                all_calls.add(call)
        
        dead = []
        for qname, symbol in symbol_builder.symbols.items():
            # Only check functions
            if symbol.type != SymbolType.FUNCTION:
                continue
                
            # Ignore dunder methods
            if symbol.name.startswith("__"): continue
            
            # Ignore main/test functions
            if "test" in symbol.name.lower() or "main" in symbol.name.lower(): continue
            
            if symbol.name not in all_calls:
                dead.append(symbol)
        
        return dead

    def _detect_unused_variables(self, symbol_builder: SymbolTableBuilder) -> List[Dict]:
        """
        Identify variables that are assigned but never used (Simplified).
        Checks:
        1. Local variables in functions.
        2. Global variables in modules.
        """
        unused = []
        
        # 1. Global Variables (Module Level)
        # Scan raw data for assignments and usages
        for file_path_str, data in self.raw_data.items():
            fpath = Path(file_path_str)
            
            # Simple AST scan for this file
            try:
                import ast
                tree = ast.parse(data.get("source_code", "")) 
                # Wait, we didn't save source code in raw_data, only extracted structure.
                # We need to re-parse or store source.
                # Re-parsing is safer for memory.
                with open(fpath, 'r', encoding='utf-8') as f:
                    code = f.read()
                tree = ast.parse(code)
            except: continue
            
            # Track Global Scopes
            global_assigns = set()
            global_usages = set()
            
            class UsageVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.current_scope = "global"
                    self.local_assigns = {} # scope -> set
                    self.local_usages = {} # scope -> set
                    
                def visit_FunctionDef(self, node):
                    prev = self.current_scope
                    self.current_scope = node.name
                    self.local_assigns[self.current_scope] = set()
                    self.local_usages[self.current_scope] = set()
                    self.generic_visit(node)
                    self.current_scope = prev
                    
                def visit_Name(self, node):
                    if isinstance(node.ctx, ast.Store):
                        if self.current_scope == "global":
                            global_assigns.add(node.id)
                        else:
                            self.local_assigns[self.current_scope].add(node.id)
                    elif isinstance(node.ctx, ast.Load):
                        if self.current_scope == "global":
                            global_usages.add(node.id)
                        else:
                            self.local_usages[self.current_scope].add(node.id)
                            
            visitor = UsageVisitor()
            visitor.visit(tree)
            
            # Check Globals
            # Filter out __all__, simple constants?
            for name in global_assigns:
                if name.startswith("__"): continue
                if name not in global_usages:
                    # Check if exported? (Hard to know, assume unused if no local usage?)
                    # Cross-file usage check:
                    # We need to check if ANY file imports this name.
                    # Simplified: Check if name appears in global usages of ANY file?
                    unused.append({
                        "file": fpath.name,
                        "line": 1, # AST doesn't easily give line for set of assigns without tracking nodes
                        "name": name,
                        "type": "global_variable"
                    })
            
            # Check Locals
            for scope, assigns in visitor.local_assigns.items():
                usages = visitor.local_usages.get(scope, set())
                for name in assigns:
                    if name not in usages:
                        unused.append({
                            "file": fpath.name,
                            "line": 1, # Placeholder
                            "name": f"{scope}.{name}",
                            "type": "local_variable"
                        })
                        
        return unused
