import os
import io
import time
import base64
import pickle
import hashlib
import functools
import requests
import jwt
import urllib.request

from flask import (
    Flask, render_template, render_template_string, request,
    redirect, url_for, session, jsonify, send_file, abort, flash, g,
    send_from_directory
)
from lxml import etree
from database import get_db, hash_password, init_db

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = 'meridian_secret_2023'          # Weak, hardcoded secret key
app.config['DATABASE'] = 'meridian.db'
app.config['DEBUG'] = True                        # Debug mode left on in production
app.config['SESSION_COOKIE_HTTPONLY'] = False     # Allows JS access to session cookie
app.config['SESSION_COOKIE_SECURE'] = False       # Cookie sent over HTTP too
app.config['SESSION_COOKIE_SAMESITE'] = None      # No SameSite protection

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'documents')
os.makedirs(UPLOAD_DIR, exist_ok=True)

JWT_SECRET = 'meridian2023'                       # Weak JWT secret, discoverable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    if 'user_id' not in session:
        return None
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    db.close()
    return user


@app.before_request
def load_user():
    g.user = get_current_user()


@app.after_request
def add_headers(response):
    # CORS misconfiguration: wildcard origin with credentials allowed
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-API-Key'
    # No Content-Security-Policy
    # No X-Frame-Options      (clickjacking possible)
    # No X-Content-Type-Options
    # No Strict-Transport-Security
    return response


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/robots.txt')
def robots_txt():
    # Realistic robots.txt — hints at interesting paths for reconnaissance
    content = """User-agent: *
Disallow: /admin/
Disallow: /api/
Disallow: /reports/
Disallow: /static/uploads/

# Internal tools (not for public indexing)
Disallow: /api/v1/debug/
Disallow: /.git/
Disallow: /files/

Sitemap: https://portal.meridian-consulting.com/sitemap.xml
"""
    return content, 200, {'Content-Type': 'text/plain'}


# Exposed .git directory — misconfiguration: app deployed from git repo root
# A real web server (nginx/apache) would serve this directory; Flask mimics that here
@app.route('/.git/<path:filename>')
def git_expose(filename):
    git_dir = os.path.join(os.path.dirname(__file__), '.git')
    try:
        return send_from_directory(git_dir, filename)
    except Exception:
        abort(404)


@app.route('/.git/HEAD')
def git_head():
    git_dir = os.path.join(os.path.dirname(__file__), '.git')
    try:
        return send_from_directory(git_dir, 'HEAD')
    except Exception:
        abort(404)


@app.route('/auth/login', methods=['GET', 'POST'])
def login():
    # Session fixation: allow setting session id from URL param
    if request.args.get('sid'):
        session['_id'] = request.args.get('sid')

    next_url = request.args.get('next', '/dashboard')
    error = None

    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        next_url = request.form.get('next', '/dashboard')

        db = get_db()
        pwd_hash = hash_password(password)

        # SQL Injection: string concatenation in login query
        query = f"SELECT * FROM users WHERE email = '{email}' AND password_hash = '{pwd_hash}'"
        try:
            user = db.execute(query).fetchone()
        except Exception as e:
            # Verbose error message leaks query structure
            error = f"Database error: {e}"
            db.close()
            return render_template('auth/login.html', error=error, next=next_url)

        if user is None:
            # Check if user exists at all (account enumeration)
            user_exists = db.execute(f"SELECT id FROM users WHERE email = '{email}'").fetchone()
            if user_exists:
                error = "Incorrect password. Please try again."
            else:
                error = "No account found with that email address."
            db.close()
            return render_template('auth/login.html', error=error, next=next_url)

        if not user['is_active']:
            error = "Your account has been deactivated. Contact support."
            db.close()
            return render_template('auth/login.html', error=error, next=next_url)

        session.clear()
        session['user_id'] = user['id']
        session['role'] = user['role']
        session['display_name'] = user['display_name']
        db.close()

        # Open redirect: next_url not validated
        return redirect(next_url)

    return render_template('auth/login.html', error=error, next=next_url)


@app.route('/auth/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        display_name = request.form.get('display_name', '').strip()
        if not email or not password or not display_name:
            error = "All fields are required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            db = get_db()
            existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                error = "An account with that email already exists."
                db.close()
            else:
                # display_name stored as-is (parameterized here, but used raw in /projects later)
                db.execute(
                    "INSERT INTO users (email, password_hash, display_name, role) VALUES (?,?,?,?)",
                    (email, hash_password(password), display_name, 'client')
                )
                db.commit()
                db.close()
                flash("Account created. Please sign in.", "success")
                return redirect(url_for('login'))
    return render_template('auth/register.html', error=error)


@app.route('/auth/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/auth/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    submitted = False
    if request.method == 'POST':
        email = request.form.get('email', '')
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            # Predictable token: current Unix timestamp
            token = str(int(time.time()))
            db.execute("UPDATE users SET reset_token = ?, reset_token_expiry = ? WHERE id = ?",
                       (token, int(time.time()) + 3600, user['id']))
            conn = db
            conn.commit()
            # In a real app, this would send an email. Here we flash the token for "dev convenience".
            flash(f"[DEV MODE] Reset link: /auth/reset-password?token={token}", "info")
            submitted = True
        else:
            # Account enumeration via different response
            flash("No account found with that email address.", "error")
        db.close()
    return render_template('auth/forgot_password.html', submitted=submitted)


@app.route('/auth/reset-password', methods=['GET', 'POST'])
def reset_password():
    token = request.args.get('token', '')
    error = None
    success = False

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE reset_token = ?", (token,)).fetchone()

    if not user:
        return render_template('auth/reset_password.html', error="Invalid or expired reset link.", token=token)

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            db.execute("UPDATE users SET password_hash = ?, reset_token = NULL WHERE id = ?",
                       (hash_password(password), user['id']))
            db.commit()
            success = True
    db.close()
    return render_template('auth/reset_password.html', error=error, success=success, token=token)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    user = g.user

    recent_invoices = db.execute(
        "SELECT * FROM invoices ORDER BY created_at DESC LIMIT 5"
    ).fetchall()

    active_projects = db.execute(
        "SELECT p.*, c.company_name FROM projects p "
        "JOIN clients c ON p.client_id = c.id "
        "WHERE p.status = 'active' ORDER BY p.created_at DESC LIMIT 4"
    ).fetchall()

    stats = {
        'total_clients': db.execute("SELECT COUNT(*) FROM clients").fetchone()[0],
        'active_projects': db.execute("SELECT COUNT(*) FROM projects WHERE status='active'").fetchone()[0],
        'pending_invoices': db.execute("SELECT COUNT(*) FROM invoices WHERE status IN ('draft','submitted')").fetchone()[0],
        'total_revenue': db.execute("SELECT COALESCE(SUM(amount),0) FROM invoices WHERE status='paid'").fetchone()[0],
    }
    db.close()
    return render_template('dashboard.html', recent_invoices=recent_invoices,
                           active_projects=active_projects, stats=stats)


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

@app.route('/clients')
@login_required
def clients_list():
    q = request.args.get('q', '')
    db = get_db()
    user_id = session['user_id']

    if q:
        # SQL Injection: user input concatenated into query
        query = f"SELECT * FROM clients WHERE (company_name LIKE '%{q}%' OR contact_name LIKE '%{q}%' OR email LIKE '%{q}%')"
        try:
            clients = db.execute(query).fetchall()
        except Exception as e:
            flash(f"Search error: {e}", "error")
            clients = []
    else:
        clients = db.execute("SELECT * FROM clients ORDER BY company_name").fetchall()

    db.close()
    return render_template('clients/list.html', clients=clients, q=q)


@app.route('/clients/create', methods=['GET', 'POST'])
@login_required
def clients_create():
    if session.get('role') not in ('admin', 'consultant'):
        abort(403)
    if request.method == 'POST':
        db = get_db()
        db.execute(
            "INSERT INTO clients (company_name, contact_name, email, phone, address, industry, owner_id) VALUES (?,?,?,?,?,?,?)",
            (request.form['company_name'], request.form['contact_name'],
             request.form.get('email'), request.form.get('phone'),
             request.form.get('address'), request.form.get('industry'),
             session['user_id'])
        )
        db.commit()
        db.close()
        flash("Client created successfully.", "success")
        return redirect(url_for('clients_list'))
    return render_template('clients/create.html')


@app.route('/clients/<int:client_id>')
@login_required
def clients_detail(client_id):
    db = get_db()
    # IDOR: no ownership/role check
    client = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        abort(404)
    projects = db.execute("SELECT * FROM projects WHERE client_id = ?", (client_id,)).fetchall()
    invoices = db.execute("SELECT * FROM invoices WHERE client_id = ? ORDER BY created_at DESC", (client_id,)).fetchall()
    db.close()
    return render_template('clients/detail.html', client=client, projects=projects, invoices=invoices)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@app.route('/invoices')
@login_required
def invoices_list():
    search = request.args.get('search', '')
    db = get_db()

    if search:
        # SQL Injection: search term concatenated directly
        query = f"SELECT * FROM invoices WHERE status != 'deleted' AND (client_name LIKE '%{search}%' OR description LIKE '%{search}%' OR invoice_number LIKE '%{search}%') ORDER BY created_at DESC"
        try:
            invoices = db.execute(query).fetchall()
        except Exception as e:
            flash(f"Search error: {e}", "error")
            invoices = []
    else:
        invoices = db.execute(
            "SELECT * FROM invoices WHERE status != 'deleted' ORDER BY created_at DESC"
        ).fetchall()

    db.close()
    return render_template('invoices/list.html', invoices=invoices, search=search)


@app.route('/invoices/create', methods=['GET', 'POST'])
@login_required
def invoices_create():
    if session.get('role') not in ('admin', 'consultant'):
        abort(403)
    db = get_db()
    clients = db.execute("SELECT * FROM clients ORDER BY company_name").fetchall()

    if request.method == 'POST':
        import random
        inv_num = f"INV-{time.strftime('%Y')}-{random.randint(100,999)}"
        # No amount validation: negative amounts accepted
        db.execute(
            "INSERT INTO invoices (invoice_number, client_id, client_name, description, amount, status, due_date, created_by, notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (inv_num, request.form.get('client_id'), request.form.get('client_name'),
             request.form.get('description'), request.form.get('amount'),
             'draft', request.form.get('due_date'), session['user_id'],
             request.form.get('notes', ''))
        )
        db.commit()
        db.close()
        flash("Invoice created.", "success")
        return redirect(url_for('invoices_list'))

    db.close()
    return render_template('invoices/create.html', clients=clients)


@app.route('/invoices/<int:invoice_id>')
@login_required
def invoices_detail(invoice_id):
    db = get_db()
    # IDOR: no ownership check — any authenticated user can view any invoice
    invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not invoice:
        abort(404)
    db.close()
    return render_template('invoices/detail.html', invoice=invoice)


@app.route('/invoices/<int:invoice_id>/update', methods=['POST'])
@login_required
def invoices_update(invoice_id):
    db = get_db()
    invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not invoice:
        abort(404)

    # Business logic flaw: no status transition validation
    new_status = request.form.get('status', invoice['status'])
    new_amount = request.form.get('amount', invoice['amount'])
    new_notes  = request.form.get('notes', invoice['notes'])

    db.execute(
        "UPDATE invoices SET status=?, amount=?, notes=? WHERE id=?",
        (new_status, new_amount, new_notes, invoice_id)
    )
    db.commit()
    db.close()
    flash("Invoice updated.", "success")
    return redirect(url_for('invoices_detail', invoice_id=invoice_id))


@app.route('/invoices/preview', methods=['GET', 'POST'])
@login_required
def invoices_preview():
    rendered_preview = None
    if request.method == 'POST':
        custom_template = request.form.get('template', '')
        invoice_data = {
            'number': request.form.get('invoice_number', 'INV-PREVIEW'),
            'client': request.form.get('client_name', 'Sample Client'),
            'amount': request.form.get('amount', '0.00'),
            'due_date': request.form.get('due_date', ''),
            'description': request.form.get('description', ''),
        }
        # SSTI: user-supplied template rendered directly with render_template_string
        template_str = f"""
{{% extends 'base.html' %}}
{{% block content %}}
<div class="card shadow-sm p-4">
  <div class="invoice-header mb-4">
    {custom_template}
  </div>
  <hr>
  <table class="table">
    <tr><th>Invoice #</th><td>{invoice_data['number']}</td></tr>
    <tr><th>Client</th><td>{invoice_data['client']}</td></tr>
    <tr><th>Amount</th><td>${invoice_data['amount']}</td></tr>
    <tr><th>Due Date</th><td>{invoice_data['due_date']}</td></tr>
    <tr><th>Description</th><td>{invoice_data['description']}</td></tr>
  </table>
</div>
{{% endblock %}}
"""
        try:
            rendered_preview = render_template_string(template_str)
            return rendered_preview
        except Exception as e:
            flash(f"Template error: {e}", "error")

    return render_template('invoices/preview.html')


@app.route('/invoices/import', methods=['GET', 'POST'])
@login_required
def invoices_import():
    if session.get('role') not in ('admin', 'consultant'):
        abort(403)
    results = []
    if request.method == 'POST':
        f = request.files.get('file')
        if f:
            try:
                # XXE: lxml parser with no XXE protection
                xml_data = f.read()
                tree = etree.parse(io.BytesIO(xml_data))
                root = tree.getroot()
                db = get_db()
                import random
                for inv_el in root.findall('invoice'):
                    number = inv_el.findtext('number', f"INV-IMP-{random.randint(1000,9999)}")
                    client_name = inv_el.findtext('client', 'Unknown')
                    amount = inv_el.findtext('amount', '0')
                    description = inv_el.findtext('description', '')
                    db.execute(
                        "INSERT INTO invoices (invoice_number, client_name, description, amount, status, created_by) VALUES (?,?,?,?,?,?)",
                        (number, client_name, description, amount, 'draft', session['user_id'])
                    )
                    results.append({'number': number, 'client': client_name, 'amount': amount})
                db.commit()
                db.close()
                flash(f"Imported {len(results)} invoice(s).", "success")
            except Exception as e:
                flash(f"Import error: {e}", "error")

    return render_template('invoices/import.html', results=results)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@app.route('/documents')
@login_required
def documents_list():
    db = get_db()
    docs = db.execute(
        "SELECT d.*, c.company_name FROM documents d LEFT JOIN clients c ON d.client_id = c.id ORDER BY d.uploaded_at DESC"
    ).fetchall()
    db.close()
    return render_template('documents/list.html', documents=docs)


@app.route('/documents/upload', methods=['GET', 'POST'])
@login_required
def documents_upload():
    if request.method == 'POST':
        f = request.files.get('file')
        if f and f.filename:
            # Unrestricted file upload: no type check, no filename sanitization
            filename = f.filename
            f.save(os.path.join(UPLOAD_DIR, filename))
            db = get_db()
            db.execute(
                "INSERT INTO documents (filename, original_name, description, client_id, uploaded_by, file_size) VALUES (?,?,?,?,?,?)",
                (filename, filename, request.form.get('description', ''),
                 request.form.get('client_id') or None,
                 session['user_id'], 0)
            )
            db.commit()
            db.close()
            flash("Document uploaded successfully.", "success")
            return redirect(url_for('documents_list'))
    db = get_db()
    clients = db.execute("SELECT id, company_name FROM clients ORDER BY company_name").fetchall()
    db.close()
    return render_template('documents/upload.html', clients=clients)


@app.route('/documents/<int:doc_id>/download')
@login_required
def documents_download(doc_id):
    db = get_db()
    # IDOR: no ownership or permission check
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    db.close()
    if not doc:
        abort(404)
    filepath = os.path.join(UPLOAD_DIR, doc['filename'])
    if not os.path.exists(filepath):
        abort(404)
    return send_file(filepath, as_attachment=True, download_name=doc['original_name'])


@app.route('/files/download')
@login_required
def files_download():
    # Path traversal: filename joined without sanitization
    filename = request.args.get('name', '')
    if not filename:
        abort(400)
    filepath = os.path.join(UPLOAD_DIR, filename)
    try:
        return send_file(filepath)
    except Exception as e:
        # Verbose error leaks server path
        return f"Error reading file: {e} (path: {filepath})", 500


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

@app.route('/expenses')
@login_required
def expenses_list():
    db = get_db()
    expenses = db.execute(
        "SELECT e.*, p.name as project_name, u.display_name as submitter "
        "FROM expenses e JOIN projects p ON e.project_id = p.id "
        "JOIN users u ON e.submitted_by = u.id ORDER BY e.submitted_at DESC"
    ).fetchall()
    db.close()
    return render_template('expenses/list.html', expenses=expenses)


@app.route('/expenses/<int:expense_id>')
@login_required
def expenses_detail(expense_id):
    db = get_db()
    # IDOR: no ownership check
    expense = db.execute(
        "SELECT e.*, p.name as project_name, u.display_name as submitter "
        "FROM expenses e JOIN projects p ON e.project_id = p.id "
        "JOIN users u ON e.submitted_by = u.id WHERE e.id = ?",
        (expense_id,)
    ).fetchone()
    db.close()
    if not expense:
        abort(404)
    return render_template('expenses/detail.html', expense=expense)


@app.route('/projects/<int:project_id>/expenses/submit', methods=['POST'])
@login_required
def expenses_submit(project_id):
    amount = float(request.form.get('amount', 0))
    description = request.form.get('description', '')
    category = request.form.get('category', 'Other')

    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        abort(404)

    # Race condition: check and update are not atomic
    if project['budget_remaining'] >= amount:
        time.sleep(0.05)  # Simulate processing delay — enables race condition
        db.execute("UPDATE projects SET budget_remaining = budget_remaining - ? WHERE id = ?",
                   (amount, project_id))
        db.execute(
            "INSERT INTO expenses (project_id, submitted_by, amount, category, description, status) VALUES (?,?,?,?,?,?)",
            (project_id, session['user_id'], amount, category, description, 'pending')
        )
        db.commit()
        flash("Expense submitted.", "success")
    else:
        flash("Insufficient project budget remaining.", "error")
    db.close()
    return redirect(url_for('projects_detail', project_id=project_id))


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@app.route('/projects')
@login_required
def projects_list():
    db = get_db()
    user = g.user

    # Second-order SQL injection: display_name from DB used in raw query
    display_name = user['display_name']
    query = f"SELECT p.*, c.company_name FROM projects p JOIN clients c ON p.client_id = c.id WHERE p.assigned_to = '{display_name}' OR p.status = 'active'"
    try:
        projects = db.execute(query).fetchall()
    except Exception as e:
        flash(f"Query error: {e}", "error")
        projects = []
    db.close()
    return render_template('projects/list.html', projects=projects)


@app.route('/projects/<int:project_id>')
@login_required
def projects_detail(project_id):
    db = get_db()
    project = db.execute(
        "SELECT p.*, c.company_name FROM projects p JOIN clients c ON p.client_id = c.id WHERE p.id = ?",
        (project_id,)
    ).fetchone()
    if not project:
        abort(404)
    expenses = db.execute("SELECT * FROM expenses WHERE project_id = ?", (project_id,)).fetchall()
    db.close()
    return render_template('projects/detail.html', project=project, expenses=expenses)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@app.route('/reports')
@login_required
def reports_list():
    return render_template('reports/list.html')


@app.route('/reports/export', methods=['GET', 'POST'])
@login_required
def reports_export():
    if request.method == 'POST':
        report_type = request.form.get('type', 'revenue')
        # Command injection: filename inserted directly into shell pipeline without quoting
        filename = request.form.get('filename', 'report')
        report_dir = '/tmp/meridian_reports'
        os.makedirs(report_dir, exist_ok=True)
        output_path = f"{report_dir}/{filename}.csv"
        try:
            # Vulnerable: filename is unquoted in the shell command — ';' injection works
            cmd = (
                f"cd {os.path.dirname(os.path.abspath(__file__))} && "
                f"python3 -c 'import sqlite3; rows=sqlite3.connect(\"meridian.db\")"
                f".execute(\"SELECT invoice_number,client_name,amount,status,due_date FROM invoices\")"
                f".fetchall(); [print(\",\".join(str(c) for c in r)) for r in rows]'"
                f" > {output_path}"
            )
            os.system(cmd)
            if os.path.exists(output_path):
                return send_file(output_path, as_attachment=True,
                                 download_name=f"{filename}.csv")
            else:
                flash("Report generation failed.", "error")
        except Exception as e:
            flash(f"Export error: {e}", "error")
    return render_template('reports/export.html')


# ---------------------------------------------------------------------------
# Integrations / SSRF
# ---------------------------------------------------------------------------

@app.route('/integrations')
@login_required
def integrations_list():
    db = get_db()
    intgrs = db.execute("SELECT * FROM integrations WHERE user_id = ?", (session['user_id'],)).fetchall()
    db.close()
    return render_template('integrations/list.html', integrations=intgrs)


@app.route('/integrations/webhook/test', methods=['POST'])
@login_required
def integrations_webhook_test():
    url = request.form.get('url', '')
    if not url:
        return jsonify({'error': 'URL required'}), 400
    try:
        # SSRF: arbitrary URL fetched by server without any validation
        # urllib supports http://, https://, and file:// protocols
        req = urllib.request.Request(url, headers={'User-Agent': 'Meridian-Webhook/2.3'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read(2000).decode('utf-8', errors='replace')
            return jsonify({
                'status': resp.status,
                'headers': dict(resp.headers),
                'body': body
            })
    except urllib.error.HTTPError as e:
        return jsonify({'status': e.code, 'error': str(e), 'body': e.read(500).decode('utf-8', errors='replace')})
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/integrations/create', methods=['GET', 'POST'])
@login_required
def integrations_create():
    if request.method == 'POST':
        db = get_db()
        db.execute(
            "INSERT INTO integrations (user_id, name, webhook_url, event_type) VALUES (?,?,?,?)",
            (session['user_id'], request.form['name'],
             request.form['webhook_url'], request.form['event_type'])
        )
        db.commit()
        db.close()
        flash("Integration created.", "success")
        return redirect(url_for('integrations_list'))
    return render_template('integrations/create.html')


# ---------------------------------------------------------------------------
# Profile / Mass assignment / CSRF
# ---------------------------------------------------------------------------

@app.route('/profile')
@login_required
def profile():
    return render_template('profile/view.html', user=g.user)


@app.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    user_id = session['user_id']
    db = get_db()

    # Mass assignment: all form fields written to DB without whitelist
    # No CSRF protection
    updates = {}
    for key, value in request.form.items():
        # Handle plaintext password from the profile form — convert to hash
        if key == 'password_plain':
            if value:
                updates['password_hash'] = hash_password(value)
            # Skip empty password_plain (user left field blank)
            continue
        updates[key] = value

    if updates:
        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [user_id]
        try:
            db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
            db.commit()
            # Update session if role was changed
            if 'role' in updates:
                session['role'] = updates['role']
            if 'display_name' in updates:
                session['display_name'] = updates['display_name']
            flash("Profile updated.", "success")
        except Exception as e:
            flash(f"Update error: {e}", "error")
    db.close()
    return redirect(url_for('profile'))


# ---------------------------------------------------------------------------
# Admin panel
# ---------------------------------------------------------------------------

@app.route('/admin')
@login_required
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))   # Redirect, not 403 — misses some cases
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    stats = {
        'users': db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'clients': db.execute("SELECT COUNT(*) FROM clients").fetchone()[0],
        'invoices': db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0],
        'documents': db.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
    }
    db.close()
    return render_template('admin/dashboard.html', users=users, stats=stats)


@app.route('/admin/users')
@login_required
def admin_users():
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY id").fetchall()
    db.close()
    return render_template('admin/users.html', users=users)


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    # CSRF: no token check
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))
    db = get_db()
    db.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    db.commit()
    db.close()
    flash("User deactivated.", "success")
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
def admin_reset_user_password(user_id):
    # CSRF: no token check
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))
    new_password = request.form.get('new_password', 'Reset1234!')
    db = get_db()
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
               (hash_password(new_password), user_id))
    db.commit()
    db.close()
    flash("Password reset.", "success")
    return redirect(url_for('admin_users'))


# ---------------------------------------------------------------------------
# API v1 — JWT-based authentication
# ---------------------------------------------------------------------------

def verify_api_token(token):
    try:
        # JWT vulnerability: signature verification disabled
        payload = jwt.decode(token, options={"verify_signature": False}, algorithms=["HS256", "none"])
        return payload
    except Exception:
        try:
            # Fallback: try verifying with weak secret
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            return payload
        except Exception:
            return None


def api_auth_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        api_key = request.headers.get('X-API-Key', '')

        # Hardcoded API key check (discoverable from JS source)
        if api_key == 'sk-meridian-internal-8f3a2b1c9d4e5f6a7b8c':
            g.api_user = {'user_id': 1, 'role': 'admin'}
            return f(*args, **kwargs)

        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            payload = verify_api_token(token)
            if payload:
                g.api_user = payload
                return f(*args, **kwargs)

        return jsonify({'error': 'Authentication required'}), 401
    return decorated


@app.route('/api/v1/auth/token', methods=['POST'])
def api_get_token():
    email = request.json.get('email', '')
    password = request.json.get('password', '')
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ? AND password_hash = ?",
                      (email, hash_password(password))).fetchone()
    db.close()
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    # Weak secret, no expiry
    token = jwt.encode({'user_id': user['id'], 'role': user['role']}, JWT_SECRET, algorithm='HS256')
    return jsonify({'token': token})


@app.route('/api/v1/invoices')
@api_auth_required
def api_invoices():
    db = get_db()
    invoices = db.execute("SELECT * FROM invoices ORDER BY created_at DESC").fetchall()
    db.close()
    return jsonify([dict(i) for i in invoices])


@app.route('/api/v1/clients')
@api_auth_required
def api_clients():
    db = get_db()
    clients = db.execute("SELECT * FROM clients ORDER BY company_name").fetchall()
    db.close()
    return jsonify([dict(c) for c in clients])


@app.route('/api/v1/users')
@api_auth_required
def api_users():
    db = get_db()
    users = db.execute("SELECT id, email, display_name, role, is_active, created_at FROM users").fetchall()
    db.close()
    return jsonify([dict(u) for u in users])


@app.route('/api/v1/users/<int:user_id>', methods=['PUT'])
@api_auth_required
def api_update_user(user_id):
    data = request.json or {}
    db = get_db()
    # Mass assignment via API: accepts all fields including is_admin, role
    if data:
        set_clause = ', '.join(f"{k} = ?" for k in data.keys())
        db.execute(f"UPDATE users SET {set_clause} WHERE id = ?",
                   list(data.values()) + [user_id])
        db.commit()
    user = db.execute("SELECT id, email, display_name, role FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()
    return jsonify(dict(user) if user else {})


# Missing auth on this admin API endpoint
@app.route('/api/v1/admin/users')
def api_admin_users():
    # No @api_auth_required — missing authentication
    db = get_db()
    users = db.execute("SELECT * FROM users").fetchall()
    db.close()
    return jsonify([dict(u) for u in users])


@app.route('/api/v1/debug/config')
def api_debug_config():
    # Debug endpoint left in production — exposes secrets
    return jsonify({
        'database': app.config.get('DATABASE'),
        'secret_key': app.secret_key,
        'debug': app.config.get('DEBUG'),
        'environment': os.environ.get('FLASK_ENV', 'production'),
        'upload_dir': UPLOAD_DIR,
        'jwt_secret': JWT_SECRET,
        'version': '2.3.1',
        'server': 'Werkzeug/2.3.7 Python/3.11',
    })


@app.route('/api/preferences', methods=['GET', 'POST'])
@login_required
def api_preferences():
    if request.method == 'POST':
        prefs = {
            'theme': request.json.get('theme', 'light'),
            'notifications': request.json.get('notifications', True),
            'language': request.json.get('language', 'en'),
        }
        # Insecure: serialize preferences as pickle and store in cookie
        serialized = base64.b64encode(pickle.dumps(prefs)).decode()
        resp = jsonify({'status': 'saved', 'preferences': prefs})
        resp.set_cookie('user_prefs', serialized)
        return resp

    # Insecure deserialization: pickle.loads on cookie value
    prefs_cookie = request.cookies.get('user_prefs')
    if prefs_cookie:
        try:
            prefs = pickle.loads(base64.b64decode(prefs_cookie))
            return jsonify(prefs)
        except Exception as e:
            return jsonify({'error': f'Could not load preferences: {e}'})

    return jsonify({'theme': 'light', 'notifications': True, 'language': 'en'})


# ---------------------------------------------------------------------------
# Error handlers — verbose messages
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


# No custom 500 handler → Flask default exposes full traceback in debug mode


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    # Debug mode: exposes interactive debugger at /__debugger__
    app.run(host='0.0.0.0', port=5000, debug=True)
