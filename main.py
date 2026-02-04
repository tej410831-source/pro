"""
Advanced Code Analyzer - Main CLI
"""

import typer
import asyncio
from pathlib import Path
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
import json
import difflib

app = typer.Typer(help="Advanced Hybrid Static + AI Code Analysis System")
console = Console()
@app.command()
def check_files(
    folder: Path = typer.Argument(..., help="Folder to check file-by-file")
):
    """
    Check each file one-by-one for syntax correctness.
    """
    from core.scanner import FileScanner
    from analyzers.static_syntax import StaticSyntaxAnalyzer

    console.print("[bold cyan]🔍 File-by-file syntax check[/bold cyan]\n")

    scanner = FileScanner(folder)
    files = scanner.scan()

    analyzer = StaticSyntaxAnalyzer()

    passed = 0
    failed = 0

    for idx, file_path in enumerate(files, 1):
        console.print(f"[yellow]{idx}/{len(files)} Checking:[/yellow] {file_path}")

        is_valid, errors = analyzer.analyze_file(file_path)

        if is_valid:
            console.print(f"  [green]✅ OK[/green]\n")
            passed += 1
        else:
            console.print(f"  [red]❌ FAILED[/red]")
            for e in errors:
                console.print(
                    f"    Line {e.line}, Col {e.column}: {e.message} "
                    f"[{e.parser}]"
                )
            console.print()
            failed += 1

    console.print(
        f"[bold green]✔ Passed:[/bold green] {passed}  "
        f"[bold red]✖ Failed:[/bold red] {failed}"
    )

@app.command()
def analyze(
    folder: Path = typer.Argument(..., help="Folder to analyze"),
    output: Path = typer.Option("report.json", "--output", "-o", help="Output report path"),
    vllm_url: str = typer.Option("http://localhost:8000/v1", "--vllm-url", help="vLLM server URL"),
    generate_fixes: bool = typer.Option(True, "--fixes/--no-fixes", "--generate-fixes", help="Generate code fixes"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Display raw LLM prompts"),
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
    asyncio.run(run_analysis(folder, output, vllm_url, generate_fixes, analysis_mode, verbose))

async def run_analysis(folder: Path, output_path: Path, vllm_url: str, generate_fixes: bool, analysis_mode: str = "full", verbose: bool = False):
    from core.scanner import FileScanner
    from analyzers.static_syntax import StaticSyntaxAnalyzer, FileSyntaxError
    from analyzers.syntax_fix_generator import SyntaxFixGenerator
    from analyzers.llm_bug_detector import LLMBugDetector
    from analyzers.fix_generator import FixGenerator
    from analyzers.cross_file_redundancy import CrossFileRedundancyDetector
    from core.symbol_table import SymbolTableBuilder, Symbol, SymbolType
    from core.call_graph_builder import CallGraphBuilder
    from llm.vllm_client import VLLMClient
    from utils.html_report_generator import HTMLReportGenerator
    
    # Initialize vLLM client
    console.print(f"[cyan]→ Connecting to vLLM at {vllm_url}[/cyan]")
    llm_client = VLLMClient(base_url=vllm_url)
    
    # Phase 1: Scan
    console.print("\n[yellow]Phase 1:[/yellow] Scanning files...")
    scanner = FileScanner(folder)
    files = scanner.scan()
    console.print(f"✓ Found {len(files)} code files\n")
    
    # Phase 2: Static Syntax Check (Scanning is universal, interaction is mode-specific)
    syntax_analyzer = StaticSyntaxAnalyzer()
    syntax_fix_generator = SyntaxFixGenerator(llm_client)
    
    lang_map = {'.py': 'python', '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.h': 'cpp'}
    
    if analysis_mode in ['full', 'syntax']:
        console.print("[yellow]Phase 2:[/yellow] Static syntax analysis (scanning all files)...")
    
    # Results containers
    valid_files = []
    error_files = [] # Files with syntax errors
    syntax_errors = {}
    syntax_fixes = {}
    applied_fixes = {}
    bugs = []
    fixes = []
    
    # Step 1: Scan all files first
    for file_path in files:
        is_valid, errors = syntax_analyzer.analyze_file(file_path)
        
        if not is_valid:
            error_files.append(file_path)
            # Store original errors
            syntax_errors[str(file_path)] = [
                {
                    "type": e.type,
                    "severity": e.severity,
                    "line": e.line,
                    "column": e.column,
                    "message": e.message,
                    "parser": e.parser
                }
                for e in errors
            ]
        else:
            valid_files.append(file_path)

    # Step 2: Show ALL errors at once (UI Only)
    if syntax_errors and analysis_mode in ['full', 'syntax']:
        error_blocks = []
        for file_path_str, errors in syntax_errors.items():
            fname = Path(file_path_str).name
            err_text = "\n".join([f"  • [bold red]Line {e['line']}:[/bold red] {e['message']}" for e in errors])
            error_blocks.append(f"### {fname}\n{err_text}")
        
        global_error_panel = Panel(
            Markdown("\n\n---\n\n".join(error_blocks)),
            title=f"[bold red]PROJECT SYNTAX ERRORS ({len(syntax_errors)} files)[/bold red]",
            border_style="red"
        )
        console.print(global_error_panel)
        console.print(f"\n[bold yellow]Found {len(syntax_errors)} files with errors. Starting interactive fixing...[/bold yellow]\n")

    # Step 3: Interactive Fixing Loop
    if generate_fixes and error_files:
        for file_path in error_files:
            file_path_str = str(file_path)
            errors_data = syntax_errors[file_path_str]
            # Convert back to FileSyntaxError objects for the generator
            errors = [FileSyntaxError(e['message'], e['parser'], e['line'], e['column']) for e in errors_data]
            language = lang_map.get(file_path.suffix, 'python')
            
            console.print(f"🔧 [bold]Interactive Fix for {file_path.name}:[/bold]")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_code = f.read()
                
                # Generate fix using vLLM
                fix_result = await syntax_fix_generator.generate_fix(
                    file_path, 
                    original_code, 
                    errors
                )
                
                if fix_result['success']:
                    proposed_fixes = fix_result['fixes']
                    regions = fix_result['regions']
                    accepted_fixes = []
                    
                    console.print(f"  [bold cyan]→ {len(proposed_fixes)} fixes proposed for review:[/bold cyan]")
                    
                    for i, fix in enumerate(proposed_fixes):
                        region_idx = fix['region'] - 1
                        region = regions[region_idx]
                        explanation = fix.get('explanation', 'Fixed syntax error.')
                        
                        # Show specific fix suggestion in a panel
                        fix_preview = Group(
                            Markdown(f"#### Fix {i+1} for {file_path.name} (Lines {region['start_line']}-{region['end_line']})"),
                            Syntax(
                                fix['fixed_code'], 
                                language, 
                                theme="monokai", 
                                line_numbers=True, 
                                start_line=region['start_line']
                            ),
                            f"\n[bold blue]Explanation:[/bold blue] {explanation}"
                        )
                        console.print(Panel(fix_preview, title=f"[bold blue]PROPOSED FIX {i+1}/{len(proposed_fixes)}[/bold blue]", border_style="blue"))
                        
                        if typer.confirm(f"  Apply fix {i+1}/{len(proposed_fixes)}?", default=True):
                            accepted_fixes.append(fix)
                            console.print(f"  [green]✔ Fix {i+1} accepted.[/green]")
                        else:
                            console.print(f"  [yellow]✘ Fix {i+1} rejected.[/yellow]")

                    if accepted_fixes:
                        console.print(f"\n  [yellow]🔧 Applying {len(accepted_fixes)} accepted fix(es)...[/yellow]")
                        fixed_code = syntax_fix_generator.apply_fixes(original_code, regions, accepted_fixes)
                        
                        # Validate the fix using static analyzer (must be error free)
                        is_fixed_valid, remaining_errors = syntax_analyzer.analyze_code(
                            fixed_code, 
                            file_path.suffix
                        )
                        
                        if is_fixed_valid:
                            # Apply to file (creates backup)
                            apply_result = syntax_fix_generator.apply_fix_to_file(
                                file_path,
                                fixed_code,
                                create_backup=True
                            )
                            
                            if apply_result['success']:
                                # Re-validate the actual file on disk
                                final_valid, final_errors = syntax_analyzer.analyze_file(file_path)
                                
                                if final_valid:
                                    syntax_fixes[str(file_path)] = {
                                        "original_code": original_code,
                                        "fixed_code": fixed_code,
                                        "fixes_total": len(proposed_fixes),
                                        "fixes_accepted": len(accepted_fixes),
                                        "backup_path": apply_result.get('backup_path')
                                    }
                                    
                                    applied_fixes[str(file_path)] = True
                                    valid_files.append(file_path)
                                    console.print(f"  [green]✅ File {file_path.name} successfully updated and verified.[/green]\n")
                                else:
                                    # Rollback!
                                    syntax_fix_generator.restore_from_backup(file_path)
                                    console.print(f"  [yellow]⚠️ Final on-disk verification failed! Restored backup.[/yellow]\n")
                            else:
                                console.print(f"  [red]✗ Failed to write fix to disk: {apply_result.get('error', 'Unknown')}[/red]\n")
                        else:
                            console.print(f"  [yellow]⚠️ Merged fix still has {len(remaining_errors)} errors. Skipping apply.[/yellow]\n")
                    else:
                        console.print(f"  [yellow]⏩ No fixes accepted for {file_path.name}.[/yellow]\n")
                else:
                    console.print(f"  [red]✗ LLM fix failed: {fix_result.get('error', 'Unknown')}[/red]\n")
            
            except Exception as e:
                console.print(f"  [red]✗ Exceptional error during fix: {e}[/red]\n")
    
    elif not generate_fixes and syntax_errors:
        console.print("[yellow]Note: --generate-fixes not enabled. Skipping interactive repairs.[/yellow]")
    
    if analysis_mode in ['full', 'syntax']:
        console.print(f"\n✓ {len(valid_files)}/{len(files)} files passed syntax check")
        if syntax_errors:
            console.print(f"✗ {len(syntax_errors)} files had syntax errors")
            if applied_fixes:
                console.print(f"✅ {len(applied_fixes)} files FIXED & APPLIED to codebase")
                console.print(f"   💾 Backups saved as .bak files\n")
            else:
                console.print("")
    
    # Phase 3 & 4: Structural Analysis
    circular_deps = []
    dead_code_symbols = []
    symbol_table = None
    
    if analysis_mode in ['full', 'structural', 'redundancy']:
        console.print("[yellow]Phase 3:[/yellow] Building symbol table & call graph...")
        from core.ast_parser import StructuralParser
        
        symbol_table = SymbolTableBuilder()
        parser = StructuralParser()
        parsed_files = {}
        
        # We need lang_map if we didn't run Phase 2
        if 'lang_map' not in locals():
            lang_map = {'.py': 'python', '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.h': 'cpp'}

        for file_path in (valid_files if valid_files else files):
            try:
                language = lang_map.get(file_path.suffix, 'python')
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                if language == 'python':
                    data = parser.parse_python(code, file_path)
                elif file_path.suffix in parser.parsers:
                    data = parser.parse_tree_sitter(code, file_path)
                else: continue
                    
                module_name = file_path.stem
                for func in data["functions"]:
                    symbol = Symbol(
                        name=func["name"],
                        symbol_type=SymbolType.FUNCTION,
                        file_path=file_path,
                        line=func["line"],
                        signature=func.get("signature", f"{func['name']}(...)"),
                        body_code=func.get("body_code", ""),
                        parent_name=func.get("parent_class", "")
                    )
                    symbol_table.add_symbol(symbol, module_name)
                
                for cls in data["classes"]:
                    symbol = Symbol(
                        name=cls["name"],
                        symbol_type=SymbolType.CLASS,
                        file_path=file_path,
                        line=cls["line"],
                        signature=f"class {cls['name']}",
                        attributes=cls.get("attributes", [])
                    )
                    symbol_table.add_symbol(symbol, module_name)
                
                cg_functions = []
                for f in data["functions"]:
                    prefix = f"{f['parent_class']}." if f.get("parent_class") else ""
                    cg_functions.append({
                        "qualified_name": f"{module_name}.{prefix}{f['name']}",
                        "calls": f.get("calls", [])
                    })
                parsed_files[file_path] = {"functions": cg_functions, "calls": data.get("calls", []), "imports": data.get("imports", [])}
            except Exception as e:
                console.print(f"  [red]✗ Error indexing {file_path.name}: {e}[/red]")
        
        call_graph = CallGraphBuilder(symbol_table)
        call_graph.build_call_graph(parsed_files)
        console.print(f"✓ Symbol table & call graph built ({len(symbol_table.symbols)} symbols indexed)\n")
        
        console.print("[yellow]Phase 4:[/yellow] Cross-file analysis...")
        circular_deps = call_graph.find_circular_dependencies()
        dead_code_symbols = call_graph.find_dead_code()
        
        if circular_deps:
            console.print(f"  [red]✗ Found {len(circular_deps)} circular dependencies:[/red]")
            for cycle in circular_deps:
                cycle_str = " -> ".join([Path(p).name for p in cycle])
                console.print(f"    • {cycle_str} -> {Path(cycle[0]).name}")
        else: console.print("  [green]✓ No circular dependencies found.[/green]")
            
        if dead_code_symbols:
            console.print(f"  [yellow]⚠ Found {len(dead_code_symbols)} dead code functions:[/yellow]")
            for symbol in dead_code_symbols[:10]:
                console.print(f"    • {symbol.name} ([dim]{symbol.file.name}:{symbol.line}[/dim])")
            if len(dead_code_symbols) > 10: console.print(f"    ... and {len(dead_code_symbols)-10} more")
        else: console.print("  [green]✓ No dead code detected.[/green]")
        console.print("")
    
    # Phase 5: Bug Detection
    if analysis_mode in ['full', 'semantic']:
        console.print("[yellow]Phase 5:[/yellow] Bug detection (static & semantic)...")
        from analyzers.static_bug_detector import StaticBugDetector
        static_bug_detector = StaticBugDetector()
        bug_detector = LLMBugDetector(llm_client)
        fix_generator = FixGenerator(llm_client)
        
        # We need lang_map if we didn't run Phase 2
        if 'lang_map' not in locals():
            lang_map = {'.py': 'python', '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.h': 'cpp'}

        for file_path in (valid_files if valid_files else files):
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
                        console.print(f"    [red]• Static Error:[/] {issue['message']} at line {issue['line']}")
                
                # 2. Detect bugs using vLLM (Semantic)
                language = lang_map.get(file_path.suffix, 'python')
                detected_bugs = []
                
                # Threshold for Focused vs Whole File analysis
                if len(code.splitlines()) > 200 and symbol_table:
                    console.print(f"    [dim]Large file detected. Switching to symbol-by-symbol audit...[/dim]")
                    file_symbols = symbol_table.get_symbols_in_file(file_path)
                    for sym in file_symbols:
                        if sym.type == SymbolType.FUNCTION:
                            # 1. Build Class Context if needed
                            class_ctx = ""
                            if sym.parent_name:
                                class_syms = [s for s in file_symbols if s.name == sym.parent_name and s.type == SymbolType.CLASS]
                                if class_syms:
                                    cls = class_syms[0]
                                    other_methods = [s.signature for s in file_symbols if s.parent_name == sym.parent_name and s.name != sym.name]
                                    class_ctx = f"Class: {cls.name}\nAttributes: {', '.join(cls.attributes)}\nOther methods: {', '.join(other_methods)}"
                            
                            # 2. Build Dependency Hints
                            dep_hints = ""
                            sym_data = next((f for f in parsed_files[file_path]["functions"] if f["qualified_name"].endswith(f".{sym.name}")), None)
                            if sym_data:
                                for call in sym_data.get("calls", []):
                                    ext_syms = symbol_table.find_symbols_by_name(call)
                                    # Skip if it's the same symbol or another symbol in the same file
                                    ext_syms = [s for s in ext_syms if s.file != file_path]
                                    for ext in ext_syms[:2]: # Limit hints
                                        dep_hints += f"- {ext.qualified_name}: {ext.signature}\n"
                            
                            sym_bugs = await bug_detector.analyze_symbol(
                                sym.name, sym.body_code, language, file_path, 
                                class_context=class_ctx, dependency_hints=dep_hints,
                                verbose=verbose
                            )
                            detected_bugs.extend(sym_bugs)
                else:
                    detected_bugs = await bug_detector.analyze_code(file_path, code, language, verbose=verbose)
                
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
                    
                    # Generate and show fix if requested
                    if generate_fixes and typer.confirm(f"  Generate AI patch for this {bug.type}?", default=True):
                        # Extract global context (imports/constants)
                        global_context = syntax_fix_generator._extract_global_context(code)
                        
                        console.print(f"  [cyan]⚡ Generating patch for line {bug.line}...[/cyan]")
                        fix = await fix_generator.generate_fix(
                            bug.type, bug.severity, file_path, bug.line,
                            code, language, bug.description, bug.suggestion, global_context
                        )
                        
                        if fix:
                            # Generate simple diff for review
                            import difflib
                            diff = difflib.unified_diff(
                                code.splitlines(),
                                fix.fixed_code.splitlines(),
                                fromfile=f"{file_path.name} (Before)",
                                tofile=f"{file_path.name} (After)",
                                lineterm=''
                            )
                            diff_text = "\n".join(diff)
                            
                            fix_info = Group(
                                Markdown("### Suggested Fix (Diff)"),
                                Syntax(diff_text, "diff", theme="monokai", line_numbers=True),
                                f"\n[bold blue]Explanation:[/bold blue] {fix.explanation}"
                            )
                            console.print(Panel(fix_info, title="[bold blue]PROPOSED SEMANTIC PATCH[/bold blue]", border_style="blue"))
                            
                            if typer.confirm(f"  Apply this patch to {file_path.name}? (A .bak backup will be created)", default=False):
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
                                    # Update 'code' variable for next bug in same file
                                    code = fix.fixed_code
                                    console.print(f"  [green]✅ Applied & Verified. Backup: {apply_result.get('backup_path')}[/green]")
                                else:
                                    console.print(f"  [red]✗ Failed to apply: {apply_result.get('error')}[/red]")
                        else:
                            console.print(f"  [yellow]✗ LLM could not generate a valid fix for this bug.[/yellow]")
                    
            except Exception as e:
                console.print(f"  [red]✗ Error analyzing {file_path.name}: {e}[/red]")
        
        console.print(f"✓ vLLM analysis complete ({len(bugs)} bugs, {len(fixes)} fixes)\n")
    
    # Phase 6: Redundancy Detection
    duplicates = []
    if analysis_mode in ['full', 'redundancy']:
        console.print("[yellow]Phase 6:[/yellow] Cross-file redundancy detection...")
        if symbol_table:
            redundancy_detector = CrossFileRedundancyDetector(symbol_table, llm_client)
            duplicates = redundancy_detector.detect_duplicates()
            console.print(f"✓ Found {len(duplicates)} duplicate function groups\n")
        else:
            console.print("[red]✗ Redundancy detection requires structural analysis first. Skipping.[/red]\n")
    
    # Generate Report
    report = {
        "metadata": {
            "folder": str(folder),
            "files_analyzed": len(files),
            "files_with_syntax_errors": len(syntax_errors),
            "syntax_errors_fixed": len(syntax_fixes),
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
        "syntax_fixes": syntax_fixes,
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


if __name__ == "__main__":
    app()
