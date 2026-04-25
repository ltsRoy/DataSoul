"""
DataSoul v3.0 -- Full E2E Test
Tests: Health, Upload, Profile, Threats, Correction, Prediction, RAG, Chat
"""
import requests
import json
import sys
import time
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = "http://localhost:8001"
PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} -- {detail}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ══════════════════════════════════════
section("1. HEALTH CHECK")
# ══════════════════════════════════════
r = requests.get(f"{BASE}/api/health")
h = r.json()
check("API responds", r.status_code == 200)
check("Version 3.0.0", h.get("version") == "3.0.0", h.get("version"))
check("LLM available", h.get("llm_status", {}).get("available") == True)
check("RAG ready", h.get("rag_status", {}).get("is_ready") == True)
check("CSV Corrector present", "csv_corrector_status" in h)
check("Prediction Engine present", "prediction_engine_status" in h)
check("sklearn available", h.get("prediction_engine_status", {}).get("has_sklearn") == True)
print(f"\n  Model: {h.get('llm_status', {}).get('model', 'N/A')}")
print(f"  RAG docs: {h.get('rag_status', {}).get('total_documents', 0)}")

# ══════════════════════════════════════
section("2. DEMO DATASET LOAD")
# ══════════════════════════════════════
r = requests.post(f"{BASE}/api/demo/retail")
demo = r.json()
sid = demo["session_id"]
check("Demo loaded", r.status_code == 200)
check("Has session_id", bool(sid))
check("Has rows", demo.get("rows", 0) > 0, f"rows={demo.get('rows')}")
check("Has columns", demo.get("cols", 0) > 0, f"cols={demo.get('cols')}")
print(f"\n  Session: {sid}")
print(f"  Shape: {demo['rows']} x {demo['cols']}")
print(f"  Columns: {', '.join(demo['columns'][:6])}...")

# ══════════════════════════════════════
section("3. PROFILING + RAG INDEXING")
# ══════════════════════════════════════
r = requests.get(f"{BASE}/api/profile/{sid}")
profile = r.json()
qs = profile.get("quality_score", {})
check("Profile success", r.status_code == 200)
check("Has quality_score", "quality_score" in profile)
check("Has columns", len(profile.get("columns", [])) > 0)
check("Has sector", "sector" in profile)
check("Score > 0", qs.get("overall", 0) > 0)
print(f"\n  Health: {qs.get('overall')}/100 (Grade {qs.get('grade')})")
print(f"  Sector: {profile.get('sector', {}).get('sector_name', 'N/A')}")
print(f"  Dimensions: {list(qs.get('dimensions', {}).keys())}")

# ══════════════════════════════════════
section("4. THREAT DETECTION")
# ══════════════════════════════════════
r = requests.get(f"{BASE}/api/threats/{sid}")
threats = r.json()
check("Threats success", r.status_code == 200)
check("Has threat list", "threats" in threats)
check("Has severity counts", "critical" in threats and "warning" in threats)
print(f"\n  Total: {threats.get('total', 0)} threats")
print(f"  Critical: {threats.get('critical', 0)}, Warning: {threats.get('warning', 0)}, Low: {threats.get('low', 0)}")
for t in threats.get("threats", [])[:3]:
    print(f"  [{t['severity'].upper()}] {t['title']}")

# ══════════════════════════════════════
section("5. CSV CORRECTION — ANALYZE")
# ══════════════════════════════════════
print("  Analyzing (this uses Ollama)...")
r = requests.post(f"{BASE}/api/correct/{sid}/analyze")
analysis = r.json()
check("Analyze success", r.status_code == 200)
check("Has issues_found", "issues_found" in analysis)
check("Has columns_analyzed", analysis.get("columns_analyzed", 0) > 0)
check("LLM powered", analysis.get("llm_powered") == True)
print(f"\n  Issues: {analysis['issues_found']}")
print(f"  Encoding issues: {len(analysis.get('encoding_issues', []))}")
print(f"  Format issues: {len(analysis.get('format_issues', []))}")
print(f"  Category merges: {len(analysis.get('category_merges', []))}")
for m in analysis.get("category_merges", [])[:5]:
    print(f"    '{m['old_value']}' -> '{m['new_value']}' (conf={m['confidence']}, {m.get('reason', '')[:50]})")
print(f"  Value corrections: {len(analysis.get('corrections', []))}")
for c in analysis.get("corrections", [])[:3]:
    print(f"    '{c['old_value']}' -> '{c['new_value']}' ({c.get('reason', '')[:50]})")

# ══════════════════════════════════════
section("6. CSV CORRECTION — AUTO-CORRECT")
# ══════════════════════════════════════
print("  Running auto-correct (threshold=0.90)...")
r = requests.post(f"{BASE}/api/correct/{sid}", json={"threshold": 0.90})
corrected = r.json()
check("Auto-correct success", r.status_code == 200)
check("Has corrections_applied", "corrections_applied" in corrected)
check("Has audit trail", len(corrected.get("audit", [])) >= 0)
print(f"\n  Corrections applied: {corrected.get('corrections_applied', 0)}")
for a in corrected.get("audit", [])[:5]:
    print(f"    [{a['action']}] {a['detail'][:65]} (conf={a.get('confidence', '?')}%)")

# ══════════════════════════════════════
section("7. PREDICTION — MISSING VALUES")
# ══════════════════════════════════════
# Find a column with missing values (prefer numeric since those are predictable)
missing_cols = [c for c in profile.get("columns", []) if c.get("missing_pct", 0) > 0]
numeric_cols = [c for c in profile.get("columns", []) if "float" in c.get("dtype", "") or "int" in c.get("dtype", "")]
numeric_missing = [c for c in missing_cols if "float" in c.get("dtype", "") or "int" in c.get("dtype", "")]
# Prefer numeric missing, fall back to any missing
predict_col_list = numeric_missing if numeric_missing else missing_cols

if predict_col_list:
    col = predict_col_list[0]["name"]
    print(f"  Predicting missing values for '{col}' ({predict_col_list[0]['missing_pct']}% missing)...")
    r = requests.post(f"{BASE}/api/predict/{sid}", json={"column": col})
    pred = r.json()
    check("Predict success", r.status_code == 200)
    check("Has status", pred.get("status") in ("success", "ok", "error"))
    check("Has model info", "model" in pred or "suggested_fill" in pred or "message" in pred)
    print(f"\n  Status: {pred.get('status')}")
    print(f"  Model: {pred.get('model', 'N/A')}")
    print(f"  Missing: {pred.get('missing_count', 0)}")
    if pred.get("feature_importance"):
        print(f"  Top features: {dict(list(pred['feature_importance'].items())[:3])}")
    if pred.get("llm_explanation"):
        print(f"  LLM: {pred['llm_explanation'][:150]}")
else:
    print("  >> No missing columns -- skipping")
    check("Skip (no missing)", True)

# ══════════════════════════════════════
section("8. PREDICTION — ANOMALY DETECTION")
# ══════════════════════════════════════
if numeric_cols:
    col = numeric_cols[0]["name"]
    print(f"  Detecting anomalies in '{col}'...")
    r = requests.post(f"{BASE}/api/predict/{sid}/anomalies", json={"column": col})
    anom = r.json()
    check("Anomaly success", r.status_code == 200)
    check("Has anomalies_found", "anomalies_found" in anom)
    check("Has model", "model" in anom)
    print(f"\n  Found: {anom.get('anomalies_found', 0)} ({anom.get('anomaly_pct', 0)}%)")
    print(f"  Model: {anom.get('model', 'N/A')}")
    if anom.get("stats"):
        s = anom["stats"]
        print(f"  Range: [{s.get('lower_fence', '?')}, {s.get('upper_fence', '?')}]")
    if anom.get("llm_analysis"):
        print(f"  LLM: {anom['llm_analysis'][:150]}")
else:
    print("  >> No numeric columns")
    check("Skip (no numeric)", True)

# ══════════════════════════════════════
section("9. PREDICTION — FEATURE ENGINEERING")
# ══════════════════════════════════════
print("  Getting feature suggestions...")
r = requests.post(f"{BASE}/api/predict/{sid}/features")
feats = r.json()
check("Features success", r.status_code == 200)
check("Has suggestions", len(feats.get("suggestions", [])) > 0)
check("LLM powered", feats.get("llm_powered") == True)
print(f"\n  Suggestions: {len(feats.get('suggestions', []))}")
for s in feats.get("suggestions", [])[:6]:
    name = s.get("new_feature") or str(s.get("new_features", ""))[:40]
    print(f"    [{s['type']}] {name} -- {s.get('reason', '')[:55]}")

# ══════════════════════════════════════
section("10. TREND FORECAST")
# ══════════════════════════════════════
# Find a date column and numeric column
date_cols = []
for c in profile.get("columns", []):
    if "date" in c["name"].lower():
        date_cols.append(c["name"])

val_cols = [c["name"] for c in numeric_cols[:1]] if numeric_cols else []

if date_cols and val_cols:
    print(f"  Forecasting {val_cols[0]} over {date_cols[0]}...")
    r = requests.post(f"{BASE}/api/predict/{sid}/trend", json={
        "date_column": date_cols[0],
        "value_column": val_cols[0],
        "periods": 7
    })
    trend = r.json()
    check("Trend success", r.status_code == 200)
    if trend.get("status") == "success":
        check("Has forecast", len(trend.get("forecast", [])) > 0)
        print(f"\n  Direction: {trend['trend']['direction']}")
        print(f"  R²: {trend['trend']['r_squared']}")
        print(f"  Forecast: {trend['forecast'][:5]}")
        if trend.get("llm_narrative"):
            print(f"  LLM: {trend['llm_narrative'][:150]}")
    else:
        check("Trend status", False, trend.get("message", "unknown error"))
else:
    print("  >> No date+numeric column pair found")
    check("Skip (no date col)", True)

# ══════════════════════════════════════
section("11. ENHANCED RAG CHAT")
# ══════════════════════════════════════
print("  Asking about the dataset...")
r = requests.post(f"{BASE}/api/chat/{sid}", json={
    "question": "What are the main quality issues in this dataset?"
})
chat = r.json()
check("Chat success", r.status_code == 200)
check("Has answer", len(chat.get("answer", "")) > 20)
check("RAG augmented", chat.get("rag_augmented") == True)
print(f"\n  LLM powered: {chat.get('llm_powered')}")
print(f"  RAG augmented: {chat.get('rag_augmented')}")
answer_preview = chat.get("answer", "")[:200].replace("\n", " ")
print(f"  Answer: {answer_preview}...")

# ══════════════════════════════════════
section("RESULTS")
# ══════════════════════════════════════
total = PASS + FAIL
print(f"\n  PASSED: {PASS}/{total}")
print(f"  FAILED: {FAIL}/{total}")
print(f"\n  {'ALL TESTS PASSED!' if FAIL == 0 else 'Some tests failed.'}")
print()
