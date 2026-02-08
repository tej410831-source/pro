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
    
    async def fix_file_manual_assist(
        self,
        file_path: Path,
        code: str,
        errors: List
    ) -> Dict:
        """
        Suggest fixes for syntax errors sequentially, waiting for USER to apply them.
        """
        # Header is kept (as requested)
        print(f"\n🔍 Analysis for {file_path.name}: Found {len(errors)} error(s)")
        print(f"{'Line':<8} {'Error Type':<15} {'Message'}")
        print("─" * 70)
        for err in errors:
            err_type = err.parser if hasattr(err, 'parser') else 'SyntaxError'
            print(f"{err.line:<8} {err_type:<15} {err.message[:60]}")
        print()
        
        fixes_presented = 0
        
        for idx, error in enumerate(errors, 1):
            print(f"⏳ Generating fix for Line {error.line}...")
            
            try:
                fix_result = await self._fix_single_error(
                    code,
                    error,
                    file_path
                )
                
                if not fix_result['success']:
                    print(f"❌ Could not generate fix: {fix_result.get('error')}")
                    continue

                region = fix_result['region']
                fixed_code = fix_result['fixed_code']
                explanation = fix_result.get('explanation', 'Fixed syntax error')
                
                # Simplified Box Design
                print(f"\n👉 REPLACE Lines {region['start_line']} - {region['end_line']} with:")
                print("────────────────────────────────────────────────────────────")
                print(fixed_code.rstrip())
                print("────────────────────────────────────────────────────────────")
                print(f"ℹ️  Wait: {explanation}")
                
                while True:
                    # Clean, simple prompt
                    choice = input(f"\n> Press Enter when pasted (or 's' to skip, 'q' to quit file): ").strip().lower()
                    
                    if choice == '': # User pressed Enter (Applied)
                        fixes_presented += 1
                        break
                    elif choice == 's': # Skip this error
                        print("  Skipped.")
                        break
                    elif choice == 'q': # Quit file
                        print("  Skipping remaining errors for this file.")
                        return {'success': True, 'fixes_presented': fixes_presented}
            
            except Exception as e:
                print(f"❌ Error processing fix: {e}")
        
        return {'success': True, 'fixes_presented': fixes_presented}

    async def fix_file_sequentially(
        self,
        file_path: Path,
        code: str,
        errors: List,
        interactive: bool = True
    ) -> Dict:
        """
        Fix syntax errors one at a time with in-memory patching.
        
        NEW sequential workflow:
        1. Show all errors in table
        2. For each error: LLM fix → user review → apply patch (in memory)
        3. Final validation after all patches
        4. Return fixed code (caller writes to file)
        
        Args:
            file_path: Path to file
            code: Original code with syntax errors
            errors: List of FileSyntaxError objects
            interactive: If True, ask user for approval
        
        Returns:
            {
                'success': bool,
                'fixed_code': str,
                'errors_fixed': int,
                'errors_skipped': int,
                'patches': List[Dict]
            }
        """
        working_code = code
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
                fix_result = await self._fix_single_error(
                    working_code,
                    error,
                    file_path
                )
                
                if not fix_result['success']:
                    print(f"  ✗ Failed: {fix_result.get('error', 'Unknown')}")
                    errors_skipped += 1
                    continue
                
                region = fix_result['region']
                fixed_code = fix_result['fixed_code']
                explanation = fix_result.get('explanation', 'Fixed syntax error.')
                
                print(f"  📝 Proposed fix for lines {region['start_line']}-{region['end_line']}:")
                print(f"  ℹ️  {explanation}\n")
                
                # User approval (if interactive)
                if interactive:
                    response = input(f"  Apply fix {idx}/{len(errors)}? [Y/n]: ").strip().lower()
                    if response and response != 'y':
                        print(f"  ✗ Fix {idx} rejected")
                        errors_skipped += 1
                        continue
                
                # Apply patch in memory
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
                print(f"  ✗ Error: {str(e)}")
                errors_skipped += 1
        
        print(f"\n📊 Applied {errors_fixed}/{len(errors)} fixes")
        
        return {
            'success': errors_fixed > 0,
            'fixed_code': working_code,
            'errors_fixed': errors_fixed,
            'errors_skipped': errors_skipped,
            'patches': patches_applied
        }
    
    async def _fix_single_error(self, code: str, error, file_path: Path) -> Dict:
        """
        Fix a single syntax error with focused context.
        
        Args:
            code: Current code (may have previous patches)
            error: Single FileSyntaxError
            file_path: Path (for language detection)
        
        Returns:
            {
                'success': bool,
                'fixed_code': str,  # Fixed region only
                'region': Dict,
                'explanation': str
            }
        """
        language = self._get_language(file_path)
        lines = code.split('\n')
        error_line_idx = error.line - 1  # 0-indexed
        
        # Extract a SMALL window around the error (+/- 5 lines)
        window_size = 5
        start_line = max(0, error_line_idx - window_size)
        end_line = min(len(lines), error_line_idx + window_size + 1)
        
        window_lines = lines[start_line:end_line]
        error_in_window = error_line_idx - start_line
        
        # Build the code window with error marker
        code_with_marker = []
        for i, line in enumerate(window_lines):
            if i == error_in_window:
                code_with_marker.append(f"{line}  <--- ERROR HERE")
            else:
                code_with_marker.append(line)
        
        code_window = '\n'.join(code_with_marker)
        
        region = {
            'error': error,
            'code': '\n'.join(window_lines),
            'start_line': start_line + 1,
            'end_line': end_line,
            'error_line_in_region': error_in_window + 1
        }
        
        # Build MINIMAL, focused prompt
        prompt = f"""Fix this {language} syntax error:

ERROR at Line {error.line}: {error.message}

CODE WINDOW (Lines {region['start_line']}-{region['end_line']}):
{code_window}

TASK: Return the EXACT same code with ONLY the syntax error fixed.

CRITICAL RULES:
1. Return ALL {len(window_lines)} lines from the code window
2. Change ONLY what's needed to fix the syntax error
3. Do NOT add comments like "# ERROR fixed" - FIX SILENTLY
4. Do NOT use placeholders like "..." or "// rest of code"
5. PRESERVE all existing code exactly as-is except for the minimal syntax fix

XML FORMAT:
<FIX>
<CODE>
[All {len(window_lines)} lines with minimal syntax fix applied]
</CODE>
<EXPLANATION>[What single change was made]</EXPLANATION>
</FIX>

EXAMPLE:
If line has: "class Foo {{" (missing closing brace)
Fix to: "class Foo {{}}" (add closing brace)
Return ALL lines, not just the changed one.
"""
        
        try:
            response = await self.llm_client.generate_completion(prompt, temperature=0.1)
            
            # Try XML then markdown
            response_data = extract_xml_fixes(response)
            if not response_data:
                response_data = extract_code_from_markdown(response, num_regions=1)
            
            if not response_data or not response_data.get('fixes'):
                raise ValueError("Could not parse LLM response")
            
            fix = response_data['fixes'][0]
            fixed_code = fix['fixed_code']
            explanation = fix.get('explanation', 'Fixed syntax error.')
            
            # Apply context-aware indentation
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
    
    def apply_patch_to_code(self, original_code: str, region: Dict, fixed_code: str) -> str:
        """
        Replace region in original_code with fixed_code.
        
        Args:
            original_code: Full file content
            region: {'start_line': int, 'end_line': int} (1-indexed)
            fixed_code: Replacement code for region
        
        Returns:
            Patched full file content
        """
        lines = original_code.split('\n')
        start_idx = region['start_line'] - 1
        end_idx = region['end_line']
        fixed_lines = fixed_code.split('\n')
        
        patched_lines = lines[:start_idx] + fixed_lines + lines[end_idx:]
        return '\n'.join(patched_lines)
    
    def _check_skip_llm(self, code: str, errors: List) -> Optional[Dict]:
        """Check if errors are trivial and should skip LLM, returning helpful message instead."""
        lines = code.split('\n')
        
        for error in errors:
            # Check for unterminated triple-quotes
            if "unterminated" in error.message.lower() and "string" in error.message.lower():
                line_idx = error.line - 1
                if 0 <= line_idx < len(lines):
                    line = lines[line_idx]
                    if '"""' in line and line.count('"""') % 2 != 0:
                        # Return message instead of fix
                        print(f"\n⚠️  Trivial Error Detected:")
                        print(f"   File: Line {error.line}")
                        print(f"   Error: {error.message}")
                        print(f"   Code: {line.strip()}")
                        print(f"   Fix: Please close the string with ''' (triple quotes)")
                        return {
                            'success': False,
                            'skip_llm': True,
                            'message': 'Trivial error - user should fix manually'
                        }
        return None
    
    def _normalize_indentation(self, fixed_code: str, region: Dict) -> str:
        """
        Normalize indentation of LLM output to match original region, PRESERVING relative structure.
        
        Key improvement: Instead of flattening all lines to one base indent, this preserves
        the RELATIVE indentation differences (e.g., method def vs method body).
        
        Args:
            fixed_code: Code returned by LLM
            region: Original region dict with 'code', 'start_line', 'end_line'
            
        Returns:
            Code with corrected indentation preserving internal structure
        """
        if not fixed_code or not fixed_code.strip():
            return fixed_code
            
        # Get original and fixed lines
        original_lines = region['code'].split('\n')
        fixed_lines = fixed_code.split('\n')
        
        # Find minimum indentation in ORIGINAL code (our baseline)
        original_min_indent = float('inf')
        for line in original_lines:
            if line.strip():  # Skip empty lines
                indent = len(line) - len(line.lstrip())
                original_min_indent = min(original_min_indent, indent)
        
        if original_min_indent == float('inf'):
            original_min_indent = 0
        
        # Find minimum indentation in FIXED code (LLM's baseline)
        fixed_min_indent = float('inf')
        for line in fixed_lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                fixed_min_indent = min(fixed_min_indent, indent)
        
        if fixed_min_indent == float('inf'):
            return fixed_code  # All empty lines
        
        # Calculate offset: how much to shift ALL lines
        indent_offset = original_min_indent - fixed_min_indent
        
        # Apply offset to each line, preserving relative differences
        normalized_lines = []
        for line in fixed_lines:
            if not line.strip():
                # Keep empty lines empty
                normalized_lines.append('')
            else:
                # Current indent + offset
                current_indent = len(line) - len(line.lstrip())
                new_indent = max(0, current_indent + indent_offset)
                
                # Reconstruct line with new indent
                content = line.lstrip()
                normalized_lines.append(' ' * new_indent + content)
        
        return '\n'.join(normalized_lines)
    
    def _get_expected_base_indent(self, full_code: str, region: Dict) -> int:
        """
        Calculate the CORRECT base indentation by analyzing where the region
        sits in the file structure (inside a class, top-level, etc).
        
        Args:
            full_code: Complete file source code
            region: Error region dict with 'start_line'
            
        Returns:
            Expected base indentation in spaces
        """
        lines = full_code.split('\n')
        region_start = region['start_line'] - 1  # 0-indexed
        
        # Scan backwards from region start to find parent block
        for i in range(region_start - 1, -1, -1):
            line = lines[i].rstrip()
            if not line or line.strip().startswith('#'):
                continue  # Skip empty and comment lines
            
            stripped = line.lstrip()
            
            # Check for class or function definition
            if (stripped.startswith('class ') or 
                stripped.startswith('def ') or
                stripped.startswith('template') or  # C++ templates
                'class ' in stripped):  # Java/C++ classes
                
                # Found parent - calculate its indent
                parent_indent = len(line) - len(stripped)
                
                # Child elements are indented +4 from parent
                return parent_indent + 4
        
        # No parent found - this is top-level code
        return 0
    
    def _force_base_indent(self, code: str, expected_base_indent: int) -> str:
        """
        Force code to have the specified base indentation, preserving relative structure.
        
        This is different from _normalize_indentation - it doesn't use the buggy original
        as reference, instead it uses the CALCULATED expected indent from file structure.
        
        Args:
            code: LLM-generated code (may have wrong base indent)
            expected_base_indent: Correct base indent (from _get_expected_base_indent)
            
        Returns:
            Code with correct base indent, relative structure preserved
        """
        if not code or not code.strip():
            return code
        
        lines = code.split('\n')
        
        # Find minimum indent in LLM output
        min_indent = float('inf')
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                min_indent = min(min_indent, indent)
        
        if min_indent == float('inf'):
            return code  # All empty lines
        
        # Calculate how much to shift
        offset = expected_base_indent - min_indent
        
        # Apply offset, preserving relative indentation
        result_lines = []
        for line in lines:
            if not line.strip():
                result_lines.append('')
            else:
                current_indent = len(line) - len(line.lstrip())
                new_indent = max(0, current_indent + offset)
                content = line.lstrip()
                result_lines.append(' ' * new_indent + content)
        
        return '\n'.join(result_lines)
    
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
    
    def apply_selective_changes(self, original_code: str, selected_changes: List[Change]) -> str:
        """
        Apply only user-approved changes to the original code.
        
        Args:
            original_code: Original code with errors
            selected_changes: List of Change objects that user approved
        
        Returns:
            Code with only approved changes applied
        """
        if not selected_changes:
            return original_code
        
        lines = original_code.splitlines()
        
        # Sort changes by line number (reverse) to maintain line offsets
        sorted_changes = sorted(selected_changes, key=lambda c: c.line_start, reverse=True)
        
        for change in sorted_changes:
            start_idx = change.line_start - 1  # Convert to 0-indexed
            end_idx = change.line_end  # Exclusive end
            
            if change.type == 'add':
                # Insert new lines
                lines[start_idx:start_idx] = change.fixed_lines
            
            elif change.type == 'delete':
                # Remove lines
                del lines[start_idx:end_idx]
            
            elif change.type == 'modify':
                # Replace lines
                lines[start_idx:end_idx] = change.fixed_lines
        
        return '\n'.join(lines)
    
    async def _fix_whole_file(self, file_path: Path, code: str, errors: List) -> Dict:
        """Fix small files by sending entire content."""
        
        language = self._get_language(file_path)
        
        # Format errors
        error_details = '\n'.join([
            f"Line {e.line}: {e.message}"
            for e in errors
        ])

        prompt = f"""Fix the syntax errors in this {language} code.

Errors:
{error_details}

Code:
{code}

Return JSON with "fixed_code" and "explanation" keys."""
        
        
        try:
            response = await self.llm_client.generate_completion(
                prompt, 
                temperature=0.0,
                max_tokens=10000 #ure sufficient tokens for complete file
            )
            
            # Debug: Log raw LLM response (first 500 chars)
            print(f"[DEBUG] Raw LLM Response (first 500 chars): {response[:500]}")
            
            fix_data = robust_json_load(response)
            
            if not fix_data:
                print(f"[DEBUG] Failed to parse LLM response. Full response:\n{response}")
                return {
                    'success': False,
                    'error': 'Could not parse LLM response (all fallback stages failed)',
                    'method': 'whole_file'
                }
            
            
            # Compute granular changes for user approval
            fixed_code = fix_data.get('fixed_code', '')
            
            # Note: For whole-file fixes, normalization is skipped as the entire context is already known
            # The LLM sees the full file, so indentation should already be correct

            changes = self.diff_analyzer.compute_changes(code, fixed_code)
            
            # For whole file, we treat it as a single region covering everything
            fix_obj = {
                'region': 1,
                'fixed_code': fixed_code,
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
                'changes': changes,  # NEW: Granular changes for approval
                'original_code': code,  # NEW: Keep original for selective merge
                'fixed_code': fixed_code,  # NEW: Complete fixed version
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
            print(f"[DEBUG] Raw Regional Response: {response[:1000]}") # DEBUG LOG
            
            # Try XML parsing first
            response_data = extract_xml_fixes(response)
            
            # If XML fails, try markdown fallback
            if not response_data:
                print(f"[DEBUG] XML parsing failed. Trying markdown fallback...")
                response_data = extract_code_from_markdown(response, num_regions=len(regions))
            
            # If both fail, raise error
            if not response_data:
                print(f"[DEBUG] Both XML and markdown parsing failed. Raw: {response[:500]}")
                raise ValueError("Could not parse LLM response (tried XML and markdown)")
                
            fixes = response_data.get('fixes', [])
            
            # Apply context-aware indentation correction
            # Calculate expected indent from file structure, not buggy original
            for i, fix in enumerate(fixes):
                if 'fixed_code' in fix and i < len(regions):
                    # Calculate where this code SHOULD be indented based on file structure
                    expected_indent = self._get_expected_base_indent(code, regions[i])
                    # Force LLM output to this calculated indent
                    fix['fixed_code'] = self._force_base_indent(fix['fixed_code'], expected_indent)

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
            
            # Smart Context: Try to find enclosing class/function
            start_line, end_line = self._find_enclosing_block(lines, error_line)
            
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

    def _find_enclosing_block(self, lines: List[str], target_idx: int) -> Tuple[int, int]:
        """Find the start/end of the enclosing class or function using indentation."""
        start_idx = max(0, target_idx - self.CONTEXT_LINES_BEFORE)
        end_idx = min(len(lines), target_idx + self.CONTEXT_LINES_AFTER + 1)
        
        # Determine indentation of the target line
        target_line = lines[target_idx]
        if not target_line.strip():
            # If line is empty, look around for context indentation? 
            # Or just assume it's same as previous non-empty line
            target_indent = 0
            for i in range(target_idx - 1, -1, -1):
                if lines[i].strip():
                    target_indent = len(lines[i]) - len(lines[i].lstrip())
                    break
        else:
            target_indent = len(target_line) - len(target_line.lstrip())
            
        found_block = False
        base_indent = 0
        current_best_start = -1
        
        # 1. Search UPWARDS for 'class' or 'def' with LOWER indentation
        for i in range(target_idx, -1, -1):
            line = lines[i]
            if not line.strip(): continue
            
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            
            # Enclosing block must be OUTER (less indentation)
            # Unless strict nesting isn't valid (e.g. one-liners), but generally true.
            if indent < target_indent:
                if stripped.startswith("class "):
                    current_best_start = i
                    base_indent = indent
                    found_block = True
                    break # Priority to class
                elif stripped.startswith("def ") and current_best_start == -1:
                    current_best_start = i
                    base_indent = indent
                    found_block = True
            
            # Stop if we hit 0 indent and handled it
            if indent == 0 and i < target_idx and not found_block:
                # If we passed root and found nothing, stop
                pass 
                
        if found_block:
            start_idx = current_best_start
            
            # 2. Search DOWNWARDS for end of block (indent <= base_indent)
            end_search_start = target_idx + 1
            max_lines = len(lines)
            end_idx = max_lines
            
            for i in range(end_search_start, max_lines):
                line = lines[i]
                if not line.strip(): continue
                
                stripped = line.lstrip()
                indent = len(line) - len(stripped)
                
                if indent <= base_indent:
                    end_idx = i
                    break
                    
        return start_idx, end_idx
    
    def _build_regional_prompt(self, file_path: Path, regions: List[Dict], errors: List, original_code: str) -> str:
        """Build prompt with error regions and global context."""
        
        language = self._get_language(file_path)
        
        # Build minimal regions section
        regions_text = []
        for i, region in enumerate(regions, 1):
            error = region['error']
            regions_text.append(f"""Region {i}:
Error: Line {error.line}: {error.message}
Code (lines {region['start_line']}-{region['end_line']}):
{region['code']}
""")
        
        regions_str = '\n'.join(regions_text)
        
        return f"""Fix these {language} syntax errors:

{regions_str}

CRITICAL: You MUST return ONLY XML tags. Do NOT use markdown code blocks (```). Do NOT add explanatory text outside the XML structure.

Return output using EXACTLY this XML format:

<FIX>
    <REGION>1</REGION>
    <CODE>
    [Insert the COMPLETE fixed code here - no markdown, no backticks, just raw code]
    </CODE>
    <EXPLANATION>[Brief one-sentence explanation]</EXPLANATION>
</FIX>

RULES:
1. Output ONLY <FIX> tags. No markdown. No ```cpp or ```python blocks.
2. Inside <CODE>, put the raw fixed code directly. Do NOT wrap it in backticks.
3. Preserve original block indentation unless it causes syntax errors (top-level code = 0 indent).
4. For multiple regions, return multiple <FIX> blocks.

Example (for C++):
<FIX>
    <REGION>1</REGION>
    <CODE>
#include <iostream>
void log_message(std::string msg) {{
    std::cout << "[LOG] " << msg << std::endl;
}}
    </CODE>
    <EXPLANATION>Fixed missing semicolon and corrected operator.</EXPLANATION>
</FIX>
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
            '.py': 'python'
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

    def _clean_code(self, code: str) -> str:
        """
        Post-process LLM output to remove visual artifacts we injected into the prompt.
        Handles:
        1. <--- ERROR markers
        2. >> pointers
        3. Line number prefixes (e.g., '  12 | ')
        4. Accidental indentation
        """
        import re
        import textwrap
        
        if not code:
            return ""
            
        # 0. Fix literal newlines (common in regex-extracted JSON)
        code = code.replace('\\n', '\n')
            
        lines = code.split('\n')
        clean_lines = []
        for line in lines:
            # 1. Strip tail markers
            if "<--- ERROR" in line:
                line = line.split("<--- ERROR")[0].rstrip()
            
            # 2. Strip lead pointers (conservative)
            # Only if line starts with >> 
            if line.strip().startswith(">> "):
                line = line.replace(">> ", "", 1)
                
            # 3. Strip line numbers (e.g. "   12 | code")
            # Regex: Start of line, optional space, digits, space, pipe, optional space
            # Be careful not to match actual code like "1 | 2"
            # We assume line numbers are at the very start
            line = re.sub(r'^\s*\d+\s*\|\s?', '', line)
            
            clean_lines.append(line)
        
        cleaned = '\n'.join(clean_lines)
        
        # 4. Dedent (if the whole block was indented)
        cleaned = textwrap.dedent(cleaned)
        
        # 5. Normalize Indentation (Heuristic)
        # Round leading spaces to nearest 4 to fix "off-by-one" errors from LLMs (e.g. 5 spaces vs 4)
        normalized_lines = []
        for line in cleaned.split('\n'):
            stripped = line.lstrip()
            if not stripped:
                normalized_lines.append("")
                continue
                
            leading_spaces = len(line) - len(stripped)
            # Round to nearest 4
            rounded = round(leading_spaces / 4) * 4
            normalized_lines.append(" " * rounded + stripped)
            
        cleaned = '\n'.join(normalized_lines)
        
        return cleaned
    def _identify_scope(self, lines: List[str], line_idx: int) -> Tuple[str, int, int]:
        """
        Identify if a line is inside a function, class, or global scope.
        Returns (scope_type, start_line, end_line)
        """
        # Scan upwards for definitions
        # This is a simplified heuristic mainly for Python/C++/Java style indentation
        
        current_indent = len(lines[line_idx]) - len(lines[line_idx].lstrip())
        
        func_start = -1
        class_start = -1
        
        for i in range(line_idx, -1, -1):
            line = lines[i]
            if not line.strip(): continue
            
            indent = len(line) - len(line.lstrip())
            stripped = line.strip()
            
            # Function detection
            if indent < current_indent and (stripped.startswith('def ') or ' void ' in line or ' int ' in line):
                 if func_start == -1:
                     func_start = i
            
            # Class detection
            if indent < current_indent and (stripped.startswith('class ') or 'class ' in line):
                class_start = i
                break # Found the enclosing class, stop
        
        # Determine scope hierarchy
        if func_start != -1:
            start, end = self._find_block_bounds(lines, func_start)
            return ('function', start, end)
        elif class_start != -1:
            start, end = self._find_block_bounds(lines, class_start)
            return ('class', start, end)
        else:
            return ('global', max(0, line_idx - 5), min(len(lines), line_idx + 6))

    def _find_block_bounds(self, lines: List[str], start_idx: int) -> Tuple[int, int]:
        """Given a start line (def/class), find where the indentation block ends."""
        start_line = lines[start_idx]
        base_indent = len(start_line) - len(start_line.lstrip())
        
        end_idx = len(lines)
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if not line.strip(): continue
            indent = len(line) - len(line.lstrip())
            if indent <= base_indent:
                end_idx = i
                break
        return start_idx, end_idx

    def _generate_class_skeleton(self, lines: List[str], class_start: int, class_end: int) -> str:
        """Create a skeleton of the class: keep vars, blank out function bodies."""
        skeleton = []
        
        for i in range(class_start, class_end):
            line = lines[i]
            if not line.strip(): 
                skeleton.append("")
                continue
                
            indent = len(line) - len(line.lstrip())
            stripped = line.strip()
            
            # Simple heuristic for method start
            is_method = stripped.startswith('def ') or ('(' in line and ')' in line and ('{' in line or ':' in line))
            
            if is_method:
                 skeleton.append(line + " ... }") # Simplified placeholder
                 continue
            
            # Keep member variables / fields
            if '=' in line or ';' in line:
                skeleton.append(line)
        
        return '\n'.join(skeleton)

    def _extract_smart_context(self, code: str, error_line: int) -> Dict:
        """
        Build rich context based on error location.
        """
        lines = code.split('\n')
        
        # 1. Identify Scope (Function vs Class vs Global)
        scope_type, start, end = self._identify_scope(lines, error_line)
        
        # 2. Extract Focused Code (The part needing fix)
        focused_lines = lines[start:end]
        focused_code = '\n'.join(focused_lines)
        
        # 3. Extract Metadata (Imports / Globals)
        metadata = self._extract_global_context(code)
        
        # 4. Extract Skeleton (Parent Context)
        skeleton = ""
        if scope_type == 'function':
            # Find parent class to give skeleton
            _, class_start, class_end = self._identify_scope(lines, start - 1)
            if class_start != -1:
                skeleton = self._generate_class_skeleton(lines, class_start, class_end)
        
        return {
            'scope': scope_type,
            'focused_code': focused_code,
            'skeleton': skeleton,
            'metadata': metadata,
            'region_start': start + 1, # 1-indexed for display
            'region_end': end
        }