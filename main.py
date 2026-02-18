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
            
        dead_code_symbols = dead_code_data
        console.print(f"✓ Symbol table built ({len(symbol_table.symbols)} symbols indexed)\n")
    
    # Only show structural analysis results for 'structural' or 'full' modes
    if analysis_mode in ['full', 'structural'] and struct_results:
        unused_vars = struct_results.get("unused_variables", [])
        function_cycles = struct_results.get("function_cycles", [])
        
        # Collect all files analyzed
        analysis_files_set = set()
        for s in dead_code_symbols:
            analysis_files_set.add(s.file)
        for v in unused_vars:
            # Match var file name back to actual Path
            for fp_str in struct_results.get("raw_data", {}).keys():
                if Path(fp_str).name == v["file"]:
                    analysis_files_set.add(Path(fp_str))
        # Also include files from valid_files/files
        for f in (valid_files if valid_files else files):
            analysis_files_set.add(f)
        
        sorted_files = sorted(list(analysis_files_set), key=lambda p: p.name)
        
        # ═══ Section 1: Unused Variables (file by file) ═══
        console.print("\n[bold yellow]═══ Unused Variables ═══[/bold yellow]\n")
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
            lang_map = {'.py': 'python', '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.java': 'java'}

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
            
            console.print(f"\n[bold cyan]Analyzing File {file_idx}/{len(analysis_queue)}: {file_path.name}[/bold cyan]")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
            except Exception as e:
                console.print(f"[red]Error reading {file_path.name}: {e}[/red]")
                continue

            # Parse file once per session
            parse_result = struct_analyzer.parser.parse(code, file_path)
            functions = parse_result.get("functions", [])
            
            # Context extraction
            imports_str = ""
            global_vars_str = ""
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
            
            language = lang_map.get(file_path.suffix, 'python')
            skip_file = False

            # 1. Globals Analysis
            if global_vars_str:
                global_bugs, _ = await bug_detector.analyze_symbol(
                    "Global Variables", global_vars_str, language, file_path,
                    class_context="", dependency_hints="", 
                    global_vars="", imports_list=imports_str
                )
                global_priority_bugs = [b for b in global_bugs if b.severity.lower() in ['critical', 'high', 'medium', 'low']]
                if global_priority_bugs:
                     console.print("\n" + "─"*50)
                     console.print(f"[bold red]BUGS DETECTED[/bold red] in [cyan]Global Variables[/cyan]")
                     
                     for i, bug in enumerate(global_priority_bugs, 1):
                         console.print(f"\n[bold]{i}. Issue:[/bold] {bug.description}")
                         console.print(f"[green]   Suggestion:[/green] {bug.suggestion}")
                     
                     # Show ONE integrated AI code patch for globals
                     # Note: analyze_symbol for "Global Variables" returns corrected code for just that block
                     if _ and _.strip():
                        console.print(Panel(
                            Syntax(_, language, theme="monokai", line_numbers=True),
                            title=f"[bold blue]UNIFIED FIX for Global Variables[/bold blue]", 
                            border_style="blue"
                        ))
                     else:
                        console.print(f"\n  [dim]No code patch generated for these issues.[/dim]")
                    
                     action = Prompt.ask("\n[bold]Next [[white]Enter[/white]=Next, [white]s[/white]=Skip File][/bold]", choices=["", "s"], default="")
                     if action == "s":
                         continue
                else:
                    console.print(f"  [green]✓ No major bugs found in Global Variables.[/green]")

            # 2. Global Code Analysis (Fallback for top-level code)
            significant_top_level = False
            if parse_result.get("calls") and len(parse_result.get("calls", [])) > 0:
                significant_top_level = True
            
            if significant_top_level:
                console.print(f"  [dim]Auditing: Global/Top-level Code...[/dim]")
                file_bugs, file_corrected_code = await bug_detector.analyze_code(file_path, code, language)
                filter_file_bugs = [b for b in file_bugs if b.severity.lower() in ['critical', 'high', 'medium', 'low']]
                
                if filter_file_bugs:
                    console.print("\n" + "─"*50)
                    console.print(f"[bold red]BUGS DETECTED[/bold red] in [cyan]Global Code[/cyan]")
                    
                    for i, bug in enumerate(filter_file_bugs, 1):
                        console.print(f"\n[bold]{i}. Issue:[/bold] {bug.description}")
                        console.print(f"[green]   Suggestion:[/green] {bug.suggestion}")
                    
                    if file_corrected_code:
                        console.print(Panel(
                            Syntax(file_corrected_code, language, theme="monokai", line_numbers=True),
                            title=f"[bold blue]UNIFIED FIX for Global Code[/bold blue]", 
                            border_style="blue"
                        ))
                    else:
                        console.print(f"\n  [dim]No code patch generated for these issues.[/dim]")
                    
                    action = Prompt.ask("\n[bold]Next [[white]Enter[/white]=Next, [white]s[/white]=Skip File][/bold]", choices=["", "s"], default="")
                    if action == "s":
                        continue
                else:
                    console.print(f"  [green]✓ No major bugs found in Global Code.[/green]")

            # 2. Sequential Function Analysis
            for target_func in functions:
                sym_name = target_func['name']
                
                # Build Context (Identical logic as before)
                class_ctx = ""
                if target_func.get("parent_class"):
                    cls_name = target_func["parent_class"]
                    cls_data = next((c for c in parse_result.get("classes", []) if c["name"] == cls_name), None)
                    if cls_data:
                        skel = [f"class {cls_name} {{"]
                        if cls_data.get("attributes"):
                            for a in cls_data["attributes"]: skel.append(f"    {a};")
                        skel.append(f"    // ... other methods ...")
                        skel.append(f"    // === TARGET: {sym_name} ===")
                        for l in target_func["body_code"].splitlines():
                            skel.append(f"    {l}")
                        skel.append("}")
                        class_ctx = "\n".join(skel)

                dep_hints = ""
                if target_func.get("calls"):
                    dep_hints += "Functions this calls: " + ", ".join(target_func["calls"]) + "\n"

                # LLM Analysis
                console.print(f"  [dim]Auditing: {sym_name}...[/dim]")
                bugs, corrected_code = await bug_detector.analyze_symbol(
                    sym_name, target_func["body_code"], language, file_path,
                    class_context=class_ctx, dependency_hints=dep_hints,
                    global_vars=global_vars_str, imports_list=imports_str
                )
                
                priority_bugs = [b for b in bugs if b.severity.lower() in ['critical', 'high', 'medium', 'low']]
                
                if priority_bugs:
                    console.print("\n" + "─"*50)
                    console.print(f"[bold red]BUGS DETECTED[/bold red] in [cyan]{sym_name}[/cyan]")
                    
                    for i, bug in enumerate(priority_bugs, 1):
                        console.print(f"\n[bold]{i}. Issue:[/bold] {bug.description}")
                        console.print(f"[green]   Suggestion:[/green] {bug.suggestion}")
                    
                    # Show ONE integrated AI code patch for the whole function
                    if corrected_code:
                        console.print(Panel(
                            Syntax(corrected_code, language, theme="monokai", line_numbers=True),
                            title=f"[bold blue]UNIFIED FIX for {sym_name}[/bold blue]", 
                            border_style="blue"
                        ))
                    else:
                        console.print(f"\n  [dim]No code patch generated for these issues.[/dim]")
                else:
                    console.print(f"  [green]✓ No major bugs found in {sym_name}.[/green]")
                    
                action = Prompt.ask("\n[bold]Next [[white]Enter[/white]=Next, [white]s[/white]=Skip File][/bold]", choices=["", "s"], default="")
                if action == "s":
                    skip_file = True
                    break
            
            if skip_file:
                continue

            # 3. Method-less Class Analysis (Data classes, etc.)
            parsed_classes = parse_result.get("classes", [])
            for cls in parsed_classes:
                # Only analyze if it has NO methods (methods are handled in the function loop)
                if cls["methods"]:
                    continue
                
                cls_name = cls["name"]
                console.print(f"  [dim]Auditing Class: {cls_name}...[/dim]")
                
                # Context for Class:
                # - Imports (already extracted)
                # - Globals (already extracted)
                # - Bases (inheritance)
                bases_str = ""
                if cls.get("bases"):
                    bases_str = f"Inherits from: {', '.join(cls['bases'])}\n"
                
                class_bugs, corrected_code = await bug_detector.analyze_symbol(
                    cls_name, 
                    cls.get("body_code", ""), 
                    language, 
                    file_path,
                    class_context="", # It IS the class
                    dependency_hints=bases_str,
                    global_vars=global_vars_str,
                    imports_list=imports_str
                )
                
                cls_priority_bugs = [b for b in class_bugs if b.severity.lower() in ['critical', 'high', 'medium', 'low']]
                
                if cls_priority_bugs:
                     console.print("\n" + "─"*50)
                     console.print(f"[bold red]BUGS DETECTED[/bold red] in [cyan]Class {cls_name}[/cyan]")
                     
                     for i, bug in enumerate(cls_priority_bugs, 1):
                         console.print(f"\n[bold]{i}. Issue:[/bold] {bug.description}")
                         console.print(f"[green]   Suggestion:[/green] {bug.suggestion}")
                     
                     if corrected_code:
                        console.print(Panel(Syntax(corrected_code, language, theme="monokai", line_numbers=True), title=f"UNIFIED FIX for Class {cls_name}", border_style="blue"))
                     else:
                        console.print(f"  [dim]No code patch generated for these issues.[/dim]")
                     
                     action = Prompt.ask("\n[bold]Next [[white]Enter[/white]=Next, [white]s[/white]=Skip File][/bold]", choices=["", "s"], default="")
                     if action == "s":
                         skip_file = True
                         break
                else:
                    console.print(f"  [green]✓ No major bugs found in Class {cls_name}.[/green]")
            
            if skip_file:
                continue
        console.print("[bold green]Semantic Analysis Complete.[/bold green]")
    # Phase 5: Redundancy Detection
    duplicates = []
    if analysis_mode in ['full', 'redundancy']:
        console.print("\n[bold blue]Phase 5: Cross-file Redundancy Detection[/bold blue]")
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
    




if __name__ == "__main__":
    app()
