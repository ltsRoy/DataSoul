"""
DataSoul — Kaggle Integration
================================
Import datasets from and export to Kaggle.
Uses the Kaggle API with kaggle.json credentials.
"""

import pandas as pd
import os
import tempfile
import json
from pathlib import Path
from . import IntegrationBase


class KaggleIntegration(IntegrationBase):
    name = "kaggle"
    display_name = "Kaggle"
    icon = "🏆"
    supports_import = True
    supports_export = True

    def validate_credentials(self, credentials: dict) -> dict:
        username = credentials.get("username", "")
        key = credentials.get("key", "")
        if not username or not key:
            return {"valid": False, "message": "Kaggle username and API key required. Get from kaggle.com/settings"}

        # Set env vars for kaggle API
        os.environ["KAGGLE_USERNAME"] = username
        os.environ["KAGGLE_KEY"] = key

        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
            api = KaggleApi()
            api.authenticate()
            return {"valid": True, "message": f"Authenticated as {username}"}
        except ImportError:
            return {"valid": False, "message": "kaggle not installed. Run: pip install kaggle"}
        except Exception as e:
            return {"valid": False, "message": f"Auth failed: {e}"}

    def import_data(self, source: str, credentials: dict | None = None, **kwargs) -> pd.DataFrame:
        """
        Import a Kaggle dataset.

        Args:
            source: Dataset slug (e.g., "username/dataset-name")
            credentials: {"username": "xxx", "key": "xxx"}
            filename: Specific file within the dataset to load
        """
        if credentials:
            os.environ["KAGGLE_USERNAME"] = credentials.get("username", "")
            os.environ["KAGGLE_KEY"] = credentials.get("key", "")

        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
        except ImportError:
            raise ImportError("Install kaggle: pip install kaggle")

        api = KaggleApi()
        api.authenticate()

        # Download to temp dir
        with tempfile.TemporaryDirectory() as tmpdir:
            api.dataset_download_files(source, path=tmpdir, unzip=True)

            # Find CSV/XLSX files
            files = list(Path(tmpdir).glob("**/*.csv")) + list(Path(tmpdir).glob("**/*.xlsx"))
            if not files:
                raise ValueError(f"No CSV/XLSX files found in dataset '{source}'")

            # Use specified filename or first file
            target_name = kwargs.get("filename")
            if target_name:
                target = next((f for f in files if f.name == target_name), None)
                if not target:
                    raise ValueError(f"File '{target_name}' not found. Available: {[f.name for f in files]}")
            else:
                target = files[0]

            if target.suffix == ".csv":
                df = pd.read_csv(target, low_memory=False)
            else:
                df = pd.read_excel(target)

        return df

    def export_data(self, df: pd.DataFrame, destination: str,
                    credentials: dict | None = None,
                    metadata: dict | None = None, **kwargs) -> dict:
        """Export DataFrame as a new Kaggle dataset."""
        if credentials:
            os.environ["KAGGLE_USERNAME"] = credentials.get("username", "")
            os.environ["KAGGLE_KEY"] = credentials.get("key", "")

        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
        except ImportError:
            raise ImportError("Install kaggle: pip install kaggle")

        api = KaggleApi()
        api.authenticate()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Save CSV
            csv_path = Path(tmpdir) / f"{destination}.csv"
            df.to_csv(csv_path, index=False)

            # Create dataset metadata
            meta = {
                "title": destination,
                "id": f"{os.environ.get('KAGGLE_USERNAME', 'user')}/{destination}",
                "licenses": [{"name": "CC0-1.0"}],
            }
            meta_path = Path(tmpdir) / "dataset-metadata.json"
            with open(meta_path, "w") as f:
                json.dump(meta, f)

            api.dataset_create_new(folder=tmpdir, dir_mode="zip")

        return {"status": "success", "dataset": destination, "rows_exported": len(df)}

    def get_status(self) -> dict:
        status = super().get_status()
        try:
            import kaggle  # noqa: F401
            status["available"] = True
            status["auth_method"] = "api_key"
        except ImportError:
            status["available"] = False
            status["install_hint"] = "pip install kaggle"
        return status
