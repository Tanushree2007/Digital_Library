"""
Dashboards, Public Landing, and Analytical Reports Routes
Computes real-time statistics directly from database records for students and administrators.
"""

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, render_template, session
from database import get_db_connection, update_overdue_statuses
from routes.auth import student_required, admin_required

dashboard_bp = Blueprint('dashboard', __name__)


# ==============================================================================
# REST API Endpoints
# ==============================================================================

@dashboard_bp.route('/api/dashboard/student', methods=['GET'])
@student_required
def api_student_dashboard():
    """
    GET /api/dashboard/student
    Returns live metrics and borrowing status for the logged-in student.
    """
    update_overdue_statuses()
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    soon_str = (now + timedelta(days=3)).strftime("%Y-%m-%d")

    # Counts
    cursor.execute("SELECT count(*) FROM borrow_records WHERE user_id = ? AND status = 'Issued'", (user_id,))
    issued_count = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM borrow_records WHERE user_id = ? AND status = 'Pending'", (user_id,))
    pending_count = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM borrow_records WHERE user_id = ? AND status = 'Overdue'", (user_id,))
    overdue_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT count(*) FROM borrow_records
        WHERE user_id = ? AND status = 'Issued' AND due_date >= ? AND due_date <= ?
    """, (user_id, today_str, soon_str))
    due_soon_count = cursor.fetchone()[0]

    # Active loans
    cursor.execute("""
        SELECT r.id, b.title, b.author, r.issue_date, r.due_date, r.status
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        WHERE r.user_id = ? AND r.status IN ('Issued', 'Overdue')
        ORDER BY r.due_date ASC
    """, (user_id,))
    active_loans = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        "success": True,
        "metrics": {
            "issued_count": issued_count,
            "pending_count": pending_count,
            "overdue_count": overdue_count,
            "due_soon_count": due_soon_count
        },
        "active_loans": active_loans
    }), 200


@dashboard_bp.route('/api/dashboard/admin', methods=['GET'])
@admin_required
def api_admin_dashboard():
    """
    GET /api/dashboard/admin
    Returns all 8 library summary metrics calculated from actual database records.
    """
    update_overdue_statuses()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total books
    cursor.execute("SELECT count(*) FROM books")
    total_books = cursor.fetchone()[0]

    # Total available copies
    cursor.execute("SELECT COALESCE(SUM(available_copies), 0) FROM books")
    available_copies = cursor.fetchone()[0]

    # Total registered members (students)
    cursor.execute("SELECT count(*) FROM users WHERE role = 'student'")
    total_members = cursor.fetchone()[0]

    # Total research papers
    cursor.execute("SELECT count(*) FROM research_papers")
    total_papers = cursor.fetchone()[0]

    # Currently issued books
    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Issued'")
    issued_books = cursor.fetchone()[0]

    # Pending requests
    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Pending'")
    pending_requests = cursor.fetchone()[0]

    # Overdue books
    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Overdue'")
    overdue_books = cursor.fetchone()[0]

    # Returned books
    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Returned'")
    returned_books = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        "success": True,
        "statistics": {
            "total_books": total_books,
            "total_available_copies": available_copies,
            "total_registered_members": total_members,
            "total_research_papers": total_papers,
            "currently_issued_books": issued_books,
            "pending_borrowing_requests": pending_requests,
            "overdue_books": overdue_books,
            "returned_books": returned_books
        }
    }), 200


@dashboard_bp.route('/api/activity-logs', methods=['GET'])
@admin_required
def api_activity_logs():
    """
    GET /api/activity-logs
    Returns system audit activity logs.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.action, a.description, a.created_at, COALESCE(u.name, 'System') as user_name
        FROM activity_logs a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.id DESC LIMIT 20
    """)
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({"success": True, "count": len(logs), "logs": logs}), 200


@dashboard_bp.route('/api/settings', methods=['GET'])
@admin_required
def api_get_settings():
    """
    GET /api/settings
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_key, setting_value FROM settings")
    settings_dict = {row['setting_key']: row['setting_value'] for row in cursor.fetchall()}
    conn.close()

    return jsonify({"success": True, "settings": settings_dict}), 200


@dashboard_bp.route('/api/settings', methods=['PUT'])
@admin_required
def api_update_settings():
    """
    PUT /api/settings
    Body: {"borrowing_period_days": "14", "max_books_per_student": "3", ...}
    """
    from flask import request
    data = request.get_json() or {}
    conn = get_db_connection()
    cursor = conn.cursor()

    for key, val in data.items():
        cursor.execute("""
            INSERT INTO settings (setting_key, setting_value)
            VALUES (?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
        """, (key, str(val)))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Settings updated successfully."}), 200


# ==============================================================================
# HTML Page Controllers
# ==============================================================================

@dashboard_bp.route('/')
def index():
    """
    Public landing page with live dynamic statistics, featured books, and latest research papers.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Calculate real statistics
    cursor.execute("SELECT count(*) FROM books")
    total_books = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(available_copies), 0) FROM books")
    available_copies = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM users WHERE role = 'student'")
    total_members = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM research_papers")
    total_papers = cursor.fetchone()[0]

    stats = {
        "total_books": total_books,
        "available_copies": available_copies,
        "total_members": total_members,
        "total_papers": total_papers
    }

    # Featured books (First 8 books)
    cursor.execute("SELECT * FROM books ORDER BY available_copies DESC, id ASC LIMIT 8")
    featured_books = cursor.fetchall()

    # Latest research papers (First 4 papers)
    cursor.execute("SELECT * FROM research_papers ORDER BY publication_year DESC, id DESC LIMIT 4")
    latest_papers = cursor.fetchall()

    conn.close()

    return render_template(
        'index.html',
        stats=stats,
        featured_books=featured_books,
        latest_papers=latest_papers
    )


@dashboard_bp.route('/about')
def about():
    """
    Public about page.
    """
    return render_template('about.html')


@dashboard_bp.route('/dashboard')
@student_required
def student_dashboard():
    """
    Student cockpit with personal active loans and borrowing metrics.
    """
    update_overdue_statuses()
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    # User details
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    # Metrics
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    soon_str = (now + timedelta(days=3)).strftime("%Y-%m-%d")

    cursor.execute("SELECT count(*) FROM borrow_records WHERE user_id = ? AND status = 'Issued'", (user_id,))
    issued_count = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM borrow_records WHERE user_id = ? AND status = 'Pending'", (user_id,))
    pending_count = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM borrow_records WHERE user_id = ? AND status = 'Overdue'", (user_id,))
    overdue_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT count(*) FROM borrow_records
        WHERE user_id = ? AND status = 'Issued' AND due_date >= ? AND due_date <= ?
    """, (user_id, today_str, soon_str))
    due_soon_count = cursor.fetchone()[0]

    metrics = {
        "issued_count": issued_count,
        "pending_count": pending_count,
        "overdue_count": overdue_count,
        "due_soon_count": due_soon_count
    }

    # Active loans
    cursor.execute("""
        SELECT r.id, b.title, b.author, r.issue_date, r.due_date, r.status
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        WHERE r.user_id = ? AND r.status IN ('Issued', 'Overdue')
        ORDER BY r.due_date ASC
    """, (user_id,))
    active_loans = cursor.fetchall()

    # Recent activity
    cursor.execute("""
        SELECT r.id, b.title, r.request_date, r.status, r.remarks
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        WHERE r.user_id = ?
        ORDER BY r.id DESC LIMIT 5
    """, (user_id,))
    recent_activity = cursor.fetchall()

    # Recently added books
    cursor.execute("SELECT id, title, author, publication_year FROM books ORDER BY id DESC LIMIT 4")
    recent_books = cursor.fetchall()

    conn.close()

    return render_template(
        'student_dashboard.html',
        user=user,
        metrics=metrics,
        active_loans=active_loans,
        recent_activity=recent_activity,
        recent_books=recent_books
    )


@dashboard_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """
    Administrator command center displaying all 8 core metrics, transactions, and breakdown.
    """
    update_overdue_statuses()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Calculate 8 Key Metrics from actual database records
    cursor.execute("SELECT count(*) FROM books")
    total_books = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(available_copies), 0) FROM books")
    available_copies = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM users WHERE role = 'student'")
    total_members = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM research_papers")
    total_papers = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Issued'")
    issued_books = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Pending'")
    pending_requests = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Overdue'")
    overdue_books = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Returned'")
    returned_books = cursor.fetchone()[0]

    stats = {
        "total_books": total_books,
        "available_copies": available_copies,
        "total_members": total_members,
        "total_papers": total_papers,
        "issued_books": issued_books,
        "pending_requests": pending_requests,
        "overdue_books": overdue_books,
        "returned_books": returned_books
    }

    # 2. Recent Transactions
    cursor.execute("""
        SELECT r.id, u.name as student_name, u.department, b.title as book_title,
               b.shelf_location, r.request_date, r.issue_date, r.due_date, r.return_date, r.status
        FROM borrow_records r
        JOIN users u ON r.user_id = u.id
        JOIN books b ON r.book_id = b.id
        ORDER BY r.id DESC LIMIT 8
    """)
    recent_transactions = cursor.fetchall()

    # 3. Category Distribution
    cursor.execute("""
        SELECT category, count(*) as count
        FROM books
        WHERE category IS NOT NULL
        GROUP BY category
        ORDER BY count DESC
    """)
    category_counts = cursor.fetchall()

    # 4. Recent Member Registrations
    cursor.execute("""
        SELECT id, name, department, student_id, status
        FROM users
        WHERE role = 'student'
        ORDER BY id DESC LIMIT 5
    """)
    recent_members = cursor.fetchall()

    # 5. System Activity Logs
    cursor.execute("""
        SELECT a.id, a.action, a.description, a.created_at, COALESCE(u.name, 'System') as user_name
        FROM activity_logs a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.id DESC LIMIT 6
    """)
    recent_logs = cursor.fetchall()

    conn.close()

    return render_template(
        'admin_dashboard.html',
        stats=stats,
        recent_transactions=recent_transactions,
        category_counts=category_counts,
        recent_members=recent_members,
        recent_logs=recent_logs
    )


@dashboard_bp.route('/admin/reports')
@admin_required
def reports():
    """
    Circulation and inventory statistical reports page.
    """
    update_overdue_statuses()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Overall Metrics
    cursor.execute("SELECT count(*), COALESCE(SUM(total_copies), 0), COALESCE(SUM(available_copies), 0) FROM books")
    b_row = cursor.fetchone()
    total_books, total_copies, available_copies = b_row[0], b_row[1], b_row[2]

    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Issued'")
    issued_books = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Overdue'")
    overdue_books = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM borrow_records WHERE status = 'Returned'")
    returned_books = cursor.fetchone()[0]

    stats = {
        "total_books": total_books,
        "total_copies": total_copies,
        "available_copies": available_copies,
        "issued_books": issued_books,
        "overdue_books": overdue_books,
        "returned_books": returned_books
    }

    # Category Statistics
    cursor.execute("""
        SELECT category, count(*) as title_count, SUM(total_copies) as sum_total, SUM(available_copies) as sum_available
        FROM books
        GROUP BY category
        ORDER BY title_count DESC
    """)
    category_stats = cursor.fetchall()

    # Popular Borrowed Books
    cursor.execute("""
        SELECT b.title, b.author, b.category, count(r.id) as borrow_count
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        GROUP BY b.id
        ORDER BY borrow_count DESC LIMIT 6
    """)
    popular_books = cursor.fetchall()

    conn.close()

    return render_template(
        'reports.html',
        stats=stats,
        category_stats=category_stats,
        popular_books=popular_books
    )
