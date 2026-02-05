"""
DiffAnalyzer - Extract granular changes between code versions.

This utility computes line-by-line differences and groups them into
logical change blocks for user review.
"""

import difflib
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class Change:
    """Represents a single logical change in the code."""
    type: str  # 'modify', 'add', 'delete'
    line_start: int  # 1-indexed
    line_end: int    # 1-indexed, inclusive
    original_lines: List[str]
    fixed_lines: List[str]
    description: str = ""
    
    def __post_init__(self):
        """Auto-generate description if not provided."""
        if not self.description:
            self.description = self._generate_description()
    
    def _generate_description(self) -> str:
        """Generate human-readable description of the change."""
        num_orig = len(self.original_lines)
        num_fixed = len(self.fixed_lines)
        
        if self.type == 'add':
            if num_fixed == 1:
                return f"Added line {self.line_start}"
            else:
                return f"Added lines {self.line_start}-{self.line_end}"
        
        elif self.type == 'delete':
            if num_orig == 1:
                return f"Deleted line {self.line_start}"
            else:
                return f"Deleted lines {self.line_start}-{self.line_end}"
        
        else:  # modify
            if self.line_start == self.line_end:
                return f"Modified line {self.line_start}"
            else:
                return f"Modified lines {self.line_start}-{self.line_end}"


class DiffAnalyzer:
    """Analyze differences between original and fixed code."""
    
    def __init__(self, context_lines: int = 0):
        """
        Args:
            context_lines: Number of unchanged lines to include around changes
        """
        self.context_lines = context_lines
    
    def compute_changes(self, original: str, fixed: str) -> List[Change]:
        """
        Compute granular changes between original and fixed code.
        
        Args:
            original: Original code with errors
            fixed: Fixed code from LLM
        
        Returns:
            List of Change objects representing individual modifications
        """
        original_lines = original.splitlines()
        fixed_lines = fixed.splitlines()
        
        # Use difflib to get opcodes
        matcher = difflib.SequenceMatcher(None, original_lines, fixed_lines)
        opcodes = matcher.get_opcodes()
        
        changes = []
        
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                # No change, skip
                continue
            
            elif tag == 'replace':
                # Lines were modified
                changes.append(Change(
                    type='modify',
                    line_start=i1 + 1,  # Convert to 1-indexed
                    line_end=i2,
                    original_lines=original_lines[i1:i2],
                    fixed_lines=fixed_lines[j1:j2]
                ))
            
            elif tag == 'delete':
                # Lines were removed
                changes.append(Change(
                    type='delete',
                    line_start=i1 + 1,
                    line_end=i2,
                    original_lines=original_lines[i1:i2],
                    fixed_lines=[]
                ))
            
            elif tag == 'insert':
                # Lines were added
                changes.append(Change(
                    type='add',
                    line_start=i1 + 1,  # Insert position in original
                    line_end=i1 + 1 + (j2 - j1) - 1,
                    original_lines=[],
                    fixed_lines=fixed_lines[j1:j2]
                ))
        
        # Group nearby changes if they're adjacent
        grouped_changes = self._group_adjacent_changes(changes)
        
        return grouped_changes
    
    def _group_adjacent_changes(self, changes: List[Change]) -> List[Change]:
        """
        Group consecutive changes that are part of the same logical modification.
        
        For example, if line 10 is modified and line 11 is added, 
        they should be shown as one change block.
        """
        if not changes:
            return []
        
        grouped = []
        current_group = changes[0]
        
        for change in changes[1:]:
            # Check if this change is adjacent to current group
            if change.line_start <= current_group.line_end + 2:  # Allow 1-line gap
                # Merge into current group
                current_group = self._merge_changes(current_group, change)
            else:
                # Start new group
                grouped.append(current_group)
                current_group = change
        
        # Don't forget the last group
        grouped.append(current_group)
        
        return grouped
    
    def _merge_changes(self, change1: Change, change2: Change) -> Change:
        """Merge two adjacent changes into one logical change."""
        return Change(
            type='modify',  # Merged changes are always 'modify'
            line_start=min(change1.line_start, change2.line_start),
            line_end=max(change1.line_end, change2.line_end),
            original_lines=change1.original_lines + change2.original_lines,
            fixed_lines=change1.fixed_lines + change2.fixed_lines,
            description=f"Modified lines {min(change1.line_start, change2.line_start)}-{max(change1.line_end, change2.line_end)}"
        )
    
    def format_change_for_display(self, change: Change) -> Tuple[str, str]:
        """
        Format a change for user-friendly display.
        
        Returns:
            (before_text, after_text) tuple
        """
        before_lines = []
        after_lines = []
        
        if change.type == 'modify':
            # Show both before and after
            for i, line in enumerate(change.original_lines):
                line_num = change.line_start + i
                before_lines.append(f"  {line_num:3d} │ {line}")
            
            for i, line in enumerate(change.fixed_lines):
                line_num = change.line_start + i
                after_lines.append(f"  {line_num:3d} │ {line}")
        
        elif change.type == 'add':
            # Show only after (additions)
            before_lines.append(f"  [No lines in original]")
            for i, line in enumerate(change.fixed_lines):
                line_num = change.line_start + i
                after_lines.append(f"  {line_num:3d} │ {line}")
        
        elif change.type == 'delete':
            # Show only before (deletions)
            for i, line in enumerate(change.original_lines):
                line_num = change.line_start + i
                before_lines.append(f"  {line_num:3d} │ {line}")
            after_lines.append(f"  [Lines removed]")
        
        return ('\n'.join(before_lines), '\n'.join(after_lines))
