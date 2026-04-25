"""
DataSoul — Google Sheets Integration
========================================
Import from and export to Google Sheets.
Uses gspread + OAuth2 or Service Account auth.
"""

import pandas as pd
import io
from typing import Optional
from . import IntegrationBase


class GoogleSheetsIntegration(IntegrationBase):
    name = "google_sheets"
    display_name = "Google Sheets"
    icon = "📊"
    supports_import = True
    supports_export = True

    def validate_credentials(self, credentials: dict) -> dict:
        """Validate Google credentials (service account JSON or OAuth token)"""
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            cred_type = credentials.get("type", "service_account")

            if cred_type == "service_account":
                scopes = [
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ]
                creds = Credentials.from_service_account_info(
                    credentials, scopes=scopes
                )
                client = gspread.authorize(creds)
                # Test by listing spreadsheets
                client.list_spreadsheet_files()
                return {"valid": True, "message": "Service account authorized successfully"}
            else:
                return {"valid": False, "message": f"Unsupported credential type: {cred_type}. Use 'service_account'."}

        except ImportError:
            return {"valid": False, "message": "gspread or google-auth not installed. Run: pip install gspread google-auth"}
        except Exception as e:
            return {"valid": False, "message": f"Authentication failed: {str(e)}"}

    def import_data(self, source: str, credentials: dict | None = None, **kwargs) -> pd.DataFrame:
        """
        Import data from a Google Sheet.

        Args:
            source: Google Sheet URL or Sheet ID
            credentials: Service account JSON dict
            sheet_name: Optional specific sheet/tab name (default: first sheet)
        """
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            raise ImportError("Install gspread: pip install gspread google-auth")

        if not credentials:
            raise ValueError("Google credentials required. Provide a service account JSON.")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(credentials, scopes=scopes)
        client = gspread.authorize(creds)

        # Open by URL or by key
        if source.startswith("http"):
            spreadsheet = client.open_by_url(source)
        else:
            spreadsheet = client.open_by_key(source)

        # Get specific sheet or first one
        sheet_name = kwargs.get("sheet_name")
        if sheet_name:
            worksheet = spreadsheet.worksheet(sheet_name)
        else:
            worksheet = spreadsheet.sheet1

        # Read all records
        records = worksheet.get_all_records()
        if not records:
            # Fallback to get_all_values for sheets without proper headers
            values = worksheet.get_all_values()
            if len(values) > 1:
                df = pd.DataFrame(values[1:], columns=values[0])
            else:
                df = pd.DataFrame()
        else:
            df = pd.DataFrame(records)

        return df

    def export_data(self, df: pd.DataFrame, destination: str,
                    credentials: dict | None = None,
                    metadata: dict | None = None, **kwargs) -> dict:
        """
        Export DataFrame to a Google Sheet.

        Args:
            df: DataFrame to export
            destination: Sheet name to create/update
            credentials: Service account JSON dict
            metadata: Optional metadata dict (health_score, filename, etc.)
        """
        try:
            import gspread
            from gspread_dataframe import set_with_dataframe
            from google.oauth2.service_account import Credentials
        except ImportError:
            raise ImportError("Install gspread-dataframe: pip install gspread gspread-dataframe google-auth")

        if not credentials:
            raise ValueError("Google credentials required.")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(credentials, scopes=scopes)
        client = gspread.authorize(creds)

        # Create new spreadsheet
        spreadsheet = client.create(destination)

        # Main data sheet
        worksheet = spreadsheet.sheet1
        worksheet.update_title("Data")
        set_with_dataframe(worksheet, df)

        # Add metadata sheet if provided
        if metadata:
            meta_ws = spreadsheet.add_worksheet("DataSoul Report", rows=20, cols=2)
            meta_rows = [["Metric", "Value"]]
            for key, value in metadata.items():
                meta_rows.append([str(key), str(value)])
            meta_ws.update(meta_rows)

        # Share publicly (read-only) for easy access
        spreadsheet.share("", perm_type="anyone", role="reader")

        return {
            "status": "success",
            "sheet_url": spreadsheet.url,
            "sheet_id": spreadsheet.id,
            "rows_exported": len(df),
            "cols_exported": len(df.columns),
        }

    def get_status(self) -> dict:
        status = super().get_status()
        try:
            import gspread  # noqa: F401
            status["available"] = True
            status["auth_method"] = "service_account"
        except ImportError:
            status["available"] = False
            status["install_hint"] = "pip install gspread gspread-dataframe google-auth"
        return status
