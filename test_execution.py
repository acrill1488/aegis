#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aegis.core.core import AegisCore

def test_execution():
    """Test the execution engine with PowerShell task"""
    
    # Create core instance
    core = AegisCore()
    
    print("Testing execution engine with PowerShell task...")
    
    # Execute task without dry-run (this should execute PowerShell commands)
    try:
        core.executor.execute_task("test-powershell-task-002", dry_run=False)
        print("Task executed successfully!")
    except Exception as e:
        print(f"Error executing task: {e}")

if __name__ == "__main__":
    test_execution()