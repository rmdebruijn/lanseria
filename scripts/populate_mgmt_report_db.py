#!/usr/bin/env python3
"""Populate SQLite management report tables from extracted JSON files.

Run: python3 scripts/populate_mgmt_report_db.py

Reads *_mgmt_report_structured.json files from context/Guarantor/Phoenix group/
and inserts into data/guarantor_analysis.db tables:
  - mgmt_report_kpis
  - mgmt_report_tenants
  - mgmt_report_arrears
  - data_source_variances
  - mgmt_report_solar_pv
"""
import json
import os
import sqlite3
from pathlib import Path

SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = SCRIPT_DIR.parent
DB_DIR = MODEL_DIR / "data"
DB_PATH = DB_DIR / "guarantor_analysis.db"
PROJECT_ROOT = MODEL_DIR.parent.parent
CONTEXT_DIR = PROJECT_ROOT / "context" / "Guarantor" / "Phoenix" / "Structured Data" / "Broll Reports"


def _sf(v):
    """Safe float."""
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def populate_kpis(cursor, entity_key, report_date, mr_data, mr_analysis):
    """Insert or replace a row in mgmt_report_kpis."""
    ds = mr_data.get("derived_signals", {})
    pd = mr_data.get("property_details", {})
    ls = mr_data.get("leasing_summary", {})
    ao = mr_data.get("arrears_overview", {})
    fs = mr_data.get("financial_summary", {})
    isp = mr_data.get("income_statement_property", {})
    sp = mr_data.get("solar_pv", {})
    meta = mr_data.get("metadata", {})

    entity_name = meta.get("entity", {}).get("legal_name", entity_key)
    group = meta.get("entity", {}).get("guarantor_group", "phoenix")

    net_income_ytd = fs.get("net_income_ytd", {})
    noi_item = isp.get("NOI", {})
    fc_item = isp.get("finance_costs", {})

    cursor.execute("""
        INSERT OR REPLACE INTO mgmt_report_kpis (
            entity_key, entity_name, report_date, guarantor_group,
            total_gla_m2, vacancy_rate_pct, vacancy_gla_m2, collections_pct,
            trading_density_per_m2, net_income_ytd, net_income_budget, net_income_variance,
            noi, finance_costs, property_net_income_monthly,
            national_tenant_pct, anchor_count, lease_expiry_12m_pct, weighted_escalation,
            utility_recovery_composite, has_solar_pv, has_active_capex,
            solar_kwp, solar_savings_ytd, quality_score, quality_flags,
            capex_ytd, arrears_total, tenant_count
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        entity_key, entity_name, report_date, group,
        _sf(pd.get("total_gla_m2")),
        _sf(ls.get("vacancy_rate_pct")),
        _sf(ls.get("vacancy_gla_m2")),
        _sf(ao.get("collections_pct")),
        _sf(ds.get("trading_density")),
        _sf(net_income_ytd.get("actual") if isinstance(net_income_ytd, dict) else None),
        _sf(net_income_ytd.get("budget") if isinstance(net_income_ytd, dict) else None),
        _sf(net_income_ytd.get("variance") if isinstance(net_income_ytd, dict) else None),
        _sf(noi_item.get("actual") if isinstance(noi_item, dict) else None),
        _sf(fc_item.get("actual") if isinstance(fc_item, dict) else None),
        _sf(ds.get("property_net_income_monthly")),
        _sf(ds.get("national_tenant_pct")),
        ds.get("anchor_count"),
        _sf(ds.get("lease_expiry_concentration_12m")),
        _sf(ds.get("weighted_escalation")),
        _sf(ds.get("utility_recovery_composite")),
        1 if ds.get("has_solar_pv") else 0,
        1 if ds.get("has_active_capex") else 0,
        _sf(sp.get("system_kwp")),
        _sf((sp.get("savings_ytd") or {}).get("actual") if isinstance(sp.get("savings_ytd"), dict) else None),
        _sf(mr_analysis.get("quality_score")) if mr_analysis else None,
        json.dumps(mr_analysis.get("quality_flags", [])) if mr_analysis else "[]",
        _sf(isp.get("capex", {}).get("actual") if isinstance(isp.get("capex"), dict) else None),
        _sf(ao.get("total")),
        pd.get("tenant_count"),
    ))


def populate_tenants(cursor, entity_key, report_date, mr_data):
    """Insert tenant rows."""
    tenants = mr_data.get("tenant_data", [])
    for t in tenants:
        if not t.get("name"):
            continue
        cursor.execute("""
            INSERT INTO mgmt_report_tenants (
                entity_key, report_date, tenant_name, trading_name,
                gla_m2, lease_start, lease_end, rental_monthly,
                rental_per_m2, escalation_pct, tenant_type, renewal_status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            entity_key, report_date,
            t.get("name"), t.get("trading_name"),
            _sf(t.get("gla_m2")), t.get("lease_start"), t.get("lease_end"),
            _sf(t.get("rental_monthly")), _sf(t.get("rental_per_m2")),
            _sf(t.get("escalation_pct")), t.get("tenant_type"),
            t.get("renewal_status"),
        ))


def populate_arrears(cursor, entity_key, report_date, mr_data):
    """Insert arrears detail rows."""
    arrears = mr_data.get("arrears_detail", [])
    for a in arrears:
        if not a.get("tenant_name"):
            continue
        cursor.execute("""
            INSERT INTO mgmt_report_arrears (
                entity_key, report_date, tenant_name, amount,
                days_outstanding, status, action, deposit_held
            ) VALUES (?,?,?,?,?,?,?,?)
        """, (
            entity_key, report_date,
            a.get("tenant_name"), _sf(a.get("amount")),
            a.get("days_outstanding"), a.get("status"),
            a.get("action"), _sf(a.get("deposit_held")),
        ))


def populate_variances(cursor, entity_key, report_date, mr_data):
    """Insert data source variance rows."""
    variances = mr_data.get("variances", {})
    for vtype, vd in variances.items():
        if not isinstance(vd, dict):
            continue
        diff = vd.get("difference")
        if diff is None and vd.get("source_a_value") is not None and vd.get("source_b_value") is not None:
            try:
                diff = float(vd["source_a_value"]) - float(vd["source_b_value"])
            except (ValueError, TypeError):
                diff = None

        # Determine severity
        severity = "low"
        if diff is not None:
            ref = max(abs(_sf(vd.get("source_a_value")) or 1), abs(_sf(vd.get("source_b_value")) or 1))
            if ref > 0 and abs(diff) / ref > 0.30:
                severity = "high"
            elif ref > 0 and abs(diff) / ref > 0.10:
                severity = "medium"

        cursor.execute("""
            INSERT INTO data_source_variances (
                entity_key, report_date, variance_type,
                source_a, source_b, source_a_value, source_b_value,
                difference, explanation, severity
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            entity_key, report_date, vtype,
            vd.get("source_a"), vd.get("source_b"),
            _sf(vd.get("source_a_value")), _sf(vd.get("source_b_value")),
            _sf(diff), vd.get("explanation"), severity,
        ))


def populate_solar(cursor, entity_key, report_date, mr_data):
    """Insert solar PV monthly production rows."""
    sp = mr_data.get("solar_pv", {})
    if not sp.get("has_solar"):
        return
    monthly = sp.get("monthly_production", sp.get("monthly_production_kwh", []))
    for m in monthly:
        if not isinstance(m, dict) or not m.get("month"):
            continue
        target = m.get("target_kwh") or m.get("target")
        actual = m.get("actual_kwh") or m.get("actual")
        cursor.execute("""
            INSERT INTO mgmt_report_solar_pv (
                entity_key, report_date, month,
                target_kwh, actual_kwh, savings_rand
            ) VALUES (?,?,?,?,?,?)
        """, (
            entity_key, report_date, m.get("month"),
            _sf(target), _sf(actual),
            _sf(m.get("savings_rand")),
        ))


def main():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Run scripts/add_mgmt_report_tables.py first.")
        return

    # Import analysis engine for quality scoring
    import sys
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        import guarantor_analysis as ga
    except ImportError:
        ga = None
        print("WARNING: guarantor_analysis module not found, quality scores will be null")

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # Find all mgmt report JSONs
    json_files = sorted(CONTEXT_DIR.glob("*_mgmt_report_structured.json"))
    if not json_files:
        print(f"No *_mgmt_report_structured.json files found in {CONTEXT_DIR}")
        conn.close()
        return

    print(f"Found {len(json_files)} management report JSONs")

    for jf in json_files:
        stem = jf.stem
        print(f"\nProcessing: {stem}")

        with open(jf, "r") as f:
            mr_data = json.load(f)

        meta = mr_data.get("metadata", {})
        entity_key = meta.get("entity", {}).get("entity_key", stem)
        rp = meta.get("reporting_period", {})
        report_date = rp.get("end_date", "2025-12-31")

        # Run analysis
        mr_analysis = None
        if ga:
            mr_analysis = ga.analyse_mgmt_report(mr_data)
            print(f"  Quality score: {mr_analysis.get('quality_score', 'N/A')}")
            print(f"  Flags: {', '.join(mr_analysis.get('quality_flags', []))}")

        # Clear existing data for this entity+date (idempotent)
        for table in ["mgmt_report_kpis", "mgmt_report_tenants", "mgmt_report_arrears",
                       "data_source_variances", "mgmt_report_solar_pv"]:
            c.execute(f"DELETE FROM {table} WHERE entity_key = ? AND report_date = ?",
                      (entity_key, report_date))

        populate_kpis(c, entity_key, report_date, mr_data, mr_analysis)
        populate_tenants(c, entity_key, report_date, mr_data)
        populate_arrears(c, entity_key, report_date, mr_data)
        populate_variances(c, entity_key, report_date, mr_data)
        populate_solar(c, entity_key, report_date, mr_data)

        conn.commit()

        # Summary
        for table in ["mgmt_report_kpis", "mgmt_report_tenants", "mgmt_report_arrears",
                       "data_source_variances", "mgmt_report_solar_pv"]:
            c.execute(f"SELECT COUNT(*) FROM {table} WHERE entity_key = ?", (entity_key,))
            count = c.fetchone()[0]
            print(f"  {table}: {count} rows")

    # Final summary
    print("\n" + "=" * 60)
    print("Database Summary:")
    for table in ["mgmt_report_kpis", "mgmt_report_tenants", "mgmt_report_arrears",
                   "data_source_variances", "mgmt_report_solar_pv"]:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        count = c.fetchone()[0]
        print(f"  {table}: {count} total rows")

    conn.close()
    print(f"\nDatabase: {DB_PATH}")
    print(f"Size: {os.path.getsize(str(DB_PATH)):,} bytes")


if __name__ == "__main__":
    main()
