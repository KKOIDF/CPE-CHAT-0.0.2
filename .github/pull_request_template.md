## Summary
- Describe what changed and why.

## Validation
- [ ] Relevant tests executed
- [ ] Docs reviewed/updated if needed

## Architecture Change Checklist
- [ ] I reviewed whether this PR changes runtime topology or call flow.
- [ ] If service names/ports/flow changed, I updated `docs/backend_c2_container.puml`.
- [ ] If C2 changed, I also updated `docs/backend_c1_c4_diagram.puml` (C2 section).
- [ ] I confirmed C2 runtime source-of-truth is `docker-compose.yml`.
- [ ] I updated C1/C3/C4 diagrams if external systems, component boundaries, or class-level architecture changed.
- [ ] I ran `bash scripts/validate_arch_diagrams.sh --render` successfully.
- [ ] I verified naming conventions in `docs/diagram_conventions.md` (OpenAI-compatible, Retrieval + Generation, Optional/Offline labels).
