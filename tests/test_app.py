"""
Comprehensive Automated Test Suite
Digital Library & Research Management System
Built with Python's standard unittest framework.
"""

import unittest
import os
import json
import sqlite3
from pathlib import Path

from app import create_app
from database import get_db_connection, init_db, seed_sample_data, update_overdue_statuses


class DigitalLibraryTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure application for testing
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.client = cls.app.test_client()

    def setUp(self):
        # Ensure base data is synchronized
        init_db()
        seed_sample_data()
        update_overdue_statuses()

    # ==========================================================================
    # 1. AUTHENTICATION & REGISTRATION TESTS
    # ==========================================================================

    def test_student_registration_success(self):
        """Verify successful student registration with all parameters."""
        unique_email = "test.newstudent@college.edu"
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE email = ?", (unique_email,))
        conn.commit()
        conn.close()

        resp = self.client.post('/api/register', json={
            "name": "David Miller",
            "email": unique_email,
            "password": "Password@123",
            "department": "Computer Science & Engineering",
            "student_id": "CS-TEST-777",
            "phone": "+1-555-0909"
        })
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json.get('success'))

        # Check DB
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (unique_email,)).fetchone()
        conn.close()
        self.assertIsNotNone(user)
        self.assertEqual(user['name'], "David Miller")
        self.assertEqual(user['role'], "student")
        self.assertEqual(user['status'], "active")

    def test_duplicate_email_registration_fails(self):
        """Verify that duplicate email registration is rejected with 409 Conflict."""
        resp = self.client.post('/api/register', json={
            "name": "Duplicate User",
            "email": "alex.turner@student.edu",  # Seeded student
            "password": "Password@123",
            "department": "Computer Science",
            "student_id": "CS-DUP-01"
        })
        self.assertEqual(resp.status_code, 409)
        self.assertIn("already exists", resp.json.get('error', '').lower())

    def test_short_password_registration_fails(self):
        """Verify password validation rejects passwords < 6 characters."""
        resp = self.client.post('/api/register', json={
            "name": "Short Pwd",
            "email": "short@college.edu",
            "password": "123",
            "department": "CS",
            "student_id": "CS-SHORT-01"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("at least 6 characters", resp.json.get('error', ''))

    def test_login_success_student(self):
        """Verify student authentication and session establishment."""
        resp = self.client.post('/api/login', json={
            "email": "alex.turner@student.edu",
            "password": "Student@12345"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json.get('success'))
        self.assertEqual(resp.json.get('user', {}).get('role'), 'student')

    def test_login_success_admin(self):
        """Verify admin authentication and privileged session."""
        resp = self.client.post('/api/login', json={
            "email": "admin@library.edu",
            "password": "Admin@12345"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json.get('user', {}).get('role'), 'admin')

    def test_login_invalid_password_rejected(self):
        """Verify rejection of invalid passwords with 401."""
        resp = self.client.post('/api/login', json={
            "email": "admin@library.edu",
            "password": "WrongPassword123"
        })
        self.assertEqual(resp.status_code, 401)

    def test_deactivated_student_login_blocked(self):
        """Verify that inactive/suspended students cannot log in."""
        resp = self.client.post('/api/login', json={
            "email": "marcus.vance@student.edu",  # Seeded as inactive
            "password": "Student@12345"
        })
        self.assertEqual(resp.status_code, 403)
        self.assertIn("deactivated", resp.json.get('error', '').lower())

    def test_logout(self):
        """Verify session clearing upon logout."""
        c = self.app.test_client()
        c.post('/api/login', json={"email": "alex.turner@student.edu", "password": "Student@12345"})
        resp = c.post('/api/logout')
        self.assertEqual(resp.status_code, 200)

        # Profile request after logout should fail
        prof = c.get('/api/profile')
        self.assertEqual(prof.status_code, 401)

    # ==========================================================================
    # 2. ROLE-BASED ACCESS CONTROL (RBAC) TESTS
    # ==========================================================================

    def test_unauthenticated_protected_routes(self):
        """Verify that anonymous users cannot access protected routes."""
        anon = self.app.test_client()
        resp_api = anon.get('/api/dashboard/admin')
        self.assertEqual(resp_api.status_code, 401)

        resp_page = anon.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(resp_page.status_code, 302)  # Redirects to /login

    def test_student_forbidden_from_admin_api(self):
        """Verify that logged-in students receive 403 Forbidden on admin APIs."""
        s_client = self.app.test_client()
        s_client.post('/api/login', json={"email": "alex.turner@student.edu", "password": "Student@12345"})

        resp = s_client.get('/api/dashboard/admin')
        self.assertEqual(resp.status_code, 403)

        members_resp = s_client.get('/api/members')
        self.assertEqual(members_resp.status_code, 403)

    # ==========================================================================
    # 3. BOOK CATALOG & INVENTORY CRUD TESTS
    # ==========================================================================

    def test_get_books_and_filtering(self):
        """Verify book catalog search and availability filters."""
        # Search by keyword
        resp = self.client.get('/api/books?q=Architecture')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json.get('count', 0) >= 1)

        # Filter by availability
        avail_resp = self.client.get('/api/books?availability=available')
        self.assertEqual(avail_resp.status_code, 200)
        for b in avail_resp.json.get('books', []):
            self.assertGreater(b['available_copies'], 0)

        # Filter out of stock
        out_resp = self.client.get('/api/books?availability=out_of_stock')
        self.assertEqual(out_resp.status_code, 200)
        for b in out_resp.json.get('books', []):
            self.assertEqual(b['available_copies'], 0)

    def test_admin_add_and_edit_book(self):
        """Verify admin can add and modify book inventory."""
        adm = self.app.test_client()
        adm.post('/api/login', json={"email": "admin@library.edu", "password": "Admin@12345"})

        isbn = "978-0111222333"
        conn = get_db_connection()
        conn.execute("DELETE FROM books WHERE isbn = ?", (isbn,))
        conn.commit()
        conn.close()

        # Add
        add_resp = adm.post('/api/books', json={
            "title": "Cloud Native Microservices",
            "author": "Dr. Keith Anderson",
            "isbn": isbn,
            "category": "Software Engineering & Web Development",
            "total_copies": 5,
            "available_copies": 5,
            "shelf_location": "Shelf C-10"
        })
        self.assertEqual(add_resp.status_code, 201)
        book_id = add_resp.json.get('book_id')

        # Edit
        edit_resp = adm.put(f'/api/books/{book_id}', json={
            "title": "Cloud Native Microservices (2nd Edition)",
            "total_copies": 8,
            "available_copies": 8
        })
        self.assertEqual(edit_resp.status_code, 200)

        # Check DB
        conn = get_db_connection()
        b = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        conn.close()
        self.assertEqual(b['total_copies'], 8)
        self.assertEqual(b['title'], "Cloud Native Microservices (2nd Edition)")

    def test_delete_book_prevented_when_active_loans_exist(self):
        """Verify safe deletion prevents removing books with active loans."""
        adm = self.app.test_client()
        adm.post('/api/login', json={"email": "admin@library.edu", "password": "Admin@12345"})

        # Book 1 has an active issued loan
        resp = adm.delete('/api/books/1')
        self.assertEqual(resp.status_code, 400)
        self.assertIn("cannot delete", resp.json.get('error', '').lower())

    # ==========================================================================
    # 4. RESEARCH PAPERS MANAGEMENT TESTS
    # ==========================================================================

    def test_research_papers_discovery_and_download(self):
        """Verify research paper search, details, and PDF file downloads."""
        # API discovery
        resp = self.client.get('/api/research?q=Spanner')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json.get('count', 0) >= 1)

        # Single paper details
        p1 = self.client.get('/api/research/1')
        self.assertEqual(p1.status_code, 200)
        self.assertIn("Attention", p1.json.get('paper', {}).get('title', ''))

        # PDF download
        pdf_resp = self.client.get('/research/download/1')
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertTrue(pdf_resp.data.startswith(b'%PDF'))
        pdf_resp.close()

    # ==========================================================================
    # 5. CIRCULATION WORKFLOW & ATOMIC TRANSACTIONS
    # ==========================================================================

    def test_complete_circulation_transaction_lifecycle(self):
        """Verify hold request -> approval -> available copies decrement -> return -> increment."""
        # Setup clean student client
        s_client = self.app.test_client()
        s_client.post('/api/login', json={"email": "alex.turner@student.edu", "password": "Student@12345"})

        # Setup admin client
        adm = self.app.test_client()
        adm.post('/api/login', json={"email": "admin@library.edu", "password": "Admin@12345"})

        # Find book with available copies
        conn = get_db_connection()
        test_book = conn.execute("SELECT id, available_copies, total_copies FROM books WHERE available_copies > 1 LIMIT 1").fetchone()
        test_book_id = test_book['id']
        start_avail = test_book['available_copies']

        # Clear any active record on this book for this student to ensure clean state
        conn.execute("DELETE FROM borrow_records WHERE user_id = 2 AND book_id = ?", (test_book_id,))
        conn.commit()
        conn.close()

        # Step 1: Student requests book
        req_resp = s_client.post('/api/borrow/request', json={"book_id": test_book_id, "remarks": "Unit test lifecycle"})
        self.assertEqual(req_resp.status_code, 201)
        rec_id = req_resp.json.get('record_id')

        # Duplicate hold prevention
        dup_req = s_client.post('/api/borrow/request', json={"book_id": test_book_id})
        self.assertEqual(dup_req.status_code, 409)

        # Step 2: Admin approves request (Should decrement available_copies by 1)
        app_resp = adm.put(f'/api/borrow/approve/{rec_id}')
        self.assertEqual(app_resp.status_code, 200)

        conn = get_db_connection()
        b_mid = conn.execute("SELECT available_copies FROM books WHERE id = ?", (test_book_id,)).fetchone()
        r_mid = conn.execute("SELECT status, due_date FROM borrow_records WHERE id = ?", (rec_id,)).fetchone()
        conn.close()

        self.assertEqual(b_mid['available_copies'], start_avail - 1)
        self.assertEqual(r_mid['status'], "Issued")
        self.assertIsNotNone(r_mid['due_date'])

        # Step 3: Admin records return (Should increment available_copies back to start_avail)
        ret_resp = adm.put(f'/api/borrow/return/{rec_id}')
        self.assertEqual(ret_resp.status_code, 200)

        conn = get_db_connection()
        b_end = conn.execute("SELECT available_copies FROM books WHERE id = ?", (test_book_id,)).fetchone()
        r_end = conn.execute("SELECT status, return_date FROM borrow_records WHERE id = ?", (rec_id,)).fetchone()
        conn.close()

        self.assertEqual(b_end['available_copies'], start_avail)
        self.assertEqual(r_end['status'], "Returned")
        self.assertIsNotNone(r_end['return_date'])

    def test_borrowing_out_of_stock_fails(self):
        """Verify borrowing request fails when book has 0 available copies."""
        s_client = self.app.test_client()
        s_client.post('/api/login', json={"email": "priya.sharma@student.edu", "password": "Student@12345"})

        # Book 10 is configured as Out of Stock (0 copies)
        resp = s_client.post('/api/borrow/request', json={"book_id": 10})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("out of stock", resp.json.get('error', '').lower())

    # ==========================================================================
    # 6. MEMBER STATUS & ADMINISTRATIVE AUDITS
    # ==========================================================================

    def test_member_status_toggle(self):
        """Verify admin can activate and deactivate student accounts."""
        adm = self.app.test_client()
        adm.post('/api/login', json={"email": "admin@library.edu", "password": "Admin@12345"})

        # Toggle to inactive
        resp_inact = adm.put('/api/members/3/status', json={"status": "inactive"})
        self.assertEqual(resp_inact.status_code, 200)
        self.assertEqual(resp_inact.json.get('status'), 'inactive')

        # Toggle back to active
        resp_act = adm.put('/api/members/3/status', json={"status": "active"})
        self.assertEqual(resp_act.status_code, 200)
        self.assertEqual(resp_act.json.get('status'), 'active')

    # ==========================================================================
    # 7. DASHBOARD METRICS CALCULATION INTEGRITY
    # ==========================================================================

    def test_dashboard_statistics_match_database(self):
        """Verify dashboard counters are strictly calculated from live DB rows."""
        adm = self.app.test_client()
        adm.post('/api/login', json={"email": "admin@library.edu", "password": "Admin@12345"})

        resp = adm.get('/api/dashboard/admin')
        self.assertEqual(resp.status_code, 200)
        stats = resp.json.get('statistics', {})

        conn = get_db_connection()
        db_books = conn.execute("SELECT count(*) FROM books").fetchone()[0]
        db_members = conn.execute("SELECT count(*) FROM users WHERE role = 'student'").fetchone()[0]
        db_issued = conn.execute("SELECT count(*) FROM borrow_records WHERE status = 'Issued'").fetchone()[0]
        db_returned = conn.execute("SELECT count(*) FROM borrow_records WHERE status = 'Returned'").fetchone()[0]
        conn.close()

        self.assertEqual(stats['total_books'], db_books)
        self.assertEqual(stats['total_registered_members'], db_members)
        self.assertEqual(stats['currently_issued_books'], db_issued)
        self.assertEqual(stats['returned_books'], db_returned)


if __name__ == '__main__':
    unittest.main()
