import re


def clean_reasoning(text: str) -> str:
    """Clean reasoning blocks and phrases from the text."""
    lines = text.splitlines()
    cleaned_lines = []
    in_initial_reasoning = False
    
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        
        # Check if this is an initial reasoning line (at the beginning of text)
        if not in_initial_reasoning and i == 0:
            if stripped_line.startswith(("First, I'll", "First, I will", "I will", 
                                       "I need to", "I should", "The user asks",
                                       "The user wants", "Let's", "Now, craft",
                                       "Now I will", "Finally", "Review:",
                                       "Based on the page", "To answer this",
                                       "I'll summarize", "I will identify",
                                       "I will analyze", "Thus,")):
                in_initial_reasoning = True
                continue  # Skip this line
            else:
                # This is not a reasoning starter, so add it to output
                cleaned_lines.append(line)
        elif in_initial_reasoning:
            # Check if we've reached the end of the initial reasoning block
            # We consider a block ended when we find the first normal Russian sentence
            if stripped_line != "":
                # This is a non-empty line, check if it looks like a proper response
                # (has capital letter at start and reasonable length)
                if stripped_line[0].isupper() and len(stripped_line) > 10:
                    # This seems to be the start of the actual response
                    in_initial_reasoning = False
                    cleaned_lines.append(line)
                else:
                    # Still in initial reasoning block - skip this line
                    continue
            else:
                # Empty line within reasoning block - skip it
                continue
        elif stripped_line == "**Суммарный ответ:**":
            # Found the summary marker, remove everything before it including the marker itself
            cleaned_lines = []
        elif stripped_line.startswith("Итог:") or stripped_line.startswith("Ответ:"):
            # Found summary marker, remove everything before it including the marker itself
            cleaned_lines = []
        else:
            cleaned_lines.append(line)
    
    result_text = "\n".join(cleaned_lines)
    
    # Handle special markers that should remove everything before them
    if "**Суммарный ответ:**" in result_text:
        parts = result_text.split("**Суммарный ответ:**", 1)
        if len(parts) > 1:
            return parts[1].strip()
    elif "Итог:" in result_text:
        parts = result_text.split("Итог:", 1)
        if len(parts) > 1:
            return parts[1].strip()
    elif "Ответ:" in result_text:
        parts = result_text.split("Ответ:", 1)
        if len(parts) > 1:
            return parts[1].strip()
    
    # Remove any remaining empty lines at the beginning
    while result_text.startswith("\n"):
        result_text = result_text[1:]
        
    return result_text