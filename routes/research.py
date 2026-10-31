"""
Research Papers Repository Routes
Provides academic publication indexing, full-text abstract discovery, 
PDF document validation and downloads, and administrative document management.
"""

import os
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app, send_from_directory, session
from werkzeug.utils import secure_filename
from database import get_db_connection, log_activity
from routes.auth import login_required, admin_required

research_bp = Blueprint('research', __name__)

ALLOWED_PDF_EXTENSIONS = {'pdf'}

def allowed_pdf(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_PDF_EXTENSIONS


# ==============================================================================
# REST API Endpoints
# ==============================================================================

@research_bp.route('/api/research', methods=['GET'])
def api_get_research():
    """
    GET /api/research
    Query params: q, subject, year
    """
    q = request.args.get('q', '').strip()
    subject = request.args.get('subject', '').strip()
    year = request.args.get('year', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM research_papers WHERE 1=1"
    params = []

    if q:
        sql += " AND (title LIKE ? OR author LIKE ? OR keywords LIKE ? OR abstract LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term, term])

    if subject:
        sql += " AND subject = ?"
        params.append(subject)

    if year:
        try:
            params.append(int(year))
            sql += " AND publication_year = ?"
        except ValueError:
            pass

    sql += " ORDER BY publication_year DESC, id DESC"
    cursor.execute(sql, params)
    papers = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({"success": True, "count": len(papers), "papers": papers}), 200


@research_bp.route('/api/research/<int:paper_id>', methods=['GET'])
def api_get_paper(paper_id):
    """
    GET /api/research/<id>
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_papers WHERE id = ?", (paper_id,))
    paper = cursor.fetchone()
    conn.close()

    if not paper:
        return jsonify({"error": "Research paper not found."}), 404

    return jsonify({"success": True, "paper": dict(paper)}), 200


@research_bp.route('/api/research', methods=['POST'])
@admin_required
def api_create_paper():
    """
    POST /api/research
    Admin endpoint to index a research paper.
    """
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    author = data.get('author', '').strip()
    subject = data.get('subject', '').strip()
    abstract = data.get('abstract', '').strip()
    publication_year = data.get('publication_year')
    journal_name = data.get('journal_name', '').strip()
    keywords = data.get('keywords', '').strip()
    pdf_path = data.get('pdf_path', '').strip()

    if not title or not author or not subject or not abstract or not publication_year:
        return jsonify({"error": "Title, author, subject, abstract, and publication_year are required."}), 400

    try:
        publication_year = int(publication_year)
    except ValueError:
        return jsonify({"error": "Publication year must be an integer."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO research_papers (
                title, author, subject, abstract, publication_year, journal_name, keywords, pdf_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, author, subject, abstract, publication_year, journal_name, keywords, pdf_path))
        new_paper_id = cursor.lastrowid
        conn.commit()
        conn.close()

        log_activity(session.get('user_id'), "Add Research Paper", f"Indexed paper: '{title}'")

        return jsonify({
            "success": True,
            "message": "Research paper indexed successfully.",
            "paper_id": new_paper_id
        }), 201
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Failed to index paper: {str(e)}"}), 500


@research_bp.route('/api/research/<int:paper_id>', methods=['PUT'])
@admin_required
def api_update_paper(paper_id):
    """
    PUT /api/research/<id>
    """
    data = request.get_json() or {}
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM research_papers WHERE id = ?", (paper_id,))
    paper = cursor.fetchone()
    if not paper:
        conn.close()
        return jsonify({"error": "Paper not found."}), 404

    title = data.get('title', paper['title']).strip()
    author = data.get('author', paper['author']).strip()
    subject = data.get('subject', paper['subject']).strip()
    abstract = data.get('abstract', paper['abstract']).strip()
    publication_year = data.get('publication_year', paper['publication_year'])
    journal_name = data.get('journal_name', paper['journal_name']).strip()
    keywords = data.get('keywords', paper['keywords']).strip()
    pdf_path = data.get('pdf_path', paper['pdf_path']).strip()

    try:
        cursor.execute("""
            UPDATE research_papers
            SET title = ?, author = ?, subject = ?, abstract = ?,
                publication_year = ?, journal_name = ?, keywords = ?, pdf_path = ?
            WHERE id = ?
        """, (title, author, subject, abstract, publication_year, journal_name, keywords, pdf_path, paper_id))
        conn.commit()
        conn.close()

        log_activity(session.get('user_id'), "Edit Research Paper", f"Updated paper #{paper_id}: '{title}'")

        return jsonify({"success": True, "message": "Research paper updated successfully."}), 200
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Failed to update paper: {str(e)}"}), 500


@research_bp.route('/api/research/<int:paper_id>', methods=['DELETE'])
@admin_required
def api_delete_paper(paper_id):
    """
    DELETE /api/research/<id>
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM research_papers WHERE id = ?", (paper_id,))
    paper = cursor.fetchone()
    if not paper:
        conn.close()
        return jsonify({"error": "Research paper not found."}), 404

    try:
        cursor.execute("DELETE FROM research_papers WHERE id = ?", (paper_id,))
        conn.commit()
        conn.close()

        log_activity(session.get('user_id'), "Delete Research Paper", f"Deleted paper #{paper_id}: '{paper['title']}'")

        return jsonify({"success": True, "message": "Research paper removed successfully."}), 200
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Failed to delete paper: {str(e)}"}), 500


# ==============================================================================
# HTML Page Controllers
# ==============================================================================

@research_bp.route('/research')
def research():
    """
    Public and student research papers directory.
    """
    q = request.args.get('q', '').strip()
    subject = request.args.get('subject', '').strip()
    year = request.args.get('year', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Subjects list for filter
    cursor.execute("SELECT DISTINCT subject FROM research_papers WHERE subject IS NOT NULL ORDER BY subject ASC")
    subjects = [row['subject'] for row in cursor.fetchall()]

    sql = "SELECT * FROM research_papers WHERE 1=1"
    params = []

    if q:
        sql += " AND (title LIKE ? OR author LIKE ? OR keywords LIKE ? OR abstract LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term, term])

    if subject:
        sql += " AND subject = ?"
        params.append(subject)

    if year:
        try:
            params.append(int(year))
            sql += " AND publication_year = ?"
        except ValueError:
            pass

    sql += " ORDER BY publication_year DESC, id DESC"
    cursor.execute(sql, params)
    paper_list = cursor.fetchall()
    conn.close()

    return render_template(
        'research.html',
        papers=paper_list,
        subjects=subjects,
        search_query=q,
        selected_subject=subject,
        selected_year=year
    )


@research_bp.route('/research/<int:paper_id>')
def research_details(paper_id):
    """
    Individual research paper view.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_papers WHERE id = ?", (paper_id,))
    paper = cursor.fetchone()
    conn.close()

    if not paper:
        flash("The requested research paper was not found.", "warning")
        return redirect(url_for('research.research'))

    return render_template('research_details.html', paper=paper)


@research_bp.route('/research/download/<int:paper_id>')
def download_paper(paper_id):
    """
    Securely serves PDF research paper document.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT pdf_path, title FROM research_papers WHERE id = ?", (paper_id,))
    paper = cursor.fetchone()
    conn.close()

    if not paper or not paper['pdf_path']:
        flash("PDF document is not attached to this publication.", "warning")
        return redirect(url_for('research.research'))

    filename = os.path.basename(paper['pdf_path'])
    folder = current_app.config['UPLOAD_FOLDER_PAPERS']

    file_path = os.path.join(folder, filename)
    if not os.path.isfile(file_path):
        flash("PDF file not found on library server.", "danger")
        return redirect(url_for('research.research_details', paper_id=paper_id))

    return send_from_directory(folder, filename, as_attachment=False)


@research_bp.route('/admin/research')
@admin_required
def manage_research():
    """
    Admin research paper management table.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_papers ORDER BY id DESC")
    papers = cursor.fetchall()
    conn.close()

    return render_template('manage_research.html', papers=papers)


@research_bp.route('/admin/research/add', methods=['GET', 'POST'])
@admin_required
def add_research():
    """
    Admin form to index and upload a new academic paper.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        new_subj = request.form.get('new_subject', '').strip()
        selected_subj = request.form.get('subject', '').strip()
        subject = new_subj if new_subj else selected_subj
        publication_year = int(request.form.get('publication_year', 2024))
        journal_name = request.form.get('journal_name', '').strip()
        keywords = request.form.get('keywords', '').strip()
        abstract = request.form.get('abstract', '').strip()

        pdf_filename = None
        if 'pdf_file' in request.files:
            file = request.files['pdf_file']
            if file and allowed_pdf(file.filename):
                safe_name = secure_filename(file.filename)
                pdf_filename = f"paper_{publication_year}_{safe_name}"
                upload_path = os.path.join(current_app.config['UPLOAD_FOLDER_PAPERS'], pdf_filename)
                file.save(upload_path)

        try:
            cursor.execute("""
                INSERT INTO research_papers (
                    title, author, subject, abstract, publication_year, journal_name, keywords, pdf_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, author, subject, abstract, publication_year, journal_name, keywords, pdf_filename))
            conn.commit()
            log_activity(session['user_id'], "Add Research Paper", f"Indexed research paper '{title}'")
            flash(f"Research paper '{title}' uploaded and indexed successfully!", "success")
            conn.close()
            return redirect(url_for('research.manage_research'))
        except Exception as e:
            flash(f"Error indexing research paper: {str(e)}", "danger")

    cursor.execute("SELECT DISTINCT subject FROM research_papers WHERE subject IS NOT NULL ORDER BY subject ASC")
    subjects = [row['subject'] for row in cursor.fetchall()]
    if not subjects:
        subjects = [
            "Computer Science & Engineering",
            "Artificial Intelligence & Data Science",
            "Software Engineering & Web Development",
            "Cybersecurity & Cryptography",
            "Mathematics & Statistics"
        ]
    conn.close()

    return render_template('add_research.html', subjects=subjects)


@research_bp.route('/admin/research/delete/<int:paper_id>', methods=['POST'])
@admin_required
def delete_research(paper_id):
    """
    Admin action to delete paper.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title, pdf_path FROM research_papers WHERE id = ?", (paper_id,))
    paper = cursor.fetchone()

    if not paper:
        conn.close()
        flash("Paper not found.", "warning")
        return redirect(url_for('research.manage_research'))

    cursor.execute("DELETE FROM research_papers WHERE id = ?", (paper_id,))
    conn.commit()
    conn.close()

    # Clean up uploaded PDF if exists
    if paper['pdf_path']:
        try:
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER_PAPERS'], paper['pdf_path'])
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

    log_activity(session['user_id'], "Delete Research Paper", f"Deleted paper '{paper['title']}'")
    flash(f"Research paper '{paper['title']}' deleted successfully.", "success")
    return redirect(url_for('research.manage_research'))
