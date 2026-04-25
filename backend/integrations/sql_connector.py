"""
DataSoul — SQL Database Integration
======================================
Import data from SQL databases (PostgreSQL, MySQL, SQLite).
Uses SQLAlchemy for broad compatibility.
"""

import pandas as pd
from . import IntegrationBase


class SQLIntegration(IntegrationBase):
    name = "sql"
    display_name = "SQL Database"
    icon = "🗄️"
    supports_import = True
    supports_export = False

    def validate_credentials(self, credentials: dict) -> dict:
        connection_string = credentials.get("connection_string", "")
        if not connection_string:
            return {"valid": False, "message": "Connection string required (e.g., sqlite:///data.db)"}

        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"valid": True, "message": "Database connection successful"}
        except ImportError:
            return {"valid": False, "message": "sqlalchemy not installed. Run: pip install sqlalchemy"}
        except Exception as e:
            return {"valid": False, "message": f"Connection failed: {e}"}

    def import_data(self, source: str, credentials: dict | None = None, **kwargs) -> pd.DataFrame:
        """
        Import data via SQL query.

        Args:
            source: SQL query string (SELECT ...)
            credentials: {"connection_string": "postgresql://user:pass@host/db"}
            table: Alternative — just provide a table name instead of full query
        """
        try:
            from sqlalchemy import create_engine
        except ImportError:
            raise ImportError("Install sqlalchemy: pip install sqlalchemy")

        conn_str = credentials.get("connection_string", "") if credentials else ""
        if not conn_str:
            raise ValueError("Database connection string required")

        engine = create_engine(conn_str)

        # If source looks like a table name (no spaces, no SELECT), wrap it
        table = kwargs.get("table")
        if table:
            query = f"SELECT * FROM {table}"
        elif " " not in source.strip():
            query = f"SELECT * FROM {source}"
        else:
            query = source

        # Apply limit if specified
        limit = kwargs.get("limit")
        if limit and "LIMIT" not in query.upper():
            query += f" LIMIT {limit}"

        df = pd.read_sql(query, engine)
        return df

    def list_tables(self, connection_string: str) -> list[str]:
        """List all tables in the connected database"""
        try:
            from sqlalchemy import create_engine, inspect
            engine = create_engine(connection_string)
            inspector = inspect(engine)
            return inspector.get_table_names()
        except Exception as e:
            return [f"Error: {e}"]

    def export_data(self, df: pd.DataFrame, destination: str,
                    credentials: dict | None = None,
                    metadata: dict | None = None, **kwargs) -> dict:
        raise NotImplementedError("SQL export not yet supported. Use CSV/XLSX export then import to your DB.")

    def get_status(self) -> dict:
        status = super().get_status()
        try:
            import sqlalchemy  # noqa: F401
            status["available"] = True
            status["auth_method"] = "connection_string"
        except ImportError:
            status["available"] = False
            status["install_hint"] = "pip install sqlalchemy"
        return status
