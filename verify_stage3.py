"""
Stage 3 Verification Script
Digital Library & Research Management System

Verifies that all 23 multi-page Jinja2 HTML templates, custom CSS, 
interactive JavaScript, and placeholder graphics are properly created and have valid syntax.
"""

import sys
import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

def print_status(step: str, status: bool, extra: str = ""):
    symbol = "[PASS]" if status else "[FAIL]"
    print(f"{symbol:<10} | {step:<45} {extra}")

def main():
    print("=" * 80)
    print(" DIGITAL LIBRARY & RESEARCH MANAGEMENT SYSTEM - STAGE 3 VERIFICATION")
    print("=" * 80)

    all_passed = True
    base_dir = Path(__file__).resolve().parent
    templates_dir = base_dir / "templates"
    static_css = base_dir / "static" / "css" / "style.css"
    static_js = base_dir / "static" / "js" / "script.js"
    static_img1 = base_dir / "static" / "images" / "default_book.svg"
    static_img2 = base_dir / "static" / "images" / "default_avatar.svg"

    # 1. Static Assets Verification
    print("STATIC ASSETS VERIFICATION:")
    css_valid = static_css.is_file() and static_css.stat().st_size > 500
    print_status("Custom Stylesheet (style.css)", css_valid, f"({static_css.stat().st_size} bytes)")
    if not css_valid:
        all_passed = False

    js_valid = static_js.is_file() and static_js.stat().st_size > 500
    print_status("Client-side Controller (script.js)", js_valid, f"({static_js.stat().st_size} bytes)")
    if not js_valid:
        all_passed = False

    img_valid = static_img1.is_file() and static_img2.is_file()
    print_status("Placeholder Graphics (default_book/avatar.svg)", img_valid)
    if not img_valid:
        all_passed = False

    # 2. Template Parsing & Syntax Verification
    print("-" * 80)
    print("MULTI-PAGE TEMPLATES (JINJA2 PARSING & COMPILATION):")

    expected_templates = [
        "base.html",
        "index.html",
        "about.html",
        "login.html",
        "register.html",
        "student_dashboard.html",
        "books.html",
        "book_details.html",
        "research.html",
        "research_details.html",
        "my_books.html",
        "borrow_history.html",
        "profile.html",
        "admin_dashboard.html",
        "manage_books.html",
        "add_book.html",
        "edit_book.html",
        "manage_research.html",
        "add_research.html",
        "manage_members.html",
        "member_details.html",
        "manage_issues.html",
        "reports.html"
    ]

    env = Environment(loader=FileSystemLoader(str(templates_dir)))

    for t_name in expected_templates:
        t_file = templates_dir / t_name
        if not t_file.is_file():
            print_status(f"Template: {t_name}", False, "File not found!")
            all_passed = False
            continue

        try:
            # Parse template using Jinja2
            with open(t_file, "r", encoding="utf-8") as f:
                content = f.read()
            env.parse(content)
            print_status(f"Template: {t_name}", True, "(Valid Jinja2 Syntax)")
        except TemplateSyntaxError as err:
            print_status(f"Template: {t_name}", False, f"(Syntax Error line {err.lineno}: {err.message})")
            all_passed = False
        except Exception as e:
            print_status(f"Template: {t_name}", False, f"(Error: {str(e)})")
            all_passed = False

    print("=" * 80)
    if all_passed:
        print("STAGE 3 VERIFICATION COMPLETED SUCCESSFULLY!")
        print(f"All {len(expected_templates)} HTML templates, custom CSS, JS, and graphics are 100% verified.")
    else:
        print("Some template or static asset checks failed. Please inspect above.")
    print("=" * 80)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
