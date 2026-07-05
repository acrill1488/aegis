import re


def clean_identity(text: str) -> str:
    """Clean identity leaks from the text."""
    # Remove lines that contain model names (not just start with them)
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line_content = line.strip()
        # Check if the line contains any of the model names
        contains_model = False
        for model in ["Qwythos", "Qwen", "Claude", "Llama", "Empero AI", "OpenAI", "Anthropic"]:
            if model in line_content:
                contains_model = True
                break
        
        # Only keep lines that don't contain model names
        if not contains_model and line_content:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines).strip()