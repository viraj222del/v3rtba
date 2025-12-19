import argparse
import os
import shutil
import tempfile
import sys
import stat
from typing import Dict, Any

# Assume these modules are present in your directory
from repo_cloner import clone_repository
from static_analyzer import run_static_analysis
from git_history_analyzer import analyze_git_history
from dependency_analyzer import analyze_dependencies
from metrics_calculator import compute_advanced_metrics
from report_generator import find_main_contributing_factor, generate_cli_report 
from contributor_analyzer import analyze_contributor_efficiency


# Simplified onerror handler for cross-platform cleanup resilience
def onerror(func, path, exc_info):
    """Error handler for shutil.rmtree that attempts to clear permissions if needed."""
    # Check if the error is due to permission denied
    if not os.access(path, os.W_OK):
        try:
            os.chmod(path, stat.S_IWUSR)
            func(path)
        except Exception:
            # Re-raise if we can't change permissions or delete after change
            raise
    else:
        raise

def run_analysis_pipeline(repo_url: str) -> Dict[str, Any]:
    """Runs the full analysis pipeline and returns the complete data dictionary."""
    
    temp_dir = None
    all_file_data: Dict[str, Any] = {}
    original_recursion_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(2000)

    try:
        # --- 1. Clone Repository ---
        print(f"🔄 Cloning repository: {repo_url}...")
        temp_dir = clone_repository(repo_url)
        if not temp_dir:
            raise Exception("Cloning failed. Git executable or repo URL is invalid.")
        print("✅ Cloning complete.")
        
        # --- 2. Static Analysis ---
        print("🔬 Running static code analysis...")
        all_file_data = run_static_analysis(temp_dir)
        
        # --- 3. Git History Analysis ---
        print("🕰️ Analyzing Git history...")
        all_file_data = analyze_git_history(temp_dir, all_file_data)
        
        # --- 4. Dependency Analysis ---
        print("🔗 Analyzing file dependencies...")
        all_file_data = analyze_dependencies(temp_dir, all_file_data)

        # --- 5. Compute Advanced Metrics (Risk Scores, Entropy) ---
        print("📊 Computing Risk Scores and Ownership Entropy...")
        all_file_data = compute_advanced_metrics(all_file_data)
        
        # --- 6. Contributor Analysis ---
        print("👤 Analyzing contributor efficiency...")
        contributor_data = analyze_contributor_efficiency(all_file_data)
        all_file_data['_contributor_stats'] = contributor_data
        
        # --- 7. Prepare Data for Reporting ---
        # Store the temporary path for filesystem scans
        all_file_data['_local_repo_path'] = temp_dir 
        
        repo_stats = all_file_data.get('_repo_stats', {})
        max_values = repo_stats.get('max_values', {})
        
        # FIX: Added isinstance check to prevent crashing on string values (like _local_repo_path)
        for path, data in list(all_file_data.items()):
            if isinstance(data, dict) and path != '_repo_stats' and path != '_contributor_stats':
                if data.get('loc', 0) > 0:
                     data['main_factor'] = find_main_contributing_factor(data, max_values)

        return all_file_data
        
    except Exception as e:
        print(f"\n❌ An error occurred during analysis: {e}", file=sys.stderr)
        raise
        
    finally:
        sys.setrecursionlimit(original_recursion_limit)
        # --- 8. Cleanup ---
        if temp_dir and os.path.exists(temp_dir):
            print(f"\n🧹 Cleaning up temporary directory: {temp_dir}")
            try:
                # Use simplified onerror handler
                shutil.rmtree(temp_dir, onerror=onerror)
                print("✅ Cleanup complete.")
            except Exception as e:
                # Print a simpler warning if cleanup fails
                print(f"⚠️ Warning: Could not fully delete temporary directory: {temp_dir}. Error: {e}", file=sys.stderr)


def main():
    """CLI Entry point: Runs analysis and generates the CLI report."""
    parser = argparse.ArgumentParser(description="Git Debt Analyzer: Clones a Git repository and performs analysis.")
    parser.add_argument('--repo-url', required=True, help='URL of the Git repository to analyze')
    
    args = parser.parse_args()
    repo_url = args.repo_url
    
    try:
        print("-" * 50)
        print("STARTING TECHNICAL DEBT ANALYSIS")
        print("-" * 50)
        
        # Run the pipeline to get the data
        all_file_data = run_analysis_pipeline(repo_url)
        
        # Generate the CLI report using the collected data
        generate_cli_report(repo_url, all_file_data)
        
        print("-" * 50)
        print("ANALYSIS COMPLETE.")
        
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()