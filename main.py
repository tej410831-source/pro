"""
Advanced Code Analyzer - Main CLI
"""

import typer
import asyncio
from pathlib import Path
from rich.console import Console
from rich.table import Table
import json

app = typer.Typer(help="Advanced Hybrid Static + AI Code Analysis System")
console = Console()

@app.command()
def analyze(
    folder: Path = typer.Argument(..., help="Folder to analyze"),
    output: Path = typer.Option("report.json", "--output", "-o", help="Output report path"),
    vllm_url: str = typer.Option("http://localhost:8000/v1", "--vllm-url", help="vLLM server URL"),
    generate_fixes: bool = typer.Option(True, "--fixes/--no-fixes", help="Generate code fixes"),
):
    """
    Analyze code folder for bugs, redundancy, and cross-file issues.
    """
    
    if not folder.exists():
        console.print(f"[red]Error: Folder {folder} does not exist[/red]")
        raise typer.Exit(1)
    
    console.print(f"[bold blue]🔍 Analyzing:[/bold blue] {folder}\n")
    
    # Run async analysis
    asyncio.run(run_analysis(folder, output, vllm_url, generate_fixes))

async def run_analysis(folder: Path, output: Path, vllm_url: str, generate_fixes: bool):
    from core.scanner import FileScanner
    from analyzers.static_syntax import StaticSyntaxAnalyzer
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
    
    # Phase 2: Static Syntax Check + Fixing
    console.print("[yellow]Phase 2:[/yellow] Static syntax analysis with auto-fixing...")
    syntax_analyzer = StaticSyntaxAnalyzer()
    syntax_fix_generator = SyntaxFixGenerator(llm_client)
    
    valid_files = []
    syntax_errors = {}
    syntax_fixes = {}
    
    for file_path in files:
        is_valid, errors = syntax_analyzer.analyze_file(file_path)
        
        if not is_valid:
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
            
            # Attempt to fix syntax errors
            if generate_fixes:
                console.print(f"  🔧 Fixing {file_path.name} ({len(errors)} errors)...")
                
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
                        # Validate the fix
                        fixed_code = fix_result['fixed_code']
                        is_fixed_valid, remaining_errors = syntax_analyzer.analyze_file(file_path)
                        
                        # Manual validation since we have the fixed code
                        try:
                            import ast
                            ast.parse(fixed_code)
                            is_fixed_valid = True
                            remaining_errors = []
                        except:
                            is_fixed_valid = False
                        
                        if is_fixed_valid:
                            syntax_fixes[str(file_path)] = {
                                "original_code": original_code,
                                "fixed_code": fixed_code,
                                "errors_fixed": len(errors),
                                "method": fix_result.get('method', 'unknown')
                            }
                            
                            # Now treat as valid for further analysis
                            valid_files.append(file_path)
                            console.print(f"  ✅ Fixed successfully using {fix_result.get('method', 'LLM')}")
                        else:
                            console.print(f"  ⚠️  Generated fix still has errors")
                    else:
                        console.print(f"  ✗ Fix generation failed: {fix_result.get('error', 'Unknown')}")
                
                except Exception as e:
                    console.print(f"  ✗ Error during fix: {e}")
        else:
            valid_files.append(file_path)
    
    console.print(f"\n✓ {len(valid_files)} files ready for analysis")
    if syntax_errors:
        console.print(f"✗ {len(syntax_errors)} files had syntax errors")
        if syntax_fixes:
            console.print(f"✅ {len(syntax_fixes)} files fixed automatically\n")
        else:
            console.print("")
    
    # Phase 3: Build Symbol Table & Call Graph
    console.print("[yellow]Phase 3:[/yellow] Building symbol table & call graph...")
    symbol_table = SymbolTableBuilder()
    
    # Simple symbol extraction from valid files
    parsed_files = {}
    for file_path in valid_files[:10]:  # Limit for demo
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # Create dummy symbols for now (full parser integration needed)
            module_name = file_path.stem
            parsed_files[file_path] = {"functions": [], "calls": []}
        except:
            pass
    
    # Build call graph
    call_graph = CallGraphBuilder(symbol_table)
    call_graph.build_call_graph(parsed_files)
    
    console.print("✓ Symbol table & call graph built\n")
    
    # Phase 4: Detect circular dependencies and dead code
    console.print("[yellow]Phase 4:[/yellow] Cross-file analysis...")
    circular_deps = call_graph.find_circular_dependencies()
    dead_code_symbols = call_graph.find_dead_code()
    
    console.print(f"✓ Found {len(circular_deps)} circular dependencies")
    console.print(f"✓ Found {len(dead_code_symbols)} dead code functions\n")
    
    # Phase 5: LLM Semantic Bug Detection (on first 5 files for demo)
    bugs = []
    fixes = []
    
    if generate_fixes and valid_files:
        console.print("[yellow]Phase 5:[/yellow] vLLM semantic bug detection...")
        bug_detector = LLMBugDetector(llm_client)
        fix_generator = FixGenerator(llm_client)
        
        for file_path in valid_files[:5]:  # Limit for demo
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                console.print(f"  🔍 Analyzing {file_path.name}...")
                
                # Detect bugs using vLLM
                language = "python" if file_path.suffix == ".py" else "javascript"
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
                    
                    # Generate fix using vLLM
                    if generate_fixes:
                        fix = await fix_generator.generate_fix(
                            bug.type, bug.severity, file_path, bug.line,
                            code, language
                        )
                        if fix:
                            fixes.append({
                                "file": str(file_path),
                                "line": bug.line,
                                "fixed_code": fix.fixed_code,
                                "explanation": fix.explanation
                            })
                
            except Exception as e:
                console.print(f"  ✗ Error analyzing {file_path.name}: {e}")
        
        console.print(f"✓ vLLM analysis complete ({len(bugs)} bugs, {len(fixes)} fixes)\n")
    
    # Phase 6: Cross-file redundancy using vLLM
    console.print("[yellow]Phase 6:[/yellow] Cross-file redundancy detection...")
    redundancy_detector = CrossFileRedundancyDetector(symbol_table, llm_client)
    duplicates = redundancy_detector.detect_duplicates()
    console.print(f"✓ Found {len(duplicates)} duplicate function groups\n")
    
    # Generate Report
    report = {
        "metadata": {
            "folder": str(folder),
            "files_analyzed": len(files),
            "files_with_syntax_errors": len(syntax_errors),
            "syntax_errors_fixed": len(syntax_fixes),
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
