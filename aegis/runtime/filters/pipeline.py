from .reasoning import clean_reasoning
from .identity import clean_identity
import re


def _clean_tool_artifacts(text: str) -> str:
    final_match = re.search(r"<final>\s*(.*?)\s*</final>", text, flags=re.DOTALL | re.IGNORECASE)
    if final_match:
        text = final_match.group(1)
    text = re.sub(
        r"<tool_code>\s*.*?\s*</tool_code>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"<tool>\s*.*?\s*</tool>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</?response>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?final>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```json\s*.*?\s*```", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</think>", "", text, flags=re.IGNORECASE)
    return text


def _remove_tool_lines(text: str) -> str:
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        if '"tool":' in line or '"arguments":' in line:
            continue
        if "'name':" in line or "'arguments':" in line:
            continue
        if stripped == 'tool' or stripped == 'arguments':
            continue
        filtered_lines.append(line)
    return '\n'.join(filtered_lines)

def clean_response(text: str) -> str:
    """
    Clean response text by applying all cleaning filters.
    
    Args:
        text (str): Input text to clean
        
    Returns:
        str: Cleaned text
    """
    # Apply all cleaning functions in sequence
    original_text = text  # Keep reference to original for fallback
    text = clean_reasoning(text)
    text = clean_identity(text)

    text = _clean_tool_artifacts(text)
    
    # Remove lines containing tool calls
    text = _remove_tool_lines(text)
    
    # Handle content after last
    # Remove extra empty lines
    lines = text.split('\n')
    cleaned_lines = []
    prev_empty = False
    
    for line in lines:
        is_empty = not line.strip()
        if not (prev_empty and is_empty):
            cleaned_lines.append(line)
        prev_empty = is_empty
    
    text = '\n'.join(cleaned_lines).strip()
    
    # If result is empty, return the original text stripped of tags but not completely empty
    if not text:
        # Try to get a clean version without tags first
        clean_text = clean_reasoning(original_text)
        clean_text = clean_identity(clean_text)
        clean_text = _clean_tool_artifacts(clean_text)
        clean_text = _remove_tool_lines(clean_text)
        clean_text = clean_text.strip()
        
        # If still empty, do not restore stripped tool calls.
        if not clean_text:
            return ""
        else:
            return clean_text
    
    return text
