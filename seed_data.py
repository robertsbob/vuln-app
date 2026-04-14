"""
Seed the database with realistic sample data.
Run this after init_db() to populate with test data.
"""
import os
import shutil
import struct
from database import get_db, hash_password, init_db


def make_minimal_pdf(title: str) -> bytes:
    """Generate a valid minimal single-page PDF with a title string."""
    text = f'Meridian Consulting — {title}'
    # Escape parentheses in PDF string
    text_escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    stream_content = f'BT /F1 12 Tf 72 720 Td ({text_escaped}) Tj ET'.encode()
    stream_len = len(stream_content)

    objects = []
    objects.append(b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
    objects.append(b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n')
    objects.append(
        b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n'
    )
    objects.append(
        b'4 0 obj\n<< /Length ' + str(stream_len).encode() + b' >>\nstream\n'
        + stream_content + b'\nendstream\nendobj\n'
    )
    objects.append(
        b'5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n'
    )

    header = b'%PDF-1.4\n'
    body = b''
    offsets = []
    pos = len(header)
    for obj in objects:
        offsets.append(pos)
        body += obj
        pos += len(obj)

    xref_offset = len(header) + len(body)
    xref = b'xref\n0 6\n0000000000 65535 f \n'
    for off in offsets:
        xref += f'{off:010d} 00000 n \n'.encode()

    trailer = (
        b'trailer\n<< /Size 6 /Root 1 0 R >>\n'
        b'startxref\n' + str(xref_offset).encode() + b'\n%%EOF\n'
    )
    return header + body + xref + trailer

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'documents')


def seed():
    # Remove existing DB
    db_path = os.path.join(os.path.dirname(__file__), 'meridian.db')
    if os.path.exists(db_path):
        os.remove(db_path)

    # Re-create upload dir
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    init_db()
    conn = get_db()
    c = conn.cursor()

    # ------------------------------------------------------------------ Users
    users = [
        (1, 'admin@meridian.com',       hash_password('Admin2024!'),    'Alex Morgan',       'admin',      1),
        (2, 'j.morrison@meridian.com',  hash_password('Welcome123'),    'James Morrison',    'consultant', 1),
        (3, 'a.patel@meridian.com',     hash_password('Meridian2023!'), 'Aisha Patel',       'consultant', 1),
        (4, 'ceo@pinnacletech.com',     hash_password('Pinnacle1!'),    'David Chen',        'client',     1),
        (5, 'finance@globalcorp.com',   hash_password('Finance2023'),   'Sandra Williams',   'client',     1),
        (6, 'contact@startupxyz.com',   hash_password('startup123'),    'Marcus Reid',       'client',     1),
    ]
    c.executemany(
        "INSERT INTO users (id, email, password_hash, display_name, role, is_active) VALUES (?,?,?,?,?,?)",
        users
    )

    # ---------------------------------------------------------------- Clients
    clients = [
        (1, 'Pinnacle Technology Partners', 'David Chen',     'ceo@pinnacletech.com',   '+1-555-0101',
         '1200 Tech Blvd, Suite 400, San Francisco, CA 94105', 'Technology', 2),
        (2, 'Global Corp Industries',       'Sandra Williams','finance@globalcorp.com',  '+1-555-0202',
         '500 Commerce St, Floor 12, New York, NY 10004',      'Manufacturing', 2),
        (3, 'Startup XYZ',                  'Marcus Reid',    'contact@startupxyz.com',  '+1-555-0303',
         '88 Innovation Way, Austin, TX 78701',                'SaaS', 3),
    ]
    c.executemany(
        "INSERT INTO clients (id, company_name, contact_name, email, phone, address, industry, owner_id) VALUES (?,?,?,?,?,?,?,?)",
        clients
    )

    # --------------------------------------------------------------- Projects
    projects = [
        (1, 'Digital Transformation Roadmap', 'Strategic assessment of IT infrastructure and 3-year digital transformation plan.',
         1, 'James Morrison', 'active', 185000, 72400, '2024-01-15', '2024-12-31', 2),
        (2, 'Supply Chain Optimisation',      'End-to-end supply chain analysis and process re-engineering.',
         2, 'Aisha Patel',   'active', 240000, 98000, '2024-03-01', '2024-11-30', 3),
        (3, 'Go-to-Market Strategy',           'Market entry analysis and GTM playbook for Series B expansion.',
         3, 'James Morrison', 'active', 55000,  21000, '2024-06-01', '2024-09-30', 2),
        (4, 'M&A Due Diligence — Project Falcon', 'Confidential operational and financial due diligence for acquisition target.',
         1, 'Alex Morgan',   'completed', 320000, 0,  '2023-09-01', '2024-02-28', 1),
    ]
    c.executemany(
        "INSERT INTO projects (id, name, description, client_id, assigned_to, status, budget, budget_remaining, start_date, end_date, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        projects
    )

    # --------------------------------------------------------------- Invoices
    invoices = [
        (1,  'INV-2024-001', 1, 'Pinnacle Technology Partners', 'Phase 1: Discovery & Assessment',              45000, 'paid',      '2024-02-15', 2, 'Phase 1 work completed on time. All deliverables accepted by client.'),
        (2,  'INV-2024-002', 1, 'Pinnacle Technology Partners', 'Phase 2: Strategy Development',               55000, 'approved',  '2024-04-30', 2, 'Includes roadmap document, executive presentation, and implementation plan.'),
        (3,  'INV-2024-003', 2, 'Global Corp Industries',       'Supply Chain Baseline Assessment',            38500, 'paid',      '2024-04-15', 3, 'Baseline report delivered. Client satisfied with findings.'),
        (4,  'INV-2024-004', 2, 'Global Corp Industries',       'Process Re-engineering Phase 1',              62000, 'submitted', '2024-06-30', 3, 'Covers warehouse ops and logistics. Travel expenses billed separately.'),
        (5,  'INV-2024-005', 3, 'Startup XYZ',                  'Market Research & Competitive Analysis',      18000, 'paid',      '2024-07-01', 2, ''),
        (6,  'INV-2024-006', 3, 'Startup XYZ',                  'GTM Playbook Development',                    22000, 'draft',     '2024-08-31', 2, 'Draft pending internal review before submission.'),
        (7,  'INV-2024-007', 1, 'Pinnacle Technology Partners', 'Phase 3: Implementation Support (Month 1)',   28000, 'submitted', '2024-07-31', 2, 'Monthly retainer for implementation oversight.'),
        (8,  'INV-2023-018', 1, 'Pinnacle Technology Partners', 'Project Falcon — Due Diligence Fees',        120000, 'paid',      '2024-03-01', 1, 'CONFIDENTIAL. Engagement under NDA. Do not discuss with client contacts outside approved list.'),
        (9,  'INV-2024-008', 2, 'Global Corp Industries',       'Process Re-engineering Phase 2',              58000, 'draft',     '2024-09-30', 3, ''),
        (10, 'INV-2024-009', 1, 'Pinnacle Technology Partners', 'Phase 3: Implementation Support (Month 2)',   28000, 'draft',     '2024-08-31', 2, 'Monthly retainer. To be submitted after timesheet approval.'),
    ]
    c.executemany(
        "INSERT INTO invoices (id, invoice_number, client_id, client_name, description, amount, status, due_date, created_by, notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        invoices
    )

    # -------------------------------------------------------------- Documents
    # Create placeholder files
    doc_files = {
        'pinnacle_dtf_phase1_report.pdf':         make_minimal_pdf('Phase 1 Digital Transformation Report — Pinnacle Technology Partners'),
        'pinnacle_dtf_roadmap_v2.pdf':            make_minimal_pdf('3-Year Digital Transformation Roadmap v2'),
        'globalcorp_supply_chain_baseline.xlsx':  b'PK [Excel - Supply Chain Baseline Assessment Data]',
        'project_falcon_due_diligence.pdf':       make_minimal_pdf('CONFIDENTIAL — Project Falcon M&A Due Diligence Report'),
        'meridian_engagement_contract_2024.pdf':  make_minimal_pdf('Master Services Agreement 2024'),
        'startupxyz_market_research.pdf':         make_minimal_pdf('Market Research & Competitive Analysis — Startup XYZ'),
        'staff_salary_review_2024.xlsx':          b'PK [INTERNAL - Staff Compensation Review Q1 2024 - CONFIDENTIAL]',
        'meridian_client_list_crm_export.csv':    b'id,company,contact,email,phone,revenue\n1,Pinnacle Technology Partners,David Chen,ceo@pinnacletech.com,+1-555-0101,185000\n2,Global Corp Industries,Sandra Williams,finance@globalcorp.com,+1-555-0202,240000\n3,Startup XYZ,Marcus Reid,contact@startupxyz.com,+1-555-0303,55000',
    }
    for fname, content in doc_files.items():
        with open(os.path.join(UPLOAD_DIR, fname), 'wb') as f:
            f.write(content)

    documents = [
        (1, 'pinnacle_dtf_phase1_report.pdf',        'Digital Transformation Phase 1 Report',        'Phase 1 deliverable',       1, 1, 2, 204800, 0),
        (2, 'pinnacle_dtf_roadmap_v2.pdf',           '3-Year Digital Transformation Roadmap v2',     '3-year strategic roadmap',  1, 1, 2, 512000, 0),
        (3, 'globalcorp_supply_chain_baseline.xlsx',  'Supply Chain Baseline Assessment Data',        'Baseline assessment',       2, 2, 3, 153600, 0),
        (4, 'project_falcon_due_diligence.pdf',       'Project Falcon Due Diligence Report',          'CONFIDENTIAL - M&A report', 1, 4, 1, 819200, 1),
        (5, 'meridian_engagement_contract_2024.pdf',  'Master Services Agreement 2024',               'Client MSA contract',       1, 1, 1, 102400, 0),
        (6, 'startupxyz_market_research.pdf',         'Market Research & Competitive Analysis',       'GTM market research',       3, 3, 2, 307200, 0),
        (7, 'staff_salary_review_2024.xlsx',          'Staff Compensation Review Q1 2024',            'INTERNAL - HR data',        None, None, 1, 40960, 1),
        (8, 'meridian_client_list_crm_export.csv',    'CRM Client Export (all clients)',              'Full CRM export',           None, None, 1, 2048,  1),
    ]
    c.executemany(
        "INSERT INTO documents (id, filename, original_name, description, client_id, project_id, uploaded_by, file_size, is_confidential) VALUES (?,?,?,?,?,?,?,?,?)",
        documents
    )

    # -------------------------------------------------------------- Expenses
    expenses = [
        (1, 1, 2, 1240.50, 'Travel',       'Return flights SFO-NYC for client workshop',       'approved', None),
        (2, 1, 2,  380.00, 'Accommodation','Hotel (3 nights) NYC client visit',                 'approved', None),
        (3, 2, 3, 2100.00, 'Travel',       'International flights for supply chain site visits','pending',  None),
        (4, 3, 2,  145.00, 'Meals',        'Working dinner with client exec team',              'approved', None),
        (5, 1, 2,  890.00, 'Software',     'Tableau license for data visualisation deliverable','approved', None),
    ]
    c.executemany(
        "INSERT INTO expenses (id, project_id, submitted_by, amount, category, description, status, receipt_filename) VALUES (?,?,?,?,?,?,?,?)",
        expenses
    )

    # ----------------------------------------------------------- Integrations
    integrations = [
        (1, 2, 'Slack — Project Notifications',  'https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX', 'invoice.approved', 1),
        (2, 3, 'Jira — Project Updates',         'https://meridian.atlassian.net/webhooks/1.0/webhook', 'project.status_change', 1),
    ]
    c.executemany(
        "INSERT INTO integrations (id, user_id, name, webhook_url, event_type, is_active) VALUES (?,?,?,?,?,?)",
        integrations
    )

    conn.commit()
    conn.close()
    print("[+] Database seeded successfully.")
    print("[+] Sample documents created in static/uploads/documents/")


if __name__ == '__main__':
    seed()
