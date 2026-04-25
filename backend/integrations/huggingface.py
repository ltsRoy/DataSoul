"""
DataSoul — Hugging Face Hub Integration
==========================================
Push cleaned datasets to Hugging Face Hub.
Auto-generates dataset card with DataSoul profiling metadata.
"""

import pandas as pd
from . import IntegrationBase


class HuggingFaceIntegration(IntegrationBase):
    name = "huggingface"
    display_name = "Hugging Face"
    icon = "🤗"
    supports_import = False
    supports_export = True

    def validate_credentials(self, credentials: dict) -> dict:
        try:
            from huggingface_hub import HfApi
            token = credentials.get("token", "")
            if not token:
                return {"valid": False, "message": "No token provided."}
            api = HfApi(token=token)
            user_info = api.whoami()
            return {"valid": True, "message": f"Authenticated as {user_info.get('name', '')}", "username": user_info.get("name", "")}
        except ImportError:
            return {"valid": False, "message": "huggingface-hub not installed."}
        except Exception as e:
            return {"valid": False, "message": f"Auth failed: {e}"}

    def import_data(self, source: str, credentials: dict | None = None, **kwargs) -> pd.DataFrame:
        from datasets import load_dataset
        return load_dataset(source, split=kwargs.get("split", "train")).to_pandas()

    def export_data(self, df: pd.DataFrame, destination: str,
                    credentials: dict | None = None,
                    metadata: dict | None = None, **kwargs) -> dict:
        from datasets import Dataset
        from huggingface_hub import HfApi

        token = credentials.get("token", "") if credentials else ""
        if not token:
            raise ValueError("HF token required.")

        api = HfApi(token=token)
        username = api.whoami().get("name", "")
        repo_id = f"{username}/{destination}" if "/" not in destination else destination
        private = kwargs.get("private", False)

        Dataset.from_pandas(df).push_to_hub(repo_id=repo_id, token=token, private=private)

        profile = metadata or {}
        hs = profile.get("profile", {}).get("quality_score", {}).get("overall", "N/A")
        card = f"---\nlicense: mit\ntags:\n- datasoul\n---\n# {destination}\n\nProfiled by DataSoul. Health: {hs}/100. {len(df):,} rows × {len(df.columns)} cols.\n"
        api.upload_file(path_or_fileobj=card.encode(), path_in_repo="README.md", repo_id=repo_id, repo_type="dataset", token=token)

        return {"status": "success", "repo_id": repo_id, "url": f"https://huggingface.co/datasets/{repo_id}", "rows_pushed": len(df)}

    def get_status(self) -> dict:
        status = super().get_status()
        try:
            import huggingface_hub  # noqa: F401
            status["available"] = True
        except ImportError:
            status["available"] = False
            status["install_hint"] = "pip install huggingface-hub datasets"
        return status
