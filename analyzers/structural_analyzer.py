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
        print(f"Phase 4: Analyzing {len(files)} files structurally...")
        
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

        # 2. Mark Usage & Build Call Graph
        called_names = set()
        for file_path_str, data in self.file_data_map.items():
            fpath = Path(file_path_str)
            mod_name = fpath.stem
            
            for call in data.get("calls", []):
                called_names.add(call)
            
            for func_data in data.get("functions", []):
                caller_prefix = f"{func_data['parent_class']}." if func_data.get("parent_class") else ""
                caller_qname = f"{mod_name}.{caller_prefix}{func_data['name']}"
                
                for f_call in func_data.get("calls", []):
                    # Resolve call to likely targets (simplified)
                    targets = self.symbol_table.find_symbols_by_name(f_call)
                    for target in targets:
                        self.call_graph.add_edge(caller_qname, target.qualified_name)

        # Mark used symbols in the table
        for qname, sym in self.symbol_table.symbols.items():
            if sym.type == STSymbolType.FUNCTION:
                if sym.name.lower() in ['main', '__init__', '__main__']:
                    sym.is_used = True
                elif sym.name in called_names:
                    sym.is_used = True
                else:
                    sym.is_used = False
            
            elif sym.type == STSymbolType.VARIABLE:
                # Basic usage check: if name appears elsewhere
                count = all_identifiers_global.count(sym.name)
                # Count > 1 means it appeared somewhere else in addition to declaration
                sym.is_used = (count > 1 or sym.name.startswith("_"))

        # 3. Detect Cycles
        import_cycles = []
        try:
            for cycle in nx.simple_cycles(self.dependency_graph):
                if len(cycle) > 1:
                    import_cycles.append(" -> ".join(cycle))
        except: pass

        call_cycles = []
        try:
            # We want SCCs for call graph as it can be large
            for cycle in nx.simple_cycles(self.call_graph):
                if len(cycle) > 1:
                    # Clean up qnames for display
                    clean_cycle = [qn.split('.')[-1] for qn in cycle]
                    call_cycles.append(" -> ".join(clean_cycle))
                if len(call_cycles) > 10: break # Limit
        except: pass

        # 4. Filter Dead Code
        dead_functions = [s for s in self.symbol_table.symbols.values() 
                         if s.type == STSymbolType.FUNCTION and not getattr(s, 'is_used', False)]
        dead_variables = [s for s in self.symbol_table.symbols.values() 
                         if s.type == STSymbolType.VARIABLE and not getattr(s, 'is_used', False)]

        return {
            "symbol_table_object": self.symbol_table,
            "raw_data": self.file_data_map,
            "dead_code": {
                "functions": dead_functions,
                "variables": dead_variables
            },
            "cycles": {
                "imports": import_cycles,
                "calls": call_cycles
            },
            "stats": {
                "total_symbols": len(self.symbol_table.symbols),
                "files_analyzed": len(files)
            },
            "circular_dependencies": import_cycles # legacy name
        }


