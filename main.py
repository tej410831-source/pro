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

async def run_analysis(folder: Path, output: Path, vllm_url: str, generate_fixes: bool, analysis_mode: str = "full", verbose: bool = False):
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
    
    # Scan files
    console.print("\nScanning files...")
    scanner = FileScanner(folder)
    files = scanner.scan()
    console.print(f"✓ Found {len(files)} code files\n")
    
    # Phase 2: Static Syntax Check (Scanning is universal, interaction is mode-specific)
    syntax_analyzer = StaticSyntaxAnalyzer()
    syntax_fix_generator = SyntaxFixGenerator(llm_client)
    
    lang_map = {'.py': 'python'}
    
    if analysis_mode in ['full', 'syntax']:
        console.print("Static syntax analysis (scanning all files)...")
    
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
                    "severity": getattr(e, 'severity', 'error'),
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
                # 🔄 Sequential Loop: Stay on this file until clean or user skips
                while True:
                    # 1. Analyze the file (Fresh scan from disk)
                    current_valid, current_errors = syntax_analyzer.analyze_file(file_path)
                    
                    if current_valid:
                        syntax_fixes[str(file_path)] = {
                            "original_code": "Modified", # simplified tracking
                            "fixed_code": "Manual Update",
                            "fixes_total": 0,
                            "fixes_accepted": 1 # Just to mark as done
                        }
                        applied_fixes[str(file_path)] = True
                        valid_files.append(file_path)
                        console.print(f"  [green]✅ File {file_path.name} is now syntax-error free![/green]\n")
                        break # Move to next file

                    # 2. Show error status
                    console.print(f"  [yellow]⚠️  File has {len(current_errors)} error(s).[/yellow]")
                    for err in current_errors:
                        console.print(f"    - Line {err.line}: {err.message}")
                    
                    # 3. Read current code for context
                    with open(file_path, 'r', encoding='utf-8') as f:
                        original_code = f.read()

                    # 4. Trigger Manual Assist (One error at a time)
                    fix_result = await syntax_fix_generator.fix_file_manual_assist(
                        file_path,
                        original_code,
                        current_errors
                    )
                    
                    # 5. Check if we should loop or break
                    fixes_made = fix_result.get('fixes_presented', 0)
                    
                    if fixes_made > 0:
                        console.print(f"\n  [yellow]🔄 Fix applied. Re-analyzing file...[/yellow]")
                        # Loop continues to re-check the file
                    else:
                        console.print(f"\n  [yellow]⏩ Skipping remaining errors for this file.[/yellow]\n")
                        break # User quit, move to next file

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
    
    # Structural Analysis (symbol table + call graph)
    circular_deps = []
    dead_code_symbols = []
    symbol_table = None
    parsed_files = {}
    
    # Always build symbol table for semantic analysis (needed for context)
    # But only show structural results for 'full' and 'structural' modes
    if analysis_mode in ['full', 'structural', 'redundancy', 'semantic']:
        console.print("Building symbol table & call graph...")
        from analyzers.structural_analyzer import StructuralAnalyzer
        
        struct_analyzer = StructuralAnalyzer()
        analysis_files = valid_files if valid_files else [f for f in files if f.suffix == '.py']
        results = struct_analyzer.analyze_codebase(analysis_files)
        
        symbol_table = results["symbol_table_object"]
        circular_deps = results["circular_dependencies"]
        dead_code_symbols = results["dead_code"]
        
        # Reconstruct parsed_files for compatibility with Semantic Phase
        for file_path_str, data in results["raw_data"].items():
            fpath = Path(file_path_str)
            module_name = fpath.stem
            
            cg_functions = []
            for f in data["functions"]:
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
    
    # Only show structural analysis results for 'structural' or 'full' modes, NOT for 'semantic'
    if analysis_mode in ['full', 'structural']:
        console.print("Cross-file analysis...")
        if circular_deps:
            console.print(f"  [red]✗ Found {len(circular_deps)} circular dependencies:[/red]")
            for cycle in circular_deps:
                cycle_str = " -> ".join([str(p) for p in cycle])
                console.print(f"    • {cycle_str}")
        else: console.print("  [green]✓ No circular imports found.[/green]")
        
        function_cycles = results.get("function_cycles", [])
        if function_cycles:
            console.print(f"  [red]✗ Found {len(function_cycles)} recursive function calls:[/red]")
            for cycle in function_cycles:
                cycle_str = " -> ".join([f"{s.name} ([dim]{s.file.name}:{s.line}[/dim])" for s in cycle])
                first = cycle[0]
                cycle_str += f" -> {first.name}"
                console.print(f"    • {cycle_str}")
            
        if dead_code_symbols:
            console.print(f"  [yellow]⚠ Found {len(dead_code_symbols)} dead code functions:[/yellow]")
            for symbol in dead_code_symbols[:10]:
                console.print(f"    • {symbol.name} ([dim]{symbol.file.name}:{symbol.line}[/dim])")
            if len(dead_code_symbols) > 10: console.print(f"    ... and {len(dead_code_symbols)-10} more")
        else: console.print("  [green]✓ No dead code detected.[/green]")
        
        unused_vars = results.get("unused_variables", [])
        if unused_vars:
            console.print(f"  [yellow]⚠ Found {len(unused_vars)} unused variables:[/yellow]")
            for var in unused_vars[:10]:
                console.print(f"    • {var['name']} ([dim]{var['file']}:{var['line']}[/dim]) [{var['type']}]")
            if len(unused_vars) > 10: console.print(f"    ... and {len(unused_vars)-10} more")
        else: console.print("  [green]✓ No unused variables detected.[/green]")
        console.print("")
    
    # Semantic Bug Detection
    if analysis_mode in ['full', 'semantic']:
        console.print("\nSemantic bug detection...")
        from analyzers.static_bug_detector import StaticBugDetector
        static_bug_detector = StaticBugDetector()
        bug_detector = LLMBugDetector(llm_client)
        fix_generator = FixGenerator(llm_client)
        
        # We need lang_map if we didn't run Phase 2
        if 'lang_map' not in locals():
                    lang_map = {'.py': 'python'}

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
                        # User requested to hide static errors to reduce noise
                        # console.print(f"    [red]• Static Error:[/] {issue['message']} at line {issue['line']}")
                
                # 2. Detect bugs using vLLM (Semantic)
                language = lang_map.get(file_path.suffix, 'python')
                detected_bugs = []
                
                # Force focused analysis if symbol table is available for better context
                if symbol_table and len(file_symbols := symbol_table.get_symbols_in_file(file_path)) > 0:
                    console.print(f"    [dim]Context-Aware Audit: Analyzing {len(file_symbols)} symbols...[/dim]")
                    
                    # Extract Module-Level Context (Once per file)
                    import ast
                    global_vars_str = ""
                    imports_str = ""
                    try:
                        tree = ast.parse(code)
                        # Extract imports
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
                        
                        # Extract global variables (module-level assignments)
                        globals_list = []
                        for node in tree.body:
                            if isinstance(node, ast.Assign):
                                for target in node.targets:
                                    if isinstance(target, ast.Name):
                                        # Get value as string (approximation)
                                        try:
                                            val_str = ast.unparse(node.value) if hasattr(ast, 'unparse') else "..."
                                        except:
                                            val_str = "..."
                                        globals_list.append(f"{target.id} = {val_str}")
                        global_vars_str = "\n".join(globals_list)
                    except:
                        pass
                    
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
                            
                            # 2. Build Enhanced Dependency Hints (Cross-File + Same-File)
                            dep_hints = ""
                            sym_data = next((f for f in parsed_files[file_path]["functions"] if f["qualified_name"].endswith(f".{sym.name}")), None)
                            if sym_data:
                                for call in sym_data.get("calls", []):
                                    all_syms = symbol_table.find_symbols_by_name(call)
                                    # Include ALL functions (cross-file AND same-file) called by this symbol
                                    for ext in all_syms[:3]: # Limit hints
                                        if ext.qualified_name != sym.qualified_name: # Don't include self
                                            location = "cross-file" if ext.file != file_path else "same-file"
                                            dep_hints += f"- {ext.qualified_name} ({location}): {ext.signature}\n"
                            
                            sym_bugs = await bug_detector.analyze_symbol(
                                sym.name, sym.body_code, language, file_path, 
                                class_context=class_ctx, dependency_hints=dep_hints,
                                global_vars=global_vars_str, imports_list=imports_str,
                                verbose=verbose
                            )
                            detected_bugs.extend(sym_bugs)
                        
                        elif sym.type == SymbolType.CLASS:
                            # Analyze class-level code (attributes, properties, etc.)
                            # Build inheritance hints
                            inheritance_hints = ""
                            # Check if class inherits from others in the symbol table
                            # This is a simplified check - full implementation would parse bases
                            
                            class_bugs = await bug_detector.analyze_symbol(
                                sym.name, sym.body_code, language, file_path,
                                class_context="",  # Classes don't have parent class context
                                dependency_hints=inheritance_hints,
                                global_vars=global_vars_str, imports_list=imports_str,
                                verbose=verbose
                            )
                            detected_bugs.extend(class_bugs)
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
                    
                    # Auto-generate patch (no user permission needed)
                    if generate_fixes:
                        # Extract global context (imports/constants)
                        global_context = syntax_fix_generator._extract_global_context(code)
                        
                        console.print(f"  [cyan]⚡ Auto-generating patch for line {bug.line}...[/cyan]")
                        fix = await fix_generator.generate_fix(
                            bug.type, bug.severity, file_path, bug.line,
                            code, language, bug.description, bug.suggestion, global_context
                        )
                        
                        if fix:
                            # Show clean code snippet instead of diff (User preference: no + signs)
                            fixed_lines = fix.fixed_code.splitlines()
                            # Centered around the bug line
                            start_idx = max(0, bug.line - 4)
                            end_idx = min(len(fixed_lines), bug.line + 5)
                            snippet = "\n".join(fixed_lines[start_idx:end_idx])
                            
                            fix_info = Group(
                                Markdown("### Proposed Code Change"),
                                Syntax(snippet, language, theme="monokai", line_numbers=True, start_line=start_idx+1),
                                f"\n[bold blue]Explanation:[/bold blue] {fix.explanation}"
                            )
                            # Use minimal box to reduce vertical lines if user dislikes them
                            from rich import box
                            console.print(Panel(
                                fix_info, 
                                title="[bold blue]PROPOSED FIX[/bold blue]", 
                                border_style="blue",
                                box=box.ROUNDED
                            ))
                            
                            # Ask permission to PROCEED to next bug (not to generate patch)
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
                                    # Update 'code' variable for next bug in same file
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
