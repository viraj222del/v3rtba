from typing import Dict, Any, Tuple, List
from collections import defaultdict # <--- Crucial for avoiding NameError

def analyze_contributor_efficiency(all_file_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Calculates efficiency and risk contribution scores for each unique author."""
    
    # Use 10 as a strong penalty multiplier for bug fixes, making them expensive.
    BUG_PENALTY_FACTOR = 10
    
    # 1. Aggregate metrics per author
    author_summary: Dict[str, Dict[str, float]] = defaultdict(lambda: {
        'total_commits': 0.0, 
        'lines_added': 0.0, 
        'lines_removed': 0.0, 
        'bug_fix_count': 0.0,
        'risk_contribution_sum': 0.0,
        'total_author_contrib_percentage': 0.0
    })

    # We iterate over a copy of the keys to safely skip the _repo_stats key
    for path, data in list(all_file_data.items()): 
        if path == '_repo_stats' or data.get('loc', 0) == 0 or 'risk_score' not in data:
            continue
            
        file_risk_score = data.get('risk_score', 0.0)
        file_total_commits = data.get('commit_count', 0) 
        
        if file_total_commits == 0:
            continue

        # Iterate over authors who contributed to this file
        for author_email, commits_in_file in data.get('author_commits', {}).items():
            
            author_commits_percentage = commits_in_file / file_total_commits
            
            author_summary[author_email]['total_commits'] += commits_in_file
            
            # Attribute proportional file metrics to the author
            author_summary[author_email]['lines_added'] += data.get('lines_added', 0) * author_commits_percentage
            author_summary[author_email]['lines_removed'] += data.get('lines_removed', 0) * author_commits_percentage
            author_summary[author_email]['bug_fix_count'] += data.get('bug_fix_count', 0) * author_commits_percentage
            
            # Risk Contribution: Author's share of the file's risk
            author_summary[author_email]['risk_contribution_sum'] += file_risk_score * author_commits_percentage
            author_summary[author_email]['total_author_contrib_percentage'] += author_commits_percentage

    # 2. Calculate final scores
    for email, summary in author_summary.items():
        
        # Denominator for Efficiency Score: Penalty for activity/bugs
        efficiency_denominator = (
            summary['total_commits'] + 
            summary['lines_removed'] + 
            (summary['bug_fix_count'] * BUG_PENALTY_FACTOR)
        )
        
        # Efficiency Score calculation (Lines Added / Penalty Cost)
        if efficiency_denominator > 0:
            efficiency = summary['lines_added'] / efficiency_denominator
        else:
            efficiency = 0.0 
        
        # Risk Contribution Score: Average risk score contributed by this author
        if summary['total_author_contrib_percentage'] > 0:
            # Average weighted risk score
            risk_score = summary['risk_contribution_sum'] / summary['total_author_contrib_percentage']
        else:
            risk_score = 0.0

        author_summary[email]['efficiency_score'] = efficiency
        author_summary[email]['risk_score'] = risk_score
        
    return dict(author_summary)