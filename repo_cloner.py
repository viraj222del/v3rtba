import git
import tempfile
import os

def clone_repository(repo_url: str) -> str | None:
    """Clones a Git repository into a temporary directory."""
    try:
        # Use tempfile to create a secure temporary directory
        temp_dir = tempfile.mkdtemp(prefix="gitdebt_")
        
        # Clone the repository
        git.Repo.clone_from(repo_url, temp_dir)
        
        return temp_dir
    except git.GitCommandError as e:
        print(f"❌ Git Command Error during cloning: {e}")
        # Clean up the partial directory if it was created
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred during cloning: {e}")
        return None