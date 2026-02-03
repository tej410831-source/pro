# Usage Guide

## Prerequisites

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start vLLM Server

**Download Qwen2.5-Coder model:**
```bash
# Using Ollama (recommended)
ollama pull qwen2.5-coder:7b-instruct

# Or download from HuggingFace
huggingface-cli download Qwen/Qwen2.5-Coder-7B-Instruct
```

**Start vLLM server:**
```bash
# Option 1: Using vLLM directly
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct --port 8000

# Option 2: Using Ollama with OpenAI compatibility
ollama serve
```

**Verify server is running:**
```bash
curl http://localhost:8000/v1/models
```

---

## Basic Usage

### Analyze a Project

```bash
python main.py analyze /path/to/your/project --output report.json
```

### With Auto-Fix Generation

```bash
python main.py analyze /path/to/your/project --output report.json --generate-fixes
```

### Custom vLLM URL

```bash
python main.py analyze /path/to/your/project --vllm-url http://localhost:11434/v1
```

---

## What Happens During Analysis

### **Phase 1: File Scanning**
- Recursively finds all code files
- Filters by extension (`.py`, `.java`, `.cpp`)
- Skips ignored directories (`.git`, `node_modules`, etc.)

### **Phase 2: Static Syntax Analysis** ✨ **NEW: Auto-Fix**
- Uses native parsers (Python: `ast`, Java/C++: tree-sitter)
- Detects syntax errors with 100% accuracy
- **Automatically generates fixes using vLLM**
- **Validates fixes before proceeding**

**Example:**
```
❌ Found: def get_user(user_id
✅ Fixed: def get_user(user_id):
```

### **Phase 3: Symbol Table & Call Graph**
- Extracts all functions/classes
- Builds dependency graph with NetworkX
- Enables cross-file analysis

### **Phase 4: Cross-File Analysis**
- **Circular Dependencies:** Detects import cycles
- **Dead Code:** Functions never called
- **Duplicates:** Similar functions across files

### **Phase 5: LLM Semantic Bug Detection**
- Logic errors (null checks, algorithm bugs)
- Security vulnerabilities (SQL injection, XSS)
- Performance issues (N+1 queries)
- Error handling problems

### **Phase 6: Code Patch Generation**
- For each bug, vLLM generates executable fix
- Includes explanation and diff
- Can be applied directly to codebase

### **Phase 7: Report Generation**
- **JSON:** Machine-readable, includes all data
- **HTML:** Beautiful dashboard with charts

---

## Output Files

### `report.json`

```json
{
  "metadata": {
    "files_analyzed": 25,
    "syntax_errors_fixed": 3,
    "valid_files": 22
  },
  "syntax_fixes": {
    "test_file.py": {
      "errors_fixed": 2,
      "original_code": "def foo(\n...",
      "fixed_code": "def foo():\n...",
      "method": "regional"
    }
  },
  "bugs": [...],
  "fixes": [...],
  "cross_file_analysis": {
    "circular_dependencies": [],
    "dead_code": [],
    "duplicate_functions": []
  }
}
```

### `report.html`

Interactive dashboard with:
- Summary statistics
- Syntax errors + auto-fixes
- Bug list with severity
- Code patches
- Circular dependency graph
- Dead code list

---

## Testing the Syntax Fix Feature

### 1. Create a file with syntax errors

Use the included test file:
```bash
# test_syntax_errors.py contains intentional errors
```

### 2. Run analysis with auto-fix

```bash
python main.py analyze . --output test_report.json --generate-fixes
```

### 3. Check the output

```bash
# View the report
cat test_report.json | jq '.syntax_fixes'

# See what was fixed
cat test_report.json | jq '.syntax_fixes["test_syntax_errors.py"].fixed_code'
```

---

## Advanced Options

### Analyze Specific Files Only

```bash
python main.py analyze /path --pattern "*.py"
```

### Change LLM Temperature

Edit `analyzers/syntax_fix_generator.py`:
```python
temperature=0.1  # Lower = more deterministic
```

### Adjust Context Window

Edit `analyzers/syntax_fix_generator.py`:
```python
CONTEXT_LINES_BEFORE = 5  # Lines before error
CONTEXT_LINES_AFTER = 5   # Lines after error
```

---

## Troubleshooting

### vLLM Server Not Responding

```bash
# Check if server is running
curl http://localhost:8000/v1/models

# Restart server
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct --port 8000
```

### Syntax Fixes Not Working

Check the console output:
```
✗ Fix generation failed: Connection refused
```

This means vLLM server is not accessible.

### Large Files Timeout

Increase timeout in `llm/vllm_client.py`:
```python
timeout=120  # Increase from default
```

---

## Performance Optimization

### For Large Codebases (1000+ files)

1. **Use regional fixing** (automatic for large files)
2. **Parallel analysis** (future feature)
3. **Cache LLM responses** (already enabled)

### Token Usage Estimation

- Small file (<100 lines): ~1K tokens
- Large file regional fix: ~200 tokens per error
- Bug detection: ~800 tokens per function

---

## Next Steps

After getting the report:

1. **Review syntax fixes** in `report.json`
2. **Apply fixes** to your codebase (manual or automated)
3. **Review semantic bugs** and generated patches
4. **Check cross-file issues** (circular deps, dead code)
5. **Open HTML dashboard** for visual analysis
