"""Model configuration — loads all JSON configs, no Streamlit."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from functools import lru_cache

from engine.currency import EUR, ZAR, FxRate

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@lru_cache(maxsize=16)
def load_config(name: str) -> dict:
    """Load a JSON config file by name (without .json extension)."""
    path = _CONFIG_DIR / f"{name}.json"
    with open(path, "r") as f:
        return json.load(f)


def load_rates() -> dict:
    return load_config("rates")


def load_structure() -> dict:
    return load_config("structure")


def load_financing() -> dict:
    return load_config("financing")


def load_waterfall_config() -> dict:
    return load_config("waterfall")


def load_operations() -> dict:
    return load_config("operations")


def load_assets() -> dict:
    return load_config("assets")


def load_fees() -> dict:
    return load_config("fees")


def load_project() -> dict:
    return load_config("project")


@dataclass
class ModelConfig:
    """Consolidated model configuration from all JSON files."""
    structure: dict = field(default_factory=dict)
    financing: dict = field(default_factory=dict)
    waterfall: dict = field(default_factory=dict)
    operations: dict = field(default_factory=dict)
    assets: dict = field(default_factory=dict)
    fees: dict = field(default_factory=dict)
    project: dict = field(default_factory=dict)
    rates: dict = field(default_factory=dict)

    # Derived constants
    ic_margin: float = 0.0
    sr_facility_rate: float = 0.0
    mz_facility_rate: float = 0.0
    sr_ic_rate: float = 0.0
    mz_ic_rate: float = 0.0
    sr_repayments: int = 14
    mz_repayments: int = 10
    fd_rate_eur: float = 0.0
    fd_rate_zar: float = 0.0
    od_rate: float = 0.0
    mz_div_gap_rate: float = 0.0
    zar_swap_rate: float = 0.0
    tax_rate: float = 0.0
    fx_rate: float = 0.0
    fx: FxRate | None = None
    dsra_rate: float = 0.0
    cc_irr_target: float = 0.0
    ops_reserve_coverage: float = 0.0

    # Equity
    equity_nwl: float = 0.0
    equity_lanred: float = 0.0
    equity_twx: float = 0.0

    @classmethod
    def load(cls) -> "ModelConfig":
        """Load all configs and derive constants."""
        cfg = cls(
            structure=load_structure(),
            financing=load_financing(),
            waterfall=load_waterfall_config(),
            operations=load_operations(),
            assets=load_assets(),
            fees=load_fees(),
            project=load_project(),
            rates=load_rates(),
        )
        cfg._derive_constants()
        return cfg

    def _derive_constants(self):
        rates = self.rates
        sr = self.structure["sources"]["senior_debt"]
        mz = self.structure["sources"]["mezzanine"]
        proj = self.project

        self.ic_margin = rates.get("intercompany_margin", 0.005)
        self.sr_facility_rate = rates["senior_debt"]["facility_rate"]
        self.mz_facility_rate = rates["mezzanine"]["total_rate"]
        self.sr_ic_rate = self.sr_facility_rate + self.ic_margin  # 5.20%
        self.mz_ic_rate = self.mz_facility_rate + self.ic_margin  # 14.75%
        self.sr_repayments = sr["repayments"]                     # 14
        self.mz_repayments = mz.get("repayments", 10)             # 10
        self.fd_rate_eur = rates["fixed_deposits"]["eur"]["rate"]  # 3.5%
        self.fd_rate_zar = rates["fixed_deposits"]["zar"]["rate"]  # 9.0%
        self.od_rate = rates["ic_overdraft"]["rate"]               # 10%
        self.mz_div_gap_rate = rates["cc_irr"]["gap"]              # 5.25%
        self.zar_swap_rate = rates["swap"]["zar_rate"]             # 9.69%
        self.cc_irr_target = rates["cc_irr"]["target"]             # 20%
        self.tax_rate = rates["tax"]["corporate_rate"]             # 27%
        self.fx_rate = rates["fx"]["eur_zar"]                      # 20.0
        self.fx = FxRate(self.fx_rate)

        # Waterfall cascade parameters
        ec = self.waterfall["entity_cascade"]
        self.ops_reserve_coverage = ec["ops_reserve_coverage_pct"]  # 1.0

        # DSRA rate from project.json (legacy)
        params = proj.get("model_parameters", {})
        self.dsra_rate = params.get("dsra_rate", 0.09)

        # Equity
        eq = params.get("equity_in_subsidiaries", {})
        fx = proj["project"]["fx_rates"]["EUR_ZAR"]
        self.equity_nwl = ZAR(eq.get("nwl_pct", 0.93) * eq.get("nwl_base_zar", 1000000)).to_eur(fx).value
        self.equity_lanred = ZAR(eq.get("lanred_pct", 1.0) * eq.get("lanred_base_zar", 1000000)).to_eur(fx).value
        self.equity_twx = ZAR(eq.get("timberworx_pct", 0.05) * eq.get("timberworx_base_zar", 1000000)).to_eur(fx).value

    def entity_loans(self) -> dict[str, dict]:
        """Return {entity_key: {senior_portion, mezz_portion, ...}} from structure."""
        return self.structure["uses"]["loans_to_subsidiaries"]

    def total_senior(self) -> float:
        return sum(l["senior_portion"] for l in self.entity_loans().values())

    def total_mezz(self) -> float:
        return sum(l["mezz_portion"] for l in self.entity_loans().values())


@dataclass
class ScenarioInputs:
    """UI-driven overrides (from Streamlit sliders or defaults)."""
    # NWL greenfield
    nwl_greenfield_growth_pct: float = 7.7
    nwl_greenfield_brine_pct: float = 10.0
    nwl_greenfield_sewage_rate_2025: float = 46.40
    nwl_greenfield_water_rate_2025: float = 62.05
    nwl_greenfield_reuse_ratio: float = 0.80
    # NWL sewerage revenue sharing
    nwl_srv_joburg_price: float = 46.40
    nwl_srv_growth_pct: float = 7.70
    nwl_srv_transport_r_km: float = 28.0
    nwl_srv_truck_capacity_m3: float = 10.0
    nwl_srv_nwl_distance_km: float = 10.0
    nwl_srv_gov_distance_km: float = 100.0
    nwl_srv_saving_to_market_pct: float = 40.0
    # NWL power
    nwl_power_kwh_per_m3: float = 0.4
    nwl_power_eskom_base: float = 2.81
    nwl_power_ic_discount: float = 10.0
    nwl_power_escalation: float = 10.0
    # LanRED
    lanred_scenario: str = "Brownfield+"
    lanred_bess_alloc_pct: float = 14.0
    # Sweep
    nwl_cash_sweep_pct: float = 100.0
    # Swap toggles
    nwl_swap_enabled: bool = True
    lanred_swap_enabled: bool = False
    nwl_swap_notional: float | None = None  # None = use default (pre-revenue hedge)
    # Hedge selections
    sclca_nwl_hedge: str = "Cross-Currency Swap"
    sclca_lanred_hedge: str = "No Hedging"
    # ECA toggles (per entity)
    nwl_eca_atradius: bool = True
    nwl_eca_exporter: bool = True
    lanred_eca_atradius: bool = False
    lanred_eca_exporter: bool = False
    timberworx_eca_atradius: bool = True
    timberworx_eca_exporter: bool = True

    @classmethod
    def from_session_state(cls, state: dict) -> "ScenarioInputs":
        """Build ScenarioInputs from Streamlit session_state dict."""
        def _float(key: str, default: float) -> float:
            try:
                return float(state.get(key, default))
            except Exception:
                return default

        def _str(key: str, default: str) -> str:
            return str(state.get(key, default))

        def _bool(key: str, default: bool) -> bool:
            return bool(state.get(key, default))

        lanred_scenario = _str("lanred_scenario", "Brownfield+")
        lanred_eca_default = lanred_scenario != "Brownfield+"

        return cls(
            nwl_greenfield_growth_pct=_float("nwl_greenfield_growth_pct", 7.7),
            nwl_greenfield_brine_pct=_float("nwl_greenfield_brine_pct", 10.0),
            nwl_greenfield_sewage_rate_2025=_float("nwl_greenfield_sewage_rate_2025", 46.40),
            nwl_greenfield_water_rate_2025=_float("nwl_greenfield_water_rate_2025", 62.05),
            nwl_greenfield_reuse_ratio=_float("nwl_greenfield_reuse_ratio", 0.80),
            nwl_srv_joburg_price=_float("nwl_srv_joburg_price", 46.40),
            nwl_srv_growth_pct=_float("nwl_srv_growth_pct", 7.70),
            nwl_srv_transport_r_km=_float("nwl_srv_transport_r_km", 28.0),
            nwl_srv_truck_capacity_m3=_float("nwl_srv_truck_capacity_m3", 10.0),
            nwl_srv_nwl_distance_km=_float("nwl_srv_nwl_distance_km", 10.0),
            nwl_srv_gov_distance_km=_float("nwl_srv_gov_distance_km", 100.0),
            nwl_srv_saving_to_market_pct=_float("nwl_srv_saving_to_market_pct", 40.0),
            nwl_power_kwh_per_m3=_float("nwl_power_kwh_per_m3", 0.4),
            nwl_power_eskom_base=_float("nwl_power_eskom_base", 2.81),
            nwl_power_ic_discount=_float("nwl_power_ic_discount", 10.0),
            nwl_power_escalation=_float("nwl_power_escalation", 10.0),
            lanred_scenario=lanred_scenario,
            lanred_bess_alloc_pct=_float("lanred_bess_alloc_pct", 14.0),
            nwl_cash_sweep_pct=_float("nwl_cash_sweep_pct", 100.0),
            nwl_swap_enabled=(_str("sclca_nwl_hedge", "Cross-Currency Swap") == "Cross-Currency Swap"),
            lanred_swap_enabled=(
                lanred_scenario != "Greenfield"
                and _str("sclca_lanred_hedge", "No Hedging") == "Cross-Currency Swap"
            ),
            nwl_swap_notional=state.get("nwl_swap_notional"),
            sclca_nwl_hedge=_str("sclca_nwl_hedge", "Cross-Currency Swap"),
            sclca_lanred_hedge=_str("sclca_lanred_hedge", "No Hedging"),
            nwl_eca_atradius=_bool("nwl_eca_atradius", True),
            nwl_eca_exporter=_bool("nwl_eca_exporter", True),
            lanred_eca_atradius=_bool("lanred_eca_atradius", lanred_eca_default),
            lanred_eca_exporter=_bool("lanred_eca_exporter", lanred_eca_default),
            timberworx_eca_atradius=_bool("timberworx_eca_atradius", True),
            timberworx_eca_exporter=_bool("timberworx_eca_exporter", True),
        )

    @classmethod
    def defaults(cls) -> "ScenarioInputs":
        """Return default ScenarioInputs (no UI overrides)."""
        return cls()
