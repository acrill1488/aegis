from .reasoning import clean_reasoning
from .identity import clean_identity

def clean_response(text: str) -> str:
    """
    Clean response text by applying all cleaning filters.
    
    Args:
        text (str): Input text to clean
        
    Returns:
        str: Cleaned text
    """
    # Apply all cleaning functions in sequence
    text = clean_reasoning(text)
    text = clean_identity(text)
    text = text.strip()  # Remove leading/trailing whitespace
    
    return text