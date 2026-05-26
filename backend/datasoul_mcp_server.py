import sys
import pandas as pd
import json
import os
import asyncio
from mcp.server.fastmcp import FastMCP

# Import DataSoul engines
from profiler import DataProfiler
from csv_corrector import CSVCorrector
from threat_detector import ThreatDetector
from prediction_engine import PredictionEngine

# Initialize FastMCP Server
mcp = FastMCP("DataSoul Data Cleaner")

@mcp.tool()
def profile_dataset(csv_path: str) -> str:
    """
    Profile a dataset to analyze column distributions, missing values, duplicates, and overall quality score.
    """
    if not os.path.exists(csv_path):
        return json.dumps({"error": f"File not found: {csv_path}"})
    
    try:
        df = pd.read_csv(csv_path)
        profiler = DataProfiler(df)
        profile_data = profiler.generate_full_profile()
        return json.dumps(profile_data, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def correct_csv(csv_path: str, output_path: str) -> str:
    """
    Automatically clean and correct a CSV dataset (fix encoding, type issues, missing values, duplicates)
    and save the cleaned data to output_path.
    """
    if not os.path.exists(csv_path):
        return json.dumps({"error": f"File not found: {csv_path}"})
    
    try:
        df = pd.read_csv(csv_path)
        corrector = CSVCorrector()
        result = corrector.auto_correct(df)
        
        cleaned_df = result.get("df")
        if cleaned_df is not None:
            cleaned_df.to_csv(output_path, index=False)
            return json.dumps({
                "status": "success",
                "original_shape": result.get("original_shape"),
                "corrected_shape": result.get("corrected_shape"),
                "corrections_applied": result.get("corrections_applied"),
                "audit": result.get("audit"),
                "output_path": output_path
            }, indent=2)
        else:
            return json.dumps({"error": "Correction failed, no dataframe returned."})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def detect_threats(csv_path: str) -> str:
    """
    Detect data threats like PII leakage, severe data drift, high cardinality IDs, or mixed types.
    """
    if not os.path.exists(csv_path):
        return json.dumps({"error": f"File not found: {csv_path}"})
        
    try:
        df = pd.read_csv(csv_path)
        detector = ThreatDetector(df)
        threats = detector.detect_threats()
        return json.dumps(threats, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def build_predictive_model(csv_path: str, target_column: str, problem_type: str = "auto") -> str:
    """
    Build a predictive model using Scikit-learn (AutoML) on the specified dataset.
    problem_type can be 'classification', 'regression', or 'auto'.
    """
    if not os.path.exists(csv_path):
        return json.dumps({"error": f"File not found: {csv_path}"})
        
    try:
        df = pd.read_csv(csv_path)
        engine = PredictionEngine(df, target_col=target_column)
        results = engine.build_model(problem_type=problem_type)
        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    # Start the FastMCP stdio server
    mcp.run()
