#!/usr/bin/env python3
"""Test script for PowerShell safe execution."""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aegis.tools.powershell import PowerShellTool
from aegis.executor.executor import ExecutionEngine

def test_powershell_tool():
    """Test the PowerShell tool's safe_run method."""
    print("Testing PowerShellTool.safe_run method...")
    
    tool = PowerShellTool()
    
    # Test allowed commands
    print("\n1. Testing allowed commands:")
    
    allowed_commands = [
        "python --version",
        "git status",
        "dir",
        "pytest",
        "ruff check"
    ]
    
    for cmd in allowed_commands:
        result = tool.execute("run", command=cmd)
        print(f"   Command: {cmd}")
        print(f"   Return code: {result.exit_code}")
        print(f"   Stdout: {result.stdout}")
        print(f"   Stderr: {result.stderr}")
        print()
    
    # Test forbidden commands
    print("\n2. Testing forbidden commands:")
    
    forbidden_commands = [
        "rm -rf /",
        "del C:\\Windows\\System32\\*",
        "Remove-Item -Recurse -Force C:\\temp",
        "shutdown /s /t 0",
        "format C:",
        "erase file.txt"
    ]
    
    for cmd in forbidden_commands:
        result = tool.safe_run(cmd)
        print(f"   Command: {cmd}")
        print(f"   Return code: {result['returncode']}")
        print(f"   Stdout: {result['stdout']}")
        print(f"   Stderr: {result['stderr']}")
        print()
    
    # Test non-allowed commands
    print("\n3. Testing non-allowed commands:")
    
    not_allowed_commands = [
        "echo hello",
        "ls -la",
        "npm install"
    ]
    
    for cmd in not_allowed_commands:
        result = tool.safe_run(cmd)
        print(f"   Command: {cmd}")
        print(f"   Return code: {result['returncode']}")
        print(f"   Stdout: {result['stdout']}")
        print(f"   Stderr: {result['stderr']}")
        print()

def test_execution_engine():
    """Test the ExecutionEngine with PowerShell steps."""
    print("Testing ExecutionEngine...")
    
    engine = ExecutionEngine()
    
    # Test dry-run mode
    print("\n1. Testing dry-run mode:")
    try:
        engine.execute_task("test-powershell-task-002", dry_run=True)
        print("   Dry-run completed successfully")
    except Exception as e:
        print(f"   Error in dry-run: {e}")
    
    # Test real execution mode
    print("\n2. Testing real execution mode:")
    try:
        engine.execute_task("test-powershell-task-002", dry_run=False)
        print("   Real execution completed successfully")
    except Exception as e:
        print(f"   Error in real execution: {e}")

if __name__ == "__main__":
    test_powershell_tool()
    test_execution_engine()
    print("\nTest completed.")