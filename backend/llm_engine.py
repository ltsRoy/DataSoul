"""Local LLM client — talks to Ollama via REST for narratives, chat, and corrections.
Falls back to template engine when Ollama is unavailable.
"""

import json
import asyncio
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Generator

try:
    import requests
except ImportError:
    requests = None

try:
    import httpx
except ImportError:
    httpx = None

OLLAMA_BASE = "http://localhost:11434"
_KEEP_ALIVE = "60m"
_HTTP_LIMITS = httpx.Limits(max_connections=8, max_keepalive_connections=4) if httpx else None
_CONNECT_ERRORS = tuple(
    exc for exc in [
        getattr(requests, "ConnectionError", None) if requests else None,
        getattr(httpx, "ConnectError", None) if httpx else None,
        urllib.error.URLError,
    ] if exc
)
_TIMEOUT_ERRORS = tuple(
    exc for exc in [
        getattr(requests, "Timeout", None) if requests else None,
        getattr(httpx, "TimeoutException", None) if httpx else None,
        TimeoutError,
    ] if exc
)
_LLM_TIMEOUT = 120  # seconds — Ollama on consumer hardware needs time for long generations
_CONNECT_TIMEOUT = 5  # seconds — fast-fail if Ollama isn't running


class LLMEngine:
    """Ollama-powered LLM client with graceful fallback (REST API)"""

    DEFAULT_MODEL = "qwen2.5:7b"
    FALLBACK_MODELS = [
        "qwen2.5:7b", "qwen2.5", "qwen2.5:1.5b",  # best for data tasks
        "llama3.2:3b", "llama3.2", "llama3.1", "llama3",
        "mistral", "phi3", "gemma2", "gemma3",
        "qwen2", "qwen2.5-coder", "deepseek-r1",
    ]

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
        self._available = False
        self._active_model: str | None = None
        self._model_info: dict = {}
        self._init_client()

    def _init_client(self):
        """Initialize by querying Ollama REST API for available models"""
        try:
            if httpx:
                resp = httpx.get(
                    f"{OLLAMA_BASE}/api/tags",
                    timeout=_CONNECT_TIMEOUT,
                )
            elif requests:
                resp = requests.get(
                    f"{OLLAMA_BASE}/api/tags",
                    timeout=_CONNECT_TIMEOUT,
                )
            else:
                resp = None
                data = self._urllib_json("GET", f"{OLLAMA_BASE}/api/tags")
            if resp is not None:
                resp.raise_for_status()
                data = resp.json()

            models_list = data.get("models", [])
            installed = {}
            for m in models_list:
                name = m.get("model", m.get("name", ""))
                base_name = name.split(":")[0]
                if not base_name:
                    continue
                installed[base_name] = {
                    "name": name,
                    "size": m.get("size", 0),
                    "modified": m.get("modified_at", ""),
                    "parameter_size": m.get("details", {}).get("parameter_size", ""),
                    "quantization": m.get("details", {}).get("quantization_level", ""),
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
                print(f"[LLM] Ollama ready — model: {self._active_model} "
                      f"({self._model_info.get('parameter_size', '?')}, "
                      f"{self._model_info.get('quantization', '?')})")
            else:
                print(f"[LLM] Ollama running but no models found. Run: ollama pull {self.DEFAULT_MODEL}")

        except _CONNECT_ERRORS:
            print("[LLM] Ollama not running. Start it: ollama serve")
            self._available = False
        except _TIMEOUT_ERRORS:
            print("[LLM] Ollama connection timed out")
            self._available = False
        except Exception as e:
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
            "parameter_size": self._model_info.get("parameter_size", ""),
            "quantization": self._model_info.get("quantization", ""),
        }

    # -- generation --

    async def agenerate(self, prompt: str, system: str | None = None,
                        temperature: float = 0.7, max_tokens: int = 2000,
                        timeout: int | None = None, json_mode: bool = False) -> str:
        """Generate text with the non-blocking Ollama client."""
        if not self._available:
            return ""

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._active_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "keep_alive": _KEEP_ALIVE,
        }
        if json_mode:
            payload["format"] = "json"

        try:
            if not httpx:
                return await asyncio.to_thread(self._generate_with_requests, payload, timeout)

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout or _LLM_TIMEOUT, connect=_CONNECT_TIMEOUT),
                limits=_HTTP_LIMITS,
            ) as client:
                resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")

        except _TIMEOUT_ERRORS:
            print(f"[LLM] Generation timed out after {timeout or _LLM_TIMEOUT}s")
            return ""
        except _CONNECT_ERRORS:
            print("[LLM] Ollama connection lost during generation")
            self._available = False
            return ""
        except Exception as e:
            print(f"[LLM] Generation error: {e}")
            return ""

    def _generate_with_requests(self, payload: dict, timeout: int | None = None) -> str:
        if requests:
            resp = requests.post(
                f"{OLLAMA_BASE}/api/chat",
                json=payload,
                timeout=(_CONNECT_TIMEOUT, timeout or _LLM_TIMEOUT),
            )
            resp.raise_for_status()
            data = resp.json()
        else:
            data = self._urllib_json("POST", f"{OLLAMA_BASE}/api/chat", payload, timeout or _LLM_TIMEOUT)
        return data.get("message", {}).get("content", "")

    @staticmethod
    def _urllib_json(method: str, url: str, payload: dict | None = None, timeout: int | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout or _CONNECT_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def generate(self, prompt: str, system: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 2000,
                 timeout: int | None = None, json_mode: bool = False) -> str:
        """Sync compatibility wrapper around agenerate."""
        return self._run_async(
            lambda: self.agenerate(
                prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                json_mode=json_mode,
            )
        )

    @staticmethod
    def _run_async(coro_factory):
        """Run async generation from legacy sync call sites."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro_factory())

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro_factory())).result()

    def generate_stream(self, prompt: str, system: str | None = None,
                        temperature: float = 0.7, max_tokens: int = 2000) -> Generator[str, None, None]:
        """Stream text generation token by token. Yields chunks."""
        if not self._available:
            return

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            if not httpx and requests:
                resp = requests.post(
                    f"{OLLAMA_BASE}/api/chat",
                    json={
                        "model": self._active_model,
                        "messages": messages,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                        "keep_alive": _KEEP_ALIVE,
                    },
                    timeout=(_CONNECT_TIMEOUT, _LLM_TIMEOUT),
                    stream=True,
                )
                resp.raise_for_status()
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
                return
            if not httpx:
                payload = {
                    "model": self._active_model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                    "keep_alive": _KEEP_ALIVE,
                }
                content = self._generate_with_requests(payload)
                if content:
                    yield content
                return

            with httpx.Client(timeout=httpx.Timeout(_LLM_TIMEOUT, connect=_CONNECT_TIMEOUT)) as client:
                with client.stream(
                    "POST",
                    f"{OLLAMA_BASE}/api/chat",
                    json={
                        "model": self._active_model,
                        "messages": messages,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                        "keep_alive": _KEEP_ALIVE,
                    },
                ) as resp:
                    resp.raise_for_status()

                    for line in resp.iter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

        except _TIMEOUT_ERRORS:
            print(f"[LLM] Stream timed out after {_LLM_TIMEOUT}s")
        except _CONNECT_ERRORS:
            print("[LLM] Ollama connection lost during streaming")
            self._available = False
        except Exception as e:
            print(f"[LLM] Stream error: {e}")

    # -- rag-augmented methods --

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

    # -- csv correction prompts --

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

    # -- helpers --

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
            result = self.generate("Say 'ready' in one word.", temperature=0, max_tokens=5, timeout=60)
            return bool(result)
        except Exception:
            return False


# singleton
_llm_instance: LLMEngine | None = None


def get_llm() -> LLMEngine:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMEngine()
    return _llm_instance
