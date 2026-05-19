import os
import sys
import io
import pandas as pd
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from profiler import DataProfiler
from csv_corrector import CSVCorrector
from pipeline_engine import IterativePipeline
from llm_engine import get_llm

def test_dirty_csv(file_path):
    print(f"\n{'='*60}")
    print(f"Testing Dirty CSV: {file_path}")
    print(f"{'='*60}")
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    # Load dataset
    try:
        df = pd.read_csv(file_path)
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding='latin1')
    print(f"Original Shape: {df.shape}")
    print(f"Original Columns: {list(df.columns)}")
    
    # Check Ollama Status
    llm = get_llm()
    print(f"\nLLM Available: {llm.is_available}")
    if llm.is_available:
        print(f"Active Model: {llm.get_status().get('model')}")
        
    # Setup session for pipeline
    session = {
        "filename": os.path.basename(file_path),
        "file_path": file_path,
        "df": df,
        "original_shape": df.shape,
        "audit_trail": [],
        "iteration_count": 0,
    }
    
    pipeline = IterativePipeline()
    
    # Profile Before
    print("\n--- Generating Initial Profile ---")
    profiler = DataProfiler(df)
    profile = profiler.generate_full_profile()
    qs_before = profile.get("quality_score", {})
    print(f"Score BEFORE: {qs_before.get('overall', 0)}/100 (Grade {qs_before.get('grade', 'N/A')})")
    session["profile"] = profile
    
    # Auto Clean
    print("\n--- Running Auto-Clean Pipeline ---")
    clean_result = pipeline.auto_clean(session)
    print(f"Actions Applied: {clean_result.get('actions_applied', 0)}")
    for a in clean_result.get('audit', []):
        print(f"  [{a.get('action', '')}] {a.get('column', 'N/A')}: {a.get('detail', '')}")
    
    # Iterate (Re-profile & Compare)
    print("\n--- Running Iteration Comparison ---")
    iter_result = pipeline.iterate(session)
    comp = iter_result.get("comparison", {})
    qs_comp = comp.get("quality_score", {})
    print(f"Score AFTER: {qs_comp.get('after', 0)}/100 (Grade {qs_comp.get('grade_after', 'N/A')})")
    print(f"Improvement: +{qs_comp.get('change', 0)} points")
    
    if comp.get('narrative'):
        print("\nImprovement Narrative:")
        print(comp['narrative'])

if __name__ == "__main__":
    if len(sys.argv) > 1:
        files_to_test = sys.argv[1:]
        for path in files_to_test:
            test_dirty_csv(path)
    else:
        downloads = os.path.expanduser(r"~\Downloads")
        files_to_test = [
            "unclean_data.csv",
            r"audible_uncleaned.csv\audible_uncleaned.csv"
        ]
        
        for filename in files_to_test:
            path = os.path.join(downloads, filename)
            test_dirty_csv(path)
