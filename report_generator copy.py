from typing import Dict, Any, List, Tuple
from operator import itemgetter
import statistics
import os
import sys
import datetime 

# --- PDF Imports ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# --- Gemini SDK Setup ---
from google import genai
from google.genai.errors import APIError
from typing import List, Tuple
import os

# --- FEATURE: KEYWORD SECURITY SCANNER (TABLE 9) ---


# --- FEATURE: KEYWORD SECURITY SCANNER (TABLE 9) ---

from typing import List, Tuple
import os
import sys

# --- FEATURE: KEYWORD SECURITY SCANNER (TABLE 9) ---


GEMINI_API_KEY = "AIzaSyAEG8MMUoKz-K9JBNs2lpPux6NyGYW5vAY" 

client = None
MODEL_NAME = 'gemini-2.5-flash'
try:
    # Initialize client only if a valid placeholder/key is set
    if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_HARDCODED_GEMINI_API_KEY_HERE":
        client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    # Changed to print to stderr to keep CLI output clean
    print(f"⚠️ Warning: Gemini client failed to initialize internally. Error: {e}", file=sys.stderr) 

# --- ANSI Color Codes ---
COLOR_END = '\033[0m'
COLOR_WHITE = '\033[97m'
COLOR_BLUE = '\033[94m'
COLOR_GREEN = '\033[92m'
COLOR_YELLOW = '\033[93m'
COLOR_RED = '\033[91m'
COLOR_BOLD = '\033[1m'
COLOR_GRAY = '\033[90m' 

# --- Helper functions ---

def normalize_metric(value: float, max_value: float, min_value: float = 0.0) -> float:
    if max_value == min_value or max_value == 0:
        return 0.0
    value = max(min_value, value)
    return min(1.0, (value - min_value) / (max_value - min_value))

def get_risk_color(score: float) -> str:
    """Returns the ANSI color code based on the risk score (0-100)."""
    if score > 66:
        return COLOR_RED + COLOR_BOLD
    elif score >= 33:
        return COLOR_YELLOW
    else:
        return COLOR_GREEN
        
def get_security_color(severity: str) -> str:
    """Returns the ANSI color code based on the security severity."""
    if 'CRITICAL' in severity:
        return COLOR_RED + COLOR_BOLD
    elif 'HIGH' in severity:
        return COLOR_RED
    elif 'MEDIUM' in severity:
        return COLOR_YELLOW
    else:
        return COLOR_GREEN

def colorize(text: str, color_code: str, reset_color: bool = True) -> str:
    """Applies a color code to a string."""
    return f"{color_code}{text}{COLOR_END if reset_color else ''}"

def find_main_contributing_factor(data: Dict[str, Any], max_values: Dict[str, float]) -> str:
    """Determines the single metric contributing most to the risk score."""
    
    WEIGHTS = {'complexity': 0.30, 'churn': 0.20, 'ownership_entropy': 0.15, 'bug_fix_frequency': 0.25, 'dependency_score': 0.10}

    norm_complexity = normalize_metric(data.get('complexity', 1), max_values.get('complexity', 1))
    norm_churn = normalize_metric(data.get('lines_added', 0) + data.get('lines_removed', 0), max_values.get('total_churn', 1))
    norm_entropy = normalize_metric(data.get('ownership_entropy', 0.0), max_values.get('ownership_entropy', 1))
    
    total_commits = data.get('commit_count', 0)
    bug_fix_freq = data.get('bug_fix_count', 0) / (total_commits or 1)
    norm_bug_freq = normalize_metric(bug_fix_freq, max_values.get('bug_fix_freq', 1))
    
    dependency_score = data.get('fan_in', 0) * 2 + data.get('fan_out', 0) * 1
    norm_dependency = normalize_metric(dependency_score, max_values.get('dependency_score', 1))

    contributions = {
        'Complexity': norm_complexity * WEIGHTS['complexity'],
        'Churn': norm_churn * WEIGHTS['churn'],
        'Entropy': norm_entropy * WEIGHTS['ownership_entropy'],
        'Bugs': norm_bug_freq * WEIGHTS['bug_fix_frequency'],
        'Dependency': norm_dependency * WEIGHTS['dependency_score'],
    }

    main_factor = max(contributions.items(), key=itemgetter(1))
    total_contribution = sum(contributions.values())
    
    if total_contribution < 0.01:
          return colorize("Low Risk / High Stability", COLOR_GREEN)
          
    return f"{main_factor[0]} ({main_factor[1]*100/total_contribution:.1f}%)"

# --- CLI REPOSITORY METADATA PRINTING (INCLUDES ALL DEPENDENCIES) ---

def print_repo_metadata(repo_metadata: Dict[str, Any]):
    """
    Prints key high-level repository metadata to the CLI, including all requested details.
    """
    print(colorize("\n## 🌐 Repository Metadata", COLOR_BLUE + COLOR_BOLD))
    print("-" * 50)

    # 1. Date Created
    date_created = repo_metadata.get('date_created')
    if date_created:
        print(f"🗓️ {colorize('Repository Creation Date:', COLOR_BOLD)} {date_created}")
    
    # 2. Issues Raised
    issues = repo_metadata.get('current_issues', [])
    print(f"🐛 {colorize('Current Open Issues:', COLOR_BOLD)} {len(issues)}")
    if issues:
        print(colorize("   Top 3 Issues:", COLOR_GRAY))
        for i, issue in enumerate(issues[:3]):
            title = issue.get('title', 'N/A')
            url = issue.get('url', '#')
            print(f"   - {i+1}. {title[:50]}... ({url})")

    # 3. Languages Used
    languages = repo_metadata.get('languages_used', {})
    if languages:
        print(f"\n💻 {colorize('Language Breakdown (by code size):', COLOR_BOLD)}")
        sorted_langs = sorted(languages.items(), key=itemgetter(1), reverse=True)
        for lang, percentage in sorted_langs:
            print(f"   - {lang}: {percentage:.1f}%")
            
    # 4. Dependencies Used (FULL LIST)
    dependencies = repo_metadata.get('dependencies', [])
    if dependencies:
        print(f"\n📦 {colorize('All Project Dependencies Used:', COLOR_BOLD)} ({len(dependencies)} total)")
        
        # Print ALL dependencies clearly
        for i, dep in enumerate(dependencies):
            print(f"   - {i+1}. {dep}")
        
    # 5. Last 5 Commit History
    commits = repo_metadata.get('last_commits', [])
    if commits:
        print(f"\n📜 {colorize('Last 5 Commit History:', COLOR_BOLD)}")
        for i, commit in enumerate(commits):
            # Assuming commit is a dictionary with 'hash', 'author', 'date', 'message'
            commit_hash = commit.get('hash', 'N/A')[:7]
            author = commit.get('author', 'N/A')
            date = commit.get('date', 'N/A')
            message = commit.get('message', 'N/A').split('\n')[0][:70] 
            
            print(f"   - {i+1}. {colorize(commit_hash, COLOR_YELLOW)} by {author} on {date}")
            print(f"     -> {message}...")
    
    print("-" * 50)


# --- PDF GENERATION HELPERS (DYNAMIC WIDTH FIX) ---

def create_table_data(title: str, headers: List[str], raw_data: List[List[Any]]) -> List[Any]:
    """Helper to format data for a ReportLab table with dynamic column sizing."""
    if not raw_data:
        styles = getSampleStyleSheet()
        return [Paragraph(f"<b>{title}</b>", styles['h3']),
                Paragraph("--- No data available. ---", styles['Normal']), Spacer(1, 0.2*inch)]
    
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"<b>{title}</b>", styles['h3']),
        Spacer(1, 0.1*inch)
    ]
    
    # 1. Clean ANSI codes from data for PDF
    def clean_cell(cell):
        # Simplified ANSI stripping for PDF
        if isinstance(cell, str):
            # ReportLab's markup is not used here, just strip the codes
            return cell.replace('\033[91m', '').replace('\033[93m', '').replace('\033[92m', '').replace('\033[0m', '').replace('\033[1m', '').replace('\033[90m', '')
        return str(cell)

    data = [headers] + [[clean_cell(cell) for cell in row] for row in raw_data]
    
    # 2. Determine Dynamic Column Widths
    
    # Total available width = Page Width - Left Margin - Right Margin = 7.5 inches.
    available_width = 7.5 * inch
    num_cols = len(headers)
    
    # Allocate a fixed, smaller width for numbers/scores/status columns.
    # Adjust fixed width slightly smaller for the Security Table to accommodate more columns
    fixed_col_width = 0.8 * inch 
    path_col_index = 0
    
    # Ensure the path/name column is the first one, or adjust index if not.
    if num_cols > 0:
        path_col_index = 0 
    
    # Calculate the total fixed width taken by all columns *except* the primary path/name column.
    total_fixed_width = (num_cols - 1) * fixed_col_width
    
    # Calculate the width available for the file path/name column.
    path_col_width = available_width - total_fixed_width
    
    # Create the final list of column widths
    col_widths = [0] * num_cols
    col_widths[path_col_index] = path_col_width
    for i in range(1, num_cols):
        col_widths[i] = fixed_col_width

    # Safety check: ensure path column has a reasonable minimum width
    if path_col_width < 1.5 * inch:
          col_widths[path_col_index] = 1.5 * inch 

    # 3. Create and Style the Table
    table = Table(data, colWidths=col_widths)
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        
        # KEY FIX: Allow text wrapping in the primary column (index 0)
        ('WORDWRAP', (0, 1), (0, -1), 1), 
    ])
    table.setStyle(style)
    story.append(table)
    story.append(Spacer(1, 0.25*inch))
    
    return story


def generate_pdf_report(repo_url: str, all_file_data: Dict[str, Dict[str, Any]], cli_data: Dict[str, Any], output_filename: str):
    """Generates the full PDF report using ReportLab, including the full dependency list."""
    
    try:
        doc = SimpleDocTemplate(output_filename, pagesize=letter,
                                rightMargin=0.5*inch, leftMargin=0.5*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        styles = getSampleStyleSheet()
        story = []
        
        # --- Title Page / Header ---
        story.append(Paragraph("Git Technical Debt Analysis Report", styles['Title']))
        story.append(Paragraph(f"Repository URL: {repo_url}", styles['h3']))
        story.append(Paragraph(f"Date Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        story.append(Spacer(1, 0.5*inch))
        
        # --- Overall Summary ---
        repo_score = cli_data['repo_score']
        summary_style = ParagraphStyle('Summary', parent=styles['h2'], textColor=colors.red if repo_score > 66 else colors.orange if repo_score >= 33 else colors.green)
        
        story.append(Paragraph(f"Overall Technical Debt Score: <b>{repo_score:.2f} / 100</b>", summary_style))
        story.append(Paragraph(f"Files Analyzed: {cli_data['files_analyzed']}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # --- AI Insight Section ---
        story.append(Paragraph("AI-Powered Technical Debt Insights", styles['h2']))
        story.append(Spacer(1, 0.1*inch))
        
        # Split the markdown list from the AI summary into separate paragraphs
        ai_summary_text = cli_data['ai_summary'].split('\n')
        for line in ai_summary_text:
            if line.strip().startswith('*') or line.strip().startswith('1.'):
                story.append(Paragraph(line.strip(), styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # --- Repository High-Level Metadata ---
        story.append(Paragraph("Repository High-Level Metadata", styles['h2']))
        
        metadata_lines = [
            f"<b>Creation Date:</b> {cli_data.get('date_created', 'N/A')}",
            f"<b>Open Issues:</b> {len(cli_data.get('current_issues', []))}",
        ]
        
        # Format Languages
        languages = cli_data.get('languages_used', {})
        if languages:
            lang_str = ", ".join([f"{lang}: {pct:.1f}%" for lang, pct in sorted(languages.items(), key=itemgetter(1), reverse=True)])
            metadata_lines.append(f"<b>Languages:</b> {lang_str}")
        
        # Add non-commit metadata
        for line in metadata_lines:
            story.append(Paragraph(line, styles['Normal']))

        # Format Last 5 Commits
        commits = cli_data.get('last_commits', [])
        if commits:
            story.append(Paragraph(f"<b>Last 5 Commits:</b>", styles['Normal']))
            for commit in commits:
                commit_hash = commit.get('hash', 'N/A')[:7]
                author = commit.get('author', 'N/A')
                message = commit.get('message', 'N/A').split('\n')[0][:70] 
                story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;* {commit_hash} by {author} - {message}...", styles['Normal']))
        
        story.append(Spacer(1, 0.3*inch))
        
        # --- Full Dependency List Section (for PDF completeness) ---
        dependencies = cli_data.get('dependencies', [])
        if dependencies:
            story.append(Paragraph(f"Full Project Dependencies ({len(dependencies)} total)", styles['h2']))
            story.append(Spacer(1, 0.1*inch))
            
            # Use a list for clean, bulleted output of all dependencies
            for dep in dependencies:
                story.append(Paragraph(f"&bull; {dep}", styles['Normal']))
            
            story.append(Spacer(1, 0.3*inch))
        # --- END DEPENDENCY SECTION ---
        
        # --- Tables (Use the processed CLI data) ---
        
        story.extend(create_table_data("1. All Highest-Risk Files", 
                                        ["File Path", "Risk Score (0-100)", "Main Factor"], 
                                        cli_data['risk_data']))

        story.extend(create_table_data("2. All Highest Regression Risk Files (Change & Dependency)", 
                                        ["File Path", "Combined Score", "Fan-in", "Total Changes"], 
                                        cli_data['refactor_data']))

        story.extend(create_table_data("3. All Anti-Pattern Candidates (Files to Break Apart)", 
                                        ["File Path", "Total Lines", "Complexity (CC)", "Total Changes"], 
                                        cli_data['god_data']))

        story.extend(create_table_data("4. All Critical Systemic Risk Hotspots", 
                                        ["File Path", "Systemic Score", "Dependent Files (Fan-In)", "Test Status"], 
                                        cli_data['systemic_data']))

        # --- Contributor Section ---
        story.append(Paragraph("Contributor Efficiency Analysis", styles['h2']))
        
        # Table 5: No Slicing, with Commits column
        story.extend(create_table_data(f"5. All {len(cli_data['efficient_data'])} Most Efficient Contributors", 
                                        ["Author (Email Prefix)", "Efficiency Score (Higher=Better)", "Commits", "Lines Added"], 
                                        cli_data['efficient_data']))
        
        # Table 6: No Slicing, with Commits column
        story.extend(create_table_data(f"6. All {len(cli_data['coaching_data'])} Priority Coaching Candidates", 
                                        ["Author (Email Prefix)", "Avg Risk Score", "Efficiency Score (Lower=Worse)", "Commits"], 
                                        cli_data['coaching_data']))
        
        # Table 7: LOC Table
        story.extend(create_table_data(f"7. All {len(cli_data['loc_data'])} Files Analyzed with Lines of Code (LOC)", 
                                        ["File Path", "Lines of Code (LOC)"], 
                                        cli_data['loc_data']))

        # Table 8: Comprehensive Summary
        story.extend(create_table_data(f"8. Comprehensive File Summary ({len(cli_data['comprehensive_data'])} Files)", 
                                        ["File Path", "LOC", "CC", "Risk Score", "Main Factor", "Fan-In (Dep.)"], 
                                        cli_data['comprehensive_data']))

        # Table 9: Security Hotspots
        story.append(Paragraph("🚨 Security Hotspots and Sensitive Data Scan", styles['h2']))
        story.extend(create_table_data(f"9. Security Hotspots ({len(cli_data['security_data'])} Issues Found)", 
                                        ["File Path", "Issue Type", "Severity", "Context/Line No."], 
                                        cli_data['security_data']))


        doc.build(story)
        print(f"\n✅ PDF Report successfully generated: {output_filename}")
        
    except Exception as e:
        print(f"\n❌ Failed to generate PDF report: {e}", file=sys.stderr)


# --- CLI Printing Functions ---

def print_table(title: str, headers: List[str], data: List[List[Any]]):
    """A generic function to print a simple ASCII table with color."""
    if not data:
        print(colorize(f"\n### {title}", COLOR_BLUE + COLOR_BOLD))
        print("--- No data available for this table. ---")
        return

    print(colorize(f"\n### {title}", COLOR_BLUE + COLOR_BOLD))
    
    def clean_text(text):
        # Removes all color codes before calculating length
        return text.replace(COLOR_END, '').replace(COLOR_RED, '').replace(COLOR_YELLOW, '').replace(COLOR_GREEN, '').replace(COLOR_WHITE, '').replace(COLOR_BLUE, '').replace(COLOR_BOLD, '').replace(COLOR_GRAY, '')

    col_widths = [len(h) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(clean_text(str(cell))))
            
    col_widths = [w + 2 for w in col_widths]
    
    separator = "+" + "+".join(["-" * w for w in col_widths]) + "+"
    print(separator)
    
    header_line = "|" + "".join([str(h).ljust(col_widths[i]) for i, h in enumerate(headers)]) + "|"
    print(header_line)
    print(separator)
    
    for row in data:
        # Calculate padding adjustment needed due to hidden ANSI color codes
        row_line = "|"
        for i, cell in enumerate(row):
            padding_adjustment = len(str(cell)) - len(clean_text(str(cell)))
            row_line += str(cell).ljust(col_widths[i] + padding_adjustment) + "|"
        print(row_line)
        
    print(separator)

def generate_refactor_summary_internal(top_risk_data: List[Dict[str, Any]]) -> str:
    """
    Internal function to call the Gemini API and generate the summary.
    """
    # NOTE: The check for API key validity is handled externally on client creation.
    if client is None:
        return f"Gemini API is unavailable or client failed to initialize (API key invalid/missing)."

    if not top_risk_data:
        return "Not enough data (no high-risk files) to generate AI insights."

    data_points = "\n".join([
        f"- File: {d['path']}, Risk Score: {d['risk_score']:.2f}, Main Factor: {d.get('main_factor', 'N/A')}, Complexity: {d.get('complexity', 0)}"
        for d in top_risk_data
    ])
    
    prompt = f"""
    Analyze the following top high-risk files (Risk Score 0-100, 100 is max debt).
    
    Data:
    {data_points}
    
    Generate a concise, 4-point summary suitable for a developer report:
    1. Overall highest-risk concern and why (mention the top file/score).
    2. A primary refactoring recommendation (e.g., reduce complexity, split ownership).
    3. The most complex file that needs immediate attention.
    4. A positive statement summarizing the low-risk areas or overall health.
    
    Format the output purely as a markdown list without any introduction or conclusion.
    """
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        return response.text
        
    except APIError as e:
        return f"Gemini API Error: Failed to generate summary. ({e})"
    except Exception as e:
        return f"An unexpected error occurred during API call: {e}"


def generate_cli_report(repo_url: str, all_file_data: Dict[str, Dict[str, Any]]):
    """Generates and prints the final CLI report, and collects data for PDF."""
    
    # 🚨 Collect all generated data lists into a dictionary for PDF generation later
    cli_data_collected = {}
    
    # Safely pop/extract data
    repo_stats = all_file_data.pop('_repo_stats', {})
    contributor_data = all_file_data.pop('_contributor_stats', {})
    # KEY STEP: Extract repo_metadata
    repo_metadata = all_file_data.pop('_repo_metadata', {}) 
    
    repo_score = repo_stats.get('overall_technical_debt', 0)
    max_values = repo_stats.get('max_values', {})
    
    cli_data_collected['repo_score'] = repo_score
    cli_data_collected.update(repo_metadata) 
    
    # IMPORTANT: file_list contains ALL files with data
    file_list = [(path, data) for path, data in all_file_data.items() if 'risk_score' in data and data.get('loc', 0) > 0]
    cli_data_collected['files_analyzed'] = len(file_list)

    if not file_list:
        print("⚠️ No relevant source files with analysis data found to report.")
        return cli_data_collected 

    # --- REPO-WIDE CALCULATIONS AND SUMMARY ---
    repo_complexities = [d['complexity'] for _, d in file_list]
    repo_chruns = [d.get('lines_added', 0) + d.get('lines_removed', 0) for _, d in file_list]
    repo_entropy = [d.get('ownership_entropy', 0.0) for _, d in file_list]

    avg_complexity = statistics.mean(repo_complexities) if repo_complexities else 0
    avg_churn = statistics.mean(repo_chruns) if repo_chruns else 0
    ownership_dispersion_index = statistics.stdev(repo_entropy) if len(repo_entropy) > 1 else 0
    
    colored_repo_score = get_risk_color(repo_score) + f"{repo_score:.2f} / 100" + COLOR_END

    # --- 1. Overall Repository Technical Debt Score ---
    print(colorize(f"\n## 📊 Repository Analysis Summary", COLOR_BLUE))
    print(f"**URL:** {repo_url}")
    print(f"**Files Analyzed:** {len(file_list)}")
    print(f"\n🚨 {colorize('OVERALL TECHNICAL DEBT SCORE:', COLOR_BOLD)} {colored_repo_score}")
    
    print(colorize(f"\n### Repository Averages", COLOR_BLUE))
    print(f"* Average File Complexity (CC): {avg_complexity:.1f}")
    print(f"* Average File Churn (LOC changed): {avg_churn:.0f}")
    print(f"* {colorize('Ownership Dispersion Index:', COLOR_BOLD)} {ownership_dispersion_index:.2f}")
    print("\n" + "---"*15)
    
    # --- Print Repo Metadata (Includes ALL Dependencies) ---
    print_repo_metadata(repo_metadata)


    # --- START OF ALL TABLE GENERATION (CLI AND PDF DATA COLLECTION) ---
    
    try:
        # --- 2. All Highest-Risk Files ---
        valid_file_list = [item for item in file_list if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], dict)]
        
        # Table 1: No Slicing
        top_risk = sorted(valid_file_list, key=lambda x: x[1].get('risk_score', 0), reverse=True)

        # --- 2.5 GEMINI AI-POWERED SUMMARY (Uses top 3 for prompt) ---
        ai_summary = ""
        if top_risk and client is not None and GEMINI_API_KEY != "YOUR_HARDCODED_GEMINI_API_KEY_HERE":
            top_3_data = [{'path': path, **data} for path, data in top_risk[:3]]
            ai_summary = generate_refactor_summary_internal(top_3_data) 
            cli_data_collected['ai_summary'] = ai_summary # Collect for PDF
            
            print(colorize("\n## 🧠 AI-Powered Technical Debt Insights", COLOR_BLUE))
            print("-" * 50)
            print(ai_summary)
            print("-" * 50)
        elif top_risk:
            ai_summary = "AI summary skipped (API key invalid/missing or client failed to initialize)."
            cli_data_collected['ai_summary'] = ai_summary 
            print(colorize("\n## 🧠 AI-Powered Technical Debt Insights", COLOR_BLUE))
            print("--- AI summary skipped (API key invalid/missing or client failed to initialize). ---")
            print("-" * 50)
        else:
             cli_data_collected['ai_summary'] = "No high-risk files found."


        # --- 3. Print Top Risk Table ---
        print(f"\n> {colorize('Description: These files have the highest weighted Technical Debt Score, combining complexity, churn, bug frequency, and ownership entropy. They are the top priority for refactoring.', COLOR_GRAY)}")
        
        risk_data = []
        for path, data in top_risk:
            colored_path = colorize(path, COLOR_WHITE)
            risk_score = data.get('risk_score', 0)
            
            colored_score = get_risk_color(risk_score) + f"{risk_score:.2f}" + COLOR_END
            factor = find_main_contributing_factor(data, max_values)
            data['main_factor'] = factor # Store factor for PDF
            
            risk_data.append([colored_path, colored_score, factor])
            
        print_table(f"1. All {len(risk_data)} Highest-Risk Files", 
                    ["File Path", "Risk Score (0-100)", "Main Factor"], 
                    risk_data)
        cli_data_collected['risk_data'] = risk_data # Collect for PDF
        
    except Exception as e:
        print(colorize(f"\n❌ CRITICAL ERROR generating Top Risk Table (1) or Gemini Summary: {e}", COLOR_RED), file=sys.stderr)


    try:
        # --- 4. Refactor Priority List (Risk * Churn * Dependency) ---
        def refactor_key(item: Tuple[str, Dict[str, Any]]):
            data = item[1]
            dep_score = data.get('fan_in', 0) * 2 + data.get('fan_out', 0) * 1
            churn = data.get('lines_added', 0) + data.get('lines_removed', 0)
            return data.get('risk_score', 0) * (churn + 1) * (dep_score + 1) 
            
        # Table 2: No Slicing
        refactor_list = sorted(file_list, key=refactor_key, reverse=True) 
        refactor_data = []
        
        max_refactor_score = refactor_key(refactor_list[0]) if refactor_list else 1
        
        for path, data in refactor_list:
            colored_path = colorize(path, COLOR_WHITE)
            score = refactor_key((path, data))
            
            normalized_score = (score / max_refactor_score) * 100 if max_refactor_score else 0
            colored_score = get_risk_color(normalized_score) + f"{score:.0f}" + COLOR_END
            
            refactor_data.append([colored_path, colored_score, data.get('fan_in', 0), data.get('lines_added', 0) + data.get('lines_removed', 0)])
            
        print(f"\n> {colorize('Description: Files ranked by the likelihood of causing a major regression. High scores mean the file is risky, frequently changes, and many other files depend on it (Fan-in).', COLOR_GRAY)}")
        print_table(f"2. All {len(refactor_data)} Highest Regression Risk Files (Change & Dependency)", 
                    ["File Path", "Combined Score", "Fan-in", "Total Changes"], 
                    refactor_data)
        cli_data_collected['refactor_data'] = refactor_data # Collect for PDF
                    
    except Exception as e:
        print(colorize(f"\n❌ Error printing Regression Risk List (2): {e}", COLOR_RED), file=sys.stderr)

    try:
        # --- 5. Churn vs. Complexity & Anti-Pattern Detection ---
        # Table 3: No Slicing
        god_classes = sorted(file_list, key=lambda x: x[1].get('complexity', 0) * (x[1].get('lines_added', 0) + x[1].get('lines_removed', 0)), reverse=True)
        god_data = []
        
        for path, data in god_classes:
            colored_path = colorize(path, COLOR_WHITE)
            churn = data.get('lines_added', 0) + data.get('lines_removed', 0)
            
            complexity_score = data.get('complexity', 0)
            cc_color = COLOR_GREEN
            if complexity_score > 100:
                cc_color = COLOR_RED
            elif complexity_score > 50:
                cc_color = COLOR_YELLOW
                
            colored_cc = colorize(str(complexity_score), cc_color)
            
            god_data.append([
                colored_path, 
                data.get('loc', 0), 
                colored_cc,
                churn
            ])
            
        print(f"\n> {colorize('Description: Files that are excessively large (LOC), complex (CC), and frequently changed. These are anti-patterns that desperately need to be broken down.', COLOR_GRAY)}")
        print_table(f"3. All {len(god_data)} Anti-Pattern Candidates (Files to Break Apart)", 
                    ["File Path", "Total Lines", "Complexity (CC)", "Total Changes"], 
                    god_data)
        cli_data_collected['god_data'] = god_data # Collect for PDF

    except Exception as e:
        print(colorize(f"\n❌ Error printing Anti-Pattern Candidates (3): {e}", COLOR_RED), file=sys.stderr)
        
    try:
        # --- 6. Systemic Risk Hotspots ---
        def systemic_key(item: Tuple[str, Dict[str, Any]]):
            return item[1].get('systemic_risk_score', 0)
            
        # Table 4: No Slicing
        systemic_list = sorted(file_list, key=systemic_key, reverse=True)
        systemic_data = []
        
        max_systemic_score = max_values.get('systemic_risk_score', 1)
        
        for path, data in systemic_list:
            colored_path = colorize(path, COLOR_WHITE)
            score = data.get('systemic_risk_score', 0)
            
            normalized_score = (score / max_systemic_score) * 100 if max_systemic_score else 0
            colored_score = get_risk_color(normalized_score) + f"{score:.0f}" + COLOR_END
            
            factor = data.get('missing_test_coverage_factor', 1.0)
            test_status = colorize("Likely Covered", COLOR_GREEN) if factor < 0.2 else \
                          colorize("High Risk/Untested", COLOR_RED) if factor > 0.9 else \
                          colorize("Ambiguous", COLOR_YELLOW)
            
            systemic_data.append([
                colored_path, 
                colored_score, 
                data.get('fan_in', 0), 
                test_status
            ])
            
        print(f"\n> {colorize('Description: The most dangerous files. They are highly depended upon (Fan-in) and likely have poor test coverage. A bug here can cause the entire system to fail.', COLOR_GRAY)}")
        print_table(f"4. All {len(systemic_data)} Critical Systemic Risk Hotspots", 
                    ["File Path", "Systemic Score", "Dependent Files (Fan-In)", "Test Status"], 
                    systemic_data)
        cli_data_collected['systemic_data'] = systemic_data # Collect for PDF

    except Exception as e:
        print(colorize(f"\n❌ Error printing Systemic Risk Hotspots (4): {e}", COLOR_RED), file=sys.stderr)


    try:
        # --- 7. Contributor Efficiency Ranking ---
        if contributor_data:
            print("\n" + "---"*15)
            print(colorize("## 👤 Contributor Efficiency Ranking", COLOR_BLUE))
            
            # Rank 1: Most Efficient (Highest E-Score) - NO SLICING
            top_efficient = sorted(contributor_data.items(), key=lambda x: x[1].get('efficiency_score', 0), reverse=True)
            efficient_data = []
            
            efficient_headers = ["Author (Email Prefix)", "Efficiency Score (Higher=Better)", "Commits", "Lines Added"]
            
            for email, stats in top_efficient:
                name = email.split('@')[0] 
                
                e_score_norm = stats.get('efficiency_score', 0) * 100 
                colored_e_score = get_risk_color(100 - e_score_norm) + f"{stats.get('efficiency_score', 0):.3f}" + COLOR_END
                
                efficient_data.append([name, colored_e_score, stats.get('total_commits', 0), f"{int(stats.get('lines_added', 0)):,d}"])
                
            print(f"\n> {colorize('Description: Authors ranked by efficiency (high output/low complexity/bug-fix cost). These are your key contributors.', COLOR_GRAY)}")
            print_table(f"5. All {len(efficient_data)} Most Efficient Contributors", 
                        efficient_headers, 
                        efficient_data)
            cli_data_collected['efficient_data'] = efficient_data # Collect for PDF
                        
            # Rank 2: Priority Coaching Candidates - NO SLICING
            def risk_inefficiency_key(item: Tuple[str, Dict[str, Any]]):
                stats = item[1]
                e_score = stats.get('efficiency_score', 0)
                risk_score = stats.get('risk_score', 0)
                # Only include contributors with > 10 commits for coaching consideration
                if stats.get('total_commits', 0) <= 10:
                    return 0.0
                if e_score > 0.01:
                    return risk_score / e_score
                return risk_score * 100
                
            # Filtered by min 10 commits, then sorted (NO SLICING)
            priority_coaching = sorted([
                (e, s) for e, s in contributor_data.items() if s.get('total_commits', 0) > 10
            ], key=risk_inefficiency_key, reverse=True)
            
            coaching_data = []
            coaching_headers = ["Author (Email Prefix)", "Avg Risk Score", "Efficiency Score (Lower=Worse)", "Commits"]
            
            for email, stats in priority_coaching:
                name = email.split('@')[0]
                
                colored_risk_score = get_risk_color(stats.get('risk_score', 0)) + f"{stats.get('risk_score', 0):.2f}" + COLOR_END
                
                e_score_norm = stats.get('efficiency_score', 0) * 100
                colored_e_score = get_risk_color(e_score_norm) + f"{stats.get('efficiency_score', 0):.3f}" + COLOR_END
                
                coaching_data.append([name, colored_risk_score, colored_e_score, stats.get('total_commits', 0)])
                
            print(f"\n> {colorize('Description: Authors whose work is associated with high average risk, despite moderate/low overall efficiency (min 10 commits). They may need code review and mentorship.', COLOR_GRAY)}")
            print_table(f"6. All {len(coaching_data)} Priority Coaching Candidates", 
                        coaching_headers, 
                        coaching_data)
            cli_data_collected['coaching_data'] = coaching_data # Collect for PDF
            
            print("\n" + "---"*15)
    except Exception as e:
        print(colorize(f"\n❌ Error printing Contributor Tables (5 & 6): {e}", COLOR_RED), file=sys.stderr)
        
    
    try:
        # --- 7. Files Analyzed with Lines of Code (LOC) ---
        # Sort by LOC descending
        loc_list = sorted(file_list, key=lambda x: x[1].get('loc', 0), reverse=True)
        loc_data = []

        for path, data in loc_list:
            colored_path = colorize(path, COLOR_WHITE)
            loc = data.get('loc', 0)
            
            loc_data.append([
                colored_path,
                f"{loc:,d}" # Formatted with comma separators
            ])
            
        print(f"\n> {colorize('Description: A complete list of all analyzed files sorted by size (Lines of Code), offering a quick overview of the repository structure.', COLOR_GRAY)}")
        print_table(f"7. All {len(loc_data)} Files Analyzed with Lines of Code (LOC)", 
                    ["File Path", "Lines of Code (LOC)"], 
                    loc_data)
        cli_data_collected['loc_data'] = loc_data # Collect for PDF

    except Exception as e:
        print(colorize(f"\n❌ Error printing Files by LOC Table (7): {e}", COLOR_RED), file=sys.stderr)
        
    # ------------------------------------------------------------------
    # --- TABLE 8: Comprehensive File Summary ---
    # ------------------------------------------------------------------
    try:
        # Sort the final summary table by Risk Score (descending)
        final_summary_list = sorted(file_list, key=lambda x: x[1].get('risk_score', 0), reverse=True)
        comprehensive_data = []

        for path, data in final_summary_list:
            colored_path = colorize(path, COLOR_WHITE)
            risk_score = data.get('risk_score', 0)
            complexity = data.get('complexity', 0)
            fan_in = data.get('fan_in', 0)
            
            colored_risk_score = get_risk_color(risk_score) + f"{risk_score:.2f}" + COLOR_END
            
            # Recalculate main factor if it wasn't saved perfectly earlier (to ensure accuracy)
            factor = find_main_contributing_factor(data, max_values)
            
            # Color complexity based on score
            cc_color = COLOR_GREEN
            if complexity > 100:
                cc_color = COLOR_RED
            elif complexity > 50:
                cc_color = COLOR_YELLOW
            colored_cc = colorize(str(complexity), cc_color)

            comprehensive_data.append([
                colored_path,
                data.get('loc', 0),
                colored_cc,
                colored_risk_score,
                factor,
                fan_in
            ])
            
        print(f"\n> {colorize('Description: The ultimate consolidated view of every analyzed file, merging size, complexity, risk, its primary risk cause, and its systemic impact (Fan-In). Sorted by Risk Score.', COLOR_GRAY)}")
        print_table(f"8. Comprehensive File Summary ({len(comprehensive_data)} Files)", 
                    ["File Path", "LOC", "CC", "Risk Score", "Main Factor", "Fan-In (Dep.)"], 
                    comprehensive_data)
        cli_data_collected['comprehensive_data'] = comprehensive_data # Collect for PDF

    except Exception as e:
        print(colorize(f"\n❌ Error printing Comprehensive File Summary Table (8): {e}", COLOR_RED), file=sys.stderr)
    
    # ------------------------------------------------------------------
    # --- NEW TABLE 9: Security Hotspots and Sensitive Data Scan ---
    # ------------------------------------------------------------------
    
    # Simulate a security scan result. In a real tool, this would be generated by scanning code.
  

    # ------------------------------------------------------------------
    # --- TABLE 9: Security Hotspots and Sensitive Data Scan (REAL) ---
    # ------------------------------------------------------------------
   # ------------------------------------------------------------------
    # --- TABLE 9: Security Hotspots and Sensitive Data Scan (REAL) ---
    # ------------------------------------------------------------------
   # ------------------------------------------------------------------
    # --- TABLE 9: Security Hotspots and Sensitive Data Scan (REAL) ---
    # ------------------------------------------------------------------
    # ... (After Table 8 logic) ...
    
    # ------------------------------------------------------------------
    # --- TABLE 9: Security Hotspots and Sensitive Data Scan (REAL) ---
    # ------------------------------------------------------------------
   