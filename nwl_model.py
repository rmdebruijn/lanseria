#!/usr/bin/env python3
"""
NWL Financial Model
-------------------
Python-based financial model for New Water Lanseria project.
Supports three-asset ECA segmentation and scenario analysis.

Usage:
    python nwl_model.py                    # Run summary
    python nwl_model.py --scenario solar   # Run solar carve-out scenario
    python nwl_model.py --eca              # Show ECA segmentation
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import argparse

# Config directory
CONFIG_DIR = Path(__file__).parent / "config"
OUTPUT_DIR = Path(__file__).parent / "output"


def load_config(name: str) -> dict:
    """Load a JSON config file."""
    path = CONFIG_DIR / f"{name}.json"
    with open(path, 'r') as f:
        return json.load(f)


@dataclass
class Asset:
    """Represents an asset segment."""
    name: str
    total: float
    mezz: float
    senior: float
    country_breakdown: Dict[str, float] = field(default_factory=dict)
    eca_eligible: float = 0
    carve_out: bool = False


@dataclass
class ECAConstraint:
    """ECA eligibility constraints."""
    min_dutch_content: float = 0.20
    max_sa_content: float = 0.33


class NWLModel:
    """Main financial model for NWL project."""

    def __init__(self):
        self.project = load_config("project")
        self.sources = load_config("sources")
        self.country_allocation = load_config("country_allocation")
        self.financing = load_config("financing")
        self.eca_segmentation = load_config("eca_segmentation")

        self.assets = self._build_assets()
        self.eca_constraints = ECAConstraint()

    def _build_assets(self) -> Dict[str, Asset]:
        """Build asset objects from config."""
        assets = {}
        by_asset = self.sources["by_asset"]

        for key, data in by_asset.items():
            assets[key] = Asset(
                name=key,
                total=data["total"],
                mezz=data["mezz"],
                senior=data["senior"],
                carve_out=data.get("carve_out", False)
            )
        return assets

    @property
    def total_project_cost(self) -> float:
        return self.sources["totals"]["total"]

    @property
    def total_senior(self) -> float:
        return self.sources["totals"]["senior_debt"]

    @property
    def total_mezz(self) -> float:
        return self.sources["totals"]["mezz"]

    @property
    def senior_limit(self) -> float:
        return self.sources["limits"]["senior_debt_max"]

    @property
    def senior_headroom(self) -> float:
        return self.senior_limit - self.total_senior

    def get_country_allocation(self, include_idc: bool = True) -> Dict[str, dict]:
        """Get country allocation with or without IDC."""
        return self.country_allocation["country_allocation"]["with_idc"]

    def check_eca_constraints(self) -> dict:
        """Check if ECA constraints are met."""
        allocation = self.get_country_allocation()
        total = self.country_allocation["country_allocation"]["total_project_cost_with_idc"]

        dutch_pct = allocation["Netherlands"]["allocation_pct"]
        sa_pct = allocation["South Africa"]["allocation_pct"]

        return {
            "dutch_content": {
                "amount": allocation["Netherlands"]["total"],
                "percentage": dutch_pct,
                "min_required": self.eca_constraints.min_dutch_content,
                "met": dutch_pct >= self.eca_constraints.min_dutch_content,
                "status": allocation["Netherlands"]["status"]
            },
            "sa_content": {
                "amount": allocation["South Africa"]["total"],
                "percentage": sa_pct,
                "max_allowed": self.eca_constraints.max_sa_content,
                "met": sa_pct <= self.eca_constraints.max_sa_content,
                "status": allocation["South Africa"]["status"]
            }
        }

    def get_exposure_waterfall(self) -> dict:
        """Calculate sponsor exposure waterfall."""
        exp = self.financing["exposure_calculation"]
        return {
            "month_24_principal": exp["month_24_principal"],
            "less_solar_carve_out": exp["less_solar_carve_out"],
            "net_lending_envelope": exp["net_lending_envelope"],
            "less_grant_acceleration": exp["less_prepayments"],
            "final_sponsor_exposure": exp["final_sponsor_exposure"]
        }

    def get_segment_exposure(self) -> Dict[str, dict]:
        """Calculate exposure by asset segment for three-segment ECA structure."""
        total_exposure = self.financing["exposure_calculation"]["final_sponsor_exposure"]

        # Calculate proportional exposure per asset (excluding solar carve-out)
        non_solar_total = sum(
            a.total for k, a in self.assets.items()
            if not a.carve_out
        )

        segments = {}
        for key, asset in self.assets.items():
            if asset.carve_out:
                segments[key] = {
                    "name": asset.name,
                    "budget": asset.total,
                    "exposure": 0,
                    "carve_out": True,
                    "note": "Independently underwritten - zero sponsor exposure"
                }
            else:
                proportion = asset.total / non_solar_total
                exposure = total_exposure * proportion
                segments[key] = {
                    "name": asset.name,
                    "budget": asset.total,
                    "exposure": round(exposure, 2),
                    "proportion": round(proportion, 4),
                    "carve_out": False
                }

        return segments

    def summary(self) -> str:
        """Generate model summary."""
        lines = [
            "=" * 60,
            "NWL FINANCIAL MODEL SUMMARY",
            "=" * 60,
            "",
            "PROJECT COSTS",
            "-" * 40,
        ]

        for key, asset in self.assets.items():
            lines.append(f"  {key.upper():12} €{asset.total:,.0f}")
        lines.append(f"  {'TOTAL':12} €{self.total_project_cost:,.0f}")

        lines.extend([
            "",
            "SOURCES",
            "-" * 40,
            f"  Senior Debt:  €{self.total_senior:,.0f} (85%)",
            f"  Mezzanine:    €{self.total_mezz:,.0f} (15%)",
            f"  Senior Limit: €{self.senior_limit:,.0f}",
            f"  Headroom:     €{self.senior_headroom:,.0f}",
        ])

        lines.extend([
            "",
            "ECA CONSTRAINTS",
            "-" * 40,
        ])
        constraints = self.check_eca_constraints()
        dutch = constraints["dutch_content"]
        sa = constraints["sa_content"]
        lines.append(f"  Dutch: {dutch['percentage']*100:.0f}% (min {dutch['min_required']*100:.0f}%) - {dutch['status']}")
        lines.append(f"  SA:    {sa['percentage']*100:.0f}% (max {sa['max_allowed']*100:.0f}%) - {sa['status']}")

        lines.extend([
            "",
            "SPONSOR EXPOSURE",
            "-" * 40,
        ])
        waterfall = self.get_exposure_waterfall()
        lines.append(f"  M24 Principal:      €{waterfall['month_24_principal']:,.0f}")
        lines.append(f"  Less Solar:         €{waterfall['less_solar_carve_out']:,.0f}")
        lines.append(f"  Net Lending:        €{waterfall['net_lending_envelope']:,.0f}")
        lines.append(f"  Less Grant Accel:   €{waterfall['less_grant_acceleration']:,.0f}")
        lines.append(f"  FINAL EXPOSURE:     €{waterfall['final_sponsor_exposure']:,.0f}")

        lines.extend([
            "",
            "SEGMENT EXPOSURE (Three-Asset ECA)",
            "-" * 40,
        ])
        segments = self.get_segment_exposure()
        for key, seg in segments.items():
            if seg["carve_out"]:
                lines.append(f"  {key.upper():12} €{seg['exposure']:,.0f} (carve-out)")
            else:
                lines.append(f"  {key.upper():12} €{seg['exposure']:,.0f} ({seg['proportion']*100:.1f}%)")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def to_json(self) -> dict:
        """Export model state to JSON."""
        return {
            "project": self.project,
            "totals": {
                "project_cost": self.total_project_cost,
                "senior_debt": self.total_senior,
                "mezzanine": self.total_mezz
            },
            "assets": {k: {"name": a.name, "total": a.total, "carve_out": a.carve_out}
                      for k, a in self.assets.items()},
            "eca_constraints": self.check_eca_constraints(),
            "exposure_waterfall": self.get_exposure_waterfall(),
            "segment_exposure": self.get_segment_exposure()
        }

    def save_output(self, filename: str = "model_output.json"):
        """Save model output to JSON file."""
        OUTPUT_DIR.mkdir(exist_ok=True)
        path = OUTPUT_DIR / filename
        with open(path, 'w') as f:
            json.dump(self.to_json(), f, indent=2)
        print(f"Output saved to: {path}")


def main():
    parser = argparse.ArgumentParser(description="NWL Financial Model")
    parser.add_argument("--eca", action="store_true", help="Show ECA segmentation details")
    parser.add_argument("--export", action="store_true", help="Export to JSON")
    args = parser.parse_args()

    model = NWLModel()

    print(model.summary())

    if args.export:
        model.save_output()


if __name__ == "__main__":
    main()
