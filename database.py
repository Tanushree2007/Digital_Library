"""
Database Module for Digital Library & Research Management System
SQLite3 database architecture with ACID transactions, foreign keys, 
indexes, sample data seeding, and helper utilities.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# Path to the SQLite database file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "digital_library.db")


def get_db_connection():
    """
    Creates and returns a connection to the SQLite database.
    - Sets row_factory = sqlite3.Row for dictionary-like column access.
    - Enforces foreign key constraint checks.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """
    Creates all seven tables, constraints, and performance indexes.
    Safe to execute multiple times (uses CREATE TABLE IF NOT EXISTS).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table (Students and Librarians/Admins)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        phone TEXT,
        department TEXT,
        student_id TEXT,
        profile_image TEXT DEFAULT 'default_avatar.png',
        role TEXT NOT NULL CHECK(role IN ('student', 'admin')),
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Categories Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_name TEXT UNIQUE NOT NULL,
        description TEXT
    );
    """)

    # 3. Books Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        isbn TEXT UNIQUE,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        category TEXT,
        publisher TEXT,
        publication_year INTEGER,
        language TEXT DEFAULT 'English',
        description TEXT,
        cover_image TEXT DEFAULT 'default_book.png',
        total_copies INTEGER NOT NULL CHECK(total_copies >= 0),
        available_copies INTEGER NOT NULL CHECK(available_copies >= 0 AND available_copies <= total_copies),
        shelf_location TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Research Papers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS research_papers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        subject TEXT,
        abstract TEXT,
        publication_year INTEGER,
        journal_name TEXT,
        keywords TEXT,
        pdf_path TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 5. Borrow Records Table (Book Circulation)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS borrow_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        request_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        issue_date DATE,
        due_date DATE,
        return_date DATE,
        status TEXT NOT NULL CHECK(status IN ('Pending', 'Issued', 'Returned', 'Rejected', 'Overdue')),
        approved_by INTEGER,
        remarks TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE,
        FOREIGN KEY (approved_by) REFERENCES users (id) ON DELETE SET NULL
    );
    """)

    # 6. Activity Logs Table (System audit & history)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        description TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
    );
    """)

    # 7. Settings Table (Configurable parameters like loan duration)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setting_key TEXT UNIQUE NOT NULL,
        setting_value TEXT
    );
    """)

    # Create Performance Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role_status ON users(role, status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_category ON books(category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_borrow_user_status ON borrow_records(user_id, status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_borrow_book_status ON borrow_records(book_id, status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_research_subject ON research_papers(subject);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_research_year ON research_papers(publication_year);")

    conn.commit()
    conn.close()


def seed_sample_data():
    """
    Inserts initial configuration settings, categories, demo books, 
    research papers, default admin/student accounts, and borrowing records.
    Safe against duplication on restarts (checks existence first).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Seed Settings
    settings_data = [
        ("borrowing_period_days", "14"),
        ("max_books_per_student", "3"),
        ("library_name", "Digital Library & Research Management System"),
        ("contact_email", "librarian@collegelibrary.edu"),
        ("late_fee_per_day", "1.00"),
    ]
    for key, val in settings_data:
        cursor.execute("""
            INSERT OR IGNORE INTO settings (setting_key, setting_value)
            VALUES (?, ?)
        """, (key, val))

    # 2. Seed Categories
    categories_data = [
        ("Computer Science & Engineering", "Foundations of algorithms, architectures, operating systems, and computation."),
        ("Artificial Intelligence & Data Science", "Machine learning, neural networks, computer vision, and big data analysis."),
        ("Software Engineering & Web Development", "Software design patterns, agile engineering, full-stack web, and DevOps."),
        ("Mathematics & Statistics", "Discrete mathematics, linear algebra, probability, and numerical methods."),
        ("Cybersecurity & Cryptography", "Information assurance, network security protocols, ethical hacking, and crypto."),
        ("Physics & Quantum Computing", "Classical physics, quantum information theory, and quantum hardware architecture."),
        ("General Sciences & Humanities", "Scientific ethics, academic research methodologies, and technical writing.")
    ]
    for cat_name, desc in categories_data:
        cursor.execute("""
            INSERT OR IGNORE INTO categories (category_name, description)
            VALUES (?, ?)
        """, (cat_name, desc))

    # 3. Seed Users (Admin & Students)
    # Check if admin already exists
    cursor.execute("SELECT id FROM users WHERE email = ?", ("admin@library.edu",))
    if not cursor.fetchone():
        admin_hash = generate_password_hash("Admin@12345")
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, phone, department, student_id, role, status)
            VALUES (?, ?, ?, ?, ?, ?, 'admin', 'active')
        """, (
            "Head Librarian (Admin)",
            "admin@library.edu",
            admin_hash,
            "+1-555-0100",
            "Library Services & Administration",
            "LIB-ADM-01"
        ))

    # Student 1: Alex Turner
    cursor.execute("SELECT id FROM users WHERE email = ?", ("alex.turner@student.edu",))
    if not cursor.fetchone():
        student1_hash = generate_password_hash("Student@12345")
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, phone, department, student_id, role, status)
            VALUES (?, ?, ?, ?, ?, ?, 'student', 'active')
        """, (
            "Alex Turner",
            "alex.turner@student.edu",
            student1_hash,
            "+1-555-0192",
            "Computer Science & Engineering",
            "CS-2024-042"
        ))

    # Student 2: Priya Sharma
    cursor.execute("SELECT id FROM users WHERE email = ?", ("priya.sharma@student.edu",))
    if not cursor.fetchone():
        student2_hash = generate_password_hash("Student@12345")
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, phone, department, student_id, role, status)
            VALUES (?, ?, ?, ?, ?, ?, 'student', 'active')
        """, (
            "Priya Sharma",
            "priya.sharma@student.edu",
            student2_hash,
            "+1-555-0198",
            "Artificial Intelligence & Data Science",
            "AI-2024-115"
        ))

    # Student 3: Marcus Vance (Inactive student for testing admin account management)
    cursor.execute("SELECT id FROM users WHERE email = ?", ("marcus.vance@student.edu",))
    if not cursor.fetchone():
        student3_hash = generate_password_hash("Student@12345")
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, phone, department, student_id, role, status)
            VALUES (?, ?, ?, ?, ?, ?, 'student', 'inactive')
        """, (
            "Marcus Vance",
            "marcus.vance@student.edu",
            student3_hash,
            "+1-555-0214",
            "Software Engineering & Web Development",
            "SE-2024-089"
        ))

    # 4. Seed Books
    books_data = [
        (
            "978-0134494166",
            "Clean Architecture: A Craftsman's Guide to Software Structure",
            "Robert C. Martin",
            "Software Engineering & Web Development",
            "Prentice Hall",
            2017,
            "English",
            "Essential rules and architectural principles for building maintainable, robust, scalable, and testable enterprise applications.",
            "clean_architecture.jpg",
            5,
            4,
            "Shelf A-12, 2nd Floor"
        ),
        (
            "978-0262046305",
            "Introduction to Algorithms (4th Edition)",
            "Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein",
            "Computer Science & Engineering",
            "MIT Press",
            2022,
            "English",
            "The premier textbook and reference work covering comprehensive algorithms, data structures, dynamic programming, and complexity analysis.",
            "intro_algorithms.jpg",
            4,
            3,
            "Shelf B-04, 2nd Floor"
        ),
        (
            "978-0262035613",
            "Deep Learning",
            "Ian Goodfellow, Yoshua Bengio, Aaron Courville",
            "Artificial Intelligence & Data Science",
            "MIT Press",
            2016,
            "English",
            "Theoretical and practical foundations of deep learning covering linear algebra, convolutional networks, and generative modeling.",
            "deep_learning.jpg",
            3,
            2,
            "Shelf C-08, 3rd Floor"
        ),
        (
            "978-1449373320",
            "Designing Data-Intensive Applications",
            "Martin Kleppmann",
            "Computer Science & Engineering",
            "O'Reilly Media",
            2017,
            "English",
            "An indispensable guide navigating data systems, distributed consistency, stream processing, batch pipelines, and scalability.",
            "designing_data_intensive.jpg",
            4,
            3,
            "Shelf A-07, 2nd Floor"
        ),
        (
            "978-0134610993",
            "Artificial Intelligence: A Modern Approach (4th Edition)",
            "Stuart Russell, Peter Norvig",
            "Artificial Intelligence & Data Science",
            "Pearson",
            2020,
            "English",
            "The globally celebrated textbook introducing AI principles, probabilistic reasoning, machine learning, search agents, and robotics.",
            "modern_ai.jpg",
            5,
            4,
            "Shelf C-01, 3rd Floor"
        ),
        (
            "978-0135957059",
            "The Pragmatic Programmer: Your Journey To Mastery",
            "David Thomas, Andrew Hunt",
            "Software Engineering & Web Development",
            "Addison-Wesley Professional",
            2019,
            "English",
            "Classic wisdom on software craftsmanship, career mastery, defensive coding, testing strategies, and pragmatic architecture.",
            "pragmatic_programmer.jpg",
            4,
            4,
            "Shelf A-03, 2nd Floor"
        ),
        (
            "978-1118063330",
            "Operating System Concepts (10th Edition)",
            "Abraham Silberschatz, Peter B. Galvin, Greg Gagne",
            "Computer Science & Engineering",
            "Wiley",
            2018,
            "English",
            "Fundamental operating system mechanisms covering concurrency, CPU scheduling, virtual memory, file systems, and kernel protection.",
            "operating_systems.jpg",
            3,
            2,
            "Shelf B-09, 2nd Floor"
        ),
        (
            "978-0136681557",
            "Computer Networking: A Top-Down Approach (8th Edition)",
            "James F. Kurose, Keith W. Ross",
            "Computer Science & Engineering",
            "Pearson",
            2021,
            "English",
            "Structured top-down pedagogy presenting internet protocols, application layer architecture, transport reliability, and routing.",
            "computer_networking.jpg",
            3,
            3,
            "Shelf B-11, 2nd Floor"
        ),
        (
            "978-0134444284",
            "Cryptography and Network Security: Principles and Practice",
            "William Stallings",
            "Cybersecurity & Cryptography",
            "Pearson",
            2017,
            "English",
            "Rigorous mathematical treatment of symmetric cipher suites, RSA, elliptic curve cryptography, digital signatures, and web security.",
            "cryptography_security.jpg",
            2,
            2,
            "Shelf D-02, 3rd Floor"
        ),
        (
            "978-0470096994",
            "Quantum Computing Explained",
            "David McMahon",
            "Physics & Quantum Computing",
            "Wiley-Interscience",
            2007,
            "English",
            "Clear tutorial introduction to qubits, superposition, quantum entanglement, and quantum computing algorithms. (Sample: Out of Stock)",
            "quantum_computing.jpg",
            1,
            0,
            "Shelf E-01, 3rd Floor"
        )
    ]

    for b in books_data:
        cursor.execute("""
            INSERT OR IGNORE INTO books (
                isbn, title, author, category, publisher, publication_year, 
                language, description, cover_image, total_copies, available_copies, shelf_location
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, b)

    # 5. Seed Research Papers
    research_papers_data = [
        (
            "Attention Is All You Need: Modern Transformer Architectures in NLP",
            "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit",
            "Artificial Intelligence & Data Science",
            "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose the Transformer, an architecture based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.",
            2017,
            "Advances in Neural Information Processing Systems (NeurIPS)",
            "Transformer, Attention Mechanism, NLP, Deep Learning, Sequence Modeling",
            "attention_is_all_you_need.pdf"
        ),
        (
            "Spanner: Google's Globally-Distributed Database",
            "James C. Corbett, Jeffrey Dean, Michael Epstein, Andrew Fikes",
            "Computer Science & Engineering",
            "Spanner is Google's scalable, multi-version, globally-distributed, and synchronously-replicated database. It provides externally consistent distributed transactions globally using the TrueTime API backed by atomic clocks and GPS receivers.",
            2013,
            "ACM Transactions on Computer Systems (TOCS)",
            "Distributed Systems, Spanner, TrueTime, ACID Transactions, Replicated DB",
            "spanner_globally_distributed_db.pdf"
        ),
        (
            "A Survey on Deep Learning for Modern Cybersecurity Defenses",
            "Dr. Elena Rostova, Kenneth Vance, Rajiv Nair",
            "Cybersecurity & Cryptography",
            "This survey provides an in-depth review of deep learning methodologies in detecting zero-day intrusions, advanced persistent threats (APTs), and binary malware analysis, benchmarked across modern network intrusion datasets.",
            2023,
            "IEEE Transactions on Information Forensics and Security",
            "Cybersecurity, Intrusion Detection, Malware Analysis, Deep Learning, Threat Hunting",
            "deep_learning_cybersecurity_survey.pdf"
        ),
        (
            "Microservices Architecture in Enterprise Web Platforms: Patterns and Resilience",
            "Sarah Jenkins, Robert Davies",
            "Software Engineering & Web Development",
            "An empirical investigation into architectural resilience patterns including circuit breakers, asynchronous event-driven sagas, and API gateways in mission-critical cloud deployments.",
            2024,
            "Journal of Systems and Software",
            "Microservices, Distributed Architectures, Fault Tolerance, Event Sourcing, REST APIs",
            "microservices_enterprise_resilience.pdf"
        )
    ]

    for p in research_papers_data:
        cursor.execute("SELECT id FROM research_papers WHERE title = ?", (p[0],))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO research_papers (
                    title, author, subject, abstract, publication_year, 
                    journal_name, keywords, pdf_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, p)

    # 6. Seed Realistic Borrow Records
    # Fetch student Alex Turner and Admin ID
    cursor.execute("SELECT id FROM users WHERE email = ?", ("alex.turner@student.edu",))
    student_alex = cursor.fetchone()
    cursor.execute("SELECT id FROM users WHERE email = ?", ("priya.sharma@student.edu",))
    student_priya = cursor.fetchone()
    cursor.execute("SELECT id FROM users WHERE email = ?", ("admin@library.edu",))
    admin_user = cursor.fetchone()

    # Fetch books
    cursor.execute("SELECT id FROM books WHERE isbn = ?", ("978-0134494166",))  # Clean Architecture
    book_clean_arch = cursor.fetchone()
    cursor.execute("SELECT id FROM books WHERE isbn = ?", ("978-1118063330",))  # Operating System Concepts
    book_os = cursor.fetchone()
    cursor.execute("SELECT id FROM books WHERE isbn = ?", ("978-0262046305",))  # Introduction to Algorithms
    book_algo = cursor.fetchone()
    cursor.execute("SELECT id FROM books WHERE isbn = ?", ("978-0262035613",))  # Deep Learning
    book_dl = cursor.fetchone()

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    if student_alex and admin_user:
        alex_id = student_alex["id"]
        admin_id = admin_user["id"]

        # Record 1: Currently Issued book (Issued 5 days ago, due in 9 days)
        if book_clean_arch:
            cursor.execute("""
                SELECT id FROM borrow_records 
                WHERE user_id = ? AND book_id = ? AND status = 'Issued'
            """, (alex_id, book_clean_arch["id"]))
            if not cursor.fetchone():
                req_date = (now - timedelta(days=6)).strftime("%Y-%m-%d %H:%M:%S")
                issue_date = (now - timedelta(days=5)).strftime("%Y-%m-%d")
                due_date = (now + timedelta(days=9)).strftime("%Y-%m-%d")
                cursor.execute("""
                    INSERT INTO borrow_records (
                        user_id, book_id, request_date, issue_date, due_date, status, approved_by, remarks
                    ) VALUES (?, ?, ?, ?, ?, 'Issued', ?, 'Approved for course semester project')
                """, (alex_id, book_clean_arch["id"], req_date, issue_date, due_date, admin_id))

        # Record 2: Overdue book (Issued 25 days ago, due 11 days ago)
        if book_os:
            cursor.execute("""
                SELECT id FROM borrow_records 
                WHERE user_id = ? AND book_id = ? AND status = 'Overdue'
            """, (alex_id, book_os["id"]))
            if not cursor.fetchone():
                req_date = (now - timedelta(days=26)).strftime("%Y-%m-%d %H:%M:%S")
                issue_date = (now - timedelta(days=25)).strftime("%Y-%m-%d")
                due_date = (now - timedelta(days=11)).strftime("%Y-%m-%d")
                cursor.execute("""
                    INSERT INTO borrow_records (
                        user_id, book_id, request_date, issue_date, due_date, status, approved_by, remarks
                    ) VALUES (?, ?, ?, ?, ?, 'Overdue', ?, 'Overdue notification sent to member')
                """, (alex_id, book_os["id"], req_date, issue_date, due_date, admin_id))

    if student_priya and admin_user:
        priya_id = student_priya["id"]
        admin_id = admin_user["id"]

        # Record 3: Pending borrowing request (Requested yesterday)
        if book_algo:
            cursor.execute("""
                SELECT id FROM borrow_records 
                WHERE user_id = ? AND book_id = ? AND status = 'Pending'
            """, (priya_id, book_algo["id"]))
            if not cursor.fetchone():
                req_date = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO borrow_records (
                        user_id, book_id, request_date, status, remarks
                    ) VALUES (?, ?, ?, 'Pending', 'Requested for competitive programming preparation')
                """, (priya_id, book_algo["id"], req_date))

        # Record 4: Completed Returned book
        if book_dl:
            cursor.execute("""
                SELECT id FROM borrow_records 
                WHERE user_id = ? AND book_id = ? AND status = 'Returned'
            """, (priya_id, book_dl["id"]))
            if not cursor.fetchone():
                req_date = (now - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
                issue_date = (now - timedelta(days=38)).strftime("%Y-%m-%d")
                due_date = (now - timedelta(days=24)).strftime("%Y-%m-%d")
                return_date = (now - timedelta(days=26)).strftime("%Y-%m-%d")
                cursor.execute("""
                    INSERT INTO borrow_records (
                        user_id, book_id, request_date, issue_date, due_date, return_date, status, approved_by, remarks
                    ) VALUES (?, ?, ?, ?, ?, ?, 'Returned', ?, 'Returned in pristine condition')
                """, (priya_id, book_dl["id"], req_date, issue_date, due_date, return_date, admin_id))

    # 7. Seed Initial Activity Logs
    cursor.execute("SELECT COUNT(*) as count FROM activity_logs")
    if cursor.fetchone()["count"] == 0:
        cursor.execute("""
            INSERT INTO activity_logs (user_id, action, description)
            VALUES (1, 'System Initialization', 'Digital Library & Research Management System initialized with default catalogs and schemas.')
        """)

    conn.commit()
    conn.close()


def update_overdue_statuses():
    """
    Checks all active 'Issued' records and marks them 'Overdue' if due_date < today.
    Runs automatically on system startup and dashboard loads.
    """
    conn = get_db_connection()
    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE borrow_records
        SET status = 'Overdue'
        WHERE status = 'Issued' AND due_date < ?
    """, (today_str,))
    updated_count = cursor.rowcount
    conn.commit()
    conn.close()
    return updated_count


def log_activity(user_id, action, description):
    """
    Appends an audit entry into activity_logs table.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO activity_logs (user_id, action, description)
            VALUES (?, ?, ?)
        """, (user_id, action, description))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to log activity: {e}")


if __name__ == "__main__":
    print("=" * 70)
    print("INITIALIZING DIGITAL LIBRARY SQLITE DATABASE...")
    print("=" * 70)
    init_db()
    print("[SUCCESS] All 7 tables, constraints, and indexes created successfully.")
    seed_sample_data()
    print("[SUCCESS] Sample demonstration data seeded successfully.")
    overdue_updates = update_overdue_statuses()
    print(f"[SUCCESS] Checked and synchronized overdue statuses (Updated: {overdue_updates}).")
    print("=" * 70)
    print(f"Database location: {DATABASE_PATH}")
    print("=" * 70)
