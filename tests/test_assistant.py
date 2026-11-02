"""
Test Suite for Smart AI Library Assistant ("Libra") and Welcome Experience
Tests intent recognition, live DB integration, role-aware responses, and action buttons.
"""

import unittest
from app import create_app
from database import get_db_connection, init_db, seed_sample_data, update_overdue_statuses


class TestLibraryAssistant(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_sample_data()
        update_overdue_statuses()
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['SECRET_KEY'] = 'test-secret-key-123'
        cls.client = cls.app.test_client()

    def setUp(self):
        self.client = self.app.test_client()

    def login_student(self):
        return self.client.post('/api/login', json={
            'email': 'alex.turner@student.edu',
            'password': 'Student@12345'
        })

    def login_admin(self):
        return self.client.post('/api/login', json={
            'email': 'admin@library.edu',
            'password': 'Admin@12345'
        })

    # ==========================================================================
    # 1. Suggestions API Tests
    # ==========================================================================

    def test_suggestions_guest(self):
        res = self.client.get('/api/assistant/suggestions')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['role'], 'guest')
        self.assertTrue(len(data['suggestions']) > 0)

    def test_suggestions_student(self):
        self.login_student()
        res = self.client.get('/api/assistant/suggestions')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['role'], 'student')
        self.assertTrue(any('borrowed' in s.lower() for s in data['suggestions']))

    def test_suggestions_admin(self):
        self.login_admin()
        res = self.client.get('/api/assistant/suggestions')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['role'], 'admin')
        self.assertTrue(any('pending' in s.lower() for s in data['suggestions']))

    # ==========================================================================
    # 2. Greeting & Identity
    # ==========================================================================

    def test_chat_greeting(self):
        res = self.client.post('/api/assistant/chat', json={'message': 'Hello Libra'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['intent'], 'greeting')
        self.assertIn('Libra', data['reply'])
        self.assertTrue(any(a['url'] == '/books' for a in data['actions']))

    # ==========================================================================
    # 3. Book Search & Catalog Navigation
    # ==========================================================================

    def test_book_search_navigation(self):
        res = self.client.post('/api/assistant/chat', json={'message': 'I want to search for a book'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'book_search_guidance')
        self.assertIn('Book Catalog', data['reply'])
        self.assertTrue(any(a['url'] == '/books' for a in data['actions']))

    def test_specific_book_lookup_found(self):
        res = self.client.post('/api/assistant/chat', json={'message': 'Do you have Clean Architecture?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'book_specific_lookup')
        self.assertIn('Clean Architecture', data['reply'])
        self.assertTrue(any('/books/' in a['url'] for a in data['actions']))

    def test_specific_book_lookup_not_found(self):
        res = self.client.post('/api/assistant/chat', json={'message': 'Do you have Quantum Warp Engines?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'book_specific_lookup')
        self.assertIn('searched our library catalog', data['reply'])
        self.assertTrue(any(a['url'] == '/books' for a in data['actions']))

    # ==========================================================================
    # 4. Student Active Loans (Live DB)
    # ==========================================================================

    def test_active_loans_authenticated_student(self):
        self.login_student()
        res = self.client.post('/api/assistant/chat', json={'message': 'How many books have I borrowed?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'student_active_loans')
        self.assertIn('My Borrowed Books', data['reply'])
        self.assertTrue(any(a['url'] == '/my-books' for a in data['actions']))

    def test_active_loans_guest(self):
        res = self.client.post('/api/assistant/chat', json={'message': 'Which books are currently issued to me?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'auth_required')
        self.assertIn('sign in', data['reply'].lower())

    # ==========================================================================
    # 5. Overdue Books & Next Return Date (Live DB)
    # ==========================================================================

    def test_overdue_books_student(self):
        self.login_student()
        res = self.client.post('/api/assistant/chat', json={'message': 'Do I have any overdue books?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'student_due_dates')
        self.assertTrue(any(a['url'] == '/my-books' for a in data['actions']))

    def test_overdue_books_admin(self):
        self.login_admin()
        res = self.client.post('/api/assistant/chat', json={'message': 'How many books are overdue system-wide?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'admin_overdue_check')
        self.assertTrue(any(a['url'] == '/admin/issues' for a in data['actions']))

    # ==========================================================================
    # 6. Borrowing History
    # ==========================================================================

    def test_borrowing_history(self):
        self.login_student()
        res = self.client.post('/api/assistant/chat', json={'message': 'Where can I see my borrowing history?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'borrowing_history')
        self.assertIn('Borrowing History', data['reply'])
        self.assertTrue(any(a['url'] == '/borrow-history' for a in data['actions']))

    # ==========================================================================
    # 7. Book Availability
    # ==========================================================================

    def test_book_availability(self):
        res = self.client.post('/api/assistant/chat', json={'message': 'How can I check whether a book is available?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'book_availability')
        self.assertIn('Book Catalog', data['reply'])
        self.assertTrue(any('/books' in a['url'] for a in data['actions']))

    # ==========================================================================
    # 8. Research Papers
    # ==========================================================================

    def test_research_papers(self):
        res = self.client.post('/api/assistant/chat', json={'message': 'Where can I find research papers?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'research_papers')
        self.assertIn('Research Papers', data['reply'])
        self.assertTrue(any(a['url'] == '/research' for a in data['actions']))

    # ==========================================================================
    # 9. Profile Management
    # ==========================================================================

    def test_profile_management(self):
        self.login_student()
        res = self.client.post('/api/assistant/chat', json={'message': 'How can I update my profile?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'profile_management')
        self.assertIn('My Profile', data['reply'])
        self.assertTrue(any(a['url'] == '/profile' for a in data['actions']))

    # ==========================================================================
    # 10. Borrow & Return Procedures
    # ==========================================================================

    def test_how_to_borrow(self):
        res = self.client.post('/api/assistant/chat', json={'message': 'How do I request or borrow a book?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'how_to_borrow')
        self.assertIn('Book Catalog', data['reply'])

    def test_how_to_return(self):
        res = self.client.post('/api/assistant/chat', json={'message': 'How can I return a book?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'how_to_return')
        self.assertIn('Circulation Desk', data['reply'])

    # ==========================================================================
    # 11. Contact Librarian & Help
    # ==========================================================================

    def test_contact_librarian(self):
        res = self.client.post('/api/assistant/chat', json={'message': 'How can I contact the librarian?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'contact_librarian')
        self.assertIn('librarian@collegelibrary.edu', data['reply'])

    # ==========================================================================
    # 12. Admin Management Commands
    # ==========================================================================

    def test_admin_pending_requests(self):
        self.login_admin()
        res = self.client.post('/api/assistant/chat', json={'message': 'Show pending borrow requests'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'admin_pending_requests')
        self.assertTrue(any(a['url'] == '/admin/issues' for a in data['actions']))

    def test_admin_add_book(self):
        self.login_admin()
        res = self.client.post('/api/assistant/chat', json={'message': 'How do I add a new book?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'admin_add_book')
        self.assertTrue(any(a['url'] == '/admin/books/add' for a in data['actions']))

    # ==========================================================================
    # 13. Fallback Response & Welcome Dismissal
    # ==========================================================================

    def test_chat_fallback(self):
        res = self.client.post('/api/assistant/chat', json={'message': 'quantum warp drive quantum teleportation xyz123'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'fallback')
        self.assertIn("couldn't understand", data['reply'].lower())

    def test_welcome_dismiss(self):
        with self.client.session_transaction() as sess:
            sess['show_welcome'] = True
        res = self.client.post('/api/welcome/dismiss')
        self.assertEqual(res.status_code, 200)


if __name__ == '__main__':
    unittest.main()
