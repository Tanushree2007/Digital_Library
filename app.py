"""
Digital Library & Research Management System
Main Application Entry Point (Flask Web Server)
"""

import os
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from database import init_db, seed_sample_data, update_overdue_statuses

# Import Blueprints
from routes.auth import auth_bp
from routes.books import books_bp
from routes.research import research_bp
from routes.borrowing import borrowing_bp
from routes.members import members_bp
from routes.dashboard import dashboard_bp
from routes.assistant import assistant_bp


def create_app():
    """
    Application Factory Pattern for Digital Library & Research Management System.
    """
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secure-salt-digital-library-2026-marathon')
    app.config['UPLOAD_FOLDER_COVERS'] = os.path.join(app.root_path, 'uploads', 'book_covers')
    app.config['UPLOAD_FOLDER_PAPERS'] = os.path.join(app.root_path, 'uploads', 'research_papers')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload limit

    # Ensure upload directories exist
    os.makedirs(app.config['UPLOAD_FOLDER_COVERS'], exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER_PAPERS'], exist_ok=True)

    # Initialize Database on Application Startup
    with app.app_context():
        init_db()
        seed_sample_data()
        update_overdue_statuses()

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(borrowing_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(assistant_bp)

    # Shorthand mapping so url_for('index') works alongside url_for('dashboard.index')
    shorthand_endpoints = {
        'index': 'dashboard.index',
        'about': 'dashboard.about',
        'student_dashboard': 'dashboard.student_dashboard',
        'admin_dashboard': 'dashboard.admin_dashboard',
        'reports': 'dashboard.reports',
        'login': 'auth.login',
        'register': 'auth.register',
        'logout': 'auth.logout',
        'profile': 'auth.profile',
        'books': 'books.books',
        'book_details': 'books.book_details',
        'manage_books': 'books.manage_books',
        'add_book': 'books.add_book',
        'edit_book': 'books.edit_book',
        'delete_book': 'books.delete_book',
        'research': 'research.research',
        'research_details': 'research.research_details',
        'manage_research': 'research.manage_research',
        'add_research': 'research.add_research',
        'delete_research': 'research.delete_research',
        'download_paper': 'research.download_paper',
        'my_books': 'borrowing.my_books',
        'borrow_history': 'borrowing.borrow_history',
        'manage_issues': 'borrowing.manage_issues',
        'manual_issue': 'borrowing.manual_issue',
        'manage_members': 'members.manage_members',
        'member_details': 'members.member_details',
    }

    def url_build_error_handler(error, endpoint, values):
        if endpoint in shorthand_endpoints:
            return url_for(shorthand_endpoints[endpoint], **values)
        raise error

    app.url_build_error_handlers.append(url_build_error_handler)

    # Serve uploaded book covers safely
    @app.route('/uploads/book_covers/<path:filename>')
    def uploaded_book_cover(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER_COVERS'], filename)

    # Global HTTP Error Handlers
    @app.errorhandler(400)
    def handle_bad_request(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Bad request. Please verify submitted parameters."}), 400
        return render_template('base.html'), 400

    @app.errorhandler(401)
    def handle_unauthorized(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Authentication required."}), 401
        return redirect(url_for('login'))

    @app.errorhandler(403)
    def handle_forbidden(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Access forbidden. Insufficient permissions."}), 403
        return redirect(url_for('index'))

    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Resource not found."}), 404
        return render_template('base.html'), 404

    @app.errorhandler(500)
    def handle_internal_error(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Internal server error occurred."}), 500
        return render_template('base.html'), 500

    return app


# Application instance for WSGI servers
app = create_app()

if __name__ == '__main__':
    print("=" * 70)
    print(" STARTING DIGITAL LIBRARY & RESEARCH MANAGEMENT SYSTEM SERVER")
    print("=" * 70)
    print(" Access URL: http://127.0.0.1:5000")
    print(" Admin Login:   admin@library.edu       / Admin@12345")
    print(" Student Login: alex.turner@student.edu / Student@12345")
    print("=" * 70)
    app.run(host='127.0.0.1', port=5000, debug=True)
