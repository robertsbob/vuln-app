import sqlite3
import hashlib
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'meridian.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def hash_password(password):
    # MD5 hashing - no salt
    return hashlib.md5(password.encode()).hexdigest()


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'client',
            is_active INTEGER NOT NULL DEFAULT 1,
            reset_token TEXT,
            reset_token_expiry INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            industry TEXT,
            owner_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            client_id INTEGER,
            assigned_to TEXT,
            status TEXT DEFAULT 'active',
            budget REAL DEFAULT 0,
            budget_remaining REAL DEFAULT 0,
            start_date TEXT,
            end_date TEXT,
            created_by INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            client_id INTEGER,
            client_name TEXT,
            description TEXT,
            amount REAL,
            status TEXT DEFAULT 'draft',
            due_date TEXT,
            created_by INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            notes TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            description TEXT,
            client_id INTEGER,
            project_id INTEGER,
            uploaded_by INTEGER,
            uploaded_at TEXT DEFAULT (datetime('now')),
            file_size INTEGER,
            is_confidential INTEGER DEFAULT 0,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            submitted_by INTEGER,
            amount REAL,
            category TEXT,
            description TEXT,
            status TEXT DEFAULT 'pending',
            receipt_filename TEXT,
            submitted_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (submitted_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            webhook_url TEXT,
            event_type TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            target_type TEXT,
            target_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    conn.commit()
    conn.close()
