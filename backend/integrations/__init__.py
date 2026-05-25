"""
DataSoul Integrations Package
===============================
Platform connectors for importing and exporting datasets.
Supports: Google Sheets, Google Colab, Hugging Face, data.gov.in, Kaggle, SQL.
"""

from typing import Optional
import pandas as pd


class IntegrationBase:
    """Base interface for all DataSoul integrations"""

    name: str = "base"
    display_name: str = "Base Integration"
    icon: str = "🔗"
    supports_import: bool = False
    supports_export: bool = False

    def validate_credentials(self, credentials: dict) -> dict:
        """Validate provided credentials. Returns { valid: bool, message: str }"""
        raise NotImplementedError

    def import_data(self, source: str, credentials: dict | None = None, **kwargs) -> pd.DataFrame:
        """Import data from external source into a DataFrame"""
        raise NotImplementedError

    def export_data(self, df: pd.DataFrame, destination: str,
                    credentials: dict | None = None,
                    metadata: dict | None = None, **kwargs) -> dict:
        """Export DataFrame to external destination. Returns result dict."""
        raise NotImplementedError

    def get_status(self) -> dict:
        """Get integration status and availability"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "icon": self.icon,
            "supports_import": self.supports_import,
            "supports_export": self.supports_export,
            "available": True,
        }


# ─── Integration Registry ───

_REGISTRY: dict[str, IntegrationBase] = {}


def register(integration: IntegrationBase):
    _REGISTRY[integration.name] = integration


def get_integration(name: str) -> IntegrationBase | None:
    return _REGISTRY.get(name)


def list_integrations() -> list[dict]:
    return [i.get_status() for i in _REGISTRY.values()]


# ─── Auto-register available integrations ───

def _auto_register():
    """Import and register all available integrations"""
    try:
        from .google_sheets import GoogleSheetsIntegration
        register(GoogleSheetsIntegration())
    except Exception:
        pass

    try:
        from .google_colab import GoogleColabIntegration
        register(GoogleColabIntegration())
    except Exception:
        pass

    try:
        from .huggingface import HuggingFaceIntegration
        register(HuggingFaceIntegration())
    except Exception:
        pass

    try:
        from .data_gov_in import DataGovInIntegration
        register(DataGovInIntegration())
    except Exception:
        pass

    try:
        from .kaggle_io import KaggleIntegration
        register(KaggleIntegration())
    except Exception:
        pass

    try:
        from .sql_connector import SQLIntegration
        register(SQLIntegration())
    except Exception:
        pass

    try:
        from .mcp_connector import MCPIntegration
        register(MCPIntegration())
    except Exception:
        pass


_auto_register()
