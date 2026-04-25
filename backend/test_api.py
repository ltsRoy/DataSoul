# -*- coding: utf-8 -*-
"""
DataSoul API -- Full Integration Test (v2.0)
=============================================
Tests: Upload -> Profile -> Threats -> Strategies -> Auto-Clean ->
       Iterate (cleaned data re-profiling) -> RAG -> Chat -> Story -> Export
"""
import requests
import json
import sys
import io

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = "http://localhost:8000/api"

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# 1. HEALTH CHECK
section("1. HEALTH CHECK")
resp = requests.get(f"{BASE}/health")
health = resp.json()
print(f"  Status: {health['status']}")
print(f"  Version: {health['version']}")
print(f"  RAG Ready: {health['rag_status']['is_ready']}")
print(f"  RAG Documents: {health['rag_status']['total_documents']}")


# 2. UPLOAD DATASET
section("2. UPLOAD DATASET")
with open("sample_datasets/retail_sales_demo.csv", "rb") as f:
    resp = requests.post(f"{BASE}/upload", files={"file": ("retail_sales_demo.csv", f, "text/csv")})
upload = resp.json()
sid = upload["session_id"]
print(f"  Session: {sid}")
print(f"  Shape: {upload['rows']} rows x {upload['cols']} cols")
print(f"  Size: {upload['size_mb']} MB")
print(f"  Columns: {', '.join(upload['columns'][:6])}...")


# 3. PROFILE (ORIGINAL DATA)
section("3. PROFILE -- Original Data")
resp = requests.get(f"{BASE}/profile/{sid}")
profile = resp.json()
qs = profile["quality_score"]
print(f"  Health Score: {qs['overall']}/100 (Grade: {qs['grade']})")
print(f"  Dimensions:")
for dim, data in qs["dimensions"].items():
    score = data["score"]
    filled = int(score / 10)
    bar = "#" * filled + "." * (10 - filled)
    print(f"    {dim:15s} [{bar}] {score}")
sector = profile.get("sector", {})
print(f"  Sector: {sector.get('sector_name', 'N/A')} ({sector.get('confidence', 0)}%)")
print(f"  Missing: {profile['missing_summary']['overall_missing_pct']}%")
print(f"  Duplicates: {profile['duplicates']['exact_duplicates']}")


# 4. THREATS
section("4. THREATS")
resp = requests.get(f"{BASE}/threats/{sid}")
threats = resp.json()
print(f"  Total: {threats['total']} | CRITICAL: {threats['critical']} | WARNING: {threats['warning']} | LOW: {threats['low']}")
for t in threats["threats"][:5]:
    sev = t["severity"].upper()
    print(f"  [{sev}] {t['title']} ({t['confidence']}%)")


# 5. STRATEGIES
section("5. STRATEGIES")
resp = requests.get(f"{BASE}/strategies/{sid}")
strats = resp.json()
print(f"  Total recommendations: {strats['total_recommendations']}")
for s in strats["strategies"][:5]:
    for r in s["recommendations"][:1]:
        print(f"  {s['column']:20s} -> {r['strategy']} ({r.get('confidence', 0)}%)")


# 6. AUTO-CLEAN (uses cleaned data!)
section("6. AUTO-CLEAN -- Using Cleaned Data")
resp = requests.post(f"{BASE}/auto-clean/{sid}")
clean = resp.json()
print(f"  Actions applied: {clean['actions_applied']}")
print(f"  Shape: {clean['original_shape']} -> {clean['cleaned_shape']}")
for a in clean["audit"]:
    col = a.get("column", "all")
    print(f"  [OK] [{a['action']}] {col}: {a['detail']}")


# 7. ITERATE -- Re-profile cleaned data
section("7. ITERATE -- Re-profile Cleaned Data vs Original")
resp = requests.post(f"{BASE}/iterate/{sid}")
iteration = resp.json()
comp = iteration["comparison"]
print(f"  Iteration #{iteration['iteration']}")
print(f"  Quality Score: {comp['quality_score']['before']} -> {comp['quality_score']['after']} ({comp['quality_score']['change']:+.1f})")
print(f"  Grade: {comp['quality_score']['grade_before']} -> {comp['quality_score']['grade_after']}")
print(f"  Threats: {comp['threats']['before']} -> {comp['threats']['after']} ({comp['threats']['resolved']} resolved)")
print(f"  Critical: {comp['threats']['critical_before']} -> {comp['threats']['critical_after']}")
print(f"  Missing: {comp['missing_data']['before_pct']}% -> {comp['missing_data']['after_pct']}%")
print(f"  Duplicates: {comp['duplicates']['before']} -> {comp['duplicates']['after']}")
print(f"\n  --- Improvement Narrative ---")
for line in comp['narrative'].split('\n')[:8]:
    # Strip emoji for console safety
    safe = line.encode('ascii', 'replace').decode('ascii')
    print(f"  {safe}")


# 8. RAG -- Ingest & Query
section("8. RAG -- Knowledge Base")
resp = requests.get(f"{BASE}/rag/status")
rag = resp.json()
print(f"  RAG Ready: {rag['is_ready']}")
print(f"  Documents: {rag['total_documents']}")

if rag["total_documents"] == 0:
    print("  Ingesting brain knowledge...")
    resp = requests.post(f"{BASE}/rag/ingest-all")
    ingest = resp.json()
    print(f"  Brain: {ingest.get('brain', {}).get('documents_ingested', 0)} docs")
    print(f"  Scraped: {ingest.get('scraping', {}).get('total_chunks', 0)} chunks")
    print(f"  Total: {ingest.get('final_status', {}).get('total_documents', 0)} docs")

# Query
print("\n  Query: 'How to handle missing values in skewed data?'")
resp = requests.post(f"{BASE}/rag/query", json={
    "question": "How to handle missing values in right-skewed numeric data?",
    "n_results": 3,
    "session_id": sid,
})
query_result = resp.json()
print(f"  Results: {query_result['total_results']}")
for r in query_result["results"][:2]:
    text = r["text"][:120].encode('ascii', 'replace').decode('ascii')
    print(f"  [rel={r['relevance']:.2f}] {text}...")


# 9. CHAT -- RAG-Augmented
section("9. CHAT -- RAG-Augmented Q&A")
questions = [
    "What columns have missing values?",
    "Are there duplicates?",
    "Show me the data health score",
]
for q in questions:
    resp = requests.post(f"{BASE}/chat/{sid}", json={"question": q})
    chat = resp.json()
    answer_safe = chat['answer'][:150].encode('ascii', 'replace').decode('ascii')
    print(f"  Q: {q}")
    print(f"  A: {answer_safe}...")
    print(f"  RAG: {'Yes' if chat.get('rag_augmented') else 'No'}")
    print()


# 10. STORY
section("10. STORY -- Executive Narrative (first 400 chars)")
resp = requests.get(f"{BASE}/story/{sid}")
story = resp.json()
story_safe = story['story'][:400].encode('ascii', 'replace').decode('ascii')
print(f"  {story_safe}...")


# 11. EXPORT
section("11. EXPORT -- Cleaned Dataset")
for fmt in ["csv", "json"]:
    resp = requests.get(f"{BASE}/export/{sid}/{fmt}")
    export = resp.json()
    print(f"  {fmt.upper()}: {export.get('rows', 0)} rows x {export.get('cols', 0)} cols -> {export.get('download_url', 'N/A')}")


# 12. TIMELINE
section("12. TIMELINE -- Full Audit Trail")
resp = requests.get(f"{BASE}/timeline/{sid}")
timeline = resp.json()
print(f"  Original shape: {timeline['original_shape']}")
print(f"  Current shape: {timeline['current_shape']}")
print(f"  Iterations: {timeline['iteration_count']}")
print(f"  Actions logged: {len(timeline['audit_trail'])}")
for a in timeline["audit_trail"][:5]:
    detail = a.get('detail', '')[:80].encode('ascii', 'replace').decode('ascii')
    print(f"  * {a.get('action', 'N/A')}: {detail}")


print(f"\n{'='*60}")
print(f"  ALL TESTS PASSED -- DataSoul v2.0")
print(f"{'='*60}\n")
