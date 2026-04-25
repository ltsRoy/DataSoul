"""
DataSoul — data.gov.in Integration
=====================================
Import datasets from India's Open Government Data portal.
API docs: https://data.gov.in/ogpl/api-policy
"""

import pandas as pd
import requests
import io
from . import IntegrationBase


class DataGovInIntegration(IntegrationBase):
    name = "data_gov_in"
    display_name = "data.gov.in"
    icon = "🇮🇳"
    supports_import = True
    supports_export = False

    API_BASE = "https://api.data.gov.in/resource"

    def validate_credentials(self, credentials: dict) -> dict:
        api_key = credentials.get("api_key", "")
        if not api_key:
            return {"valid": False, "message": "API key required. Register at https://data.gov.in/user/register"}
        # Test with a lightweight call
        try:
            resp = requests.get(
                f"{self.API_BASE}/6176ee09-3d56-4a3b-8115-21841576b2f6",
                params={"api-key": api_key, "format": "json", "limit": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                return {"valid": True, "message": "API key validated successfully"}
            return {"valid": False, "message": f"API returned status {resp.status_code}"}
        except Exception as e:
            return {"valid": False, "message": f"Validation failed: {e}"}

    def import_data(self, source: str, credentials: dict | None = None, **kwargs) -> pd.DataFrame:
        """
        Import from data.gov.in.

        Args:
            source: Resource ID from data.gov.in (the UUID in the dataset URL)
            credentials: {"api_key": "your_key"}
            limit: Max records to fetch (default 1000)
            offset: Pagination offset
        """
        api_key = credentials.get("api_key", "") if credentials else ""
        if not api_key:
            raise ValueError("data.gov.in API key required.")

        limit = kwargs.get("limit", 1000)
        offset = kwargs.get("offset", 0)
        fmt = kwargs.get("format", "json")

        params = {
            "api-key": api_key,
            "format": fmt,
            "limit": limit,
            "offset": offset,
        }

        # Apply filters if provided
        filters = kwargs.get("filters", {})
        for key, value in filters.items():
            params[f"filters[{key}]"] = value

        resp = requests.get(f"{self.API_BASE}/{source}", params=params, timeout=30)
        resp.raise_for_status()

        if fmt == "json":
            data = resp.json()
            records = data.get("records", [])
            if not records:
                raise ValueError(f"No records found for resource {source}")
            df = pd.DataFrame(records)
        elif fmt == "csv":
            df = pd.read_csv(io.StringIO(resp.text))
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        # Clean up common data.gov.in column issues
        df.columns = [c.strip().replace("__", "_").lower() for c in df.columns]

        return df

    def search_datasets(self, query: str, api_key: str, limit: int = 20) -> list[dict]:
        """Search data.gov.in catalog for datasets"""
        try:
            resp = requests.get(
                "https://api.data.gov.in/lists",
                params={"api-key": api_key, "format": "json", "search": query, "limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("records", []):
                results.append({
                    "resource_id": item.get("resource_id", ""),
                    "title": item.get("title", ""),
                    "org": item.get("org", ""),
                    "sector": item.get("sector", ""),
                    "source": item.get("source", ""),
                    "created": item.get("created", ""),
                })
            return results
        except Exception:
            return []

    def export_data(self, df: pd.DataFrame, destination: str,
                    credentials: dict | None = None,
                    metadata: dict | None = None, **kwargs) -> dict:
        raise NotImplementedError("data.gov.in is import-only")

    def get_status(self) -> dict:
        status = super().get_status()
        status["available"] = True  # Only needs requests which is already installed
        status["auth_method"] = "api_key"
        status["register_url"] = "https://data.gov.in/user/register"
        return status
