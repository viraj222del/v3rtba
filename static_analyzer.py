import os
import re
import ast
from typing import Dict, Any, List

# List of file extensions to analyze for complexity and LOC
ANALYZE_EXTENSIONS = ('.py', '.js', '.ts', '.java', '.c', '.cpp', '.html', '.css')

COMMENT_PATTERNS = {
    '.py': re.compile(r'^\s*#'),
    '.js': re.compile(r'^\s*//'),
    '.ts': re.compile(r'^\s*//'),
    '.java': re.compile(r'^\s*//'),
    '.c': re.compile(r'^\s*//'),
    '.cpp': re.compile(r'^\s*//'),
    '.h': re.compile(r'^\s*//'),
    # Note: Block comments handled line-by-line below for better accuracy
}

def calculate_cyclomatic_complexity(node: ast.AST) -> int:
    """Calculates Cyclomatic Complexity for a single AST node."""
    if isinstance(node, (ast.If, ast.While, ast.For, ast.With, ast.ExceptHandler)):
        return 1
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return 1
    elif isinstance(node, ast.BoolOp):
        # Count the number of terms connected by "and" or "or"
        return len(node.values) - 1
    return 0

def get_cyclomatic_complexity(code: str) -> int:
    """Calculates Cyclomatic Complexity for the entire code string."""
    try:
        # The base complexity starts at 1 (for the function/module itself)
        cc = 1
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            cc += calculate_cyclomatic_complexity(node)
        
        return cc
    except SyntaxError:
        # Handle cases where the code is not valid Python syntax (e.g., HTML, JS)
        # We return 1 as a baseline or a simple count based on keywords
        return 1 + code.count('<div') + code.count('<section') # A basic guess for HTML/Markup structure
    except Exception:
        return 1

def analyze_file(file_path: str) -> Dict[str, Any]:
    """Performs static analysis (LOC, CC) on a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()
    except Exception:
        return {'loc': 0, 'complexity': 1} # Cannot read file

    loc = len(code.splitlines())
    complexity = 1
    
    if file_path.endswith('.py'):
        complexity = get_cyclomatic_complexity(code)
    else:
        # Use a simple line-based or keyword-based complexity for non-Python files
        # Example: count functions/classes/large blocks in other languages
        complexity = 1 + code.count('function ') + code.count('class ') + code.count('if (')
        
    return {
        'loc': loc,
        'complexity': complexity
    }

def run_static_analysis(repo_path: str) -> Dict[str, Dict[str, Any]]:
    """Analyzes all relevant files in the repository."""
    all_file_data: Dict[str, Dict[str, Any]] = {}
    
    for root, _, files in os.walk(repo_path):
        # Skip the temporary .git directory
        if '.git' in root:
            continue
            
        for file_name in files:
            if file_name.endswith(ANALYZE_EXTENSIONS):
                file_path = os.path.join(root, file_name)
                # Get path relative to the repository root
                relative_path = os.path.relpath(file_path, repo_path)
                
                # Run the static analysis
                analysis_results = analyze_file(file_path)
                
                # Only store files with meaningful content
                if analysis_results['loc'] > 0:
                    all_file_data[relative_path] = analysis_results
                    
    return all_file_data