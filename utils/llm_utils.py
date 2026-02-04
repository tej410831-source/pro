import json
import re
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

    # Stage 2: Fast Heuristic (regex pairs)
    fast_data = fast_repair_and_load(json_str)
    if fast_data:
        return fast_data

    # Stage 3: Deep Search (Greedy extraction for specific keys)
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
