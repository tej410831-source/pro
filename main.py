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
    lang_map = {'.py': 'python', '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.java': 'java'}
    
    # ── File-by-File Syntax Flow ──────────────────────────────
    if analysis_mode in ['full', 'syntax']:
        for idx, file_path in enumerate(files, 1):
            # 1. DETECT — scan this file
            is_valid, errors = syntax_analyzer.analyze_file(file_path)
            
            if is_valid:
                valid_files.append(file_path)
                console.print(f"  [green]✅ {idx}/{len(files)} {file_path.name}[/green]")
                continue
            
            # ── This file has errors → clear screen and focus on it ──
            os.system('cls' if os.name == 'nt' else 'clear')
            
            # Store errors for the report
            syntax_errors[str(file_path)] = [
                {"line": e.line, "column": e.column, "message": e.message, "parser": e.parser}
                for e in errors
            ]
            
            # 2. SHOW — display errors with code snippet
            console.print(Panel(
                f"[bold]{file_path.name}[/bold]  ({idx}/{len(files)})",
                title="[bold red]SYNTAX ERRORS[/bold red]",
                border_style="red",
                expand=False
            ))
            
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
    # Phase 3 & 4: Structural Analysis
    # Always build symbol table if needed for semantic analysis
    circular_deps = []
    dead_code_data = {}
    symbol_table = None
    parsed_files = {}
    struct_results = None
    
    if analysis_mode in ['full', 'structural', 'redundancy', 'semantic']:
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
            
        console.print(f"✓ Symbol table built ({len(symbol_table.symbols)} symbols indexed)\n")
    
    # Only show structural analysis results for 'structural' or 'full' modes
    if analysis_mode in ['full', 'structural'] and struct_results:
        console.print("\n[bold blue]Phase 4: Dead Code & Cycle Detection[/bold blue]")
        
        dead_data = struct_results.get("dead_code", {})
        cycle_data = struct_results.get("cycles", {})
        stats = struct_results.get("stats", {})

        # Print Text Report as requested by user
        print("\n" + "="*70)
        print("STATIC CODE ANALYSIS REPORT")
        print("="*70)
        
        # Summary
        unused_funcs = dead_data.get("functions", [])
        unused_vars = dead_data.get("variables", [])
        total_unused = len(unused_funcs) + len(unused_vars)
        
        import_cycles = cycle_data.get("imports", [])
        call_cycles = cycle_data.get("calls", [])
        total_cycles = len(import_cycles) + len(call_cycles)
        
        print(f"\nSUMMARY:")
        print(f"  Total symbols analyzed: {stats.get('total_symbols', 0)}")
        print(f"  Total unused symbols: {total_unused}")
        print(f"  Total cycles detected: {total_cycles}")
        
        # Unused Functions
        print(f"\n{'='*70}")
        print(f"UNUSED FUNCTIONS/METHODS ({len(unused_funcs)})")
        print(f"{'='*70}")
        for symbol in unused_funcs[:20]:
            print(f"  [{symbol.language if hasattr(symbol, 'language') else 'unknown'}] {symbol.name} at {symbol.file}:{symbol.line}")
        if len(unused_funcs) > 20:
            print(f"  ... and {len(unused_funcs) - 20} more")
        
        # Unused Variables
        print(f"\n{'='*70}")
        print(f"UNUSED VARIABLES ({len(unused_vars)})")
        print(f"{'='*70}")
        for symbol in unused_vars[:20]:
            print(f"  [{symbol.language if hasattr(symbol, 'language') else 'unknown'}] {symbol.name} at {symbol.file}:{symbol.line}")
        if len(unused_vars) > 20:
            print(f"  ... and {len(unused_vars) - 20} more")
        
        # Import Cycles
        print(f"\n{'='*70}")
        print(f"IMPORT CYCLES ({len(import_cycles)})")
        print(f"{'='*70}")
        for cycle in import_cycles:
            print(f"  {cycle}")
        
        # Call Cycles
        print(f"\n{'='*70}")
        print(f"CALL CYCLES ({len(call_cycles)})")
        print(f"{'='*70}")
        for cycle in call_cycles:
            print(f"  {cycle}")
        
        print("\n" + "="*70)


    
    # Semantic Bug Detection
    if analysis_mode in ['full', 'semantic']:
        console.print("\nSemantic bug detection...")
        from analyzers.static_bug_detector import StaticBugDetector
        static_bug_detector = StaticBugDetector()
        bug_detector = LLMBugDetector(llm_client)
        fix_generator = FixGenerator(llm_client)
        
        if 'lang_map' not in locals():
            lang_map = {'.py': 'python'}

        # Interactive Semantic Analysis Loop
        from rich.prompt import Prompt
        from analyzers.fix_generator import FixGenerator
        
        # Ensure helper objects are ready
        fix_gen = FixGenerator(llm_client)
        if 'struct_analyzer' not in locals():
            from analyzers.structural_analyzer import StructuralAnalyzer
            struct_analyzer = StructuralAnalyzer()

        # Iterate through files interactively
        analysis_queue = valid_files if valid_files else files
        
        for file_idx, file_path in enumerate(analysis_queue, 1):
            if file_path.name in ['.gitignore', 'requirements.txt']: continue
            
            # Clear screen for focus
            os.system('cls' if os.name == 'nt' else 'clear')
            console.print(Panel(f"[bold]Analyzing File {file_idx}/{len(analysis_queue)}:[/bold] {file_path.name}", style="cyan"))
            
            analyzed_symbols = set()
            
            while True: # Function Loop (supports re-parsing after edits)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                except Exception as e:
                    console.print(f"[red]Error reading {file_path.name}: {e}[/red]")
                    break
                
                # Dynamic re-parse of the single file
                parse_result = struct_analyzer.parser.parse(code, file_path)
                functions = parse_result.get("functions", [])
                
                # Context extraction (Imports & Globals) form parsed result
                imports_str = ""
                global_vars_str = ""
                
                # Imports
                parsed_imports = parse_result.get("imports", [])
                if parsed_imports:
                    imp_lines = []
                    for imp in parsed_imports:
                        if isinstance(imp, dict):
                            mod = imp.get("module", "")
                            nms = imp.get("names", [])
                            if nms: imp_lines.append(f"from {mod} import {', '.join(nms)}")
                            elif mod: imp_lines.append(mod)
                        else: imp_lines.append(str(imp))
                    imports_str = "\n".join(imp_lines)
                
                parsed_globals = parse_result.get("global_vars", [])
                if parsed_globals:
                    global_vars_str = "\n".join(parsed_globals)
                
                # Analyze Globals First (if not already done for this file)
                if global_vars_str and "Global Variables" not in analyzed_symbols:
                    analyzed_symbols.add("Global Variables")
                    # console.print(f"  [dim]Scanning Global Variables...[/dim]")
                    
                    language = lang_map.get(file_path.suffix, 'python')
                    
                    global_bugs = await bug_detector.analyze_symbol(
                        "Global Variables", global_vars_str, language, file_path,
                        class_context="", dependency_hints="", 
                        global_vars="", imports_list=imports_str
                    )
                    
                    global_priority_bugs = [b for b in global_bugs if b.severity.lower() in ['critical', 'high']]
                    
                    if global_priority_bugs:
                         for bug in global_priority_bugs:
                             console.print("\n" + "─"*50)
                             console.print(f"[bold red]BUG DETECTED[/bold red] in [cyan]Global Variables[/cyan]")
                             console.print(f"[red]Issue:[/red] {bug.description}")
                             console.print(f"[green]Suggestion:[/green] {bug.suggestion}")
                         
                         Prompt.ask("\n[bold]Press Enter to continue to functions...[/bold]", choices=[""], default="")
                
                # Find next unanalyzed function
                target_func = None
                for f in functions:
                    if f['name'] not in analyzed_symbols:
                        target_func = f
                        break
                
                if not target_func:
                    break # File complete
                
                sym_name = target_func['name']
                analyzed_symbols.add(sym_name)
                
                # Build Class Context if needed
                class_ctx = ""
                if target_func.get("parent_class"):
                    cls_name = target_func["parent_class"]
                    cls_data = next((c for c in parse_result.get("classes", []) if c["name"] == cls_name), None)
                    if cls_data:
                        skel = [f"class {cls_name} {{"]
                        if cls_data.get("attributes"):
                            skel.append("    // Fields")
                            for a in cls_data["attributes"]: skel.append(f"    {a};")
                        
                        skel.append("    // ... other methods ...")
                        skel.append(f"    // === TARGET: {sym_name} ===")
                        for l in target_func["body_code"].splitlines():
                            skel.append(f"    {l}")
                        skel.append("}")
                        class_ctx = "\n".join(skel)

                # Build Dependency Hints (Callers/Callees) - using global symbol table (snapshot)
                dep_hints = ""
                if target_func.get("calls"):
                    dep_hints += "Functions this calls:\n" + ", ".join(target_func["calls"]) + "\n"

                # Analyze
                # console.print(f"  [dim]Scanning {sym_name}...[/dim]")
                language = lang_map.get(file_path.suffix, 'python')
                
                bugs = await bug_detector.analyze_symbol(
                    sym_name, target_func["body_code"], language, file_path,
                    class_context=class_ctx, dependency_hints=dep_hints,
                    global_vars=global_vars_str, imports_list=imports_str
                )
                
                # STIFF FILTER: Only show CRITICAL/HIGH severity bugs as requested
                priority_bugs = [b for b in bugs if b.severity.lower() in ['critical', 'high']]
                
                if not priority_bugs:
                    continue

                # BUG FOUND
                for bug in priority_bugs:
                    console.print("\n" + "─"*50)
                    console.print(f"[bold red]BUG DETECTED[/bold red] in [cyan]{sym_name}[/cyan]")
                    console.print(f"[red]Issue:[/red] {bug.description}")
                    console.print(f"[green]Suggestion:[/green] {bug.suggestion}")
                    
                    # Generate Fix
                    console.print("[dim]Generating fix...[/dim]")
                    fix_obj = await fix_gen.generate_fix(
                        bug.type, bug.severity, file_path, bug.line,
                        target_func["body_code"], language, bug.description, bug.suggestion,
                        global_context=f"{imports_str}\n{global_vars_str}"
                    )
                    
                    if fix_obj and fix_obj.fixed_code:
                        # Show Diff
                        console.print(Panel(
                            Syntax(fix_obj.fixed_code, language, theme="monokai", line_numbers=True),
                            title="[bold green]PROPOSED FIX[/bold green]", expand=False
                        ))
                        
                        choice = Prompt.ask(
                            "\n[bold]Action [[white]Enter[/white]=Apply, [white]s[/white]=Skip][/bold]", 
                            choices=["apply", "skip"], 
                            default="apply"
                        )
                        
                        if choice == "apply":
                            # Apply Fix: Replace function body in file
                            start_byte = target_func.get("start_byte")
                            end_byte = target_func.get("end_byte")
                            
                            # Python fallback: use line numbers if bytes missing
                            if start_byte is None and target_func.get("line"):
                                start_line = target_func["line"] - 1 # 0-indexed
                                end_line = target_func.get("end_line")
                                if end_line:
                                    lines = code.splitlines(keepends=True)
                                    # Replace lines
                                    new_code = "".join(lines[:start_line]) + fix_obj.fixed_code + "\n" + "".join(lines[end_line:])
                                    with open(file_path, 'w', encoding='utf-8') as f:
                                        f.write(new_code)
                                    console.print("[bold green]✓ Fix Applied![/bold green]")
                                    time.sleep(1)
                                    # Break inner loop to re-parse file (offsets changed)
                                    break 
                                else:
                                    console.print("[bold red]Cannot apply Python fix: missing end_line info.[/bold red]")
                            
                            elif start_byte is not None and end_byte is not None:
                                try:
                                    code_bytes = code.encode('utf-8')
                                    fix_bytes = fix_obj.fixed_code.encode('utf-8')
                                    
                                    new_bytes = code_bytes[:start_byte] + fix_bytes + code_bytes[end_byte:]
                                    new_code = new_bytes.decode('utf-8')
                                    
                                    with open(file_path, 'w', encoding='utf-8') as f:
                                        f.write(new_code)
                                        
                                    console.print("[bold green]✓ Fix Applied![/bold green]")
                                    time.sleep(1)
                                    break # Re-parse
                                except Exception as e:
                                     console.print(f"[red]Error applying fix: {e}[/red]")

                        # elif choice == "skip": pass # Implicit continue
                    else:
                        console.print("[yellow]Could not generate a fix code block.[/yellow]")
                        
                if target_func is None: # explicit next file
                    break
        
        console.print("[bold green]Semantic Analysis Complete.[/bold green]")

        # OLD LOOP DISABLED
        for file_path in []: # (valid_files if valid_files else files):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                console.print(f"  🔍 Analyzing {file_path.name}...")
                
                # 1. Static Bug Detection (Deterministic)
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
                
                # 2. Detect bugs using vLLM (Semantic)
                language = lang_map.get(file_path.suffix, file_path.suffix.lstrip('.'))
                detected_bugs = []
                
                # Force focused analysis if symbol table is available for better context
                if symbol_table and len(file_symbols := symbol_table.get_symbols_in_file(file_path)) > 0:
                    console.print(f"    [dim]Context-Aware Audit: Analyzing {len(file_symbols)} symbols...[/dim]")
                    
                    # Extract Module-Level Context from parsed data
                    global_vars_str = ""
                    imports_str = ""
                    try:
                        file_data = results.get("raw_data", {}).get(str(file_path), {})
                        
                        # Imports: from parsed data (works for all languages)
                        parsed_imports = file_data.get("imports", [])
                        if parsed_imports:
                            import_lines = []
                            for imp in parsed_imports:
                                if isinstance(imp, dict):
                                    module = imp.get("module", "")
                                    names = imp.get("names", [])
                                    if names:
                                        import_lines.append(f"from {module} import {', '.join(names)}")
                                    elif module:
                                        import_lines.append(module)
                                else:
                                    import_lines.append(str(imp))
                            imports_str = "\n".join(import_lines)
                        
                        # Global variables: from parsed data
                        parsed_globals = file_data.get("global_vars", [])
                        if parsed_globals:
                            global_vars_str = "\n".join(parsed_globals)
                        
                        # Python fallback: ast-based extraction for richer context
                        if file_path.suffix == '.py' and not imports_str:
                            import ast as ast_mod
                            py_tree = ast_mod.parse(code)
                            py_imports = []
                            for node in ast_mod.walk(py_tree):
                                if isinstance(node, ast_mod.Import):
                                    for alias in node.names:
                                        py_imports.append(f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""))
                                elif isinstance(node, ast_mod.ImportFrom):
                                    module = node.module or ""
                                    names = ", ".join([alias.name + (f" as {alias.asname}" if alias.asname else "") for alias in node.names])
                                    py_imports.append(f"from {module} import {names}")
                            imports_str = "\n".join(py_imports)
                            
                            py_globals = []
                            for node in py_tree.body:
                                if isinstance(node, ast_mod.Assign):
                                    for target in node.targets:
                                        if isinstance(target, ast_mod.Name):
                                            try:
                                                val_str = ast_mod.unparse(node.value) if hasattr(ast_mod, 'unparse') else "..."
                                            except:
                                                val_str = "..."
                                            py_globals.append(f"{target.id} = {val_str}")
                            global_vars_str = "\n".join(py_globals)
                    except:
                        pass
                    
                    for sym in file_symbols:
                        if sym.type == SymbolType.FUNCTION:
                            # 1. Build structured Class Skeleton if function is in a class
                            class_ctx = ""
                            if sym.parent_name:
                                class_syms = [s for s in file_symbols if s.name == sym.parent_name and s.type == SymbolType.CLASS]
                                if class_syms:
                                    cls = class_syms[0]
                                    # Build code-like skeleton
                                    skeleton_lines = [f"class {cls.name} {{"]
                                    
                                    # Class fields/attributes
                                    if cls.attributes:
                                        skeleton_lines.append("    // Fields")
                                        for attr in cls.attributes:
                                            skeleton_lines.append(f"    {attr};")
                                        skeleton_lines.append("")
                                    
                                    # Other method signatures (before target)
                                    other_before = []
                                    other_after = []
                                    found_target = False
                                    all_methods = [s for s in file_symbols if s.parent_name == sym.parent_name and s.type == SymbolType.FUNCTION]
                                    for m in all_methods:
                                        if m.name == sym.name:
                                            found_target = True
                                            continue
                                        if not found_target:
                                            other_before.append(m)
                                        else:
                                            other_after.append(m)
                                    
                                    if other_before:
                                        for m in other_before:
                                            skeleton_lines.append(f"    {m.signature};")
                                        skeleton_lines.append("")
                                    
                                    # Target function — full code
                                    skeleton_lines.append(f"    // === TARGET FUNCTION ===")
                                    for line in sym.body_code.splitlines():
                                        skeleton_lines.append(f"    {line}")
                                    skeleton_lines.append("")
                                    
                                    # Other method signatures (after target)
                                    if other_after:
                                        for m in other_after:
                                            skeleton_lines.append(f"    {m.signature};")
                                        skeleton_lines.append("")
                                    
                                    skeleton_lines.append("}")
                                    class_ctx = "\n".join(skeleton_lines)
                            
                            # 2. Build call graph context (callees + callers)
                            dep_hints = ""
                            
                            # 2a. What this function CALLS (callees)
                            sym_data = next((f for f in parsed_files[file_path]["functions"] if f["qualified_name"].endswith(f".{sym.name}")), None)
                            callees_list = []
                            if sym_data:
                                for call in sym_data.get("calls", []):
                                    all_syms = symbol_table.find_symbols_by_name(call)
                                    for ext in all_syms[:3]:
                                        if ext.qualified_name != sym.qualified_name:
                                            location = "cross-file" if ext.file != file_path else "same-file"
                                            callees_list.append(f"- {ext.qualified_name} ({location}): {ext.signature}")
                            if callees_list:
                                dep_hints += "Functions this calls:\n" + "\n".join(callees_list) + "\n"
                            
                            # 2b. Which functions CALL this function (callers — reverse lookup)
                            callers_list = []
                            for fp_str, fp_data in parsed_files.items():
                                for func_info in fp_data.get("functions", []):
                                    if sym.name in func_info.get("calls", []):
                                        caller_name = func_info["qualified_name"]
                                        if caller_name != sym.qualified_name:
                                            loc = "cross-file" if str(file_path) != fp_str else "same-file"
                                            caller_sym = symbol_table.find_symbols_by_name(func_info["qualified_name"].split(".")[-1])
                                            sig = caller_sym[0].signature if caller_sym else caller_name
                                            callers_list.append(f"- {caller_name} ({loc}): {sig}")
                            if callers_list:
                                dep_hints += "Called by:\n" + "\n".join(callers_list) + "\n"
                            
                            sym_bugs = await bug_detector.analyze_symbol(
                                sym.name, sym.body_code, language, file_path, 
                                class_context=class_ctx, dependency_hints=dep_hints,
                                global_vars=global_vars_str, imports_list=imports_str
                            )
                            # Show progress
                            console.print(f"    [dim]Analyzed {sym.name}...[/dim]")
                            detected_bugs.extend(sym_bugs)
                        
                        elif sym.type == SymbolType.CLASS:
                            inheritance_hints = ""
                            
                            class_bugs = await bug_detector.analyze_symbol(
                                sym.name, sym.body_code, language, file_path,
                                class_context="",
                                dependency_hints=inheritance_hints,
                                global_vars=global_vars_str, imports_list=imports_str
                            )
                            detected_bugs.extend(class_bugs)
                    
                    # 3. Analyze global variables for bugs (if any exist)
                    if global_vars_str:
                        global_bugs = await bug_detector.analyze_symbol(
                            "Global Variables", global_vars_str, language, file_path,
                            class_context="",
                            dependency_hints="",
                            global_vars="", imports_list=imports_str
                        )
                        detected_bugs.extend(global_bugs)
                else:
                    detected_bugs = await bug_detector.analyze_code(file_path, code, language)
                
                for bug in detected_bugs:
                    bugs.append({
                        "file": str(file_path),
                        "type": bug.type,
                        "severity": bug.severity,
                        "line": bug.line,
                        "description": bug.description,
                        "suggestion": bug.suggestion
                    })
                    
                    # Get code snippet for the bug line
                    code_lines = code.splitlines()
                    start_line = max(0, bug.line - 2)
                    end_line = min(len(code_lines), bug.line + 1)
                    snippet = "\n".join(code_lines[start_line:end_line])
                    
                    # Display bug summary in a Panel
                    bug_info = Group(
                        Markdown(f"### {bug.type.replace('_', ' ').title()} ({bug.severity})"),
                        f"[bold red]Location:[/bold red] {file_path.name}:{bug.line}",
                        f"[bold red]Issue:[/bold red] {bug.description}",
                        f"[bold green]Suggestion:[/bold green] {bug.suggestion}",
                        Markdown("#### Affected Code:"),
                        Syntax(snippet, language, theme="monokai", line_numbers=True, start_line=start_line+1, highlight_lines={bug.line})
                    )
                    console.print(Panel(bug_info, title=f"[bold red]BUG DETECTED[/bold red]", border_style="red"))
                    
                    # Auto-generate patch (no user permission needed)
                    if generate_fixes:
                        global_context = syntax_fix_generator._extract_global_context(code)
                        
                        console.print(f"  [cyan]⚡ Auto-generating patch for line {bug.line}...[/cyan]")
                        fix = await fix_generator.generate_fix(
                            bug.type, bug.severity, file_path, bug.line,
                            code, language, bug.description, bug.suggestion, global_context
                        )
                        
                        if fix:
                            fixed_lines = fix.fixed_code.splitlines()
                            start_idx = max(0, bug.line - 4)
                            end_idx = min(len(fixed_lines), bug.line + 5)
                            snippet = "\n".join(fixed_lines[start_idx:end_idx])
                            
                            fix_info = Group(
                                Markdown("### Proposed Code Change"),
                                Syntax(snippet, language, theme="monokai", line_numbers=True, start_line=start_idx+1),
                                f"\n[bold blue]Explanation:[/bold blue] {fix.explanation}"
                            )
                            from rich import box
                            console.print(Panel(
                                fix_info, 
                                title="[bold blue]PROPOSED FIX[/bold blue]", 
                                border_style="blue",
                                box=box.ROUNDED
                            ))
                            
                            if typer.confirm(f"  Apply this patch and proceed to next bug?", default=True):
                                apply_result = syntax_fix_generator.apply_fix_to_file(
                                    file_path,
                                    fix.fixed_code,
                                    create_backup=True
                                )
                                
                                if apply_result['success']:
                                    fixes.append({
                                        "file": str(file_path),
                                        "line": bug.line,
                                        "fixed_code": fix.fixed_code,
                                        "explanation": fix.explanation
                                    })
                                    code = fix.fixed_code
                                    console.print(f"  [green]✅ Applied & Verified. Backup: {apply_result.get('backup_path')}[/green]")
                                else:
                                    console.print(f"  [red]✗ Failed to apply: {apply_result.get('error')}[/red]")
                            else:
                                console.print(f"  [yellow]⏭ Skipped. Moving to next bug...[/yellow]")
                        else:
                            console.print(f"  [yellow]✗ LLM could not generate a valid fix for this bug.[/yellow]")
                
                # File completion message
                console.print("\n" + "="*80)
                if not detected_bugs:
                    console.print(f"[bold green]✓ File Processed: {file_path.name}[/bold green]")
                    console.print(f"[green]   Result: No semantic bugs found[/green]")
                else:
                    console.print(f"[bold green]✓ File Processed: {file_path.name}[/bold green]")
                    console.print(f"[green]   Result: {len(detected_bugs)} bugs detected and processed[/green]")
                console.print("="*80 + "\n")
                    
            except Exception as e:
                console.print(f"  [red]✗ Error analyzing {file_path.name}: {e}[/red]")
        
        console.print(f"✓ vLLM analysis complete ({len(bugs)} bugs, {len(fixes)} fixes)\n")
    
    # Redundancy Detection
    duplicates = []
    if analysis_mode in ['full', 'redundancy']:
        console.print("\nCross-file redundancy detection...")
        if symbol_table:
            redundancy_detector = CrossFileRedundancyDetector(symbol_table, llm_client)
            duplicates = await redundancy_detector.detect_duplicates()
            console.print(f"✓ Found {len(duplicates)} duplicate function groups\n")
        else:
            console.print("[red]✗ Redundancy detection requires structural analysis first. Skipping.[/red]\n")
    
    # Generate Report
    report = {
        "metadata": {
            "folder": str(folder),
            "files_analyzed": len(files),
            "files_with_syntax_errors": len(syntax_errors),
            "fixes_applied_to_codebase": len(applied_fixes),
            "valid_files": len(valid_files)
        },
        "summary": {
            "total_issues": len(syntax_errors) + len(bugs) + len(circular_deps) + len(dead_code_symbols),
            "critical": len([b for b in bugs if b.get("severity") == "critical"]),
            "high": len([b for b in bugs if b.get("severity") == "high"]),
            "medium": len([b for b in bugs if b.get("severity") == "medium"]),
            "low": len([b for b in bugs if b.get("severity") == "low"])
        },
        "syntax_errors": syntax_errors,
        "bugs": bugs,
        "fixes": fixes,
        "cross_file_analysis": {
            "circular_dependencies": [[str(f) for f in cycle] for cycle in circular_deps],
            "dead_code": [
                {"file": str(s.file), "name": s.name, "line": s.line}
                for s in dead_code_symbols
            ],
            "duplicate_functions": [
                {
                    "functions": [{"file": str(f.file), "name": f.name} for f in dup.functions],
                    "similarity": dup.similarity
                }
                for dup in duplicates
            ]
        }
    }
    
    # Save JSON
    with open(output, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Generate HTML Dashboard
    html_path = output.parent / "report.html"
    html_generator = HTMLReportGenerator()
    html_generator.generate(report, html_path)
    
    console.print(f"\n[green]✅ JSON report saved to:[/green] {output}")
    console.print(f"[green]✅ HTML dashboard saved to:[/green] {html_path}")

if __name__ == "__main__":
    app()
