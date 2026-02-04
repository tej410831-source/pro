from pathlib import Path
from typing import List, Dict, Optional
import json
import shutil
from utils.llm_utils import extract_json, robust_json_load

class SyntaxFixGenerator:
    """Generate fixes for syntax errors using vLLM with smart context extraction."""
    
    CONTEXT_LINES_BEFORE = 10 # Lines before error
    CONTEXT_LINES_AFTER = 10   # Lines after error
    MAX_LINES_FOR_WHOLE_FILE = 100  # Threshold for whole-file vs regional
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    async def generate_fix(
        self, 
        file_path: Path, 
        code: str, 
        errors: List
    ) -> Dict:
        """
        Generate fix for syntax errors.
        
        Args:
            file_path: Path to the file
            code: Original code with syntax errors
            errors: List of SyntaxError objects
        
        Returns:
            Dict with 'success', 'fixed_code', and 'method' keys
        """
        
        lines = code.split('\n')
        
        # Choose strategy based on file size
        if len(lines) <= self.MAX_LINES_FOR_WHOLE_FILE:
            # Small file: send whole thing
            return await self._fix_whole_file(file_path, code, errors)
        else:
            # Large file: regional fixing
            return await self._fix_regions(file_path, code, errors)
    
    def apply_fixes(self, original_code: str, regions: List[Dict], selected_fixes: List[Dict]) -> str:
        """Apply a subset of fixes to the original code."""
        lines = original_code.split('\n')
        
        # Apply fixes in reverse order to maintain line numbers
        # selected_fixes should be a list of fix objects from the LLM
        fixes = sorted(selected_fixes, key=lambda x: x['region'], reverse=True)
        
        for fix in fixes:
            region_idx = fix['region'] - 1
            if region_idx < len(regions):
                region = regions[region_idx]
                fixed_lines = fix['fixed_code'].split('\n')
                
                # Replace lines in original
                start = region['start_line'] - 1
                end = region['end_line']
                lines[start:end] = fixed_lines
        
        return '\n'.join(lines)
    
    async def _fix_whole_file(self, file_path: Path, code: str, errors: List) -> Dict:
        """Fix small files by sending entire content."""
        
        language = self._get_language(file_path)
        
        # Format errors
        error_details = '\n'.join([
            f"  - Line {e.line}, Column {e.column}: {e.message}"
            for e in errors
        ])
        
        prompt = f"""You are an expert {language} developer. Fix ALL syntax errors below.

**File:** {file_path.name}

**Syntax Errors:**
{error_details}

**Code with Errors:**
```{language}
{code}
```

**Task:** Fix ALL syntax errors. Return the corrected code and a brief explanation of what was changed.

**Response Format (JSON):**
Return a JSON object with EXACTLY two keys: "fixed_code" and "explanation". 
IMPORTANT: Use double backslashes for newlines in fixed_code strings, or ensure the response is valid JSON that can be parsed by `json.loads`.

{{
  "fixed_code": "def example():\\n    print('fixed')",
  "explanation": "Brief description"
}}
"""
        
        try:
            response = await self.llm_client.generate_completion(prompt, temperature=0.1)
            fix_data = json.loads(extract_json(response))
            
            # For whole file, we treat it as a single region covering everything
            fix_obj = {
                'region': 1,
                'fixed_code': fix_data.get('fixed_code', ''),
                'explanation': fix_data.get('explanation', 'Fixed syntax errors.')
            }
            
            # Create a "pseudo-region" for the whole file
            region_obj = {
                'error': errors[0], # Just use first error for ref
                'code': code,
                'start_line': 1,
                'end_line': len(code.split('\n')),
                'error_line_in_region': errors[0].line
            }

            return {
                'success': True,
                'fixes': [fix_obj],
                'regions': [region_obj],
                'method': 'whole_file'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'method': 'whole_file'
            }
    
    async def _fix_regions(self, file_path: Path, code: str, errors: List) -> Dict:
        """Fix large files by extracting error regions."""
        
        # Extract regions around each error
        regions = self._extract_error_regions(code, errors)
        
        # Build prompt
        prompt = self._build_regional_prompt(file_path, regions, errors, code)
        
        try:
            # Get fixes from LLM
            response = await self.llm_client.generate_completion(prompt, temperature=0.1)
            response_data = robust_json_load(response)
            if not response_data:
                raise ValueError("Could not parse LLM response")
            fixes = response_data.get('fixes', [])

            return {
                'success': True,
                'fixes': fixes,
                'regions': regions,
                'method': 'regional'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'method': 'regional'
            }
    
    def _extract_error_regions(self, code: str, errors: List) -> List[Dict]:
        """Extract code regions around each error."""
        
        lines = code.split('\n')
        regions = []
        
        for error in errors:
            error_line = error.line - 1  # Convert to 0-indexed
            
            # Calculate context window
            start_line = max(0, error_line - self.CONTEXT_LINES_BEFORE)
            end_line = min(len(lines), error_line + self.CONTEXT_LINES_AFTER + 1)
            
            # Extract region
            region_lines = lines[start_line:end_line]
            region_code = '\n'.join(region_lines)
            
            regions.append({
                'error': error,
                'code': region_code,
                'start_line': start_line + 1,  # Back to 1-indexed
                'end_line': end_line,
                'error_line_in_region': error_line - start_line + 1
            })
        
        return regions
    
    def _build_regional_prompt(self, file_path: Path, regions: List[Dict], errors: List, original_code: str) -> str:
        """Build prompt with error regions and global context."""
        
        language = self._get_language(file_path)
        
        # Extract global context (imports, constants)
        global_context = self._extract_global_context(original_code)
        
        # Build regions section
        regions_text = []
        for i, region in enumerate(regions, 1):
            error = region['error']
            regions_text.append(f"""
**Error Region {i}:**
- Line {error.line}: {error.message}
- Code (lines {region['start_line']}-{region['end_line']}):

```{language}
{region['code']}
```
""")
        
        regions_str = '\n'.join(regions_text)
        
        return f"""You are an expert {language} developer. Fix the syntax errors in each region below.

**File:** {file_path.name}

**Global Context (Imports & Constants):**
```{language}
{global_context}
```

{regions_str}

**Task:** For each error region, provide the FIXED version.
Return JSON with fixes for each region.

**Response Format:**
{{
  "fixes": [
    {{
      "region": 1, 
      "fixed_code": "...",
      "explanation": "<brief explanation of fix for this region>"
    }},
    {{
      "region": 2, 
      "fixed_code": "...",
      "explanation": "..."
    }}
  ]
}}
"""
    
    def apply_fix_to_file(self, file_path: Path, fixed_code: str, create_backup: bool = True) -> Dict:
        """Write fixed code to file, optionally creating a backup."""
        try:
            if create_backup:
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                shutil.copy2(file_path, backup_path)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_code)
            
            return {'success': True, 'backup_path': str(backup_path) if create_backup else None}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def restore_from_backup(self, file_path: Path) -> bool:
        """Restore file from its .bak version if it exists."""
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        if backup_path.exists():
            shutil.move(backup_path, file_path)
            return True
        return False
    
    def _get_language(self, file_path: Path) -> str:
        """Determine language from file extension."""
        ext_map = {
            '.py': 'python',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'cpp'  # Header files treated as C++ for syntax
        }
        return ext_map.get(file_path.suffix, 'python')
    
    def _extract_code(self, response: str, language: str) -> str:
        """Extract code from LLM response."""
        
        # Try language-specific code block
        marker = f"```{language}"
        if marker in response:
            start = response.find(marker) + len(marker)
            end = response.find("```", start)
            return response[start:end].strip()
        
        # Try generic code block
        if "```" in response:
            start = response.find("```") + 3
            # Skip language identifier if present
            newline = response.find("\n", start)
            if newline != -1:
                start = newline + 1
            end = response.find("```", start)
            return response[start:end].strip()
        
        # No code block found, return as-is
        return response.strip()
    
    # _extract_json replaced by utils.llm_utils.extract_json

    def _extract_global_context(self, code: str) -> str:
        """
        Scans values for imports and global constants.
        This provides the LLM with necessary context even when fixing a small region.
        """
        lines = code.split('\n')
        context_lines = []
        
        for line in lines:
            stripped = line.strip()
            # 1. Capture all Import statements
            if stripped.startswith('import ') or stripped.startswith('from '):
                context_lines.append(line)
            
            # 2. Capture Global Constants (e.g., MAX_RETRIES = 5)
            # We look for lines that look like: VARIABLE_NAME = ...
            elif '=' in line:
                parts = line.split('=')
                left_side = parts[0].strip()
                # Heuristic: Uppercase usually implies a constant
                if left_side.isupper() and ' ' not in left_side:
                    context_lines.append(line)
        
        return '\n'.join(context_lines)
