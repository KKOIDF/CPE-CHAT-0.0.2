import os
import sys
import re
import json
import time
from datetime import datetime
from pathlib import Path

# Resolve repo root from this file so the script works across machines.
ROOT = Path(__file__).resolve().parents[1]
RAG_SERVICE_DIR = ROOT / 'services' / 'rag-service'
sys.path.insert(0, str(RAG_SERVICE_DIR))

from app.sqlite_client import fetch_docs_with_path, domain_sqlite_path

QUESTIONS = [
    ('curriculum', 'CPE 342 คือวิชาอะไร'),
    ('curriculum', 'LNG 220 คือวิชาอะไร'),
    ('curriculum', 'GEN 121 คือวิชาอะไร'),
    ('curriculum', 'CPE 342 อยู่ปีไหน'),
    ('curriculum', 'LNG 220 อยู่กลุ่มวิชาอะไร'),
    ('curriculum', 'GEN 121 มีกี่หน่วยกิต'),
]

FALLBACK_HINTS = ('ไม่พบข้อมูล',)


def norm_code(q: str):
    m = re.search(r'([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})', q)
    if not m:
        return None
    p, n = m.group(1).upper(), m.group(2)
    return {'spaced': f'{p} {n}', 'compact': f'{p}{n}'}


def has_code(text: str, code):
    if not text or not code:
        return False
    t = text.upper()
    return code['spaced'] in t or code['compact'] in t


def _norm_alnum(text: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', (text or '').upper())


def _code_match_loose(text: str, code) -> bool:
    if not text or not code:
        return False
    t = _norm_alnum(text)
    return code['compact'] in t


def _contexts_text(contexts: list) -> list[str]:
    out = []
    for c in contexts or []:
        parts = [
            str(c.get('text') or ''),
            str(c.get('source') or ''),
            str(c.get('path') or ''),
        ]
        out.append('\n'.join(parts))
    return out


def _hydrate_contexts_with_text(contexts: list, domain: str | None) -> list:
    if not contexts:
        return []
    ids: list[str] = []
    for c in contexts:
        did = c.get('doc_id')
        if isinstance(did, str) and did:
            ids.append(did)
    if not ids:
        return contexts

    sqlite_path = domain_sqlite_path(domain)
    docs = fetch_docs_with_path(ids, sqlite_path=sqlite_path)
    by_id = {d.get('doc_id'): d for d in docs if d.get('doc_id')}

    out: list = []
    for c in contexts:
        did = c.get('doc_id')
        if isinstance(did, str) and did in by_id:
            merged = dict(c)
            merged['text'] = by_id[did].get('text') or ''
            out.append(merged)
        else:
            out.append(c)
    return out


def run_mode(exact_on: bool):
    os.environ['RAG_CURRICULUM_EXACT_CODE_FIRST'] = '1' if exact_on else '0'

    # Ensure app-level config is reloaded with the current env for each mode.
    for m in list(sys.modules.keys()):
        if m == 'app' or m.startswith('app.'):
            del sys.modules[m]

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    rows = []
    for domain, question in QUESTIONS:
        code = norm_code(question)
        qres = client.post('/rag/query', json={'domain': domain, 'question': question})
        ares = client.post('/rag/answer', json={'domain': domain, 'question': question})

        qj = qres.json() if qres.status_code == 200 else {}
        aj = ares.json() if ares.status_code == 200 else {}
        contexts = _hydrate_contexts_with_text(qj.get('contexts') or [], domain)
        prompt = qj.get('prompt') or ''

        ctx_texts = _contexts_text(contexts)
        top1_text = ctx_texts[0] if ctx_texts else ''
        top3_text = '\n'.join(ctx_texts[:3])
        top5_text = '\n'.join(ctx_texts[:5])

        answer = (aj.get('answer') or '').strip()
        fallback = any(h in answer for h in FALLBACK_HINTS)

        rows.append({
            'question': question,
            'query_status': qres.status_code,
            'answer_status': ares.status_code,
            'contexts_n': len(contexts),
            'hit_top1_exact_code': has_code(top1_text, code),
            'hit_top3_exact_code': has_code(top3_text, code),
            'hit_top5_exact_code': has_code(top5_text, code),
            'hit_top1_loose': _code_match_loose(top1_text, code),
            'hit_top3_loose': _code_match_loose(top3_text, code),
            'hit_top5_loose': _code_match_loose(top5_text, code),
            'hit_prompt_loose': _code_match_loose(prompt, code),
            'answer_has_code': has_code(answer, code),
            'answer_is_fallback': fallback,
            'answer_is_structured': (aj.get('prompt') == '(structured curriculum answer)'),
            'top1_source': (contexts[0].get('source') if contexts else None),
            'top1_page': (contexts[0].get('page_start') if contexts else None),
            'answer_preview': answer[:200],
        })
    return rows


def summarize(rows):
    n = max(1, len(rows))
    return {
        'n': len(rows),
        'hit_top1_rate': sum(r['hit_top1_exact_code'] for r in rows) / n,
        'hit_top3_rate': sum(r['hit_top3_exact_code'] for r in rows) / n,
        'hit_top5_rate': sum(r['hit_top5_exact_code'] for r in rows) / n,
        'hit_top1_loose_rate': sum(r['hit_top1_loose'] for r in rows) / n,
        'hit_top3_loose_rate': sum(r['hit_top3_loose'] for r in rows) / n,
        'hit_top5_loose_rate': sum(r['hit_top5_loose'] for r in rows) / n,
        'hit_prompt_loose_rate': sum(r['hit_prompt_loose'] for r in rows) / n,
        'answer_has_code_rate': sum(r['answer_has_code'] for r in rows) / n,
        'non_fallback_rate': sum((not r['answer_is_fallback']) for r in rows) / n,
        'structured_answer_rate': sum(r['answer_is_structured'] for r in rows) / n,
    }


def main():
    os.environ['CPE_INDEX_ROOT'] = str(ROOT / 'indexes')
    os.environ['LLM_ENABLE'] = os.environ.get('LLM_ENABLE', '0')
    os.environ['RAG_USE_LANGCHAIN'] = '0'
    os.environ['RAG_USE_STRUCTURED_CURRICULUM'] = '0'
    os.environ['EMBED_DEVICE'] = 'cpu'
    os.environ['CUDA_VISIBLE_DEVICES'] = ''

    print('EVAL_ENV', {
        'CPE_INDEX_ROOT': os.environ.get('CPE_INDEX_ROOT'),
        'LLM_ENABLE': os.environ.get('LLM_ENABLE'),
        'RAG_USE_LANGCHAIN': os.environ.get('RAG_USE_LANGCHAIN'),
        'RAG_USE_STRUCTURED_CURRICULUM': os.environ.get('RAG_USE_STRUCTURED_CURRICULUM'),
        'EMBED_DEVICE': os.environ.get('EMBED_DEVICE'),
        'CUDA_VISIBLE_DEVICES': os.environ.get('CUDA_VISIBLE_DEVICES'),
    })

    start = time.time()
    before_rows = run_mode(False)
    after_rows = run_mode(True)

    before = summarize(before_rows)
    after = summarize(after_rows)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_json = ROOT / 'reports' / f'course_code_ab_eval_{ts}.json'
    out_md = ROOT / 'reports' / f'course_code_ab_eval_{ts}.md'
    out_json.parent.mkdir(parents=True, exist_ok=True)

    report = {
        'generated_at': ts,
        'duration_sec': round(time.time() - start, 3),
        'question_set': [q for _, q in QUESTIONS],
        'before': before,
        'after': after,
        'delta': {k: round(after[k] - before[k], 4) for k in before if k != 'n'},
        'before_rows': before_rows,
        'after_rows': after_rows,
    }
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = [
        '# Course-code A/B eval',
        '',
        f'- json: {out_json}',
        f"- duration_sec: {report['duration_sec']}",
        '',
        '## Summary',
        '',
    ]
    for k in [
        'hit_top1_rate',
        'hit_top3_rate',
        'hit_top5_rate',
        'hit_top1_loose_rate',
        'hit_top3_loose_rate',
        'hit_top5_loose_rate',
        'hit_prompt_loose_rate',
        'answer_has_code_rate',
        'non_fallback_rate',
        'structured_answer_rate',
    ]:
        lines.append(f"- {k}: before={before[k]:.3f} after={after[k]:.3f} delta={after[k]-before[k]:+.3f}")
    lines.append('')
    lines.append('## After per-question')
    lines.append('')
    for r in after_rows:
        lines.append(f"- Q: {r['question']}")
        lines.append(
            f"  hit@1={r['hit_top1_exact_code']} hit@3={r['hit_top3_exact_code']} hit@5={r['hit_top5_exact_code']} loose@5={r['hit_top5_loose']} prompt_hit={r['hit_prompt_loose']} answer_has_code={r['answer_has_code']} fallback={r['answer_is_fallback']} structured={r['answer_is_structured']}"
        )
        lines.append(f"  top1={r['top1_source']}/{r['top1_page']}")
        lines.append(f"  answer={r['answer_preview']}")
        lines.append('')
    out_md.write_text('\n'.join(lines), encoding='utf-8')

    print('AB_JSON', out_json)
    print('AB_MD', out_md)
    print('SUMMARY_BEFORE', before)
    print('SUMMARY_AFTER', after)
    print('DELTA', report['delta'])


if __name__ == '__main__':
    main()
