# DataSoul System Optimization Checklist

## Ollama / LLM Performance
- [x] Replace blocking Ollama calls with an async `httpx` client path.
- [x] Add JSON-mode support for structured Ollama requests.
- [x] Send a long `keep_alive` value with all Ollama generation requests.
- [x] Parallelize LLM column analysis with bounded concurrency.
- [x] Parallelize CSV correction LLM category/value scans where safe.

## RAG Pipeline
- [x] Add delta ingestion using file hashes.
- [x] Recursively ingest JSON, JSONL, and Markdown files from `datasoul_brain`.
- [x] Remove stale per-file chunks before re-indexing changed files.
- [x] Inject RAG guidance into LLM column cleaning prompts.
- [x] Inject RAG guidance into CSV merge/value correction prompts.

## Structured Cleaning Plans
- [x] Return strict JSON cleaning plans from the pipeline planner.
- [x] Replace substring-based imputation decisions with explicit column strategy lookup.
- [x] Preserve deterministic fallbacks when LLM/RAG is unavailable.

## Frontend Polish
- [x] Replace repetitive Ollama/AI marketing copy with precise product labels.
- [x] Keep "Scan with Ollama" visible and actionable.
- [x] Show a clear offline diagnostic message when local Ollama is unavailable.
- [x] Ensure the AI Corrector drawer opens during scans and displays loading/errors.

## Verification
- [x] Run Python syntax/import checks for backend changes.
- [x] Run frontend TypeScript checks where practical.
- [ ] Smoke-check the health page UI after frontend changes.
