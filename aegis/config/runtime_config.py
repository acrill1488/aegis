import yaml
from aegis.config.services import get_service_base_url
from pathlib import Path
from typing import Dict, Any

def get_runtime_profile(name: str | None = None) -> Dict[str, Any]:
    """
    Get runtime profile configuration from YAML file.
    
    Args:
        name: Profile name to retrieve. If None, uses default_profile.
        
    Returns:
        Dictionary containing profile configuration.
    """
    config_path = Path("config/runtime.yaml")
    
    if not config_path.exists():
        raise FileNotFoundError(f"Runtime configuration file not found at {config_path}")
    
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    
    if name is None:
        name = config.get('default_profile', 'coding')
    
    profile = config.get('profiles', {}).get(name)
    
    if not profile:
        raise ValueError(f"Profile '{name}' not found in configuration")
    
    # Add max_tokens to profile if it doesn't exist
    if 'max_tokens' not in profile:
        profile['max_tokens'] = 4096
    if not profile.get('base_url'):
        profile['base_url'] = get_service_base_url('ollama')
    
    return profile
