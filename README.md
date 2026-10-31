# Digital Library & Research Management System

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1%2B-black.svg)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-3-lightgrey.svg)](https://www.sqlite.org/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-purple.svg)](https://getbootstrap.com/)
[![License](https://img.shields.io/badge/License-Academic%20Marathon-teal.svg)]()

A complete, production-grade, responsive multi-page web platform engineered for academic institutions to unify physical book circulation, digital academic paper distribution, member accounts, and librarian administration.

---

## 🏛️ Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
  - [Student / Member Capabilities](#student--member-capabilities)
  - [Admin / Librarian Capabilities](#admin--librarian-capabilities)
- [Technology Stack](#-technology-stack)
- [Architecture & Folder Structure](#-architecture--folder-structure)
- [Database Schema (All 7 Relational Tables)](#-database-schema-all-7-relational-tables)
- [Default Demonstration Logins](#-default-demonstration-logins)
- [REST API Reference](#-rest-api-reference)
- [Installation & Execution Guide](#-installation--execution-guide)
- [Automated Testing & Verification](#-automated-testing--verification)

---

## 🌟 Overview

The **Digital Library & Research Management System** modernizes collegiate library operations. It bridges physical book holdings with open-access digital scholarship:
- Eliminates manual paper registers and Excel spreadsheets.
- Implements atomic circulation transactions (reservation hold &rarr; librarian approval &rarr; copy decrement &rarr; return &rarr; copy increment).
- Automatically tracks loan periods (default 14 days) and synchronizes overdue statuses.
- Provides immediate open-access viewing and downloads for academic research papers in PDF format.
- Offers an interactive, modern user interface designed with a professional **Navy Blue & Teal** palette.

---

## 🚀 Key Features

### Student / Member Capabilities
1. **Self-Registration**: Sign up with institutional email, Student ID, academic department, and password.
2. **Secure Login & Session**: Session-based authentication with Werkzeug password hashing.
3. **Profile Management**: View account credentials, update phone and department, and change passwords.
4. **Complete Book Catalog**: Browse physical book holdings with realistic aspect-ratio cover cards.
5. **Search & Discovery**: Query catalog by title, author, and ISBN simultaneously.
6. **Multi-criteria Filtering**: Filter books by academic discipline, availability (*Available* vs *Out of Stock*), and sorting (*Title A-Z/Z-A*, *Publication Year Newest/Oldest*).
7. **Book Details**: Full bibliographic overview, publisher, ISBN, and physical shelf/location indicator.
8. **Live Copy Tracking**: Real-time counter of available copies vs. total library inventory.
9. **Instant Borrowing Requests**: Submit book hold requests with custom loan notes.
10. **Active Loans Portal**: Dedicated cockpit at `/my-books` displaying current book loans.
11. **Due Date Warnings**: Clear due date deadlines with automated overdue alert badges.
12. **Historical Borrowing Ledger**: Complete audit history of previous borrowings and returns at `/borrow-history`.
13. **Research Paper Library**: Explore faculty research, preprints, and academic journal articles.
14. **Research Filtering**: Search publications by title, author, subject area, keywords, or publication year.
15. **Full Abstract Viewer**: In-depth abstract reading with categorized keyword pills.
16. **PDF Document Delivery**: Stream or download peer-reviewed research papers in PDF format.
17. **Secure Logout**: Safe session invalidation.
18. **Role-Based Guards (RBAC)**: Non-admin users are strictly prevented from viewing administrative consoles.

### Admin / Librarian Capabilities
1. **Dedicated Cockpit**: Overview cockpit at `/admin/dashboard`.
2. **8 Real-time Summary Cards**: Dynamically calculated metrics derived directly from database rows:
   - Total Books
   - Total Available Copies
   - Total Registered Members
   - Total Research Papers
   - Currently Issued Books
   - Pending Borrowing Requests
   - Overdue Books
   - Returned Books
3. **Inventory Management**: Searchable and filterable inventory table at `/admin/books`.
4. **Add New Books**: Register books with automatic category creation and cover upload.
5. **Modify Books**: Edit book metadata, language, publisher, and physical shelf coordinates.
6. **Safe Book Deletion**: Guard mechanism that prevents deleting books with active student loans.
7. **Category Management**: Dedicated API (`/api/categories`) and automatic category indexing.
8. **Research Indexing**: Upload and index research papers with PDF document validation.
9. **Research Deletion**: Delete papers with automatic server-side PDF cleanup.
10. **Student Member Roster**: Complete searchable student directory at `/admin/members`.
11. **Member Audit**: Inspect individual student borrowing activity, active holds, and past checkouts.
12. **Account Suspension**: One-click toggle to activate or deactivate student borrowing privileges.
13. **Circulation Desk**: Process pending student borrowing holds at `/admin/issues`.
14. **Approval & Decrement**: Atomic transaction that assigns due date and decrements available copies by 1.
15. **Rejection with Remarks**: Decline requests with custom reasons visible to the student.
16. **Direct Counter Issue**: Manually issue any available book to any active student on demand.
17. **Return Recording**: Instant return processing that increments available copies by 1.
18. **Automatic Overdue Calculation**: Evaluates active loan dates on every dashboard load.
19. **Executive Reports & Analytics**: Departmental collection breakdown and most popular books at `/admin/reports`.
20. **Printable Layout**: Clean print stylesheet (`window.print()`) for institutional reporting.
21. **System Audit Trail**: Complete log of all administrative operations in the `activity_logs` table.
22. **Configurable Settings**: Dynamic API (`/api/settings`) to adjust borrowing duration and checkout limits.

---

## 🛠️ Technology Stack

| Layer | Technology | Specification / Role |
| :--- | :--- | :--- |
| **Frontend** | HTML5, CSS3, JavaScript (ES6+) | 23 multi-page Jinja2 templates, semantic markup, AJAX requests |
| **Styling** | Custom CSS3 + Bootstrap 5.3.3 | Navy Blue (`#0f172a`), Teal (`#0d9488`), Cyan (`#06b6d4`), Light Grey (`#f8fafc`) |
| **Backend** | Python 3.8+ & Flask 3.1+ | Application Factory pattern, 6 modular Blueprints, REST APIs |
| **Database** | SQLite3 (Built-in) | ACID compliance, foreign keys (`PRAGMA foreign_keys = ON`), transactions |
| **Security** | Werkzeug Security | Secure password hashing (`scrypt`/`pbkdf2`), session cookie RBAC |
| **Testing** | Python `unittest` | 18 comprehensive automated unit and integration tests |

---

## 📁 Architecture & Folder Structure

```text
Digital_Library/
│
├── app.py                      # Flask Application Factory & blueprint registration
├── database.py                 # SQLite schema, foreign keys, seeding, & transactions
├── requirements.txt            # Python dependencies (Flask, Werkzeug)
├── README.md                   # Comprehensive documentation & execution guide
├── .gitignore                  # Git hygiene rules
├── digital_library.db          # Active SQLite database file
│
├── routes/                     # Modular Flask Blueprints
│   ├── __init__.py             # Routes package marker
│   ├── auth.py                 # RBAC decorators & authentication controllers
│   ├── books.py                # Book catalog, filtering, and inventory CRUD
│   ├── research.py             # Academic repository, PDF streaming, & document indexing
│   ├── borrowing.py            # Circulation: hold requests, approvals, returns
│   ├── members.py              # Student roster & account activation/deactivation
│   └── dashboard.py            # Real-time analytics, landing page, & reports
│
├── templates/                  # 23 Multi-Page Jinja2 Templates
│   ├── base.html               # Shared layout (dynamic navbar, alerts, footer)
│   ├── index.html              # Landing page (Hero, search, live stats, highlights)
│   ├── about.html              # Institutional library rules & hours
│   ├── login.html              # Multi-role authentication page
│   ├── register.html           # Student registration portal
│   ├── student_dashboard.html  # Student metrics, active loans, & new titles
│   ├── books.html              # Public catalog grid with live filters
│   ├── book_details.html       # Bibliographic metadata & borrow actions
│   ├── research.html           # Research directory with subject/year filters
│   ├── research_details.html   # Full paper abstract & PDF document download
│   ├── my_books.html           # Active borrowed books & due dates
│   ├── borrow_history.html     # Historical checkout ledger
│   ├── profile.html            # Profile editor & password modification
│   ├── admin_dashboard.html    # Admin console with 8 metrics & audit log
│   ├── manage_books.html       # Book inventory table
│   ├── add_book.html           # New book registration form
│   ├── edit_book.html          # Existing book modification form
│   ├── manage_research.html    # Academic repository management
│   ├── add_research.html       # Research paper upload form
│   ├── manage_members.html     # Student membership roster
│   ├── member_details.html     # In-depth member profile & loan audit
│   ├── manage_issues.html      # Circulation desk: pending holds & returns
│   └── reports.html            # Statistical circulation & catalog reports
│
├── static/                     # Static UI Assets
│   ├── css/
│   │   └── style.css           # Custom theme stylesheet
│   ├── js/
│   │   └── script.js           # Client-side AJAX controller & toast alerts
│   └── images/
│       ├── default_book.svg    # Vector placeholder for books without custom covers
│       └── default_avatar.svg  # Vector placeholder for student & staff avatars
│
├── uploads/                    # Secure File Upload Storage
│   ├── book_covers/            # Uploaded book cover graphics
│   └── research_papers/        # Uploaded academic research PDF documents
│
├── tests/                      # Automated Test Suite
│   ├── __init__.py             # Test package marker
│   └── test_app.py             # 18 automated integration test cases
│
├── verify_stage1.py            # Stage 1 verification script
├── verify_stage2.py            # Stage 2 verification script
├── verify_stage3.py            # Stage 3 verification script
├── verify_stage4.py            # Stage 4 verification script
├── verify_stage5.py            # Stage 5 verification script
└── verify_stage6.py            # Stage 6 verification script
```

---

## 🗄️ Database Schema (All 7 Relational Tables)

The application utilizes an SQLite database named `digital_library.db` with strict foreign key constraints:

### 1. `users`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique user identifier |
| `name` | TEXT | NOT NULL | Member's full name |
| `email` | TEXT | UNIQUE NOT NULL | Institutional email address |
| `password_hash` | TEXT | NOT NULL | Secure Werkzeug password hash |
| `phone` | TEXT | | Contact phone number |
| `department` | TEXT | | Academic department / major |
| `student_id` | TEXT | | Registration / roll number |
| `profile_image` | TEXT | DEFAULT 'default_avatar.png' | Avatar image filename |
| `role` | TEXT | NOT NULL CHECK('student', 'admin') | Access control role |
| `status` | TEXT | NOT NULL CHECK('active', 'inactive') | Account operational status |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Registration timestamp |

### 2. `books`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique book ID |
| `isbn` | TEXT | UNIQUE | International Standard Book Number |
| `title` | TEXT | NOT NULL | Book title |
| `author` | TEXT | NOT NULL | Author(s) |
| `category` | TEXT | | Academic subject category |
| `publisher` | TEXT | | Publishing house |
| `publication_year` | INTEGER | | Year of publication |
| `language` | TEXT | DEFAULT 'English' | Language of text |
| `description` | TEXT | | Book synopsis |
| `cover_image` | TEXT | DEFAULT 'default_book.png' | Book artwork filename |
| `total_copies` | INTEGER | NOT NULL CHECK(&ge; 0) | Total copies owned |
| `available_copies` | INTEGER | NOT NULL CHECK(&ge; 0 AND &le; total) | Currently unborrowed copies |
| `shelf_location` | TEXT | | Physical library shelf coordinates |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Date cataloged |

### 3. `categories`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Category ID |
| `category_name` | TEXT | UNIQUE NOT NULL | Category name |
| `description` | TEXT | | Scope description |

### 4. `research_papers`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Research paper ID |
| `title` | TEXT | NOT NULL | Publication title |
| `author` | TEXT | NOT NULL | Research author(s) |
| `subject` | TEXT | | Academic field |
| `abstract` | TEXT | | Full academic abstract |
| `publication_year` | INTEGER | | Publication year |
| `journal_name` | TEXT | | Journal or conference venue |
| `keywords` | TEXT | | Comma-delimited keyword tags |
| `pdf_path` | TEXT | | Filename of uploaded PDF |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Indexing timestamp |

### 5. `borrow_records`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Circulation record ID |
| `user_id` | INTEGER | NOT NULL REFERENCES users(id) | Student member borrowing the book |
| `book_id` | INTEGER | NOT NULL REFERENCES books(id) | Book title borrowed |
| `request_date` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Hold submission timestamp |
| `issue_date` | DATE | | Physical checkout date |
| `due_date` | DATE | | Return deadline |
| `return_date` | DATE | | Check-in timestamp |
| `status` | TEXT | CHECK('Pending', 'Issued', 'Returned', 'Rejected', 'Overdue') | Current loan state |
| `approved_by` | INTEGER | REFERENCES users(id) | Approving librarian ID |
| `remarks` | TEXT | | Circulation notes |

### 6. `activity_logs`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Log entry ID |
| `user_id` | INTEGER | REFERENCES users(id) | Actor performing the operation |
| `action` | TEXT | NOT NULL | Operation classification |
| `description` | TEXT | | Detailed audit message |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Event timestamp |

### 7. `settings`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Setting ID |
| `setting_key` | TEXT | UNIQUE NOT NULL | Parameter key |
| `setting_value` | TEXT | | Configured parameter value |

---

## 🔑 Default Demonstration Logins

The application seeds default accounts for demonstration:

| Role | Name | Email Address | Password | Account Status |
| :--- | :--- | :--- | :--- | :--- |
| **Admin / Librarian** | Head Librarian | `admin@library.edu` | `Admin@12345` | `active` |
| **Student** | Alex Turner | `alex.turner@student.edu` | `Student@12345` | `active` |
| **Student** | Priya Sharma | `priya.sharma@student.edu` | `Student@12345` | `active` |
| **Student (Suspended)** | Marcus Vance | `marcus.vance@student.edu` | `Student@12345` | `inactive` |

---

## 📡 REST API Reference

All REST endpoints return standardized JSON structures.

### Authentication
- `POST /api/register` – Register student account.
- `POST /api/login` – Sign in and establish session.
- `POST /api/logout` – Clear session.
- `GET /api/profile` – Retrieve authenticated profile.

### Books
- `GET /api/books` – Search and filter books (`?q=...&category=...&availability=...&sort=...`).
- `GET /api/books/<id>` – Retrieve single book record.
- `POST /api/books` – Add new book (*Admin*).
- `PUT /api/books/<id>` – Update book details (*Admin*).
- `DELETE /api/books/<id>` – Delete book (*Admin*).
- `GET /api/categories` – List all book categories.
- `POST /api/categories` – Create new category (*Admin*).

### Research Papers
- `GET /api/research` – Search publications (`?q=...&subject=...&year=...`).
- `GET /api/research/<id>` – Retrieve paper details.
- `POST /api/research` – Upload/index paper (*Admin*).
- `PUT /api/research/<id>` – Edit paper details (*Admin*).
- `DELETE /api/research/<id>` – Delete paper and remove PDF (*Admin*).

### Borrowing & Circulation
- `POST /api/borrow/request` – Submit borrowing hold (*Student*).
- `GET /api/borrow/my-records` – Current student's loans and history (*Student*).
- `GET /api/borrow/all-records` – Master circulation ledger (*Admin*).
- `PUT /api/borrow/approve/<id>` – Approve request and decrement available copy (*Admin*).
- `PUT /api/borrow/reject/<id>` – Decline request with reason (*Admin*).
- `PUT /api/borrow/return/<id>` – Process return and increment available copy (*Admin*).

### Member Management & Dashboards
- `GET /api/members` – Search student directory (*Admin*).
- `GET /api/members/<id>` – Retrieve student loan history (*Admin*).
- `PUT /api/members/<id>/status` – Activate/deactivate account (*Admin*).
- `GET /api/dashboard/student` – Student personal loan counters (*Student*).
- `GET /api/dashboard/admin` – 8 calculated library metrics (*Admin*).
- `GET /api/activity-logs` – System audit trail logs (*Admin*).
- `GET /api/settings` – View configurable library settings (*Admin*).
- `PUT /api/settings` – Update library parameters (*Admin*).

---

## 💻 Installation & Execution Guide

### Prerequisites
- Python 3.8 or higher.
- Git.

### 1. Clone the Repository
```powershell
git clone <repository-url>
cd Digital_Library
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Initialize the Database & Seed Demonstration Data
```powershell
python database.py
```

### 4. Run the Web Application
```powershell
python app.py
```
Open your browser and navigate to:
**`http://127.0.0.1:5000`**

---

## 🧪 Automated Testing & Verification

The project includes automated verification test scripts:

### 1. Run the Full Unit Test Suite (`unittest`)
```powershell
python -m unittest tests/test_app.py
```
*Executes all 18 unit tests covering authentication, RBAC, book CRUD, paper delivery, and atomic circulation transactions.*

### 2. Run Stage-by-Stage Verification Scripts
```powershell
python verify_stage1.py   # Verifies project folder architecture & dependencies
python verify_stage2.py   # Verifies SQLite database, 7 tables, & relationships
python verify_stage3.py   # Parses & compiles all 23 Jinja2 HTML templates
python verify_stage4.py   # Tests Flask backend routes & REST APIs
python verify_stage5.py   # Tests complete end-to-end user journeys & database sync
python verify_stage6.py   # Tests all 18 student & 24 admin capabilities
```

---

## 🏆 Project Accomplishments

- **Zero Missing Buttons or Dead Ends**: Every single card, link, form, modal, and button performs real backend operations.
- **Zero Hardcoded Counters**: All 8 dashboard statistics are computed live via SQL aggregation.
- **Safe Transactions**: Prevents duplicate active issues, enforces copy count constraints, and automatically synchronizes overdue states.
- **Academic Ready**: Fully compliant with college marathon evaluation criteria.
