import git
import os
from typing import Dict, Any, List

def analyze_git_history(repo_path: str, all_file_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Analyzes Git history for churn, authorship, and bug fixes."""
    try:
        repo = git.Repo(repo_path)
    except git.InvalidGitRepositoryError:
        print("❌ Not a valid Git repository. Skipping history analysis.")
        return all_file_data

    # Define common bug keywords
    BUG_KEYWORDS = ['fix', 'bug', 'error', 'broken', 'issue', 'hotfix']

    for file_path in list(all_file_data.keys()):
        file_data = all_file_data[file_path]
        
        total_lines_added = 0
        total_lines_removed = 0
        total_commit_count = 0
        unique_authors: Dict[str, int] = {}
        bug_fix_count = 0
        
        try:
            # Iterate through commits affecting the file
            for commit in repo.iter_commits(paths=file_path, reverse=True):
                total_commit_count += 1
                
                # 1. Authorship
                author_email = commit.author.email
                unique_authors[author_email] = unique_authors.get(author_email, 0) + 1
                
                # 2. Bug Fixes
                if any(keyword in commit.message.lower() for keyword in BUG_KEYWORDS):
                    bug_fix_count += 1
                
                # 3. Churn (lines added/removed)
                if commit.parents:
                    diff_index = commit.tree.diff(commit.parents[0].tree, paths=[file_path])
                    
                    for diff in diff_index:
                        if diff.change_type in ('M', 'A', 'D'):
                            # Need to handle case where file is deleted (D) or added (A)
                            if diff.a_path == file_path and diff.b_path: # Modified
                                try:
                                    # Get diff statistics (this can be expensive)
                                    stats = repo.git.diff(commit.parents[0].hexsha, commit.hexsha, '--numstat', '--', file_path).splitlines()
                                    if stats:
                                        added, removed, _ = stats[0].split('\t')
                                        total_lines_added += int(added)
                                        total_lines_removed += int(removed)
                                except Exception:
                                    pass # Ignore diff stat errors

            # Update the file data with historical metrics
            file_data.update({
                'commit_count': total_commit_count,
                'lines_added': total_lines_added,
                'lines_removed': total_lines_removed,
                'unique_author_count': len(unique_authors),
                'bug_fix_count': bug_fix_count,
                'author_commits': unique_authors # Detailed authorship for entropy calculation
            })
            
        except git.GitCommandError as e:
            # This can happen if a file was moved or deleted in the history
            print(f"⚠️ Git history error for {file_path}: {e}")
            # Ensure basic data is still present if analysis failed
            file_data.update({
                'commit_count': 0, 'lines_added': 0, 'lines_removed': 0, 
                'unique_author_count': 0, 'bug_fix_count': 0, 'author_commits': {}
            })
            
    return all_file_data