#!/usr/bin/env python3
"""Store consolidated SA electricity tariff data in project_intelligence.db"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "project_intelligence.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# --- Table 1: sa_electricity_tariffs ---
c.execute("""
CREATE TABLE IF NOT EXISTS sa_electricity_tariffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    tariff_name TEXT NOT NULL,
    tariff_year TEXT NOT NULL,
    season TEXT,
    period TEXT,
    rate_r_per_kwh REAL,
    rate_eur_per_kwh REAL,
    escalation_pct REAL,
    source TEXT,
    verified_date TEXT,
    note TEXT
)
""")

tariff_rows = [
    # City Power JHB
    ("City Power JHB", "Business", "2024/25", "all", "blended", 2.289, 0.111, None, "joburg.org.za tariff schedule", "2026-02-10", "Municipal C&I rate. Smart City offtake benchmark."),
    ("City Power JHB", "Business (est)", "2025/26", "all", "blended", 2.581, 0.125, 12.74, "Estimated (12.74% NERSA increase)", "2026-02-11", "Projected. Municipalities typically pass through Eskom increase + own markup."),

    # Eskom Business (flat)
    ("Eskom", "Business (flat)", "2024/25", "all", "blended", 2.81, 0.136, None, "operations.json", "2026-02-10", "NWL IC power baseline. Megaflex energy-only ~50-70% of Homeflex."),
    ("Eskom", "Business (flat est)", "2025/26", "all", "blended", 3.168, 0.154, 12.74, "Estimated (NERSA approved avg)", "2026-02-11", "Projected at approved 12.74% increase."),

    # Eskom Homeflex TOU 2024/25
    ("Eskom", "Homeflex", "2024/25", "high_demand", "peak", 7.04, 0.342, None, "ecoflow.com/za verified", "2026-02-10", "Jun-Aug. Ceiling benchmark (residential)."),
    ("Eskom", "Homeflex", "2024/25", "high_demand", "standard", 2.14, 0.104, None, "ecoflow.com/za verified", "2026-02-10", "Jun-Aug"),
    ("Eskom", "Homeflex", "2024/25", "high_demand", "offpeak", 1.02, 0.050, None, "ecoflow.com/za verified", "2026-02-10", "Jun-Aug"),
    ("Eskom", "Homeflex", "2024/25", "low_demand", "peak", 2.00, 0.097, None, "ecoflow.com/za verified", "2026-02-10", "Sep-May"),
    ("Eskom", "Homeflex", "2024/25", "low_demand", "standard", 2.30, 0.112, None, "ecoflow.com/za verified", "2026-02-10", "Sep-May"),
    ("Eskom", "Homeflex", "2024/25", "low_demand", "offpeak", 1.59, 0.077, None, "ecoflow.com/za verified", "2026-02-10", "Sep-May"),

    # Eskom Homeflex TOU 2025/26 (projected per NERSA component increases)
    ("Eskom", "Homeflex", "2025/26", "high_demand", "peak", 7.67, 0.372, 9.0, "Projected (9% HD peak)", "2026-02-11", "Jun-Aug. R7.04 x 1.09"),
    ("Eskom", "Homeflex", "2025/26", "high_demand", "standard", 1.90, 0.092, -11.0, "Projected (-11% HD standard)", "2026-02-11", "Jun-Aug. R2.14 x 0.89"),
    ("Eskom", "Homeflex", "2025/26", "high_demand", "offpeak", 1.12, 0.054, 10.0, "Projected (10% HD offpeak)", "2026-02-11", "Jun-Aug. R1.02 x 1.10"),
    ("Eskom", "Homeflex", "2025/26", "low_demand", "peak", 2.76, 0.134, 38.0, "Projected (38% LD peak)", "2026-02-11", "Sep-May. R2.00 x 1.38. Big jump!"),
    ("Eskom", "Homeflex", "2025/26", "low_demand", "standard", 2.60, 0.126, 13.0, "Projected (13% LD standard)", "2026-02-11", "Sep-May. R2.30 x 1.13"),
    ("Eskom", "Homeflex", "2025/26", "low_demand", "offpeak", 2.02, 0.098, 27.0, "Projected (27% LD offpeak)", "2026-02-11", "Sep-May. R1.59 x 1.27"),

    # LanRED IC pricing
    ("LanRED (IC)", "Eskom -10%", "2024/25", "all", "blended", 2.53, 0.123, 10.0, "operations.json", "2026-02-10", "NWL buys from LanRED. R2.81 x 0.9. 10% p.a. escalation."),
    ("LanRED (IC)", "Eskom -10% (est)", "2025/26", "all", "blended", 2.78, 0.135, 10.0, "Model assumption", "2026-02-11", "R2.53 x 1.10"),

    # PPA market rates
    ("Market", "C&I Solar PPA (low)", "2024/25", "all", "blended", 0.85, 0.041, None, "SAPVIA/GreenCape", "2026-02-10", "Bottom of SA C&I PPA range"),
    ("Market", "C&I Solar PPA (mid)", "2024/25", "all", "blended", 1.20, 0.058, None, "SAPVIA/GreenCape", "2026-02-10", "Mid-market C&I PPA"),
    ("Market", "C&I Solar PPA (high)", "2024/25", "all", "blended", 1.80, 0.087, None, "SAPVIA/GreenCape", "2026-02-10", "Premium firm-capacity PPA"),
    ("Market", "Wheeled Power (low)", "2024/25", "all", "blended", 1.20, 0.058, None, "Market data", "2026-02-10", "Wheeled renewable energy"),
    ("Market", "Wheeled Power (mid)", "2024/25", "all", "blended", 1.50, 0.073, None, "Market data", "2026-02-10", "Wheeled renewable energy"),
    ("Market", "Wheeled Power (high)", "2024/25", "all", "blended", 2.20, 0.107, None, "Market data", "2026-02-10", "Wheeled renewable energy"),
]

c.executemany("""
INSERT INTO sa_electricity_tariffs
    (provider, tariff_name, tariff_year, season, period, rate_r_per_kwh, rate_eur_per_kwh, escalation_pct, source, verified_date, note)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", tariff_rows)

# --- Table 2: sa_tariff_escalation ---
c.execute("""
CREATE TABLE IF NOT EXISTS sa_tariff_escalation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year TEXT NOT NULL,
    nersa_approved_pct REAL,
    actual_avg_pct REAL,
    model_assumption_pct REAL,
    source TEXT,
    note TEXT
)
""")

escalation_rows = [
    ("2019/20", 9.41, None, 10.0, "NERSA MYPD4", "Pre-COVID baseline."),
    ("2020/21", 6.90, None, 10.0, "NERSA MYPD4", "COVID-era suppressed increase."),
    ("2021/22", 15.06, None, 10.0, "NERSA MYPD4", "Large catch-up increase."),
    ("2022/23", 9.61, None, 10.0, "NERSA MYPD4", None),
    ("2023/24", 18.65, None, 10.0, "NERSA MYPD5", "Record increase. Eskom debt crisis."),
    ("2024/25", 12.74, 12.74, 10.0, "NERSA MYPD5", "Current year. TOU structure changes (peak compression)."),
    ("2025/26", 12.74, None, 10.0, "NERSA MYPD5 (est)", "Expected similar. Multi-year determination."),
    ("2026/27", None, None, 10.0, "Model assumption", "No NERSA guidance yet. 10% conservative vs 12-18% actuals."),
]

c.executemany("""
INSERT INTO sa_tariff_escalation
    (year, nersa_approved_pct, actual_avg_pct, model_assumption_pct, source, note)
VALUES (?, ?, ?, ?, ?, ?)
""", escalation_rows)

conn.commit()

# Verify
print("=== sa_electricity_tariffs ===")
for row in c.execute("SELECT id, provider, tariff_name, tariff_year, season, period, rate_r_per_kwh, escalation_pct FROM sa_electricity_tariffs ORDER BY id"):
    print(row)

print("\n=== sa_tariff_escalation ===")
for row in c.execute("SELECT * FROM sa_tariff_escalation ORDER BY year"):
    print(row)

print(f"\nTariff rows: {c.execute('SELECT COUNT(*) FROM sa_electricity_tariffs').fetchone()[0]}")
print(f"Escalation rows: {c.execute('SELECT COUNT(*) FROM sa_tariff_escalation').fetchone()[0]}")

conn.close()
print("\nDone. Stored in:", os.path.abspath(DB_PATH))
