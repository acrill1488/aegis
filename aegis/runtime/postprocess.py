def remove_think_blocks(text: str) -> str:
    """Remove think blocks from the text."""
    import re
    # Remove blocks like
    return re.sub(r'```think.*?```', '', text, flags=re.DOTALL)

def remove_model_identity_leaks(text: str) -> str:
    """Remove model identity leaks from the text."""
    import re
    # Remove mentions of specific models
    patterns = [
        r'(?i)(Qwythos|Qwen|Claude|Llama|Empero AI)',
        r'(?i)I am a language model',
        r'(?i)I am an AI assistant',
        r'(?i)I am an artificial intelligence',
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return text.strip()

def clean_model_response(text: str) -> str:
    """Clean the model response by removing think blocks and identity leaks."""
    import re
    # Remove think blocks
    text = re.sub(r'```think.*?```', '', text, flags=re.DOTALL)
    
    # Remove model identity leaks
    patterns = [
        r'(?i)(Qwythos|Qwen|Claude|Llama|Empero AI)',
        r'(?i)I am a language model',
        r'(?i)I am an AI assistant',
        r'(?i)I am an artificial intelligence',
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Trim whitespace
    return text.strip()