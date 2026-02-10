from typing import List, Dict, Tuple
import re
import math
from pathlib import Path

from .sqlite_client import keyword_search, fetch_docs_with_path, domain_sqlite_path
from .chroma_client import semantic_search_domain
from .config import TOKEN_BUDGET, RRF_K, MAX_CONTEXTS, KNOWN_DOMAINS
from .neo4j_client import extract_course_codes, graph_doc_ids_for_codes, graph_expand_from_seed_chunks

# Simple token counter heuristic (~4 chars/token Thai)
CHAR_PER_TOKEN = 4.0

def est_tokens(text: str) -> int:
    return max(1, int(math.ceil(len(text) / CHAR_PER_TOKEN)))


def _cite_label(c: Dict) -> str:
    src = c.get('source') or c.get('path') or 'unknown'
    try:
        name = Path(str(src)).name
    except Exception:
        name = str(src)
    page = c.get('page_start')
    try:
        page_i = int(page) if page is not None else 0
    except Exception:
        page_i = 0
    return f"{name}/{page_i}"


def hybrid_retrieve(question: str, k_vec: int = 20, k_kw: int = 30) -> List[Dict]:
    return retrieve_all_domains(question, k_vec=k_vec, k_kw=k_kw)


def retrieve_all_domains(
    question: str,
    k_vec: int = 20,
    k_kw: int = 30,
    domains: List[str] | None = None,
) -> List[Dict]:
    doms = [d.strip().lower() for d in (domains or list(KNOWN_DOMAINS)) if (d or '').strip()]
    if not doms:
        doms = list(KNOWN_DOMAINS)

    bank: Dict[str, Dict] = {}
    ranks: Dict[str, float] = {}

    for dom in doms:
        try:
            results = retrieve_by_domain(question, domain=dom, k_vec=k_vec, k_kw=k_kw)
        except Exception:
            # Best-effort: if one domain is missing/corrupt, still answer from others.
            continue

        # retrieve_by_domain already returns a ranked list; fuse across domains via RRF.
        for r, d in enumerate(results, 1):
            doc_id = d.get('doc_id') or d.get('source') or f'unk_{r}'
            key = f"{dom}:{doc_id}"
            if key not in bank:
                bank[key] = {**d, 'doc_id': doc_id, 'domain': dom}
            else:
                bank[key].setdefault('domain', dom)
            ranks[key] = ranks.get(key, 0.0) + 1.0 / (RRF_K + r)

    merged = [{**bank[k], 'score_rrf': v} for k, v in ranks.items()]
    merged.sort(key=lambda x: x.get('score_rrf', 0.0), reverse=True)
    return merged[:MAX_CONTEXTS]


def retrieve_by_domain(question: str, domain: str | None, k_vec: int = 20, k_kw: int = 30) -> List[Dict]:
    dom = (domain or '').strip().lower()

    # Domain 1&2: "RAG ธรรมดา" (vector + keyword/FTS)
    if dom in ('announcements', 'regulations'):
        sqlite_path = domain_sqlite_path(dom)
        sem = semantic_search_domain(question, top_k=k_vec, domain=dom)
        kw_ids = keyword_search(question, limit=k_kw, sqlite_path=sqlite_path)
        kw_docs = fetch_docs_with_path(kw_ids, sqlite_path=sqlite_path)

        bank: Dict[str, Dict] = {}
        ranks: Dict[str, float] = {}

        for r, d in enumerate(sem, 1):
            doc_id = d.get('doc_id') or d.get('source') or f'vec_{r}'
            bank[doc_id] = d
            ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)

        for r, d in enumerate(kw_docs, 1):
            doc_id = d.get('doc_id') or f'kw_{r}'
            bank.setdefault(doc_id, d)
            ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)

        merged = [{**bank[k], 'score_rrf': v, 'doc_id': k} for k, v in ranks.items()]
        merged.sort(key=lambda x: x['score_rrf'], reverse=True)
        return merged[:MAX_CONTEXTS]

    # Domain 3: curriculum = hybrid graph (vector + keyword + Neo4j expansion)
    # If no domain was provided, keep legacy behavior (vector+keyword on default env paths)
    sqlite_path = domain_sqlite_path(dom) if dom else None

    sem = semantic_search_domain(question, top_k=k_vec, domain=dom or None)
    kw_ids = keyword_search(question, limit=k_kw, sqlite_path=sqlite_path)
    kw_docs = fetch_docs_with_path(kw_ids, sqlite_path=sqlite_path)

    # Graph expansion (best-effort; requires Neo4j + graph ingested)
    codes = sorted(extract_course_codes(question))
    graph_docs: List[Dict] = []
    if dom == 'curriculum' and codes:
        graph_ids = graph_doc_ids_for_codes(codes=codes, domain=dom, limit=max(30, MAX_CONTEXTS * 8))
        graph_docs = fetch_docs_with_path(graph_ids, sqlite_path=sqlite_path)

    # Graph neighborhood expansion from retrieved chunks (works even without course codes)
    graph_neighbor_docs: List[Dict] = []
    if dom == 'curriculum':
        seed_ids: List[str] = []
        for d in (sem[:8] + kw_docs[:8]):
            did = d.get('doc_id')
            if did and did not in seed_ids:
                seed_ids.append(did)
        if seed_ids:
            neighbor_ids = graph_expand_from_seed_chunks(seed_ids, domain=dom, window=2, limit=max(60, MAX_CONTEXTS * 8))
            graph_neighbor_docs = fetch_docs_with_path(neighbor_ids, sqlite_path=sqlite_path)

    bank: Dict[str, Dict] = {}
    ranks: Dict[str, float] = {}

    # vector ranks
    for r, d in enumerate(sem, 1):
        doc_id = d.get('doc_id') or d.get('source') or f'vec_{r}'
        bank[doc_id] = d
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)
    # keyword ranks
    credit_total_re = None
    if dom == 'curriculum' and ('หน่วยกิต' in (question or '')):
        credit_total_re = re.compile(r"จ\s*า\s*น\s*ว\s*น\s*หน่วยกิต\s*ที่\s*เรียน\s*ตลอด\s*หลักสูตร[^\d]{0,60}(\d{2,3})\s*หน่วยกิต")

    for r, d in enumerate(kw_docs, 1):
        doc_id = d.get('doc_id') or f'kw_{r}'
        bank.setdefault(doc_id, d)
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)

        # Extra boost when the chunk clearly contains the total-credits statement.
        if credit_total_re is not None:
            txt = (d.get('text') or '')
            if txt and credit_total_re.search(txt):
                ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0

    # graph ranks
    for r, d in enumerate(graph_docs, 1):
        doc_id = d.get('doc_id') or f'graph_{r}'
        bank.setdefault(doc_id, d)
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + r)

    # neighborhood ranks (slightly down-weight by shifting rank)
    for r, d in enumerate(graph_neighbor_docs, 1):
        doc_id = d.get('doc_id') or f'graphn_{r}'
        bank.setdefault(doc_id, d)
        ranks[doc_id] = ranks.get(doc_id, 0.0) + 1.0 / (RRF_K + (r + 10))

    merged = [{**bank[k], 'score_rrf': v, 'doc_id': k} for k, v in ranks.items()]
    merged.sort(key=lambda x: x['score_rrf'], reverse=True)

    if dom == 'curriculum' and graph_neighbor_docs:
        neighbor_set = {d.get('doc_id') for d in graph_neighbor_docs if d.get('doc_id')}
        # Force-include up to 2 neighbor chunks to make graph expansion observable/useful.
        must_include = min(2, MAX_CONTEXTS)
        picked: List[Dict] = []
        seen: set[str] = set()
        for m in merged:
            did = m.get('doc_id')
            if did in neighbor_set and did not in seen:
                picked.append(m)
                seen.add(did)
                if len(picked) >= must_include:
                    break
        for m in merged:
            did = m.get('doc_id')
            if did and did not in seen:
                picked.append(m)
                seen.add(did)
                if len(picked) >= MAX_CONTEXTS:
                    break
        return picked

    return merged[:MAX_CONTEXTS]


def pack_context(chunks: List[Dict], budget_tokens: int = TOKEN_BUDGET) -> Tuple[str, Dict[int, str]]:
    packed_blocks = []
    used = 0
    cites = {}
    for i, c in enumerate(chunks, 1):
        cite = _cite_label(c)
        block = f"[{cite}] {c.get('text','').strip()}"
        t = est_tokens(block)
        if used + t > budget_tokens:
            break
        packed_blocks.append(block)
        used += t
        cites[i] = cite
    return '\n\n'.join(packed_blocks), cites


def build_prompt(question: str, ctx: str, cites: Dict[int, str]) -> str:
    instruction = (
        "คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ ณ มหาวิทยาลัยไทย ตอบเป็นภาษาไทย.\n"
        "หลักการตอบ:\n"
        "1) ใช้เฉพาะข้อมูลในบริบทที่ให้ หากไม่พบให้ตอบว่า 'ไม่พบข้อมูลในเอกสาร'.\n"
        "2) ตอบโดยตรงและชัดเจน สามารถใช้รูปแบบ bullet หรือย่อหน้าตามความเหมาะสม.\n"
        "3) ห้ามเดาข้อมูลนอกรายการที่มี ใช้เฉพาะข้อมูลที่มีในบริบทเท่านั้น.\n"
        "4) หากคำถามขอ 'สรุป' หรือ 'โครงสร้าง' ให้จัดลำดับหัวข้อก่อนรายละเอียด.\n"
    )
    return (
        f"{instruction}\nคำถาม:\n{question}\n\nบริบท:\n{ctx}\n\nคำตอบ:\n"
    )


def rag_query(question: str) -> Dict:
    retrieved = retrieve_all_domains(question)
    ctx, cites = pack_context(retrieved)
    prompt = build_prompt(question, ctx, cites)
    return {
        'prompt': prompt,
        'contexts': [
            {
                'doc_id': r.get('doc_id'),
                'domain': r.get('domain'),
                'source': r.get('source'),
                'path': r.get('path'),
                'page_start': r.get('page_start'),
                'page_end': r.get('page_end'),
                'score_rrf': r.get('score_rrf'),
            } for r in retrieved
        ],
        'token_est': est_tokens(ctx)
    }


def rag_query_domain(question: str, domain: str | None) -> Dict:
    retrieved = retrieve_by_domain(question, domain=domain)
    ctx, cites = pack_context(retrieved)
    prompt = build_prompt(question, ctx, cites)
    return {
        'prompt': prompt,
        'contexts': [
            {
                'doc_id': r.get('doc_id'),
                'source': r.get('source') or (r.get('metadata') or {}).get('source'),
                'path': r.get('path') or (r.get('metadata') or {}).get('path'),
                'page_start': r.get('page_start') or (r.get('metadata') or {}).get('page_start'),
                'page_end': r.get('page_end') or (r.get('metadata') or {}).get('page_end'),
                'score_rrf': r.get('score_rrf'),
            } for r in retrieved
        ],
        'token_est': est_tokens(ctx)
    }
