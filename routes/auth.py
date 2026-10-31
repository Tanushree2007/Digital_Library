"""
Authentication & Authorization Routes and Decorators
Handles user registration, login, logout, password hashing, and role checks.
"""

from functools import wraps
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection, log_activity

auth_bp = Blueprint('auth', __name__)


# ==============================================================================
# Security & Access Control Decorators
# ==============================================================================

def login_required(f):
    """
    Decorator that ensures a user is authenticated via session.
    Returns 401 JSON for API requests or redirects to login for HTML requests.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            if request.path.startswith('/api/'):
                return jsonify({"error": "Authentication required. Please log in."}), 401
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator that restricts access to users with role == 'admin'.
    Returns 403 JSON for API requests or redirects with flash for HTML requests.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            if request.path.startswith('/api/'):
                return jsonify({"error": "Authentication required. Please log in."}), 401
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        
        if session.get('role') != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({"error": "Access denied. Administrator privileges required."}), 403
            flash("Access denied. Administrator privileges required.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    """
    Decorator that restricts access to users with role == 'student'.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            if request.path.startswith('/api/'):
                return jsonify({"error": "Authentication required. Please log in."}), 401
            flash("Please sign in as a student to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        
        if session.get('role') != 'student':
            if request.path.startswith('/api/'):
                return jsonify({"error": "Access denied. Student portal only."}), 403
            flash("Access restricted to student accounts.", "warning")
            return redirect(url_for('admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ==============================================================================
# REST API Endpoints
# ==============================================================================

@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    """
    POST /api/register
    Registers a new student account.
    """
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    department = data.get('department', '').strip()
    student_id = data.get('student_id', '').strip()
    phone = data.get('phone', '').strip()

    if not name or not email or not password or not department or not student_id:
        return jsonify({"error": "Name, email, password, student ID, and department are required."}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters long."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if email is already registered
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "An account with this email address already exists."}), 409

    pwd_hash = generate_password_hash(password)
    try:
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, phone, department, student_id, role, status)
            VALUES (?, ?, ?, ?, ?, ?, 'student', 'active')
        """, (name, email, pwd_hash, phone, department, student_id))
        new_user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        log_activity(new_user_id, "Student Registration", f"Student account registered: {name} ({email})")

        return jsonify({
            "success": True,
            "message": "Student account registered successfully! You may now sign in.",
            "user_id": new_user_id
        }), 201
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500


@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    """
    POST /api/login
    Authenticates a user (student or admin) and initializes session.
    """
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({"error": "Invalid email address or password."}), 401

    if user['status'] != 'active':
        return jsonify({"error": "Your library account is deactivated. Please contact the librarian."}), 403

    # Set Session State
    session.clear()
    session['user_id'] = user['id']
    session['name'] = user['name']
    session['email'] = user['email']
    session['role'] = user['role']
    session['student_id'] = user['student_id']
    session['department'] = user['department']

    log_activity(user['id'], "Login", f"User logged in: {user['name']} ({user['role']})")

    return jsonify({
        "success": True,
        "message": f"Welcome back, {user['name']}!",
        "user": {
            "id": user['id'],
            "name": user['name'],
            "email": user['email'],
            "role": user['role'],
            "department": user['department'],
            "student_id": user['student_id']
        }
    }), 200


@auth_bp.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    """
    POST /api/logout
    Clears the active session.
    """
    user_id = session.get('user_id')
    user_name = session.get('name')
    session.clear()
    if user_id:
        log_activity(user_id, "Logout", f"User logged out: {user_name}")

    return jsonify({"success": True, "message": "Successfully logged out."}), 200


@auth_bp.route('/api/profile', methods=['GET'])
@login_required
def api_profile():
    """
    GET /api/profile
    Retrieves the authenticated user's profile details.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, email, phone, department, student_id, profile_image, role, status, created_at
        FROM users WHERE id = ?
    """, (session['user_id'],))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "User profile not found."}), 404

    return jsonify({"success": True, "profile": dict(user)}), 200


# ==============================================================================
# HTML Page Handlers
# ==============================================================================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Renders login page and processes form-based submissions.
    """
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if not user or not check_password_hash(user['password_hash'], password):
            flash("Invalid email or password. Please verify your credentials.", "danger")
            return render_template('login.html')

        if user['status'] != 'active':
            flash("Your library account is deactivated. Please contact the librarian.", "danger")
            return render_template('login.html')

        # Initialize session
        session.clear()
        session['user_id'] = user['id']
        session['name'] = user['name']
        session['email'] = user['email']
        session['role'] = user['role']
        session['student_id'] = user['student_id']
        session['department'] = user['department']

        log_activity(user['id'], "Login", f"User logged in: {user['name']} ({user['role']})")
        flash(f"Welcome back, {user['name']}!", "success")

        # Redirect according to role
        if user['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Renders registration page and creates new student accounts.
    """
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        department = request.form.get('department', '').strip()
        student_id = request.form.get('student_id', '').strip()
        phone = request.form.get('phone', '').strip()

        if not name or not email or not password or not department or not student_id:
            flash("All mandatory fields must be filled out.", "danger")
            return render_template('register.html')

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return render_template('register.html')

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('register.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            flash("An account with this email address already exists. Please sign in.", "warning")
            return render_template('register.html')

        pwd_hash = generate_password_hash(password)
        try:
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, phone, department, student_id, role, status)
                VALUES (?, ?, ?, ?, ?, ?, 'student', 'active')
            """, (name, email, pwd_hash, phone, department, student_id))
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()

            log_activity(new_id, "Registration", f"Student registration: {name}")
            flash("Registration successful! You may now sign in to your student portal.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            conn.close()
            flash(f"An error occurred while creating your account: {str(e)}", "danger")
            return render_template('register.html')

    return render_template('register.html')


@auth_bp.route('/logout')
def logout():
    """
    Clears user session and redirects to home page.
    """
    user_id = session.get('user_id')
    user_name = session.get('name')
    session.clear()
    if user_id:
        log_activity(user_id, "Logout", f"User logged out: {user_name}")

    flash("You have been signed out safely.", "info")
    return redirect(url_for('index'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    View and update user personal profile or change password.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            name = request.form.get('name', '').strip()
            phone = request.form.get('phone', '').strip()
            department = request.form.get('department', '').strip()

            if not name:
                flash("Name cannot be empty.", "danger")
            else:
                cursor.execute("""
                    UPDATE users
                    SET name = ?, phone = ?, department = ?
                    WHERE id = ?
                """, (name, phone, department, session['user_id']))
                conn.commit()
                session['name'] = name
                session['department'] = department
                flash("Profile details updated successfully!", "success")

        elif action == 'change_password':
            current_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_new_pwd = request.form.get('confirm_new_password', '')

            if not check_password_hash(user['password_hash'], current_pwd):
                flash("Your current password was entered incorrectly.", "danger")
            elif new_pwd != confirm_new_pwd:
                flash("New passwords do not match.", "danger")
            elif len(new_pwd) < 6:
                flash("New password must be at least 6 characters.", "danger")
            else:
                new_hash = generate_password_hash(new_pwd)
                cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, session['user_id']))
                conn.commit()
                flash("Password changed successfully!", "success")

        cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()

    conn.close()
    return render_template('profile.html', user=user)
