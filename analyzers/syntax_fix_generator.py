"""
Syntax Error Fix Generator
Uses vLLM to automatically fix syntax errors with regional context.
"""

from pathlib import Path
from typing import List, Dict
import json

class SyntaxFixGenerator:
    """Generate fixes for syntax errors using vLLM with smart context extraction."""
    
    CONTEXT_LINES_BEFORE = 5  # Lines before error
    CONTEXT_LINES_AFTER = 5   # Lines after error
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

**Task:** Fix ALL syntax errors. Return ONLY the corrected code.
Do NOT change logic or add features - ONLY fix syntax.

**Output:**
```{language}
<your_fixed_code_here>
```
"""
        
        try:
            response = await self.llm_client.generate_completion(prompt, temperature=0.1)
            fixed_code = self._extract_code(response, language)
            
            return {
                'success': True,
                'fixed_code': fixed_code,
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
        prompt = self._build_regional_prompt(file_path, regions, errors)
        
        try:
            # Get fixes from LLM
            response = await self.llm_client.generate_completion(prompt, temperature=0.1)
            
            # Apply fixes to original code
            fixed_code = self._apply_regional_fixes(code, regions, response)
            
            return {
                'success': True,
                'fixed_code': fixed_code,
                'method': 'regional',
                'regions_fixed': len(regions)
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
    
    def _build_regional_prompt(self, file_path: Path, regions: List[Dict], errors: List) -> str:
        """Build prompt with error regions."""
        
        language = self._get_language(file_path)
        
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

{regions_str}

**Task:** For each error region, provide the FIXED version.
Return JSON with fixes for each region.

**Response Format:**
{{
  "fixes": [
    {{"region": 1, "fixed_code": "..."}},
    {{"region": 2, "fixed_code": "..."}}
  ]
}}
"""
    
    def _apply_regional_fixes(self, original_code: str, regions: List[Dict], llm_response: str) -> str:
        """Apply regional fixes to original code."""
        
        try:
            # Extract JSON from response
            response_data = json.loads(self._extract_json(llm_response))
            
            lines = original_code.split('\n')
            
            # Apply each fix (in reverse order to maintain line numbers)
            fixes = sorted(response_data.get('fixes', []), key=lambda x: x['region'], reverse=True)
            
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
            
        except Exception as e:
            # If parsing fails, return original
            return original_code
    
    def _get_language(self, file_path: Path) -> str:
        """Determine language from file extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.go': 'go'
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
    
    def _extract_json(self, response: str) -> str:
        """Extract JSON from response."""
        
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            return response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            return response[start:end].strip()
        else:
            # Try to find JSON object
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                return response[start:end]
            return response.strip()
