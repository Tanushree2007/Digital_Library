"""
Book Circulation & Borrowing Management Routes
Handles student borrowing requests, admin issue approvals, return recordings,
overdue state transitions, and atomic database transactions.
"""

from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from database import get_db_connection, log_activity, update_overdue_statuses
from routes.auth import login_required, student_required, admin_required

borrowing_bp = Blueprint('borrowing', __name__)


# ==============================================================================
# REST API Endpoints
# ==============================================================================

@borrowing_bp.route('/api/borrow/request', methods=['POST'])
@student_required
def api_request_borrow():
    """
    POST /api/borrow/request
    Body: {"book_id": <int>, "remarks": <string>}
    Student initiates a book loan hold.
    """
    data = request.get_json() or {}
    book_id = data.get('book_id')
    remarks = data.get('remarks', 'Requested via student portal').strip()

    if not book_id:
        return jsonify({"error": "book_id is required."}), 400

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Check student active account status
    cursor.execute("SELECT status, name FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user or user['status'] != 'active':
        conn.close()
        return jsonify({"error": "Your library account is not active. Borrowing is restricted."}), 403

    # 2. Check maximum allowed active books
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'max_books_per_student'")
    row = cursor.fetchone()
    max_books = int(row['setting_value']) if row else 3

    cursor.execute("""
        SELECT count(*) FROM borrow_records
        WHERE user_id = ? AND status IN ('Issued', 'Overdue', 'Pending')
    """, (user_id,))
    active_count = cursor.fetchone()[0]

    if active_count >= max_books:
        conn.close()
        return jsonify({
            "error": f"Borrowing limit reached. You have {active_count} active or pending loans (Maximum: {max_books})."
        }), 400

    # 3. Check if book exists and has available copies
    cursor.execute("SELECT id, title, available_copies FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()
    if not book:
        conn.close()
        return jsonify({"error": "Book does not exist."}), 404

    if book['available_copies'] < 1:
        conn.close()
        return jsonify({"error": f"'{book['title']}' is currently out of stock."}), 400

    # 4. Check duplicate active requests for the exact same book
    cursor.execute("""
        SELECT id FROM borrow_records
        WHERE user_id = ? AND book_id = ? AND status IN ('Issued', 'Overdue', 'Pending')
    """, (user_id, book_id))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "You already have an active loan or pending request for this book."}), 409

    # 5. Insert Pending Borrow Record
    try:
        cursor.execute("""
            INSERT INTO borrow_records (user_id, book_id, request_date, status, remarks)
            VALUES (?, ?, CURRENT_TIMESTAMP, 'Pending', ?)
        """, (user_id, book_id, remarks))
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()

        log_activity(user_id, "Borrow Request", f"Requested book #{book_id} ('{book['title']}')")

        return jsonify({
            "success": True,
            "message": f"Borrow request for '{book['title']}' submitted! Please await librarian approval.",
            "record_id": record_id
        }), 201
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Failed to submit request: {str(e)}"}), 500


@borrowing_bp.route('/api/borrow/my-records', methods=['GET'])
@student_required
def api_my_records():
    """
    GET /api/borrow/my-records
    Returns all loans and requests for the current student.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.book_id, b.title, b.author, b.isbn, b.category, b.shelf_location,
               r.request_date, r.issue_date, r.due_date, r.return_date, r.status, r.remarks
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        WHERE r.user_id = ?
        ORDER BY r.id DESC
    """, (session['user_id'],))
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({"success": True, "count": len(records), "records": records}), 200


@borrowing_bp.route('/api/borrow/all-records', methods=['GET'])
@admin_required
def api_all_records():
    """
    GET /api/borrow/all-records
    Admin endpoint to view all circulation records across students.
    """
    status_filter = request.args.get('status', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT r.id, r.user_id, u.name as student_name, u.email as student_email, u.student_id,
               r.book_id, b.title as book_title, b.author, b.isbn, b.shelf_location,
               r.request_date, r.issue_date, r.due_date, r.return_date, r.status, r.remarks,
               r.approved_by, adm.name as approver_name
        FROM borrow_records r
        JOIN users u ON r.user_id = u.id
        JOIN books b ON r.book_id = b.id
        LEFT JOIN users adm ON r.approved_by = adm.id
        WHERE 1=1
    """
    params = []
    if status_filter:
        sql += " AND r.status = ?"
        params.append(status_filter)

    sql += " ORDER BY r.id DESC"
    cursor.execute(sql, params)
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({"success": True, "count": len(records), "records": records}), 200


@borrowing_bp.route('/api/borrow/approve/<int:record_id>', methods=['PUT'])
@admin_required
def api_approve_borrow(record_id):
    """
    PUT /api/borrow/approve/<id>
    Admin approves a pending hold. Uses safe database transaction:
    - Sets status = 'Issued'
    - Decrements book available_copies by 1
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, b.title as book_title, b.available_copies, u.name as student_name
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        JOIN users u ON r.user_id = u.id
        WHERE r.id = ?
    """, (record_id,))
    rec = cursor.fetchone()

    if not rec:
        conn.close()
        return jsonify({"error": "Borrow record not found."}), 404

    if rec['status'] != 'Pending':
        conn.close()
        return jsonify({"error": f"Record is already in '{rec['status']}' state."}), 400

    if rec['available_copies'] < 1:
        conn.close()
        return jsonify({"error": f"Cannot approve. '{rec['book_title']}' has no available copies remaining."}), 400

    # Fetch configured borrowing duration in days
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'borrowing_period_days'")
    setting_row = cursor.fetchone()
    loan_days = int(setting_row['setting_value']) if setting_row else 14

    now = datetime.now()
    issue_date = now.strftime("%Y-%m-%d")
    due_date = (now + timedelta(days=loan_days)).strftime("%Y-%m-%d")

    try:
        # Atomic Transaction
        cursor.execute("""
            UPDATE borrow_records
            SET status = 'Issued', issue_date = ?, due_date = ?, approved_by = ?,
                remarks = 'Approved and issued by librarian'
            WHERE id = ?
        """, (issue_date, due_date, session['user_id'], record_id))

        cursor.execute("""
            UPDATE books
            SET available_copies = available_copies - 1
            WHERE id = ? AND available_copies > 0
        """, (rec['book_id'],))

        conn.commit()
        conn.close()

        log_activity(session['user_id'], "Approve Issue", f"Issued '{rec['book_title']}' to {rec['student_name']} (Due: {due_date})")

        return jsonify({
            "success": True,
            "message": f"Successfully issued '{rec['book_title']}' to {rec['student_name']}. Due on {due_date}.",
            "issue_date": issue_date,
            "due_date": due_date
        }), 200
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": f"Transaction failed: {str(e)}"}), 500


@borrowing_bp.route('/api/borrow/reject/<int:record_id>', methods=['PUT'])
@admin_required
def api_reject_borrow(record_id):
    """
    PUT /api/borrow/reject/<id>
    Admin rejects a pending request.
    """
    data = request.get_json() or {}
    remarks = data.get('remarks', 'Request declined by library administration').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM borrow_records WHERE id = ?", (record_id,))
    rec = cursor.fetchone()
    if not rec:
        conn.close()
        return jsonify({"error": "Borrow record not found."}), 404

    if rec['status'] != 'Pending':
        conn.close()
        return jsonify({"error": f"Record is not in Pending status (Current: {rec['status']})."}), 400

    try:
        cursor.execute("""
            UPDATE borrow_records
            SET status = 'Rejected', approved_by = ?, remarks = ?
            WHERE id = ?
        """, (session['user_id'], remarks, record_id))
        conn.commit()
        conn.close()

        log_activity(session['user_id'], "Reject Request", f"Rejected borrow request #{record_id}")

        return jsonify({"success": True, "message": "Borrow request rejected successfully."}), 200
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Failed to reject request: {str(e)}"}), 500


@borrowing_bp.route('/api/borrow/return/<int:record_id>', methods=['PUT'])
@admin_required
def api_return_borrow(record_id):
    """
    PUT /api/borrow/return/<id>
    Admin records the return of an issued or overdue book.
    - Sets status = 'Returned'
    - Increments book available_copies by 1
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, b.title as book_title, b.total_copies, u.name as student_name
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        JOIN users u ON r.user_id = u.id
        WHERE r.id = ?
    """, (record_id,))
    rec = cursor.fetchone()

    if not rec:
        conn.close()
        return jsonify({"error": "Borrow record not found."}), 404

    if rec['status'] not in ['Issued', 'Overdue']:
        conn.close()
        return jsonify({"error": f"Cannot return. Record status is '{rec['status']}'."}), 400

    return_date = datetime.now().strftime("%Y-%m-%d")

    try:
        # Atomic Transaction
        cursor.execute("""
            UPDATE borrow_records
            SET status = 'Returned', return_date = ?, remarks = 'Returned to inventory in good condition'
            WHERE id = ?
        """, (return_date, record_id))

        cursor.execute("""
            UPDATE books
            SET available_copies = MIN(total_copies, available_copies + 1)
            WHERE id = ?
        """, (rec['book_id'],))

        conn.commit()
        conn.close()

        log_activity(session['user_id'], "Return Book", f"Recorded return of '{rec['book_title']}' from {rec['student_name']}")

        return jsonify({
            "success": True,
            "message": f"'{rec['book_title']}' successfully returned to inventory.",
            "return_date": return_date
        }), 200
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": f"Transaction failed: {str(e)}"}), 500


# ==============================================================================
# HTML Page Controllers
# ==============================================================================

@borrowing_bp.route('/my-books')
@student_required
def my_books():
    """
    Student page displaying currently borrowed books and due dates.
    """
    update_overdue_statuses()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.book_id, b.title, b.author, b.isbn, b.category, b.shelf_location,
               r.request_date, r.issue_date, r.due_date, r.status
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        WHERE r.user_id = ? AND r.status IN ('Issued', 'Overdue')
        ORDER BY r.due_date ASC
    """, (session['user_id'],))
    books = cursor.fetchall()
    conn.close()

    return render_template('my_books.html', books=books)


@borrowing_bp.route('/borrow-history')
@student_required
def borrow_history():
    """
    Student page displaying previous borrowing history ledger.
    """
    update_overdue_statuses()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.book_id, b.title, b.author, b.isbn, b.category,
               r.request_date, r.issue_date, r.due_date, r.return_date, r.status, r.remarks
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        WHERE r.user_id = ?
        ORDER BY r.id DESC
    """, (session['user_id'],))
    records = cursor.fetchall()
    conn.close()

    return render_template('borrow_history.html', records=records)


@borrowing_bp.route('/admin/issues')
@admin_required
def manage_issues():
    """
    Librarian circulation desk: Review pending requests and manage active loans.
    """
    update_overdue_statuses()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Pending Requests
    cursor.execute("""
        SELECT r.id, r.user_id, u.name as student_name, u.email, u.student_id,
               r.book_id, b.title as book_title, b.available_copies, b.shelf_location,
               r.request_date, r.remarks
        FROM borrow_records r
        JOIN users u ON r.user_id = u.id
        JOIN books b ON r.book_id = b.id
        WHERE r.status = 'Pending'
        ORDER BY r.id ASC
    """)
    pending_requests = cursor.fetchall()

    # Active Loans (Issued & Overdue)
    cursor.execute("""
        SELECT r.id, r.user_id, u.name as student_name, u.email, u.student_id,
               r.book_id, b.title as book_title, b.author,
               r.issue_date, r.due_date, r.status
        FROM borrow_records r
        JOIN users u ON r.user_id = u.id
        JOIN books b ON r.book_id = b.id
        WHERE r.status IN ('Issued', 'Overdue')
        ORDER BY r.due_date ASC
    """)
    active_loans = cursor.fetchall()

    # Data for manual issue modal
    cursor.execute("SELECT id, name, email, student_id FROM users WHERE role = 'student' AND status = 'active' ORDER BY name ASC")
    all_students = cursor.fetchall()

    cursor.execute("SELECT id, title, available_copies FROM books WHERE available_copies > 0 ORDER BY title ASC")
    available_books = cursor.fetchall()

    conn.close()

    return render_template(
        'manage_issues.html',
        pending_requests=pending_requests,
        active_loans=active_loans,
        all_students=all_students,
        available_books=available_books
    )


@borrowing_bp.route('/admin/issues/manual', methods=['POST'])
@admin_required
def manual_issue():
    """
    Direct issue of a book to a student performed at circulation counter.
    """
    user_id = request.form.get('user_id')
    book_id = request.form.get('book_id')
    loan_days = int(request.form.get('borrow_days', 14))
    remarks = request.form.get('remarks', 'Direct counter issue by librarian').strip()

    if not user_id or not book_id:
        flash("Both student and book must be selected.", "danger")
        return redirect(url_for('borrowing.manage_issues'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, available_copies FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()
    if not book or book['available_copies'] < 1:
        conn.close()
        flash("Selected book has no available copies to issue.", "danger")
        return redirect(url_for('borrowing.manage_issues'))

    cursor.execute("SELECT id, name, status FROM users WHERE id = ?", (user_id,))
    student = cursor.fetchone()
    if not student or student['status'] != 'active':
        conn.close()
        flash("Student account is not active.", "danger")
        return redirect(url_for('borrowing.manage_issues'))

    now = datetime.now()
    issue_date = now.strftime("%Y-%m-%d")
    due_date = (now + timedelta(days=loan_days)).strftime("%Y-%m-%d")

    try:
        cursor.execute("""
            INSERT INTO borrow_records (
                user_id, book_id, request_date, issue_date, due_date, status, approved_by, remarks
            ) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, 'Issued', ?, ?)
        """, (user_id, book_id, issue_date, due_date, session['user_id'], remarks))

        cursor.execute("""
            UPDATE books SET available_copies = available_copies - 1
            WHERE id = ? AND available_copies > 0
        """, (book_id,))

        conn.commit()
        conn.close()

        log_activity(session['user_id'], "Manual Book Issue", f"Issued '{book['title']}' to {student['name']}")
        flash(f"Successfully issued '{book['title']}' to {student['name']}. Due: {due_date}", "success")
    except Exception as e:
        conn.rollback()
        conn.close()
        flash(f"Error issuing book: {str(e)}", "danger")

    return redirect(url_for('borrowing.manage_issues'))
