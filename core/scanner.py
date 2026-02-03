"""
File Scanner
Recursively discovers code files.
"""

import os
from pathlib import Path
from typing import List

class FileScanner:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs'}
    
    def scan(self) -> List[Path]:
        """Scan for code files."""
        code_files = []
        
        for root, dirs, files in os.walk(self.root_path):
            # Skip common ignored directories
            dirs[:] = [d for d in dirs if d not in {
                '.git', 'node_modules', '__pycache__', 'venv', '.venv',
                'build', 'dist', '.tox', '.egg-info'
            }]
            
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix in self.extensions:
                    code_files.append(file_path)
        
        return code_files
