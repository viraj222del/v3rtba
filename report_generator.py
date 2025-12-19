from typing import Dict, Any, List, Tuple
from operator import itemgetter
import statistics
import os
import shutil
import tempfile
import sys
import stat
import datetime 
import re # Needed for print_table's width calculation logic

# --- PDF Imports ---


# --- Gemini SDK Setup ---
from google import genai
from google.genai.errors import APIError
import os

# --- FEATURE: KEYWORD SECURITY SCANNER (TABLE 9) ---

def security_keyword_scan(scan_directory: str) -> Tuple[List[List[Any]], int]:
    """
    Scans files in the target directory specifically for the keywords: 
    'api', 'apikey', and 'api key' (case-insensitive).
    
    It returns a list of [File Path, Total Matches] and the grand total count.
    """
    
    # Target keywords as explicitly requested by the user
    TARGET_KEYWORDS = ["api", "apikey", "api key"]
    SKIP_EXTENSIONS = ('.jpg', '.png', '.gif', '.zip', '.exe', '.dll', '.bin', '.pdf', '.lock', '.min.js', '.ico')
    
    file_findings: List[List[Any]] = []
    total_findings_count = 0 

    if not scan_directory or scan_directory.startswith('http') or not os.path.isdir(scan_directory):
        # Return empty data if the path is invalid
        return [], 0
    
    print(f"\nScanning local directory: {os.path.basename(scan_directory)} for specific security keywords...")

    for root, dirnames, files in os.walk(scan_directory):
        # Skip hidden directories
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            
        for file_name in files:
            # Skip binary and minified files
            if file_name.lower().endswith(SKIP_EXTENSIONS):
                continue
            
            file_path = os.path.join(root, file_name)
            relative_path = os.path.relpath(file_path, scan_directory)
            
            api_count = 0
            
            try:
                # Skip files larger than 1MB
                if os.path.getsize(file_path) > 1024 * 1024: 
                    continue
                    
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    for keyword in TARGET_KEYWORDS:
                        api_count += content.count(keyword) 
                        
            except Exception:
                # Skip files that cannot be read
                continue 
            
            if api_count > 0:
                # Return format: [file_path, total_api_matches]
                file_findings.append([
                    relative_path, 
                    api_count
                ])

            total_findings_count += api_count
            
    print(f"Security scan finished: {total_findings_count} potential issues found.")
    return file_findings, total_findings_count

# --- ANSI Color Codes (DISABLED for Plain Text Output) ---
COLOR_END = ''
COLOR_WHITE = ''
COLOR_BLUE = ''
COLOR_GREEN = ''
COLOR_YELLOW = ''
COLOR_RED = ''
COLOR_BOLD = ''
COLOR_GRAY = '' 

# --- Helper functions (colorize now returns plain text) ---

def normalize_metric(value: float, max_value: float, min_value: float = 0.0) -> float:
    if max_value == min_value or max_value == 0:
        return 0.0
    value = max(min_value, value)
    return min(1.0, (value - min_value) / (max_value - min_value))

def get_risk_color(score: float, max_score: float = 100.0) -> str:
    """Returns empty string (plain text) regardless of score."""
    return ""
        
def colorize(text: Any, color_code: str = "", reset_color: bool = True) -> str:
    """Returns only the text, ignoring color codes."""
    return str(text)

def find_main_contributing_factor(data: Dict[str, Any], max_values: Dict[str, float]) -> str:
    """Determines the single metric contributing most to the risk score (Logic Unchanged)."""
    
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
          return "Low Risk / High Stability"
          
    return f"{main_factor[0]} ({main_factor[1]*100/total_contribution:.1f}%)"


def print_table(title: str, headers: List[str], data: List[List[Any]]):
    """A generic function to print a simple ASCII table (Colors disabled)."""
    if not data:
        print(f"\n### {title}")
        print("--- No data available for this table. ---")
        return

    # Print the title without color
    print(f"\n### {title}")
    
    col_widths = [len(h) for h in headers]
    
    # Calculate widths using simple length since there are no colors
    def get_display_width(text):
        return len(str(text))
        
    for row in data:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], get_display_width(cell))
            
    col_widths = [w + 2 for w in col_widths]
    
    separator = "+" + "+".join(["-" * w for w in col_widths]) + "+"
    print(separator)
    
    header_line = "|" + "".join([str(h).ljust(col_widths[i]) for i, h in enumerate(headers)]) + "|"
    print(header_line)
    print(separator)
    
    for row in data:
        row_line = "|"
        for i, cell in enumerate(row):
            stripped_len = get_display_width(cell)
            padding_needed = col_widths[i] - stripped_len
            row_line += str(cell) + (" " * padding_needed) + "|"
        print(row_line)
        
    print(separator)

# Stub for the AI summary function (logic remains external/mocked)
 



def generate_cli_report(repo_url: str, all_file_data: Dict[str, Dict[str, Any]]):
    """Generates and prints the final CLI report using the new required output format (plain text)."""
    
    cli_data_collected = {} 
    
    repo_stats = all_file_data.pop('_repo_stats', {})
    contributor_data = all_file_data.pop('_contributor_stats', {})
    repo_metadata = all_file_data.pop('_repo_metadata', {}) 
    temp_local_path = all_file_data.pop('_local_repo_path', repo_url) 

    repo_score = repo_stats.get('overall_technical_debt', 0)
    max_values = repo_stats.get('max_values', {})
    
    cli_data_collected['repo_score'] = repo_score
    cli_data_collected.update(repo_metadata) 
    
    # Filter files for analysis
    file_list = [(path, data) for path, data in all_file_data.items() if 'risk_score' in data and data.get('loc', 0) > 0]
    cli_data_collected['files_analyzed'] = len(file_list)

    if not file_list:
        print("⚠️ No relevant source files with analysis data found to report.")
        return cli_data_collected 

    # --- Print Header: URL and Files Analyzed ---
    print(f"\n## Analysis Report")
    print("-" * 50)
    print(f"URL: {repo_url}")
    print(f"No. of Files Analysed: {len(file_list)}")
    print("-" * 50)

    # --- 1. Data Preparation ---
    
    # Prepare all files sorted by LOC (for Table 2)
    loc_list = sorted(file_list, key=lambda x: x[1].get('loc', 0), reverse=True)
    
    # Prepare all files for Complexity/Churn (for Table 3)
    max_complexity = max_values.get('complexity', 1)
    
    # Prepare all files sorted by Risk (for Table 4, 7)
    top_risk = sorted(file_list, key=lambda x: x[1].get('risk_score', 0), reverse=True)
    
    # Prepare all files sorted by Systemic Risk (for Table 5)
    def systemic_key(item: Tuple[str, Dict[str, Any]]):
        return item[1].get('systemic_risk_score', 0)
    systemic_list = sorted(file_list, key=systemic_key, reverse=True)
    
    # Prepare contributor data (for Table 6)
    top_efficient = sorted(contributor_data.items(), key=lambda x: x[1].get('efficiency_score', 0), reverse=True)

    # --- 2. Table: (file name, loc) ---
    loc_data = []
    for path, data in loc_list:
        loc_data.append([path, f"{data.get('loc', 0):,d}"])
        
    print(f"\n> Description: All files sorted by size (Lines of Code).")
    print_table(f"2. File Size Summary ({len(loc_data)} Files)", 
                ["File Path", "LOC"], 
                loc_data)

    # --- 3. Table: (file, code complexity, total changes) ---
    complexity_churn_data = []
    for path, data in file_list:
        churn = data.get('lines_added', 0) + data.get('lines_removed', 0)
        complexity_score = data.get('complexity', 0)
        
        plain_cc = str(complexity_score)
        plain_churn = str(churn)
        
        complexity_churn_data.append([
            path, 
            plain_cc,
            plain_churn
        ])
    
    def get_sortable_numeric_value(string_value):
        try:
            # Handles comma-formatted strings if they were present
            return int(str(string_value).replace(',', ''))
        except ValueError:
            return 0
            
    # Sort by complexity * churn 
    complexity_churn_data.sort(key=lambda x: get_sortable_numeric_value(x[1]) * get_sortable_numeric_value(x[2]), reverse=True)

    print(f"\n> Description: Files ranked by the combination of Cyclomatic Complexity (CC) and Total Changes (Churn). Indicates high maintenance cost and complexity.")
    print_table(f"3. Complexity and Change Cost Summary ({len(complexity_churn_data)} Files)", 
                ["File Path", "Code Complexity (CC)", "Total Changes (Churn)"], 
                complexity_churn_data)

    # --- 4. Table: (file, risk score, main factor) ---
    risk_data = []
    for path, data in top_risk:
        risk_score = data.get('risk_score', 0)
        plain_score = f"{risk_score:.2f}"
        factor = find_main_contributing_factor(data, max_values)
        
        risk_data.append([path, plain_score, factor])
        
    print(f"\n> Description: Files with the highest weighted Technical Debt Score. Top priority for refactoring.")
    print_table(f"4. Highest-Risk Files ({len(risk_data)} Files)", 
                ["File Path", "Risk Score (0-100)", "Main Factor"], 
                risk_data)

    # --- 5. Table: (file, fanin, test status, systematic score) ---
    systemic_data = []
    for path, data in systemic_list:
        score = data.get('systemic_risk_score', 0)
        plain_score = f"{score:.0f}"
        factor = data.get('missing_test_coverage_factor', 1.0)
        fan_in = data.get('fan_in', 0)
        
        plain_fan_in = str(fan_in)

        if factor < 0.2:
            test_status = "Likely Covered"
        elif factor > 0.9:
            test_status = "High Risk/Untested"
        else:
            test_status = "Ambiguous"
        
        # Required order: (file, fanin, test status, systematic score)
        systemic_data.append([
            path, 
            plain_fan_in, 
            test_status, 
            plain_score
        ])
            
    print(f"\n> Description: Files that are highly depended upon (Fan-in) and/or lack test coverage. A bug here can cause the entire system to fail.")
    print_table(f"5. Critical Systemic Risk Hotspots ({len(systemic_data)} Files)", 
                ["File Path", "Dependent Files (Fan-In)", "Test Status", "Systematic Score"], 
                systemic_data)
        
    # --- 6. Table: (author, commits, lines added, efficiency score) ---
    efficient_data = []
    for email, stats in top_efficient:
        name = email.split('@')[0] 
        plain_e_score = f"{stats.get('efficiency_score', 0):.3f}"
        
        # Required order: (author, commits, lines added, efficiency score)
        efficient_data.append([
            name, 
            stats.get('total_commits', 0), 
            f"{int(stats.get('lines_added', 0)):,d}", 
            plain_e_score
        ])
        
    print(f"\n> Description: Authors ranked by efficiency (high output/low complexity/bug-fix cost). These are your key contributors.")
    print_table(f"6. Contributor Efficiency Analysis ({len(efficient_data)} Authors)", 
                ["Author (Email Prefix)", "Commits", "Lines Added", "Efficiency Score (Higher=Better)"], 
                efficient_data)


    # --- 7. Table: Summary (file, loc, cc, risk score, main factor, fan in, churn) ---
    final_summary_list = top_risk 
    comprehensive_data = []

    for path, data in final_summary_list:
        risk_score = data.get('risk_score', 0)
        complexity = data.get('complexity', 0)
        fan_in = data.get('fan_in', 0)
        churn = data.get('lines_added', 0) + data.get('lines_removed', 0)
        
        plain_risk_score = f"{risk_score:.2f}"
        factor = find_main_contributing_factor(data, max_values)
        plain_cc = str(complexity)
        plain_fan_in = str(fan_in)
        plain_churn = str(churn)

        # Required order: (file, loc, cc, risk score, main factor, fan in, churn)
        comprehensive_data.append([
            path,
            data.get('loc', 0),
            plain_cc,
            plain_risk_score,
            factor,
            plain_fan_in,
            plain_churn
        ])
        
    print(f"\n> Description: The consolidated view of every analyzed file, merging all core metrics for comparative analysis. Sorted by Risk Score.")
    print_table(f"7. Comprehensive File Summary ({len(comprehensive_data)} Files)", 
                ["File Path", "LOC", "CC", "Risk Score", "Main Factor", "Fan-In", "Churn"], 
                comprehensive_data)
    
    
    # ------------------------------------------------------------------
    # --- 8. Table: Comment-to-Code Ratio Summary (NEW TABLE) ---
    # ------------------------------------------------------------------
    comment_ratio_data = []
    for path, data in file_list:
        loc = data.get('loc', 0)
        comment_lines = data.get('comment_lines', 0)
        
        total_lines = loc + comment_lines
        
        # Calculate ratio: Comment Lines / (LOC + Comment Lines)
        if total_lines > 0:
            ratio = comment_lines / total_lines
        else:
            ratio = 0.0

        comment_ratio_data.append({
            'path': path, 
            'ratio': ratio,
            'comment_lines': comment_lines,
            'loc': loc
        })
        
    # Sort by ratio (Higher is better/more documented)
    comment_ratio_data.sort(key=itemgetter('ratio'), reverse=True)

    comment_ratio_table = []
    for item in comment_ratio_data:
        # Format the ratio as a percentage
        formatted_ratio = f"{item['ratio'] * 100:.1f}%"
        comment_ratio_table.append([
            item['path'], 
            str(item['comment_lines']),
            str(item['loc']),
            formatted_ratio
        ])
        
    print(f"\n> Description: Measures the file's documentation quality (higher ratio is generally better). Calculated as Comment Lines / (Lines of Code + Comment Lines).")
    print_table(f"8. Comment-to-Code Ratio Summary ({len(comment_ratio_table)} Files)", 
                ["File Path", "Comment Lines", "LOC (Code)", "Comment Ratio"], 
                comment_ratio_table)


    # ------------------------------------------------------------------
    # --- 9. Table: Security Keyword Matches (RENUMBERED FROM 8) ---
    # ------------------------------------------------------------------
    try:
        # Pass the local repo path to the new security scan function
        security_data, total_api_findings = security_keyword_scan(temp_local_path) 

        # Sort by count (item at index 1)
        if security_data:
            security_data.sort(key=itemgetter(1), reverse=True) 

        # Convert counts to strings for table printing
        security_table_data = [[item[0], str(item[1])] for item in security_data]

        print(f"\n> Description: Files containing explicit API key keywords ('api', 'apikey', 'api key'). Potential security hotspots.")
        headers = ["File Path", "Keyword Matches (n)"]
        
        # FIX APPLIED: Corrected variable name from security_data_parsed to security_data and updated number to 9.
        print_table(f"9. Security Keyword Hotspots ({len(security_data)} Files with Matches | {total_api_findings} Total Matches)", 
                    headers, 
                    security_table_data)

    except Exception as e:
        print(f"\n❌ Error printing Security Hotspot Table (9): {e}", file=sys.stderr)


    # --- FINAL FOOTER ---
    
    plain_repo_score = f"{repo_score:.2f}"
    
    print("\n" + "=" * 50)
    print(f"Overall Tech Debt: {plain_repo_score} / 100")
    
    ai_summary = "AI summary skipped (API key invalid/missing or client failed to initialize)."
    
    print(f"\nAI Summary:")
    print(f"{ai_summary}")

    print("=" * 50)


    return cli_data_collected
