"""
Symbol Table Builder
Creates a global index of all symbols for cross-file analysis.
"""

from pathlib import Path
from typing import Dict, List
from enum import Enum

class SymbolType(Enum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"

class Symbol:
    def __init__(
        self,
        name: str,
        symbol_type: SymbolType,
        file_path: Path,
        line: int,
        signature: str,
        docstring: str = "",
        body_code: str = "",
        parent_name: str = "",
        attributes: List[str] = None
    ):
        self.name = name
        self.type = symbol_type
        self.file = file_path
        self.line = line
        self.signature = signature
        self.docstring = docstring
        self.body_code = body_code
        self.parent_name = parent_name
        self.attributes = attributes or []
        self.qualified_name = ""  # Set by table builder

class SymbolTableBuilder:
    """
    Builds a comprehensive symbol table from parsed files.
    """
    
    def __init__(self):
        self.symbols: Dict[str, Symbol] = {}
    
    def add_symbol(self, symbol: Symbol, module_name: str):
        """
        Add symbol with qualified name.
        Format: module.class.method or module.function
        """
        if symbol.parent_name:
            symbol.qualified_name = f"{module_name}.{symbol.parent_name}.{symbol.name}"
        else:
            symbol.qualified_name = f"{module_name}.{symbol.name}"
        self.symbols[symbol.qualified_name] = symbol
    
    def get_symbol(self, qualified_name: str) -> Symbol:
        return self.symbols.get(qualified_name)
    
    def find_symbols_by_name(self, name: str) -> List[Symbol]:
        """Find all symbols with given name (across modules)."""
        return [s for qn, s in self.symbols.items() if s.name == name]
    
    def get_symbols_in_file(self, file_path: Path) -> List[Symbol]:
        """Get all symbols defined in a file."""
        return [s for s in self.symbols.values() if s.file == file_path]
