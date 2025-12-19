import os
from typing import Dict, Any, List
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

def generate_pdf_report(repo_url: str, all_file_data: Dict[str, Dict[str, Any]], output_path: str = 'debt_report.pdf'):
    """Generates a professional PDF report from the analysis data."""
    
    repo_stats = all_file_data.get('_repo_stats', {})
    repo_score = f"{repo_stats.get('overall_technical_debt', 0):.2f}"
    
    # 1. Prepare Data for Template
    file_list = [(path, data) for path, data in all_file_data.items() if 'risk_score' in data and data.get('loc', 0) > 0]
    
    # Simple function to get data rows for the top risk table
    def get_risk_data(files):
        return [[path, f"{data['risk_score']:.2f}", data.get('main_factor', 'N/A')] for path, data in files]

    # Assume we've stored 'main_factor' during CLI report generation (we need to slightly adjust report_generator for this)
    # Since we don't have the CLI report changes, we'll use raw data here:
    top_risk = sorted(file_list, key=lambda x: x[1]['risk_score'], reverse=True)[:10]
    top_risk_data = [[path, f"{data['risk_score']:.2f}", 'Complexity (Simulated)'] for path, data in top_risk] # Simplified factor

    template_data = {
        'repo_url': repo_url,
        'files_analyzed': len(file_list),
        'repo_score': repo_score,
        'top_risk_data': top_risk_data,
        'analysis_note': "Technical Debt Growth Trend and Detailed Metrics are omitted for PDF simplicity.",
    }

    # 2. Load and Render Jinja2 Template
    # This assumes report_template.html is in the same directory
    env = Environment(loader=FileSystemLoader('.')) 
    template = env.get_template('report_template.html')
    html_out = template.render(template_data)

    # 3. Convert HTML to PDF using WeasyPrint
    print(f"📄 Generating PDF report to: {output_path}")
    
    # WeasyPrint requires a base_url for linking CSS/fonts if used
    HTML(string=html_out, base_url=os.path.abspath(os.path.dirname(__file__))).write_pdf(
        output_path, 
        stylesheets=[CSS(string='@page {size: A4; margin: 1cm;}')]
    )
    print("✅ PDF generation complete.")
    
    return output_path