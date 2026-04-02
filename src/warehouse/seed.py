"""Create DuckDB warehouse with schemas, tables, and realistic seed data."""

import random
import duckdb
from datetime import date, datetime, timedelta
from config.settings import settings


def seed_warehouse(db_path: str | None = None):
    """Build the entire warehouse from scratch."""
    path = db_path or settings.duckdb_path
    conn = duckdb.connect(path)

    _create_schemas(conn)
    _create_tables(conn)
    _insert_seed_data(conn)

    print(f"Warehouse seeded at {path}")
    conn.close()


def _create_schemas(conn: duckdb.DuckDBPyConnection):
    for schema in ("finance", "operations", "client_services"):
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")


def _create_tables(conn: duckdb.DuckDBPyConnection):
    conn.execute("""
    CREATE OR REPLACE TABLE operations.departments (
        department_code VARCHAR(10) PRIMARY KEY,
        department_name VARCHAR(200) NOT NULL,
        cost_center VARCHAR(20),
        parent_department_code VARCHAR(10),
        head_employee_id INTEGER
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE operations.staffing (
        employee_id INTEGER PRIMARY KEY,
        full_name VARCHAR(200) NOT NULL,
        department_code VARCHAR(10) REFERENCES operations.departments(department_code),
        title VARCHAR(100),
        hourly_cost_rate DECIMAL(8,2),
        hourly_bill_rate DECIMAL(8,2),
        status VARCHAR(20),
        hire_date DATE,
        termination_date DATE
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE client_services.clients (
        client_id INTEGER PRIMARY KEY,
        client_name VARCHAR(300) NOT NULL,
        industry VARCHAR(100),
        segment VARCHAR(50),
        account_manager_id INTEGER,
        status VARCHAR(20),
        onboarded_date DATE,
        region VARCHAR(50)
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE client_services.clients_v1 (
        client_id INTEGER PRIMARY KEY,
        client_name VARCHAR(300),
        industry VARCHAR(100),
        segment VARCHAR(50),
        status VARCHAR(20),
        created_date DATE
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE client_services.contracts (
        contract_id INTEGER PRIMARY KEY,
        client_id INTEGER,
        contract_type VARCHAR(50),
        start_date DATE,
        end_date DATE,
        total_value DECIMAL(15,2),
        annual_value DECIMAL(15,2),
        status VARCHAR(20),
        auto_renew BOOLEAN,
        signed_date DATE
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE client_services.engagements (
        engagement_id INTEGER PRIMARY KEY,
        contract_id INTEGER,
        engagement_name VARCHAR(300),
        engagement_type VARCHAR(50),
        start_date DATE,
        end_date DATE,
        budget_hours DECIMAL(10,2),
        consumed_hours DECIMAL(10,2),
        status VARCHAR(20)
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE client_services.client_feedback (
        feedback_id INTEGER PRIMARY KEY,
        client_id INTEGER,
        engagement_id INTEGER,
        survey_date DATE,
        nps_score INTEGER,
        csat_score DECIMAL(3,1),
        comments VARCHAR(2000),
        response_status VARCHAR(20)
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE finance.gl_transactions (
        transaction_id INTEGER PRIMARY KEY,
        transaction_date DATE,
        posted_date DATE,
        account_code VARCHAR(20),
        account_name VARCHAR(200),
        department_code VARCHAR(10),
        amount DECIMAL(15,2),
        currency VARCHAR(3) DEFAULT 'USD',
        description VARCHAR(500),
        source_system VARCHAR(50),
        status VARCHAR(20),
        fiscal_year INTEGER,
        fiscal_period INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE finance.gl_transactions_archive (
        transaction_id INTEGER PRIMARY KEY,
        transaction_date DATE,
        posted_date DATE,
        account_code VARCHAR(20),
        account_name VARCHAR(200),
        department_code VARCHAR(10),
        amount DECIMAL(15,2),
        currency VARCHAR(3) DEFAULT 'USD',
        description VARCHAR(500),
        source_system VARCHAR(50),
        status VARCHAR(20),
        fiscal_year INTEGER,
        fiscal_period INTEGER,
        created_at TIMESTAMP
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE finance.revenue_recognition (
        rev_rec_id INTEGER PRIMARY KEY,
        contract_id INTEGER,
        recognition_date DATE,
        recognized_amount DECIMAL(15,2),
        deferred_amount DECIMAL(15,2),
        recognition_method VARCHAR(50),
        fiscal_year INTEGER,
        fiscal_period INTEGER,
        status VARCHAR(20),
        adjustment_reason VARCHAR(200)
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE finance.accounts_receivable (
        invoice_id INTEGER PRIMARY KEY,
        client_id INTEGER,
        invoice_date DATE,
        due_date DATE,
        amount DECIMAL(15,2),
        paid_amount DECIMAL(15,2) DEFAULT 0,
        status VARCHAR(20),
        currency VARCHAR(3) DEFAULT 'USD',
        payment_date DATE,
        aging_bucket VARCHAR(20)
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE finance.budgets (
        budget_id INTEGER PRIMARY KEY,
        department_code VARCHAR(10),
        account_code VARCHAR(20),
        fiscal_year INTEGER,
        fiscal_period INTEGER,
        budgeted_amount DECIMAL(15,2),
        revised_amount DECIMAL(15,2),
        approved_date DATE
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE operations.work_orders (
        work_order_id INTEGER PRIMARY KEY,
        engagement_id INTEGER,
        assigned_team VARCHAR(100),
        lead_consultant_id INTEGER,
        created_date DATE,
        target_completion_date DATE,
        actual_completion_date DATE,
        estimated_hours DECIMAL(8,2),
        actual_hours DECIMAL(8,2),
        status VARCHAR(20),
        priority VARCHAR(10),
        billable BOOLEAN DEFAULT TRUE
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE operations.service_delivery (
        delivery_id INTEGER PRIMARY KEY,
        engagement_id INTEGER,
        milestone_name VARCHAR(200),
        planned_date DATE,
        actual_date DATE,
        deliverable_value DECIMAL(15,2),
        acceptance_status VARCHAR(20),
        sign_off_date DATE
    )""")

    conn.execute("""
    CREATE OR REPLACE TABLE operations.timesheets (
        timesheet_id INTEGER PRIMARY KEY,
        employee_id INTEGER,
        work_order_id INTEGER,
        work_date DATE,
        hours DECIMAL(5,2),
        billable BOOLEAN,
        status VARCHAR(20),
        submitted_at TIMESTAMP,
        approved_by INTEGER
    )""")


def _insert_seed_data(conn: duckdb.DuckDBPyConnection):
    # Deterministic seed ensures evaluation results are reproducible.
    random.seed(42)

    # --- Departments ---
    departments = [
        ("ENG", "Engineering", "CC-100", None),
        ("FIN", "Finance & Accounting", "CC-200", None),
        ("OPS", "Operations", "CC-300", None),
        ("CS", "Client Services", "CC-400", None),
        ("SALES", "Sales", "CC-500", None),
        ("HR", "Human Resources", "CC-600", None),
        ("MKT", "Marketing", "CC-700", None),
        ("EXEC", "Executive", "CC-800", None),
        ("DATA", "Data & Analytics", "CC-150", "ENG"),
        ("INFRA", "Infrastructure", "CC-160", "ENG"),
        ("PMO", "Project Management Office", "CC-310", "OPS"),
        ("QA", "Quality Assurance", "CC-170", "ENG"),
    ]
    for code, name, cc, parent in departments:
        conn.execute(
            "INSERT INTO operations.departments VALUES (?, ?, ?, ?, NULL)",
            [code, name, cc, parent],
        )

    # --- Staffing (150 employees) ---
    titles = [
        "Software Engineer", "Senior Software Engineer", "Staff Engineer",
        "Data Analyst", "Senior Data Analyst", "Data Scientist",
        "Consultant", "Senior Consultant", "Principal Consultant",
        "Project Manager", "Senior Project Manager",
        "Account Manager", "Director", "VP", "Analyst",
    ]
    first_names = ["Alice", "Bob", "Carol", "David", "Eva", "Frank", "Grace",
                   "Henry", "Iris", "Jack", "Karen", "Leo", "Maya", "Nick", "Olivia",
                   "Paul", "Quinn", "Rachel", "Sam", "Tina"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
                  "Miller", "Davis", "Wilson", "Anderson", "Taylor", "Thomas",
                  "Moore", "Jackson", "Martin", "Lee", "White", "Harris", "Clark", "Lewis"]
    dept_codes = [d[0] for d in departments]
    statuses_staff = ["active"] * 12 + ["on_leave", "terminated"]

    for eid in range(1, 151):
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        dept = random.choice(dept_codes)
        title = random.choice(titles)
        cost = round(random.uniform(50, 200), 2)
        bill = round(cost * random.uniform(1.8, 3.0), 2)
        status = random.choice(statuses_staff)
        hire = date(random.randint(2018, 2025), random.randint(1, 12), random.randint(1, 28))
        term = date(2025, random.randint(6, 12), random.randint(1, 28)) if status == "terminated" else None
        conn.execute(
            "INSERT INTO operations.staffing VALUES (?,?,?,?,?,?,?,?,?)",
            [eid, name, dept, title, cost, bill, status, hire, term],
        )

    # Update department heads
    for code, *_ in departments:
        conn.execute(f"""
            UPDATE operations.departments SET head_employee_id = (
                SELECT employee_id FROM operations.staffing
                WHERE department_code = '{code}' AND status = 'active'
                LIMIT 1
            ) WHERE department_code = '{code}'
        """)

    # --- Clients (80) ---
    industries = ["Technology", "Healthcare", "Financial Services", "Manufacturing",
                  "Retail", "Energy", "Telecommunications", "Media"]
    segments = ["enterprise", "mid_market", "smb"]
    regions = ["North America", "EMEA", "APAC", "LATAM"]
    client_statuses = ["active"] * 10 + ["churned", "prospect"]

    for cid in range(1, 81):
        conn.execute(
            "INSERT INTO client_services.clients VALUES (?,?,?,?,?,?,?,?)",
            [cid, f"Client {cid:03d} - {random.choice(['Acme','Global','Prime','Nexus','Atlas','Vertex','Summit'])} {random.choice(['Corp','Inc','Ltd','Group','Partners'])}",
             random.choice(industries), random.choice(segments),
             random.randint(1, 150), random.choice(client_statuses),
             date(random.randint(2019, 2025), random.randint(1, 12), random.randint(1, 28)),
             random.choice(regions)],
        )

    # Legacy clients_v1 (stale data from old CRM)
    for cid in range(1, 51):
        conn.execute(
            "INSERT INTO client_services.clients_v1 VALUES (?,?,?,?,?,?)",
            [cid, f"Legacy Client {cid}", random.choice(industries),
             random.choice(segments), random.choice(["active", "inactive"]),
             date(2023, random.randint(1, 12), random.randint(1, 28))],
        )

    # --- Contracts (120) ---
    contract_types = ["fixed_fee", "time_and_materials", "retainer"]
    contract_statuses = ["active"] * 6 + ["expired", "terminated", "pending_renewal"]

    for ctid in range(1, 121):
        cid = random.randint(1, 80)
        ctype = random.choice(contract_types)
        start = date(random.randint(2023, 2025), random.randint(1, 12), random.randint(1, 28))
        end = start + timedelta(days=random.choice([365, 730, 180]))
        tcv = round(random.uniform(50000, 2000000), 2)
        acv = round(tcv / max(1, (end - start).days / 365), 2)
        status = random.choice(contract_statuses)
        conn.execute(
            "INSERT INTO client_services.contracts VALUES (?,?,?,?,?,?,?,?,?,?)",
            [ctid, cid, ctype, start, end, tcv, acv, status,
             random.choice([True, False]), start - timedelta(days=random.randint(7, 30))],
        )

    # --- Engagements (200) ---
    eng_types = ["implementation", "advisory", "managed_services", "staff_aug"]
    eng_statuses = ["active"] * 5 + ["completed", "on_hold", "at_risk"]

    for eid in range(1, 201):
        ctid = random.randint(1, 120)
        start = date(random.randint(2024, 2026), random.randint(1, 12), min(28, random.randint(1, 28)))
        budget_hrs = round(random.uniform(100, 5000), 2)
        consumed = round(budget_hrs * random.uniform(0.1, 1.3), 2)
        status = random.choice(eng_statuses)
        end = start + timedelta(days=random.randint(30, 365)) if status == "completed" else None
        conn.execute(
            "INSERT INTO client_services.engagements VALUES (?,?,?,?,?,?,?,?,?)",
            [eid, ctid,
             f"Engagement {eid} - {random.choice(['Platform Migration','Data Integration','Process Optimization','Cloud Transformation','Security Audit','Analytics Build'])}",
             random.choice(eng_types), start, end, budget_hrs, consumed, status],
        )

    # --- Client Feedback (400) ---
    fb_statuses = ["pending_review", "acknowledged", "action_taken"]
    for fid in range(1, 401):
        cid = random.randint(1, 80)
        eng_id = random.randint(1, 200) if random.random() > 0.3 else None
        survey_date = date(random.randint(2024, 2026), random.randint(1, 12), random.randint(1, 28))
        # Known quality issue: Q1 2025 has ~20% null NPS scores
        if survey_date.year == 2025 and survey_date.month <= 3 and random.random() < 0.20:
            nps = None
        else:
            nps = random.randint(3, 10)
        csat = round(random.uniform(2.0, 5.0), 1) if nps is not None else None
        conn.execute(
            "INSERT INTO client_services.client_feedback VALUES (?,?,?,?,?,?,?,?)",
            [fid, cid, eng_id, survey_date, nps, csat,
             random.choice(["Great experience", "Room for improvement", "Very satisfied",
                           "Communication could be better", "Excellent delivery", None]),
             random.choice(fb_statuses)],
        )

    # --- GL Transactions (5000 for current, 2000 for archive) ---
    account_map = {
        "4000": "Revenue - Services", "4010": "Revenue - Licensing",
        "4020": "Revenue - Support",
        "5000": "Cost of Revenue", "5100": "Salaries & Wages",
        "5200": "Benefits", "5300": "Contractor Costs",
        "6000": "Rent & Facilities", "6100": "Software & Tools",
        "6200": "Travel & Entertainment", "6300": "Professional Services",
        "7000": "Depreciation", "7100": "Amortization",
    }
    sources = ["SAP", "Manual", "Accrual"]
    gl_statuses = ["posted"] * 15 + ["pending", "reversed"]

    txn_id = 1
    for yr in (2025, 2026):
        max_period = 12 if yr == 2025 else 3
        for period in range(1, max_period + 1):
            for _ in range(200 if yr == 2025 else 300):
                acct_code = random.choice(list(account_map.keys()))
                dept = random.choice(dept_codes[:8])
                day = random.randint(1, 28)
                txn_date = date(yr, period, day)
                posted_date = txn_date + timedelta(days=random.randint(0, 5))
                if acct_code.startswith("4"):
                    amount = -round(random.uniform(1000, 150000), 2)  # credit (revenue)
                else:
                    amount = round(random.uniform(500, 80000), 2)  # debit (expense)
                conn.execute(
                    "INSERT INTO finance.gl_transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [txn_id, txn_date, posted_date, acct_code, account_map[acct_code],
                     dept, amount, "USD",
                     f"GL entry for {account_map[acct_code]}",
                     random.choice(sources), random.choice(gl_statuses),
                     yr, period, datetime(yr, period, day, random.randint(6, 18), 0)],
                )
                txn_id += 1

    # Archive (pre-2025 data)
    arch_id = 1
    for yr in (2023, 2024):
        for period in range(1, 13):
            for _ in range(80):
                acct_code = random.choice(list(account_map.keys()))
                dept = random.choice(dept_codes[:8])
                txn_date = date(yr, period, random.randint(1, 28))
                if acct_code.startswith("4"):
                    amount = -round(random.uniform(800, 120000), 2)
                else:
                    amount = round(random.uniform(400, 60000), 2)
                conn.execute(
                    "INSERT INTO finance.gl_transactions_archive VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [arch_id, txn_date, txn_date + timedelta(days=random.randint(0, 3)),
                     acct_code, account_map[acct_code], dept, amount, "USD",
                     f"Archive GL entry", random.choice(sources), "posted",
                     yr, period, datetime(yr, period, random.randint(1, 28), 12, 0)],
                )
                arch_id += 1

    # --- Revenue Recognition (800 rows, but stale - stops at Feb 2026) ---
    methods = ["point_in_time", "over_time", "milestone"]
    rev_statuses = ["recognized"] * 8 + ["deferred", "adjusted"]

    for rrid in range(1, 801):
        ctid = random.randint(1, 120)
        # Intentionally NO March 2026 data (stale)
        # Intentionally stops at Feb 2026 — simulates a stale table. This is the
        # data quality issue the agent should warn about.
        yr = random.choice([2025] * 8 + [2026] * 2)
        max_p = 12 if yr == 2025 else 2
        period = random.randint(1, max_p)
        rec_date = date(yr, period, 28)
        recognized = round(random.uniform(5000, 200000), 2)
        deferred = round(random.uniform(0, 50000), 2)
        status = random.choice(rev_statuses)
        adj = "Period-end adjustment" if status == "adjusted" else None
        conn.execute(
            "INSERT INTO finance.revenue_recognition VALUES (?,?,?,?,?,?,?,?,?,?)",
            [rrid, ctid, rec_date, recognized, deferred,
             random.choice(methods), yr, period, status, adj],
        )

    # --- Accounts Receivable (1200 rows) ---
    ar_statuses = ["paid"] * 6 + ["open"] * 3 + ["overdue", "written_off"]
    aging = ["current", "30_days", "60_days", "90_plus"]

    for invid in range(1, 1201):
        cid = random.randint(1, 80)
        inv_date = date(random.randint(2025, 2026), random.randint(1, 12 if 2025 else 3), random.randint(1, 28))
        due = inv_date + timedelta(days=30)
        amount = round(random.uniform(2000, 300000), 2)
        status = random.choice(ar_statuses)
        paid = amount if status == "paid" else (round(amount * random.uniform(0, 0.5), 2) if status != "open" else 0)
        pay_date = due + timedelta(days=random.randint(-5, 30)) if status == "paid" else None
        bucket = random.choice(aging) if status != "paid" else "current"
        conn.execute(
            "INSERT INTO finance.accounts_receivable VALUES (?,?,?,?,?,?,?,?,?,?)",
            [invid, cid, inv_date, due, amount, paid, status, "USD", pay_date, bucket],
        )

    # --- Budgets (200 rows) ---
    budget_accounts = ["5100", "5200", "5300", "6000", "6100", "6200"]
    bid = 1
    for yr in (2025, 2026):
        for dept in dept_codes[:8]:
            for acct in random.sample(budget_accounts, 3):
                for period in range(1, 13):
                    budgeted = round(random.uniform(20000, 200000), 2)
                    revised = round(budgeted * random.uniform(0.9, 1.15), 2) if random.random() > 0.7 else None
                    conn.execute(
                        "INSERT INTO finance.budgets VALUES (?,?,?,?,?,?,?,?)",
                        [bid, dept, acct, yr, period, budgeted, revised,
                         date(yr - 1, 11, 15)],
                    )
                    bid += 1

    # --- Work Orders (500) ---
    wo_statuses = ["completed"] * 4 + ["in_progress"] * 3 + ["draft", "cancelled"]
    priorities = ["low", "medium", "high", "critical"]

    for woid in range(1, 501):
        eid = random.randint(1, 200)
        lead = random.randint(1, 150)
        created = date(random.randint(2024, 2026), random.randint(1, 12), random.randint(1, 28))
        target = created + timedelta(days=random.randint(14, 120))
        status = random.choice(wo_statuses)
        actual = target + timedelta(days=random.randint(-10, 30)) if status == "completed" else None
        est_hrs = round(random.uniform(20, 500), 2)
        act_hrs = round(est_hrs * random.uniform(0.5, 1.5), 2) if status in ("completed", "in_progress") else 0
        conn.execute(
            "INSERT INTO operations.work_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [woid, eid, random.choice(["Team Alpha", "Team Beta", "Team Gamma", "Team Delta"]),
             lead, created, target, actual, est_hrs, act_hrs, status,
             random.choice(priorities), random.choice([True, True, True, False])],
        )

    # --- Service Delivery (300 milestones) ---
    acceptance = ["accepted"] * 5 + ["pending"] * 3 + ["rejected"]

    for did in range(1, 301):
        eid = random.randint(1, 200)
        planned = date(random.randint(2024, 2026), random.randint(1, 12), random.randint(1, 28))
        acc_status = random.choice(acceptance)
        # Known issue: 30% of completed milestones have null actual_date
        if acc_status == "accepted" and random.random() < 0.30:
            actual = None
        elif acc_status == "accepted":
            actual = planned + timedelta(days=random.randint(-5, 20))
        else:
            actual = None
        sign_off = actual + timedelta(days=random.randint(1, 7)) if actual else None
        conn.execute(
            "INSERT INTO operations.service_delivery VALUES (?,?,?,?,?,?,?,?)",
            [did, eid,
             f"Milestone {did} - {random.choice(['Phase 1 Delivery','UAT Signoff','Go-Live','Design Review','Data Migration','Integration Testing'])}",
             planned, actual, round(random.uniform(10000, 500000), 2),
             acc_status, sign_off],
        )

    # --- Timesheets (15000 rows) ---
    ts_statuses = ["approved"] * 8 + ["submitted", "rejected"]

    for tsid in range(1, 15001):
        emp = random.randint(1, 150)
        wo = random.randint(1, 500)
        work_date = date(2025, 1, 1) + timedelta(days=random.randint(0, 455))
        hours = round(random.uniform(1, 10), 2)
        billable = random.random() > 0.25
        status = random.choice(ts_statuses)
        submitted = datetime(work_date.year, work_date.month, work_date.day, 17, random.randint(0, 59))
        # Simulates a workflow bug that started in January — the agent should flag
        # this when querying recent timesheets. Null rate is conditional on date.
        if work_date >= date(2026, 1, 1) and random.random() < 0.15:
            approved_by = None
        elif status == "approved":
            approved_by = random.randint(1, 150)
        else:
            approved_by = None
        conn.execute(
            "INSERT INTO operations.timesheets VALUES (?,?,?,?,?,?,?,?,?)",
            [tsid, emp, wo, work_date, hours, billable, status, submitted, approved_by],
        )

    conn.execute("CHECKPOINT")


if __name__ == "__main__":
    seed_warehouse()
