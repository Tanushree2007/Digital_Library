"""
Stage 4 Verification Script
Digital Library & Research Management System

Verifies Flask backend, session authentication, role-based access control,
modular Blueprints, and all REST API endpoints using Flask test client.
"""

import sys
import os
import json
from pathlib import Path

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
    print(" DIGITAL LIBRARY & RESEARCH MANAGEMENT SYSTEM - STAGE 4 VERIFICATION")
    print("=" * 80)

    all_passed = True

    try:
        from app import app
    except Exception as e:
        print(f"Failed to import Flask application from app.py: {e}")
        return 1

    app.config['TESTING'] = True
    client = app.test_client()

    # 1. Public Pages Routing Test
    print("PUBLIC WEB PAGES ROUTING:")
    public_urls = [
        ('/', 'Home Landing Page (/)'),
        ('/about', 'About Page (/about)'),
        ('/books', 'Books Catalog (/books)'),
        ('/research', 'Research Papers (/research)'),
        ('/login', 'Login Portal (/login)'),
        ('/register', 'Registration Portal (/register)')
    ]
    for url, desc in public_urls:
        resp = client.get(url)
        passed = (resp.status_code == 200)
        print_status(desc, passed, f"(Status: {resp.status_code})")
        if not passed:
            all_passed = False

    # 2. Authentication REST APIs
    print("-" * 80)
    print("AUTHENTICATION & SECURITY APIS:")

    # Invalid login test
    bad_login = client.post('/api/login', json={"email": "admin@library.edu", "password": "WrongPassword"})
    bad_pass = (bad_login.status_code == 401)
    print_status("Invalid Password Rejection (401)", bad_pass)
    if not bad_pass:
        all_passed = False

    # Admin Login test
    admin_login = client.post('/api/login', json={"email": "admin@library.edu", "password": "Admin@12345"})
    admin_pass = (admin_login.status_code == 200)
    print_status("Admin Login API (POST /api/login)", admin_pass)
    if not admin_pass:
        all_passed = False

    # Profile API with session
    profile_resp = client.get('/api/profile')
    prof_pass = (profile_resp.status_code == 200 and profile_resp.json.get('profile', {}).get('role') == 'admin')
    print_status("Authenticated Profile (GET /api/profile)", prof_pass)
    if not prof_pass:
        all_passed = False

    # Admin Dashboard API as admin
    admin_dash = client.get('/api/dashboard/admin')
    adash_pass = (admin_dash.status_code == 200 and 'statistics' in admin_dash.json)
    print_status("Admin Dashboard API (GET /api/dashboard/admin)", adash_pass)
    if not adash_pass:
        all_passed = False

    # Logout
    logout_resp = client.post('/api/logout')
    logout_pass = (logout_resp.status_code == 200)
    print_status("Logout API (POST /api/logout)", logout_pass)
    if not logout_pass:
        all_passed = False

    # Student Login & RBAC test
    student_client = app.test_client()
    s_login = student_client.post('/api/login', json={"email": "alex.turner@student.edu", "password": "Student@12345"})
    s_pass = (s_login.status_code == 200)
    print_status("Student Login API (POST /api/login)", s_pass)
    if not s_pass:
        all_passed = False

    # RBAC: Student attempting to access Admin API -> Must be 403 Forbidden!
    forbidden_resp = student_client.get('/api/dashboard/admin')
    rbac_pass = (forbidden_resp.status_code == 403)
    print_status("RBAC Enforcement (Student -> Admin API: 403)", rbac_pass)
    if not rbac_pass:
        all_passed = False

    # Student Dashboard API
    s_dash = student_client.get('/api/dashboard/student')
    sdash_pass = (s_dash.status_code == 200 and 'metrics' in s_dash.json)
    print_status("Student Dashboard API (GET /api/dashboard/student)", sdash_pass)
    if not sdash_pass:
        all_passed = False

    # 3. Books & Research REST APIs
    print("-" * 80)
    print("CATALOG & REPOSITORY REST APIS:")

    books_resp = client.get('/api/books')
    b_pass = (books_resp.status_code == 200 and books_resp.json.get('count', 0) >= 10)
    print_status("Catalog Books API (GET /api/books)", b_pass, f"({books_resp.json.get('count', 0)} titles)")
    if not b_pass:
        all_passed = False

    book_single = client.get('/api/books/1')
    b1_pass = (book_single.status_code == 200 and 'book' in book_single.json)
    print_status("Single Book Details API (GET /api/books/1)", b1_pass)
    if not b1_pass:
        all_passed = False

    research_resp = client.get('/api/research')
    r_pass = (research_resp.status_code == 200 and research_resp.json.get('count', 0) >= 4)
    print_status("Research Papers API (GET /api/research)", r_pass, f"({research_resp.json.get('count', 0)} papers)")
    if not r_pass:
        all_passed = False

    # 4. Circulation & Members APIs
    print("-" * 80)
    print("CIRCULATION & MEMBER MANAGEMENT APIS:")

    my_records = student_client.get('/api/borrow/my-records')
    my_pass = (my_records.status_code == 200 and 'records' in my_records.json)
    print_status("Student Borrow Records (GET /api/borrow/my-records)", my_pass)
    if not my_pass:
        all_passed = False

    # Admin client for member endpoints
    adm_client = app.test_client()
    adm_client.post('/api/login', json={"email": "admin@library.edu", "password": "Admin@12345"})

    all_records = adm_client.get('/api/borrow/all-records')
    all_rec_pass = (all_records.status_code == 200 and 'records' in all_records.json)
    print_status("Admin All Records (GET /api/borrow/all-records)", all_rec_pass)
    if not all_rec_pass:
        all_passed = False

    members_resp = adm_client.get('/api/members')
    mem_pass = (members_resp.status_code == 200 and len(members_resp.json.get('members', [])) >= 2)
    print_status("Admin Members Roster (GET /api/members)", mem_pass)
    if not mem_pass:
        all_passed = False

    print("=" * 80)
    if all_passed:
        print("STAGE 4 VERIFICATION COMPLETED SUCCESSFULLY!")
        print("Flask backend, Blueprints, Sessions, RBAC security, and REST APIs are 100% operational.")
    else:
        print("Some backend route or API checks failed. Please inspect above.")
    print("=" * 80)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
