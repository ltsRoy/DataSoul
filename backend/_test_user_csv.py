"""Test the profiler + corrector with the user's actual CSV file"""
import pandas as pd
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from profiler import DataProfiler
from csv_corrector import CSVCorrector

# Load the user's original file
df = pd.read_csv(r'C:\Users\sroy1\Downloads\my_file (1).csv')
print("=== ORIGINAL FILE ===")
print(f"Shape: {df.shape}")
print(f"Dtypes: {dict(df.dtypes.value_counts())}")
print(f"Columns: {list(df.columns)}")
print(f"Sample (row 0): {dict(df.iloc[0])}")

# Profile BEFORE fix
profiler = DataProfiler(df)
profile = profiler.generate_full_profile()
qs = profile["quality_score"]
print(f"\nScore BEFORE: {qs['overall']}/100 Grade {qs['grade']}")
for dim, data in qs["dimensions"].items():
    print(f"  {dim}: {data['score']}")
if "type_issues" in qs:
    print(f"\nType issues detected: {len(qs['type_issues'])}")
    for ti in qs["type_issues"]:
        print(f"  - {ti['column']}: {ti['issue']} ({ti})")

# Run corrector
print("\n=== RUNNING CORRECTOR ===")
corrector = CSVCorrector()
result = corrector.auto_correct(df, profile=profile)
df_clean = result["df"]
print(f"Corrections applied: {result['corrections_applied']}")
for a in result["audit"]:
    print(f"  [{a['action']}] {a.get('column', 'N/A')}: {a['detail'][:80]}")
print(f"\nDtypes after: {dict(df_clean.dtypes.value_counts())}")
print(f"Sample (row 0) after: {dict(df_clean.iloc[0])}")

# Profile AFTER fix
profiler2 = DataProfiler(df_clean)
profile2 = profiler2.generate_full_profile()
qs2 = profile2["quality_score"]
print(f"\nScore AFTER: {qs2['overall']}/100 Grade {qs2['grade']}")
for dim, data in qs2["dimensions"].items():
    print(f"  {dim}: {data['score']}")

delta = qs2["overall"] - qs["overall"]
print(f"\n{'='*50}")
print(f"DELTA: {qs['overall']} -> {qs2['overall']} ({delta:+.1f} points)")
print(f"GRADE: {qs['grade']} -> {qs2['grade']}")
print(f"{'='*50}")
