# security_analyzer.py - A Single-File CLI Security Analysis Tool with Color
#
# Dependencies required: pip install GitPython bandit safety colorama
#
# Note: This script uses subprocess to run external tools (Bandit, Safety)
# and requires them to be installed and available in the system PATH.

import argparse
import os
import shutil
import tempfile
import subprocess
import json
import re
import sys
from typing import Dict, Any, List, Tuple
from colorama import init, Fore, Style # Import colorama for styling

# Initialize Colorama for cross-platform compatibility
init(autoreset=True)

# --- Configuration ---
TOOL_VERSION = "v1.0.0-color-release"
MAX_PENALTY_SCORE = 100 # Used for normalizing the Risk Score (Feature 7)

# --- Feature 7: Scoring Weights ---
SEVERITY_WEIGHTS: Dict[str, int] = {
    'HIGH': 10,
    'MEDIUM': 5,
    'LOW': 1,
    'INFO': 0
}

# --- Color Mapping for Output ---
COLOR_MAP: Dict[str, str] = {
    'HIGH': Fore.RED + Style.BRIGHT,
    'MEDIUM': Fore.YELLOW,
    'LOW': Fore.BLUE,
    'INFO': Fore.GREEN,
    'SUCCESS': Fore.GREEN + Style.BRIGHT,
    'ERROR': Fore.RED + Style.BRIGHT,
    'WARNING': Fore.YELLOW + Style.BRIGHT,
    'HEADER': Fore.CYAN + Style.BRIGHT,
    'NORMAL': Fore.WHITE
}

# --- Feature 1: Secrets Detection Patterns ---
SECRET_PATTERNS: Dict[str, str] = {
    "AWS_KEY": r"AKIA[0-9A-Z]{16}",
    "GENERIC_PASSWORD": r"(password|passwd|pwd|secret|key|token)\s*=\s*['\"]([^'\"]+)['\"]",
    "PRIVATE_KEY": r"-----BEGIN (RSA|EC|DSA) PRIVATE KEY-----",
    "API_KEY": r"(api|client|access)[._]key\s*:\s*([a-z0-9]{32,64})"
}

# --- Utility Functions ---

def print_colored(message: str, color_key: str):
    """Prints a message using a predefined color."""
    print(f"{COLOR_MAP.get(color_key, COLOR_MAP['NORMAL'])}{message}{Style.RESET_ALL}")

def clean_up(path: str):
    """Clean up the temporary directory."""
    try:
        if os.path.exists(path):
            shutil.rmtree(path)
            print_colored(f"\n[CLEANUP] Removed temporary directory: {path}", 'NORMAL')
    except OSError as e:
        print_colored(f"[ERROR] Error cleaning up {path}: {e}", 'ERROR')

def run_external_tool(cmd: List[str], tool_name: str, target_path: str = None) -> Tuple[bool, str]:
    """Helper function to run external security tools."""
    print_colored(f"[{tool_name}] Running {tool_name}...", 'NORMAL')
    try:
        # Popen allows for better control, but run is simpler for synchronous CLI tools
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, check=False, timeout=600 # 10 minute timeout
        )
        # Bandit returns 0 for clean, 1 for issues found, but 2 for error
        if result.returncode not in [0, 1] and tool_name == 'Bandit':
             print_colored(f"[{tool_name}] Execution failed (Code {result.returncode}). Stderr: {result.stderr.strip()}", 'ERROR')
             return False, ""
        
        # Safety returns 0 for clean, 1 for issues found
        if result.returncode not in [0, 1] and tool_name == 'Safety':
             print_colored(f"[{tool_name}] Execution failed (Code {result.returncode}). Stderr: {result.stderr.strip()}", 'ERROR')
             return False, ""

        return True, result.stdout
    except FileNotFoundError:
        print_colored(f"[FATAL ERROR] '{cmd[0]}' command not found. Please ensure {tool_name} is installed and in PATH.", 'ERROR')
        return False, ""
    except subprocess.TimeoutExpired:
        print_colored(f"[{tool_name}] Execution timed out after 600 seconds.", 'ERROR')
        return False, ""
    except Exception as e:
        print_colored(f"[ERROR] {tool_name} scan failed: {e}", 'ERROR')
        return False, ""

def run_bandit(target_path: str) -> List[Dict[str, Any]]:
    """Feature 3, 4, 6: Runs Bandit SAST tool."""
    success, output = run_external_tool(['bandit', '-r', target_path, '-f', 'json', '-n', '3', '-q'], 'Bandit')
    
    findings: List[Dict[str, Any]] = []
    if success and output:
        try:
            bandit_results = json.loads(output)
            if 'results' in bandit_results:
                for item in bandit_results['results']:
                    # Map Bandit results to our standard format
                    findings.append({
                        "code": item['test_id'],
                        "severity": item['issue_severity'].upper(),
                        "msg": item['issue_text'],
                        "cwe": item['issue_cwe']['id'] if item.get('issue_cwe') else "N/A",
                        "file": os.path.relpath(item['filename'], target_path),
                        "line": item['line_number'],
                        "remediation": f"Check documentation for {item['test_id']} for detailed fix. Generally involves using safe libraries or inputs."
                    })
        except json.JSONDecodeError:
            print_colored("[ERROR] Failed to parse Bandit JSON output.", 'ERROR')
    
    return findings

def run_safety(target_path: str) -> List[Dict[str, Any]]:
    """Feature 2: Runs Safety tool on requirements files."""
    req_files = ['requirements.txt'] # Safety primarily checks this file
    found_vulnerabilities = []

    for req_file in req_files:
        full_path = os.path.join(target_path, req_file)
        if os.path.exists(full_path):
            success, output = run_external_tool(['safety', 'check', '-r', full_path, '--json'], 'Safety')
            
            if success and output:
                try:
                    safety_results = json.loads(output)
                    for finding in safety_results:
                        # Ensure finding structure is as expected from Safety's JSON output
                        if isinstance(finding, dict) and 'package' in finding:
                            found_vulnerabilities.append({
                                "code": "DEP-001",
                                "severity": "HIGH",
                                "msg": f"Vulnerable dependency: {finding['package']}@{finding['installed_version']}. ID: {finding.get('id', 'N/A')}",
                                "cwe": finding.get('cve', 'N/A'),
                                "file": req_file,
                                "line": 0,
                                "remediation": f"Upgrade to {finding['secure_versions']} or later."
                            })
                except json.JSONDecodeError:
                    print_colored("[ERROR] Failed to parse Safety JSON output.", 'ERROR')

    return found_vulnerabilities

def scan_for_secrets(target_path: str) -> List[Dict[str, Any]]:
    """Feature 1: Basic file content scan for hardcoded secrets."""
    print_colored("[CUSTOM] Scanning files for hardcoded secrets (Feature 1)...", 'NORMAL')
    secrets_found: List[Dict[str, Any]] = []
    
    # Simple walk, excluding common directories like .git, venv, node_modules
    for root, dirs, files in os.walk(target_path):
        dirs[:] = [d for d in dirs if d not in ['.git', 'venv', 'node_modules', '__pycache__']]
        
        for file in files:
            # Check common file types for secrets
            if not file.endswith(('.py', '.json', '.yaml', '.yml', '.env', '.sh', '.conf', '.txt', '.html', '.js', '.ts', '.java', '.go', '.c', '.h')):
                continue

            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, target_path)

            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f, 1):
                        for pattern_name, pattern_regex in SECRET_PATTERNS.items():
                            if re.search(pattern_regex, line, re.IGNORECASE | re.MULTILINE):
                                # Only report the first match per line for clarity
                                secrets_found.append({
                                    "code": f"SEC-{pattern_name}",
                                    "severity": "HIGH",
                                    "msg": f"Possible exposed {pattern_name.replace('_', ' ')}.",
                                    "cwe": "CWE-798 (Use of Hard-coded Credentials)",
                                    "file": relative_path,
                                    "line": i,
                                    "remediation": "Move secret to a secure environment variable or vault. Consider Git history cleaning."
                                })
                                break # Move to next line after finding one secret
            except Exception:
                pass # Skip files we cannot read/decode

    return secrets_found

# --- Core Analyzer Logic ---

def analyze_repo(repo_url: str, return_data: bool = False):
    """Clones and executes all security checks.
    
    Args:
        repo_url: GitHub repository URL to analyze
        return_data: If True, returns data dict instead of printing output
    
    Returns:
        If return_data=True, returns dict with keys: repo_url, risk_score, severity_counts, findings, tool_version
        Otherwise returns None and prints output
    """
    try:
        from git import Repo
    except ImportError:
        if return_data:
            return None
        print_colored("\n[FATAL ERROR] GitPython not found. Please install it (`pip install GitPython`).", 'ERROR')
        return None

    temp_dir = tempfile.mkdtemp()
    if not return_data:
        print_colored(f"\n[INFO] Starting analysis for: {repo_url}", 'NORMAL')
        print_colored(f"[INFO] Cloning repository into: {temp_dir}", 'NORMAL')

    try:
        # Clone the repository
        Repo.clone_from(repo_url, temp_dir)
        if not return_data:
            print_colored("[INFO] Cloning successful.", 'SUCCESS')
    except Exception as e:
        if return_data:
            return None
        print_colored(f"[FATAL ERROR] Failed to clone repository. Check URL and access rights: {e}", 'ERROR')
        clean_up(temp_dir)
        return None

    all_findings: List[Dict[str, Any]] = []

    # 1. Exposed Secrets & Credentials (File Content Scan)
    all_findings.extend(scan_for_secrets(temp_dir))
    
    # 2, 3, 4, 6: SAST Analysis (Bandit)
    all_findings.extend(run_bandit(temp_dir))

    # 2. Dependency Vulnerabilities (Safety)
    all_findings.extend(run_safety(temp_dir))

    # --- Feature 5: Secrets in Git History ---
    # NOTE: True Git History scan requires external tools like Gitleaks/TruffleHog binary.
    if not return_data:
        print_colored("[INFO] Skipping full Git History Scan (Feature 5) - Requires separate external binary install.", 'WARNING')
        print_colored("[INFO] Hardcoded Secrets check (Feature 1) covered current files.", 'WARNING')


    # --- Feature 7: Calculate Overall Security Risk Score ---
    total_penalty = 0
    severity_counts: Dict[str, int] = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'INFO': 0}

    for finding in all_findings:
        sev = finding['severity'].upper()
        if sev in SEVERITY_WEIGHTS:
            total_penalty += SEVERITY_WEIGHTS[sev]
            severity_counts[sev] += 1

    # Normalize the penalty to a 0-100 score where 100 is best (0 risk)
    penalty_ratio = min(1.0, total_penalty / MAX_PENALTY_SCORE)
    risk_score = int(100 - (penalty_ratio * 100))

    # --- Return data or display results ---
    if return_data:
        # Clean up the cloned repository
        clean_up(temp_dir)
        return {
            "repo_url": repo_url,
            "risk_score": risk_score,
            "severity_counts": severity_counts,
            "findings": all_findings,
            "tool_version": TOOL_VERSION
        }
    else:
        # --- Display Results ---
        display_output(repo_url, all_findings, severity_counts, risk_score)
        
        # Clean up the cloned repository
        clean_up(temp_dir)
        return None


def display_output(repo_url: str, findings: List[Dict[str, Any]], counts: Dict[str, int], risk_score: int):
    """Displays the final, structured analysis report with color."""
    
    print("\n" + "="*80)
    print_colored(f"### 🛡️ SECURITY ANALYSIS REPORT | {repo_url} ###", 'HEADER')
    print("="*80)

    # --- Feature 7: Overall Security Risk Score ---
    print_colored(f"\n## 📈 Overall Security Risk Score", 'HEADER')
    print("-" * 35)
    
    # Color code the risk score
    if risk_score > 90:
        score_color, score_msg = 'SUCCESS', 'Excellent'
    elif risk_score > 70:
        score_color, score_msg = 'INFO', 'Good'
    elif risk_score > 50:
        score_color, score_msg = 'WARNING', 'Needs Improvement'
    else:
        score_color, score_msg = 'ERROR', 'Critical'

    print_colored(f"**RISK SCORE:** {risk_score}/100 - ({score_msg})", score_color)
    print_colored(f"Total findings found: {len(findings)}", 'NORMAL')

    # --- Aggregated Severity Summary ---
    print_colored("\n## 🚨 Aggregated Severity Summary", 'HEADER')
    print("-" * 35)
    print_colored(f"HIGH: {counts.get('HIGH', 0)}", 'HIGH')
    print_colored(f"MEDIUM: {counts.get('MEDIUM', 0)}", 'MEDIUM')
    print_colored(f"LOW: {counts.get('LOW', 0)}", 'LOW')
    print_colored(f"INFO: {counts.get('INFO', 0)}", 'INFO')
    print("-" * 35)

    # --- Detailed Findings Table ---
    if not findings:
        print_colored("\n🎉 **No security findings detected in the codebase.**", 'SUCCESS')
        return

    print_colored("\n## 📋 Detailed Findings Report", 'HEADER')
    print("-" * 80)
    
    # Sort findings by severity (HIGH first)
    severity_order = {'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'INFO': 1}
    sorted_findings = sorted(findings, key=lambda x: severity_order.get(x['severity'], 0), reverse=True)

    for i, finding in enumerate(sorted_findings, 1):
        sev_key = finding['severity'].upper()
        sev_color = COLOR_MAP.get(sev_key, COLOR_MAP['NORMAL'])
        
        print(f"\n{sev_color}--- FINDING #{i} ---{Style.RESET_ALL}")
        print_colored(f"**SEVERITY:** {sev_key}", sev_key)
        print_colored(f"**CODE/ID:** {finding['code']}", 'NORMAL')
        print_colored(f"**CWE/CVE:** {finding['cwe']}", 'NORMAL')
        print_colored(f"**MESSAGE:** {finding['msg']}", 'NORMAL')
        print_colored(f"**LOCATION:** {finding['file']}:{finding['line']}", 'NORMAL')

        # Feature Mapping (3, 4, 6, 1)
        category = ""
        code = finding['code']
        if code.startswith('B6'):
            category = "Dangerous Code Execution (Feature 3)" 
        elif code.startswith('B2') or code.startswith('B5'):
            category = "Injection Risk Indicators (Feature 4)"
        elif code.startswith('B3') or code.startswith('B4'):
            category = "Insecure Cryptography Usage (Feature 6)"
        elif code.startswith('SEC'):
            category = "Exposed Secrets & Credentials (Feature 1)"
        elif code.startswith('DEP'):
            category = "Dependency Vulnerabilities (Feature 2)"

        if category:
            print_colored(f"**CATEGORY:** {category}", 'NORMAL')

        # Remediation Guidance
        print_colored(f"**REMEDIATION:** {finding['remediation']}", 'NORMAL')
        print("-" * 20)

# --- Main Execution Block ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Single-File CLI Security Analyzer for GitHub Repositories.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "url",
        help="The GitHub repository URL to analyze (e.g., https://github.com/user/repo)"
    )
    
    args = parser.parse_args()
    
    try:
        # Check for required modules before starting
        import git
        import bandit
        import safety
        import colorama
        
        analyze_repo(args.url)
        
    except ImportError as e:
        print("\n" + "="*80)
        print_colored("!!! INITIAL SETUP REQUIRED !!!", 'ERROR')
        print("The following Python libraries are missing:")
        print(f"Error details: {e}")
        print_colored("Run the following command to install them:", 'WARNING')
        print("pip install GitPython bandit safety colorama")
        print("="*80)
        sys.exit(1)
    except Exception as e:
        print_colored(f"\n[FATAL ERROR] An unexpected error occurred: {e}", 'ERROR')
        sys.exit(1)