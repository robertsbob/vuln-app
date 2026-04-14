# Getting Started — Meridian Consulting Portal

Welcome to the Meridian Consulting Portal pentesting lab. This document covers everything you need to set up and start using the application.

---

## What Is This?

The Meridian Consulting Portal is a web application for a fictional management consulting firm. It's a realistic business application — not a toy or CTF challenge. It has features you'd find in a real company's internal tools: client management, invoicing, project tracking, document management, and more.

Your goal is to explore it from a security perspective and find vulnerabilities.

---

## Setup

### Requirements

- Python 3.9+
- pip

### Install & Run

```bash
cd /home/user/vuln-app

# Install dependencies
pip install -r requirements.txt

# Initialize the database with sample data
python seed_data.py

# Start the application
python app.py
```

The application will be available at: **http://localhost:5000**

### Stopping the App

Press `Ctrl+C` in the terminal where the app is running.

### Resetting the Database

If you've made changes to the data during testing and want a clean slate:
```bash
python seed_data.py
```
This removes the database and all uploaded files, then re-seeds everything from scratch.

---

## Your Starting Credentials

You are starting with access to the following account:

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@meridian.com` | `Admin2024!` |

There is also a client account you can use to see the app from a client's perspective:

| Role | Email | Password |
|------|-------|----------|
| Client | `contact@startupxyz.com` | `startup123` |

---

## The Application

### Business Context

Meridian Management Consulting is a mid-size consulting firm. The portal is used by:

- **Consultants** — manage clients, projects, invoices, and deliverables
- **Clients** — view their project status, download deliverables, see invoices
- **Admin** — manage users, system settings, and the platform

The app has been in production for about 3 years, built and maintained by a small internal development team.

### Main Features

- **Dashboard** — overview of recent activity
- **Clients** — manage client company profiles and contacts
- **Projects** — track consulting engagements
- **Invoices** — create, submit, and manage invoices
- **Documents** — upload and share project deliverables
- **Expenses** — submit and approve expense reports
- **Reports** — generate and export business reports
- **Integrations** — configure webhook endpoints for external tools
- **Admin Panel** — user management and system settings
- **API** — RESTful API at `/api/v1/` for programmatic access

---

## Recommended Tools

You can use any tools you like. Some commonly used ones for web pentesting:

| Tool | Purpose |
|------|---------|
| Burp Suite Community Edition | HTTP proxy, request interception, repeater |
| Firefox DevTools | Network inspection, cookie inspection, JS debugging |
| curl | Command-line HTTP requests |
| ffuf | Directory/parameter fuzzing |
| sqlmap | SQL injection testing |
| hashcat / john | Password hash cracking |
| jwt.io | JWT decoding and inspection |

---

## Approach Suggestion

This is a black-box + gray-box environment. You have access to the app as a legitimate user and can also look at the source code if you choose (though starting without looking at source is more educational).

A good starting progression:
1. Explore the app as a normal user — understand what it does
2. Identify all input points (forms, URL parameters, headers)
3. Think about what could go wrong at each input point
4. Experiment systematically
5. Move from low-hanging fruit to more complex vulnerabilities

There is no single "correct" order. Real-world pentesting is iterative.

---

## Notes

- The app is intentionally vulnerable — this is a training environment
- Data in the app is fictional
- Do not expose this app to the internet
- Reset the database (`python seed_data.py`) if you accidentally break something or want a clean state
