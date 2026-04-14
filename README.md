# Meridian Consulting Portal — Web Pentesting Lab

A realistic, intentionally vulnerable web application for practising web application security testing. Built to resemble a genuine business application in production, not a CTF challenge.

---

## What is this?

**Meridian** is a fictional management consulting firm's internal portal. It handles client management, project tracking, invoicing, document management, expense reporting, and integrations with external tools.

The application was built to serve as a hands-on pentesting training environment. It covers a wide range of vulnerability classes across the OWASP Top 10 and beyond, implemented the way they actually appear in real production codebases — as the result of deadline pressure, developer oversights, and features added without security review.

---

## Tech Stack

- **Backend**: Python 3 / Flask
- **Database**: SQLite
- **Frontend**: Jinja2 templates, Bootstrap 5, vanilla JavaScript
- **API**: RESTful JSON API at `/api/v1/`

---

## Features

The portal includes:

- User authentication (multiple roles: admin, consultant, client)
- Client company management
- Project tracking with budget monitoring
- Invoice creation, approval workflows, and bulk import
- Document upload and management
- Expense reporting
- Report generation and export
- Webhook integrations
- Admin panel for user management
- REST API with JWT authentication

---

## Setup

**Requirements**: Python 3.9+

```bash
# Install dependencies
pip install -r requirements.txt

# Initialise the database with sample data
python seed_data.py

# Start the application
python app.py
```

The app runs at **http://localhost:5000**

To reset to a clean state at any time:
```bash
python seed_data.py
```
This removes the database and all uploaded files, then re-seeds everything from scratch.

---

## Documentation

| File | Description |
|------|-------------|
| `docs/USER_getting_started.md` | Setup, credentials, recommended tools |
| `docs/USER_app_overview.md` | Application features and URL map |

Additional documentation is available for instructors and AI-assisted learning workflows — see the `docs/` directory.

---

## Scope

This environment is intended for:

- Learning and practising web application penetration testing
- Exploring both manual and tool-assisted testing techniques
- Understanding how common vulnerabilities arise in real applications

**Do not expose this application to the internet.** It is intentionally insecure.

---

## Learning Approach

The app is designed to be explored from a black-box perspective first. Resist the urge to read the source code before finding issues manually — the learning value is in the discovery process.

Both beginner and more advanced techniques are applicable. Some vulnerabilities chain together; others are standalone. The app rewards thorough reconnaissance.

---

## AI-Assisted Learning

The repository includes structured documentation for use with AI coding assistants (see `CLAUDE.md`). When you get stuck, an AI agent loaded with this project can provide progressive hints without spoiling the solution.
