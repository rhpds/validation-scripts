from typing import Dict, Any, List
import os
import re

def parse_module_directory_structure(root_path: str) -> Dict[str, Any]:
    """
    Parse module directory structure into a custom format:
    
    module:
      stage:
        - path: script-name.sh
          hostname: hostname
    """
    structure = {}
    
    # Regular expression to extract info from filenames
    # Matches patterns like: setup-host1.sh, validation-openssh-server.sh
    pattern = re.compile(r"^(setup|solve|validation)-([^.]+)\.sh$")
    
    # Get all directories in the root path (excluding hidden directories)
    for item in os.listdir(root_path):
        item_path = os.path.join(root_path, item)
        
        # Skip hidden directories and non-directories
        if item.startswith('_') or item.startswith('.') or not os.path.isdir(item_path):
            continue
        
        # Initialize module entry
        module_name = item
        structure[module_name] = {}
        
        # Process files in the module directory
        for filename in os.listdir(item_path):
            file_path = os.path.join(item_path, filename)
            
            # Skip directories and non-sh files
            if os.path.isdir(file_path) or not filename.endswith('.sh'):
                continue
            
            # Try to match the filename pattern
            match = pattern.match(filename)
            if match:
                stage, hostname = match.groups()
                
                # Initialize stage if not exists
                if stage not in structure[module_name]:
                    structure[module_name][stage] = []
                
                # Add file info to the stage
                structure[module_name][stage].append({
                    "path": filename,
                    "hostname": hostname
                })
    
    return structure

def get_module_config_from_directory_structure(full_structure: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Convert the directory structure to a simplified format showing only modules and their stages:
    
    module:
      - setup
      - solve
      - validation
    """
    simplified = {}
    
    for module, stages in full_structure.items():
        simplified[module] = list(stages.keys())
    
    return simplified