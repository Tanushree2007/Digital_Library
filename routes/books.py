"""
Books Catalog and Inventory Management Routes
Supports public catalog browsing, multi-criteria filtering, and admin CRUD operations.
"""

import os
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app, session
from werkzeug.utils import secure_filename
from database import get_db_connection, log_activity
from routes.auth import login_required, admin_required

books_bp = Blueprint('books', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


# ==============================================================================
# REST API Endpoints
# ==============================================================================

@books_bp.route('/api/books', methods=['GET'])
def api_get_books():
    """
    GET /api/books
    Query params: q, category, availability ('available'/'out_of_stock'), sort
    """
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    availability = request.args.get('availability', '').strip()
    sort = request.args.get('sort', 'title_asc')

    conn = get_db_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM books WHERE 1=1"
    params = []

    if q:
        sql += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term])

    if category:
        sql += " AND category = ?"
        params.append(category)

    if availability == 'available':
        sql += " AND available_copies > 0"
    elif availability == 'out_of_stock':
        sql += " AND available_copies = 0"

    # Sorting
    if sort == 'title_desc':
        sql += " ORDER BY title DESC"
    elif sort == 'year_desc':
        sql += " ORDER BY publication_year DESC"
    elif sort == 'year_asc':
        sql += " ORDER BY publication_year ASC"
    else:
        sql += " ORDER BY title ASC"

    cursor.execute(sql, params)
    books = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({"success": True, "count": len(books), "books": books}), 200


@books_bp.route('/api/books/<int:book_id>', methods=['GET'])
def api_get_book(book_id):
    """
    GET /api/books/<id>
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()
    conn.close()

    if not book:
        return jsonify({"error": "Book not found."}), 404

    return jsonify({"success": True, "book": dict(book)}), 200


@books_bp.route('/api/categories', methods=['GET', 'POST'])
def api_categories():
    """
    GET /api/categories: List all categories
    POST /api/categories: Add new category (Admin only)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        if not session.get('user_id') or session.get('role') != 'admin':
            conn.close()
            return jsonify({"error": "Admin required."}), 403

        data = request.get_json() or {}
        cat_name = data.get('category_name', '').strip()
        description = data.get('description', '').strip()

        if not cat_name:
            conn.close()
            return jsonify({"error": "category_name is required."}), 400

        cursor.execute("SELECT id FROM categories WHERE category_name = ?", (cat_name,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"error": "Category already exists."}), 409

        cursor.execute("INSERT INTO categories (category_name, description) VALUES (?, ?)", (cat_name, description))
        cat_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"success": True, "category_id": cat_id, "message": "Category added successfully."}), 201

    cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
    cats = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "categories": cats}), 200


@books_bp.route('/api/books', methods=['POST'])
@admin_required
def api_create_book():
    """
    POST /api/books
    Admin endpoint to add a new book to inventory.
    """
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    author = data.get('author', '').strip()
    isbn = data.get('isbn', '').strip()
    category = data.get('category', '').strip()
    publisher = data.get('publisher', '').strip()
    publication_year = data.get('publication_year')
    language = data.get('language', 'English').strip()
    description = data.get('description', '').strip()
    shelf_location = data.get('shelf_location', '').strip()
    total_copies = data.get('total_copies')
    available_copies = data.get('available_copies')

    if not title or not author or not isbn or total_copies is None:
        return jsonify({"error": "Title, author, ISBN, and total_copies are required."}), 400

    try:
        total_copies = int(total_copies)
        available_copies = int(available_copies) if available_copies is not None else total_copies
    except ValueError:
        return jsonify({"error": "Total and available copies must be numeric integers."}), 400

    if total_copies < 1:
        return jsonify({"error": "Total copies must be at least 1."}), 400

    if available_copies < 0 or available_copies > total_copies:
        return jsonify({"error": "Available copies must be between 0 and total copies."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check ISBN uniqueness
    cursor.execute("SELECT id FROM books WHERE isbn = ?", (isbn,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "A book with this ISBN already exists."}), 409

    try:
        cursor.execute("""
            INSERT INTO books (
                isbn, title, author, category, publisher, publication_year,
                language, description, total_copies, available_copies, shelf_location
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            isbn, title, author, category, publisher, publication_year,
            language, description, total_copies, available_copies, shelf_location
        ))
        new_book_id = cursor.lastrowid
        conn.commit()
        conn.close()

        log_activity(session.get('user_id'), "Add Book", f"Added book: '{title}' (ISBN: {isbn})")

        return jsonify({
            "success": True,
            "message": "Book successfully added to library catalog.",
            "book_id": new_book_id
        }), 201
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Failed to add book: {str(e)}"}), 500


@books_bp.route('/api/books/<int:book_id>', methods=['PUT'])
@admin_required
def api_update_book(book_id):
    """
    PUT /api/books/<id>
    Admin endpoint to modify an existing book.
    """
    data = request.get_json() or {}
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Book not found."}), 404

    title = data.get('title', existing['title']).strip()
    author = data.get('author', existing['author']).strip()
    isbn = data.get('isbn', existing['isbn']).strip()
    category = data.get('category', existing['category']).strip()
    publisher = data.get('publisher', existing['publisher'])
    publication_year = data.get('publication_year', existing['publication_year'])
    language = data.get('language', existing['language'])
    description = data.get('description', existing['description'])
    shelf_location = data.get('shelf_location', existing['shelf_location'])

    try:
        total_copies = int(data.get('total_copies', existing['total_copies']))
        available_copies = int(data.get('available_copies', existing['available_copies']))
    except ValueError:
        conn.close()
        return jsonify({"error": "Total and available copies must be numeric integers."}), 400

    if available_copies > total_copies or available_copies < 0:
        conn.close()
        return jsonify({"error": "Available copies cannot exceed total copies or be negative."}), 400

    # Check if ISBN is duplicate with another book
    cursor.execute("SELECT id FROM books WHERE isbn = ? AND id != ?", (isbn, book_id))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "Another book already uses this ISBN."}), 409

    try:
        cursor.execute("""
            UPDATE books
            SET title = ?, author = ?, isbn = ?, category = ?, publisher = ?,
                publication_year = ?, language = ?, description = ?,
                total_copies = ?, available_copies = ?, shelf_location = ?
            WHERE id = ?
        """, (
            title, author, isbn, category, publisher, publication_year,
            language, description, total_copies, available_copies, shelf_location, book_id
        ))
        conn.commit()
        conn.close()

        log_activity(session.get('user_id'), "Edit Book", f"Updated book #{book_id}: '{title}'")

        return jsonify({"success": True, "message": "Book updated successfully."}), 200
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Failed to update book: {str(e)}"}), 500


@books_bp.route('/api/books/<int:book_id>', methods=['DELETE'])
@admin_required
def api_delete_book(book_id):
    """
    DELETE /api/books/<id>
    Admin endpoint to delete a book. Prevents deletion if active issued copies exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()
    if not book:
        conn.close()
        return jsonify({"error": "Book not found."}), 404

    # Prevent deletion if active issues exist
    cursor.execute("""
        SELECT count(*) FROM borrow_records
        WHERE book_id = ? AND status IN ('Issued', 'Overdue', 'Pending')
    """, (book_id,))
    active_count = cursor.fetchone()[0]

    if active_count > 0:
        conn.close()
        return jsonify({
            "error": f"Cannot delete book. There are currently {active_count} active or pending loan records."
        }), 400

    try:
        cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()
        conn.close()

        log_activity(session.get('user_id'), "Delete Book", f"Deleted book #{book_id}: '{book['title']}'")

        return jsonify({"success": True, "message": "Book removed successfully from catalog."}), 200
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Failed to delete book: {str(e)}"}), 500


# ==============================================================================
# HTML Page Controllers
# ==============================================================================

@books_bp.route('/books')
def books():
    """
    Public and student book catalog page with live filtering.
    """
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    availability = request.args.get('availability', '').strip()
    sort = request.args.get('sort', 'title_asc')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
    categories = cursor.fetchall()

    sql = "SELECT * FROM books WHERE 1=1"
    params = []

    if q:
        sql += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term])

    if category:
        sql += " AND category = ?"
        params.append(category)

    if availability == 'available':
        sql += " AND available_copies > 0"
    elif availability == 'out_of_stock':
        sql += " AND available_copies = 0"

    if sort == 'title_desc':
        sql += " ORDER BY title DESC"
    elif sort == 'year_desc':
        sql += " ORDER BY publication_year DESC"
    elif sort == 'year_asc':
        sql += " ORDER BY publication_year ASC"
    else:
        sql += " ORDER BY title ASC"

    cursor.execute(sql, params)
    book_list = cursor.fetchall()
    conn.close()

    return render_template(
        'books.html',
        books=book_list,
        categories=categories,
        search_query=q,
        selected_category=category,
        selected_availability=availability,
        selected_sort=sort
    )


@books_bp.route('/books/<int:book_id>')
def book_details(book_id):
    """
    Detailed profile view for an individual book.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()
    conn.close()

    if not book:
        flash("The requested book was not found in our catalog.", "warning")
        return redirect(url_for('books.books'))

    return render_template('book_details.html', book=book)


@books_bp.route('/admin/books')
@admin_required
def manage_books():
    """
    Admin book inventory table.
    """
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
    categories = cursor.fetchall()

    sql = "SELECT * FROM books WHERE 1=1"
    params = []
    if q:
        sql += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term])
    if category:
        sql += " AND category = ?"
        params.append(category)

    sql += " ORDER BY id DESC"
    cursor.execute(sql, params)
    books = cursor.fetchall()
    conn.close()

    return render_template(
        'manage_books.html',
        books=books,
        categories=categories,
        search_query=q,
        selected_category=category
    )


@books_bp.route('/admin/books/add', methods=['GET', 'POST'])
@admin_required
def add_book():
    """
    Admin form to add a new book.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        isbn = request.form.get('isbn', '').strip()
        new_cat = request.form.get('new_category', '').strip()
        selected_cat = request.form.get('category', '').strip()
        category = new_cat if new_cat else selected_cat
        publisher = request.form.get('publisher', '').strip()
        publication_year = request.form.get('publication_year') or None
        language = request.form.get('language', 'English').strip()
        description = request.form.get('description', '').strip()
        shelf_location = request.form.get('shelf_location', '').strip()
        total_copies = int(request.form.get('total_copies', 1))
        available_copies = int(request.form.get('available_copies', total_copies))

        if category:
            cursor.execute("INSERT OR IGNORE INTO categories (category_name) VALUES (?)", (category,))
            conn.commit()

        cover_filename = 'default_book.svg'
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and allowed_image(file.filename):
                safe_name = secure_filename(file.filename)
                cover_filename = f"book_{isbn}_{safe_name}"
                upload_path = os.path.join(current_app.config['UPLOAD_FOLDER_COVERS'], cover_filename)
                file.save(upload_path)

        cursor.execute("SELECT id FROM books WHERE isbn = ?", (isbn,))
        if cursor.fetchone():
            flash("A book with this ISBN already exists.", "danger")
        else:
            try:
                cursor.execute("""
                    INSERT INTO books (
                        isbn, title, author, category, publisher, publication_year,
                        language, description, cover_image, total_copies, available_copies, shelf_location
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    isbn, title, author, category, publisher, publication_year,
                    language, description, cover_filename, total_copies, available_copies, shelf_location
                ))
                conn.commit()
                log_activity(session['user_id'], "Add Book", f"Registered book '{title}' (ISBN {isbn})")
                flash(f"Book '{title}' added successfully!", "success")
                conn.close()
                return redirect(url_for('books.manage_books'))
            except Exception as e:
                flash(f"Error adding book: {str(e)}", "danger")

    cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
    categories = cursor.fetchall()
    conn.close()
    return render_template('add_book.html', categories=categories)


@books_bp.route('/admin/books/edit/<int:book_id>', methods=['GET', 'POST'])
@admin_required
def edit_book(book_id):
    """
    Admin form to edit existing book details.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()
    if not book:
        conn.close()
        flash("Book not found.", "warning")
        return redirect(url_for('books.manage_books'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        isbn = request.form.get('isbn', '').strip()
        category = request.form.get('category', '').strip()
        publisher = request.form.get('publisher', '').strip()
        publication_year = request.form.get('publication_year') or None
        language = request.form.get('language', 'English').strip()
        description = request.form.get('description', '').strip()
        shelf_location = request.form.get('shelf_location', '').strip()
        total_copies = int(request.form.get('total_copies', book['total_copies']))
        available_copies = int(request.form.get('available_copies', book['available_copies']))

        cover_filename = book['cover_image']
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and allowed_image(file.filename):
                safe_name = secure_filename(file.filename)
                cover_filename = f"book_{isbn}_{safe_name}"
                upload_path = os.path.join(current_app.config['UPLOAD_FOLDER_COVERS'], cover_filename)
                file.save(upload_path)

        try:
            cursor.execute("""
                UPDATE books
                SET title = ?, author = ?, isbn = ?, category = ?, publisher = ?,
                    publication_year = ?, language = ?, description = ?,
                    cover_image = ?, total_copies = ?, available_copies = ?, shelf_location = ?
                WHERE id = ?
            """, (
                title, author, isbn, category, publisher, publication_year,
                language, description, cover_filename, total_copies, available_copies, shelf_location, book_id
            ))
            conn.commit()
            log_activity(session['user_id'], "Edit Book", f"Updated book '{title}'")
            flash(f"Book '{title}' updated successfully!", "success")
            conn.close()
            return redirect(url_for('books.manage_books'))
        except Exception as e:
            flash(f"Error updating book: {str(e)}", "danger")

    cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
    categories = cursor.fetchall()
    conn.close()
    return render_template('edit_book.html', book=book, categories=categories)


@books_bp.route('/admin/books/delete/<int:book_id>', methods=['POST'])
@admin_required
def delete_book(book_id):
    """
    Admin action to delete book.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()
    if not book:
        conn.close()
        flash("Book not found.", "warning")
        return redirect(url_for('books.manage_books'))

    cursor.execute("""
        SELECT count(*) FROM borrow_records
        WHERE book_id = ? AND status IN ('Issued', 'Overdue', 'Pending')
    """, (book_id,))
    active = cursor.fetchone()[0]

    if active > 0:
        conn.close()
        flash(f"Cannot delete '{book['title']}'. There are {active} active/pending borrow records.", "danger")
        return redirect(url_for('books.manage_books'))

    cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()

    log_activity(session['user_id'], "Delete Book", f"Deleted book '{book['title']}'")
    flash(f"Book '{book['title']}' deleted successfully.", "success")
    return redirect(url_for('books.manage_books'))
