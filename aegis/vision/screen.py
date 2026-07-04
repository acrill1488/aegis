import os
import time
from datetime import datetime
from typing import Optional

from mss import mss
from PIL import Image


def capture_screen(output_dir: Optional[str] = None) -> str:
    """
    Capture screenshot of the main monitor and save it to file.
    
    Args:
        output_dir: Directory to save screenshot. If None, uses F:\\AI_WORKSPACE\\screenshots
        
    Returns:
        Path to the saved screenshot file
    """
    # Use default directory if none provided
    if output_dir is None:
        output_dir = "F:\\AI_WORKSPACE\\screenshots"
    
    # Create directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    filepath = os.path.join(output_dir, filename)
    
    # Capture screenshot
    with mss() as sct:
        # Capture the main monitor (usually monitor 0)
        sct.shot(output=filepath)
    
    return filepath


def capture_screen_simple():
    """
    Simple function to capture screen without parameters.
    This is for backward compatibility or simple usage.
    """
    return capture_screen()


if __name__ == "__main__":
    # Test the function
    try:
        path = capture_screen()
        print(f"Screenshot saved to: {path}")
    except Exception as e:
        print(f"Error capturing screenshot: {e}")