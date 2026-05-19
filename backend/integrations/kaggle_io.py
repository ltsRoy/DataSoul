"""
DataSoul — Kaggle Integration
================================
Import datasets from and export to Kaggle.
Compatible with both kaggle v1 (api_key in kaggle.json) and v2 (OAuth/env vars).
"""

import pandas as pd
import os
import tempfile
import json
from pathlib import Path
from . import IntegrationBase


def _get_kaggle_api(credentials: dict | None = None):
    """Build and authenticate a KaggleApi instance.

    Supports kaggle v1 (KaggleApi) and gracefully falls back to env-var
    based auth (KAGGLE_USERNAME + KAGGLE_KEY) which is the safest approach
    for headless server usage with both v1 and v2 SDKs.
    """
    if credentials:
        username = credentials.get("username", "")
        key = credentials.get("key", "")
        if username:
            os.environ["KAGGLE_USERNAME"] = username
        if key:
            os.environ["KAGGLE_KEY"] = key

    # Try v1 API first (most stable for server use)
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        return api, "v1"
    except ImportError:
        raise ImportError("kaggle package not installed. Run: pip install kaggle")
    except SystemExit as e:
        # Kaggle 2.x raises SystemExit when credentials aren't found
        raise PermissionError(
            f"Kaggle authentication failed: {e}. "
            "Provide username and API key from kaggle.com/settings/account"
        )
    except Exception as e:
        raise PermissionError(f"Kaggle authentication failed: {e}")


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
            return {
                "valid": False,
                "message": "Kaggle username and API key required. "
                           "Get your key at kaggle.com/settings → API → Create New Token",
            }

        try:
            api, _ = _get_kaggle_api(credentials)
            # Test authentication by calling a protected endpoint
            try:
                api.competitions_list(page=1)
            except Exception as e:
                return {"valid": False, "message": f"Kaggle authentication failed: Invalid credentials."}
            return {"valid": True, "message": f"Authenticated as {username}"}
        except ImportError as e:
            return {"valid": False, "message": str(e)}
        except PermissionError as e:
            return {"valid": False, "message": str(e)}
        except Exception as e:
            return {"valid": False, "message": f"Auth failed: {e}"}

    def import_data(self, source: str, credentials: dict | None = None, **kwargs) -> pd.DataFrame:
        """Import a Kaggle dataset.

        Args:
            source:      Dataset slug (e.g. "username/dataset-name") or full Kaggle dataset URL
            credentials: {"username": "xxx", "key": "xxx"}
            filename:    Specific CSV/XLSX file within the dataset (optional)
        """
        if not source:
            raise ValueError("Invalid dataset slug or URL.")
            
        import urllib.parse
        if "kaggle.com" in source:
            path = urllib.parse.urlparse(source).path
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 3 and parts[0] == "datasets":
                source = f"{parts[1]}/{parts[2]}"
            elif len(parts) >= 2:
                source = f"{parts[-2]}/{parts[-1]}"

        if "/" not in source:
            raise ValueError(
                "Invalid dataset slug. Use format 'owner/dataset-name' "
                "(found on any Kaggle dataset page URL)."
            )

        api, _ver = _get_kaggle_api(credentials)

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                api.dataset_download_files(source, path=tmpdir, unzip=True, quiet=True)
            except Exception as e:
                raise ValueError(
                    f"Failed to download '{source}': {e}. "
                    "Check the dataset slug and that your account has access to it."
                )

            # Find CSV/XLSX files
            files = (
                list(Path(tmpdir).glob("**/*.csv"))
                + list(Path(tmpdir).glob("**/*.xlsx"))
            )
            if not files:
                raise ValueError(
                    f"No CSV/XLSX files found in dataset '{source}'. "
                    f"Files present: {[f.name for f in Path(tmpdir).rglob('*') if f.is_file()]}"
                )

            # Use specified filename or the largest CSV (most likely the main dataset)
            target_name = kwargs.get("filename")
            if target_name:
                target = next((f for f in files if f.name == target_name), None)
                if not target:
                    raise ValueError(
                        f"File '{target_name}' not found in dataset. "
                        f"Available: {[f.name for f in files]}"
                    )
            else:
                # Prefer CSVs, pick the largest one as the primary dataset file
                csvs = [f for f in files if f.suffix == ".csv"]
                target = max(csvs, key=lambda f: f.stat().st_size) if csvs else files[0]

            try:
                if target.suffix == ".csv":
                    df = pd.read_csv(target, low_memory=False)
                else:
                    df = pd.read_excel(target)
            except Exception as e:
                raise ValueError(f"Failed to parse '{target.name}': {e}")

        return df

    def export_data(
        self,
        df: pd.DataFrame,
        destination: str,
        credentials: dict | None = None,
        metadata: dict | None = None,
        **kwargs,
    ) -> dict:
        """Export a cleaned DataFrame as a new Kaggle dataset."""
        api, _ver = _get_kaggle_api(credentials)
        username = os.environ.get("KAGGLE_USERNAME", "user")

        # Sanitise dataset name (Kaggle slugs: lowercase, hyphens only)
        import re
        slug = re.sub(r"[^a-z0-9-]", "-", destination.lower()).strip("-")

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / f"{slug}.csv"
            df.to_csv(csv_path, index=False)

            meta = {
                "title": destination,
                "id": f"{username}/{slug}",
                "licenses": [{"name": "CC0-1.0"}],
            }
            meta_path = Path(tmpdir) / "dataset-metadata.json"
            with open(meta_path, "w") as f:
                json.dump(meta, f)

            try:
                api.dataset_create_new(folder=tmpdir, dir_mode="zip", quiet=True)
            except Exception as e:
                raise ValueError(f"Kaggle upload failed: {e}")

        return {
            "status": "success",
            "dataset": f"{username}/{slug}",
            "rows_exported": len(df),
            "url": f"https://www.kaggle.com/datasets/{username}/{slug}",
        }

    def get_status(self) -> dict:
        status = super().get_status()
        try:
            import importlib.metadata
            version = importlib.metadata.version("kaggle")
            status["available"] = True
            status["auth_method"] = "api_key (KAGGLE_USERNAME + KAGGLE_KEY env vars)"
            status["version"] = version
        except importlib.metadata.PackageNotFoundError:
            status["available"] = False
            status["install_hint"] = "pip install kaggle"
        return status
