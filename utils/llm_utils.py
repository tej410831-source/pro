import json
import re
import html
from typing import Optional, Dict, Any

def extract_json(response: str) -> str:
    """
    Extracts JSON string from an LLM response, handling markdown blocks 
    and common formatting errors.
    """
    json_str = ""
    # 1. Try to find markdown JSON block
    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        json_str = response[start:end].strip()
    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        json_str = response[start:end].strip()
    else:
        # 2. Try to find first { and last }
        start = response.find("{")
        end = response.rfind("}") + 1
        if start != -1 and end > start:
            json_str = response[start:end]
        else:
            json_str = response.strip()

    return repair_json(json_str)

def repair_json(json_str: str) -> str:
    """
    Highly resilient JSON repair for LLM responses.
    Handles raw newlines, unescaped quotes in strings, and bad encoding.
    """
    if not json_str:
        return ""

    # 1. Basic cleanup
    json_str = json_str.strip()
    if not json_str.startswith('{'):
        start = json_str.find('{')
        if start != -1:
            json_str = json_str[start:]
    if not json_str.endswith('}'):
        end = json_str.rfind('}')
        if end != -1:
            json_str = json_str[:end+1]
    
    # 1.5. LM Studio Fix: Convert Python triple-quotes to valid JSON
    # LM Studio often generates: "fixed_code": """...multi-line..."""
    # We need to convert this to: "fixed_code": "...\\n...\\n..."
    def replace_triple_quotes(match):
        key = match.group(1)
        content = match.group(2)
        # Escape internal quotes and convert newlines
        escaped = content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
        return f'"{key}": "{escaped}"'
    
    # Match: "key": """content"""
    # Use lookahead (?=[,}]) to ensure we identify the TRUE closing triple quote
    # This prevents matching "internal" triple quotes (like docstrings)
    json_str = re.sub(r'"([^"]+)":\s*"""(.*?)"""\s*(?=[,}])', replace_triple_quotes, json_str, flags=re.DOTALL)

    # 2. State-machine based character escaping for strings
    corrected = ""
    in_string = False
    i = 0
    while i < len(json_str):
        char = json_str[i]
        
        # Handle escaped characters already in the string
        if char == '\\' and i + 1 < len(json_str):
            corrected += json_str[i:i+2]
            i += 2
            continue
            
        if char == '"':
            # Is this a delimiter or an internal quote?
            # Check if it's followed by : or preceded by : / { / [ / ,
            # This is a heuristic but remarkably effective for LLM JSON
            is_probably_delimiter = False
            
            # Look ahead for ":"
            lookahead = json_str[i+1:].strip()
            if lookahead.startswith(':') or lookahead.startswith(',') or lookahead.startswith('}') or lookahead.startswith(']'):
                is_probably_delimiter = True
            
            # Look behind
            lookbehind = json_str[:i].strip()
            if lookbehind.endswith(':') or lookbehind.endswith('{') or lookbehind.endswith(',') or lookbehind.endswith('['):
                is_probably_delimiter = True
                
            if is_probably_delimiter:
                in_string = not in_string
                corrected += char
            else:
                # Internal quote - escape it if we are in a string
                if in_string:
                    corrected += '\\"'
                else:
                    # Not in string but not a delimiter? Probably a messy LLM start
                    in_string = True
                    corrected += char
            i += 1
            continue

        if char == '\n' and in_string:
            corrected += "\\n"
        elif char == '\r' and in_string:
            pass
        else:
            corrected += char
        i += 1
        
    return corrected

def robust_json_load(response: str) -> Optional[Dict[str, Any]]:
    """
    The ultimate failsafe for LLM JSON responses.
    Stages:
    1. Standard extract + repair + json.loads
    2. Heuristic regex key-value extraction
    3. Deep search for specific known keys (fixed_code, explanation, issues)
    """
    if not response:
        return None

    # Stage 1: Standard Pipeline
    json_str = extract_json(response)
    try:
        return json.loads(json_str)
    except:
        pass

    # Stage 2: Manual character-by-character extraction (Handles complex escaping)
    # Work on json_str (already preprocessed by repair_json)
    try:
        # Find the start of fixed_code value
        start_marker = '"fixed_code"'
        start_idx = json_str.find(start_marker)
        if start_idx == -1:
            raise ValueError("fixed_code not found")
        
        # Move past the key and find the opening quote of the value
        i = start_idx + len(start_marker)
        while i < len(json_str) and json_str[i] in ' \t\n\r:':
            i += 1
        
        if i >= len(json_str) or json_str[i] != '"':
            raise ValueError("No opening quote for fixed_code value")
        
        # Now extract the string value, respecting escapes
        i += 1  # Skip opening quote
        value_chars = []
        while i < len(json_str):
            ch = json_str[i]
            if ch == '\\' and i + 1 < len(json_str):
                # Escape sequence - take both characters literally
                value_chars.append(ch)
                value_chars.append(json_str[i + 1])
                i += 2
            elif ch == '"':
                # Unescaped quote - this is the end of the string value
                break
            else:
                value_chars.append(ch)
                i += 1
        
        raw_code = ''.join(value_chars)
        
        # Now unescape the JSON string
        try:
            # Try using json.loads on just this value
            fixed_code = json.loads('"' + raw_code + '"')
        except Exception as e:
            # Manual unescape fallback
            fixed_code = (raw_code
                         .replace('\\n', '\n')
                         .replace('\\t', '\t')
                         .replace('\\r', '\r')
                         .replace('\\"', '"')
                         .replace('\\\\', '\\'))
            
        # Try to fetch explanation too from json_str
        expl = ""
        expl_match = re.search(r'"explanation"\s*:\s*"(.*?)"(?=\s*})', json_str, re.DOTALL)
        if expl_match:
             expl = expl_match.group(1).replace('\\"', '"').replace('\\n', '\n')
        
        return {"fixed_code": fixed_code, "explanation": expl}
    except:
        pass

    # Stage 3: Specific Extraction for "fixes" list (Regional Mode)
    try:
        # Look for "fixes": [...]
        fixes_match = re.search(r'"fixes"\s*:\s*(\[.*?\])', json_str, re.DOTALL)
        if fixes_match:
            fixes_json = fixes_match.group(1)
            # Try to repair and load JUST the list
            try:
                fixes_list = json.loads(fixes_json)
                return {"fixes": fixes_list}
            except:
                # If list itself is malformed, try to extract objects inside it
                # regex to find { ... } inside the list
                obj_matches = re.findall(r'(\{[^{}]+\})', fixes_json)
                fixes = []
                for obj_str in obj_matches:
                    try:
                        # Attempt to load each object
                        obj = json.loads(obj_str)
                        fixes.append(obj)
                    except:
                        pass
                if fixes:
                    return {"fixes": fixes}
    except:
        pass

    # Stage 4: Deep Search (Greedy extraction for specific keys)
    # This handles cases where the LLM might have put garbage between fields
    deep_results = {}
    
    # Target keys we usually care about
    target_keys = ["fixed_code", "explanation", "issues", "fixes", "regions"]
    
    for key in target_keys:
        # Look for "key": "..." with DOTALL
        pattern = rf'"{key}"\s*:\s*"(.*?)"(?=\s*[,\}}\n])'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            # Clean up the extracted value (basic unescape)
            val = match.group(1).replace('\\n', '\n').replace('\\"', '"')
            deep_results[key] = val
        
        # Also try without quotes for key (rare but happens)
        elif not match:
             pattern = rf'{key}\s*:\s*"(.*?)"(?=\s*[,\}}\n])'
             match = re.search(pattern, response, re.DOTALL)
             if match:
                 deep_results[key] = match.group(1)

    if deep_results:
        return deep_results

    return None

def fast_repair_and_load(json_str: str) -> Optional[Dict[str, Any]]:
    """Regex-based key-value extraction for broken JSON structures."""
    try:
        results = {}
        # Matches "key": "value" pairs with comma or brace lookahead
        pairs = re.findall(r'"([^"]+)"\s*:\s*"(.*?)"(?=\s*[,}])', json_str, re.DOTALL)
        for k, v in pairs:
            # Basic repair for internal quotes that might have been escaped or not
            cleaned_v = v.replace('\\n', '\n').replace('\\"', '"')
            results[k] = cleaned_v
            
        if results:
            return results
        return None

    except:
        return None

def extract_xml_fixes(response: str) -> Optional[Dict[str, Any]]:
    """
    Extracts fixes from XML-style LLM response.
    Format:
    <FIX>
        <REGION>1</REGION>
        <CODE>...</CODE>
        <EXPLANATION>...</EXPLANATION>
    </FIX>
    """
    fixes = []
    
    # Regex to find all <FIX> blocks
    # Use re.DOTALL to match newlines
    fix_blocks = re.findall(r'<FIX>(.*?)</FIX>', response, re.DOTALL | re.IGNORECASE)
    
    for block in fix_blocks:
        try:
            # Extract Region ID
            region_match = re.search(r'<REGION>\s*(\d+)\s*</REGION>', block, re.IGNORECASE)
            region_id = int(region_match.group(1)) if region_match else 1
            
            # Extract Code
            # Note: LLM may return `<CODE>...</CODE>` where ... contains angle brackets like `#include <iostream>`
            # XML parser may escape these as `&lt;iostream&gt;`, so we need to unescape them
            code_match = re.search(r'<CODE>(.*?)</CODE>', block, re.DOTALL | re.IGNORECASE)
            fixed_code = code_match.group(1).strip() if code_match else ""
            
            # Clean up CDATA markers if present
            fixed_code = fixed_code.replace('<![CDATA[', '').replace(']]>', '').strip()
            
            # Unescape HTML entities (e.g., &lt; -> <, &gt; -> >)
            fixed_code = html.unescape(fixed_code)
            
            # Extract Explanation
            expl_match = re.search(r'<EXPLANATION>(.*?)</EXPLANATION>', block, re.DOTALL | re.IGNORECASE)
            explanation = expl_match.group(1).strip() if expl_match else "Fixed syntax error."
            
            fixes.append({
                "region": region_id,
                "fixed_code": fixed_code,
                "explanation": explanation
            })
        except:
            continue
            
    if fixes:
        return {"fixes": fixes}
        
    return None


def extract_code_from_markdown(response: str, num_regions: int = None) -> Optional[Dict[str, Any]]:
    """
    Fallback parser for when LLM returns markdown code blocks instead of XML.
    
    Extracts code from markdown blocks like:
    ```cpp
    code here
    ```
    
    Args:
        response: LLM response containing markdown code blocks
        num_regions: Expected number of regions (for validation)
        
    Returns:
        Dict with same structure as extract_xml_fixes: {"fixes": [...]}
    """
    fixes = []
    
    # Regex to find markdown code blocks: ```language\ncode\n```
    # Captures: language and code
    pattern = r'```(\w+)\s*\n(.*?)\n```'
    matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
    
    if not matches:
        return None
    
    # Map each code block to a region (assume sequential order)
    for idx, (language, code) in enumerate(matches):
        region_id = idx + 1
        
        # Try to extract explanation from text following the code block
        # Look for "Explanation:" or similar patterns
        explanation = "Fixed syntax error."
        
        # Search for explanation text between this block and the next
        try:
            # Find position of current code block
            block_pattern = r'```' + re.escape(language) + r'\s*\n' + re.escape(code[:50])
            block_match = re.search(block_pattern, response, re.DOTALL)
            
            if block_match:
                # Get text after this block
                remaining_text = response[block_match.end():]
                
                # Look for explanation patterns
                expl_patterns = [
                    r'Explanation:\s*([^\n]+)',
                    r'Fixed:\s*([^\n]+)',
                    r'Note:\s*([^\n]+)',
                ]
                
                for pattern in expl_patterns:
                    expl_match = re.search(pattern, remaining_text, re.IGNORECASE)
                    if expl_match:
                        explanation = expl_match.group(1).strip()
                        break
        except:
            pass  # Use default explanation
        
        fixes.append({
            "region": region_id,
            "fixed_code": code.strip(),
            "explanation": explanation
        })
    
    # Validate if num_regions provided
    if num_regions and len(fixes) != num_regions:
        # LLM may have grouped multiple regions - just return what we found
        pass
    
    if fixes:
        return {"fixes": fixes}
    
    return None
