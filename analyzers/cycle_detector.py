from typing import List, Dict, Set, Any
from rich.console import Console

console = Console()

class CycleDetector:
    def __init__(self):
        pass

    def detect_cycles(self, symbol_table: Dict[str, Any]) -> List[List[str]]:
        """
        Detect recursion cycles in the call graph using Tarjan's algorithm for SCCs.
        Returns a list of cycles, where each cycle is a list of function names ['A', 'B', 'A'].
        """
        # 1. Build Adjacency List
        # Node = Function Name (globally unique? No, name collision possible. Should use file:name)
        # But symbol_table structure is file -> functions.
        # Let's map "Name" to NodeID if possible, or just use Name if unique enough for now.
        # Actually, different files can have same function name (static calls vs global).
        # Phase 2 AST parser returns "calls": ["func_name"].
        # It doesn't resolve WHICH "func_name" (file1 or file2).
        # We'll assume global namespace for simplicity (C-like) or simple match.
        
        adj = {}
        all_funcs = set()
        
        # We need to map short names to full entries to report locations.
        func_locations = {} # name -> {file, line}
        
        for file_path, file_data in symbol_table.items():
            for func in file_data.get("functions", []):
                name = func["name"]
                
                # Store location for reporting
                if name not in func_locations:
                    func_locations[name] = []
                func_locations[name].append(f"{file_path}:{func['line']}")
                
                all_funcs.add(name)
                if name not in adj:
                    adj[name] = set()
                
                for callee in func.get("calls", []):
                    # We add edge name -> callee
                    adj[name].add(callee)
                    all_funcs.add(callee) # callee might be external or not defined

        # 2. Tarjan's Algorithm
        index = 0
        stack = []
        indices = {}
        lowlinks = {}
        on_stack = set()
        visited = set()
        cycles = []

        def strongconnect(v):
            nonlocal index
            indices[v] = index
            lowlinks[v] = index
            index += 1
            stack.append(v)
            on_stack.add(v)
            visited.add(v)

            neighbors = adj.get(v, [])
            for w in neighbors:
                if w not in visited:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif w in on_stack:
                    lowlinks[v] = min(lowlinks[v], indices[w])

            # If v is a root node, pop the stack and generate an SCC
            if lowlinks[v] == indices[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == v:
                        break
                
                # Check if SCC is a cycle
                # SCC of size > 1 is a cycle.
                # SCC of size 1 is a cycle ONLY if it has a self-loop.
                is_cycle = False
                if len(scc) > 1:
                    is_cycle = True
                elif len(scc) == 1:
                    node = scc[0]
                    if node in adj.get(node, []):
                        is_cycle = True
                
                if is_cycle:
                    # Provide full cycle path for clarity? SCC is a set.
                    # Just returning the members is enough for "Cycle detected between A, B, C".
                    cycles.append(scc)

        for v in all_funcs:
            if v not in visited:
                strongconnect(v)
                
        # 3. Format result
        # Return list of cycles with location info?
        # The caller (main.py) will format it.
        # We return list of names in the cycle.
        return cycles, func_locations
