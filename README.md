# Advanced Code Analysis System

🔍 Hybrid static + AI code analysis with cross-file intelligence

## Features

✅ **Static-First Syntax Analysis** - 100% accurate syntax checking  
✅ **Cross-File Redundancy Detection** - Find duplicate functions  
✅ **Dead Code Detection** - Functions never called  
✅ **Circular Dependency Detection** - Import cycles  
✅ **LLM Semantic Analysis** - Logic errors, security issues  
✅ **Automatic Fix Generation** - Executable code patches  

## 💻 Supported Languages
- **Python** (`.py`)

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

### Step 1: Start vLLM Server

**Important:** The system requires a running vLLM server for semantic analysis.

```bash
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-Coder-7B-Instruct \
    --port 8000
```

### Step 2: Test vLLM Connection (Optional)

```bash
python test_vllm.py
```

Expected output:
```
🔍 Testing vLLM Connection...
✅ vLLM Response:
{
  "issues": [...]
}
✅ vLLM is working correctly!
```

### Step 3: Run Analysis

```bash
# Analyze your code
python main.py analyze /path/to/your/code

# Custom options
python main.py analyze /path/to/code \
    --output results.json \
    --vllm-url http://localhost:8000/v1
```

## How vLLM is Used

The system uses vLLM for:

1. **Semantic Bug Detection** (`analyzers/llm_bug_detector.py`)
   - Logic errors, null checks
   - Security vulnerabilities (SQL injection, XSS)
   - Performance issues
   - Edge case handling

2. **Auto-Fix Generation** (`analyzers/fix_generator.py`)
   - Generates executable code patches
   - Validates fixes are syntactically correct

3. **Cross-File Redundancy** (`analyzers/cross_file_redundancy.py`)
   - Semantic similarity validation
   - Determines if functions are truly duplicates

**All vLLM calls go through:** `llm/vllm_client.py` with caching

## Output

### JSON Report
```json
{
  "metadata": {...},
  "syntax_errors": {...},
  "cross_file_analysis": {
    "circular_dependencies": [...],
    "dead_code": [...],
    "duplicate_functions": [...]
  }
}
```

### HTML Dashboard
Interactive web dashboard with:
- Summary statistics
- Syntax error list
- Cross-file issues (circular deps, dead code)
- Duplicate function detection
- Modern gradient UI

## Architecture

```
1. Scan → 2. Static Syntax → 3. Symbol Table → 4. Call Graph
    ↓
5. Cross-File Analysis (Redundancy, Dead Code, Circular Deps)
    ↓
6. HTML Report Generation
```

## Components

- **core/scanner.py** - File discovery
- **analyzers/static_syntax.py** - Syntax validation  
- **core/symbol_table.py** - Symbol indexing
- **core/call_graph_builder.py** - Dependency graphs (NetworkX)
- **analyzers/cross_file_redundancy.py** - Duplicate detection
- **analyzers/fix_generator.py** - Auto-fix generation
- **utils/html_report_generator.py** - Dashboard creation

## Example

```bash
python main.py analyze ./my_project
```

Output:
```
🔍 Analyzing: ./my_project

Phase 1: Scanning files...
✓ Found 25 code files

Phase 2: Static syntax analysis...
✓ 24 files passed syntax check
✗ 1 files have syntax errors

✅ Report saved to: report.json

╭─────────────── Analysis Summary ───────────────╮
│ Metric           │ Value                       │
├──────────────────┼─────────────────────────────┤
│ Total Files      │ 25                          │
│ Valid Files      │ 24                          │
│ Syntax Errors    │ 1                           │
│ Circular Deps    │ 2                           │
│ Dead Functions   │ 5                           │
╰──────────────────┴─────────────────────────────╯
```

## License

MIT
