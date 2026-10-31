"""
Member & Student Account Management Routes
Handles student roster inspection, loan audits, and account activation/deactivation.
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from database import get_db_connection, log_activity, update_overdue_statuses
from routes.auth import admin_required

members_bp = Blueprint('members', __name__)


# ==============================================================================
# REST API Endpoints
# ==============================================================================

@members_bp.route('/api/members', methods=['GET'])
@admin_required
def api_get_members():
    """
    GET /api/members
    Query params: q (name/email/student_id), status ('active'/'inactive')
    """
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    sql = "SELECT id, name, email, phone, department, student_id, role, status, created_at FROM users WHERE role = 'student'"
    params = []

    if q:
        sql += " AND (name LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term])

    if status in ['active', 'inactive']:
        sql += " AND status = ?"
        params.append(status)

    sql += " ORDER BY id DESC"
    cursor.execute(sql, params)
    members = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({"success": True, "count": len(members), "members": members}), 200


@members_bp.route('/api/members/<int:member_id>', methods=['GET'])
@admin_required
def api_get_member(member_id):
    """
    GET /api/members/<id>
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, email, phone, department, student_id, role, status, created_at
        FROM users WHERE id = ?
    """, (member_id,))
    member = cursor.fetchone()

    if not member:
        conn.close()
        return jsonify({"error": "Member not found."}), 404

    # Active loans
    cursor.execute("""
        SELECT r.id, b.title, r.issue_date, r.due_date, r.status
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        WHERE r.user_id = ? AND r.status IN ('Issued', 'Overdue')
    """, (member_id,))
    active_loans = [dict(row) for row in cursor.fetchall()]

    # Complete history
    cursor.execute("""
        SELECT r.id, b.title, r.request_date, r.issue_date, r.return_date, r.status, r.remarks
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        WHERE r.user_id = ?
        ORDER BY r.id DESC
    """, (member_id,))
    history = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        "success": True,
        "member": dict(member),
        "active_loans": active_loans,
        "history": history
    }), 200


@members_bp.route('/api/members/<int:member_id>/status', methods=['PUT'])
@admin_required
def api_update_member_status(member_id):
    """
    PUT /api/members/<id>/status
    Body: {"status": "active" | "inactive"}
    """
    data = request.get_json() or {}
    new_status = data.get('status', '').strip().lower()

    if new_status not in ['active', 'inactive']:
        return jsonify({"error": "Status must be 'active' or 'inactive'."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, role FROM users WHERE id = ?", (member_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "Member not found."}), 404

    if user['role'] == 'admin':
        conn.close()
        return jsonify({"error": "Cannot change the status of an administrator account."}), 400

    try:
        cursor.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, member_id))
        conn.commit()
        conn.close()

        log_activity(session['user_id'], "Member Status Update", f"Changed status of {user['name']} to '{new_status}'")

        return jsonify({
            "success": True,
            "message": f"Member account status successfully updated to {new_status}.",
            "status": new_status
        }), 200
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Failed to update status: {str(e)}"}), 500


# ==============================================================================
# HTML Page Controllers
# ==============================================================================

@members_bp.route('/admin/members')
@admin_required
def manage_members():
    """
    Admin student roster view.
    """
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM users WHERE role = 'student'"
    params = []

    if q:
        sql += " AND (name LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term])

    if status in ['active', 'inactive']:
        sql += " AND status = ?"
        params.append(status)

    sql += " ORDER BY id DESC"
    cursor.execute(sql, params)
    members = cursor.fetchall()
    conn.close()

    return render_template(
        'manage_members.html',
        members=members,
        search_query=q,
        selected_status=status
    )


@members_bp.route('/admin/members/<int:member_id>')
@admin_required
def member_details(member_id):
    """
    Admin detailed member profile and circulation history view.
    """
    update_overdue_statuses()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (member_id,))
    member = cursor.fetchone()

    if not member:
        conn.close()
        flash("Member not found.", "warning")
        return redirect(url_for('members.manage_members'))

    # Active Loans
    cursor.execute("""
        SELECT r.id, b.title, r.issue_date, r.due_date, r.status
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        WHERE r.user_id = ? AND r.status IN ('Issued', 'Overdue')
        ORDER BY r.due_date ASC
    """, (member_id,))
    active_loans = cursor.fetchall()

    # History
    cursor.execute("""
        SELECT r.id, b.title, r.request_date, r.issue_date, r.return_date, r.status, r.remarks
        FROM borrow_records r
        JOIN books b ON r.book_id = b.id
        WHERE r.user_id = ?
        ORDER BY r.id DESC
    """, (member_id,))
    history = cursor.fetchall()

    conn.close()

    return render_template(
        'member_details.html',
        member=member,
        active_loans=active_loans,
        history=history
    )
