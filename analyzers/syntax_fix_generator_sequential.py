from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
import shutil
from utils.llm_utils import extract_json, robust_json_load, extract_xml_fixes, extract_code_from_markdown
from utils.diff_analyzer import DiffAnalyzer, Change

class SyntaxFixGenerator:
    """Generate fixes for syntax errors using vLLM with smart context extraction."""
    
    CONTEXT_LINES_BEFORE = 10 # Lines before error
    CONTEXT_LINES_AFTER = 10   # Lines after error
    MAX_LINES_FOR_WHOLE_FILE = 100  # Threshold for whole-file vs regional
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.diff_analyzer = DiffAnalyzer()
    
    async def fix_file_sequentially(
        self,
        file_path: Path,
        code: str,
        errors: List,
        interactive: bool = True
    ) -> Dict:
        """
        Fix syntax errors one at a time with in-memory patching.
        
        This is the NEW sequential workflow that processes errors individually:
        1. Show all errors in a table
        2. For each error:
           - Extract context region
           - Get LLM fix for THAT error only
           - User reviews fix
           - Apply patch to working_code (in memory)
        3. Final validation after all patches applied
        4. Return fixed code (caller handles file writes)
        
        Args:
            file_path: Path to the file
            code: Original code with syntax errors
            errors: List of FileSyntaxError objects
            interactive: If True, ask user for approval on each fix
        
        Returns:
            {
                'success': bool,
                'fixed_code': str,  # Fully patched code
                'errors_fixed': int,
                'errors_skipped': int,
                'patches': List[Dict]  # History of applied patches
            }
        """
        working_code = code  # Start with original, apply patches iteratively
        patches_applied = []
        errors_fixed = 0
        errors_skipped = 0
        
        print(f"\n🔍 Found {len(errors)} syntax error(s) in {file_path.name}")
        print(f"\n{'Line':<8} {'Error Type':<15} {'Message'}")
        print("─" * 70)
        for err in errors:
            err_type = err.parser if hasattr(err, 'parser') else 'SyntaxError'
            print(f"{err.line:<8} {err_type:<15} {err.message[:50]}")
        print()
        
        # Process each error sequentially
        for idx, error in enumerate(errors, 1):
            print(f"\n→ Fixing error {idx}/{len(errors)} (Line {error.line})...")
            
            try:
                # Fix single error with current working_code
                fix_result = await self._fix_single_error(
                    working_code,
                    error,
                    file_path
                )
                
                if not fix_result['success']:
                    print(f"  ✗ Failed to generate fix: {fix_result.get('error', 'Unknown')}")
                    errors_skipped += 1
                    continue
                
                # Show fix to user
                region = fix_result['region']
                fixed_code = fix_result['fixed_code']
                explanation = fix_result.get('explanation', 'Fixed syntax error.')
                
                print(f"  📝 Proposed fix for lines {region['start_line']}-{region['end_line']}:")
                print(f"  ℹ️  {explanation}\n")
                
                # User approval (if interactive)
                if interactive:
                    # TODO: Show actual diff here
                    response = input(f"  Apply fix {idx}/{len(errors)}? [Y/n]: ").strip().lower()
                    if response and response != 'y':
                        print(f"  ✗ Fix {idx} rejected by user")
                        errors_skipped += 1
                        continue
                
                # Apply patch to working code (in memory)
                working_code = self.apply_patch_to_code(
                    working_code,
                    region,
                    fixed_code
                )
                
                patches_applied.append({
                    'error_line': error.line,
                    'region': region,
                    'explanation': explanation
                })
                
                errors_fixed += 1
                print(f"  ✓ Fix {idx} applied to working code")
                
            except Exception as e:
                print(f"  ✗ Error processing fix: {str(e)}")
                errors_skipped += 1
                continue
        
        print(f"\n📊 Applied {errors_fixed}/{len(errors)} fixes")
        
        return {
            'success': errors_fixed > 0,
            'fixed_code': working_code,
            'errors_fixed': errors_fixed,
            'errors_skipped': errors_skipped,
            'patches': patches_applied
        }
    
    async def _fix_single_error(
        self,
        code: str,
        error,  # FileSyntaxError
        file_path: Path
    ) -> Dict:
        """
        Fix a single syntax error with focused context.
        
        Args:
            code: Current code (may already have previous patches applied)
            error: Single FileSyntaxError object
            file_path: Path to file (for language detection)
        
        Returns:
            {
                'success': bool,
                'fixed_code': str,  # Just the fixed region code
                'region': Dict,     # {start_line, end_line, ...}
                'explanation': str
            }
        """
        language = self._get_language(file_path)
        
        # Extract region around this specific error
        lines = code.split('\n')
        error_line = error.line - 1  # Convert to 0-indexed
        
        # Find enclosing block
        start_line, end_line = self._find_enclosing_block(lines, error_line)
        
        # Extract region code
        region_lines = lines[start_line:end_line]
        region_code = '\n'.join(region_lines)
        
        region = {
            'error': error,
            'code': region_code,
            'start_line': start_line + 1,  # Back to 1-indexed
            'end_line': end_line,
            'error_line_in_region': error_line - start_line + 1
        }
        
        # Build prompt for SINGLE error
        prompt = f"""Fix this {language} syntax error:

Error: Line {error.line}: {error.message}

Code (lines {region['start_line']}-{region['end_line']}):
{region_code}

CRITICAL: Return ONLY the FIXED code for these lines. Use this XML format:

<FIX>
    <CODE>
    [Insert the COMPLETE fixed code here - no markdown, no backticks, just raw code]
    </CODE>
    <EXPLANATION>[Brief one-sentence explanation]</EXPLANATION>
</FIX>

RULES:
1. Output ONLY ONE <FIX> tag (this is a single error)
2. Inside <CODE>, put the raw fixed code directly. Do NOT wrap it in backticks.
3. Preserve original indentation unless it causes the syntax error.
"""
        
        try:
            # Get fix from LLM
            response = await self.llm_client.generate_completion(prompt, temperature=0.1)
            
            # Try XML parsing first
            response_data = extract_xml_fixes(response)
            
            # If XML fails, try markdown fallback
            if not response_data:
                response_data = extract_code_from_markdown(response, num_regions=1)
            
            # If both fail, raise error
            if not response_data or not response_data.get('fixes'):
                raise ValueError("Could not parse LLM response")
            
            fix = response_data['fixes'][0]  # Should only be one fix
            fixed_code = fix['fixed_code']
            explanation = fix.get('explanation', 'Fixed syntax error.')
            
            # Apply context-aware indentation correction
            expected_indent = self._get_expected_base_indent(code, region)
            fixed_code = self._force_base_indent(fixed_code, expected_indent)
            
            return {
                'success': True,
                'fixed_code': fixed_code,
                'region': region,
                'explanation': explanation
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'region': region
            }
    
    def apply_patch_to_code(
        self,
        original_code: str,
        region: Dict,
        fixed_code: str
    ) -> str:
        """
        Replace a region in the original code with fixed code.
        
        Args:
            original_code: Full file content
            region: Dictionary with 'start_line' and 'end_line' (1-indexed)
            fixed_code: Replacement code for that region
        
        Returns:
            Updated full file content with patch applied
        """
        lines = original_code.split('\n')
        
        # Convert to 0-indexed
        start_idx = region['start_line'] - 1
        end_idx = region['end_line']
        
        # Split fixed_code into lines
        fixed_lines = fixed_code.split('\n')
        
        # Replace region with fixed lines
        patched_lines = lines[:start_idx] + fixed_lines + lines[end_idx:]
        
        return '\n'.join(patched_lines)
    
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
        # Skip LLM for trivial unterminated string errors
        skip_result = self._check_skip_llm(code, errors)
        if skip_result:
            return skip_result
            
        # Use LLM for regional fixes
        return await self._fix_regions(file_path, code, errors)
