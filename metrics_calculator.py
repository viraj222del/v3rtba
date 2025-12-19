from typing import Dict, Any
import math
import statistics
import datetime
from operator import itemgetter

def assign_test_coverage_status(path: str) -> float:
    """
    Simulates checking for test coverage based on file name patterns.
    
    Returns a 'Missing Test Coverage' factor:
    0.1: Likely Covered (Good)
    0.5: Ambiguous/Needs Check
    1.0: Likely Uncovered (Bad - High Risk)
    """
    
    # Files often covered by tests (low penalty)
    if "test" in path.lower() or path.endswith("_spec.rb") or path.endswith("_test.py"):
        return 0.1 

    # Common critical file types that should ALWAYS be tested (high penalty)
    if any(keyword in path.lower() for keyword in ["model", "interface", "util", "core", "api", "database"]):
        return 1.0 
        
    # Standard source files (moderate penalty)
    return 0.5 

def compute_advanced_metrics(all_file_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Calculates technical debt risk scores, ownership entropy, and the new Systemic Risk Score.
    """
    
    repo_stats = all_file_data.get('_repo_stats', {})
    
    # --- 1. First Pass: Calculate and Normalize Max Values ---
    
    # Identify files to process (exclude stats entries)
    file_entries = {path: data for path, data in all_file_data.items() if not path.startswith('_') and data.get('loc', 0) > 0}
    
    max_values = {
        'complexity': max([d.get('complexity', 0) for d in file_entries.values()] or [1]),
        'total_churn': max([d.get('lines_added', 0) + d.get('lines_removed', 0) for d in file_entries.values()] or [1]),
        'ownership_entropy': 1.0, # Max is always 1
        'bug_fix_freq': max([d.get('bug_fix_count', 0) / (d.get('commit_count', 1) or 1) for d in file_entries.values()] or [0.1]),
        'dependency_score': max([(d.get('fan_in', 0) * 2 + d.get('fan_out', 0) * 1) for d in file_entries.values()] or [1]),
        'systemic_risk_score': 0.0 # Will be updated in the second pass
    }

    def normalize_metric(value: float, max_value: float, min_value: float = 0.0) -> float:
        if max_value == min_value or max_value == 0:
            return 0.0
        value = max(min_value, value)
        return min(1.0, (value - min_value) / (max_value - min_value))

    # --- 2. Second Pass: Calculate Risk and Systemic Scores ---
    
    weighted_scores = []
    
    for path, data in file_entries.items():
        
        # --- A. Technical Debt Risk Score (0-100) ---
        
        WEIGHTS = {'complexity': 0.30, 'churn': 0.20, 'ownership_entropy': 0.15, 'bug_fix_frequency': 0.25, 'dependency_score': 0.10}
        
        # Normalize the metrics
        norm_complexity = normalize_metric(data.get('complexity', 0), max_values['complexity'])
        norm_churn = normalize_metric(data.get('lines_added', 0) + data.get('lines_removed', 0), max_values['total_churn'])
        norm_entropy = normalize_metric(data.get('ownership_entropy', 0.0), max_values['ownership_entropy'])
        
        total_commits = data.get('commit_count', 0)
        bug_fix_freq = data.get('bug_fix_count', 0) / (total_commits or 1)
        norm_bug_freq = normalize_metric(bug_fix_freq, max_values['bug_fix_freq'])
        
        dependency_score = data.get('fan_in', 0) * 2 + data.get('fan_out', 0) * 1
        norm_dependency = normalize_metric(dependency_score, max_values['dependency_score'])

        # Calculate weighted sum
        risk_score = (
            norm_complexity * WEIGHTS['complexity'] +
            norm_churn * WEIGHTS['churn'] +
            norm_entropy * WEIGHTS['ownership_entropy'] +
            norm_bug_freq * WEIGHTS['bug_fix_frequency'] +
            norm_dependency * WEIGHTS['dependency_score']
        ) * 100
        
        data['risk_score'] = risk_score
        
        # --- B. Systemic Risk Score ---
        
        # 1. Get Missing Test Coverage Factor
        missing_test_coverage_factor = assign_test_coverage_status(path)
        data['missing_test_coverage_factor'] = missing_test_coverage_factor

        # 2. Calculate Systemic Risk Score
        # Formula: Fan-In × Risk Score × Missing Test Coverage Factor
        fan_in = data.get('fan_in', 0)
        
        systemic_risk_score = fan_in * risk_score * missing_test_coverage_factor
        data['systemic_risk_score'] = systemic_risk_score
        
        max_values['systemic_risk_score'] = max(max_values['systemic_risk_score'], systemic_risk_score)
        
        # Update the entry
        all_file_data[path] = data
        weighted_scores.append(risk_score)

    # --- 3. Final Repository Stats Update ---
    
    repo_stats['max_values'] = max_values
    repo_stats['overall_technical_debt'] = statistics.mean(weighted_scores) if weighted_scores else 0
    all_file_data['_repo_stats'] = repo_stats
    
    return all_file_data

# Ensure other required functions (e.g., those used by git_debt_analyzer.py) are present
# For example, if you moved find_main_contributing_factor here, it should be included.
# Assuming find_main_contributing_factor remains in report_generator.py for now.