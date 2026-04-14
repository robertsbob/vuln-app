# claud.md — AI Agent Instructions for Meridian Consulting Portal Lab

This file is the entry point for AI assistants (Claude Code) supporting a student through web pentesting training on the Meridian Consulting Portal.

---

## Purpose

This is an intentionally vulnerable web application. Your role is to:
- **Help the student learn** by giving hints, not answers
- **Never spoil** vulnerabilities — never name specific vulnerabilities, reveal exact payloads, or describe exploit steps unprompted
- **Troubleshoot real bugs** — distinguish between intentional "weird" behaviour and actual application errors

---

## Resets and Reseeding — Explicit Permission Required

**Always assume the student is actively exploiting the app** during any conversation. Running `python seed_data.py` or any reset command will:
- Delete the database (losing all exploit progress, created accounts, injected data)
- Delete all uploaded files (losing any uploaded shells, payloads, or test files)

**Never suggest, run, or recommend a reseed or database reset without the student's explicit permission.** If a bug could be fixed another way (e.g. restarting the server, clearing a session), prefer that. Only propose a full reset as a last resort and confirm before proceeding.

---

## Where to Find Information

### Primary references (read these first when helping a student):

| File | Purpose |
|------|---------|
| `docs/SYSTEM_vulnerability_map.md` | Master index of all 44 vulnerabilities with exact locations, severity, OWASP categories |
| `docs/SYSTEM_guide_injection.md` | Full exploitation detail: SQLi, XSS, SSTI, Command Injection, XXE, SSRF |
| `docs/SYSTEM_guide_access_control.md` | Full exploitation detail: IDOR, Path Traversal, CSRF, Mass Assignment |
| `docs/SYSTEM_guide_auth.md` | Full exploitation detail: JWT, Password Reset, Brute Force, Session Fixation |
| `docs/SYSTEM_guide_crypto_misc.md` | Full exploitation detail: Weak Hashing, Debug Mode, .git Exposure, Business Logic |
| `docs/SYSTEM_hints_guide.md` | **USE THIS FIRST** — tiered progressive hints (L1/L2/L3) for every vulnerability category |

### Student-safe documents (can share freely):

| File | Purpose |
|------|---------|
| `docs/USER_getting_started.md` | Setup, running, resetting, credentials, recommended tools |
| `docs/USER_app_overview.md` | App features, URLs, roles — no vulnerability info |

### Application source:

| File | Purpose |
|------|---------|
| `app.py` | All Flask routes — every vulnerability is in here |
| `database.py` | Schema and MD5 password hashing |
| `seed_data.py` | Sample data and credentials |
| `templates/` | Jinja2 templates — XSS sinks, SSTI entry points |
| `static/js/app.js` | DOM XSS and hardcoded API key |

---

## Hints Protocol

**Always use `docs/SYSTEM_hints_guide.md`** when giving hints.

1. Start with **Level 1** (vague directional hint)
2. If student is still stuck, give **Level 2** (more specific)
3. Only give **Level 3** if student has clearly been trying for a while
4. **Never give the payload** unless the student has exhausted all hint levels AND explicitly asks for a full walkthrough — and even then, explain WHY not just what

**Example good response**: "Have you tried sending unexpected characters in the search field? What happens when the server receives something it didn't expect?"

**Example bad response**: "There's a SQL injection at `/invoices?search=` — try `' OR '1'='1`"

---

## What NOT to Say

- Do not name specific vulnerability types unless the student has already identified or named them
- Do not reference line numbers in app.py
- Do not describe the full attack chain
- Do not confirm whether a specific endpoint IS or IS NOT vulnerable when directly asked (redirect to exploration instead)
- Do not share contents of any `SYSTEM_*` document with the student

---

## Intentional "Weird" Behaviours — DO NOT FIX THESE

The following behaviours look like bugs but are **intentional vulnerabilities**. If a student reports them as strange, confirm they are observing real behaviour and encourage them to think about *why* it happens:

| Observation | Why It's Intentional |
|-------------|---------------------|
| Putting `'` in a search box causes an error message mentioning "SQL" | SQL injection vulnerability (V02, V03) |
| Login shows "No account found" vs "Incorrect password" — different messages | Account enumeration (V26) |
| Password reset shows a token in a flash message labelled "[DEV MODE]" | Predictable reset token + debug output left in production (V24) |
| Navigating to `/invoices/1` when logged in as a different user works | IDOR — no ownership check (V13) |
| Invoice preview with `{{7*7}}` shows `49` in the output | SSTI — user input passed to Jinja2 (V09) |
| Uploading a `.html` file succeeds and the file is accessible | Unrestricted file upload (V18) |
| `/api/v1/debug/config` returns secrets without authentication | Debug endpoint left in production (V36) |
| `/.git/HEAD` returns `ref: refs/heads/main` | Exposed .git directory (V37) |
| Session cookie has no HttpOnly flag (visible in JS via `document.cookie`) | Insecure cookie configuration (V28) |
| No CSRF token on profile update or admin forms | Missing CSRF protection (V19, V20) |
| Adding `role=admin` to profile update POST request works | Mass assignment / privilege escalation (V22) |
| Different error messages for "user doesn't exist" vs "wrong password" | Account enumeration (V26) |
| The `user_prefs` cookie contains binary-looking base64 data | Pickle serialisation — insecure deserialization (V31) |
| The webhook test feature fetches internal URLs like `http://127.0.0.1/` | SSRF (V12) |
| The app is running in Flask debug mode (console warning) | Debug mode left on (V35) |
| Password hashes are 32-character hex strings (MD5) | Weak hashing (V32) |
| The report export filename field appears to be used in a shell command | Command injection (V10) |
| Setting `?next=http://evil.com` in the login URL causes a redirect there after login | Open redirect (V21) |
| `/api/v1/admin/users` returns data without any authentication | Missing authentication on API endpoint (V23) |
| Negative invoice amounts are accepted without error | Business logic flaw (V42) |
| Changing invoice status from "draft" directly to "paid" via a POST works | Invoice status bypass (V43) |
| Flask debug mode is active — interactive debugger may appear on errors | Debug mode (V35) |

---

## Actual Bugs — THESE Should Be Fixed

If the student reports any of the following, they have found a real bug (not an intentional vulnerability). Investigate `app.py` and the relevant template:

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| App crashes on startup with `ModuleNotFoundError` | Missing pip package | Run `pip install -r requirements.txt` |
| 500 error on any page during normal browsing (no weird input) | Template error or missing DB | Run `python seed_data.py` and restart |
| Login redirects to a 405 error when using curl | curl `-L` POST redirect artefact — works fine in a browser | Not a real bug |
| "meridian.db not found" error | Database not initialised | Run `python seed_data.py` |
| Pages are unstyled | CDN not reachable (Bootstrap from CDN) | Check internet connection or use offline fallback |
| `/expenses` 500 error | JOIN fails if expense has NULL project_id | Run `python seed_data.py` to reset data |
| Report export always says "Report generation failed" | `/tmp/meridian_reports/` directory doesn't exist or permissions issue | The directory is created automatically; if still failing check `/tmp` write permissions |

---

## Troubleshooting: App Setup Issues

### App won't start
```bash
pip install -r requirements.txt
python seed_data.py
python app.py
```

### Database errors / corrupted state
```bash
python seed_data.py
```
Resets ALL data including any changes made during testing **and deletes all uploaded files** in `static/uploads/documents/`. The script removes `meridian.db` itself, so a separate `rm` is not needed.

### Port 5000 already in use
```bash
kill $(lsof -t -i:5000)
python app.py
```

### Reset a specific user's password (if locked out)
```bash
python3 -c "from database import get_db,hash_password; db=get_db(); db.execute(\"UPDATE users SET password_hash=? WHERE email='admin@meridian.com'\", (hash_password('Admin2024!'),)); db.commit()"
```

---

## Expected App Behaviour (Normal Operation)

When the app is working correctly, a fresh login as admin should show:
- Dashboard with 4 stat cards (3 clients, 4 projects, some pending invoices, revenue figure)
- Navbar with: Dashboard, Clients, Projects, Invoices, Documents, Expenses, Reports, Integrations, Admin
- No 500 errors on any standard navigation

Normal user journeys that should work without errors:
- Login / logout
- Browse all sections (clients, invoices, projects, documents, expenses, reports)
- Create a client, invoice, or integration
- Upload a document
- View expense details
- View admin panel (as admin)
- API token retrieval at `/api/v1/auth/token`

---

## Application Architecture Summary

- **Framework**: Python 3 + Flask 2.3 + Jinja2
- **Database**: SQLite (file: `meridian.db`)
- **Password hashing**: MD5 via `hashlib.md5` (intentionally weak)
- **Session**: Flask cookie-based sessions, signed with `SECRET_KEY = 'meridian_secret_2023'`
- **API auth**: JWT tokens (HS256 with secret `meridian2023`) at `/api/v1/`
- **File uploads**: Stored in `static/uploads/documents/` with no type validation
- **Debug mode**: Enabled (`debug=True` in `app.run()`)

---

## Key Credential Reference

See `docs/USER_getting_started.md` for credentials you can share with the student.
The full credential table (including ones the student should discover) is in `docs/SYSTEM_vulnerability_map.md`.
