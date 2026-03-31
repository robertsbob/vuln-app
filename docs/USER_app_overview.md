# Application Overview — Meridian Consulting Portal

This document describes the application's features and how they work from a user perspective. It's safe to read.

---

## User Roles

The application has three types of users:

### Admin
Full access to everything. Manages users, can view all data, configures system settings.

### Consultant
Meridian staff. Can:
- Manage their assigned clients
- Create and manage projects
- Create and submit invoices
- Upload documents for clients
- Submit expense reports
- Use the invoice preview and template features
- Configure webhooks for project notifications

### Client
External users (clients of the firm). Can:
- View their own project status
- Download deliverables and documents shared with them
- View invoices issued to them
- View their company profile

---

## Application Sections

### Dashboard (`/dashboard`)
Shows a summary of recent activity: recent invoices, active projects, upcoming deadlines, and notifications.

### Clients (`/clients`)
List of all client companies. Consultants can create/edit client profiles. Each client has:
- Company name and contact details
- Assigned consultant
- Link to their projects and invoices

### Projects (`/projects`)
Consulting engagements. Each project has:
- Status (Active, On Hold, Completed)
- Budget and budget remaining
- Assigned team
- Linked client
- Expense tracking

### Invoices (`/invoices`)
Financial invoices. Features include:
- Create invoices linked to clients
- Invoice statuses: Draft → Submitted → Approved → Paid
- Notes/description field for each invoice
- Invoice preview with custom template branding
- Import invoices from XML file
- Search/filter invoices

### Documents (`/documents`)
File storage for project deliverables. Features:
- Upload documents (PDFs, spreadsheets, presentations)
- Organize by client/project
- Download documents
- Share specific documents with client users

### Expenses (`/expenses`)
Internal expense reporting. Consultants submit expenses, admins approve.

### Reports (`/reports`)
Generate summary reports (revenue by client, project status, etc.) and export them.

### Integrations (`/integrations`)
Configure webhook URLs for third-party tools (Slack, project management systems, etc.). Includes a "test" feature to verify your webhook endpoint is reachable.

### Admin Panel (`/admin`)
User management, system configuration. Admin-only.

### API (`/api/v1/`)
RESTful API. Requires authentication via JWT Bearer token. Get a token from `/api/v1/auth/token`.

---

## Data in the System

The app is seeded with realistic fictional data:

**Client Companies**:
- Pinnacle Technology Partners
- Global Corp Industries
- Startup XYZ

**Sample Projects**: Various consulting engagements with realistic names and budgets

**Sample Documents**: Contracts, project deliverables, financial reports (fictional content)

**Sample Invoices**: Various invoices in different states

---

## Useful URLs to Know

| URL | Description |
|-----|-------------|
| `/auth/login` | Login page |
| `/auth/forgot-password` | Password reset |
| `/dashboard` | Main dashboard |
| `/invoices` | Invoice list |
| `/invoices/create` | Create new invoice |
| `/invoices/preview` | Preview invoice with custom template |
| `/invoices/import` | Import invoices from XML |
| `/clients` | Client list |
| `/documents` | Document list |
| `/documents/upload` | Upload a document |
| `/files/download` | Download a file by name |
| `/reports` | Reports section |
| `/reports/export` | Generate and export a report |
| `/integrations` | Webhook integrations |
| `/integrations/webhook/test` | Test a webhook URL |
| `/profile` | Your user profile |
| `/profile/update` | Update profile settings |
| `/admin` | Admin panel |
| `/api/v1/auth/token` | Get API JWT token |
| `/api/v1/invoices` | API: list invoices |
| `/api/v1/clients` | API: list clients |
