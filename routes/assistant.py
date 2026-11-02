"""
Smart AI Library Assistant ("Libra") Routes & Intent Engine
Provides context-aware conversational guidance, live database status queries,
role-based assistance (Student vs Admin), and navigation recommendations.
"""

import re
from datetime import datetime
from flask import Blueprint, request, jsonify, session, url_for
from database import get_db_connection, update_overdue_statuses

assistant_bp = Blueprint('assistant', __name__)


# ==============================================================================
# Helper Functions: Intent Matching & Live DB Lookups
# ==============================================================================

def normalize_text(text: str) -> str:
    """Lowercases, strips, and cleans input text."""
    if not text:
        return ""
    text = text.lower().strip()
    return re.sub(r'[^\w\s]', ' ', text)


def get_greeting(user_name: str = "") -> str:
    """Generates a warm, time-of-day greeting."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        period = "Good morning"
    elif 12 <= hour < 17:
        period = "Good afternoon"
    elif 17 <= hour < 22:
        period = "Good evening"
    else:
        period = "Hello"

    if user_name:
        return f"{period}, {user_name}! Ready to explore something new?"
    return f"{period}! Welcome to Your Digital Library."


# ==============================================================================
# Intent Processor
# ==============================================================================

def process_assistant_query(query: str, user_id: int = None, role: str = None, user_name: str = ""):
    """
    Evaluates user intent and executes live database queries where applicable.
    Returns: {"reply": str, "actions": list[dict], "intent": str}
    """
    clean_q = normalize_text(query)
    words = set(clean_q.split())
    role = role or "guest"

    update_overdue_statuses()
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # ----------------------------------------------------------------------
        # 1. Greetings & Identity
        # ----------------------------------------------------------------------
        if any(w in words for w in ['hello', 'hi', 'hey', 'greetings', 'hola']) or 'who are you' in clean_q or 'what can you do' in clean_q:
            time_greet = get_greeting(user_name)
            reply = (
                f"{time_greet}\n\n"
                "I'm **Libra**, your personal Library Assistant. I can help you navigate the library, "
                "find books, explore research papers, track your active loans, and check due dates."
            )
            actions = [
                {"label": "Open Book Catalog", "url": "/books", "icon": "bi-book"},
                {"label": "Explore Research Papers", "url": "/research", "icon": "bi-file-earmark-text"}
            ]
            if role == "student":
                actions.insert(0, {"label": "My Borrowed Books", "url": "/my-books", "icon": "bi-journal-check"})
            elif role == "admin":
                actions.insert(0, {"label": "Admin Console", "url": "/admin/dashboard", "icon": "bi-speedometer2"})
            return {"reply": reply, "actions": actions, "intent": "greeting"}

        # ----------------------------------------------------------------------
        # 2. Admin Pending Requests (Check early for admin queries)
        # ----------------------------------------------------------------------
        if role == "admin" and ('pending' in clean_q or ('request' in clean_q and ('borrow' in clean_q or 'issue' in clean_q))):
            cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Pending'")
            pending_cnt = cursor.fetchone()[0]
            reply = f"You have **{pending_cnt} pending borrowing request(s)** awaiting review in the Circulation Desk."
            actions = [{"label": "Open Circulation Desk", "url": "/admin/issues", "icon": "bi-arrow-left-right"}]
            return {"reply": reply, "actions": actions, "intent": "admin_pending_requests"}

        # ----------------------------------------------------------------------
        # 3. Specific Book Title Search / Lookup in Catalog
        # ----------------------------------------------------------------------
        # If user asks: "Do you have <title>?", "Is <title> available?", or mentions a title
        cursor.execute("SELECT id, title, author, available_copies, total_copies, shelf_location FROM books")
        all_books = cursor.fetchall()
        matched_book = None
        for b in all_books:
            b_title_norm = normalize_text(b['title'])
            main_title = normalize_text(b['title'].split(':')[0].split('(')[0])
            if (len(main_title) >= 4 and main_title in clean_q) or (len(b_title_norm) >= 6 and b_title_norm in clean_q):
                matched_book = b
                break

        if matched_book:
            b = matched_book
            status_txt = (
                f"**{b['available_copies']} of {b['total_copies']} copy/copies available** (Location: {b['shelf_location'] or 'Main Stacks'})."
                if b['available_copies'] > 0 else
                "currently **Out of Stock** (all copies issued)."
            )
            reply = (
                f"Yes! We have **\"{b['title']}\"** by {b['author']}.\n\n"
                f"Status: {status_txt}"
            )
            actions = [
                {"label": f"View \"{b['title'][:25]}...\"", "url": f"/books/{b['id']}", "icon": "bi-info-circle"},
                {"label": "Open Catalog", "url": "/books", "icon": "bi-book"}
            ]
            return {"reply": reply, "actions": actions, "intent": "book_specific_lookup"}

        # If user specifically asked "do you have..." or "is ... available" for a book not found
        if ('do you have' in clean_q or 'is' in clean_q and 'available' in clean_q and 'book' not in clean_q) and len(clean_q) > 12:
            reply = (
                "I searched our library catalog, but could not find a title matching that query.\n\n"
                "You can browse the full catalog or contact the librarian to recommend a new book acquisition."
            )
            actions = [
                {"label": "Open Book Catalog", "url": "/books", "icon": "bi-book"},
                {"label": "Contact Librarian", "url": "/about#hours", "icon": "bi-envelope"}
            ]
            return {"reply": reply, "actions": actions, "intent": "book_specific_lookup"}

        # ----------------------------------------------------------------------
        # 4. Student Active Borrowed Books ("How many books have I borrowed?", "Which books are issued to me?")
        # ----------------------------------------------------------------------
        if ('how many books' in clean_q and ('borrow' in clean_q or 'have i' in clean_q or 'my' in clean_q)) or \
           ('borrowed' in clean_q and ('book' in clean_q or 'my' in clean_q or 'what' in clean_q or 'which' in clean_q or 'see' in clean_q or 'check' in clean_q)) or \
           ('issued' in clean_q and ('to me' in clean_q or 'my' in clean_q or 'currently' in clean_q)):
            if role != "student" or not user_id:
                if role == "admin":
                    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Issued'")
                    issued_total = cursor.fetchone()[0]
                    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Overdue'")
                    overdue_total = cursor.fetchone()[0]
                    reply = (
                        f"Across the library, there are currently **{issued_total} active issued book(s)** "
                        f"and **{overdue_total} overdue book(s)** checked out to students."
                    )
                    actions = [{"label": "Open Circulation Desk", "url": "/admin/issues", "icon": "bi-arrow-left-right"}]
                    return {"reply": reply, "actions": actions, "intent": "admin_issued_stats"}
                else:
                    reply = "You can check your borrowed books once you sign in to your student account."
                    actions = [{"label": "Sign In to Account", "url": "/login", "icon": "bi-box-arrow-in-right"}]
                    return {"reply": reply, "actions": actions, "intent": "auth_required"}

            # Query student's active loans
            cursor.execute("""
                SELECT b.title, b.author, r.due_date, r.status
                FROM borrow_records r
                JOIN books b ON r.book_id = b.id
                WHERE r.user_id = ? AND r.status IN ('Issued', 'Overdue')
                ORDER BY r.due_date ASC
            """, (user_id,))
            active_loans = cursor.fetchall()

            cursor.execute("SELECT count(*) FROM borrow_records WHERE user_id = ?", (user_id,))
            lifetime_count = cursor.fetchone()[0]

            if active_loans:
                book_items = []
                for idx, al in enumerate(active_loans, 1):
                    overdue_tag = " ⚠️ **(OVERDUE)**" if al['status'] == 'Overdue' else ""
                    book_items.append(f"{idx}. **{al['title']}** (Due: {al['due_date']}){overdue_tag}")
                
                reply = (
                    f"You currently have **{len(active_loans)} active book loan(s)** checked out "
                    f"(and {lifetime_count} total lifetime requests):\n\n" +
                    "\n".join(book_items) +
                    "\n\nYou can check your borrowed books in the My Borrowed Books section. Click below to open it."
                )
            else:
                reply = (
                    "You currently have **0 active book loans**.\n\n"
                    "You can explore our catalog anytime to find and request textbooks!"
                )

            actions = [
                {"label": "Open My Borrowed Books", "url": "/my-books", "icon": "bi-journal-check"},
                {"label": "Browse Book Catalog", "url": "/books", "icon": "bi-book"}
            ]
            return {"reply": reply, "actions": actions, "intent": "student_active_loans"}

        # ----------------------------------------------------------------------
        # 5. Overdue Books & Next Due Date ("Do I have overdue books?", "When is my return date?")
        # ----------------------------------------------------------------------
        if 'overdue' in clean_q or ('due' in clean_q and ('when' in clean_q or 'date' in clean_q or 'next' in clean_q or 'check' in clean_q)):
            if role == "admin":
                cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Overdue'")
                overdue_count = cursor.fetchone()[0]
                reply = (
                    f"There are currently **{overdue_count} overdue book(s)** in the library circulation system.\n\n"
                    "You can view the full list and contact students or process returns from the circulation desk."
                )
                actions = [
                    {"label": "Open Circulation Desk", "url": "/admin/issues", "icon": "bi-arrow-left-right"},
                    {"label": "View Reports & Stats", "url": "/admin/reports", "icon": "bi-graph-up"}
                ]
                return {"reply": reply, "actions": actions, "intent": "admin_overdue_check"}

            if role != "student" or not user_id:
                reply = "Please sign in to check your active loans and overdue book statuses."
                actions = [{"label": "Sign In", "url": "/login", "icon": "bi-box-arrow-in-right"}]
                return {"reply": reply, "actions": actions, "intent": "auth_required"}

            cursor.execute("""
                SELECT b.title, r.due_date, r.status
                FROM borrow_records r
                JOIN books b ON r.book_id = b.id
                WHERE r.user_id = ? AND r.status = 'Overdue'
            """, (user_id,))
            overdue_list = cursor.fetchall()

            cursor.execute("""
                SELECT b.title, r.due_date
                FROM borrow_records r
                JOIN books b ON r.book_id = b.id
                WHERE r.user_id = ? AND r.status = 'Issued'
                ORDER BY r.due_date ASC LIMIT 1
            """, (user_id,))
            next_due = cursor.fetchone()

            if overdue_list:
                items = [f"- **{o['title']}** (Was due: {o['due_date']})" for o in overdue_list]
                reply = (
                    f"⚠️ **Attention:** You have **{len(overdue_list)} overdue book(s)**:\n\n" +
                    "\n".join(items) +
                    "\n\nPlease return them to the library counter as soon as possible."
                )
            elif next_due:
                reply = (
                    f"Great news! You have **no overdue books**.\n\n"
                    f"Your next return date is **{next_due['due_date']}** for **\"{next_due['title']}\"**."
                )
            else:
                reply = (
                    "You currently have no books checked out, so there are no upcoming due dates or overdue records!"
                )

            actions = [
                {"label": "Open My Borrowed Books", "url": "/my-books", "icon": "bi-journal-check"},
                {"label": "View Borrowing History", "url": "/borrow-history", "icon": "bi-clock-history"}
            ]
            return {"reply": reply, "actions": actions, "intent": "student_due_dates"}

        # ----------------------------------------------------------------------
        # 6. Borrowing History ("Where can I see my borrowing history?")
        # ----------------------------------------------------------------------
        if 'history' in clean_q or ('past' in clean_q and 'book' in clean_q) or ('previous' in clean_q and ('book' in clean_q or 'transaction' in clean_q)):
            if role == "student" and user_id:
                cursor.execute("SELECT count(*) FROM borrow_records WHERE user_id = ? AND status = 'Returned'", (user_id,))
                returned_cnt = cursor.fetchone()[0]
                reply = (
                    f"You have completed **{returned_cnt} return(s)** so far.\n\n"
                    "Open your Borrowing History to view your previous and current book transactions."
                )
                actions = [
                    {"label": "View Borrowing History", "url": "/borrow-history", "icon": "bi-clock-history"},
                    {"label": "Open My Borrowed Books", "url": "/my-books", "icon": "bi-journal-check"}
                ]
                return {"reply": reply, "actions": actions, "intent": "borrowing_history"}
            elif role == "admin":
                reply = "You can view complete circulation history across all students from the reports or member details sections."
                actions = [
                    {"label": "Circulation Desk", "url": "/admin/issues", "icon": "bi-arrow-left-right"},
                    {"label": "Library Reports", "url": "/admin/reports", "icon": "bi-graph-up"}
                ]
                return {"reply": reply, "actions": actions, "intent": "admin_history"}
            else:
                reply = "Please sign in to view your complete borrowing history."
                actions = [{"label": "Sign In", "url": "/login", "icon": "bi-box-arrow-in-right"}]
                return {"reply": reply, "actions": actions, "intent": "auth_required"}

        # ----------------------------------------------------------------------
        # 7. Book Availability & Catalog ("How can I check whether a book is available?", "How many books are available?")
        # ----------------------------------------------------------------------
        if ('available' in clean_q and ('book' in clean_q or 'how many' in clean_q or 'check' in clean_q or 'whether' in clean_q or 'status' in clean_q)) or \
           ('stock' in clean_q):
            cursor.execute("SELECT count(*), COALESCE(SUM(available_copies), 0), COALESCE(SUM(total_copies), 0) FROM books")
            row = cursor.fetchone()
            total_titles = row[0]
            avail_copies = row[1]
            total_copies = row[2]

            reply = (
                f"The library currently holds **{total_titles} book titles** with a total of **{total_copies} physical copies**.\n\n"
                f"Currently, **{avail_copies} copies are available** for immediate checkout.\n\n"
                "Open the Book Catalog and check the availability status displayed for each book."
            )
            actions = [
                {"label": "Check Book Availability", "url": "/books?availability=available", "icon": "bi-check-circle"},
                {"label": "Open Book Catalog", "url": "/books", "icon": "bi-book"}
            ]
            return {"reply": reply, "actions": actions, "intent": "book_availability"}

        # ----------------------------------------------------------------------
        # 8. Book Search & Catalog ("I want to search for a book", "Where can I find books?")
        # ----------------------------------------------------------------------
        if ('search' in clean_q and 'book' in clean_q) or ('find' in clean_q and 'book' in clean_q) or \
           ('catalog' in clean_q) or ('browse' in clean_q and 'book' in clean_q) or ('where can i find books' in clean_q):
            reply = "Go to the Book Catalog to search by title, author, or category."
            actions = [
                {"label": "Open Book Catalog", "url": "/books", "icon": "bi-book"},
                {"label": "Explore Categories", "url": "/books#categories", "icon": "bi-tags"}
            ]
            return {"reply": reply, "actions": actions, "intent": "book_search_guidance"}

        # ----------------------------------------------------------------------
        # 9. Research Papers ("Where can I find research papers?", "How many research papers?")
        # ----------------------------------------------------------------------
        if 'research' in clean_q or 'paper' in clean_q or 'journal' in clean_q or 'abstract' in clean_q:
            cursor.execute("SELECT count(*) FROM research_papers")
            paper_cnt = cursor.fetchone()[0]
            cursor.execute("SELECT DISTINCT subject FROM research_papers LIMIT 4")
            sample_subjs = [r['subject'] for r in cursor.fetchall() if r['subject']]

            subj_text = f" across subjects like {', '.join(sample_subjs)}" if sample_subjs else ""
            reply = (
                f"There are currently **{paper_cnt} academic research papers** available{subj_text}.\n\n"
                "Visit the Research Papers section to explore academic papers, read abstracts, and download full-text PDFs."
            )
            actions = [
                {"label": "Explore Research Papers", "url": "/research", "icon": "bi-file-earmark-pdf"}
            ]
            if role == "admin":
                actions.append({"label": "Add Research Paper", "url": "/admin/research/add", "icon": "bi-cloud-arrow-up"})
            return {"reply": reply, "actions": actions, "intent": "research_papers"}

        # ----------------------------------------------------------------------
        # 10. Profile & Account Management ("How can I update my profile?")
        # ----------------------------------------------------------------------
        if 'profile' in clean_q or ('update' in clean_q and ('account' in clean_q or 'password' in clean_q or 'phone' in clean_q or 'department' in clean_q or 'name' in clean_q)):
            if not user_id:
                reply = "Please sign in to access and update your profile."
                actions = [{"label": "Sign In", "url": "/login", "icon": "bi-box-arrow-in-right"}]
            else:
                reply = "You can manage your account information, update your phone/department, and change your password from the My Profile section."
                actions = [{"label": "Open My Profile", "url": "/profile", "icon": "bi-person-circle"}]
            return {"reply": reply, "actions": actions, "intent": "profile_management"}

        # ----------------------------------------------------------------------
        # 11. How to Request / Borrow / Issue a Book
        # ----------------------------------------------------------------------
        if ('how' in words and ('request' in clean_q or 'borrow' in clean_q or 'issue' in clean_q)) or \
           ('request a book' in clean_q) or ('borrow a book' in clean_q) or ('how to borrow' in clean_q):
            if role == "admin":
                reply = (
                    "As an administrator, you can:\n"
                    "1. Review and approve student requests from the **Circulation Desk**.\n"
                    "2. Use **Manual Direct Issue** to immediately issue any book to an active student."
                )
                actions = [
                    {"label": "Open Circulation Desk", "url": "/admin/issues", "icon": "bi-arrow-left-right"},
                    {"label": "Book Inventory", "url": "/admin/books", "icon": "bi-book"}
                ]
                return {"reply": reply, "actions": actions, "intent": "admin_how_to_issue"}

            reply = (
                "To borrow a book as a student:\n"
                "1. Open the **Book Catalog**.\n"
                "2. Find an available book and click **Borrow**.\n"
                "3. Your hold request will be submitted to the librarian for approval.\n"
                "4. Once approved, you can pick up the book for a **14-day borrowing period**!"
            )
            actions = [
                {"label": "Open Book Catalog", "url": "/books", "icon": "bi-book"},
                {"label": "View Active Loans", "url": "/my-books", "icon": "bi-journal-check"}
            ]
            return {"reply": reply, "actions": actions, "intent": "how_to_borrow"}

        # ----------------------------------------------------------------------
        # 12. How to Return a Book
        # ----------------------------------------------------------------------
        if ('how' in words and 'return' in clean_q) or ('return a book' in clean_q) or ('return procedure' in clean_q):
            if role == "admin":
                reply = (
                    "To record a returned book:\n"
                    "1. Go to **Circulation & Issues** (`/admin/issues`).\n"
                    "2. Find the active loan under **Active Book Loans**.\n"
                    "3. Click **Record Return**. The book's available stock will automatically increment by 1."
                )
                actions = [{"label": "Circulation Desk", "url": "/admin/issues", "icon": "bi-arrow-left-right"}]
                return {"reply": reply, "actions": actions, "intent": "admin_how_to_return"}

            reply = (
                "To return a book:\n"
                "1. Bring the physical book to the **Library Circulation Desk** (Building B, Level 2).\n"
                "2. The librarian will scan and check in the volume.\n"
                "3. Your account record will immediately update to **Returned** and appear in your Borrowing History!"
            )
            actions = [
                {"label": "Open My Borrowed Books", "url": "/my-books", "icon": "bi-journal-check"},
                {"label": "View Library Hours", "url": "/about#hours", "icon": "bi-clock-history"}
            ]
            return {"reply": reply, "actions": actions, "intent": "how_to_return"}

        # ----------------------------------------------------------------------
        # 13. Contact Librarian / Helpdesk / Operating Hours
        # ----------------------------------------------------------------------
        if 'contact' in clean_q or 'librarian' in clean_q or 'help' in words or 'hours' in clean_q or 'phone' in clean_q or 'email' in clean_q:
            reply = (
                "**Library Helpdesk & Reference Services:**\n\n"
                "📍 **Location:** Central Campus Library, Building B, Level 2\n"
                "📧 **Email:** librarian@collegelibrary.edu\n"
                "📞 **Phone:** +1 (555) 019-2834\n"
                "⏰ **Hours:** Mon – Fri: 8:00 AM – 9:00 PM | Sat: 9:00 AM – 5:00 PM\n"
                "🌐 **Online Catalog:** Available 24/7"
            )
            actions = [
                {"label": "About Library & Hours", "url": "/about#hours", "icon": "bi-info-circle"},
                {"label": "Circulation Policy", "url": "/about#circulation-policy", "icon": "bi-journal-text"}
            ]
            return {"reply": reply, "actions": actions, "intent": "contact_librarian"}

        # ----------------------------------------------------------------------
        # 14. Admin Actions: Add Book, Member Management, Reports
        # ----------------------------------------------------------------------
        if role == "admin":
            if ('add' in clean_q and 'book' in clean_q) or ('new book' in clean_q):
                reply = "You can register a new book in the library catalog with ISBN, copies, and shelf coordinates."
                actions = [
                    {"label": "Add New Book", "url": "/admin/books/add", "icon": "bi-plus-circle"},
                    {"label": "Book Inventory", "url": "/admin/books", "icon": "bi-book"}
                ]
                return {"reply": reply, "actions": actions, "intent": "admin_add_book"}

            if 'member' in clean_q or 'student' in clean_q or 'roster' in clean_q:
                cursor.execute("SELECT count(*) FROM users WHERE role = 'student'")
                m_cnt = cursor.fetchone()[0]
                reply = f"There are currently **{m_cnt} registered student members**. You can inspect their loan history or activate/deactivate accounts."
                actions = [{"label": "Manage Members", "url": "/admin/members", "icon": "bi-people"}]
                return {"reply": reply, "actions": actions, "intent": "admin_members"}

            if 'report' in clean_q or 'stat' in clean_q or 'analytics' in clean_q:
                reply = "You can view discipline breakdown, most borrowed titles, and printable circulation metrics in Reports."
                actions = [
                    {"label": "Reports & Analytics", "url": "/admin/reports", "icon": "bi-graph-up"},
                    {"label": "Admin Dashboard", "url": "/admin/dashboard", "icon": "bi-speedometer2"}
                ]
                return {"reply": reply, "actions": actions, "intent": "admin_reports"}

        # ----------------------------------------------------------------------
        # 15. Fallback Polite Response
        # ----------------------------------------------------------------------
        reply = (
            "I'm sorry, I couldn't understand that request. "
            "You can ask me about books, borrowing, research papers, or library navigation."
        )
        actions = [
            {"label": "Open Book Catalog", "url": "/books", "icon": "bi-book"},
            {"label": "Explore Research Papers", "url": "/research", "icon": "bi-file-earmark-pdf"}
        ]
        if role == "student":
            actions.append({"label": "My Borrowed Books", "url": "/my-books", "icon": "bi-journal-check"})
        elif role == "admin":
            actions.append({"label": "Admin Dashboard", "url": "/admin/dashboard", "icon": "bi-speedometer2"})

        return {"reply": reply, "actions": actions, "intent": "fallback"}

    finally:
        conn.close()


# ==============================================================================
# REST API Endpoints
# ==============================================================================

@assistant_bp.route('/api/assistant/chat', methods=['POST'])
def api_assistant_chat():
    """
    POST /api/assistant/chat
    Body: {"message": "Where can I find books?"}
    """
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()

    if not user_message:
        return jsonify({"error": "Message is required."}), 400

    user_id = session.get('user_id')
    role = session.get('role', 'guest')
    user_name = session.get('name', '')

    result = process_assistant_query(
        query=user_message,
        user_id=user_id,
        role=role,
        user_name=user_name
    )

    return jsonify({
        "success": True,
        "reply": result["reply"],
        "actions": result["actions"],
        "intent": result["intent"]
    }), 200


@assistant_bp.route('/api/assistant/suggestions', methods=['GET'])
def api_assistant_suggestions():
    """
    GET /api/assistant/suggestions
    Returns contextual suggested questions based on user role.
    """
    role = session.get('role', 'guest')

    if role == 'admin':
        suggestions = [
            "Show pending borrow requests",
            "How many books are overdue?",
            "How do I add a new book?",
            "Show library statistics",
            "View registered members",
            "How do I return a book?"
        ]
    elif role == 'student':
        suggestions = [
            "Where can I find books?",
            "How many books have I borrowed?",
            "Show my overdue books",
            "Find research papers",
            "How do I return a book?",
            "Where can I see my borrowing history?",
            "How can I contact the librarian?"
        ]
    else:
        suggestions = [
            "Where can I find books?",
            "How do I check book availability?",
            "Find research papers",
            "How do I borrow a book?",
            "How can I contact the librarian?"
        ]

    return jsonify({
        "success": True,
        "role": role,
        "suggestions": suggestions
    }), 200
