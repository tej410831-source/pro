"""
HTML Dashboard Report Generator
Creates interactive HTML report with charts and filtering.
"""

from pathlib import Path
from typing import Dict, List
import json

class HTMLReportGenerator:
    """
    Generates beautiful HTML dashboard for analysis results.
    """
    
    def generate(self, report_data: Dict, output_path: Path):
        """
        Generate HTML report from analysis data.
        """
        html = self._build_html(report_data)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
    
    def _build_html(self, data: Dict) -> str:
        """Build complete HTML document."""
        
        metadata = data.get("metadata", {})
        summary = data.get("summary", {})
        syntax_errors = data.get("syntax_errors", {})
        bugs = data.get("bugs", [])
        cross_file = data.get("cross_file_analysis", {})
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Analysis Report - {metadata.get('folder', 'Unknown')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 3rem 2rem;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .header p {{
            opacity: 0.9;
            font-size: 1.1rem;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            padding: 2rem;
            background: #f8f9fa;
        }}
        
        .stat-card {{
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.2s;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        
        .stat-value {{
            font-size: 2.5rem;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 0.5rem;
        }}
        
        .stat-label {{
            color: #6c757d;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .section {{
            padding: 2rem;
        }}
        
        .section-title {{
            font-size: 1.8rem;
            margin-bottom: 1.5rem;
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 0.5rem;
        }}
        
        .issue-card {{
            background: #fff;
            border-left: 4px solid #dc3545;
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .issue-card.critical {{ border-left-color: #dc3545; }}
        .issue-card.high {{ border-left-color: #fd7e14; }}
        .issue-card.medium {{ border-left-color: #ffc107; }}
        .issue-card.low {{ border-left-color: #28a745; }}
        
        .issue-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }}
        
        .issue-type {{
            font-weight: 600;
            color: #333;
        }}
        
        .severity-badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .severity-critical {{ background: #dc3545; color: white; }}
        .severity-high {{ background: #fd7e14; color: white; }}
        .severity-medium {{ background: #ffc107; color: #333; }}
        .severity-low {{ background: #28a745; color: white; }}
        
        .issue-file {{
            color: #6c757d;
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
        }}
        
        .issue-description {{
            color: #495057;
            line-height: 1.6;
        }}
        
        code {{
            background: #f8f9fa;
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
        }}
        
        .empty-state {{
            text-align: center;
            padding: 3rem;
            color: #6c757d;
        }}
        
        .empty-state svg {{
            width: 100px;
            height: 100px;
            margin-bottom: 1rem;
            opacity: 0.5;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Code Analysis Report</h1>
            <p>{metadata.get('folder', 'Unknown Project')}</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{metadata.get('files_analyzed', 0)}</div>
                <div class="stat-label">Files Analyzed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{summary.get('total_issues', 0)}</div>
                <div class="stat-label">Total Issues</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{summary.get('critical', 0)}</div>
                <div class="stat-label">Critical</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(cross_file.get('circular_dependencies', []))}</div>
                <div class="stat-label">Circular Deps</div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">🐛 Syntax Errors</h2>
            {self._render_syntax_errors(syntax_errors)}
        </div>
        
        <div class="section">
            <h2 class="section-title">🔗 Cross-File Analysis</h2>
            {self._render_cross_file(cross_file)}
        </div>
        
        <div class="section">
            <h2 class="section-title">📊 Redundancy Analysis</h2>
            {self._render_redundancy(cross_file.get('duplicate_functions', []))}
        </div>
    </div>
</body>
</html>"""
    
    def _render_syntax_errors(self, syntax_errors: Dict) -> str:
        if not syntax_errors:
            return '<div class="empty-state">✅ No syntax errors found!</div>'
        
        html = ""
        for file, errors in syntax_errors.items():
            for error in errors:
                html += f"""
                <div class="issue-card critical">
                    <div class="issue-header">
                        <span class="issue-type">Syntax Error</span>
                        <span class="severity-badge severity-critical">Critical</span>
                    </div>
                    <div class="issue-file">{file}:{error.get('line', 0)}</div>
                    <div class="issue-description">{error.get('message', 'Unknown error')}</div>
                </div>
                """
        return html
    
    def _render_cross_file(self, cross_file: Dict) -> str:
        circular = cross_file.get('circular_dependencies', [])
        dead_code = cross_file.get('dead_code', [])
        
        if not circular and not dead_code:
            return '<div class="empty-state">✅ No cross-file issues found!</div>'
        
        html = ""
        
        for cycle in circular:
            cycle_str = " → ".join(cycle)
            html += f"""
            <div class="issue-card high">
                <div class="issue-header">
                    <span class="issue-type">Circular Dependency</span>
                    <span class="severity-badge severity-high">High</span>
                </div>
                <div class="issue-description">
                    Cycle detected: <code>{cycle_str}</code>
                </div>
            </div>
            """
        
        for func in dead_code:
            html += f"""
            <div class="issue-card medium">
                <div class="issue-header">
                    <span class="issue-type">Dead Code</span>
                    <span class="severity-badge severity-medium">Medium</span>
                </div>
                <div class="issue-file">{func.get('file', 'Unknown')}:{func.get('line', 0)}</div>
                <div class="issue-description">
                    Function <code>{func.get('name', 'unknown')}</code> is never called
                </div>
            </div>
            """
        
        return html
    
    def _render_redundancy(self, duplicates: List) -> str:
        if not duplicates:
            return '<div class="empty-state">✅ No duplicate functions found!</div>'
        
        html = ""
        for dup in duplicates:
            files = ", ".join([f.get('file', 'Unknown') for f in dup.get('functions', [])])
            html += f"""
            <div class="issue-card medium">
                <div class="issue-header">
                    <span class="issue-type">Duplicate Functions</span>
                    <span class="severity-badge severity-medium">Medium</span>
                </div>
                <div class="issue-description">
                    Similar functions found in: <code>{files}</code><br>
                    Similarity: {dup.get('similarity', 0):.0%}
                </div>
            </div>
            """
        
        return html
