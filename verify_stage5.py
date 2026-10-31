"""
Stage 5 Verification Script
Digital Library & Research Management System

Verifies full end-to-end integration across frontend templates, backend routes,
AJAX endpoints, session management, and SQLite database persistence.
"""

import sys
import os
import json
import html
import sqlite3
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

def print_status(step: str, status: bool, extra: str = ""):
    symbol = "[PASS]" if status else "[FAIL]"
    print(f"{symbol:<10} | {step:<48} {extra}")

def main():
    print("=" * 82)
    print(" DIGITAL LIBRARY & RESEARCH MANAGEMENT SYSTEM - STAGE 5 VERIFICATION")
    print("=" * 82)

    all_passed = True
    base_dir = Path(__file__).resolve().parent

    try:
        from app import app
        from database import get_db_connection
    except Exception as e:
        print(f"Failed to import app or database: {e}")
        return 1

    app.config['TESTING'] = True
    client = app.test_client()

    # --------------------------------------------------------------------------
    # Journey 1: Student Registration, Database Persistence & Login
    # --------------------------------------------------------------------------
    print("1. REGISTRATION & AUTHENTICATION INTEGRATION:")
    test_email = "marathon.tester@student.edu"
    test_pass = "Tester@12345"

    # Clean up test user if exists from prior runs
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE email = ?", (test_email,))
    conn.commit()
    conn.close()

    # Submit registration form
    reg_resp = client.post('/register', data={
        "name": "Marathon Test Student",
        "email": test_email,
        "student_id": "CS-TEST-999",
        "phone": "+1-555-9999",
        "department": "Computer Science & Engineering",
        "password": test_pass,
        "confirm_password": test_pass
    }, follow_redirects=True)
    reg_ok = (reg_resp.status_code == 200)

    # Verify directly in SQLite database
    conn = get_db_connection()
    user_row = conn.execute("SELECT * FROM users WHERE email = ?", (test_email,)).fetchone()
    conn.close()

    user_persisted = (user_row is not None and user_row['name'] == "Marathon Test Student")
    print_status("Student Registration Form -> DB Persistence", reg_ok and user_persisted, f"(ID: {user_row['id'] if user_row else 'None'})")
    if not (reg_ok and user_persisted):
        all_passed = False

    test_student_id = user_row['id'] if user_row else None

    # Login with newly created student credentials
    s_client = app.test_client()
    login_resp = s_client.post('/login', data={
        "email": test_email,
        "password": test_pass
    }, follow_redirects=True)
    s_login_ok = (login_resp.status_code == 200 and "Marathon Test Student" in login_resp.text)
    print_status("Form Login -> Session State & Dashboard Render", s_login_ok)
    if not s_login_ok:
        all_passed = False

    # --------------------------------------------------------------------------
    # Journey 2: Book Catalog & Borrow Request Cycle
    # --------------------------------------------------------------------------
    print("-" * 82)
    print("2. CIRCULATION WORKFLOW (REQUEST -> APPROVAL -> COPY COUNT -> RETURN):")

    # Pick an available book
    conn = get_db_connection()
    target_book = conn.execute("SELECT * FROM books WHERE available_copies > 1 LIMIT 1").fetchone()
    conn.close()

    if not target_book:
        print("ERROR: No available books with copies > 1 for testing.")
        return 1

    book_id = target_book['id']
    initial_avail = target_book['available_copies']

    # Student submits borrow request via AJAX endpoint
    borrow_req = s_client.post('/api/borrow/request', json={"book_id": book_id, "remarks": "Marathon loan test"})
    req_pass = (borrow_req.status_code == 201 and borrow_req.json.get('success') is True)
    record_id = borrow_req.json.get('record_id')
    print_status("Borrow Request API (POST /api/borrow/request)", req_pass, f"(Record #{record_id})")
    if not req_pass:
        all_passed = False

    # Verify pending state in database
    conn = get_db_connection()
    rec = conn.execute("SELECT * FROM borrow_records WHERE id = ?", (record_id,)).fetchone()
    conn.close()
    pending_in_db = (rec is not None and rec['status'] == 'Pending')
    print_status("Pending Record Verification in DB", pending_in_db)
    if not pending_in_db:
        all_passed = False

    # Admin Login to approve
    admin_client = app.test_client()
    admin_client.post('/login', data={"email": "admin@library.edu", "password": "Admin@12345"}, follow_redirects=True)

    # Admin approves hold
    approve_resp = admin_client.put(f'/api/borrow/approve/{record_id}')
    approve_ok = (approve_resp.status_code == 200 and approve_resp.json.get('success') is True)
    print_status("Librarian Hold Approval (PUT /api/borrow/approve)", approve_ok)
    if not approve_ok:
        all_passed = False

    # Verify database copy decrement
    conn = get_db_connection()
    book_after_issue = conn.execute("SELECT available_copies FROM books WHERE id = ?", (book_id,)).fetchone()
    rec_after_issue = conn.execute("SELECT status, due_date FROM borrow_records WHERE id = ?", (record_id,)).fetchone()
    conn.close()

    decrement_ok = (book_after_issue['available_copies'] == initial_avail - 1)
    status_issued_ok = (rec_after_issue['status'] == 'Issued' and rec_after_issue['due_date'] is not None)
    print_status("Inventory Decrement (Available: -1 in DB)", decrement_ok, f"({initial_avail} -> {book_after_issue['available_copies']})")
    print_status("Loan Record Status Transition -> 'Issued'", status_issued_ok)
    if not (decrement_ok and status_issued_ok):
        all_passed = False

    # Verify Student's My Books UI renders the newly issued book
    my_books_resp = s_client.get('/my-books')
    book_title_part = target_book['title'][:18]
    my_books_rendered = (my_books_resp.status_code == 200 and (book_title_part in my_books_resp.text or html.escape(target_book['title']) in my_books_resp.text))
    print_status("Student Active Loans Page (/my-books)", my_books_rendered)
    if not my_books_rendered:
        all_passed = False

    # Return book workflow
    return_resp = admin_client.put(f'/api/borrow/return/{record_id}')
    return_ok = (return_resp.status_code == 200 and return_resp.json.get('success') is True)
    print_status("Librarian Book Return (PUT /api/borrow/return)", return_ok)
    if not return_ok:
        all_passed = False

    # Verify database copy increment back to initial
    conn = get_db_connection()
    book_after_return = conn.execute("SELECT available_copies FROM books WHERE id = ?", (book_id,)).fetchone()
    rec_after_return = conn.execute("SELECT status, return_date FROM borrow_records WHERE id = ?", (record_id,)).fetchone()
    conn.close()

    increment_ok = (book_after_return['available_copies'] == initial_avail)
    status_returned_ok = (rec_after_return['status'] == 'Returned' and rec_after_return['return_date'] is not None)
    print_status("Inventory Increment (Available: +1 in DB)", increment_ok, f"({initial_avail - 1} -> {book_after_return['available_copies']})")
    print_status("Loan Record Status Transition -> 'Returned'", status_returned_ok)
    if not (increment_ok and status_returned_ok):
        all_passed = False

    # --------------------------------------------------------------------------
    # Journey 3: Member Account Status Lifecycle
    # --------------------------------------------------------------------------
    print("-" * 82)
    print("3. MEMBER MANAGEMENT & ACCESS CONTROL:")

    # Admin deactivates student
    deact_resp = admin_client.put(f'/api/members/{test_student_id}/status', json={"status": "inactive"})
    deact_ok = (deact_resp.status_code == 200)

    # Deactivated student tries to login
    deact_client = app.test_client()
    deact_login = deact_client.post('/login', data={"email": test_email, "password": test_pass})
    login_blocked = ("deactivated" in deact_login.text)
    print_status("Account Deactivation & Login Prevention", deact_ok and login_blocked)
    if not (deact_ok and login_blocked):
        all_passed = False

    # Admin reactivates student
    react_resp = admin_client.put(f'/api/members/{test_student_id}/status', json={"status": "active"})
    react_ok = (react_resp.status_code == 200)

    # Student logs in successfully again
    react_login = deact_client.post('/login', data={"email": test_email, "password": test_pass}, follow_redirects=True)
    react_login_ok = (react_login.status_code == 200 and "Welcome back" in react_login.text)
    print_status("Account Reactivation & Login Restoration", react_ok and react_login_ok)
    if not (react_ok and react_login_ok):
        all_passed = False

    # --------------------------------------------------------------------------
    # Journey 4: Admin Add Book & Edit Book Flow
    # --------------------------------------------------------------------------
    print("-" * 82)
    print("4. BOOK INVENTORY CRUD WORKFLOW:")

    new_isbn = "978-0999999999"
    # Clean up if exists
    conn = get_db_connection()
    conn.execute("DELETE FROM books WHERE isbn = ?", (new_isbn,))
    conn.commit()
    conn.close()

    add_resp = admin_client.post('/admin/books/add', data={
        "title": "Automated Testing in Distributed Cloud Systems",
        "author": "Dr. Sarah Miller",
        "isbn": new_isbn,
        "category": "Software Engineering & Web Development",
        "publisher": "Engineering University Press",
        "publication_year": 2025,
        "language": "English",
        "total_copies": 4,
        "available_copies": 4,
        "shelf_location": "Shelf F-01, 3rd Floor",
        "description": "Comprehensive reference on automated integration test harnesses."
    }, follow_redirects=True)

    conn = get_db_connection()
    new_book_row = conn.execute("SELECT * FROM books WHERE isbn = ?", (new_isbn,)).fetchone()
    conn.close()

    book_added = (new_book_row is not None and new_book_row['total_copies'] == 4)
    print_status("Admin Add Book Form -> DB Persistence", book_added, f"(Book ID: {new_book_row['id'] if new_book_row else 'None'})")
    if not book_added:
        all_passed = False

    # Edit the book
    if new_book_row:
        edit_resp = admin_client.post(f'/admin/books/edit/{new_book_row["id"]}', data={
            "title": "Automated Testing in Distributed Cloud Systems (2nd Ed)",
            "author": "Dr. Sarah Miller",
            "isbn": new_isbn,
            "category": "Software Engineering & Web Development",
            "publisher": "Engineering University Press",
            "publication_year": 2026,
            "language": "English",
            "total_copies": 6,
            "available_copies": 6,
            "shelf_location": "Shelf F-02, 3rd Floor",
            "description": "Expanded edition."
        }, follow_redirects=True)

        conn = get_db_connection()
        updated_book_row = conn.execute("SELECT * FROM books WHERE id = ?", (new_book_row['id'],)).fetchone()
        conn.close()

        book_updated = (updated_book_row['title'] == "Automated Testing in Distributed Cloud Systems (2nd Ed)" and updated_book_row['total_copies'] == 6)
        print_status("Admin Edit Book Form -> DB Update", book_updated)
        if not book_updated:
            all_passed = False

    # --------------------------------------------------------------------------
    # Journey 5: Research Paper Document Serving
    # --------------------------------------------------------------------------
    print("-" * 82)
    print("5. RESEARCH REPOSITORY & DOCUMENT DELIVERY:")

    conn = get_db_connection()
    sample_paper = conn.execute("SELECT id, title, pdf_path FROM research_papers WHERE pdf_path IS NOT NULL LIMIT 1").fetchone()
    conn.close()

    if sample_paper:
        pdf_resp = client.get(f'/research/download/{sample_paper["id"]}')
        pdf_served = (pdf_resp.status_code == 200 and pdf_resp.data.startswith(b'%PDF'))
        print_status("Secure PDF Document Delivery (/research/download)", pdf_served, f"({sample_paper['pdf_path']})")
        if not pdf_served:
            all_passed = False
    else:
        print_status("Secure PDF Document Delivery (/research/download)", False, "No paper with PDF found")
        all_passed = False

    print("=" * 82)
    if all_passed:
        print("STAGE 5 VERIFICATION COMPLETED SUCCESSFULLY!")
        print("Frontend, Backend, and Database are fully integrated with live transactions.")
    else:
        print("Some integration tests failed. Please inspect logs above.")
    print("=" * 82)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
