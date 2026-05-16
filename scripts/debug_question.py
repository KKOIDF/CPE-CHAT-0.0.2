from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / 'services' / 'rag-service'
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.onb_rag.engine import answer_with_context, retrieve_context  # noqa: E402
from app.onb_rag.prompting import build_prompt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--question', required=True)
    parser.add_argument('--domain')
    parser.add_argument('--show-candidates', action='store_true')
    parser.add_argument('--show-context', action='store_true')
    parser.add_argument('--show-final-prompt', action='store_true')
    parser.add_argument('--show-answer', action='store_true')
    args = parser.parse_args()

    payload = retrieve_context(args.question, requested_domain=args.domain)
    print(f"question: {args.question}")
    print('query_variants:')
    for item in payload.get('query_variants') or []:
        print(f"  - {item}")
    print('candidate_domains:')
    for item in payload.get('candidate_domains') or []:
        print(f"  - {item.get('domain')}: {item.get('score')}")
    print(f"raw_vector_candidates: {len(payload.get('vector_candidates') or [])}")
    print(f"raw_keyword_candidates: {len(payload.get('keyword_candidates') or [])}")
    print(f"merged_candidates: {len(payload.get('merged_candidates') or [])}")
    print(f"selected_chunks: {len(payload.get('selected_chunks') or [])}")
    print('sources_used:')
    for item in payload.get('sources_used') or []:
        print(f"  - {item}")
    print('citation_mapping:')
    for key, value in sorted((payload.get('citation_map') or {}).items()):
        print(f"  [{key}] -> {value}")
    if args.show_candidates:
        print('selected_chunk_preview:')
        for item in payload.get('selected_chunks') or []:
            print(
                '  - '
                f"source={item.get('source_name') or item.get('source')} "
                f"domain={item.get('domain')} "
                f"score={round(float(item.get('rerank_score') or item.get('hybrid_score') or 0.0), 4)} "
                f"overlap={item.get('keyword_overlap') or 0} "
                f"section={item.get('section_heading') or '-'} "
                f"text={str(item.get('text') or '')[:140].replace(chr(10), ' ')}"
            )
    if args.show_context:
        print('formatted_context:')
        print(payload.get('formatted_context') or '')
    if args.show_final_prompt:
        print('final_system_prompt_and_user_prompt:')
        print(build_prompt(args.question, str(payload.get('formatted_context') or ''), cites=payload.get('citation_map') or {}))
    if args.show_answer:
        print('final_answer:')
        print(answer_with_context(args.question, str(payload.get('formatted_context') or ''), citation_map=payload.get('citation_map') or {}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
