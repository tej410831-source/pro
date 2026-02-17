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
    
    # Only show structural analysis results for 'structural' or 'full' modes
    if analysis_mode in ['full', 'structural'] and struct_results:
        console.print("\n[bold blue]Phase 2: Dead Code & Cycle Detection[/bold blue]")
        
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
        for symbol in unused_funcs:
            lang = symbol.file.suffix.lstrip('.')
            print(f"  [{lang}] {symbol.name} at {symbol.file}:{symbol.line}")
        
        # Unused Variables
        print(f"\n{'='*70}")
        print(f"UNUSED VARIABLES ({len(unused_vars)})")
        print(f"{'='*70}")
        for symbol in unused_vars:
            lang = symbol.file.suffix.lstrip('.')
            print(f"  [{lang}] {symbol.name} at {symbol.file}:{symbol.line}")
        
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


    
    # Phase 3: Semantic Bug Detection
    if analysis_mode in ['full', 'semantic']:
        console.print("\n[bold blue]Phase 3: Semantic Bug Detection[/bold blue]")
        from analyzers.static_bug_detector import StaticBugDetector
        static_bug_detector = StaticBugDetector()
        bug_detector = LLMBugDetector(llm_client)
        fix_generator = FixGenerator(llm_client)
        
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
                global_bugs = await bug_detector.analyze_symbol(
                    "Global Variables", global_vars_str, language, file_path,
                    class_context="", dependency_hints="", 
                    global_vars="", imports_list=imports_str
                )
                
                global_priority_bugs = [b for b in global_bugs if b.severity.lower() in ['critical', 'high', 'medium', 'low']]
                if global_priority_bugs:
                     for bug in global_priority_bugs:
                         console.print("\n" + "─"*50)
                         console.print(f"[bold red]BUG DETECTED[/bold red] in [cyan]Global Variables[/cyan]")
                         console.print(f"[red]Issue:[/red] {bug.description}")
                         console.print(f"[green]Suggestion:[/green] {bug.suggestion}")
                         if bug.code_patch:
                            console.print(Panel(Syntax(bug.code_patch, language, theme="monokai", line_numbers=True), title="PROPOSED FIX", border_style="blue"))
                     
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
                file_bugs = await bug_detector.analyze_code(file_path, code, language)
                filter_file_bugs = [b for b in file_bugs if b.severity.lower() in ['critical', 'high', 'medium', 'low']]
                
                if filter_file_bugs:
                    for bug in filter_file_bugs:
                        console.print("\n" + "─"*50)
                        console.print(f"[bold red]BUG DETECTED[/bold red] in [cyan]Global Code[/cyan]")
                        console.print(f"[red]Issue:[/red] {bug.description}")
                        console.print(f"[green]Suggestion:[/green] {bug.suggestion}")
                        if bug.code_patch:
                            console.print(Panel(Syntax(bug.code_patch, language, theme="monokai", line_numbers=True), title="PROPOSED FIX", border_style="blue"))
                    
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
                bugs = await bug_detector.analyze_symbol(
                    sym_name, target_func["body_code"], language, file_path,
                    class_context=class_ctx, dependency_hints=dep_hints,
                    global_vars=global_vars_str, imports_list=imports_str
                )
                
                priority_bugs = [b for b in bugs if b.severity.lower() in ['critical', 'high', 'medium', 'low']]
                
                if priority_bugs:
                    for bug in priority_bugs:
                        console.print("\n" + "─"*50)
                        console.print(f"[bold red]BUG DETECTED[/bold red] in [cyan]{sym_name}[/cyan]")
                        console.print(f"[red]Issue:[/red] {bug.description}")
                        console.print(f"[green]Suggestion:[/green] {bug.suggestion}")
                        
                        # Show integrated AI code patch
                        if bug.code_patch:
                            console.print(Panel(
                                Syntax(bug.code_patch, language, theme="monokai", line_numbers=True),
                                title=f"[bold blue]PROPOSED FIX for {sym_name}[/bold blue]", 
                                border_style="blue"
                            ))
                else:
                    console.print(f"  [green]✓ No major bugs found in {sym_name}.[/green]")
                    
                action = Prompt.ask("\n[bold]Next [[white]Enter[/white]=Next, [white]s[/white]=Skip File][/bold]", choices=["", "s"], default="")
                if action == "s":
                    skip_file = True
                    break
            
            if skip_file:
                continue
        
        console.print("[bold green]Semantic Analysis Complete.[/bold green]")
    # Phase 4: Redundancy Detection
    duplicates = []
    if analysis_mode in ['full', 'redundancy']:
        console.print("\n[bold blue]Phase 4: Cross-file Redundancy Detection[/bold blue]")
        if symbol_table:
            redundancy_detector = CrossFileRedundancyDetector(symbol_table, llm_client)
            duplicates = await redundancy_detector.detect_duplicates()
            console.print(f"✓ Found {len(duplicates)} duplicate function groups\n")
        else:
            console.print("[red]✗ Redundancy detection requires structural analysis first. Skipping.[/red]\n")
    
    # Reporting disabled per user request
    pass

if __name__ == "__main__":
    app()
