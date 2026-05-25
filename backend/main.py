"""FastAPI backend — dataset profiling, threat detection, auto-cleaning,
AI narratives, RAG chat, predictions, and integrations.
"""

import os
import uuid
import json
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
import pandas as pd
import numpy as np

from profiler import DataProfiler
from threat_detector import ThreatDetector
from sector_detector import SectorDetector
from strategy_engine import StrategyEngine
from narrative_engine import NarrativeEngine
from rag_engine import RAGEngine, get_rag
from knowledge_scraper import KnowledgeScraper
from pipeline_engine import IterativePipeline
from llm_engine import get_llm
from csv_corrector import CSVCorrector
from prediction_engine import PredictionEngine
from integrations import list_integrations, get_integration


app = FastAPI(
    title="DataSoul API",
    description="Intelligent Data Readiness & Business Intelligence Engine with RAG, Iterative Pipeline, CSV Correction & Predictions",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# session store (in-memory; swap for DB in prod)
sessions: dict = {}
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# engines
rag_engine = RAGEngine()
pipeline = IterativePipeline()
llm = get_llm()
csv_corrector = CSVCorrector()
prediction_engine = PredictionEngine()


def _active_df(session: dict) -> pd.DataFrame:
    """Return the latest dataframe for the session."""
    return session.get("df_transformed", session["df"])


def _invalidate_analysis_cache(session: dict) -> None:
    """Drop cached analysis after any dataframe mutation."""
    session.pop("profile", None)
    session.pop("threats", None)


def _profile_session(session: dict, df: pd.DataFrame | None = None) -> dict:
    """Build and cache a fresh profile for the latest dataframe."""
    active = df if df is not None else _active_df(session)
    profiler = DataProfiler(active)
    profile = profiler.generate_full_profile()
    profile["filename"] = session.get("filename", "dataset")
    profile["sector"] = SectorDetector().detect(active)
    session["profile"] = profile
    return profile


# --- core endpoints ---

@app.get("/api/health")
def api_health():
    """Health check"""
    return {
        "status": "ok",
        "version": "3.0.0",
        "engine": "DataSoul AI",
        "rag_status": rag_engine.get_status(),
        "llm_status": llm.get_status(),
        "csv_corrector_status": csv_corrector.get_status(),
        "prediction_engine_status": prediction_engine.get_status(),
        "active_sessions": len(sessions),
    }


@app.post("/api/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """Upload a CSV/XLSX file and create a session"""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(400, f"Unsupported file type: .{ext}. Use CSV or XLSX.")

    session_id = str(uuid.uuid4())[:8]
    file_path = UPLOAD_DIR / f"{session_id}_{file.filename}"

    # Save file
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Parse
    try:
        if ext == "csv":
            df = pd.read_csv(file_path, low_memory=False)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse file: {str(e)}")

    # Store in session
    sessions[session_id] = {
        "filename": file.filename,
        "file_path": str(file_path),
        "df": df,
        "original_shape": df.shape,
        "audit_trail": [],
        "iteration_count": 0,
    }

    return {
        "session_id": session_id,
        "filename": file.filename,
        "rows": df.shape[0],
        "cols": df.shape[1],
        "columns": list(df.columns),
        "size_mb": round(len(content) / (1024 * 1024), 2),
    }


@app.get("/api/profile/{session_id}")
def get_profile(session_id: str):
    """Get full dataset profile"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    df = _active_df(session)
    profile = _profile_session(session, df)

    # Auto-index dataset context into RAG for contextual Q&A
    if rag_engine.is_ready:
        try:
            rag_engine.ingest_dataset_context(df, profile, session_id)
        except Exception as e:
            print(f"[DataSoul] Dataset RAG indexing failed (non-critical): {e}")

    return profile


@app.get("/api/threats/{session_id}")
def get_threats(session_id: str):
    """Get threat analysis"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    df = _active_df(session)
    profile = _profile_session(session, df)
    detector = ThreatDetector(df, profile)
    threats = detector.detect_all_threats()

    session["threats"] = threats
    return threats


@app.get("/api/strategies/{session_id}")
def get_strategies(session_id: str):
    """Get preprocessing strategy recommendations"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    df = _active_df(session)
    profile = _profile_session(session, df)

    engine = StrategyEngine()
    strategies = engine.recommend(df, profile)

    session["strategies"] = strategies
    return strategies


@app.post("/api/transform/{session_id}")
def transform_dataset(session_id: str, actions: dict):
    """Apply approved transformations"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    df = _active_df(session).copy()
    input_shape = df.shape
    audit = []

    for action in actions.get("approved_actions", []):
        action_type = action.get("type")
        column = action.get("column")

        if action_type == "remove_duplicates":
            before = len(df)
            df = df.drop_duplicates()
            removed = before - len(df)
            audit.append({
                "action": "REMOVE_DUPLICATES",
                "detail": f"Removed {removed} duplicate rows",
                "rows_affected": removed,
            })

        elif action_type == "impute_median" and column:
            missing = df[column].isna().sum()
            median_val = df[column].median()
            df[column] = df[column].fillna(median_val)
            audit.append({
                "action": "IMPUTE_MISSING",
                "column": column,
                "detail": f"Filled {missing} missing values with median ({median_val:.2f})",
                "rows_affected": int(missing),
            })

        elif action_type == "impute_mode" and column:
            missing = df[column].isna().sum()
            mode_val = df[column].mode().iloc[0] if not df[column].mode().empty else "Unknown"
            df[column] = df[column].fillna(mode_val)
            audit.append({
                "action": "IMPUTE_MISSING",
                "column": column,
                "detail": f"Filled {missing} missing values with mode ({mode_val})",
                "rows_affected": int(missing),
            })

        elif action_type == "standardize_case" and column:
            before_unique = df[column].nunique()
            df[column] = df[column].astype(str).str.strip().str.title()
            after_unique = df[column].nunique()
            audit.append({
                "action": "STANDARDIZE",
                "column": column,
                "detail": f"Standardized case: {before_unique} → {after_unique} unique values",
                "rows_affected": len(df),
            })

        elif action_type == "drop_column" and column:
            df = df.drop(columns=[column])
            audit.append({
                "action": "DROP_COLUMN",
                "column": column,
                "detail": f"Dropped column '{column}'",
                "rows_affected": 0,
            })

    session["df_transformed"] = df
    session["audit_trail"].extend(audit)
    _invalidate_analysis_cache(session)

    return {
        "status": "success",
        "original_shape": list(input_shape),
        "new_shape": list(df.shape),
        "actions_applied": len(audit),
        "audit_trail": audit,
    }


@app.get("/api/insights/{session_id}")
def get_insights(session_id: str):
    """Get auto-generated business insights"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    df = _active_df(session)
    profile = _profile_session(session, df)
    threats = ThreatDetector(df, profile).detect_all_threats()
    session["threats"] = threats

    if not profile:
        profiler = DataProfiler(df)
        profile = profiler.generate_full_profile()

    engine = NarrativeEngine()
    insights = engine.generate_insights(df, profile)

    return insights


@app.get("/api/story/{session_id}")
def get_story(session_id: str):
    """Get AI-generated executive narrative with RAG augmentation"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    df = _active_df(session)
    profile = _profile_session(session, df)
    threats = ThreatDetector(df, profile).detect_all_threats()
    session["threats"] = threats
    threats = session.get("threats", {"threats": []})

    # Get RAG context for enrichment
    rag_context = ""
    if rag_engine.is_ready and profile:
        sector = profile.get("sector", {}).get("sector_name", "General")
        rag_context = rag_engine.get_context_for_prompt(
            f"business narrative for {sector} dataset with {len(df)} rows",
            dataset_profile=profile,
            n_results=3,
        )

    engine = NarrativeEngine()
    story = engine.generate_story(df, profile, threats, rag_context=rag_context)

    # Append RAG-enhanced insights if available and LLM didn't already use it
    if rag_context and "No relevant knowledge" not in rag_context and not llm.is_available:
        story += "\n\n---\n\n### 🧠 DataSoul Intelligence (RAG-Enhanced)\n\n"
        story += "The following insights are augmented by DataSoul's knowledge base:\n\n"
        for line in rag_context.split("\n"):
            if line.strip() and not line.startswith("#"):
                story += f"> {line.strip()[:200]}\n"

    return {"story": story, "llm_powered": llm.is_available}


@app.get("/api/story/{session_id}/stream")
def stream_story(session_id: str):
    """Stream AI-generated narrative via SSE (Server-Sent Events)"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if not llm.is_available:
        raise HTTPException(503, "LLM not available. Install Ollama and pull a model.")

    df = session.get("df_transformed", session["df"])
    profile = session.get("profile")
    threats = session.get("threats", {"threats": [], "total": 0, "critical": 0, "warning": 0})

    # Get profile if not cached
    if not profile:
        profiler = DataProfiler(df)
        profile = profiler.generate_full_profile()
        session["profile"] = profile

    # Get threats if not cached
    if not session.get("threats"):
        detector = ThreatDetector(df, profile)
        threats = detector.detect_all_threats()
        session["threats"] = threats

    # Get RAG context
    rag_context = ""
    if rag_engine.is_ready:
        sector = profile.get("sector", {}).get("sector_name", "General")
        rag_context = rag_engine.get_context_for_prompt(
            f"executive narrative for {sector} dataset with {len(df)} rows",
            dataset_profile=profile,
            n_results=5,
        )

    # Build summary for LLM
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    num_summary = {}
    for col in numeric_cols[:5]:
        clean = df[col].dropna()
        if len(clean) > 0:
            num_summary[col] = {"total": round(float(clean.sum()), 2), "mean": round(float(clean.mean()), 2), "median": round(float(clean.median()), 2)}

    df_summary = {"rows": len(df), "cols": len(df.columns), "numeric_summary": num_summary}

    def event_stream():
        import json as _json
        try:
            for token in llm.generate_narrative_stream(profile, threats, df_summary, rag_context=rag_context):
                yield f"data: {_json.dumps({'token': token})}\n\n"
            yield f"data: {_json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/timeline/{session_id}")
def get_timeline(session_id: str):
    """Get time-travel audit trail"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    return {
        "audit_trail": session.get("audit_trail", []),
        "original_shape": list(session.get("original_shape", (0, 0))),
        "current_shape": list(session.get("df_transformed", session["df"]).shape),
        "iteration_count": session.get("iteration_count", 0),
    }


@app.post("/api/chat/{session_id}")
def chat(session_id: str, body: dict):
    """Conversational Data Chat — RAG-augmented answers about your dataset"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    question = body.get("question", "")
    if not question:
        raise HTTPException(400, "No question provided")

    df = _active_df(session)

    # Use cached profile/threats if available — don't recompute on every question
    profile = session.get("profile")
    if not profile:
        profile = _profile_session(session, df)

    threats = session.get("threats")
    if not threats:
        threats = ThreatDetector(df, profile).detect_all_threats()
        session["threats"] = threats

    # Get dataset-aware RAG context (combines brain + dataset-specific context)
    rag_context = ""
    if rag_engine.is_ready:
        try:
            rag_context = rag_engine.get_dataset_aware_context(
                question,
                session_id=session_id,
                profile=profile,
                n_results=3,
            )
        except Exception:
            rag_context = ""

    engine = NarrativeEngine()
    answer = engine.answer_question(question, df, profile, rag_context=rag_context, threats=threats)

    # If the base engine gives a default/fallback response, try to augment with RAG
    if rag_context and "No relevant knowledge" not in rag_context and "Try asking" in answer:
        answer += "\n\n---\n\n**From DataSoul Knowledge Base:**\n\n"
        try:
            results = rag_engine.query(question, n_results=2)
            for r in results:
                text = r["text"][:300]
                answer += f"- {text}\n\n"
        except Exception:
            pass

    return {"question": question, "answer": answer, "rag_augmented": bool(rag_context), "llm_powered": llm.is_available}


@app.post("/api/chat/{session_id}/stream")
def stream_chat(session_id: str, body: dict):
    """Stream conversational data chat via SSE"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    question = body.get("question", "")
    if not question:
        raise HTTPException(400, "No question provided")

    if not llm.is_available:
        raise HTTPException(503, "LLM not available.")

    df = session.get("df_transformed", session["df"])
    profile = session.get("profile", {})

    # Build dataset context
    df_context = f"Columns: {list(df.columns)}\n"
    df_context += f"Shape: {df.shape}\n"
    df_context += f"Dtypes: {dict(df.dtypes.astype(str).value_counts())}\n"
    missing = df.isna().sum()
    missing_cols = missing[missing > 0]
    if len(missing_cols) > 0:
        df_context += f"Missing: {dict(missing_cols.head(5))}\n"
    for col in df.select_dtypes(include=[np.number]).columns[:3]:
        clean = df[col].dropna()
        if len(clean) > 0:
            df_context += f"{col}: mean={clean.mean():.2f}, median={clean.median():.2f}, min={clean.min():.2f}, max={clean.max():.2f}\n"

    # RAG context
    rag_context = ""
    if rag_engine.is_ready:
        rag_context = rag_engine.get_context_for_prompt(question, dataset_profile=profile, n_results=3)

    def event_stream():
        import json as _json
        try:
            for token in llm.answer_question_stream(question, df_context, profile, rag_context):
                yield f"data: {_json.dumps({'token': token})}\n\n"
            yield f"data: {_json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/llm/status")
def llm_status():
    """Get LLM engine status and configuration"""
    return llm.get_status()


@app.post("/api/llm/warmup")
def llm_warmup():
    """Warmup the LLM by loading the model into memory"""
    if not llm.is_available:
        return {"status": "unavailable", "message": "Ollama not running or no models installed"}
    success = llm.warmup()
    return {"status": "ready" if success else "failed", "model": llm.get_status()["model"]}


# --- csv correction endpoints ---

@app.post("/api/correct/{session_id}")
async def auto_correct_dataset(session_id: str, body: dict | None = None):
    """Full AI-powered CSV correction pipeline"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    df = session.get("df_transformed", session["df"])
    profile = session.get("profile")
    threshold = (body or {}).get("threshold", 0.90)

    # Run CPU-bound auto_correct in a thread to avoid blocking the event loop
    result = await asyncio.to_thread(csv_corrector.auto_correct, df, profile=profile, threshold=threshold)

    if result["corrections_applied"] > 0:
        session["df_transformed"] = result.pop("df")
        session["audit_trail"] = session.get("audit_trail", []) + result["audit"]
        _invalidate_analysis_cache(session)
    else:
        result.pop("df", None)

    return result


@app.post("/api/correct/{session_id}/analyze")
async def analyze_corrections(session_id: str):
    """Analyze dataset and return correction suggestions without applying changes"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    df = session.get("df_transformed", session["df"])
    profile = session.get("profile")

    # Directly await the async implementation — no ThreadPoolExecutor needed
    return await csv_corrector.analyze_async(df, profile=profile)


@app.post("/api/correct/{session_id}/apply")
def apply_corrections(session_id: str, body: dict):
    """Apply user-approved corrections from an analysis result"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    corrections = body.get("corrections", [])
    if not corrections:
        raise HTTPException(400, "No corrections provided")

    df = session.get("df_transformed", session["df"])
    result = csv_corrector.apply_corrections(df, corrections)

    if result["corrections_applied"] > 0:
        session["df_transformed"] = result.pop("df")
        session["audit_trail"] = session.get("audit_trail", []) + result["audit"]
        _invalidate_analysis_cache(session)
    else:
        result.pop("df", None)

    return result


# --- prediction endpoints ---

@app.post("/api/predict/{session_id}")
def predict_missing(session_id: str, body: dict):
    """Predict missing values in a column using ML + LLM interpretation"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    target_col = body.get("column")
    if not target_col:
        raise HTTPException(400, "column is required")

    df = session.get("df_transformed", session["df"])
    profile = session.get("profile")

    return prediction_engine.predict_missing(df, target_col, profile=profile)


@app.post("/api/predict/{session_id}/trend")
def forecast_trend(session_id: str, body: dict):
    """Forecast trends for a time-series column"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    date_col = body.get("date_column")
    value_col = body.get("value_column")
    periods = body.get("periods", 10)

    if not date_col or not value_col:
        raise HTTPException(400, "date_column and value_column are required")

    df = session.get("df_transformed", session["df"])
    profile = session.get("profile")

    return prediction_engine.forecast_trend(df, date_col, value_col, periods=periods, profile=profile)


@app.post("/api/predict/{session_id}/anomalies")
def detect_anomalies(session_id: str, body: dict):
    """Detect anomalous values in a numeric column"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    column = body.get("column")
    if not column:
        raise HTTPException(400, "column is required")

    df = session.get("df_transformed", session["df"])
    profile = session.get("profile")

    return prediction_engine.detect_anomalies(df, column, profile=profile)


@app.post("/api/predict/{session_id}/features")
def suggest_features(session_id: str):
    """Suggest feature engineering ideas using LLM + statistical analysis"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    df = session.get("df_transformed", session["df"])
    profile = session.get("profile")

    return prediction_engine.suggest_features(df, profile=profile)


# --- iterative pipeline endpoints ---

@app.post("/api/iterate/{session_id}")
def iterate_dataset(session_id: str):
    """Re-profile cleaned data and compare with original — the iterative improvement loop"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if "df_transformed" not in session and session.get("iteration_count", 0) == 0:
        raise HTTPException(400, "No transformations applied yet. Use /api/transform or /api/auto-clean first.")

    result = pipeline.iterate(session)
    return result


@app.post("/api/auto-clean/{session_id}")
def auto_clean_dataset(session_id: str):
    """Apply safe automatic cleaning (dedup, standardize case, impute safe columns)"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    result = pipeline.auto_clean(session)
    return result


@app.post("/api/auto-clean-and-iterate/{session_id}")
def auto_clean_and_iterate(session_id: str):
    """One-click: auto-clean then re-profile and compare"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    # Step 1: Auto-clean
    clean_result = pipeline.auto_clean(session)

    # Step 2: Iterate (re-profile and compare)
    iter_result = pipeline.iterate(session)

    return {
        "cleaning": clean_result,
        "iteration": iter_result,
    }


# --- rag endpoints ---

@app.get("/api/rag/status")
def rag_status():
    """Get RAG engine status"""
    return rag_engine.get_status()


@app.post("/api/rag/ingest")
def rag_ingest_brain():
    """Ingest all datasoul_brain knowledge into RAG"""
    result = rag_engine.ingest_brain_knowledge()
    return result


@app.post("/api/rag/scrape")
def rag_scrape_and_ingest():
    """Scrape external knowledge sources and ingest into RAG"""
    scraper = KnowledgeScraper()

    # Step 1: Scrape (or generate builtin if scraping fails)
    scrape_result = scraper.scrape_all(delay=0.5)

    # Step 2: Ingest into RAG
    chunks = scraper.get_chunks()
    ingest_result = rag_engine.ingest_scraped_content(chunks)

    return {
        "scraping": scrape_result,
        "ingestion": ingest_result,
    }


@app.post("/api/rag/query")
def rag_query(body: dict):
    """Query the RAG knowledge base"""
    question = body.get("question", "")
    if not question:
        raise HTTPException(400, "No question provided")

    n_results = body.get("n_results", 5)
    session_id = body.get("session_id")

    # Get profile context if session provided
    profile = None
    if session_id and session_id in sessions:
        profile = sessions[session_id].get("profile")

    context = rag_engine.get_context_for_prompt(question, dataset_profile=profile, n_results=n_results)
    results = rag_engine.query(question, n_results=n_results)

    return {
        "question": question,
        "results": results,
        "context": context,
        "total_results": len(results),
    }


@app.post("/api/rag/reset")
def rag_reset():
    """Clear and reset the RAG knowledge base"""
    return rag_engine.reset()


@app.post("/api/rag/ingest-all")
def rag_ingest_all():
    """Full pipeline: ingest brain + scrape external + ingest scraped"""
    results = {}

    # 1. Ingest brain knowledge
    results["brain"] = rag_engine.ingest_brain_knowledge()

    # 2. Scrape and ingest external knowledge
    scraper = KnowledgeScraper()
    scrape_result = scraper.scrape_all(delay=0.3)
    results["scraping"] = scrape_result

    chunks = scraper.get_chunks()
    results["scraped_ingestion"] = rag_engine.ingest_scraped_content(chunks)

    # 3. Final status
    results["final_status"] = rag_engine.get_status()

    return results


# --- demo endpoint ---

SAMPLE_DIR = Path("sample_datasets")

@app.post("/api/demo/{dataset_name}")
def load_demo_dataset(dataset_name: str):
    """Load a pre-built sample dataset and create a session"""
    # Map friendly names to filenames
    demo_map = {
        "retail": "retail_sales_demo.csv",
        "retail_sales_demo": "retail_sales_demo.csv",
    }

    filename = demo_map.get(dataset_name, f"{dataset_name}.csv")
    file_path = SAMPLE_DIR / filename

    if not file_path.exists():
        available = [f.stem for f in SAMPLE_DIR.glob("*.csv")]
        raise HTTPException(404, f"Demo dataset '{dataset_name}' not found. Available: {available}")

    try:
        df = pd.read_csv(file_path, low_memory=False)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse demo file: {str(e)}")

    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        "filename": filename,
        "file_path": str(file_path),
        "df": df,
        "original_shape": df.shape,
        "audit_trail": [],
        "iteration_count": 0,
    }

    return {
        "session_id": session_id,
        "filename": filename,
        "rows": df.shape[0],
        "cols": df.shape[1],
        "columns": list(df.columns),
        "size_mb": round(file_path.stat().st_size / (1024 * 1024), 2),
    }


# --- export endpoints ---

@app.get("/api/export/{session_id}/{format}")
def export_dataset(session_id: str, format: str):
    """Export dataset in various formats"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    df = session.get("df_transformed", session["df"])

    if format == "csv":
        export_path = UPLOAD_DIR / f"{session_id}_clean.csv"
        df.to_csv(export_path, index=False)
        return {"download_url": f"/api/download/{export_path.name}", "format": "csv", "rows": len(df), "cols": len(df.columns)}

    if format == "json":
        export_path = UPLOAD_DIR / f"{session_id}_clean.json"
        df.to_json(export_path, orient="records", indent=2)
        return {"download_url": f"/api/download/{export_path.name}", "format": "json", "rows": len(df), "cols": len(df.columns)}

    if format == "xlsx":
        export_path = UPLOAD_DIR / f"{session_id}_clean.xlsx"
        df.to_excel(export_path, index=False)
        return {"download_url": f"/api/download/{export_path.name}", "format": "xlsx", "rows": len(df), "cols": len(df.columns)}

    return {"error": f"Format '{format}' not supported", "available": ["csv", "json", "xlsx"]}


@app.get("/api/download/{filename}")
def download_file(filename: str):
    """Download an exported file"""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path=str(file_path), filename=filename)


# --- integration endpoints ---

@app.get("/api/integrations")
def get_integrations():
    """List all available integrations and their auth status"""
    return {"integrations": list_integrations()}
# --- MCP (Model Context Protocol) endpoints ---

@app.get("/api/mcp/awesome")
def get_awesome_mcp_servers():
    """Get the curated list of awesome MCP servers."""
    json_path = Path(__file__).parent / "integrations" / "awesome_mcp_servers.json"
    if not json_path.exists():
        return {"servers": []}
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return {"servers": json.load(f)}
    except Exception as e:
        raise HTTPException(500, f"Failed to load awesome servers: {e}")


@app.post("/api/mcp/connect")
async def connect_mcp_server(body: dict):
    """Initiate connection to an MCP server (stdio or sse)."""
    integration = get_integration("mcp")
    if not integration:
        raise HTTPException(503, "MCP integration not available")
        
    try:
        conn_id = await integration.connect_client(body)
        client = integration.get_client(conn_id)
        if not client:
            raise HTTPException(500, "Failed to register connection client")
            
        return {
            "status": "success",
            "connection_id": conn_id,
            "server_info": client.server_info,
            "capabilities": client.capabilities,
            "logs": client.logs
        }
    except Exception as e:
        raise HTTPException(400, f"Connection failed: {str(e)}")


@app.get("/api/mcp/discover/{connection_id}")
def discover_mcp_server(connection_id: str):
    """Retrieve logs, tools, and resources for an active MCP server."""
    integration = get_integration("mcp")
    if not integration:
        raise HTTPException(503, "MCP integration not available")
        
    client = integration.get_client(connection_id)
    if not client:
        raise HTTPException(404, f"No active connection found for ID: {connection_id}")
        
    return {
        "connection_id": connection_id,
        "is_connected": client.is_connected,
        "server_info": client.server_info,
        "capabilities": client.capabilities,
        "logs": client.logs
    }


@app.get("/api/mcp/discover/{connection_id}/details")
async def discover_mcp_server_details(connection_id: str):
    """Fetch lists of tools and resources exposed by the server."""
    integration = get_integration("mcp")
    if not integration:
        raise HTTPException(503, "MCP integration not available")
        
    client = integration.get_client(connection_id)
    if not client:
        raise HTTPException(404, f"No active connection found for ID: {connection_id}")
        
    try:
        tools = []
        resources = []
        
        # Check capabilities
        if client.capabilities.get("tools"):
            tools = await client.list_tools()
        if client.capabilities.get("resources"):
            resources = await client.list_resources()
            
        return {
            "connection_id": connection_id,
            "tools": tools,
            "resources": resources
        }
    except Exception as e:
        raise HTTPException(400, f"Discovery failed: {str(e)}")


@app.post("/api/mcp/call-tool/{connection_id}")
async def call_mcp_tool(connection_id: str, body: dict):
    """Call a specific tool on the connected server."""
    integration = get_integration("mcp")
    if not integration:
        raise HTTPException(503, "MCP integration not available")
        
    client = integration.get_client(connection_id)
    if not client:
        raise HTTPException(404, f"No active connection found for ID: {connection_id}")
        
    name = body.get("name", "")
    arguments = body.get("arguments", {})
    if not name:
        raise HTTPException(400, "tool 'name' is required")
        
    try:
        res = await client.call_tool(name, arguments)
        return res
    except Exception as e:
        raise HTTPException(400, f"Tool execution failed: {str(e)}")


@app.post("/api/mcp/read-resource/{connection_id}")
async def read_mcp_resource(connection_id: str, body: dict):
    """Read a specific resource from the connected server."""
    integration = get_integration("mcp")
    if not integration:
        raise HTTPException(503, "MCP integration not available")
        
    client = integration.get_client(connection_id)
    if not client:
        raise HTTPException(404, f"No active connection found for ID: {connection_id}")
        
    uri = body.get("uri", "")
    if not uri:
        raise HTTPException(400, "resource 'uri' is required")
        
    try:
        res = await client.read_resource(uri)
        return res
    except Exception as e:
        raise HTTPException(400, f"Resource read failed: {str(e)}")


@app.post("/api/mcp/disconnect/{connection_id}")
async def disconnect_mcp_server(connection_id: str):
    """Cleanly close an MCP connection."""
    integration = get_integration("mcp")
    if not integration:
        raise HTTPException(503, "MCP integration not available")
        
    await integration.disconnect_client(connection_id)
    return {"status": "success", "message": f"Connection {connection_id} terminated"}


@app.post("/api/import/mcp")
def import_mcp_data(body: dict):
    """Import dataset generated from MCP tool calls or resource reads."""
    integration = get_integration("mcp")
    if not integration:
        raise HTTPException(503, "MCP integration not available")
        
    content = body.get("content", "")
    source_name = body.get("source_name", "mcp_import")
    
    if not content:
        raise HTTPException(400, "No content provided to import")
        
    try:
        df = integration.import_data(source_name, content=content)
    except Exception as e:
        raise HTTPException(400, f"Import parser failed: {e}")
        
    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        "filename": f"mcp_{source_name[:20]}.csv",
        "file_path": "mcp",
        "df": df,
        "original_shape": df.shape,
        "audit_trail": [],
        "iteration_count": 0,
        "source": "mcp",
    }
    
    return {
        "session_id": session_id,
        "filename": f"MCP Import ({source_name})",
        "rows": df.shape[0],
        "cols": df.shape[1],
        "columns": list(df.columns)
    }


@app.post("/api/import/google-sheets")
def import_google_sheets(body: dict):

    """Import dataset from a Google Sheet URL"""
    integration = get_integration("google_sheets")
    if not integration:
        raise HTTPException(503, "Google Sheets integration not available")

    sheet_url = body.get("sheet_url", "")
    credentials = body.get("credentials", {})
    sheet_name = body.get("sheet_name")

    if not sheet_url:
        raise HTTPException(400, "sheet_url is required")

    try:
        df = integration.import_data(sheet_url, credentials, sheet_name=sheet_name)
    except Exception as e:
        raise HTTPException(400, f"Import failed: {e}")

    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        "filename": f"google_sheet_{session_id}.csv",
        "file_path": "google_sheets",
        "df": df,
        "original_shape": df.shape,
        "audit_trail": [],
        "iteration_count": 0,
        "source": "google_sheets",
    }
    return {"session_id": session_id, "filename": f"Google Sheet", "rows": df.shape[0], "cols": df.shape[1], "columns": list(df.columns)}


@app.post("/api/import/data-gov-in")
def import_data_gov_in(body: dict):
    """Import dataset from data.gov.in"""
    integration = get_integration("data_gov_in")
    if not integration:
        raise HTTPException(503, "data.gov.in integration not available")

    resource_id = body.get("resource_id", "")
    api_key = body.get("api_key", "")

    if not resource_id or not api_key:
        raise HTTPException(400, "resource_id and api_key are required")

    try:
        df = integration.import_data(
            resource_id,
            {"api_key": api_key},
            limit=body.get("limit", 1000),
            filters=body.get("filters", {}),
        )
    except Exception as e:
        raise HTTPException(400, f"Import failed: {e}")

    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        "filename": f"datagov_{resource_id[:12]}.csv",
        "file_path": "data_gov_in",
        "df": df,
        "original_shape": df.shape,
        "audit_trail": [],
        "iteration_count": 0,
        "source": "data_gov_in",
    }
    return {"session_id": session_id, "filename": f"data.gov.in dataset", "rows": df.shape[0], "cols": df.shape[1], "columns": list(df.columns)}


@app.post("/api/import/kaggle")
def import_kaggle(body: dict):
    """Import dataset from Kaggle"""
    integration = get_integration("kaggle")
    if not integration:
        raise HTTPException(503, "Kaggle integration not available")

    dataset_slug = body.get("dataset_slug", "")
    # Credentials can be passed as { username, key } from the frontend
    raw_creds = body.get("credentials") or {}
    if isinstance(raw_creds, dict) and raw_creds.get("username") and raw_creds.get("key"):
        credentials = {"username": raw_creds["username"], "key": raw_creds["key"]}
    else:
        credentials = None  # fall back to env vars / kaggle.json

    if not dataset_slug:
        raise HTTPException(400, "dataset_slug is required (e.g., 'username/dataset-name')")

    try:
        df = integration.import_data(dataset_slug, credentials, filename=body.get("filename"))
    except Exception as e:
        raise HTTPException(400, f"Import failed: {e}")

    session_id = str(uuid.uuid4())[:8]
    dataset_name = dataset_slug.split("/")[-1] if "/" in dataset_slug else dataset_slug
    sessions[session_id] = {
        "filename": f"kaggle_{dataset_name}.csv",
        "file_path": "kaggle",
        "df": df,
        "original_shape": df.shape,
        "audit_trail": [],
        "iteration_count": 0,
        "source": "kaggle",
    }
    try:
        size_mb = round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2)
    except Exception:
        size_mb = 0.0

    return {
        "session_id": session_id,
        "filename": f"kaggle_{dataset_name}.csv",
        "rows": df.shape[0],
        "cols": df.shape[1],
        "columns": list(df.columns),
        "size_mb": size_mb,
    }



@app.post("/api/import/sql")
def import_sql(body: dict):
    """Import data from a SQL database"""
    integration = get_integration("sql")
    if not integration:
        raise HTTPException(503, "SQL integration not available")

    connection_string = body.get("connection_string", "")
    query = body.get("query", "")
    table = body.get("table")

    if not connection_string:
        raise HTTPException(400, "connection_string is required")
    if not query and not table:
        raise HTTPException(400, "Either query or table is required")

    try:
        df = integration.import_data(
            query or table,
            {"connection_string": connection_string},
            table=table,
            limit=body.get("limit"),
        )
    except Exception as e:
        raise HTTPException(400, f"Import failed: {e}")

    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        "filename": f"sql_query_{session_id}.csv",
        "file_path": "sql",
        "df": df,
        "original_shape": df.shape,
        "audit_trail": [],
        "iteration_count": 0,
        "source": "sql",
    }
    return {"session_id": session_id, "filename": "SQL Query Result", "rows": df.shape[0], "cols": df.shape[1], "columns": list(df.columns)}


@app.post("/api/export/{session_id}/google-sheets")
def export_to_google_sheets(session_id: str, body: dict):
    """Export cleaned dataset to Google Sheets"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    integration = get_integration("google_sheets")
    if not integration:
        raise HTTPException(503, "Google Sheets integration not available")

    df = session.get("df_transformed", session["df"])
    sheet_name = body.get("sheet_name", f"DataSoul_{session_id}")
    credentials = body.get("credentials", {})

    try:
        result = integration.export_data(
            df, sheet_name, credentials,
            metadata={"health_score": session.get("profile", {}).get("quality_score", {}).get("overall", "N/A")},
        )
        return result
    except Exception as e:
        raise HTTPException(400, f"Export failed: {e}")


@app.post("/api/export/{session_id}/huggingface")
def export_to_huggingface(session_id: str, body: dict):
    """Push cleaned dataset to Hugging Face Hub"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    integration = get_integration("huggingface")
    if not integration:
        raise HTTPException(503, "Hugging Face integration not available")

    df = session.get("df_transformed", session["df"])
    repo_name = body.get("repo_name", f"datasoul-{session_id}")
    token = body.get("token", "")
    private = body.get("private", False)

    try:
        result = integration.export_data(
            df, repo_name,
            credentials={"token": token},
            metadata={"profile": session.get("profile", {})},
            private=private,
        )
        return result
    except Exception as e:
        raise HTTPException(400, f"Export failed: {e}")


@app.post("/api/export/{session_id}/colab-notebook")
def export_colab_notebook(session_id: str):
    """Generate and download a Colab-ready Jupyter notebook"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    integration = get_integration("google_colab")
    if not integration:
        raise HTTPException(503, "Colab notebook integration not available")

    df = session.get("df_transformed", session["df"])
    filename = session.get("filename", "dataset").rsplit(".", 1)[0]

    metadata = {
        "profile": session.get("profile", {}),
        "threats": session.get("threats", {}),
    }

    # Generate notebook bytes and save to uploads
    notebook_bytes = integration.generate_notebook_bytes(df, filename, metadata)
    nb_path = UPLOAD_DIR / f"{session_id}_{filename}.ipynb"
    with open(nb_path, "wb") as f:
        f.write(notebook_bytes)

    return {
        "download_url": f"/api/download/{nb_path.name}",
        "format": "ipynb",
        "filename": nb_path.name,
        "rows": len(df),
        "cols": len(df.columns),
    }


@app.post("/api/export/{session_id}/kaggle")
def export_to_kaggle(session_id: str, body: dict):
    """Export cleaned dataset to Kaggle"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    integration = get_integration("kaggle")
    if not integration:
        raise HTTPException(503, "Kaggle integration not available")

    df = session.get("df_transformed", session["df"])
    dataset_name = body.get("dataset_name", f"datasoul-{session_id}")
    credentials = body.get("credentials", {})

    try:
        result = integration.export_data(df, dataset_name, credentials)
        return result
    except Exception as e:
        raise HTTPException(400, f"Export failed: {e}")


# startup
@app.on_event("startup")
async def startup_event():
    """Auto-ingest brain knowledge on startup"""
    try:
        if rag_engine.is_ready:
            status = rag_engine.get_status()
            print("[DataSoul] Syncing brain knowledge base...")
            result = rag_engine.ingest_brain_knowledge()
            print(
                f"[DataSoul] Brain sync: {result.get('documents_ingested', 0)} chunks, "
                f"{result.get('files_updated', 0)} updated, {result.get('files_skipped', 0)} unchanged"
            )

            if status["total_documents"] == 0:
                # Generate and ingest builtin knowledge (no live scraping at startup)
                try:
                    scraper = KnowledgeScraper()
                    existing = scraper.load_from_disk()
                    if not existing:
                        print("[DataSoul] Generating builtin knowledge base...")
                        builtin_result = scraper._generate_builtin_knowledge()
                        existing = scraper.get_chunks()

                    if existing:
                        ingest = rag_engine.ingest_scraped_content(existing)
                        print(f"[DataSoul] Builtin knowledge ingested: {ingest.get('documents_ingested', 0)} documents")
                except Exception as e:
                    print(f"[DataSoul] Builtin knowledge ingestion failed (non-critical): {e}")

                print(f"[DataSoul] RAG ready with {rag_engine.get_status()['total_documents']} total documents")
            else:
                print(f"[DataSoul] RAG loaded with {rag_engine.get_status()['total_documents']} documents")
        else:
            print("[DataSoul] ChromaDB not available -- RAG features disabled")
    except Exception as e:
        print(f"[DataSoul] Startup RAG init failed (non-critical): {e}")


# run
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
