"""End-to-end test: Upload → Profile → LLM Cleaning Plan → Auto-Clean → Story"""
import os, sys
os.environ["OLLAMA_NUM_GPU"] = "0"

from llm_engine import get_llm
from rag_engine import RAGEngine
from profiler import DataProfiler
from threat_detector import ThreatDetector
from pipeline_engine import IterativePipeline
from narrative_engine import NarrativeEngine
import pandas as pd

# 1. Load demo data
print("=" * 60)
print("STEP 1: Loading demo dataset")
demo_path = os.path.join(os.path.dirname(__file__), "..", "datasoul_brain", "demo_datasets", "retail_sales_5000.csv")
if not os.path.exists(demo_path):
    print("Demo dataset not found, creating synthetic data...")
    import numpy as np
    np.random.seed(42)
    n = 1000
    df = pd.DataFrame({
        "order_id": range(1, n+1),
        "product_name": np.random.choice(["Laptop", "Headphones", "Mouse", "Keyboard", "Monitor"], n),
        "category": np.random.choice(["Electronics", "Audio", "Peripherals"], n),
        "unit_price": np.random.lognormal(8, 1, n).round(2),
        "quantity": np.random.randint(1, 10, n),
        "discount": np.where(np.random.random(n) > 0.7, np.random.uniform(5, 30, n).round(1), 0),
        "total_amount": np.random.lognormal(10, 1.5, n).round(2),
    })
    # Inject missing values
    for col in ["unit_price", "discount"]:
        mask = np.random.random(n) < 0.05
        df.loc[mask, col] = np.nan
    # Inject duplicates
    df = pd.concat([df, df.sample(20)], ignore_index=True)
else:
    df = pd.read_csv(demo_path)

print(f"  Shape: {df.shape}")
print(f"  Missing: {df.isna().sum().sum()} cells")
print(f"  Duplicates: {df.duplicated().sum()} rows")

# 2. Profile
print("\n" + "=" * 60)
print("STEP 2: Profiling dataset")
profiler = DataProfiler(df)
profile = profiler.generate_full_profile()
print(f"  Health Score: {profile['quality_score']['overall']}/100 (Grade: {profile['quality_score']['grade']})")

# 3. Detect threats
print("\n" + "=" * 60)
print("STEP 3: Detecting threats")
detector = ThreatDetector(df, profile)
threats = detector.detect_all_threats()
print(f"  Threats: {threats['total']} ({threats['critical']} critical, {threats['warning']} warning)")

# 4. LLM status
print("\n" + "=" * 60)
print("STEP 4: LLM + RAG Status")
llm = get_llm()
rag = RAGEngine()
print(f"  LLM Available: {llm.is_available} ({llm.get_status()['model']})")
print(f"  RAG Ready: {rag.is_ready} ({rag.get_status()['total_documents']} documents)")

# 5. Auto-clean with LLM+RAG
print("\n" + "=" * 60)
print("STEP 5: LLM+RAG Auto-Clean")
session = {"df": df, "profile": profile, "threats": threats}
pipeline = IterativePipeline()
result = pipeline.auto_clean(session)
print(f"  Actions: {result['actions_applied']}")
print(f"  LLM Powered: {result.get('llm_powered', False)}")
if result.get("llm_plan"):
    print(f"\n  --- LLM Cleaning Plan (first 300 chars) ---")
    print(f"  {result['llm_plan'][:300]}")
print(f"\n  --- Audit Trail ---")
for a in result["audit"]:
    source = a.get("source", "deterministic")
    print(f"  [{source}] {a['action']}: {a['detail']}")
    if a.get("reasoning"):
        print(f"           Reasoning: {a['reasoning'][:120]}")
if result.get("llm_summary"):
    print(f"\n  --- LLM Summary ---")
    print(f"  {result['llm_summary']}")

# 6. Quick LLM narrative test
if llm.is_available:
    print("\n" + "=" * 60)
    print("STEP 6: LLM Narrative Generation (first 200 chars)")
    engine = NarrativeEngine()
    story = engine.generate_story(df, profile, threats, rag_context="")
    print(f"  {story[:200]}...")
    print(f"\n  Narrative length: {len(story)} chars")

print("\n" + "=" * 60)
print("ALL TESTS COMPLETE")
