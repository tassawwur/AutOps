#!/usr/bin/env python3
"""
Verification script for code formatting and line endings.
This script ensures that all code meets formatting standards.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def check_black_formatting():
    """Check if all Python files are properly formatted with Black."""
    print("🔍 Checking Black formatting...")
    
    exit_code, stdout, stderr = run_command(["black", "--check", "src", "tests"])
    
    if exit_code == 0:
        print("✅ All files are properly formatted with Black!")
        return True
    else:
        print("❌ Black formatting issues found:")
        print(stdout)
        print(stderr)
        return False


def check_line_endings():
    """Check for consistent line endings."""
    print("🔍 Checking line endings...")
    
    # Check for CRLF line endings in Python files
    exit_code, stdout, stderr = run_command([
        "grep", "-r", "-l", "\\r", "src/", "tests/"
    ])
    
    if exit_code != 0:  # grep returns non-zero when no matches found
        print("✅ All files have consistent Unix line endings!")
        return True
    else:
        print("❌ Files with CRLF line endings found:")
        print(stdout)
        return False


def check_gitattributes():
    """Verify .gitattributes file exists."""
    print("🔍 Checking .gitattributes configuration...")
    
    gitattributes_path = Path(".gitattributes")
    if gitattributes_path.exists():
        print("✅ .gitattributes file found!")
        return True
    else:
        print("❌ .gitattributes file missing!")
        return False


def main():
    """Run all verification checks."""
    print("🚀 Starting formatting verification...\n")
    
    checks = [
        check_gitattributes,
        check_line_endings,
        check_black_formatting,
    ]
    
    all_passed = True
    
    for check in checks:
        if not check():
            all_passed = False
        print()
    
    if all_passed:
        print("🎉 All formatting checks passed! Your code is CI-ready.")
        sys.exit(0)
    else:
        print("💥 Some checks failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main() 