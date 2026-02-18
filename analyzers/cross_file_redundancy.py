import ast
import re
import json
import difflib
from typing import List, Dict
from pathlib import Path
from core.symbol_table import Symbol, SymbolType


class DuplicateFunction:
    def __init__(self, functions: List[Symbol], similarity: float, reason: str):
        self.functions = functions
        self.similarity = similarity
        self.reason = reason
        self.suggestion = ""


class CrossFileRedundancyDetector:
    """
    Detects semantic duplicates: functions with same LOGIC but different NAMES/VARIABLES.
    
    Pipeline:
      1. Structural Filter  — compare AST fingerprints to find candidate pairs
      2. LLM Verification   — ask the model to confirm functional equivalence
    """

    # Dunder methods to skip — boilerplate that is naturally similar across classes
    SKIP_METHODS = {
        '__init__', '__str__', '__repr__', '__eq__', '__ne__', '__lt__', '__gt__',
        '__le__', '__ge__', '__hash__', '__len__', '__bool__', '__del__',
        '__enter__', '__exit__', '__iter__', '__next__', '__getitem__', '__setitem__',
        '__contains__', '__call__', '__new__', '__setattr__', '__getattr__',
    }

    MIN_BODY_LINES = 3           # minimum function body lines to consider
    AST_SIMILARITY_THRESHOLD = 0.55  # structural similarity cutoff for LLM pass
    AUTO_CONFIRM_THRESHOLD = 0.95    # above this → auto-confirm without LLM (near-exact structure only)

    def __init__(self, symbol_table, llm_client=None):
        self.symbol_table = symbol_table
        self.llm_client = llm_client

    # ── Main entry point ─────────────────────────────────────────────
    async def detect_duplicates(self, console=None) -> List[DuplicateFunction]:
        duplicates = []

        # ── Step 0: exact duplicate definitions (same name, same scope) ──
        seen_files = {sym.file for sym in self.symbol_table.symbols.values()}

        for file_path in seen_files:
            try:
                source = file_path.read_text(encoding='utf-8')
                tree = ast.parse(source)
                exact_dups = self._find_duplicate_defs(tree, file_path, source)
                if exact_dups:
                    duplicates.extend(exact_dups)
                    if console:
                        for dup in exact_dups:
                            f1, f2 = dup.functions
                            console.print(
                                f"  [red]⚠ Exact duplicate: {f1.name}() at lines "
                                f"{f1.line} & {f2.line} in {file_path.name}[/red]"
                            )
            except Exception:
                pass

        # ── Step 1: collect candidate functions ──────────────────────
        functions = [
            s for s in self.symbol_table.symbols.values()
            if s.type == SymbolType.FUNCTION
            and s.body_code
            and len(s.body_code.strip().splitlines()) >= self.MIN_BODY_LINES
            and s.name not in self.SKIP_METHODS
        ]

        if console:
            console.print(
                f"  [dim]Comparing {len(functions)} functions for similarity "
                f"(skipped dunder methods)...[/dim]"
            )

        # ── Step 2: generate structural fingerprints ─────────────────
        fingerprints: Dict[str, str] = {}
        for func in functions:
            try:
                fp = self._fingerprint(func.body_code, func.file.suffix)
                fingerprints[func.qualified_name] = fp
            except Exception:
                fingerprints[func.qualified_name] = ""

        # ── Step 3: pairwise comparison ──────────────────────────────
        functions.sort(key=lambda x: x.qualified_name)
        compared_pairs = set()  # track already-compared pairs to avoid duplicates

        for i, func1 in enumerate(functions):
            fp1 = fingerprints.get(func1.qualified_name, "")
            if not fp1:
                continue

            for func2 in functions[i + 1:]:
                fp2 = fingerprints.get(func2.qualified_name, "")
                if not fp2:
                    continue

                # ensure each pair is only compared once
                pair_key = tuple(sorted([func1.qualified_name, func2.qualified_name]))
                if pair_key in compared_pairs:
                    continue
                compared_pairs.add(pair_key)

                # skip methods of the same class (e.g. get vs set)
                if (func1.parent_name and func2.parent_name
                        and func1.parent_name == func2.parent_name):
                    continue

                # structural similarity
                sim = difflib.SequenceMatcher(None, fp1, fp2).ratio()

                if console:
                    console.print(
                        f"  [dim]{func1.name} ({func1.file.name}:{func1.line}) vs "
                        f"{func2.name} ({func2.file.name}:{func2.line}): "
                        f"structural={sim:.0%}[/dim]"
                    )

                if sim < self.AST_SIMILARITY_THRESHOLD:
                    continue

                # ── Step 4: LLM verification ─────────────────────────
                scope = "same-file" if func1.file == func2.file else "cross-file"
                if console:
                    console.print(
                        f"  [cyan]🔍 Candidate ({scope}): "
                        f"{func1.name} ({func1.file.name}:{func1.line}) ↔ "
                        f"{func2.name} ({func2.file.name}:{func2.line}) "
                        f"(structural {sim:.0%})[/cyan]"
                    )

                is_dup = False
                reason = f"Structurally similar ({sim:.0%})"
                suggestion = ""

                if sim >= self.AUTO_CONFIRM_THRESHOLD:
                    # Very high structural match → auto-confirm
                    is_dup = True
                    reason = (f"Near-identical code structure ({sim:.0%} AST match). "
                              f"Both functions have the same control flow, operations, "
                              f"and return pattern — only variable names differ.")
                    suggestion = "Keep one function and remove the other"
                elif self.llm_client:
                    result = await self._llm_verify(func1, func2)
                    is_dup = result.get("are_duplicates", False)
                    if is_dup:
                        reason = result.get("shared_logic_summary", "Same logic")
                        suggestion = result.get("optimization_suggestion", "")
                else:
                    # no LLM → trust structural similarity alone
                    is_dup = True

                if is_dup:
                    dup = DuplicateFunction(
                        functions=[func1, func2],
                        similarity=sim,
                        reason=reason,
                    )
                    dup.suggestion = suggestion
                    duplicates.append(dup)
                    if console:
                        console.print("    [red]⚠ Confirmed duplicate![/red]")
                else:
                    if console:
                        console.print("    [green]✓ Not a duplicate[/green]")

        return duplicates

    # ── Structural Fingerprinting ────────────────────────────────────

    def _fingerprint(self, code: str, extension: str) -> str:
        """Route to language-specific fingerprinter."""
        code = code.strip()
        if not code:
            return ""
        if extension == '.py':
            return self._python_fingerprint(code)
        if extension in ('.c', '.cpp', '.h', '.hpp', '.java'):
            return self._c_java_fingerprint(code)
        return code  # fallback: raw text

    def _python_fingerprint(self, code: str) -> str:
        """
        Walk the AST and collect node-type tokens.
        Enhanced to differentiate:
          - BinOp subtypes  (Add / Mult / Sub / ...)
          - JoinedStr       (f-strings → "FStr")
          - Constants       (str → "ConstStr", num → "ConstNum")
        This makes math functions structurally different from string functions.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return ""

        tokens = []
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp):
                tokens.append(f"BinOp_{type(node.op).__name__}")
            elif isinstance(node, ast.JoinedStr):
                tokens.append("FStr")
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, str):
                    tokens.append("ConstStr")
                elif isinstance(node.value, (int, float)):
                    tokens.append("ConstNum")
                else:
                    tokens.append("Const")
            else:
                tokens.append(type(node).__name__)
        return " ".join(tokens)

    def _c_java_fingerprint(self, code: str) -> str:
        """
        Regex-based keyword sequence for C / C++ / Java.
        Extracts control-flow and type keywords in order.
        """
        keywords = re.findall(
            r'\b(if|else|for|while|do|switch|case|return|break|continue|'
            r'int|float|double|char|void|long|short|unsigned|bool|'
            r'class|struct|public|private|protected|static|const|'
            r'try|catch|throw|new|delete)\b',
            code
        )
        return " ".join(keywords)

    # ── Exact duplicate definitions ──────────────────────────────────

    def _find_duplicate_defs(self, tree, file_path, source: str) -> List[DuplicateFunction]:
        """Find functions defined twice at the same scope in one file."""
        source_lines = source.splitlines()
        scopes: Dict[tuple, list] = {}

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.setdefault(("top", node.name), []).append(node)
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        scopes.setdefault((node.name, item.name), []).append(item)

        duplicates = []
        for (scope, name), nodes in scopes.items():
            if len(nodes) < 2:
                continue
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    n1, n2 = nodes[i], nodes[j]
                    end1 = getattr(n1, 'end_lineno', n1.lineno + 5)
                    end2 = getattr(n2, 'end_lineno', n2.lineno + 5)
                    body1 = "\n".join(source_lines[n1.lineno - 1:end1])
                    body2 = "\n".join(source_lines[n2.lineno - 1:end2])

                    parent = scope if scope != "top" else None
                    sym1 = Symbol(
                        name=name, symbol_type=SymbolType.FUNCTION,
                        file_path=file_path, line=n1.lineno,
                        signature=f"def {name}(...)", body_code=body1,
                        parent_name=parent or "",
                    )
                    sym2 = Symbol(
                        name=name, symbol_type=SymbolType.FUNCTION,
                        file_path=file_path, line=n2.lineno,
                        signature=f"def {name}(...)", body_code=body2,
                        parent_name=parent or "",
                    )
                    dup = DuplicateFunction(
                        functions=[sym1, sym2],
                        similarity=1.0,
                        reason=f"Exact duplicate: {name}() defined twice in {file_path.name}",
                    )
                    dup.suggestion = f"Remove the duplicate definition at line {n2.lineno}"
                    duplicates.append(dup)
        return duplicates

    # ── LLM Verification ─────────────────────────────────────────────

    async def _llm_verify(self, func1: Symbol, func2: Symbol) -> Dict:
        """
        Ask the LLM whether two functions are functionally equivalent.
        Returns dict with 'are_duplicates', 'shared_logic_summary',
        'optimization_suggestion'.
        """
        if not self.llm_client:
            return {"are_duplicates": False}

        prompt = f"""You are a strict code similarity auditor. Determine if these two functions perform THE EXACT SAME TASK.

Function A — "{func1.name}":
```
{func1.body_code}
```

Function B — "{func2.name}":
```
{func2.body_code}
```

INSTRUCTIONS:
1. Describe what Function A does in one sentence.
2. Describe what Function B does in one sentence.
3. Compare: do they perform the same computation/task?
4. If they ARE duplicates, explain in 1-2 sentences WHY they are the same (what shared logic they have).
5. If they are NOT duplicates, explain WHY they differ.

RULES:
- IGNORE: variable names, function names, comments, formatting.
- Two functions that both compute `width * height` (area) with different variable names ARE duplicates.
- Two functions where one computes `a * b` (multiplication) and the other returns `a + b` (addition) are NOT duplicates.
- A function doing math (like `return w * h`) and a function building a string (like `return f"SELECT..."`) are NOT duplicates — completely different domains.
- If both check inputs then do the same math, but one uses `if a < 0 or b < 0` and the other uses two separate `if` statements, they ARE still duplicates.

After your analysis, output your verdict as JSON:

```json
{{
  "are_duplicates": true or false,
  "shared_logic_summary": "Short explanation of WHY they are duplicates or WHY they differ",
  "optimization_suggestion": "how to consolidate (or N/A)"
}}
```"""

        try:
            response = await self.llm_client.generate_completion(prompt)
            return self._parse_llm_json(response)
        except Exception as e:
            # On any failure, conservatively say "not duplicates"
            return {"are_duplicates": False}

    def _parse_llm_json(self, response: str) -> Dict:
        """Extract JSON from LLM response, trying multiple strategies."""
        # Strategy 1: fenced json block
        m = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
        if m:
            return self._safe_json_load(m.group(1))

        # Strategy 2: fenced block without language tag
        m = re.search(r'```\s*(\{.*?\})\s*```', response, re.DOTALL)
        if m:
            return self._safe_json_load(m.group(1))

        # Strategy 3: bare JSON object anywhere in text
        m = re.search(r'(\{[^{}]*"are_duplicates"[^{}]*\})', response, re.DOTALL)
        if m:
            return self._safe_json_load(m.group(1))

        # Strategy 4: keyword extraction fallback
        dup_match = re.search(r'"are_duplicates"\s*:\s*(true|false)', response, re.IGNORECASE)
        if dup_match:
            is_dup = dup_match.group(1).lower() == 'true'
            summary_match = re.search(r'"shared_logic_summary"\s*:\s*"([^"]*)"', response)
            suggestion_match = re.search(r'"optimization_suggestion"\s*:\s*"([^"]*)"', response)
            return {
                "are_duplicates": is_dup,
                "shared_logic_summary": summary_match.group(1) if summary_match else "Similar logic",
                "optimization_suggestion": suggestion_match.group(1) if suggestion_match else "Consolidate",
            }

        return {"are_duplicates": False}

    @staticmethod
    def _safe_json_load(text: str) -> Dict:
        """Parse JSON with boolean normalization."""
        text = text.replace(': True', ': true').replace(': False', ': false')
        text = text.replace(':True', ':true').replace(':False', ':false')
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"are_duplicates": False}
