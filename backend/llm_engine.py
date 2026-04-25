"""
DataSoul — LLM Engine
========================
Local LLM client using Ollama for generating intelligent narratives,
conversational Q&A, and dataset-specific insights.

Architecture:
  1. Ollama must be running locally (ollama serve)
  2. At least one model must be pulled (ollama pull llama3.2)
  3. RAG context from ChromaDB is injected into every prompt
  4. Falls back to template engine if Ollama is unavailable

Supports: streaming, multi-turn chat, RAG-augmented generation.
"""

import json
import time
from typing import Optional, Generator


class LLMEngine:
    """Ollama-powered LLM client with graceful fallback"""

    DEFAULT_MODEL = "llama3.2"
    FALLBACK_MODELS = ["llama3.1", "llama3", "mistral", "phi3", "gemma2", "qwen2", "deepseek-r1"]

    # DataSoul system persona — injected into every conversation
    SYSTEM_PERSONA = """You are **DataSoul AI** — India's premier data intelligence analyst.

RULES:
- Be concise, professional, and data-driven.
- Use Indian number formatting: lakhs (L) and crores (Cr) for large numbers.
- Format responses in clean Markdown with headers, bullet points, and tables.
- Reference specific column names, statistics, and percentages from the data provided.
- If given RAG context from the knowledge base, weave it naturally into your response.
- Never hallucinate data. If you don't have enough information, say so clearly.
- Sign off important reports with "— DataSoul AI Engine"."""

    def __init__(self, model: str | None = None):
        self.model = model or self.DEFAULT_MODEL
        self._client = None
        self._available = False
        self._active_model: str | None = None
        self._model_info: dict = {}
        self._init_client()

    def _init_client(self):
        """Initialize Ollama client and detect best model"""
        try:
            import ollama
            self._client = ollama

            # Check which models are available
            models_resp = ollama.list()
            models_list = models_resp.get("models", [])

            if not models_list:
                # Try alternate response format (newer ollama versions)
                if isinstance(models_resp, list):
                    models_list = models_resp

            installed = {}
            for m in models_list:
                name = m.get("name", "") if isinstance(m, dict) else str(m)
                base_name = name.split(":")[0]
                installed[base_name] = {
                    "name": name,
                    "size": m.get("size", 0) if isinstance(m, dict) else 0,
                    "modified": m.get("modified_at", "") if isinstance(m, dict) else "",
                }

            # Priority: exact match → fallback chain → any installed model
            if self.model in installed:
                self._active_model = installed[self.model]["name"]
                self._model_info = installed[self.model]
                self._available = True
            else:
                for fb in self.FALLBACK_MODELS:
                    if fb in installed:
                        self._active_model = installed[fb]["name"]
                        self._model_info = installed[fb]
                        self._available = True
                        break

                if not self._available and installed:
                    first_key = next(iter(installed))
                    self._active_model = installed[first_key]["name"]
                    self._model_info = installed[first_key]
                    self._available = True

            if self._available:
                print(f"[LLM] Ollama ready -- model: {self._active_model}")
            else:
                print(f"[LLM] Ollama running but no models found. Run: ollama pull {self.DEFAULT_MODEL}")

        except Exception as e:
            error_msg = str(e)
            if "refused" in error_msg.lower() or "connect" in error_msg.lower():
                print(f"[LLM] Ollama not running. Start it: ollama serve")
            else:
                print(f"[LLM] Ollama not available: {e}")
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def get_status(self) -> dict:
        return {
            "available": self._available,
            "model": self._active_model,
            "preferred_model": self.model,
            "engine": "ollama",
            "model_size": self._model_info.get("size", 0),
        }

    # ─── CORE GENERATION ───

    def generate(self, prompt: str, system: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """Generate text from a prompt. Returns empty string if LLM unavailable."""
        if not self._available or not self._client:
            return ""

        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = self._client.chat(
                model=self._active_model,
                messages=messages,
                options={"temperature": temperature, "num_predict": max_tokens, "num_gpu": 0},
            )

            content = ""
            if isinstance(response, dict):
                content = response.get("message", {}).get("content", "")
            return content

        except Exception as e:
            print(f"[LLM] Generation error: {e}")
            return ""

    def generate_stream(self, prompt: str, system: str | None = None,
                        temperature: float = 0.7, max_tokens: int = 2000) -> Generator[str, None, None]:
        """Stream text generation token by token. Yields chunks."""
        if not self._available or not self._client:
            return

        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            stream = self._client.chat(
                model=self._active_model,
                messages=messages,
                options={"temperature": temperature, "num_predict": max_tokens, "num_gpu": 0},
                stream=True,
            )

            for chunk in stream:
                if isinstance(chunk, dict):
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token

        except Exception as e:
            print(f"[LLM] Stream error: {e}")

    # ─── RAG-AUGMENTED METHODS ───

    def generate_narrative(self, profile: dict, threats: dict,
                           df_summary: dict, rag_context: str = "") -> str:
        """Generate an executive narrative using LLM + RAG context"""

        health = profile.get("quality_score", {})
        sector = profile.get("sector", {}).get("sector_name", "General")

        prompt = f"""Generate an executive data intelligence report for this dataset.

## DATASET FACTS (use these exact numbers):
- **Records**: {df_summary.get('rows', 0):,} rows × {df_summary.get('cols', 0)} dimensions
- **Sector**: {sector}
- **Health Score**: {health.get('overall', 0)}/100 (Grade: {health.get('grade', 'N/A')})

## QUALITY DIMENSIONS:
{json.dumps(health.get('dimensions', {}), indent=2)}

## THREATS ({threats.get('total', 0)} total — {threats.get('critical', 0)} critical, {threats.get('warning', 0)} medium):
{chr(10).join(f"- [{t['severity'].upper()}] {t['title']}: {t.get('impact', '')[:120]}" for t in threats.get('threats', [])[:6])}

## KEY STATISTICS:
{json.dumps(df_summary.get('numeric_summary', {}), indent=2, default=str)}

{self._format_rag_section(rag_context)}

## INSTRUCTIONS:
Write a professional executive narrative in Markdown. Include:
1. **Opening** — one-line verdict on data readiness
2. **📈 Key Metrics** — financial/operational KPIs with Indian formatting (₹, lakhs, crores)
3. **🛡️ Threat Summary** — prioritized by severity
4. **🎯 Quality Dimensions** — table with scores
5. **✅ Action Plan** — 3-4 concrete next steps
6. **💰 ROI** — analyst hours saved, threats caught

Keep it under 500 words. Be direct and data-driven."""

        return self.generate(prompt, system=self.SYSTEM_PERSONA, temperature=0.4, max_tokens=2500)

    def generate_narrative_stream(self, profile: dict, threats: dict,
                                   df_summary: dict, rag_context: str = "") -> Generator[str, None, None]:
        """Stream the executive narrative generation"""

        health = profile.get("quality_score", {})
        sector = profile.get("sector", {}).get("sector_name", "General")

        prompt = f"""Generate an executive data intelligence report for this dataset.

## DATASET:
- {df_summary.get('rows', 0):,} rows × {df_summary.get('cols', 0)} dimensions | Sector: {sector}
- Health: {health.get('overall', 0)}/100 (Grade: {health.get('grade', 'N/A')})

## THREATS: {threats.get('total', 0)} total ({threats.get('critical', 0)} critical)
{chr(10).join(f"- [{t['severity'].upper()}] {t['title']}" for t in threats.get('threats', [])[:5])}

## STATISTICS:
{json.dumps(df_summary.get('numeric_summary', {}), indent=2, default=str)}

{self._format_rag_section(rag_context)}

Write a concise executive narrative in Markdown with: metrics (₹ lakhs/crores), threats, quality dimensions, action plan. Under 400 words."""

        yield from self.generate_stream(prompt, system=self.SYSTEM_PERSONA, temperature=0.4, max_tokens=2500)

    def answer_question(self, question: str, df_context: str,
                        profile: dict, rag_context: str = "") -> str:
        """Answer a conversational question about the dataset using LLM + RAG"""

        system = self.SYSTEM_PERSONA + """

ADDITIONAL RULES FOR Q&A:
- Answer the user's specific question — don't give a generic overview unless asked.
- If the question is about a specific column, provide exact statistics.
- If you use RAG knowledge, cite it naturally: "According to DataSoul's knowledge base..."
- Keep answers focused: 100-300 words unless a detailed analysis is requested."""

        prompt = f"""## USER QUESTION:
{question}

## DATASET CONTEXT:
{df_context}

## PROFILE SUMMARY:
- Rows: {profile.get('overview', {}).get('rows', '?')}
- Columns: {profile.get('overview', {}).get('cols', '?')}
- Health: {profile.get('quality_score', {}).get('overall', '?')}/100
- Missing: {profile.get('overview', {}).get('total_missing_pct', '?')}%

{self._format_rag_section(rag_context)}

Answer the question directly and specifically."""

        return self.generate(prompt, system=system, temperature=0.3, max_tokens=1500)

    def answer_question_stream(self, question: str, df_context: str,
                                profile: dict, rag_context: str = "") -> Generator[str, None, None]:
        """Stream answer to a conversational question"""

        system = self.SYSTEM_PERSONA + "\nAnswer concisely. Use Markdown. Cite specific data."

        prompt = f"""Question: {question}

Dataset: {df_context}

Health: {profile.get('quality_score', {}).get('overall', '?')}/100 | {profile.get('overview', {}).get('rows', '?')} rows

{self._format_rag_section(rag_context)}

Answer:"""

        yield from self.generate_stream(prompt, system=system, temperature=0.3, max_tokens=1500)

    # ─── CSV CORRECTION PROMPTS ───

    def correct_values(self, column_name: str, sample_values: list[str],
                       context: str = "") -> str:
        """Prompt optimized for value correction in CSV columns."""
        if not self._available:
            return ""

        prompt = f"""Analyze these values from column "{column_name}" and identify errors.

VALUES: {json.dumps(sample_values[:30])}

{f"CONTEXT: {context[:500]}" if context else ""}

For each error, suggest the correction. Be specific and concise.
Format: "wrong_value" → "correct_value" (reason)
If no errors, say "No errors detected."
"""
        return self.generate(prompt, system=self.SYSTEM_PERSONA, temperature=0.1, max_tokens=600)

    def interpret_prediction(self, prediction_results: dict,
                              column_name: str, context: str = "") -> str:
        """Explain ML prediction results in plain English."""
        if not self._available:
            return ""

        prompt = f"""Interpret these ML prediction results for a data analyst (2-3 sentences):

Column: {column_name}
Model: {prediction_results.get('model', 'Unknown')}
Score: {prediction_results.get('train_score', 'N/A')}
Key drivers: {json.dumps(prediction_results.get('feature_importance', {}), default=str)}
Predictions summary: {json.dumps(prediction_results.get('stats', {}), default=str)}

{f"Domain context: {context[:300]}" if context else ""}

Be specific about what drives the predictions and how reliable they are."""

        return self.generate(prompt, system=self.SYSTEM_PERSONA, temperature=0.3, max_tokens=300)

    def suggest_corrections_batch(self, issues_batch: list[dict]) -> str:
        """Batch multiple correction requests for efficiency."""
        if not self._available:
            return ""

        issues_text = "\n".join(
            f"{i+1}. Column '{iss.get('column', '?')}': {iss.get('description', '')}"
            for i, iss in enumerate(issues_batch[:10])
        )

        prompt = f"""Review these data quality issues and suggest specific fixes:

{issues_text}

For each issue, give a ONE-LINE actionable recommendation.
Format your response as a numbered list matching the inputs."""

        return self.generate(prompt, system=self.SYSTEM_PERSONA, temperature=0.2, max_tokens=500)

    # ─── HELPERS ───

    @staticmethod
    def _format_rag_section(rag_context: str) -> str:
        """Format RAG context for prompt injection"""
        if not rag_context or "No relevant knowledge" in rag_context:
            return ""
        return f"""## KNOWLEDGE BASE CONTEXT (from DataSoul RAG):
{rag_context[:2000]}

Use this context to enrich your response where relevant."""

    def warmup(self) -> bool:
        """Warmup the model with a simple query to load it into memory"""
        if not self._available:
            return False
        try:
            result = self.generate("Say 'ready' in one word.", temperature=0, max_tokens=5)
            return bool(result)
        except Exception:
            return False


# ─── Singleton instance ───
_llm_instance: LLMEngine | None = None


def get_llm() -> LLMEngine:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMEngine()
    return _llm_instance
