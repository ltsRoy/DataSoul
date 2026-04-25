"""
DataSoul Sector Detector
==========================
Automatically detects the business sector from column names
using weighted pattern matching against sector intelligence.
"""

import json
from pathlib import Path
import pandas as pd


# Sector definitions with weighted column patterns
SECTOR_DEFINITIONS = {
    "retail": {
        "name": "Retail & E-Commerce",
        "columns": ["sku", "product", "price", "quantity", "order", "cart", "category",
                     "discount", "revenue", "inventory", "stock", "item", "shipping",
                     "customer", "sale", "payment", "coupon", "return"],
        "weight": 1.0,
    },
    "healthcare": {
        "name": "Healthcare",
        "columns": ["patient", "diagnosis", "icd", "medication", "prescription",
                     "admit", "discharge", "readmit", "blood_pressure", "treatment",
                     "insurance_claim", "hospital", "symptom", "dose", "vitals"],
        "weight": 1.2,  # Higher weight since healthcare is more specific
    },
    "finance": {
        "name": "Finance & Banking",
        "columns": ["transaction", "balance", "account", "loan", "interest",
                     "credit", "debit", "portfolio", "investment", "yield", "risk",
                     "apy", "apr", "maturity", "collateral", "default"],
        "weight": 1.1,
    },
    "hr": {
        "name": "Human Resources",
        "columns": ["employee", "salary", "department", "hire_date", "performance",
                     "attrition", "tenure", "job_title", "leave", "overtime",
                     "manager", "appraisal", "promotion", "headcount"],
        "weight": 1.0,
    },
    "manufacturing": {
        "name": "Manufacturing",
        "columns": ["machine", "sensor", "production", "defect", "batch",
                     "yield_rate", "maintenance", "downtime", "quality_score",
                     "throughput", "cycle_time", "oee", "scrap"],
        "weight": 1.1,
    },
    "education": {
        "name": "Education",
        "columns": ["student", "grade", "enrollment", "course", "gpa",
                     "attendance", "semester", "faculty", "curriculum", "score",
                     "exam", "assignment", "dropout", "graduation"],
        "weight": 1.0,
    },
    "logistics": {
        "name": "Logistics & Supply Chain",
        "columns": ["shipment", "tracking", "warehouse", "delivery", "route",
                     "carrier", "freight", "lead_time", "supply", "demand",
                     "procurement", "vendor", "fulfillment", "dock"],
        "weight": 1.0,
    },
    "real_estate": {
        "name": "Real Estate",
        "columns": ["property", "listing", "listing_price", "sale_price", "sqft",
                     "square_feet", "bedrooms", "bathrooms", "lot_size", "year_built",
                     "mls", "agent", "hoa", "zoning", "appraisal"],
        "weight": 1.0,
    },
}


class SectorDetector:
    def __init__(self, custom_sectors: dict | None = None):
        self.sectors = {**SECTOR_DEFINITIONS}
        if custom_sectors:
            self.sectors.update(custom_sectors)

    def detect(self, df: pd.DataFrame) -> dict:
        """Detect the most likely business sector from column names"""
        col_names = [col.lower().replace(" ", "_") for col in df.columns]
        col_str = " ".join(col_names)

        scores: dict[str, float] = {}

        for sector_id, sector_def in self.sectors.items():
            score = 0.0
            matched_cols = []

            for pattern in sector_def["columns"]:
                for col_name in col_names:
                    if pattern in col_name:
                        score += sector_def["weight"]
                        matched_cols.append(col_name)
                        break  # One match per pattern

            # Normalize by number of patterns
            if len(sector_def["columns"]) > 0:
                scores[sector_id] = score / len(sector_def["columns"]) * 100

        if not scores or max(scores.values()) < 5:
            return {
                "sector_id": "general",
                "sector_name": "General Business",
                "confidence": 50,
                "matched_columns": [],
                "reasoning": "No sector-specific column patterns detected. Using general analysis mode.",
            }

        best_sector = max(scores, key=scores.get)  # type: ignore
        confidence = min(round(scores[best_sector], 1), 99)

        # Get matched columns for explanation
        matched = []
        for pattern in self.sectors[best_sector]["columns"]:
            for col_name in col_names:
                if pattern in col_name:
                    matched.append(col_name)
                    break

        return {
            "sector_id": best_sector,
            "sector_name": self.sectors[best_sector]["name"],
            "confidence": confidence,
            "matched_columns": matched,
            "scores": {k: round(v, 1) for k, v in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]},
            "reasoning": f"Detected {self.sectors[best_sector]['name']} based on {len(matched)} matching column patterns ({', '.join(matched[:5])}).",
        }
