#!/usr/bin/env python3
"""Create SQLite structured database for project intelligence data.

Run: python3 scripts/create_intelligence_db.py

Creates data/project_intelligence.db with tables:
  - eskom_tou_tariffs: Eskom Time-of-Use tariff rates by season/period
  - energy_benchmarks: SA solar PV and BESS cost/performance benchmarks
  - bess_arbitrage_model: 2-cycle seasonal arbitrage model parameters
"""
import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "project_intelligence.db")

def main():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Table 1: Eskom TOU Tariffs ──
    c.execute('''CREATE TABLE IF NOT EXISTS eskom_tou_tariffs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tariff_name TEXT NOT NULL,
        tariff_year TEXT NOT NULL,
        season TEXT NOT NULL,
        season_months TEXT,
        period TEXT NOT NULL,
        rate_r_per_kwh REAL NOT NULL,
        source TEXT,
        verified_date TEXT,
        note TEXT
    )''')

    tariffs = [
        ('Homeflex', '2024/25', 'high_demand', 'Jun-Aug', 'peak', 7.04, 'ecoflow.com/za', '2026-02-10', None),
        ('Homeflex', '2024/25', 'high_demand', 'Jun-Aug', 'standard', 2.14, 'ecoflow.com/za', '2026-02-10', None),
        ('Homeflex', '2024/25', 'high_demand', 'Jun-Aug', 'offpeak', 1.02, 'ecoflow.com/za', '2026-02-10', None),
        ('Homeflex', '2024/25', 'low_demand', 'Sep-May', 'peak', 2.00, 'ecoflow.com/za', '2026-02-10', None),
        ('Homeflex', '2024/25', 'low_demand', 'Sep-May', 'standard', 2.30, 'ecoflow.com/za', '2026-02-10', None),
        ('Homeflex', '2024/25', 'low_demand', 'Sep-May', 'offpeak', 1.59, 'ecoflow.com/za', '2026-02-10', None),
        ('Homeflex', '2024/25', 'annual_weighted', 'All', 'peak', 3.26, 'Calculated', '2026-02-10', '3mo HD + 9mo LD weighted'),
        ('Homeflex', '2024/25', 'annual_weighted', 'All', 'offpeak', 1.45, 'Calculated', '2026-02-10', '3mo HD + 9mo LD weighted'),
    ]
    c.executemany(
        'INSERT INTO eskom_tou_tariffs (tariff_name, tariff_year, season, season_months, period, rate_r_per_kwh, source, verified_date, note) VALUES (?,?,?,?,?,?,?,?,?)',
        tariffs
    )

    # ── Table 2: Energy Benchmarks ──
    c.execute('''CREATE TABLE IF NOT EXISTS energy_benchmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        metric TEXT NOT NULL,
        value REAL,
        unit TEXT,
        range_low REAL,
        range_high REAL,
        region TEXT DEFAULT 'South Africa',
        year TEXT,
        source TEXT,
        note TEXT
    )''')

    benchmarks = [
        ('solar_pv', 'installed_cost', 15000, 'R/kWp', 12000, 18000, 'South Africa', '2024/25', 'GreenCape', 'C&I mid-range'),
        ('solar_pv', 'installed_cost_eur', 728, 'EUR/kWp', 583, 874, 'South Africa', '2024/25', 'GreenCape', 'At R20.6/EUR'),
        ('solar_pv', 'capacity_factor', 21.5, '%', 21, 22, 'Gauteng', '2024/25', 'CSIR', 'Fixed-tilt'),
        ('solar_pv', 'degradation', 0.5, '%/yr', 0.3, 0.7, 'Global', '2024', 'Industry', 'Mono-PERC'),
        ('solar_pv', 'ppa_rate', 2.0, 'R/kWh', 1.50, 2.50, 'South Africa', '2024/25', 'Market', 'C&I PPA'),
        ('solar_pv', 'asset_life', 25, 'years', 20, 30, 'Global', '2024', 'Industry', None),
        ('bess', 'installed_cost', 7500, 'R/kWh', 6000, 10000, 'South Africa', '2024/25', 'GreenCape', 'LFP Li-ion'),
        ('bess', 'installed_cost_eur', 364, 'EUR/kWh', 291, 485, 'South Africa', '2024/25', 'GreenCape', 'At R20.6/EUR'),
        ('bess', 'roundtrip_efficiency', 85, '%', 85, 90, 'Global', '2024', 'Industry', 'LFP chemistry'),
        ('bess', 'usable_dod', 90, '%', 80, 95, 'Global', '2024', 'Industry', None),
        ('bess', 'degradation_260cyc', 2.0, '%/yr', 1.5, 2.5, 'Global', '2024', 'BloombergNEF', '260 cycles/yr'),
        ('bess', 'degradation_456cyc', 3.0, '%/yr', 2.5, 3.5, 'Global', '2024', 'Interpolated', '456 cycles/yr (2-cycle seasonal)'),
        ('bess', 'degradation_730cyc', 4.0, '%/yr', 3.5, 4.5, 'Global', '2024', 'BloombergNEF', '730 cycles/yr (2/day)'),
        ('bess', 'asset_life', 10, 'years', 8, 15, 'Global', '2024', 'Industry', 'LFP at 80% DoD'),
    ]
    c.executemany(
        'INSERT INTO energy_benchmarks (category, metric, value, unit, range_low, range_high, region, year, source, note) VALUES (?,?,?,?,?,?,?,?,?,?)',
        benchmarks
    )

    # ── Table 3: BESS Arbitrage Model ──
    c.execute('''CREATE TABLE IF NOT EXISTS bess_arbitrage_model (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_name TEXT NOT NULL,
        season TEXT NOT NULL,
        cycle_name TEXT NOT NULL,
        charge_source TEXT,
        charge_rate_r_kwh REAL,
        discharge_peak_r_kwh REAL,
        rt_efficiency REAL,
        net_spread_r_kwh REAL,
        days_per_season REAL,
        cycles_per_day INTEGER,
        annual_cycles INTEGER,
        note TEXT
    )''')

    arbitrage = [
        ('2_cycle_seasonal', 'high_demand', 'Cycle 1 (Grid)', 'Grid off-peak', 1.02, 7.04, 0.85, 4.96, 91.2, 1, 91, 'Grid off-peak → morning peak'),
        ('2_cycle_seasonal', 'high_demand', 'Cycle 2 (Solar)', 'Own solar', 0.10, 7.04, 0.85, 5.88, 91.2, 1, 91, 'Solar → evening peak'),
        ('2_cycle_seasonal', 'low_demand', 'Cycle 2 (Solar)', 'Own solar', 0.10, 2.00, 0.85, 1.60, 273.6, 1, 274, 'Solar → peak only; Grid spread R0.11 not viable'),
    ]
    c.executemany(
        'INSERT INTO bess_arbitrage_model (model_name, season, cycle_name, charge_source, charge_rate_r_kwh, discharge_peak_r_kwh, rt_efficiency, net_spread_r_kwh, days_per_season, cycles_per_day, annual_cycles, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
        arbitrage
    )

    conn.commit()

    # Verify
    for table in ['eskom_tou_tariffs', 'energy_benchmarks', 'bess_arbitrage_model']:
        c.execute(f'SELECT COUNT(*) FROM {table}')
        count = c.fetchone()[0]
        print(f"  {table}: {count} rows")

    conn.close()
    print(f"\nDatabase: {DB_PATH}")
    print(f"Size: {os.path.getsize(DB_PATH):,} bytes")

if __name__ == "__main__":
    main()
