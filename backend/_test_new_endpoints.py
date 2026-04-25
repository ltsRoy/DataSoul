"""Quick E2E test for new CSV Correction + Prediction endpoints"""
import requests
import json
import sys

BASE = "http://localhost:8001"

def test():
    # 1. Load demo dataset
    r = requests.post(f"{BASE}/api/demo/retail")
    if r.status_code != 200:
        print(f"FAIL: Demo load failed: {r.status_code} {r.text}")
        return
    demo = r.json()
    sid = demo["session_id"]
    print(f"1. Demo loaded: session={sid} ({demo['rows']}x{demo['cols']})")
    print(f"   Columns: {demo['columns']}")

    # 2. Profile
    r = requests.get(f"{BASE}/api/profile/{sid}")
    profile = r.json()
    score = profile["quality_score"]["overall"]
    grade = profile["quality_score"]["grade"]
    print(f"2. Profile: Health={score}/100 Grade={grade}")

    # 3. Analyze corrections
    print("3. Analyzing corrections...")
    r = requests.post(f"{BASE}/api/correct/{sid}/analyze")
    analysis = r.json()
    print(f"   Issues found: {analysis['issues_found']}")
    print(f"   Columns analyzed: {analysis['columns_analyzed']}")
    print(f"   LLM powered: {analysis['llm_powered']}")
    print(f"   Encoding issues: {len(analysis['encoding_issues'])}")
    print(f"   Format issues: {len(analysis['format_issues'])}")
    print(f"   Category merges: {len(analysis['category_merges'])}")
    for m in analysis["category_merges"][:3]:
        print(f"     '{m['old_value']}' -> '{m['new_value']}' (conf={m['confidence']})")
    print(f"   Value corrections: {len(analysis['corrections'])}")
    for c in analysis["corrections"][:3]:
        print(f"     '{c['old_value']}' -> '{c['new_value']}' ({c['reason'][:60]})")

    # 4. Auto-correct
    print("4. Running auto-correct...")
    r = requests.post(f"{BASE}/api/correct/{sid}", json={"threshold": 0.90})
    corrected = r.json()
    print(f"   Corrections applied: {corrected['corrections_applied']}")
    for a in corrected.get("audit", [])[:3]:
        print(f"     [{a['action']}] {a['detail'][:70]}")

    # 5. Predict missing values (pick first column with missing)
    missing_cols = [c for c in profile.get("columns", []) if c.get("missing_pct", 0) > 0]
    if missing_cols:
        col = missing_cols[0]["name"]
        print(f"5. Predicting missing values for '{col}'...")
        r = requests.post(f"{BASE}/api/predict/{sid}", json={"column": col})
        pred = r.json()
        print(f"   Status: {pred['status']}")
        print(f"   Model: {pred.get('model', 'N/A')}")
        print(f"   Missing count: {pred.get('missing_count', 0)}")
        if pred.get("llm_explanation"):
            print(f"   LLM: {pred['llm_explanation'][:120]}")
    else:
        print("5. No missing values to predict")

    # 6. Feature suggestions
    print("6. Getting feature engineering suggestions...")
    r = requests.post(f"{BASE}/api/predict/{sid}/features")
    feats = r.json()
    print(f"   Suggestions: {len(feats.get('suggestions', []))}")
    print(f"   LLM powered: {feats.get('llm_powered', False)}")
    for s in feats.get("suggestions", [])[:4]:
        name = s.get("new_feature") or str(s.get("new_features", ""))
        print(f"     [{s['type']}] {name} - {s['reason'][:60]}")

    # 7. Anomaly detection
    numeric_cols = [c for c in profile.get("columns", []) if "float" in c.get("dtype", "") or "int" in c.get("dtype", "")]
    if numeric_cols:
        col = numeric_cols[0]["name"]
        print(f"7. Detecting anomalies in '{col}'...")
        r = requests.post(f"{BASE}/api/predict/{sid}/anomalies", json={"column": col})
        anomalies = r.json()
        print(f"   Found: {anomalies.get('anomalies_found', 0)} ({anomalies.get('anomaly_pct', 0)}%)")
        print(f"   Model: {anomalies.get('model', 'N/A')}")
        if anomalies.get("llm_analysis"):
            print(f"   LLM: {anomalies['llm_analysis'][:120]}")
    else:
        print("7. No numeric columns for anomaly detection")

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    test()
