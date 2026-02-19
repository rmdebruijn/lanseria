#!/usr/bin/env python3
"""Add management report tables to guarantor_analysis.db.

Run: python scripts/add_mgmt_report_tables.py

Idempotent migration — all tables use CREATE TABLE IF NOT EXISTS.

Adds the following tables to data/guarantor_analysis.db:
  - mgmt_report_kpis:        One row per entity per report_date. Captures KPIs
                              extracted from management reports (vacancy, collections,
                              NOI, lease expiry, solar PV, capex, etc.).
  - mgmt_report_tenants:     Per-tenant rent roll data per entity per report_date.
  - mgmt_report_arrears:     Per-debtor arrears schedule per entity per report_date.
  - data_source_variances:   Cross-source reconciliation variances per entity per
                              report_date (e.g. entity financials vs. property-level
                              reports, insurance values vs. book values).
  - mgmt_report_solar_pv:    Monthly solar PV generation and savings per entity
                              per report_date.
"""
import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "guarantor_analysis.db")


def main():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Table 1: mgmt_report_kpis ──
    # One row per entity per report_date.
    # UNIQUE constraint on (entity_key, report_date) prevents duplicate rows on re-run.
    c.execute('''CREATE TABLE IF NOT EXISTS mgmt_report_kpis (
        id                          INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_key                  TEXT    NOT NULL,
        entity_name                 TEXT,
        report_date                 TEXT    NOT NULL,
        guarantor_group             TEXT,
        total_gla_m2                REAL,
        vacancy_rate_pct            REAL,
        vacancy_gla_m2              REAL,
        collections_pct             REAL,
        trading_density_per_m2      REAL,
        net_income_ytd              REAL,
        net_income_budget           REAL,
        net_income_variance         REAL,
        noi                         REAL,
        finance_costs               REAL,
        property_net_income_monthly REAL,
        national_tenant_pct         REAL,
        anchor_count                INTEGER,
        lease_expiry_12m_pct        REAL,
        weighted_escalation         REAL,
        utility_recovery_composite  REAL,
        has_solar_pv                INTEGER,
        has_active_capex            INTEGER,
        solar_kwp                   REAL,
        solar_savings_ytd           REAL,
        quality_score               REAL,
        quality_flags               TEXT,
        capex_ytd                   REAL,
        arrears_total               REAL,
        tenant_count                INTEGER,
        created_at                  TEXT    DEFAULT (datetime('now')),
        UNIQUE (entity_key, report_date)
    )''')

    # ── Table 2: mgmt_report_tenants ──
    # Per-tenant rent roll entry per entity per report_date.
    c.execute('''CREATE TABLE IF NOT EXISTS mgmt_report_tenants (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_key     TEXT    NOT NULL,
        report_date    TEXT    NOT NULL,
        tenant_name    TEXT    NOT NULL,
        trading_name   TEXT,
        gla_m2         REAL,
        lease_start    TEXT,
        lease_end      TEXT,
        rental_monthly REAL,
        rental_per_m2  REAL,
        escalation_pct REAL,
        tenant_type    TEXT,
        renewal_status TEXT,
        created_at     TEXT    DEFAULT (datetime('now'))
    )''')

    # ── Table 3: mgmt_report_arrears ──
    # Per-debtor arrears entry per entity per report_date.
    c.execute('''CREATE TABLE IF NOT EXISTS mgmt_report_arrears (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_key       TEXT    NOT NULL,
        report_date      TEXT    NOT NULL,
        tenant_name      TEXT    NOT NULL,
        amount           REAL,
        days_outstanding INTEGER,
        status           TEXT,
        action           TEXT,
        deposit_held     REAL,
        created_at       TEXT    DEFAULT (datetime('now'))
    )''')

    # ── Table 4: data_source_variances ──
    # Cross-source reconciliation variances per entity per report_date.
    # variance_type examples: net_income_entity_vs_property, revenue_report_vs_gl,
    #                         insured_vs_book.
    c.execute('''CREATE TABLE IF NOT EXISTS data_source_variances (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_key      TEXT    NOT NULL,
        report_date     TEXT    NOT NULL,
        variance_type   TEXT    NOT NULL,
        source_a        TEXT,
        source_b        TEXT,
        source_a_value  REAL,
        source_b_value  REAL,
        difference      REAL,
        explanation     TEXT,
        severity        TEXT,
        created_at      TEXT    DEFAULT (datetime('now'))
    )''')

    # ── Table 5: mgmt_report_solar_pv ──
    # Monthly solar PV generation and savings per entity per report_date.
    c.execute('''CREATE TABLE IF NOT EXISTS mgmt_report_solar_pv (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_key  TEXT    NOT NULL,
        report_date TEXT    NOT NULL,
        month       TEXT    NOT NULL,
        target_kwh  REAL,
        actual_kwh  REAL,
        savings_rand REAL,
        created_at  TEXT    DEFAULT (datetime('now'))
    )''')

    conn.commit()

    # ── Verify: print table names and row counts ──
    tables = [
        'mgmt_report_kpis',
        'mgmt_report_tenants',
        'mgmt_report_arrears',
        'data_source_variances',
        'mgmt_report_solar_pv',
    ]
    print("Tables in guarantor_analysis.db:")
    for table in tables:
        c.execute(f'SELECT COUNT(*) FROM {table}')
        count = c.fetchone()[0]
        print(f"  {table}: {count} rows")

    conn.close()
    print(f"\nDatabase: {DB_PATH}")
    print(f"Size: {os.path.getsize(DB_PATH):,} bytes")


if __name__ == "__main__":
    main()
