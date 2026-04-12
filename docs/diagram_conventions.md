# Diagram Conventions (Backend Architecture)

This document defines shared conventions for backend architecture diagrams in `docs/*.puml`.

## Scope
- Applies to C1, C2, C3, C4 backend diagrams.
- Primary files:
- `docs/backend_c1_context.puml`
- `docs/backend_c2_container.puml`
- `docs/backend_c3_ingestion.puml`
- `docs/backend_c3_rag.puml`
- `docs/backend_c4_code.puml`
- `docs/backend_c1_c4_diagram.puml` (combined view)

## Term Definitions
- `Optional`: Feature/path that may be enabled by configuration or environment; system must still function without it.
- `Offline`: Non-request path, usually batch/CLI operation (for example ingestion jobs), not part of interactive runtime request flow.
- `External`: System outside this repository/runtime boundary (for example OCR provider, LLM provider).
- `Runtime Path`: Request-serving path active in deployed runtime topology (for this project: OpenWeb-UI -> RAG `/v1` API).

## Naming Rules
- Use `OpenAI-compatible` (with hyphen), not `OpenAI compatible`.
- Use `Retrieval + Generation` for RAG pipeline summary labels.
- Use `FastAPI Entry Point` for service entrypoint component naming.
- Use `(Optional)` suffix in labels for optional subsystems.
- Use `(Offline)` suffix in labels for batch/non-runtime flows.

## Source Of Truth
- C2 runtime topology source of truth is `docker-compose.yml`.
- When service names, ports, or call flow change in `docker-compose.yml`, C2 diagrams must be updated in the same PR.
- If runtime behavior and C2 diverge, treat `docker-compose.yml` as authoritative and patch diagrams immediately.

## Change Policy
- Any PR that changes architecture-relevant behavior should update affected diagrams:
- Service/container name changes
- New external dependencies (LLM/OCR/DB/etc.)
- Runtime path changes (routing, API flow)
- Optional/offline path enablement changes

## Validation And Rendering
- Run syntax check and SVG rendering for all PUML files:

```bash
bash scripts/validate_arch_diagrams.sh --render
```

- Rendered output is written to `docs/rendered/`.
