import re


def clean_reasoning(text: str) -> str:
    """Clean reasoning blocks and phrases from the text."""
    # Remove blocks enclosed in ```think``` tags
    # First, find all occurrences of ```think ... ``` patterns
    pattern = r'```think.*?```'
    matches = list(re.finditer(pattern, text, re.DOTALL))
    
    # Process from end to start to maintain correct indices
    result = text
    for match in reversed(matches):
        start, end = match.span()
        result = result[:start] + result[end:]
    
    # Handle case where there's only a closing tag ```think without opening tag
    # Find all closing tags that don't have corresponding opening tags
    closing_tags = list(re.finditer(r'```think', result))
    for match in reversed(closing_tags):
        start, end = match.span()
        # Remove everything from this point to the end of the string
        result = result[:start]
    
    # Remove lines that start with or contain specific reasoning phrases
    lines = result.split('\n')
    cleaned_lines = []
    for line in lines:
        line_content = line.strip()
        # Skip lines starting with the specified patterns
        if line_content.startswith(("The user", "I need to", "I should", "I will", "I must", "However,", "Therefore,", "Now, I will", "Let's", "We need")):
            continue
        # Also check if the line contains any of these phrases
        contains_phrase = False
        for phrase in ["The user", "I need to", "I should", "I will", "I must", "However,", "Therefore,", "Now, I will", "Let's", "We need"]:
            if phrase in line_content:
                contains_phrase = True
                break
        if not contains_phrase and line_content:  # Only add non-empty lines that don't contain the phrases
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines).strip()