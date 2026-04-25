"""
DataSoul RAG Engine
=====================
ChromaDB-powered Retrieval Augmented Generation engine.
Ingests the entire DataSoul brain knowledge base + scraped external
knowledge and provides semantic search for context-aware AI responses.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

BRAIN_DIR = Path(__file__).parent.parent / "datasoul_brain"
RAG_PERSIST_DIR = Path(__file__).parent / "rag_store"


class RAGEngine:
    """Retrieval Augmented Generation engine using ChromaDB"""

    def __init__(self, persist_dir: str | None = None):
        self.persist_dir = Path(persist_dir) if persist_dir else RAG_PERSIST_DIR
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = None
        self.collection = None
        self.is_ready = False
        self._stats = {"total_documents": 0, "sources": []}

        if HAS_CHROMA:
            self._init_chroma()

    def _init_chroma(self):
        """Initialize ChromaDB client and collection"""
        try:
            self.client = chromadb.Client(Settings(
                anonymized_telemetry=False,
                is_persistent=True,
                persist_directory=str(self.persist_dir),
            ))
            self.collection = self.client.get_or_create_collection(
                name="datasoul_knowledge",
                metadata={"description": "DataSoul intelligence knowledge base"},
            )
            self._stats["total_documents"] = self.collection.count()
            self.is_ready = True
        except Exception as e:
            print(f"[RAG] ChromaDB init failed: {e}")
            self.is_ready = False

    # ─── INGESTION ───

    def ingest_brain_knowledge(self) -> dict:
        """Ingest all JSON files from datasoul_brain directory"""
        if not self.is_ready:
            return {"status": "error", "message": "ChromaDB not initialized"}

        ingested = 0
        sources = []

        for json_file in BRAIN_DIR.rglob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                rel_path = str(json_file.relative_to(BRAIN_DIR))
                chunks = self._extract_chunks_from_json(data, source=rel_path)

                for chunk in chunks:
                    doc_id = self._make_id(chunk["text"])
                    try:
                        self.collection.add(
                            documents=[chunk["text"]],
                            metadatas=[chunk["metadata"]],
                            ids=[doc_id],
                        )
                        ingested += 1
                    except Exception:
                        # Duplicate ID — skip
                        pass

                sources.append(rel_path)
            except Exception as e:
                print(f"[RAG] Failed to ingest {json_file}: {e}")

        # Ingest JSONL training data
        jsonl_path = BRAIN_DIR / "training_data" / "fine_tune_dataset.jsonl"
        if jsonl_path.exists():
            try:
                with open(jsonl_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    # Try parsing as JSON array first
                    try:
                        entries = json.loads(content)
                    except json.JSONDecodeError:
                        entries = [json.loads(line) for line in content.splitlines() if line.strip()]

                for entry in entries:
                    text = f"INSTRUCTION: {entry.get('instruction', '')}\nINPUT: {entry.get('input', '')}\nOUTPUT: {entry.get('output', '')}"
                    doc_id = self._make_id(text)
                    try:
                        self.collection.add(
                            documents=[text],
                            metadatas=[{"source": "training_data", "type": "few_shot_example"}],
                            ids=[doc_id],
                        )
                        ingested += 1
                    except Exception:
                        pass

                sources.append("training_data/fine_tune_dataset.jsonl")
            except Exception as e:
                print(f"[RAG] Failed to ingest JSONL: {e}")

        self._stats["total_documents"] = self.collection.count()
        self._stats["sources"] = sources

        return {
            "status": "success",
            "documents_ingested": ingested,
            "total_in_index": self.collection.count(),
            "sources": sources,
        }

    def ingest_scraped_content(self, chunks: list[dict]) -> dict:
        """Ingest scraped knowledge chunks into ChromaDB"""
        if not self.is_ready:
            return {"status": "error", "message": "ChromaDB not initialized"}

        ingested = 0
        for chunk in chunks:
            text = chunk.get("text", "")
            if not text or len(text) < 20:
                continue

            doc_id = self._make_id(text)
            metadata = {
                "source": chunk.get("source", "scraped"),
                "category": chunk.get("category", "general"),
                "url": chunk.get("url", ""),
                "type": "scraped_knowledge",
            }

            try:
                self.collection.add(
                    documents=[text],
                    metadatas=[metadata],
                    ids=[doc_id],
                )
                ingested += 1
            except Exception:
                pass

        self._stats["total_documents"] = self.collection.count()
        return {
            "status": "success",
            "documents_ingested": ingested,
            "total_in_index": self.collection.count(),
        }

    def ingest_text_chunks(self, chunks: list[dict]) -> dict:
        """Ingest arbitrary text chunks with metadata"""
        if not self.is_ready:
            return {"status": "error", "message": "ChromaDB not initialized"}

        ingested = 0
        for chunk in chunks:
            text = chunk.get("text", "")
            if not text or len(text) < 10:
                continue

            doc_id = self._make_id(text)
            metadata = chunk.get("metadata", {})
            metadata.setdefault("source", "manual")
            metadata.setdefault("type", "knowledge")

            # ChromaDB metadata values must be str, int, float, or bool
            clean_meta = {}
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                else:
                    clean_meta[k] = str(v)

            try:
                self.collection.add(
                    documents=[text],
                    metadatas=[clean_meta],
                    ids=[doc_id],
                )
                ingested += 1
            except Exception:
                pass

        self._stats["total_documents"] = self.collection.count()
        return {"status": "success", "documents_ingested": ingested}

    # ─── RETRIEVAL ───

    def query(self, question: str, n_results: int = 5, filter_metadata: dict | None = None) -> list[dict]:
        """Semantic search for relevant knowledge chunks"""
        if not self.is_ready or not self.collection:
            return []

        try:
            kwargs = {
                "query_texts": [question],
                "n_results": min(n_results, self.collection.count() or 1),
            }
            if filter_metadata:
                kwargs["where"] = filter_metadata

            results = self.collection.query(**kwargs)

            retrieved = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    entry = {
                        "text": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                        "relevance": round(max(0, 1 - (results["distances"][0][i] if results["distances"] else 0)), 3),
                    }
                    retrieved.append(entry)

            return retrieved
        except Exception as e:
            print(f"[RAG] Query failed: {e}")
            return []

    def get_context_for_prompt(self, question: str, dataset_profile: dict | None = None, n_results: int = 5) -> str:
        """Get formatted context block for LLM prompt injection"""
        # Build enriched query
        enriched_query = question
        if dataset_profile:
            cols = [c.get("name", "") for c in dataset_profile.get("columns", [])[:10]]
            sector = dataset_profile.get("sector", {}).get("sector_name", "")
            enriched_query = f"[Sector: {sector}] [Columns: {', '.join(cols)}] {question}"

        results = self.query(enriched_query, n_results=n_results)

        if not results:
            return "No relevant knowledge retrieved."

        context_parts = ["## Retrieved Knowledge (RAG)\n"]
        for i, r in enumerate(results, 1):
            source = r["metadata"].get("source", "unknown")
            relevance = r.get("relevance", 0)
            text = r["text"][:800]  # Cap each chunk
            context_parts.append(f"### Source {i} ({source}) — Relevance: {relevance}")
            context_parts.append(text)
            context_parts.append("")

        return "\n".join(context_parts)

    # ─── DATASET-AWARE INDEXING ───

    def ingest_dataset_context(self, df, profile: dict, session_id: str) -> dict:
        """Index column metadata and relationships from an uploaded dataset
        so they become searchable via RAG for hyper-contextual Q&A."""
        if not self.is_ready:
            return {"status": "error", "message": "ChromaDB not initialized"}

        import numpy as np
        ingested = 0
        sector = profile.get("sector", {}).get("sector_name", "General")

        # 1. Column-level metadata chunks
        for col_prof in profile.get("columns", []):
            col_name = col_prof["name"]
            parts = [f"Column: {col_name}", f"Type: {col_prof.get('dtype', 'unknown')}"]
            parts.append(f"Missing: {col_prof.get('missing_pct', 0)}%")
            parts.append(f"Unique values: {col_prof.get('unique', 0)} ({col_prof.get('cardinality', '')})")

            if col_prof.get("stats"):
                s = col_prof["stats"]
                parts.append(f"Stats: mean={s.get('mean')}, median={s.get('median')}, "
                             f"std={s.get('std')}, min={s.get('min')}, max={s.get('max')}")
            if col_prof.get("top_values"):
                top = list(col_prof["top_values"].items())[:5]
                parts.append(f"Top values: {', '.join(f'{k}({v})' for k, v in top)}")
            if col_prof.get("distribution"):
                parts.append(f"Distribution: {col_prof['distribution']}")

            text = "\n".join(parts)
            doc_id = self._make_id(f"ds_{session_id}_{col_name}")
            try:
                self.collection.add(
                    documents=[text],
                    metadatas=[{"source": f"dataset_{session_id}", "type": "dataset_column",
                                "session_id": session_id, "column": col_name, "sector": sector}],
                    ids=[doc_id],
                )
                ingested += 1
            except Exception:
                pass

        # 2. Correlation chunks
        corr_pairs = profile.get("correlations", {}).get("pairs", [])
        for pair in corr_pairs[:10]:
            text = (f"Correlation: {pair['col1']} and {pair['col2']} have "
                    f"{'strong' if abs(pair['correlation']) > 0.85 else 'moderate'} "
                    f"correlation of {pair['correlation']} in this {sector} dataset.")
            doc_id = self._make_id(f"ds_{session_id}_corr_{pair['col1']}_{pair['col2']}")
            try:
                self.collection.add(
                    documents=[text],
                    metadatas=[{"source": f"dataset_{session_id}", "type": "dataset_correlation",
                                "session_id": session_id, "sector": sector}],
                    ids=[doc_id],
                )
                ingested += 1
            except Exception:
                pass

        # 3. Quality summary chunk
        qs = profile.get("quality_score", {})
        quality_text = (f"Dataset quality: {qs.get('overall', 0)}/100 (Grade {qs.get('grade', 'N/A')}). "
                        f"Sector: {sector}. Shape: {profile.get('overview', {}).get('rows', '?')} rows x "
                        f"{profile.get('overview', {}).get('cols', '?')} columns.")
        if qs.get("dimensions"):
            for dim, data in qs["dimensions"].items():
                quality_text += f"\n{dim}: {data['score']}/100"
        doc_id = self._make_id(f"ds_{session_id}_quality")
        try:
            self.collection.add(
                documents=[quality_text],
                metadatas=[{"source": f"dataset_{session_id}", "type": "dataset_quality",
                            "session_id": session_id, "sector": sector}],
                ids=[doc_id],
            )
            ingested += 1
        except Exception:
            pass

        # 4. Missing data pattern chunk
        missing = profile.get("missing_summary", {})
        if missing.get("by_column"):
            miss_text = f"Missing data patterns in {sector} dataset:\n"
            for mc in missing["by_column"][:10]:
                miss_text += f"- {mc['column']}: {mc['missing_pct']}% missing ({mc['severity']})\n"
            doc_id = self._make_id(f"ds_{session_id}_missing")
            try:
                self.collection.add(
                    documents=[miss_text],
                    metadatas=[{"source": f"dataset_{session_id}", "type": "dataset_missing",
                                "session_id": session_id, "sector": sector}],
                    ids=[doc_id],
                )
                ingested += 1
            except Exception:
                pass

        self._stats["total_documents"] = self.collection.count()
        return {"status": "success", "documents_ingested": ingested,
                "session_id": session_id, "total_in_index": self.collection.count()}

    def get_dataset_aware_context(self, question: str, session_id: str,
                                   profile: dict | None = None, n_results: int = 5) -> str:
        """Combine brain + scraped + dataset-specific context for richer answers."""
        # 1. Dataset-specific context (filtered by session)
        ds_results = []
        if session_id:
            try:
                ds_results = self.query(question, n_results=3,
                                        filter_metadata={"session_id": session_id})
            except Exception:
                pass

        # 2. General knowledge context
        general_ctx = self.get_context_for_prompt(question, dataset_profile=profile,
                                                   n_results=n_results)

        # 3. Merge — dataset context first (higher priority)
        parts = []
        if ds_results:
            parts.append("## Your Dataset Context\n")
            for i, r in enumerate(ds_results, 1):
                parts.append(f"**[Dataset]** {r['text'][:600]}\n")

        if general_ctx and "No relevant" not in general_ctx:
            parts.append(general_ctx)

        return "\n".join(parts) if parts else "No relevant knowledge retrieved."

    # ─── STATUS ───

    def get_status(self) -> dict:
        return {
            "is_ready": self.is_ready,
            "has_chromadb": HAS_CHROMA,
            "total_documents": self._stats["total_documents"],
            "sources": self._stats["sources"],
            "persist_dir": str(self.persist_dir),
        }

    def reset(self) -> dict:
        """Clear the entire knowledge base"""
        if not self.is_ready or not self.client:
            return {"status": "error"}
        try:
            self.client.delete_collection("datasoul_knowledge")
            self.collection = self.client.get_or_create_collection(
                name="datasoul_knowledge",
                metadata={"description": "DataSoul intelligence knowledge base"},
            )
            self._stats = {"total_documents": 0, "sources": []}
            return {"status": "success", "message": "Knowledge base cleared"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ─── HELPERS ───

    def _extract_chunks_from_json(self, data: dict | list, source: str, prefix: str = "") -> list[dict]:
        """Recursively extract text chunks from nested JSON structures"""
        chunks = []

        if isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    chunks.extend(self._extract_chunks_from_json(item, source, f"{prefix}[{i}]"))
                elif isinstance(item, str) and len(item) > 30:
                    chunks.append({
                        "text": item,
                        "metadata": {"source": source, "type": "brain_knowledge", "path": f"{prefix}[{i}]"},
                    })

        elif isinstance(data, dict):
            # Try to create a meaningful chunk from the dict
            text_parts = []
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 10:
                    text_parts.append(f"{key}: {value}")
                elif isinstance(value, list) and all(isinstance(v, str) for v in value):
                    text_parts.append(f"{key}: {', '.join(value)}")
                elif isinstance(value, dict):
                    chunks.extend(self._extract_chunks_from_json(value, source, f"{prefix}.{key}"))
                elif isinstance(value, list):
                    chunks.extend(self._extract_chunks_from_json(value, source, f"{prefix}.{key}"))

            if text_parts:
                chunk_text = "\n".join(text_parts)
                if len(chunk_text) > 30:
                    chunks.append({
                        "text": chunk_text,
                        "metadata": {"source": source, "type": "brain_knowledge", "path": prefix or "/"},
                    })

        return chunks

    @staticmethod
    def _make_id(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()
