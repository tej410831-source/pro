"""
Call Graph Builder
Constructs function call graph and file dependency graph using NetworkX.
"""

from pathlib import Path
from typing import Dict, List, Set, Tuple
import networkx as nx
from core.symbol_table import Symbol, SymbolTableBuilder

class CallGraphBuilder:
    """
    Builds directed graph of function calls across the codebase.
    """
    
    def __init__(self, symbol_table: SymbolTableBuilder):
        self.symbol_table = symbol_table
        self.function_graph = nx.DiGraph()  # Function -> Function calls
        self.file_graph = nx.DiGraph()       # File -> File dependencies
        self.call_sites: Dict[str, List[str]] = {}  # function -> list of functions it calls
    
    def build_call_graph(self, parsed_files: Dict[Path, dict]):
        """
        Build call graph and file dependency graph from parsed file data.
        """
        # Phase 1: Add all function nodes
        for qualified_name, symbol in self.symbol_table.symbols.items():
            self.function_graph.add_node(qualified_name, symbol=symbol)
        
        # Phase 2: Add call edges (Function -> Function)
        for file_path, data in parsed_files.items():
            for func_data in data.get("functions", []):
                caller = func_data.get("qualified_name")
                calls = func_data.get("calls", [])
                
                if caller:
                    self.call_sites[caller] = calls
                    for call_name in calls:
                        callee = self._resolve_call(call_name, file_path)
                        if callee and callee in self.symbol_table.symbols:
                            self.function_graph.add_edge(caller, callee)
            
            # Phase 3: Add import edges (File -> File) directly from parser data
            caller_file = str(file_path)
            if not self.file_graph.has_node(caller_file):
                self.file_graph.add_node(caller_file)
                
            for imp in data.get("imports", []):
                # Handle 'from module import names'
                if imp.get("module"):
                    module_name = imp["module"]
                    # Find file corresponding to this module
                    # (Simple heuristic: module name matches filename)
                    for other_path in parsed_files.keys():
                        if other_path.stem == module_name:
                            self.file_graph.add_edge(caller_file, str(other_path))
                
                # Handle 'import name'
                for name in imp.get("names", []):
                    for other_path in parsed_files.keys():
                        if other_path.stem == name:
                            self.file_graph.add_edge(caller_file, str(other_path))
        
        # Phase 4: Build file dependency graph from function calls as well
        self._build_file_graph()
    
    def _resolve_call(self, call_name: str, current_file: Path) -> str:
        """
        Resolve a function call to its qualified name.
        Simple heuristic: check if exact match exists in symbol table.
        """
        # Try exact match first
        if call_name in self.symbol_table.symbols:
            return call_name
        
        # Try matching by name only (find in same file first)
        candidates = self.symbol_table.find_symbols_by_name(call_name)
        
        # Prefer symbols in same file
        for candidate in candidates:
            if candidate.file == current_file:
                return candidate.qualified_name
        
        # Return first match if any
        if candidates:
            return candidates[0].qualified_name
        
        return None
    
    def _build_file_graph(self):
        """Build file dependency graph from function call graph."""
        for caller, callee in self.function_graph.edges():
            caller_symbol = self.symbol_table.get_symbol(caller)
            callee_symbol = self.symbol_table.get_symbol(callee)
            
            if caller_symbol and callee_symbol:
                caller_file = str(caller_symbol.file)
                callee_file = str(callee_symbol.file)
                
                if caller_file != callee_file:
                    self.file_graph.add_edge(caller_file, callee_file)
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """
        Detect circular dependencies in file graph.
        Returns list of cycles (each cycle is a list of file paths).
        """
        try:
            cycles = list(nx.simple_cycles(self.file_graph))
            return cycles
        except:
            return []
    
    def find_dead_code(self, entry_points: List[str] = None) -> List[Symbol]:
        """
        Find functions never called from entry points.
        
        Args:
            entry_points: List of qualified function names (e.g., ["main.main"])
                         If None, finds functions with no incoming edges
        """
        if entry_points:
            # Find all reachable functions from entry points
            reachable = set()
            for entry in entry_points:
                if entry in self.function_graph:
                    reachable.add(entry)
                    reachable.update(nx.descendants(self.function_graph, entry))
            
            # Dead code = all functions - reachable
            all_functions = set(self.function_graph.nodes())
            dead = all_functions - reachable
        else:
            # Simple heuristic: functions with no incoming edges (except entry points)
            dead = set()
            for node in self.function_graph.nodes():
                if self.function_graph.in_degree(node) == 0:
                    # Check if it's not a common entry point name
                    symbol = self.symbol_table.get_symbol(node)
                    if symbol and symbol.name not in {'main', '__main__', 'run', 'start'}:
                        dead.add(node)
        
        # Convert to Symbol objects
        return [self.symbol_table.get_symbol(qname) for qname in dead 
                if self.symbol_table.get_symbol(qname)]
    
    def get_call_chain(self, from_func: str, to_func: str) -> List[str]:
        """Get shortest call chain between two functions."""
        try:
            if nx.has_path(self.function_graph, from_func, to_func):
                return nx.shortest_path(self.function_graph, from_func, to_func)
        except:
            pass
        return []
