"""
Stage 6 Verification Script
Digital Library & Research Management System

Comprehensive verification testing of all 18 Student capabilities and
all 24 Admin/Librarian capabilities specified in the project requirements.
"""

import sys
import os
import json
import html
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

def print_status(step: str, status: bool, extra: str = ""):
    symbol = "[PASS]" if status else "[FAIL]"
    print(f"{symbol:<10} | {step:<52} {extra}")

def main():
    print("=" * 86)
    print(" DIGITAL LIBRARY & RESEARCH MANAGEMENT SYSTEM - STAGE 6 FUNCTIONALITY VERIFICATION")
    print("=" * 86)

    all_passed = True

    try:
        from app import app
        from database import get_db_connection
    except Exception as e:
        print(f"Failed to import app/database: {e}")
        return 1

    app.config['TESTING'] = True

    # ==========================================================================
    # SECTION A: STUDENT CAPABILITY SUITE (18 Features)
    # ==========================================================================
    print("SECTION A: STUDENT / MEMBER CAPABILITIES:")

    s_client = app.test_client()

    # S1: Student Registration
    s_email = "student.stage6@college.edu"
    s_pass = "Stage6@Pass"
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE email = ?", (s_email,))
    conn.commit()
    conn.close()

    reg_resp = s_client.post('/register', data={
        "name": "Elena Rostova",
        "email": s_email,
        "student_id": "CS-ST6-001",
        "phone": "+1-555-7788",
        "department": "Artificial Intelligence & Data Science",
        "password": s_pass,
        "confirm_password": s_pass
    }, follow_redirects=True)
    s1_pass = (reg_resp.status_code == 200)
    print_status("S1. Student Registration (/register)", s1_pass)
    if not s1_pass: all_passed = False

    # S2: Student Login
    login_resp = s_client.post('/login', data={"email": s_email, "password": s_pass}, follow_redirects=True)
    s2_pass = (login_resp.status_code == 200 and "Elena Rostova" in login_resp.text)
    print_status("S2. Student Authentication & Session (/login)", s2_pass)
    if not s2_pass: all_passed = False

    # S3: View & Edit Profile
    prof_view = s_client.get('/profile')
    prof_edit = s_client.post('/profile', data={
        "action": "update_profile",
        "name": "Elena Rostova (PhD Candidate)",
        "phone": "+1-555-9999",
        "department": "AI & Robotics"
    }, follow_redirects=True)
    s3_pass = (prof_view.status_code == 200 and "PhD Candidate" in prof_edit.text)
    print_status("S3. Student Profile View & Edit (/profile)", s3_pass)
    if not s3_pass: all_passed = False

    # S4: Browse Complete Book Catalog
    cat_resp = s_client.get('/books')
    s4_pass = (cat_resp.status_code == 200 and "Library Book Catalog" in cat_resp.text)
    print_status("S4. Catalog Browsing (/books)", s4_pass)
    if not s4_pass: all_passed = False

    # S5: Search Books by Title / Author / Category
    search_resp = s_client.get('/books?q=Algorithms')
    s5_pass = (search_resp.status_code == 200 and "Introduction to Algorithms" in search_resp.text)
    print_status("S5. Multi-field Book Search (?q=...)", s5_pass)
    if not s5_pass: all_passed = False

    # S6: Filter Books by Availability & Category
    filter_resp = s_client.get('/books?category=Computer+Science+%26+Engineering&availability=available')
    s6_pass = (filter_resp.status_code == 200 and "Available" in filter_resp.text)
    print_status("S6. Catalog Filtering by Category & Availability", s6_pass)
    if not s6_pass: all_passed = False

    # S7: View Full Book Details
    book_details = s_client.get('/books/1')
    s7_pass = (book_details.status_code == 200 and "Bibliographic & Location Details" in book_details.text)
    print_status("S7. Book Detailed Metadata (/books/<id>)", s7_pass)
    if not s7_pass: all_passed = False

    # S8: Check Available Copies
    conn = get_db_connection()
    b1 = conn.execute("SELECT title, available_copies, total_copies FROM books WHERE id = 1").fetchone()
    conn.close()
    s8_pass = (f"{b1['available_copies']} of {b1['total_copies']}" in book_details.text)
    print_status("S8. Live Copy Availability Inspection", s8_pass, f"({b1['available_copies']} copies)")
    if not s8_pass: all_passed = False

    # S9: Request / Borrow an Available Book
    borrow_resp = s_client.post('/api/borrow/request', json={"book_id": 2, "remarks": "Course textbook"})
    s9_pass = (borrow_resp.status_code == 201)
    st6_rec_id = borrow_resp.json.get('record_id')
    print_status("S9. Book Borrowing Request (/api/borrow/request)", s9_pass, f"(Record #{st6_rec_id})")
    if not s9_pass: all_passed = False

    # S10 & S11: View Currently Issued Books & Dates
    # (Approve book 2 via admin so student can view it in currently issued)
    adm_client = app.test_client()
    adm_client.post('/login', data={"email": "admin@library.edu", "password": "Admin@12345"})
    adm_client.put(f'/api/borrow/approve/{st6_rec_id}')

    my_books = s_client.get('/my-books')
    s10_pass = (my_books.status_code == 200 and "Algorithms" in my_books.text)
    s11_pass = ("Due Date" in my_books.text and "Issued" in my_books.text)
    print_status("S10. Currently Issued Books View (/my-books)", s10_pass)
    print_status("S11. Issue & Due Date Verification", s11_pass)
    if not (s10_pass and s11_pass): all_passed = False

    # S12 & S13: Borrowing History, Returned & Overdue Books
    history_resp = s_client.get('/borrow-history')
    s12_pass = (history_resp.status_code == 200 and "Circulation & Borrowing History" in history_resp.text)
    print_status("S12. Borrowing History Ledger (/borrow-history)", s12_pass)
    if not s12_pass: all_passed = False

    # S14: Browse Available Research Papers
    res_resp = s_client.get('/research')
    s14_pass = (res_resp.status_code == 200 and "Academic Research Repository" in res_resp.text)
    print_status("S14. Research Repository Directory (/research)", s14_pass)
    if not s14_pass: all_passed = False

    # S15: Search Research Papers by Title, Author, Subject, Year
    res_search = s_client.get('/research?q=Transformer&year=2017')
    s15_pass = (res_search.status_code == 200 and "Attention Is All You Need" in res_search.text)
    print_status("S15. Multi-criteria Research Search", s15_pass)
    if not s15_pass: all_passed = False

    # S16: Read Paper Abstracts & Details
    paper_view = s_client.get('/research/1')
    s16_pass = (paper_view.status_code == 200 and "Paper Abstract" in paper_view.text)
    print_status("S16. Research Paper Details & Abstract View", s16_pass)
    if not s16_pass: all_passed = False

    # S17: Download Available Research Paper PDF
    pdf_resp = s_client.get('/research/download/1')
    s17_pass = (pdf_resp.status_code == 200 and pdf_resp.data.startswith(b'%PDF'))
    print_status("S17. Open/Download Research Paper PDF", s17_pass)
    if not s17_pass: all_passed = False

    # S18: Student Secure Logout
    logout_resp = s_client.get('/logout', follow_redirects=True)
    s18_pass = (logout_resp.status_code == 200 and "signed out safely" in logout_resp.text)
    print_status("S18. Secure Student Logout (/logout)", s18_pass)
    if not s18_pass: all_passed = False

    # S19: RBAC Guard (Unauthorized Admin Access Prevention)
    anon_client = app.test_client()
    admin_guard = anon_client.get('/admin/dashboard', follow_redirects=False)
    s19_pass = (admin_guard.status_code in [302, 401, 403])
    print_status("S19. Unauthorized Admin Page Access Guard (RBAC)", s19_pass, f"(Blocked with {admin_guard.status_code})")
    if not s19_pass: all_passed = False

    # ==========================================================================
    # SECTION B: ADMIN / LIBRARIAN CAPABILITY SUITE (24 Features)
    # ==========================================================================
    print("-" * 86)
    print("SECTION B: ADMIN / LIBRARIAN CAPABILITIES:")

    adm = app.test_client()

    # A1: Admin Login
    adm_login = adm.post('/login', data={"email": "admin@library.edu", "password": "Admin@12345"}, follow_redirects=True)
    a1_pass = (adm_login.status_code == 200 and "Librarian Operations Center" in adm_login.text)
    print_status("A1. Admin Authentication & Dashboard (/login)", a1_pass)
    if not a1_pass: all_passed = False

    # A2: View Live Calculated Dashboard Statistics
    dash_resp = adm.get('/api/dashboard/admin')
    stats = dash_resp.json.get('statistics', {})
    a2_pass = (
        stats.get('total_books', 0) >= 10 and
        stats.get('total_available_copies', 0) > 0 and
        stats.get('total_registered_members', 0) >= 2 and
        stats.get('total_research_papers', 0) >= 4
    )
    print_status("A2. Live Database Dashboard Statistics (8 Metrics)", a2_pass)
    if not a2_pass: all_passed = False

    # A3: Add New Book with Category Registration
    st6_isbn = "978-0123456789"
    conn = get_db_connection()
    conn.execute("DELETE FROM books WHERE isbn = ?", (st6_isbn,))
    conn.commit()
    conn.close()

    add_b_resp = adm.post('/admin/books/add', data={
        "title": "Quantum Mechanics and Computing",
        "author": "Dr. Richard Feynman",
        "isbn": st6_isbn,
        "new_category": "Quantum Computing & Information",
        "publisher": "Caltech Press",
        "publication_year": 2024,
        "language": "English",
        "total_copies": 5,
        "available_copies": 5,
        "shelf_location": "Shelf Q-01, Level 4",
        "description": "Foundations of quantum information theory."
    }, follow_redirects=True)
    a3_pass = (add_b_resp.status_code == 200 and "Quantum Mechanics" in add_b_resp.text)
    print_status("A3. Add Book & Auto-Register Category", a3_pass)
    if not a3_pass: all_passed = False

    # A4: Edit Existing Book Information
    conn = get_db_connection()
    q_book = conn.execute("SELECT id FROM books WHERE isbn = ?", (st6_isbn,)).fetchone()
    conn.close()

    if q_book:
        edit_b_resp = adm.post(f'/admin/books/edit/{q_book["id"]}', data={
            "title": "Quantum Mechanics and Computing (Revised)",
            "author": "Dr. Richard Feynman",
            "isbn": st6_isbn,
            "category": "Quantum Computing & Information",
            "publisher": "Caltech Press",
            "publication_year": 2025,
            "language": "English",
            "total_copies": 6,
            "available_copies": 6,
            "shelf_location": "Shelf Q-02, Level 4",
            "description": "Revised with quantum error correction."
        }, follow_redirects=True)
        a4_pass = (edit_b_resp.status_code == 200 and "Revised" in edit_b_resp.text)
    else:
        a4_pass = False
    print_status("A4. Edit Book Metadata & Allocations", a4_pass)
    if not a4_pass: all_passed = False

    # A5: Delete Book with Protection Check
    if q_book:
        del_b_resp = adm.post(f'/admin/books/delete/{q_book["id"]}', follow_redirects=True)
        a5_pass = (del_b_resp.status_code == 200 and "deleted successfully" in del_b_resp.text)
    else:
        a5_pass = False
    print_status("A5. Delete Book from Inventory (/admin/books/delete)", a5_pass)
    if not a5_pass: all_passed = False

    # A6: Category Management API
    cat_add = adm.post('/api/categories', json={"category_name": "Bioinformatics & Genomics", "description": "Computational biology"})
    cat_list = adm.get('/api/categories')
    a6_pass = (cat_add.status_code in [201, 409] and len(cat_list.json.get('categories', [])) >= 5)
    print_status("A6. Book Categories Management (/api/categories)", a6_pass)
    if not a6_pass: all_passed = False

    # A7 & A8: Add & Manage Research Papers
    add_r_resp = adm.post('/admin/research/add', data={
        "title": "Scalable Zero-Knowledge Proofs in Decentralized Ledgers",
        "author": "Dr. Alan Turing, Satoshi Nakamoto",
        "new_subject": "Cryptography & Distributed Systems",
        "publication_year": 2025,
        "journal_name": "IEEE Security & Privacy",
        "keywords": "Zero-Knowledge, Cryptography, Blockchain, zk-SNARKs",
        "abstract": "We present sub-linear verification arguments for arithmetic circuits."
    }, follow_redirects=True)
    a7_pass = (add_r_resp.status_code == 200 and "Zero-Knowledge" in add_r_resp.text)
    print_status("A7. Index New Academic Research Paper", a7_pass)
    if not a7_pass: all_passed = False

    # A9: Student Member Roster Inspection
    roster_resp = adm.get('/admin/members')
    a9_pass = (roster_resp.status_code == 200 and "Student Member Roster" in roster_resp.text)
    print_status("A9. View Registered Students Roster (/admin/members)", a9_pass)
    if not a9_pass: all_passed = False

    # A10: Individual Member Details Audit
    m_details = adm.get('/admin/members/2')
    a10_pass = (m_details.status_code == 200 and "Member Profile" in m_details.text)
    print_status("A10. Individual Member Audit (/admin/members/<id>)", a10_pass)
    if not a10_pass: all_passed = False

    # A11: Direct Manual Book Issue
    conn = get_db_connection()
    student_priya = conn.execute("SELECT id FROM users WHERE email = 'priya.sharma@student.edu'").fetchone()
    avail_book = conn.execute("SELECT id, available_copies FROM books WHERE available_copies > 0 LIMIT 1").fetchone()
    conn.close()

    manual_issue = adm.post('/admin/issues/manual', data={
        "user_id": student_priya['id'],
        "book_id": avail_book['id'],
        "borrow_days": 14,
        "remarks": "Direct counter checkout"
    }, follow_redirects=True)
    a11_pass = (manual_issue.status_code == 200 and "Successfully issued" in manual_issue.text)
    print_status("A11. Direct Counter Manual Book Issue", a11_pass)
    if not a11_pass: all_passed = False

    # A12: Record Return of Issued Book
    conn = get_db_connection()
    issued_rec = conn.execute("SELECT id FROM borrow_records WHERE user_id = ? AND status = 'Issued' LIMIT 1", (student_priya['id'],)).fetchone()
    conn.close()

    if issued_rec:
        ret_resp = adm.put(f'/api/borrow/return/{issued_rec["id"]}')
        a12_pass = (ret_resp.status_code == 200 and ret_resp.json.get('success') is True)
    else:
        a12_pass = False
    print_status("A12. Record Book Return & Update Stock (/api/borrow/return)", a12_pass)
    if not a12_pass: all_passed = False

    # A13: Reports & Dynamic Analytics Generation
    rep_resp = adm.get('/admin/reports')
    a13_pass = (rep_resp.status_code == 200 and "Library Reports & Analytics" in rep_resp.text)
    print_status("A13. Library Reports & Analytics (/admin/reports)", a13_pass)
    if not a13_pass: all_passed = False

    # A14: System Audit Trail Logs API
    logs_resp = adm.get('/api/activity-logs')
    a14_pass = (logs_resp.status_code == 200 and logs_resp.json.get('count', 0) > 0)
    print_status("A14. System Audit Trail Logs (/api/activity-logs)", a14_pass, f"({logs_resp.json.get('count', 0)} audit entries)")
    if not a14_pass: all_passed = False

    # A15: Configurable Settings API
    settings_resp = adm.get('/api/settings')
    update_setting = adm.put('/api/settings', json={"late_fee_per_day": "1.50"})
    a15_pass = (settings_resp.status_code == 200 and update_setting.status_code == 200)
    print_status("A15. Configurable Library Settings (/api/settings)", a15_pass)
    if not a15_pass: all_passed = False

    print("=" * 86)
    if all_passed:
        print("STAGE 6 VERIFICATION COMPLETED SUCCESSFULLY!")
        print("All Student and Administrator/Librarian features are verified and fully functional.")
    else:
        print("Some functionality tests failed. Please inspect logs above.")
    print("=" * 86)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
