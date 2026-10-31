"""
Stage 1 Verification Script
Digital Library & Research Management System

Verifies that the project directory structure, dependencies, and core files are properly configured.
"""

import sys
import os
from importlib import metadata
from pathlib import Path

# Ensure UTF-8 output even on legacy Windows code pages
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

def print_status(step: str, status: bool, extra: str = ""):
    symbol = "[PASS]" if status else "[FAIL]"
    print(f"{symbol:<10} | {step:<40} {extra}")

def main():
    print("=" * 70)
    print(" DIGITAL LIBRARY & RESEARCH MANAGEMENT SYSTEM - STAGE 1 VERIFICATION")
    print("=" * 70)

    all_passed = True

    # 1. Check Python version
    py_version = sys.version.split()[0]
    py_pass = sys.version_info >= (3, 8)
    print_status("Python Environment (>= 3.8)", py_pass, f"(Detected: v{py_version})")
    if not py_pass:
        all_passed = False

    # 2. Check required dependencies
    try:
        import flask
        try:
            flask_ver = metadata.version("flask")
        except Exception:
            flask_ver = "installed"
        print_status("Flask Installation", True, f"(Detected: v{flask_ver})")
    except ImportError:
        print_status("Flask Installation", False, "(Run: pip install -r requirements.txt)")
        all_passed = False

    try:
        import werkzeug
        try:
            werkzeug_ver = metadata.version("werkzeug")
        except Exception:
            werkzeug_ver = "installed"
        print_status("Werkzeug Installation", True, f"(Detected: v{werkzeug_ver})")
    except ImportError:
        print_status("Werkzeug Installation", False, "(Missing Werkzeug)")
        all_passed = False

    try:
        import sqlite3
        sqlite_ver = sqlite3.sqlite_version
        print_status("SQLite3 Built-in Library", True, f"(SQLite engine: v{sqlite_ver})")
    except ImportError:
        print_status("SQLite3 Built-in Library", False, "(Missing sqlite3)")
        all_passed = False

    print("-" * 70)
    print("DIRECTORY STRUCTURE VERIFICATION:")

    base_dir = Path(__file__).resolve().parent

    required_dirs = [
        "routes",
        "templates",
        "static/css",
        "static/js",
        "static/images",
        "uploads/book_covers",
        "uploads/research_papers",
        "tests",
    ]

    for rel_dir in required_dirs:
        dir_path = base_dir / rel_dir
        exists = dir_path.is_dir()
        print_status(f"Directory: {rel_dir}/", exists)
        if not exists:
            all_passed = False

    print("-" * 70)
    print("CORE FILES VERIFICATION:")

    required_files = [
        "requirements.txt",
        ".gitignore",
        "README.md",
        "routes/__init__.py",
        "tests/__init__.py",
    ]

    for rel_file in required_files:
        file_path = base_dir / rel_file
        exists = file_path.is_file()
        print_status(f"File: {rel_file}", exists)
        if not exists:
            all_passed = False

    print("=" * 70)
    if all_passed:
        print("STAGE 1 VERIFICATION COMPLETED SUCCESSFULLY!")
        print("Your environment and project architecture are fully ready for Stage 2.")
    else:
        print("Some items are missing or failed verification. Please review above.")
    print("=" * 70)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
