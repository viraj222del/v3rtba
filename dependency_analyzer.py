import os
import re
from typing import Dict, Any, Tuple

# Common import/include patterns for various languages
DEPENDENCY_PATTERNS = {
    '.py': r'(?:from|import)\s+([\w\.]+)',
    '.js': r'(?:require|import)\s+[\'"]?([.\/a-zA-Z0-9_-]+)[\'"]?',
    '.ts': r'(?:import|export)\s+[\'"]?([.\/a-zA-Z0-9_-]+)[\'"]?',
    '.java': r'import\s+([\w\.]+);',
    '.c': r'#include\s+["<]([\w\/\.]+)[">]',
    '.cpp': r'#include\s+["<]([\w\/\.]+)[">]',
    '.html': r'(?:<script\s+src|href)\s*=\s*["\']([^"\']+)["\']', # Basic HTML resource detection
}

def analyze_dependencies(repo_path: str, all_file_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Analyzes dependencies (Fan-in/Fan-out) between files."""
    
    # Initialize dependency graph
    fan_out_map: Dict[str, List[str]] = {path: [] for path in all_file_data.keys()}
    
    # 1. Determine Fan-out (dependencies a file uses)
    for path, data in all_file_data.items():
        file_extension = os.path.splitext(path)[1]
        pattern = DEPENDENCY_PATTERNS.get(file_extension)
        
        if not pattern:
            continue

        file_path_abs = os.path.join(repo_path, path)
        try:
            with open(file_path_abs, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            continue
            
        found_dependencies = set(re.findall(pattern, content))

        for dep in found_dependencies:
            # Simple heuristic: look for paths that match
            for target_path in all_file_data.keys():
                if dep in target_path or os.path.basename(dep) in target_path:
                    if target_path != path: # Don't count self-dependency
                        fan_out_map[path].append(target_path)
                        break
        
        # Store Fan-out count
        data['fan_out'] = len(set(fan_out_map[path]))

    # 2. Determine Fan-in (dependencies that use the file)
    fan_in_map: Dict[str, int] = {path: 0 for path in all_file_data.keys()}
    for dependents, targets in fan_out_map.items():
        for target in set(targets):
            fan_in_map[target] = fan_in_map.get(target, 0) + 1
            
    # Update data with Fan-in counts
    for path, data in all_file_data.items():
        data['fan_in'] = fan_in_map.get(path, 0)
        
    return all_file_data