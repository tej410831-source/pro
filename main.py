"""
Advanced Code Analyzer - Main CLI
"""

import typer
import asyncio
import os
from pathlib import Path
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
import json
import difflib
import warnings
import time

# Suppress Tree-sitter deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="tree_sitter")

app = typer.Typer(help="Advanced Hybrid Static + AI Code Analysis System")
console = Console()

@app.command()
def analyze(
    folder: Path = typer.Argument(..., help="Folder to analyze"),
    output: Path = typer.Option("report.json", "--output", "-o", help="Output report path"),
    vllm_url: str = typer.Option("http://127.0.0.1:1234/v1", "--vllm-url", help="LLM server URL (OpenAI-compatible)"),
    generate_fixes: bool = typer.Option(True, "--fixes/--no-fixes", "--generate-fixes", help="Generate code fixes"),

):
    """
    Analyze code folder with interactive task selection.
    """
    
    if not folder.exists():
        console.print(f"[red]Error: Folder {folder} does not exist[/red]")
        raise typer.Exit(1)
    
    # Interactive Menu
    menu = Table.grid(padding=(0, 1))
    menu.add_column(style="cyan", justify="right")
    menu.add_column(style="white")
    menu.add_row("1.", "Full Analysis (Everything)")
    menu.add_row("2.", "Quick Syntax Check & Fix")
    menu.add_row("3.", "Semantic Bug Detection (LLM)")
    menu.add_row("4.", "Structural Assessment (Call Graph, Dead Code)")
    menu.add_row("5.", "Redundancy & Duplicate Check")

    console.print(Panel(
        menu,
        title="[bold green]Select Analysis Mode[/bold green]",
        expand=False,
        border_style="green"
    ))

    from rich.prompt import Prompt
    choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4", "5"], default="1")
    
    mode_map = {
        "1": "full",
        "2": "syntax",
        "3": "semantic",
        "4": "structural",
        "5": "redundancy"
    }
    analysis_mode = mode_map[choice]

    # Initialize report variables to prevent UnboundLocalError in the report generation phase
    # These are passed to run_analysis and then potentially updated.
    dead_code_symbols = {"functions": [], "variables": []}
    redundant_map = []
    cycles = {"imports": [], "calls": []}
    symbol_table = None # Will be an instance of SymbolTable if structural analysis runs
    
    console.print(f"\n[bold blue]🔍 Starting {analysis_mode.upper()} Analysis:[/bold blue] {folder}\n")
    
    # Run async analysis
    asyncio.run(run_analysis(folder, output, vllm_url, generate_fixes, analysis_mode))

async def run_analysis(folder: Path, output: Path, vllm_url: str, generate_fixes: bool, analysis_mode: str = "full"):
    from core.scanner import FileScanner
    from analyzers.static_syntax import StaticSyntaxAnalyzer, FileSyntaxError
    from analyzers.syntax_fix_generator import SyntaxFixGenerator
    from analyzers.llm_bug_detector import LLMBugDetector
    from analyzers.fix_generator import FixGenerator
    from analyzers.cross_file_redundancy import CrossFileRedundancyDetector
    from core.symbol_table import SymbolTableBuilder, Symbol, SymbolType
    from core.call_graph_builder import CallGraphBuilder
    from analyzers.structural_analyzer import StructuralAnalyzer
    from llm.vllm_client import VLLMClient
    from utils.html_report_generator import HTMLReportGenerator
    
    # Initialize vLLM client
    console.print(f"[cyan]→ Connecting to LLM at {vllm_url}[/cyan]")
    llm_client = VLLMClient(base_url=vllm_url)
    
    # Scan files
    console.print("\nScanning files...")
    scanner = FileScanner(folder)
    files = scanner.scan()
    console.print(f"✓ Found {len(files)} code files\n")
    
    # Phase 2: Static Syntax Check
    syntax_analyzer = StaticSyntaxAnalyzer(llm_client)
    syntax_fix_generator = SyntaxFixGenerator(llm_client)
    
    # Results containers
    valid_files = []
    syntax_errors = {}
    applied_fixes = {}
    bugs = []
    fixes = []
    bugs = []
    fixes = []
    lang_map = {'.py': 'python', '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.java': 'java'}

    # Initialize report variables for all modes
    dead_code_symbols = []
    redundant_map = []
    circular_deps = []
    cycles = {"imports": [], "calls": []}
    symbol_table = None
    
    # ── File-by-File Syntax Flow ──────────────────────────────
    if analysis_mode in ['full', 'syntax']:
        for idx, file_path in enumerate(files, 1):
            # 1. DETECT — scan this file
            is_valid, errors = syntax_analyzer.analyze_file(file_path)
            
            if is_valid:
                valid_files.append(file_path)
                console.print(f"  [green]✅ {idx}/{len(files)} {file_path.name}[/green]")
                continue
            
            # Store errors for the report
            syntax_errors[str(file_path)] = [
                {"line": e.line, "column": e.column, "message": e.message, "parser": e.parser}
                for e in errors
            ]
            
            # 2. SHOW — display errors with code snippet
            console.print(f"\n[bold]{file_path.name}[/bold]  ({idx}/{len(files)})")
            
            for err in errors:
                console.print(f"  [red]Line {err.line}, Col {err.column}:[/red] {err.message} [{err.parser}]")
            console.print()
            
            # 3. FIXING LOOP — if fixes are enabled
            if not generate_fixes:
                console.print("[yellow]Fixes disabled (--no-fixes). Skipping.[/yellow]\n")
                continue
            
            # Interactive fix loop: stay on this file until clean or user skips
            while True:
                # Re-read and re-parse from disk
                current_valid, current_errors = syntax_analyzer.analyze_file(file_path)
                
                if current_valid:
                    applied_fixes[str(file_path)] = True
                    valid_files.append(file_path)
                    console.print(f"\n  [bold green]✅ {file_path.name} — all syntax errors fixed![/bold green]\n")
                    input("  Press Enter to continue to the next file...")
                    break
                
                # Read current code
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_code = f.read()
                
                # 4. SUGGEST — LLM generates fix (shown as suggestion)
                fix_result = await syntax_fix_generator.fix_file_manual_assist(
                    file_path,
                    current_code,
                    current_errors
                )
                
                fixes_made = fix_result.get('fixes_presented', 0)
                
                if fixes_made > 0:
                    # 5. VERIFY — re-parse after user edits
                    console.print(f"\n  [cyan]🔄 Re-checking {file_path.name}...[/cyan]")
                else:
                    console.print(f"\n  [yellow]⏩ Skipping {file_path.name}.[/yellow]\n")
                    break
        
        # Summary
        console.print(f"\n{'─'*50}")
        console.print(f"  [bold]Syntax Check Summary[/bold]")
        console.print(f"  ✓ {len(valid_files)}/{len(files)} files clean")
        if syntax_errors:
            console.print(f"  ✗ {len(syntax_errors)} files had errors")
        if applied_fixes:
            console.print(f"  ✅ {len(applied_fixes)} files fixed")
        console.print(f"{'─'*50}\n")
    else:
        # Non-syntax modes: just silently classify files
        for file_path in files:
            is_valid, _ = syntax_analyzer.analyze_file(file_path)
            if is_valid:
                valid_files.append(file_path)
    
    # Structural Analysis (symbol table + call graph)
    # Phase 2: Structural Analysis
    # Always build symbol table if needed for semantic analysis
    circular_deps = []
    dead_code_data = {}
    symbol_table = None
    parsed_files = {}
    struct_results = None
    
    if analysis_mode in ['full', 'structural', 'redundancy', 'semantic']:
        if analysis_mode == 'structural':
            console.print("\n[bold blue]Phase 4: Structural Analysis[/bold blue]")
        
        console.print("Building symbol table & call graph...")
        from analyzers.structural_analyzer import StructuralAnalyzer
        
        struct_analyzer = StructuralAnalyzer()
        analysis_files = valid_files if valid_files else files
        struct_results = struct_analyzer.analyze_codebase(analysis_files)
        
        symbol_table = struct_results["symbol_table_object"]
        circular_deps = struct_results["circular_dependencies"]
        dead_code_data = struct_results["dead_code"]
        
        # Reconstruct parsed_files for compatibility with Semantic Phase
        for file_path_str, data in struct_results["raw_data"].items():
            fpath = Path(file_path_str)
            module_name = fpath.stem
            
            cg_functions = []
            for f in data.get("functions", []):
                 prefix = f"{f['parent_class']}." if f.get("parent_class") else ""
                 cg_functions.append({
                     "qualified_name": f"{module_name}.{prefix}{f['name']}",
                     "calls": f.get("calls", [])
                 })
            
            parsed_files[fpath] = {
                "functions": cg_functions,
                "calls": data.get("calls", []),
                "imports": data.get("imports", [])
            }
            
        dead_code_symbols = dead_code_data.get("functions", []) + dead_code_data.get("variables", [])
        console.print(f"✓ Symbol table built ({len(symbol_table.symbols)} symbols indexed)\n")
    
    # Only show structural analysis results for 'structural' or 'full' modes, NOT for 'semantic'
    if analysis_mode in ['full', 'structural']:
        unused_vars = results.get("unused_variables", [])
        function_cycles = results.get("function_cycles", [])
        
        # Collect all files analyzed
        analysis_files_set = set()
        for s in dead_code_symbols:
            analysis_files_set.add(s.file)
        for v in unused_vars:
            # Match var file name back to actual Path
            for fp_str in results.get("raw_data", {}).keys():
                if Path(fp_str).name == v["file"]:
                    analysis_files_set.add(Path(fp_str))
        # Also include files from valid_files/files
        for f in (valid_files if valid_files else files):
            analysis_files_set.add(f)
        
        sorted_files = sorted(analysis_files_set, key=lambda p: p.name)
        
        # ═══ Section 1: Unused Variables (file by file) ═══
        console.print("[bold yellow]═══ Unused Variables ═══[/bold yellow]\n")
        total_unused = 0
        for fpath in sorted_files:
            file_vars = [v for v in unused_vars if v["file"] == fpath.name]
            if not file_vars:
                continue
            total_unused += len(file_vars)
            console.print(f"  [bold cyan]📄 {fpath.name}[/bold cyan]")
            for var in file_vars:
                vtype = "global" if var["type"] == "global_variable" else "local"
                console.print(f"    • [yellow]{var['name']}[/yellow] (line {var['line']}) \\[{vtype}]")
            console.print()
        if total_unused == 0:
            console.print("  [green]✓ No unused variables detected.[/green]\n")
        else:
            console.print(f"  [dim]Total: {total_unused} unused variable(s)[/dim]\n")
        
        # ═══ Section 2: Dead Code / Uncalled Functions (file by file) ═══
        console.print("[bold yellow]═══ Uncalled Functions ═══[/bold yellow]\n")
        total_dead = 0
        for fpath in sorted_files:
            file_dead = [s for s in dead_code_symbols if s.file == fpath]
            if not file_dead:
                continue
            total_dead += len(file_dead)
            console.print(f"  [bold cyan]📄 {fpath.name}[/bold cyan]")
            for sym in file_dead:
                parent = f" ({sym.parent_name})" if sym.parent_name else ""
                console.print(f"    • [yellow]{sym.name}[/yellow]{parent} (line {sym.line})")
            console.print()
        if total_dead == 0:
            console.print("  [green]✓ No uncalled functions detected.[/green]\n")
        else:
            console.print(f"  [dim]Total: {total_dead} uncalled function(s)[/dim]\n")
        
        # ═══ Section 3: Recursive / Cycle Calls ═══
        console.print("[bold yellow]═══ Recursive / Cycle Calls ═══[/bold yellow]\n")
        if function_cycles:
            for i, cycle in enumerate(function_cycles, 1):
                cycle_str = " → ".join([f"{s.name} ([dim]{s.file.name}:{s.line}[/dim])" for s in cycle])
                cycle_str += f" → {cycle[0].name}"
                console.print(f"  {i}. {cycle_str}")
            console.print(f"\n  [dim]Total: {len(function_cycles)} cycle(s)[/dim]\n")
        else:
            console.print("  [green]✓ No recursive cycles detected.[/green]\n")
        
        # ═══ Section 4: Circular Imports ═══
        console.print("[bold yellow]═══ Circular Imports ═══[/bold yellow]\n")
        if circular_deps:
            for i, cycle in enumerate(circular_deps, 1):
                cycle_str = " → ".join([str(p) for p in cycle])
                console.print(f"  {i}. {cycle_str}")
            console.print(f"\n  [dim]Total: {len(circular_deps)} circular import(s)[/dim]\n")
        else:
            console.print("  [green]✓ No circular imports detected.[/green]\n")
        console.print()
    
    # Phase 3: Semantic Bug Detection
    if analysis_mode in ['full', 'semantic']:
        console.print("\n[bold magenta]═══ Phase 3: Semantic Bug Detection ═══[/bold magenta]\n")
        from analyzers.static_bug_detector import StaticBugDetector
        static_bug_detector = StaticBugDetector()
        bug_detector = LLMBugDetector(llm_client)
        fix_generator = FixGenerator(llm_client)
        from rich import box
        
        if 'lang_map' not in locals():
            lang_map = {'.py': 'python'}

        analysis_files = valid_files if valid_files else files
        total_bugs_found = 0
        total_fixes_applied = 0

        for file_idx, file_path in enumerate(analysis_files, 1):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                language = lang_map.get(file_path.suffix, 'python')
                file_bugs_count = 0
                
                # 1. Static Bug Detection (silent — collected for report)
                if file_path.suffix == '.py':
                    static_issues = static_bug_detector.analyze_file(file_path)
                    for issue in static_issues:
                        bugs.append({
                            "file": str(file_path),
                            "type": "static_logic_bug",
                            "severity": "critical",
                            "line": issue["line"],
                            "description": issue["message"],
                            "suggestion": "Define variable or fix reference."
                        })
                
                # 2. Context-Aware Function-by-Function Analysis
                if symbol_table and len(file_symbols := symbol_table.get_symbols_in_file(file_path)) > 0:
                    # Count analyzable symbols (functions + classes)
                    func_symbols = [s for s in file_symbols if s.type == SymbolType.FUNCTION]
                    class_symbols = [s for s in file_symbols if s.type == SymbolType.CLASS]
                    total_symbols = len(func_symbols) + len(class_symbols)
                    
                    # ── File Header ──
                    console.print(Panel(
                        f"[bold white]{file_path.name}[/bold white]\n"
                        f"[dim]{file_path}[/dim]\n"
                        f"[cyan]{len(func_symbols)} functions[/cyan], [cyan]{len(class_symbols)} classes[/cyan]",
                        title=f"[bold yellow]📄 File {file_idx}/{len(analysis_files)}[/bold yellow]",
                        border_style="yellow",
                        box=box.DOUBLE
                    ))
                    
                    # Extract Module-Level Context (once per file)
                    import ast
                    global_vars_str = ""
                    imports_str = ""
                    try:
                        tree = ast.parse(code)
                        imports = []
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    imports.append(f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""))
                            elif isinstance(node, ast.ImportFrom):
                                module = node.module or ""
                                names = ", ".join([alias.name + (f" as {alias.asname}" if alias.asname else "") for alias in node.names])
                                imports.append(f"from {module} import {names}")
                        imports_str = "\n".join(imports)
                        
                        globals_list = []
                        for node in tree.body:
                            if isinstance(node, ast.Assign):
                                for target in node.targets:
                                    if isinstance(target, ast.Name):
                                        try:
                                            val_str = ast.unparse(node.value) if hasattr(ast, 'unparse') else "..."
                                        except:
                                            val_str = "..."
                                        globals_list.append(f"{target.id} = {val_str}")
                        global_vars_str = "\n".join(globals_list)
                    except:
                        pass
                    
                    # ── Analyze each symbol one-by-one ──
                    sym_index = 0
                    all_symbols = func_symbols + class_symbols
                    
                    for sym in all_symbols:
                        sym_index += 1
                        sym_label = "function" if sym.type == SymbolType.FUNCTION else "class"
                        parent_label = f" ({sym.parent_name})" if sym.parent_name else ""
                        
                        console.print(f"\n  [bold cyan]🔍 [{sym_index}/{total_symbols}] Analyzing {sym_label}: [white]{sym.name}[/white]{parent_label}[/bold cyan]")
                        
                        # Build context for this symbol
                        class_ctx = ""
                        dep_hints = ""
                        
                        if sym.type == SymbolType.FUNCTION:
                            # Class context
                            if sym.parent_name:
                                class_syms = [s for s in file_symbols if s.name == sym.parent_name and s.type == SymbolType.CLASS]
                                if class_syms:
                                    cls = class_syms[0]
                                    other_methods = [s.signature for s in file_symbols if s.parent_name == sym.parent_name and s.name != sym.name]
                                    class_ctx = f"Class: {cls.name}\nAttributes: {', '.join(cls.attributes)}\nOther methods: {', '.join(other_methods)}"
                            
                            # Dependency hints
                            sym_data = next((f for f in parsed_files[file_path]["functions"] if f["qualified_name"].endswith(f".{sym.name}")), None)
                            if sym_data:
                                for call in sym_data.get("calls", []):
                                    all_syms_found = symbol_table.find_symbols_by_name(call)
                                    for ext in all_syms_found[:3]:
                                        if ext.qualified_name != sym.qualified_name:
                                            location = "cross-file" if ext.file != file_path else "same-file"
                                            dep_hints += f"- {ext.qualified_name} ({location}): {ext.signature}\n"
                        
                        # LLM Analysis for this single symbol
                        sym_bugs = await bug_detector.analyze_symbol(
                            sym.name, sym.body_code, language, file_path,
                            class_context=class_ctx,
                            dependency_hints=dep_hints,
                            global_vars=global_vars_str, imports_list=imports_str,
                            verbose=verbose
                        )
                        
                        if not sym_bugs:
                            console.print(f"  [green]  ✅ No issues found in {sym.name}[/green]")
                        else:
                            file_bugs_count += len(sym_bugs)
                            
                            # Collect all bugs for report
                            for bug in sym_bugs:
                                bugs.append({
                                    "file": str(file_path),
                                    "type": bug.type,
                                    "severity": bug.severity,
                                    "line": bug.line,
                                    "description": bug.description,
                                    "suggestion": bug.suggestion
                                })
                            
                            # ── Show ALL bugs for this function in one panel ──
                            bug_entries = []
                            combined_description = []
                            combined_suggestion = []
                            for i, bug in enumerate(sym_bugs, 1):
                                bug_entries.append(
                                    f"[bold red]{i}. [{bug.severity.upper()}] {bug.type.replace('_', ' ').title()}[/bold red]\n"
                                    f"   Line {bug.line}: {bug.description}\n"
                                    f"   [green]Fix:[/green] {bug.suggestion}"
                                )
                                combined_description.append(f"{i}. (Line {bug.line}) {bug.description}")
                                combined_suggestion.append(f"{i}. {bug.suggestion}")
                            
                            bug_panel_content = Group(
                                Markdown(f"### {len(sym_bugs)} issue(s) found in `{sym.name}()`"),
                                *[f"\n{entry}" for entry in bug_entries]
                            )
                            console.print(Panel(bug_panel_content, title=f"[bold red]🐛 BUGS in {sym.name}()[/bold red]", border_style="red"))
                            
                            # ── Generate ONE combined patch for all bugs ──
                            if generate_fixes:
                                global_context = syntax_fix_generator._extract_global_context(code)
                                all_desc = "\n".join(combined_description)
                                all_sugg = "\n".join(combined_suggestion)
                                
                                # Pass the function's body code, not the entire file
                                func_code = sym.body_code if sym.body_code else code
                                
                                console.print(f"  [cyan]⚡ Generating combined patch for {len(sym_bugs)} issue(s)...[/cyan]")
                                fix = await fix_generator.generate_fix(
                                    "multiple_bugs", "high", file_path, sym_bugs[0].line,
                                    func_code, language, all_desc, all_sugg, global_context
                                )
                                
                                if fix:
                                    # Show the COMPLETE corrected function code
                                    fix_info = Group(
                                        Markdown(f"### Corrected `{sym.name}()` — {len(sym_bugs)} bug(s) fixed"),
                                        Syntax(fix.fixed_code, language, theme="monokai", line_numbers=True),
                                        f"\n[bold blue]Explanation:[/bold blue] {fix.explanation}"
                                    )
                                    console.print(Panel(
                                        fix_info,
                                        title="[bold blue]PROPOSED FIX[/bold blue]",
                                        border_style="blue",
                                        box=box.ROUNDED
                                    ))
                                else:
                                    console.print(f"  [yellow]✗ LLM could not generate a valid fix.[/yellow]")
                        
                        # ── Wait for user before moving to next function ──
                        if sym_index < total_symbols:
                            input("\n  Press Enter to continue to next function...")
                
                else:
                    # Fallback: no symbol table, analyze whole file
                    console.print(Panel(
                        f"[bold white]{file_path.name}[/bold white] [dim](whole-file analysis)[/dim]",
                        title=f"[bold yellow]📄 File {file_idx}/{len(analysis_files)}[/bold yellow]",
                        border_style="yellow"
                    ))
                    
                    detected_bugs = await bug_detector.analyze_code(file_path, code, language, verbose=verbose)
                    file_bugs_count = len(detected_bugs)
                    
                    for bug in detected_bugs:
                        bugs.append({
                            "file": str(file_path),
                            "type": bug.type,
                            "severity": bug.severity,
                            "line": bug.line,
                            "description": bug.description,
                            "suggestion": bug.suggestion
                        })
                        
                        code_lines = code.splitlines()
                        start_line = max(0, bug.line - 2)
                        end_line = min(len(code_lines), bug.line + 1)
                        snippet = "\n".join(code_lines[start_line:end_line])
                        
                        bug_info = Group(
                            Markdown(f"### {bug.type.replace('_', ' ').title()} ({bug.severity})"),
                            f"[bold red]Location:[/bold red] {file_path.name}:{bug.line}",
                            f"[bold red]Issue:[/bold red] {bug.description}",
                            f"[bold green]Suggestion:[/bold green] {bug.suggestion}",
                            Syntax(snippet, language, theme="monokai", line_numbers=True, start_line=start_line+1, highlight_lines={bug.line})
                        )
                        console.print(Panel(bug_info, title=f"[bold red]🐛 BUG DETECTED[/bold red]", border_style="red"))
                    
                    if not detected_bugs:
                        console.print(f"  [green]✅ No semantic bugs found[/green]")
                
                # ── File Completion ──
                total_bugs_found += file_bugs_count
                console.print(f"\n{'─'*60}")
                if file_bugs_count == 0:
                    console.print(f"[bold green]✓ {file_path.name}: Clean — no semantic bugs[/bold green]")
                else:
                    console.print(f"[bold yellow]✓ {file_path.name}: {file_bugs_count} bug(s) found[/bold yellow]")
                console.print(f"{'─'*60}\n")
                    
            except Exception as e:
                console.print(f"  [red]✗ Error analyzing {file_path.name}: {e}[/red]\n")
        
        console.print(f"[bold magenta]═══ Semantic Analysis Complete ═══[/bold magenta]")
        console.print(f"  Total bugs: {total_bugs_found} | Fixes applied: {total_fixes_applied}\n")
    
    # ═══════════════════════════════════════════════════════
    # Phase 5: Redundancy & Duplicate Detection
    # ═══════════════════════════════════════════════════════
    duplicates = []
    if analysis_mode in ['full', 'redundancy']:
        console.print("\n[bold magenta]Phase 5: Redundancy & Duplicate Detection[/bold magenta]\n")
        if symbol_table:
            redundancy_detector = CrossFileRedundancyDetector(symbol_table, llm_client)
            duplicates = await redundancy_detector.detect_duplicates(console=console)
            
            console.print(f"\n[bold yellow]═══ Redundant / Duplicate Functions ═══[/bold yellow]\n")
            
            if duplicates:
                for idx, dup in enumerate(duplicates, 1):
                    f1, f2 = dup.functions[0], dup.functions[1]
                    same_file = f1.file == f2.file
                    scope = "same-file" if same_file else "cross-file"
                    
                    console.print(f"  [bold red]#{idx}[/bold red] [bold]{f1.name}[/bold] ↔ [bold]{f2.name}[/bold]  [dim]({scope}, {dup.similarity:.0%} match)[/dim]")
                    console.print(f"    📄 {f1.file.name}:{f1.line} → [yellow]{f1.name}[/yellow]({f1.signature.split('(')[1] if '(' in f1.signature else ''})")
                    console.print(f"    📄 {f2.file.name}:{f2.line} → [yellow]{f2.name}[/yellow]({f2.signature.split('(')[1] if '(' in f2.signature else ''})")
                    console.print(f"    💡 [cyan]{dup.reason}[/cyan]")
                    if hasattr(dup, 'suggestion') and dup.suggestion:
                        console.print(f"    🔧 [green]{dup.suggestion}[/green]")
                    console.print()
                
                console.print(f"  [dim]Total: {len(duplicates)} duplicate pair(s) found[/dim]\n")
            else:
                console.print("  [green]✓ No redundant or duplicate functions detected.[/green]\n")
        else:
            console.print("[red]  ✗ Redundancy detection requires structural analysis first. Skipping.[/red]\n")
    

    """
    # Summary Table
    table = Table(title="Analysis Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    
    table.add_row("Total Files", str(len(files)))
    table.add_row("Valid Files", str(len(valid_files)))
    table.add_row("Syntax Errors", str(len(syntax_errors)))
    table.add_row("Syntax Fixes (vLLM)", str(len(syntax_fixes)))
    table.add_row("Bugs Found (vLLM)", str(len(bugs)))
    table.add_row("Bug Fixes Generated", str(len(fixes)))
    table.add_row("Circular Dependencies", str(len(circular_deps)))
    table.add_row("Dead Code Functions", str(len(dead_code_symbols)))
    table.add_row("Duplicate Groups", str(len(duplicates)))
    
    console.print(table)
    """

if __name__ == "__main__":
    app()
